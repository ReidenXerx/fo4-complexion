"""A painted mark at lower opacity, from its finished multiplier -- no repaint: the multiply material scales the skin
by factor = 1 + alpha * (colour / skin - 1), stored as factor x NEUTRAL, so scaling alpha by k is exactly
m' = NEUTRAL + k * (m - NEUTRAL). For showing a reviewer a more transparent variant (alasdairn, 2026-10-10).

    python tools/paint/fade_marks.py <k> <out dir> <template base> [...]
"""
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_marks import NEUTRAL  # noqa: E402

ROOT = HERE.parent.parent


def main():
    k, out = float(sys.argv[1]), pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for base in sys.argv[3:]:
        for png in sorted((ROOT / 'build' / 'marks').glob(f'{base}_[FM]0*_d.png')):
            m = np.asarray(Image.open(png).convert('RGB'), np.float64) / 255.0
            faded = np.clip(NEUTRAL + k * (m - NEUTRAL), 0, 1)
            Image.fromarray(np.uint8(faded * 255 + 0.5)).save(out / png.name)
            print(out / png.name)


if __name__ == '__main__':
    main()
