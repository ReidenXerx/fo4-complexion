"""An artist preview's files to hand back: the wrapped result as ink on transparency (to tweak) and a test mod that
puts it in game under an EXISTING template's name (a new piece has no slot in game until it is added to Complexion).

    python tools/paint/artist_files.py <marks png> <out dir> <stem> <existing template id to borrow>
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_marks as mm  # noqa: E402


def ink(multiplier_png):
    """The multiply texture back to colour + alpha over the painters' skin (the least alpha that keeps the colour in
    range: dark ink by max(1 - f), the rare lighter-than-skin ink by how far over 1 it goes)."""
    f = np.asarray(Image.open(multiplier_png).convert('RGB'), dtype=np.float32) / 255.0 / mm.NEUTRAL
    dark = np.clip(1 - f, 0, 1).max(-1)
    light = np.clip((f - 1) * mm.SKIN / (1 - mm.SKIN), 0, 1).max(-1)
    a = np.maximum(dark, light)
    c = np.clip(mm.SKIN * (1 + (f - 1) / np.maximum(a, 1e-4)[..., None]), 0, 1)
    a[a < 2 / 255] = 0
    rgba = np.dstack([c * 255, a * 255]).round().astype(np.uint8)
    rgba[a == 0, :3] = 0
    return Image.fromarray(rgba, 'RGBA')


def main():
    src, out, stem, borrow = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    out.mkdir(parents=True, exist_ok=True)
    size = Image.open(src).size[0]
    ink(src).save(out / f'{stem}_wrapped_{size}.png', optimize=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        tex = tmp / 'mod' / 'Textures' / 'Overlays' / 'Complexion'
        tex.mkdir(parents=True)
        shutil.copy(src, tmp / f'{borrow}_d.png')
        mm.encode(mm.texconv(), tmp / f'{borrow}_d.png', tex, borrow)
        z = out / f'{stem}_test_mod.zip'
        z.unlink(missing_ok=True)
        subprocess.run(['7z', 'a', '-tzip', str(z.resolve()), 'Textures'], cwd=tmp / 'mod', check=True, capture_output=True)
    print(out / f'{stem}_wrapped_{size}.png')
    print(z)


if __name__ == '__main__':
    main()
