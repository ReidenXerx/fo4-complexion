"""An artist's tattoo PNG (ink on transparency, laid out on the body UV like the files in the work pack) turned into
Complexion's multiply texture, and a preview sheet of it on the body -- for the artist and the reviewer, before
anything goes into the build (alasdairn's rule, 2026-10-14: preview only until the artist calls it final AND he
approves it).

    python tools/paint/artist_art.py <out dir> <png> [<png> ...]

Each PNG is named after the template it replaces or adds (Complexion_FlashEagle_F01.png; a trailing _d is fine). It
is scaled to the template's size, faded before the neck and wrist seams like every painted mark, and written to
<out dir>/marks/<id>_d.png; tools/paint/approval.py then renders <out dir>/<base>.jpg from that folder only.

A PNG with no transparency is taken as already in the multiply format (50% grey = untouched skin), the way the
in-game test recipe makes it.
"""
import os
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_marks as mm  # noqa: E402
import seams  # noqa: E402
from body import UVMap  # noqa: E402


def template_id(png):
    stem = png.stem[:-2] if png.stem.lower().endswith('_d') else png.stem
    return stem


def convert(png, out):
    tid = template_id(png)
    row = next((r for r in mm.MARKS if r[0] == tid), None)
    sex = row[1] if row else ('female' if tid.split('_')[-1].startswith('F') else 'male')
    size = row[4] if row else 2048   # rows are (tid, sex, painter, args, size, tag)
    painter = row[2] if row else ''
    m = UVMap(mm.DATA, sex, size)
    im = Image.open(png)
    if im.size != (size, size):
        print(f'  {png.name}: {im.size[0]}px, scaled to the template\'s {size}px')
        im = im.resize((size, size), Image.LANCZOS)
    if im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info:
        px = np.asarray(im.convert('RGBA'), dtype=np.float64) / 255.0
        rgb, alpha = px[..., :3], px[..., 3]
    else:   # already multiply grey: back to colour + alpha over the painters' skin, as make_marks paints
        f = np.asarray(im.convert('RGB'), dtype=np.float64) / 255.0 / mm.NEUTRAL
        alpha = np.clip(1 - f, 0, 1).max(-1)
        rgb = np.clip(mm.SKIN * (1 + (f - 1) / np.maximum(alpha, 1e-4)[..., None]), 0, 1)
    off = float((alpha[~m.covered] > 0.05).mean()) * 100
    if off > 0.5:
        print(f'  {png.name}: {off:.1f}% of the off-body area has ink -- it will not show (check the UV layout)')
    save(out, tid, m, rgb, alpha, painter)
    return tid


# A tattoo ends where its artist ends it: it only needs the hard edge at the head / hands seam softened, not the
# ~4 cm fade that grime and freckles take (a 6 cm anchor 2.5 cm above the wrist lost its lower half to that, 10-14).
TATTOO_FADE = (0.3, 0.5)   # game units: gone within 0.3 of the seam, full from 0.8 (about 1.1 cm)


def save(out, tid, m, rgb, alpha, painter='', fade=TATTOO_FADE):
    """colour + alpha on the UV map -> the finished multiplier in <out>/marks, as make_marks finishes a painted mark."""
    if painter not in mm.SEAM_EXEMPT:
        alpha = alpha * seams.seam_fade(m, *fade)
    rgb = mm.dilate(rgb, alpha, m.covered)
    img = mm.bleed(mm.multiplier(rgb, alpha), m.covered)
    (out / 'marks').mkdir(parents=True, exist_ok=True)
    img.save(out / 'marks' / f'{tid}_d.png')


def render(out, bases):
    env = dict(os.environ, COMPLEXION_MARKS=str(out / 'marks'))
    subprocess.run([sys.executable, str(HERE / 'approval.py'), str(out), *bases], env=env, check=True)


def main():
    out = pathlib.Path(sys.argv[1])
    bases = []
    for p in sys.argv[2:]:
        tid = convert(pathlib.Path(p), out)
        base = tid.rsplit('_', 1)[0]
        if base not in bases:
            bases.append(base)
    render(out, bases)


if __name__ == '__main__':
    main()
