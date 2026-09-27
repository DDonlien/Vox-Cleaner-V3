"""Run in a fresh background Blender; VOX_SAMPLES_DIR must contain chr_knight.vox."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import bpy

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vox_benchmark', root / '__init__.py',
                                            submodule_search_locations=[str(root)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()
settings = bpy.context.scene.vox_tool
settings.OriginsAtBottom = False
settings.CreateBackup = False
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
sample = Path(os.environ['VOX_SAMPLES_DIR']) / 'chr_knight.vox'
assert bpy.ops.voxcleaner.importvox(filepath=str(sample)) == {'FINISHED'}
original = bpy.context.active_object
source = original.data.copy()
objects = [original]
for _ in range(3):
    obj = original.copy()
    obj.data = source.copy()
    bpy.context.scene.collection.objects.link(obj)
    objects.append(obj)
results = []
for workers in (1, 2):
    settings.BatchWorkers = workers
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.data = source.copy()
        obj.select_set(True)
    bpy.context.view_layer.objects.active = original
    started = time.perf_counter()
    assert bpy.ops.voxcleaner.lazyclean() == {'FINISHED'}
    elapsed = time.perf_counter() - started
    assert len(addon.batch.LAST_REPORT['completed']) == 4
    results.append(dict(workers=workers, seconds=elapsed,
                        vertices=[len(obj.data.vertices) for obj in objects]))
print('VOX_BENCH ' + json.dumps(results), flush=True)
