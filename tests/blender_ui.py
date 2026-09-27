"""Run in a fresh foreground Blender with --enable-event-simulate.

Verifies the actual modal event loop, undo, and Esc cancellation, then exits
that test Blender instance. It never opens or saves a user project.
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vox_ui_test', ROOT / '__init__.py',
                                            submodule_search_locations=[str(ROOT)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()
OUTPUT = Path(tempfile.mkdtemp(prefix='vox-ui-test-'))
state = {'phase': 'start', 'started': time.monotonic()}


def select():
    bpy.ops.object.select_all(action='DESELECT')
    for name in ('Batch_A', 'Batch_B'):
        bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects['Batch_A']


def tick():
    try:
        if time.monotonic() - state['started'] > 90:
            raise TimeoutError('Modal batch did not finish within 90 seconds')
        window = bpy.context.window_manager.windows[0]
        area = next(area for area in window.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(window=window, area=area, region=region):
            if state['phase'] == 'start':
                bpy.ops.object.select_all(action='SELECT')
                bpy.ops.object.delete(use_global=False)
                for name in ('Batch_A', 'Batch_B'):
                    bpy.ops.mesh.primitive_cube_add()
                    obj = bpy.context.object
                    obj.name = name
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.subdivide(number_cuts=3)
                    bpy.ops.object.mode_set(mode='OBJECT')
                select()
                settings = bpy.context.scene.vox_tool
                settings.BatchWorkers = 2
                settings.BakeTex = False
                settings.CreateBackup = False
                settings.ExportLocation = str(OUTPUT)
                state['initial'] = len(bpy.data.objects['Batch_A'].data.vertices)
                bpy.ops.ed.undo_push(message='Before Vox batch')
                assert bpy.ops.voxcleaner.lazyclean('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
                state['phase'] = 'cleaning'
            elif state['phase'] == 'cleaning' and addon.batch.ACTIVE is None:
                assert len(addon.batch.LAST_REPORT['completed']) == 2, addon.batch.LAST_REPORT
                assert len(bpy.data.objects['Batch_A'].data.vertices) < state['initial']
                assert bpy.ops.ed.undo() == {'FINISHED'}
                assert len(bpy.data.objects['Batch_A'].data.vertices) == state['initial'], 'Batch undo failed'
                select()
                assert bpy.ops.voxcleaner.exportobj('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
                state['phase'] = 'exporting'
            elif state['phase'] == 'exporting' and addon.batch.ACTIVE is None:
                assert len(addon.batch.LAST_REPORT['completed']) == 2, addon.batch.LAST_REPORT
                assert len(list(OUTPUT.glob('*.obj'))) == 2
                select()
                assert bpy.ops.voxcleaner.lazyclean('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
                window.event_simulate(type='ESC', value='PRESS')
                state['phase'] = 'cancelling'
            elif state['phase'] == 'cancelling' and addon.batch.ACTIVE is None:
                assert addon.batch.LAST_REPORT['cancelled'], addon.batch.LAST_REPORT
                assert len(bpy.data.objects['Batch_A'].data.vertices) == state['initial']
                result = dict(ok=True, blender=bpy.app.version_string, checks=['modal clean', 'undo', 'modal export', 'Esc cancellation'])
                (OUTPUT / 'report.json').write_text(json.dumps(result))
                print('VOX_UI_PASS', str(OUTPUT), json.dumps(result), flush=True)
                bpy.ops.wm.quit_blender()
                return None
        return 0.1
    except Exception:
        error = traceback.format_exc()
        (OUTPUT / 'error.txt').write_text(error)
        print('VOX_UI_FAIL', str(OUTPUT), error, flush=True)
        if addon.batch.ACTIVE:
            addon.batch.ACTIVE.stop()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=1)
