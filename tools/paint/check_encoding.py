"""Every shipped overlay texture, decoded, against what was painted: the multiply factor the game draws (texel x
2 x base colour) minus the painted one (png / 128), averaged over 8x8 texel areas -- what an eye sees as a patch.

    python tools/paint/check_encoding.py [--soft 0.005] [--ink 0.02]

Two limits, because a patch shows only where the skin is meant to look untouched: an 8x8 area that is clean skin
or a mark's faint soft edge (painted no more than 8 levels off neutral) may be off by 0.5%; one inside a mark's ink
by 2% (hard-edged bold flash measures ~1% in BC7 at its best). Untouched skin must multiply by exactly 1.
Written after the BC1 patches of 0.1.0 and 0.1.1 (a player's report, 2026-10-04): a preview drawn from the PNG never
shows what the compression did. scripts/make-release.ps1 runs it.
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_marks as mm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--soft', type=float, default=0.005)
    ap.add_argument('--ink', type=float, default=0.02)
    args = ap.parse_args()
    base = np.array(mm.BASE_COLOUR) * mm.SCALE
    tex = mm.ROOT / 'data' / 'Textures' / 'Overlays' / 'Complexion'
    worst = []
    bad = 0
    for tid, *_ in mm.MARKS:
        png = mm.ROOT / 'build' / 'marks' / f'{tid}_d.png'
        p = np.asarray(Image.open(png).convert('RGB'), dtype=np.float64)
        d = np.asarray(Image.open(tex / f'{tid}_d.dds').convert('RGB'), dtype=np.float64)
        if d.shape != p.shape:
            print(f'{tid}: texture {d.shape} but painted {p.shape}')
            bad += 1
            continue
        e = (d / 255 * base - p / 128).mean(-1)
        h, w = e.shape
        blocks = np.abs(e[:h // 8 * 8, :w // 8 * 8].reshape(h // 8, 8, w // 8, 8).mean((1, 3)))
        dev = np.abs(p - 128).max(-1)[:h // 8 * 8, :w // 8 * 8].reshape(h // 8, 8, w // 8, 8).max((1, 3))
        soft = float(blocks[dev <= 8].max()) if (dev <= 8).any() else 0.0
        ink = float(blocks[dev > 8].max()) if (dev > 8).any() else 0.0
        clean = np.abs(p - 128).max(-1) == 0
        off = abs(float((d[clean] / 255 * base).mean()) - 1.0) if clean.any() else 0.0
        worst.append((soft, ink, tid))
        if soft > args.soft or ink > args.ink or off > 0.002:
            bad += 1
            print(f'{tid}: worst 8x8 area on skin or soft edge {soft:.4f}, in ink {ink:.4f}, untouched skin x{1 + off:.4f}')
    print('worst on skin and soft edges:', ', '.join(f'{t} {a:.4f}' for a, _, t in sorted(worst, reverse=True)[:3]))
    print('worst in ink:', ', '.join(f'{t} {b:.4f}' for _, b, t in sorted(worst, key=lambda w: -w[1])[:3]))
    print(f'{len(worst)} texture(s), {bad} over the limits (soft {args.soft}, ink {args.ink})')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
