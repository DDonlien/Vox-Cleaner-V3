"""Blender-independent reader for MagicaVoxel VOX 150 and 200.

Format: https://github.com/ephtracy/voxel-model (base and extension specs).
Animated scenes are imported at their first stored frame, as static meshes.
"""
import struct


class VoxFormatError(ValueError):
    pass


class Reader:
    def __init__(self, data):
        self.data = memoryview(data)
        self.pos = 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise VoxFormatError("Truncated VOX chunk")
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))

    def integer(self):
        return self.unpack('<i')[0]

    def count(self):
        count = self.integer()
        if count < 0 or count > (len(self.data) - self.pos) // 4:
            raise VoxFormatError("Invalid VOX item count")
        return count

    def dictionary(self):
        result = {}
        for _ in range(self.count()):
            key = bytes(self.take(self.integer())).decode('utf-8')
            value = bytes(self.take(self.integer())).decode('utf-8')
            result[key] = value
        return result


def default_palette():
    levels = (255, 204, 153, 102, 51, 0)
    colors = [(r, g, b, 255) for r in levels for g in levels for b in levels
              if r or g or b]
    ramp = (238, 221, 187, 170, 136, 119, 85, 68, 34, 17)
    for channel in range(4):
        colors.extend(tuple(v if c == channel or channel == 3 else 0
                            for c in range(3)) + (255,) for v in ramp)
    return [[c / 255 for c in color] for color in colors]


IDENTITY = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))


def transform(frame):
    matrix = [list(row) for row in IDENTITY]
    if '_r' in frame:
        code = int(frame['_r'])
        first, second = code & 3, (code >> 2) & 3
        if first > 2 or second > 2 or first == second:
            raise VoxFormatError("Invalid VOX rotation")
        axes = (first, second, 3 - first - second)
        for row, axis in enumerate(axes):
            matrix[row][:3] = [0, 0, 0]
            matrix[row][axis] = -1 if code & (1 << (4 + row)) else 1
    if '_t' in frame:
        coords = tuple(map(int, frame['_t'].split()))
        if len(coords) != 3:
            raise VoxFormatError("Invalid VOX translation")
        for row, value in enumerate(coords):
            matrix[row][3] = value
    return matrix


def multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def read_vox(path, roughness=0.5, max_maps=False):
    with open(path, 'rb') as source:
        reader = Reader(source.read())
    magic, version = reader.unpack('<4si')
    if magic != b'VOX ' or version not in (150, 200):
        raise VoxFormatError(f"Expected VOX 150 or 200; found {magic!r}, version {version}")
    name, size, children = reader.unpack('<4sii')
    if name != b'MAIN' or size != 0 or children < 0:
        raise VoxFormatError("Invalid VOX MAIN chunk")
    body = Reader(reader.take(children))
    if reader.pos != len(reader.data):
        raise VoxFormatError("Unexpected data after VOX MAIN chunk")
    models, nodes, layers = [], {}, {}
    palette = default_palette()
    materials = [[roughness, 0.0, 0.0, 0.0] for _ in range(255)]
    model_size = None

    def chunks(parent, depth=0):
        if depth > 128:
            raise VoxFormatError("VOX chunk nesting is too deep")
        while parent.pos < len(parent.data):
            chunk, size, children = parent.unpack('<4sii')
            content = Reader(parent.take(size))
            nested = Reader(parent.take(children))
            yield chunk, content
            yield from chunks(nested, depth + 1)

    for chunk, data in chunks(body):
        if chunk == b'SIZE':
            model_size = data.unpack('<3i')
            if any(v < 1 or v > 256 for v in model_size):
                raise VoxFormatError("Invalid VOX model dimensions")
        elif chunk == b'XYZI':
            if model_size is None:
                raise VoxFormatError("XYZI chunk has no preceding SIZE")
            count = data.count()
            voxels = list(struct.iter_unpack('<4B', data.take(count * 4)))
            if any(c == 0 or any(v >= s for v, s in zip((x, y, z), model_size))
                   for x, y, z, c in voxels):
                raise VoxFormatError("Voxel outside its model or invalid palette index")
            models.append((model_size, voxels))
            model_size = None
        elif chunk == b'RGBA':
            palette = [[c / 255 for c in rgba] for rgba in
                       struct.iter_unpack('<4B', data.take(1024))][:255]
        elif chunk == b'LAYR':
            layer = data.integer()
            layers[layer] = data.dictionary()
            data.integer()  # reserved
        elif chunk in (b'nTRN', b'nGRP', b'nSHP'):
            node_id = data.integer()
            if node_id in nodes:
                raise VoxFormatError("Duplicate VOX scene node")
            attrs = data.dictionary()
            node = {'kind': chunk, 'attrs': attrs}
            if chunk == b'nTRN':
                node['child'], _, node['layer'] = data.unpack('<3i')
                frames = [data.dictionary() for _ in range(data.count())]
                if not frames:
                    raise VoxFormatError("Transform node has no frames")
                node['matrix'] = transform(min(frames, key=lambda f: int(f.get('_f', 0))))
            elif chunk == b'nGRP':
                node['children'] = [data.integer() for _ in range(data.count())]
            else:
                frames = [(data.integer(), data.dictionary()) for _ in range(data.count())]
                if not frames:
                    raise VoxFormatError("Shape node has no models")
                node['model'] = min(frames, key=lambda f: int(f[1].get('_f', 0)))[0]
            nodes[node_id] = node
        elif chunk == b'MATL':
            index = data.integer()
            attrs = data.dictionary()
            if not 1 <= index <= 255:
                continue
            kind = attrs.get('_type', '_diffuse')
            mat = materials[index - 1]
            mat[0] = float(attrs.get('_rough', roughness))
            if kind in ('_metal', '_blend'):
                mat[1] = float(attrs.get('_metal', attrs.get('_weight', 1)))
            if kind == '_emit':
                mat[2] = 1.0 if max_maps else float(attrs.get('_emit', attrs.get('_weight', 1)))
            if kind in ('_glass', '_blend') and attrs.get('_media_type') != '_sss':
                mat[3] = 1.0 if max_maps else float(attrs.get('_trans', attrs.get('_alpha', attrs.get('_weight', 1))))
        elif chunk == b'MATT':
            index, kind, weight, flags = data.unpack('<iifi')
            props = {bit: data.unpack('<f')[0] for bit in range(7) if flags & (1 << bit)}
            if 1 <= index <= 255:
                mat = materials[index - 1]
                mat[0] = props.get(1, roughness)
                if kind in (1, 2, 3):
                    mat[{1: 1, 2: 3, 3: 2}[kind]] = 1.0 if max_maps and kind != 1 else weight
        # Unknown extension chunks can be skipped using their declared lengths.

    if not models:
        raise VoxFormatError("VOX file contains no models")
    instances = []

    def walk(node_id, matrix, visible, name, ancestors):
        if node_id in ancestors or node_id not in nodes or len(ancestors) > 128:
            raise VoxFormatError("Cyclic, missing, or excessively nested VOX scene node")
        node = nodes[node_id]
        attrs = node['attrs']
        visible = visible and attrs.get('_hidden', '0') != '1'
        name = attrs.get('_name', name)
        ancestors = ancestors | {node_id}
        if node['kind'] == b'nTRN':
            visible = visible and layers.get(node['layer'], {}).get('_hidden', '0') != '1'
            walk(node['child'], multiply(matrix, node['matrix']), visible, name, ancestors)
        elif node['kind'] == b'nGRP':
            for child in node['children']:
                walk(child, matrix, visible, name, ancestors)
        else:
            index = node['model']
            if not 0 <= index < len(models):
                raise VoxFormatError("Scene references a missing VOX model")
            instances.append((index, name, visible, matrix))

    if nodes:
        children = {child for node in nodes.values() for child in
                    ([node['child']] if node['kind'] == b'nTRN' else node.get('children', []))}
        roots = sorted(set(nodes) - children)
        if not roots:
            raise VoxFormatError("VOX scene has no root")
        for root in roots:
            walk(root, IDENTITY, True, '', set())
    else:
        instances = [(i, '', True, IDENTITY) for i in range(len(models))]
    return {'version': version, 'models': models, 'instances': instances,
            'palette': palette, 'materials': materials}
