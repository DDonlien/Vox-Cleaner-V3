"""Run with python3 -m unittest discover -s tests -v (no Blender required)."""
import struct
import tempfile
from pathlib import Path
import unittest

from vox_format import read_vox, VoxFormatError, default_palette


def ints(*values):
    return struct.pack('<' + 'i' * len(values), *values)


def dictionary(values=None):
    values = values or {}
    result = ints(len(values))
    for key, value in values.items():
        for item in (key, str(value)):
            encoded = item.encode('utf-8')
            result += ints(len(encoded)) + encoded
    return result


def chunk(name, content=b'', children=b''):
    return name + ints(len(content), len(children)) + content + children


def model(voxels=((0, 0, 0, 1),), size=(2, 2, 2)):
    return chunk(b'SIZE', ints(*size)) + chunk(b'XYZI', ints(len(voxels)) + b''.join(bytes(v) for v in voxels))


def vox(content, version=150):
    return b'VOX ' + ints(version) + chunk(b'MAIN', children=content)


def trn(node=0, child=1, layer=-1, attrs=None, frames=None):
    frames = frames or [{}]
    return chunk(b'nTRN', ints(node) + dictionary(attrs) + ints(child, -1, layer, len(frames)) + b''.join(dictionary(f) for f in frames))


def shape(node=1, models=((0, {}),)):
    return chunk(b'nSHP', ints(node) + dictionary() + ints(len(models)) + b''.join(ints(i) + dictionary(a) for i, a in models))


class FormatTests(unittest.TestCase):
    def parse(self, content, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.vox'
            path.write_bytes(content)
            return read_vox(path, **kwargs)

    def test_legacy_without_scene_or_palette(self):
        data = self.parse(vox(model()))
        self.assertEqual(data['version'], 150)
        self.assertEqual(len(data['instances']), 1)
        self.assertEqual(data['palette'][0], [1, 1, 1, 1])
        self.assertEqual(len(data['palette']), 255)

    def test_default_palette_order_and_ramps(self):
        palette = default_palette()
        self.assertEqual(palette[1], [1, 1, 0.8, 1])
        self.assertEqual(palette[215], [238 / 255, 0, 0, 1])
        self.assertEqual(palette[-1], [17 / 255] * 3 + [1])

    def test_legacy_pack_and_custom_palette(self):
        palette = bytes((12, 34, 56, 255)) * 256
        data = self.parse(vox(chunk(b'PACK', ints(2)) + model() * 2 + chunk(b'RGBA', palette)))
        self.assertEqual(len(data['instances']), 2)
        self.assertEqual(data['palette'][0], [12 / 255, 34 / 255, 56 / 255, 1])

    def test_scene_150_and_200_and_missing_layer(self):
        for version in (150, 200):
            data = self.parse(vox(model() + trn(node=7, child=9, layer=12,
                attrs={'_hidden': 0, '_name': '模型'}, frames=[{'_t': '10 20 30', '_r': 4}]) + shape(node=9), version))
            _, name, visible, matrix = data['instances'][0]
            self.assertEqual(name, '模型')
            self.assertTrue(visible)
            self.assertEqual([row[3] for row in matrix[:3]], [10, 20, 30])

    def test_layer_visibility_value(self):
        for flag in (0, 1):
            layer = chunk(b'LAYR', ints(2) + dictionary({'_hidden': flag}) + ints(-1))
            data = self.parse(vox(model() + trn(layer=2) + shape() + layer))
            self.assertEqual(data['instances'][0][2], flag == 0)

    def test_animated_records_consume_model_dicts(self):
        data = self.parse(vox(model() * 2 + trn(frames=[{'_f': 10, '_t': '5 0 0'}, {'_f': 0}]) +
            shape(models=((1, {'_f': 10}), (0, {'_f': 0})))))
        self.assertEqual(data['instances'][0][0], 0)
        self.assertEqual(data['instances'][0][3][0][3], 0)

    def test_material_keys_are_order_independent(self):
        material = chunk(b'MATL', ints(1) + dictionary({'_rough': 0.2, '_alpha': 0.4, '_type': '_glass'}))
        data = self.parse(vox(model() + material))
        self.assertEqual(data['materials'][0], [0.2, 0, 0, 0.4])
        self.assertEqual(self.parse(vox(model() + material), max_maps=True)['materials'][0][3], 1)

    def test_legacy_matt(self):
        material = chunk(b'MATT', struct.pack('<iifif', 1, 1, 0.8, 2, 0.3))
        data = self.parse(vox(model() + material))
        self.assertAlmostEqual(data['materials'][0][0], 0.3)
        self.assertAlmostEqual(data['materials'][0][1], 0.8)

    def test_unknown_chunks_and_nested_lengths(self):
        self.assertEqual(len(self.parse(vox(chunk(b'NEW!', b'ignored', model())))['models']), 1)

    def test_rejects_malformed_input(self):
        cases = [b'', vox(model())[:-1], vox(model(), 99), vox(chunk(b'XYZI', ints(0))),
                 vox(model(((4, 0, 0, 1),))), vox(model() + trn(child=0)),
                 vox(model() + trn() + shape(models=((6, {}),))),
                 vox(model() + trn(frames=[{'_r': 3}]) + shape())]
        for content in cases:
            with self.subTest(content=content[:20]):
                with self.assertRaises(VoxFormatError):
                    self.parse(content)


if __name__ == '__main__':
    unittest.main()
