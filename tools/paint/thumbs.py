"""Pictures for the overlay window (C-19): a close-up of each of Complexion's own templates, packed into atlases.

For every template make_marks paints (not the packs': C-8, their art is not ours to render and ship), the
finished texture (build/marks/<id>_d.png, the multiplier the game multiplies the skin by) is drawn on the body,
front and back, with collage.py's rasterizer; the side where the mark shows more is kept, and a square around the
mark is cut out -- re-drawn closer for a small mark -- and scaled to one cell. Nails are cut from the hands'
texture space on plain skin.

    python tools/paint/thumbs.py

Writes data/Textures/Complexion/Thumbs<Sex>_<build>_0.dds -- ONE atlas a sex, 4096 square, 32 x 32 cells of 128,
BC1, one mip: the first window split a sex over two 2048 atlases and the second one's pictures did not show in game
(the owner, 2026-10-04); Silhouette's window mounts one a sex -- and data/F4SE/Plugins/Complexion/thumbs.json:
{"build": ..., "cells": {"f:<id>": [atlas, cell]}, "focus": {"f:<id>": [h, x, y, nx, ny, nz, spread, arm]}}.
focus is where the mark sits, so the window's camera can go to it (the owner: "make the camera move to the last
overlay you picked"): the centroid of the texels it changes, in the body's own frame (h 0 the feet .. 1 the neck
seam; x the character's right, y forward, both in body heights), their mean normal, how far they spread, and
whether they are on an arm (the game's idle pose holds the arms down, the mesh's out: arms are framed loosely).
The build is a hash of the templates in order: an atlas of another build is never mounted by the window (the build
is in the file name), so a picture never shows for the wrong template.
"""
import hashlib
import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_marks as mm  # noqa: E402
from collage import Views, render  # noqa: E402
from body import REGIONS, UVMap  # noqa: E402
from preview import SKIN  # noqa: E402

ATLAS = 4096
CELL = 128
COLS = ATLAS // CELL          # 32
PER_ATLAS = COLS * COLS       # 1024
SCALES = (7.5, 15.0, 30.0)    # pixels per game unit: whole body, closer, close


def mark_box(img, base):
    """The bounding box (x0, y0, x1, y1) of the pixels the mark changes, and how many, from a render and the bare
    body's render."""
    a = np.asarray(img, dtype=np.int16)
    b = np.asarray(base, dtype=np.int16)
    diff = np.abs(a - b).max(-1) > 6
    n = int(diff.sum())
    if n == 0:
        return None, 0
    ys, xs = np.nonzero(diff)
    return (xs.min(), ys.min(), xs.max(), ys.max()), n


def body_thumb(views, tex, bases):
    best = None
    for side in ('front', 'back'):
        img = render(views, tex, side, SCALES[0], None, 1.0)
        base = bases[side]
        box, n = mark_box(img, base)
        if box and (best is None or n > best[2]):
            best = (side, box, n)
    if best is None:
        return Image.new('RGB', (CELL, CELL), (40, 40, 44))
    side, (x0, y0, x1, y1), _ = best
    span = max(x1 - x0, y1 - y0) * 1.25 + 8
    # closer for a small mark: the scale that makes its box about a cell and a half across
    scale = SCALES[0]
    for s in SCALES[1:]:
        if span * (s / SCALES[0]) <= CELL * 1.6:
            scale = s
    k = scale / SCALES[0]
    img = render(views, tex, side, scale, None, 1.0)
    cx, cy = (x0 + x1) / 2 * k, (y0 + y1) / 2 * k
    half = max(span * k / 2, CELL * 0.5)
    crop = img.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half)))
    return crop.resize((CELL, CELL), Image.LANCZOS)


def hand_thumb(tex):
    """Nails: the hands' texture space around what the template changes, on plain skin."""
    size = tex.shape[0]
    dev = np.abs(tex - mm.NEUTRAL).max(-1) > 0.02
    img = np.clip(SKIN * tex * 2.0, 0, 1)
    pic = Image.fromarray((img * 255).astype(np.uint8))
    if not dev.any():
        return pic.resize((CELL, CELL))
    ys, xs = np.nonzero(dev)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    half = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2 * 1.15 + 6
    return pic.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half))).resize((CELL, CELL), Image.LANCZOS)


