"""The installed body as a model: any preset's body is the reference plus the sum of value x diff.

BodySlide builds `built = reference + sum(value_i * diff_i)` and "Build Morphs" writes every diff_i at
100% into the body's .tri (base_body.py). The body in Meshes is built zeroed (S-5; verify_bodygen checks
it), so it IS the reference, and any preset's body can be built here, measured and drawn, without
BodySlide. Read-only NIF parsing (positions, triangles, skin weights, bone names) after fo4-anatomy's
tools/nif.py, which is the same author's.
"""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import base_body  # noqa: E402

SHAPES = ('BSTriShape', 'BSSubIndexTriShape', 'BSMeshLODTriShape', 'BSDynamicTriShape')
VA_SKINNED = 1 << 6
VA_FULL = 1 << 10
ASSETS = pathlib.Path('Meshes/actors/character/characterassets')
# The installed bodies Silhouette shapes: the mesh, its main shape, and the slider set that builds it
BODIES = {'female': ('FemaleBody', 'CBBE', 'Anatomy Body'),
          'male': ('MaleBody', 'BaseMaleBody:0', 'BodyTalk4')}


class _Cursor:
    def __init__(self, b, o=0):
        self.b, self.o = b, o

    def take(self, fmt):
        v = struct.unpack_from('<' + fmt, self.b, self.o)
        self.o += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]

    def string8(self):
        n = self.take('B')
        self.o += n

    def string32(self):
        n = self.take('I')
        s = self.b[self.o:self.o + n]
        self.o += n
        return s.decode('latin1')


class Mesh:
    """One tri-shape of a Fallout 4 NIF: positions, triangles, and the heaviest bone of each vertex."""

    def __init__(self, path, shape_name):
        b = pathlib.Path(path).read_bytes()
        c = _Cursor(b, b.index(b'\n') + 1)
        version, _endian, _user = c.take('I'), c.take('B'), c.take('I')
        nblocks = c.take('I')
        if version != 0x14020007 or c.take('I') != 130:
            raise ValueError(f'{path}: not a Fallout 4 NIF')
        for _ in range(4):
            c.string8()
        types = [c.string32() for _ in range(c.take('H'))]
        kinds = [types[c.take('H') & 0x7FFF] for _ in range(nblocks)]
        sizes = [c.take('I') for _ in range(nblocks)]
        strings = [None] * c.take('I')
        c.take('I')
        strings = [c.string32() for _ in strings]
        for _ in range(c.take('I')):
            c.take('I')
        offsets, o = [], c.o
        for s in sizes:
            offsets.append(o)
            o += s

        def name_at(cur):
            i = cur.take('i')
            name = strings[i] if 0 <= i < len(strings) else None
            for _ in range(cur.take('I')):
                cur.take('i')
            cur.take('i'); cur.take('I'); cur.take('3f'); cur.take('9f'); cur.take('f'); cur.take('i')
            return name

        nodes = {}
        for i, k in enumerate(kinds):
            if k in ('NiNode', 'BSFadeNode', 'BSLeafAnimNode'):
                nodes[i] = name_at(_Cursor(b, offsets[i]))
        for i, k in enumerate(kinds):
            if k not in SHAPES:
                continue
            cur = _Cursor(b, offsets[i])
            if name_at(cur) != shape_name:
                continue
            cur.take('4f')
            skin = cur.take('i')
            cur.take('i'); cur.take('i')
            desc = cur.take('Q')
            ntri, nv = cur.take('I'), cur.take('H')
            cur.take('I')
            stride = (desc & 0xF) * 4
            flags = (desc >> 44) & 0xFFF
            full = bool(flags & VA_FULL)
            skin_at = ((desc >> 28) & 0xF) * 4
            at = cur.o
            self.positions = [struct.unpack_from('<3f' if full else '<3e', b, at + v * stride) for v in range(nv)]
            t0 = at + nv * stride
            self.triangles = [struct.unpack_from('<3H', b, t0 + 6 * k) for k in range(ntri)]
            bones = []
            if skin >= 0 and kinds[skin] == 'BSSkin::Instance':
                sc = _Cursor(b, offsets[skin])
                sc.take('i'); sc.take('i')
                bones = [nodes.get(r) for r in (sc.take('i') for _ in range(sc.take('I')))]
            self.bone = []
            for v in range(nv):
                if not flags & VA_SKINNED:
                    self.bone.append('')
                    continue
                o2 = at + v * stride + skin_at
                w = struct.unpack_from('<4e', b, o2)
                s = struct.unpack_from('<4B', b, o2 + 8)
                k = max(range(4), key=lambda j: w[j])
                self.bone.append((bones[s[k]] if s[k] < len(bones) else None) or '')
            return
        raise ValueError(f'{path}: no shape {shape_name!r}')


def region_of(bone):
    """'arm', 'leg' or 'torso' by the vertex's heaviest bone: slices of the torso leave the arms out."""
    low = bone.lower()
    if any(k in low for k in ('arm', 'hand', 'finger', 'thumb', 'elbow', 'wrist')):
        return 'arm'
    if any(k in low for k in ('thigh', 'calf', 'knee', 'foot', 'toe', 'leg')):
        return 'leg'
    return 'torso'


class Body:
    """The installed body of one sex: reference mesh, slider diffs, skin regions."""

    def __init__(self, data, sex):
        name, shape, self.slider_set = BODIES[sex]
        mesh = Mesh(pathlib.Path(data) / ASSETS / f'{name}.nif', shape)
        self.sex = sex
        self.ref = mesh.positions
        self.tris = mesh.triangles
        self.region = [region_of(b) for b in mesh.bone]
        self.diffs = base_body.read_tri(pathlib.Path(data) / ASSETS / f'{name}.tri')[shape]

    def build(self, values):
        """values: {slider: fraction, 1.0 = 100%} -> vertex positions"""
        v = [list(p) for p in self.ref]
        for name, w in values.items():
            if not w:
                continue
            for i, (x, y, z) in self.diffs.get(name, {}).items():
                q = v[i]
                q[0] += w * x
                q[1] += w * y
                q[2] += w * z
        return v
