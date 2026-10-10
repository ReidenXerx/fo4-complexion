"""Collages of every finished template, for the owner to eyeball by the hundred (2026-10-03: "for quick verifying of
that giant number of overlays ... I will eyeball instead of checking all in game").

Each template is drawn from its FINISHED texture (build/marks/<id>_d.png, the multiplier the game multiplies the skin
by) on the body, front and back, grouped by kind (data/tags/complexion.json), a page per dozen. Kinds whose detail is
small or local get a closer view: nipples the chest, pubic hair the pelvis.

The body is RASTERIZED once per view into a buffer of texture coordinates and shading (preview.py's point splatting
leaves holes when zoomed in), so each tile is only a texture lookup.

    python tools/paint/collage.py [--sex female|male|both] [--kinds mole,scar] [--prefix Complexion_Moles]
"""
import argparse
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from body import ASSETS, BODIES, UVMap, read_shape  # noqa: E402
from marks import landmarks  # noqa: E402
from preview import SKIN  # noqa: E402

ROOT = HERE.parent.parent
DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
# kind -> (pixels per game unit, crop: (low landmark, offset, high landmark, offset) or None, width fraction kept)
ZOOM = {'nipple': (24.0, ('underbust', -0.04, 'chest', 0.01), 0.34),
        'pubic_hair': (24.0, ('crotch', -0.10, 'navel', 0.04), 0.30)}
FULL = 7.5  # pixels per game unit for the whole body (about 850 px tall)


class Views:
    """The body's mesh, rasterized per (side, scale, crop) into texture coordinates and a shade per pixel."""

    def __init__(self, sex):
        name, shape = BODIES[sex]
        self.V, self.uv, self.T, _ = read_shape(DATA / ASSETS / f'{name}.nif', shape)
        fn = np.cross(self.V[self.T[:, 1]] - self.V[self.T[:, 0]], self.V[self.T[:, 2]] - self.V[self.T[:, 0]])
        vn = np.zeros_like(self.V)
        for k in range(3):
            np.add.at(vn, self.T[:, k], fn)
        self.N = vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
        self.m = UVMap(DATA, sex, 256)   # for the landmarks only
        self.cache = {}

    def get(self, side, scale, crop=None, keep=1.0):
        key = (side, scale, crop, keep)
        if key in self.cache:
            return self.cache[key]
        V, N, T, uv = self.V, self.N, self.T, self.uv
        lo, hi = V.min(axis=0), V.max(axis=0)
        sign = 1.0 if side == 'front' else -1.0
        W = int((hi[0] - lo[0]) * scale) + 40
        H = int((hi[2] - lo[2]) * scale) + 20
        sx = ((hi[0] - V[:, 0]) if side == 'front' else (V[:, 0] - lo[0])) * scale + 20
        sy = (hi[2] - V[:, 2]) * scale + 10
        depth = V[:, 1] * sign
        r0, r1, c0, c1 = 0, H, 0, W
        if crop:
            L = landmarks(self.m)
            zl = lo[2] + (L[crop[0]] + crop[1]) * (hi[2] - lo[2])
            zh = lo[2] + (L[crop[2]] + crop[3]) * (hi[2] - lo[2])
            r0, r1 = int((hi[2] - zh) * scale) + 10, int((hi[2] - zl) * scale) + 10
            c0, c1 = int(W * (0.5 - keep / 2)), int(W * (0.5 + keep / 2))
        h, w = r1 - r0, c1 - c0
        zbuf = np.full((h, w), -np.inf)
        U = np.full((h, w), -1.0)
        Vv = np.full((h, w), -1.0)
        shade = np.zeros((h, w))
        light = np.array((0.35 * -sign, 0.85 * sign, 0.4))
        light /= np.linalg.norm(light)
        vshade = np.clip(N @ light, 0.15, 1.0) * 0.85 + 0.15
        facing = N[:, 1] * sign
        for t in T:
            if facing[t].max() < -0.2:
                continue
            xs, ys = sx[t] - c0, sy[t] - r0
            x0, x1 = int(max(0, np.floor(xs.min()))), int(min(w - 1, np.ceil(xs.max())))
            y0, y1 = int(max(0, np.floor(ys.min()))), int(min(h - 1, np.ceil(ys.max())))
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
            z = l1 * depth[t[0]] + l2 * depth[t[1]] + l3 * depth[t[2]]
            yy, xx = np.nonzero(inside)
            yy, xx = yy + y0, xx + x0
            zi = z[inside]
            win = zi > zbuf[yy, xx]
            if not win.any():
                continue
            yy, xx = yy[win], xx[win]
            a, b, c = l1[inside][win], l2[inside][win], l3[inside][win]
            zbuf[yy, xx] = zi[win]
            U[yy, xx] = a * uv[t[0], 0] + b * uv[t[1], 0] + c * uv[t[2], 0]
            Vv[yy, xx] = a * uv[t[0], 1] + b * uv[t[1], 1] + c * uv[t[2], 1]
            shade[yy, xx] = a * vshade[t[0]] + b * vshade[t[1]] + c * vshade[t[2]]
        out = (U, Vv, shade, U >= 0)
        self.cache[key] = out
        return out


