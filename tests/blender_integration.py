"""blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py

Uses generated VOX 150/200 fixtures. Optionally also imports the local 0.99.6
distribution's examples when VOX_SAMPLES_DIR points to its vox directory.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT))
from test_vox_format import chunk, dictionary, ints, model, shape, trn, vox

spec = importlib.util.spec_from_file_location('vox_integration', ROOT / '__init__.py',
                                            submodule_search_locations=[str(ROOT)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()
OUTPUT = Path(tempfile.mkdtemp(prefix='vox-integration-'))
reports = []


def select(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def reset():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.scene.vox_tool.CommonUV = False
    bpy.context.scene.vox_tool.CreateBackup = False
    bpy.context.scene.vox_tool.CleanGeo = True
    bpy.context.scene.vox_tool.BakeTex = True
    bpy.context.scene.cycles.samples = 1
    bpy.context.scene.cycles.device = 'CPU'


def fixture(name, version=150):
    colors = bytes((255, 0, 0, 255, 0, 255, 0, 255)) + bytes((255, 255, 255, 255)) * 254
    voxels = [(x, y, z, 1 if x < 2 else 2) for x in range(4) for y in range(4) for z in range(4)]
    path = OUTPUT / (name + '.vox')
    path.write_bytes(vox(model(voxels, (4, 4, 4)) + chunk(b'RGBA', colors) +
                        (trn() + shape() if version == 200 else b''), version))
    assert bpy.ops.voxcleaner.importvox(filepath=str(path)) == {'FINISHED'}
    return bpy.context.active_object


def check_batch(operation, count):
    report = addon.batch.LAST_REPORT
    assert report['operation'] == operation, report
    assert len(report['completed']) == count and not report['errors'], report
    assert report['peak_workers'] == min(count, 2), report
    reports.append(report)


def assert_pixels(obj):
    image = obj.data.materials[0].node_tree.nodes['Color'].image
    assert image.packed_file and min(image.size) > 0
    values = list(image.pixels)
    colors = list(zip(values[0::4], values[1::4], values[2::4]))
    assert any(r > 0.8 and g < 0.1 for r, g, b in colors), 'Red color lost during bake'
    assert any(g > 0.8 and r < 0.1 for r, g, b in colors), 'Green color lost during bake'
    return image


def run():
    reset()
    settings = bpy.context.scene.vox_tool
    settings.BatchWorkers = 2
    settings.OriginsAtBottom = False
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / 'source.blend'))
    settings.ExportLocation = '//'
    objs = [fixture('old', 150), fixture('new', 200)]
    objs[0].name, objs[1].name = 'Same/Name', 'Same\\Name'
    # Preserve parent transforms, object identity, custom properties, shared meshes,
    # selection and external material users across a parallel clean.
    parent = bpy.data.objects.new('Parent', None)
    bpy.context.scene.collection.objects.link(parent)
    parent.location = (3, 4, 5)
    parent.rotation_euler = (0.1, 0.2, 0.3)
    objs[0].parent = parent
    objs[0].location = (1, 2, 3)
    objs[1].location = (-2, 0, 1)
    objs[0]['keep'] = 42
    untouched = objs[0].copy()
    bpy.context.scene.collection.objects.link(untouched)
    source_mesh = objs[0].data
    bpy.context.view_layer.update()
    matrices = [obj.matrix_world.copy() for obj in objs]
    ids = [obj.as_pointer() for obj in objs]
    initial = [len(obj.data.vertices) for obj in objs]
    original_material = source_mesh.materials[0]
    links = [(link.from_node.name, link.to_socket.name) for link in original_material.node_tree.links]
    select(objs)
    settings.CreateBackup = True
    engine = bpy.context.scene.render.engine
    assert bpy.ops.voxcleaner.lazyclean() == {'FINISHED'}
    check_batch('clean', 2)
    assert objs[0]['keep'] == 42 and objs[0].parent == parent
    assert [obj.as_pointer() for obj in objs] == ids
    assert set(bpy.context.selected_objects) == set(objs)
    assert bpy.context.active_object == objs[0]
    assert bpy.context.scene.render.engine == engine
    assert untouched.data == source_mesh and len(source_mesh.vertices) == initial[0]
    assert links == [(link.from_node.name, link.to_socket.name) for link in original_material.node_tree.links]
    assert len(bpy.data.collections['Vox Cleaner Backups'].objects) == 2
    for obj, before, matrix in zip(objs, initial, matrices):
        assert len(obj.data.vertices) < before
        assert obj.matrix_world == matrix
        assert_pixels(obj)
    # Read OBJ contents: one file per mesh, unique sanitized names, material/PNG
    # references and actual world coordinates (including the parent transform).
    assert bpy.ops.voxcleaner.exportobj() == {'FINISHED'}
    check_batch('obj', 2)
    names = addon.batch.safe_names(obj.name for obj in objs)
    for obj in objs:
        path = OUTPUT / (names[obj.name] + '.obj')
        content = path.read_text()
        verts = [tuple(map(float, line.split()[1:])) for line in content.splitlines() if line.startswith('v ')]
        expected = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        # Blender Z-up -> OBJ Y-up.
        expected = [(v.x, v.z, -v.y) for v in expected]
        for axis in range(3):
            assert abs(min(v[axis] for v in verts) - min(v[axis] for v in expected)) < 1e-4
            assert abs(max(v[axis] for v in verts) - max(v[axis] for v in expected)) < 1e-4
        mtl = path.with_suffix('.mtl').read_text()
        assert 'map_Kd' in mtl
        for line in mtl.splitlines():
            if line.startswith('map_Kd '):
                assert (OUTPUT / line[7:]).is_file(), line
    assert bpy.ops.voxcleaner.exportfbx() == {'FINISHED'}
    check_batch('fbx', 2)
    for obj in objs:
        path = OUTPUT / (names[obj.name] + '.fbx')
        assert path.read_bytes().startswith(b'Kaydara FBX Binary')
    # Shared texture exports should produce one PNG per image, without worker races.
    settings.CreateBackup = False
    select(objs)
    image = assert_pixels(objs[0])
    objs[1].data.materials.clear()
    objs[1].data.materials.append(objs[0].data.materials[0])
    assert addon.VoxMethods.TextureExport(bpy.context) == 5

    # One failed object must not roll back the successful object or leave busy state.
    reset()
    good = fixture('good')
    empty = bpy.data.objects.new('empty', bpy.data.meshes.new('empty'))
    bpy.context.scene.collection.objects.link(empty)
    select([good, empty])
    assert bpy.ops.voxcleaner.lazyclean() == {'FINISHED'}
    report = addon.batch.LAST_REPORT
    assert len(report['completed']) == 1 and len(report['errors']) == 1
    assert len(empty.data.vertices) == 0 and addon.batch.ACTIVE is None
    assert not addon.FlowData.ProcessRunning
    assert_pixels(good)
    reports.append(report)

    # Cancellation before results are applied leaves both source meshes intact.
    reset()
    objs = [fixture('cancel_a'), fixture('cancel_b')]
    select(objs)
    meshes = [obj.data for obj in objs]
    run = addon.batch.BatchRun(bpy.context, 'clean', objs, addon)
    run.tick()
    processes = [job['process'] for job in run.running]
    assert processes
    run.stop()
    run.close()
    assert all(process.poll() is not None for process in processes)
    assert [obj.data for obj in objs] == meshes

    # Existing single-object, Shared UV and manual 2-step workflows still work.
    reset()
    single = fixture('single')
    select([single])
    scene = bpy.context.scene
    scene.render.bake.margin = 11
    scene.render.bake.use_clear = True
    scene.cycles.device = 'CPU'
    engine = scene.render.engine
    assert bpy.ops.voxcleaner.lazyclean() == {'FINISHED'}
    assert_pixels(single)
    assert scene.render.engine == engine and scene.render.bake.margin == 11 and scene.render.bake.use_clear
    assert bpy.ops.voxcleaner.exportobj() == {'FINISHED'}
    assert bpy.ops.voxcleaner.exportfbx() == {'FINISHED'}
    # Meshes without color attributes and the Blender 5.2 POINT -> CORNER path.
    reset()
    bpy.ops.mesh.primitive_cube_add()
    plain = bpy.context.object
    # --factory-startup still loads user preferences, so explicitly disable GPU
    # devices in this isolated test process to exercise the CPU fallback.
    bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'NONE'
    scene.cycles.device = 'GPU'
    assert bpy.ops.voxcleaner.lazyclean() == {'FINISHED'}
    assert plain.data.materials[0].node_tree.nodes['Color'].image.packed_file
    assert scene.cycles.device == 'GPU'
    reset()
    bpy.ops.mesh.primitive_cube_add()
    colored = bpy.context.object
    attribute = colored.data.color_attributes.new(name='Color', type='BYTE_COLOR', domain='POINT')
    for value in attribute.data:
        value.color = (1, 0, 0, 1)
    addon.VoxMethods.MrModelTypeChecker([colored])
    assert colored.data.color_attributes['Color'].domain == 'CORNER'
    assert colored.data.color_attributes['Color'].data_type == 'FLOAT_COLOR'
    reset()
    objs = [fixture('shared_a'), fixture('shared_b')]
    objs[1].location.x = 2
    select(objs)
    settings.CommonUV = True
    assert bpy.ops.voxcleaner.lazyclean() == {'FINISHED'}
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(meshes) == 2
    assert len({assert_pixels(obj) for obj in meshes}) == 1
    reset()
    single = fixture('manual')
    select([single])
    assert bpy.ops.voxcleaner.prepareforbake() == {'FINISHED'}
    assert bpy.ops.voxcleaner.postuvbake() == {'FINISHED'}
    assert bpy.ops.voxcleaner.terminate() == {'FINISHED'}
    assert_pixels(single)
    assert not addon.FlowData.ProcessRunning

    samples = os.environ.get('VOX_SAMPLES_DIR')
    if samples:
        reset()
        objs = []
        for name in ('3x3x3.vox', '8x8x8.vox', 'chr_knight.vox'):
            assert bpy.ops.voxcleaner.importvox(filepath=str(Path(samples) / name)) == {'FINISHED'}
            objs.extend(bpy.context.selected_objects)
        select(objs)
        assert bpy.ops.voxcleaner.lazyclean() == {'FINISHED'}
        check_batch('clean', 3)
        assert bpy.ops.voxcleaner.exportobj() == {'FINISHED'}
        check_batch('obj', 3)
        assert bpy.ops.voxcleaner.exportfbx() == {'FINISHED'}
        check_batch('fbx', 3)
    addon.unregister()
    addon.register()
    addon.unregister()
    result = {'blender': bpy.app.version_string, 'output': str(OUTPUT), 'batches': reports}
    (OUTPUT / 'report.json').write_text(json.dumps(result, indent=2))
    print('VOX_INTEGRATION_PASS ' + json.dumps(result), flush=True)


run()