def focus(m, tex):
    """Where the mark sits, in the body's frame (see the module's docstring), or None for a mark over the whole body."""
    if tex.shape[0] != m.size:
        tex = np.asarray(Image.fromarray((tex * 255).astype(np.uint8)).resize((m.size, m.size)), dtype=np.float64) / 255.0
    dev = np.abs(tex - mm.NEUTRAL).max(-1) * m.covered
    w = np.where(dev > 0.03, dev, 0.0)
    total = w.sum()
    if total <= 0:
        return None
    P = m.position[w > 0]
    N = m.normal[w > 0]
    wt = w[w > 0]
    c = (P * wt[:, None]).sum(0) / total
    spread = float(np.sqrt(((((P - c) ** 2).sum(-1)) * wt).sum() / total))
    lo, hi = m.bounds
    H = hi[2] - lo[2]
    if spread > 0.25 * H:
        return None  # body-wide: the whole body is the view
    n = (N * wt[:, None]).sum(0)
    n = n / max(np.linalg.norm(n), 1e-6)
    arm = float((wt * (m.region[w > 0] == REGIONS.index('arm'))).sum() / total) > 0.5
    return [round(float((c[2] - lo[2]) / H), 4), round(float(c[0] / H), 4), round(float(c[1] / H), 4),
            round(float(n[0]), 3), round(float(n[1]), 3), round(float(n[2]), 3), round(spread / H, 4), 1 if arm else 0]


def main():
    work = mm.ROOT / 'build' / 'marks'
    out_tex = mm.ROOT / 'data' / 'Textures' / 'Complexion'
    out_tex.mkdir(parents=True, exist_ok=True)
    order = {'female': [], 'male': []}
    for tid, sex, painter, args, size, tag in mm.MARKS:
        order[sex].append((tid, painter in mm.HAND_PAINTERS))
    # The layout is in the build too: the 2048 atlases of the same templates had the same name and were read with
    # the new cell maths until deployed over (microscope, 10-04).
    build = hashlib.sha256((f'{ATLAS}x{CELL}|' + '|'.join(t for s in ('female', 'male') for t, _ in order[s])).encode()).hexdigest()[:8]
    for old in out_tex.glob('Thumbs*.dds'):
        old.unlink()
    cells = {}
    spots = {}
    tool = mm.texconv()
    for sex, items in order.items():
        tag = 'f:' if sex == 'female' else 'm:'
        views = Views(sex)
        blank = np.full((64, 64, 3), mm.NEUTRAL)
        bases = {side: render(views, blank, side, SCALES[0], None, 1.0) for side in ('front', 'back')}
        where = UVMap(mm.DATA, sex, 1024)
        atlases = []
        for i, (tid, on_hands) in enumerate(items):
            png = work / f'{tid}_d.png'
            if not png.exists():
                print(f'  {tid}: no texture, no picture')
                continue
            tex = np.asarray(Image.open(png).convert('RGB'), dtype=np.float64) / 255.0
            pic = hand_thumb(tex) if on_hands else body_thumb(views, tex, bases)
            if not on_hands:
                f = focus(where, tex)
                if f:
                    spots[tag + tid] = f
            n, cell = divmod(i, PER_ATLAS)
            while len(atlases) <= n:
                atlases.append(Image.new('RGB', (ATLAS, ATLAS), (20, 20, 20)))
            atlases[n].paste(pic, ((cell % COLS) * CELL, (cell // COLS) * CELL))
            cells[tag + tid] = [n, cell]
            if i % 50 == 0:
                print(f'  {sex}: {i}/{len(items)}')
        name = 'Female' if sex == 'female' else 'Male'
        for n, atlas in enumerate(atlases):
            png = mm.ROOT / 'build' / f'Thumbs{name}_{build}_{n}.png'
            atlas.save(png)
            r = subprocess.run([str(tool), '-nologo', '-y', '-ft', 'dds', '-f', 'BC1_UNORM', '-m', '1', '-o', str(out_tex), str(png)],
                               capture_output=True, text=True)
            made = next((f for f in out_tex.iterdir() if f.name.lower() == png.with_suffix('.dds').name.lower()), None)
            if r.returncode or not made:
                sys.exit(f'texconv failed on {png}')
            if made.name != png.with_suffix('.dds').name:
                made.rename(out_tex / png.with_suffix('.dds').name)
            print(f'{name} atlas {n}: {out_tex / png.with_suffix(".dds").name}')
    index = mm.ROOT / 'data' / 'F4SE' / 'Plugins' / 'Complexion' / 'thumbs.json'
    index.write_text(json.dumps({'build': build, 'cell': CELL, 'cols': COLS, 'cells': cells, 'focus': spots}, indent=0),
                     encoding='utf-8', newline='\n')
    print(f'{len(cells)} picture(s), {len(spots)} spot(s), build {build} -> {index}')


if __name__ == '__main__':
    main()
