"""Entry point for a single isolated Blender job. Invoked only by batch.py."""
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

import bpy


def run(job):
    root = Path(job['addon'])
    spec = importlib.util.spec_from_file_location(
        'vox_cleaner_worker_addon', root / '__init__.py',
        submodule_search_locations=[str(root)])
    addon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = addon
    spec.loader.exec_module(addon)
    addon.register()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    with bpy.data.libraries.load(job['input'], link=False) as (source, target):
        target.objects = [job['object']]
    obj = target.objects[0]
    # Library dependencies can include parents and modifier targets. They must
    # participate in the depsgraph for exports to retain the correct transform.
    for dependency in list(bpy.data.objects):
        if dependency.name not in bpy.context.scene.objects:
            bpy.context.scene.collection.objects.link(dependency)
    obj.hide_set(False)
    obj.hide_viewport = False
    obj.hide_select = False
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # Preserve the original world transform, including unlinked parent dependencies.
    bpy.context.view_layer.update()
    settings = bpy.context.scene.vox_tool
    for name, value in job['settings'].items():
        setattr(settings, name, value)
    settings.CommonUV = False
    settings.CreateBackup = False  # The live scene creates its backup on successful import.
    bpy.context.scene.render.threads_mode = 'FIXED'
    bpy.context.scene.render.threads = job['threads']
    bpy.context.scene.cycles.device = 'CPU'
    started = time.time()
    if job['operation'] == 'clean':
        if not obj.data.polygons:
            raise ValueError('Mesh has no faces')
        before = len(obj.data.vertices)
        result = bpy.ops.voxcleaner.lazyclean()
        if result != {'FINISHED'}:
            raise RuntimeError(f'Cleaning returned {result}')
        bpy.data.libraries.write(job['output'], {obj.data}, path_remap='ABSOLUTE')
        return dict(mesh=obj.data.name, vertices_before=before, vertices_after=len(obj.data.vertices),
                    started=started, finished=time.time())
    addon.export_one(bpy.context, obj, job['operation'], job['export_name'])
    return dict(started=started, finished=time.time())


if __name__ == '__main__':
    job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
    try:
        result = {'ok': True, **run(job)}
    except Exception as error:
        result = {'ok': False, 'error': str(error)}
        traceback.print_exc()
    Path(job['status']).write_text(json.dumps(result), encoding='utf-8')
    if not result['ok']:
        raise SystemExit(1)
