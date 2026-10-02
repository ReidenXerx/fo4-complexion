"""The body as the overlays see it: every texel of its UV map with the 3D point, normal and region it lands on.

An overlay is a texture on the body's own UV map (f4ee clones the skin shape and swaps its material), so the
only layout that matters is the one in the mesh the game loads. It is read straight out of that NIF -- no
guessed layout, no probe texture (Rapport's make_overlays.py could not place sweat for want of exactly this).

NIF reading after Silhouette's tools/pool/mesh.py (NifTools' nif.xml, version 20.2.0.7, stream 130). The vertex
descriptor's nibbles give each attribute's offset in 4-byte units: bits 8-11 the UV, 28-31 the skinning;
bit 44+10 says the position is full-precision floats rather than halves.
"""
import pathlib
import struct

import numpy as np

SHAPES = ('BSTriShape', 'BSSubIndexTriShape', 'BSMeshLODTriShape', 'BSDynamicTriShape')
VA_UV = 1 << 1
VA_SKINNED = 1 << 6
VA_FULL = 1 << 10
ASSETS = pathlib.Path('Meshes/actors/character/characterassets')
# The body mesh of each sex and its main shape (the owner's: CBBE, BodyTalk4 -- Silhouette's BODIES).
BODIES = {'female': ('FemaleBody', 'CBBE'), 'male': ('MaleBody', 'BaseMaleBody:0')}


class _Cursor:
    def __init__(self, b, o=0):
        self.b, self.o = b, o

    def take(self, fmt):
        v = struct.unpack_from('<' + fmt, self.b, self.o)
        self.o += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]

    def string8(self):
        n = self.take('B')  # not `self.o += self.take('B')`: that adds to the offset read BEFORE take moved it
        self.o += n

    def string32(self):
        n = self.take('I')
        s = self.b[self.o:self.o + n]
        self.o += n
        return s.decode('latin1')


def read_shape(path, shape_name):
    """(positions Nx3, uvs Nx2, triangles Mx3, heaviest bone name per vertex)"""
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

    nodes = {i: name_at(_Cursor(b, offsets[i])) for i, k in enumerate(kinds) if k in ('NiNode', 'BSFadeNode', 'BSLeafAnimNode')}
    found = []
    for i, k in enumerate(kinds):
        if k not in SHAPES:
            continue
        cur = _Cursor(b, offsets[i])
        name = name_at(cur)
        found.append(name)
        if name != shape_name:
            continue
        cur.take('4f')
        skin = cur.take('i')
        cur.take('i'); cur.take('i')
        desc = cur.take('Q')
        ntri, nv = cur.take('I'), cur.take('H')
        cur.take('I')
        stride = (desc & 0xF) * 4
        flags = (desc >> 44) & 0xFFF
        if not flags & VA_UV:
            raise ValueError(f'{path}: shape {shape_name} has no UVs')
        full = bool(flags & VA_FULL)
        uv_at = ((desc >> 8) & 0xF) * 4
        skin_at = ((desc >> 28) & 0xF) * 4
        at = cur.o
        raw = np.frombuffer(b, dtype=np.uint8, count=nv * stride, offset=at).reshape(nv, stride)
        if full:
            pos = raw[:, 0:12].copy().view('<f4').reshape(nv, 3).astype(np.float64)
        else:
            pos = raw[:, 0:6].copy().view('<f2').reshape(nv, 3).astype(np.float64)
        uv = raw[:, uv_at:uv_at + 4].copy().view('<f2').reshape(nv, 2).astype(np.float64)
        tris = np.frombuffer(b, dtype='<u2', count=ntri * 3, offset=at + nv * stride).reshape(ntri, 3).astype(np.int64)
        bone_names = []
        if skin >= 0 and kinds[skin] == 'BSSkin::Instance':
            sc = _Cursor(b, offsets[skin])
            sc.take('i'); sc.take('i')
            bone_names = [nodes.get(r) or '' for r in (sc.take('i') for _ in range(sc.take('I')))]
        bones = []
        for v in range(nv):
            if not flags & VA_SKINNED or not bone_names:
                bones.append('')
                continue
            w = struct.unpack_from('<4e', b, at + v * stride + skin_at)
            s = struct.unpack_from('<4B', b, at + v * stride + skin_at + 8)
            k = max(range(4), key=lambda j: w[j])
            bones.append(bone_names[s[k]] if s[k] < len(bone_names) else '')
        return pos, uv, tris, bones
    raise ValueError(f'{path}: no shape {shape_name!r} (it has {found})')