def render(views, tex, side, scale, crop, keep):
    U, Vv, shade, mask = views.get(side, scale, crop, keep)
    size = tex.shape[0]
    col = np.clip((U * size).astype(int), 0, size - 1)
    row = np.clip((Vv * size).astype(int), 0, size - 1)
    img = np.full(U.shape + (3,), 0.16, np.float32)   # float32: close-ups of the whole body ran out of memory
    factor = tex[row[mask], col[mask]] * 2.0
    img[mask] = np.clip(SKIN * factor, 0, 1) * shade[mask][:, None]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def tile(views, tid, kind):
    tex = np.asarray(Image.open(ROOT / 'build' / 'marks' / f'{tid}_d.png').convert('RGB'), dtype=np.float64) / 255.0
    scale, crop, keep = ZOOM.get(kind, (FULL, None, 1.0))
    f = render(views, tex, 'front', scale, crop, keep)
    b = render(views, tex, 'back', scale, crop, keep) if not crop else None   # close-ups: the front is what matters
    t = Image.new('RGB', (f.width + (b.width if b else 0), f.height + 22), (30, 30, 34))
    t.paste(f, (0, 22))
    if b:
        t.paste(b, (f.width, 22))
    ImageDraw.Draw(t).text((6, 4), tid.replace('Complexion_', ''), fill=(255, 255, 170))
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sex', default='both')
    ap.add_argument('--kinds', default='')
    ap.add_argument('--prefix', default='')
    ap.add_argument('--per', type=int, default=12)
    ap.add_argument('--out', type=pathlib.Path, default=ROOT / 'build' / 'collages')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    tags = json.loads((ROOT / 'data' / 'tags' / 'complexion.json').read_text(encoding='utf-8'))
    kinds = set(a.kinds.split(',')) if a.kinds else None
    made = 0
    for sex in (('female', 'male') if a.sex == 'both' else (a.sex,)):
        tag = 'f:' if sex == 'female' else 'm:'
        groups = {}
        for key, v in tags.items():
            tid = key[2:]
            if not key.startswith(tag) or v['kind'] == 'nails':
                continue
            if (a.prefix and not tid.startswith(a.prefix)) or (kinds and v['kind'] not in kinds):
                continue
            if not (ROOT / 'build' / 'marks' / f'{tid}_d.png').exists():
                continue
            groups.setdefault(v['kind'], []).append(tid)
        if not groups:
            continue
        views = Views(sex)
        for kind, tids in sorted(groups.items()):
            tids.sort()
            for page in range(0, len(tids), a.per):
                tiles = [tile(views, tid, kind) for tid in tids[page:page + a.per]]
                cols = min(6 if kind in ZOOM else 4, len(tiles))
                rows = (len(tiles) + cols - 1) // cols
                W = max(t.width for t in tiles)
                H = max(t.height for t in tiles)
                out = Image.new('RGB', (W * cols, H * rows), (20, 20, 20))
                for i, t in enumerate(tiles):
                    out.paste(t, ((i % cols) * W, (i // cols) * H))
                path = a.out / f'{sex}_{kind}_{page // a.per + 1:02d}.jpg'
                out.save(path, quality=88)
                made += 1
                print(f'{path.name}: {len(tiles)}  ({out.width}x{out.height})')
    print(f'{made} page(s) in {a.out}')


if __name__ == '__main__':
    main()
