"""Offline renders of changed overlays, for a reviewer's approval before a release (the owner's rule, 2026-10-09:
alasdairn approves every changed overlay from an offline render first).

    python tools/paint/approval.py <out dir> <template base> [<template base> ...]

A template base is an id without its sex suffix (Complexion_FlashEagle). One sheet per base: a row per sex that has
it -- a close-up of the mark, then the whole body front and back -- labelled with the window's name for it. The
texture is the painted multiplier (build/marks/<id>_d.png), which the shipped BC7 texture matches within 0.3%
(tools/paint/check_encoding.py).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from collage import FULL, Views, render  # noqa: E402

ROOT = HERE.parent.parent
CLOSE = 48.0  # pixels per game unit for the close-up
BG, INK = (24, 24, 28), (236, 226, 200)


def font(n):
    for f in ('segoeuib.ttf', 'arialbd.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(f, n)
        except OSError:
            pass
    return ImageFont.load_default()


def closeup(views, tex, blank):
    """The side where the mark is, at CLOSE scale, cropped to where it changes the skin (padded)."""
    best = None
    for side in ('front', 'back'):
        img = np.asarray(render(views, tex, side, CLOSE, None, 1.0)).astype(int)
        base = np.asarray(render(views, blank, side, CLOSE, None, 1.0)).astype(int)
        diff = np.abs(img - base).max(-1) > 6
        if best is None or diff.sum() > best[0]:
            best = (diff.sum(), side, img, diff)
    n, side, img, diff = best
    if n == 0:
        return Image.fromarray(img.astype(np.uint8)), side
    ys, xs = np.nonzero(diff)
    pad = 60
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, img.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, img.shape[1])
    crop = Image.fromarray(img[y0:y1, x0:x1].astype(np.uint8))
    crop.thumbnail((700, 820))
    return crop, side


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    tags = json.loads((ROOT / 'data' / 'tags' / 'complexion.json').read_text(encoding='utf-8'))
    views = {}
    for base in sys.argv[2:]:
        rows = []
        for sex, suffix in (('female', 'F'), ('male', 'M')):
            ids = sorted(p.stem[:-2] for p in (ROOT / 'build' / 'marks').glob(f'{base}_{suffix}0*_d.png'))
            for tid in ids:
                if sex not in views:
                    views[sex] = Views(sex)
                v = views[sex]
                tex = np.asarray(Image.open(ROOT / 'build' / 'marks' / f'{tid}_d.png').convert('RGB'), dtype=np.float64) / 255.0
                blank = np.full((64, 64, 3), 0.5)
                close, side = closeup(v, tex, blank)
                front = render(v, tex, 'front', FULL, None, 1.0)
                back = render(v, tex, 'back', FULL, None, 1.0)
                key = ('f:' if sex == 'female' else 'm:') + tid
                rows.append((tid, tags.get(key, {}).get('note', ''), close, front, back))
        if not rows:
            print(f'{base}: no template')
            continue
        H = max(max(r[2].height, r[3].height) for r in rows)
        W = max(r[2].width + r[3].width + r[4].width for r in rows) + 80
        sheet = Image.new('RGB', (W, 90 + len(rows) * (H + 60)), BG)
        d = ImageDraw.Draw(sheet)
        d.text((24, 20), f'{rows[0][1]}', fill=(214, 168, 92), font=font(40))
        for i, (tid, note, close, front, back) in enumerate(rows):
            y = 90 + i * (H + 60)
            d.text((24, y), f'{tid}', fill=INK, font=font(22))
            x = 24
            for im in (close, front, back):
                sheet.paste(im, (x, y + 34))
                x += im.width + 16
        path = out / f'{base}.jpg'
        sheet.save(path, quality=90)
        print(path)


if __name__ == '__main__':
    main()