REGIONS = ['torso', 'arm', 'hand', 'leg', 'foot', 'head']


def region_of(bone):
    low = bone.lower()
    if any(k in low for k in ('hand', 'finger', 'thumb', 'wrist')):
        return 'hand'
    if any(k in low for k in ('arm', 'elbow', 'shoulder', 'clavicle')):
        return 'arm'
    if any(k in low for k in ('foot', 'toe', 'ankle')):
        return 'foot'
    if any(k in low for k in ('thigh', 'calf', 'knee', 'leg')):
        return 'leg'
    if any(k in low for k in ('neck', 'head')):
        return 'head'
    return 'torso'


class UVMap:
    """Per texel of a size x size map: covered (bool), position (x, y, z), normal, region index. Texel (row,
    col) is UV (col + 0.5, row + 0.5) / size, V downwards as DDS rows are."""

    def __init__(self, data, sex, size=2048):
        name, shape = BODIES[sex]
        pos, uv, tris, bones = read_shape(pathlib.Path(data) / ASSETS / f'{name}.nif', shape)
        self.size, self.sex = size, sex
        self.vertices, self.triangles = pos, tris
        vreg = np.array([REGIONS.index(region_of(bn)) for bn in bones], dtype=np.int8)
        # Vertex normals, area-weighted from the faces.
        fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
        vn = np.zeros_like(pos)
        for k in range(3):
            np.add.at(vn, tris[:, k], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
        self.covered = np.zeros((size, size), bool)
        self.position = np.zeros((size, size, 3))
        self.normal = np.zeros((size, size, 3))
        self.region = np.full((size, size), -1, np.int8)
        px = uv * size - 0.5
        for t in tris:
            a, b_, c_ = px[t[0]], px[t[1]], px[t[2]]
            x0, x1 = int(max(0, np.floor(min(a[0], b_[0], c_[0])))), int(min(size - 1, np.ceil(max(a[0], b_[0], c_[0]))))
            y0, y1 = int(max(0, np.floor(min(a[1], b_[1], c_[1])))), int(min(size - 1, np.ceil(max(a[1], b_[1], c_[1]))))
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            d = (b_[1] - c_[1]) * (a[0] - c_[0]) + (c_[0] - b_[0]) * (a[1] - c_[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((b_[1] - c_[1]) * (xs - c_[0]) + (c_[0] - b_[0]) * (ys - c_[1])) / d
            l2 = ((c_[1] - a[1]) * (xs - c_[0]) + (a[0] - c_[0]) * (ys - c_[1])) / d
            l3 = 1 - l1 - l2
            inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
            if not inside.any():
                continue
            yy, xx = ys[inside], xs[inside]
            w = np.stack([l1[inside], l2[inside], l3[inside]], axis=1)
            self.covered[yy, xx] = True
            self.position[yy, xx] = w @ pos[t]
            n = w @ vn[t]
            self.normal[yy, xx] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
            self.region[yy, xx] = vreg[t[np.argmax(w, axis=1)]]
        lo = pos.min(axis=0)
        hi = pos.max(axis=0)
        self.bounds = (lo, hi)

    def height(self):
        """0 at the feet, 1 at the top of the shape, per texel."""
        lo, hi = self.bounds
        return (self.position[..., 2] - lo[2]) / max(hi[2] - lo[2], 1e-9)
