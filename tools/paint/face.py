"""Heads as face tints see them: every texel of a head mesh's UV map with the 3D point it lands on (body.UVMap's
twin for heads).

LooksMenu's overlays never reach the head (docs/complexion-research.md): a face takes LooksMenu face TINTS, textures
on the head mesh's own UV map registered per race in F4SE/Plugins/F4EE/Tints/<plugin>/. So a face mark is painted
on the head the game draws for that race:
- the vanilla heads, from Fallout4 - Meshes.ba2 (BaseMaleHead / BaseFemaleHead; the two sexes' layouts differ in
  places, so each sex gets its own texture);
- Ace Male Race's head, from its own BA2 (acemalehead.nif) -- a different mesh with a different UV layout (ears
  elsewhere, the face wider: measured 2026-11-13), so it gets its own texture too.

Only the names table and the one file are read from an archive, never the archive whole (11-05: whole-archive
reads in six processes ran the PC out of memory).
"""
import pathlib
import struct
import zlib

import numpy as np

from body import read_shape

DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
ACE = pathlib.Path(r'D:\Vortex\fallout4\mods\Ace Male Race 1.0.0-84395-1-0-0-1718058198')
# name -> (archive, path inside, shape, the race's editor id in the tint json, LooksMenu gender)
HEADS = {
    'human_male': (DATA / 'Fallout4 - Meshes.ba2', r'meshes\actors\character\characterassets\basemalehead.nif', 'BaseMaleHead:0', 'HumanRace', 0),
    'human_female': (DATA / 'Fallout4 - Meshes.ba2', r'meshes\actors\character\characterassets\basefemalehead.nif', 'BaseFemaleHead:0', 'HumanRace', 1),
    'ace_male': (ACE / 'AceMaleRace - Main.ba2', r'meshes\actors\character\anewhumanmale\acemalehead.nif', 'AceMaleHead', 'AceHumanRace', 0),
}


def ba2_file(archive, rel):
    """One file out of a general (GNRL) BA2."""
    with open(archive, 'rb') as f:
        magic, _ver, kind, count, names_at = struct.unpack('<4sI4sIQ', f.read(24))
        if magic != b'BTDX' or kind != b'GNRL':
            raise ValueError(f'{archive}: not a general BA2')
        raw = f.read(36 * count)
        f.seek(names_at)
        blob = f.read()
    off = 0
    want = rel.lower().replace('/', '\\')
    for i in range(count):
        (ln,) = struct.unpack_from('<H', blob, off)
        name = blob[off + 2:off + 2 + ln].decode('latin-1').lower().replace('/', '\\')
        off += 2 + ln
        if name == want:
            _h, _e, _d, _fl, at, packed, size, _a = struct.unpack_from('<IIIIQIII', raw, 36 * i)
            with open(archive, 'rb') as f:
                f.seek(at)
                data = f.read(packed or size)
            return zlib.decompress(data) if packed else data
    raise FileNotFoundError(f'{rel} not in {archive}')


class HeadMap:
    """Per texel of a size x size map: covered, position, normal (as body.UVMap). Texel (row, col) is UV
    (col + 0.5, row + 0.5) / size."""

    def __init__(self, head, size=1024, cache=None):
        archive, rel, shape, self.race, self.gender = HEADS[head]
        self.head, self.size = head, size
        path = pathlib.Path(cache or pathlib.Path(__file__).resolve().parents[2] / 'build' / 'heads') / f'{head}.nif'
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(ba2_file(archive, rel))
        pos, uv, tris, _ = read_shape(path, shape)
        self.vertices, self.triangles, self.uv = pos, tris, uv
        fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
        vn = np.zeros_like(pos)
        for k in range(3):
            np.add.at(vn, tris[:, k], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
        self.covered = np.zeros((size, size), bool)
        self.position = np.zeros((size, size, 3))
        self.normal = np.zeros((size, size, 3))
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
        self.bounds = (pos.min(axis=0), pos.max(axis=0))


def render(m, tex, view='front', scale=40.0, skin=(0.80, 0.64, 0.54)):
    """The head drawn with a face tint multiplied in (tex: HxWx3, 1 = untouched), front or from its right side
    ('side'), lit from the front and above; for review sheets. Returns a PIL image."""
    from PIL import Image
    V, T, uv = m.vertices, m.triangles, m.uv
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, T[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    lo, hi = m.bounds
    if view == 'front':
        sx, depth, light = (hi[0] - V[:, 0]) * scale, V[:, 1], np.array((-0.3, 0.85, 0.45))
        W = int((hi[0] - lo[0]) * scale)
    else:
        sx, depth, light = (hi[1] - V[:, 1]) * scale, V[:, 0], np.array((0.85, 0.4, 0.45))
        W = int((hi[1] - lo[1]) * scale)
    sy = (hi[2] - V[:, 2]) * scale
    W, H = W + 20, int((hi[2] - lo[2]) * scale) + 20
    sx, sy = sx + 10, sy + 10
    light /= np.linalg.norm(light)
    shade_v = np.clip(vn @ light, 0.12, 1.0) * 0.85 + 0.15
    zbuf = np.full((H, W), -np.inf)
    U = np.full((H, W), -1.0)
    Vv = np.full((H, W), -1.0)
    shade = np.zeros((H, W))
    for t in T:
        xs, ys = sx[t], sy[t]
        x0, x1 = int(max(0, np.floor(xs.min()))), int(min(W - 1, np.ceil(xs.max())))
        y0, y1 = int(max(0, np.floor(ys.min()))), int(min(H - 1, np.ceil(ys.max())))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(d) < 1e-9:
            continue
        l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
        l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        if not inside.any():
            continue
        zz = l1 * depth[t[0]] + l2 * depth[t[1]] + l3 * depth[t[2]]
        yy, xx = np.nonzero(inside)
        yy, xx = yy + y0, xx + x0
        zi = zz[inside]
        win = zi > zbuf[yy, xx]
        yy, xx = yy[win], xx[win]
        a, b, c = l1[inside][win], l2[inside][win], l3[inside][win]
        zbuf[yy, xx] = zi[win]
        U[yy, xx] = a * uv[t[0], 0] + b * uv[t[1], 0] + c * uv[t[2], 0]
        Vv[yy, xx] = a * uv[t[0], 1] + b * uv[t[1], 1] + c * uv[t[2], 1]
        shade[yy, xx] = a * shade_v[t[0]] + b * shade_v[t[1]] + c * shade_v[t[2]]
    mask = U >= 0
    size = tex.shape[0]
    col = np.clip((U[mask] * size).astype(int), 0, size - 1)
    row = np.clip((Vv[mask] * size).astype(int), 0, size - 1)
    img = np.full((H, W, 3), 0.16)
    img[mask] = np.clip(np.asarray(skin) * tex[row, col], 0, 1) * shade[mask][:, None]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
