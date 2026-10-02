"""Draws the body's UV map coloured by what each texel is (region, front/back, height), to check body.py
reads the layout right. python tools/paint/probe.py <female|male> <out.png>"""
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from body import REGIONS, UVMap  # noqa: E402

DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
COLOURS = {'torso': (200, 160, 130), 'arm': (90, 150, 220), 'hand': (40, 60, 200), 'leg': (110, 200, 110),
           'foot': (30, 120, 30), 'head': (220, 220, 60)}

m = UVMap(DATA, sys.argv[1], 1024)
img = np.zeros((m.size, m.size, 3))
for i, r in enumerate(REGIONS):
    img[m.region == i] = COLOURS[r]
# Back-facing texels darker: the body faces +y.
back = m.covered & (m.normal[..., 1] < -0.3)
img[back] *= 0.55
# Height bands every 10%.
h = m.height()
band = m.covered & ((h * 10) % 1 < 0.06)
img[band] = (255, 255, 255)
Image.fromarray(img.astype(np.uint8)).save(sys.argv[2])
lo, hi = m.bounds
print(f'{m.sex}: {len(m.vertices)} vertices, {len(m.triangles)} triangles, {m.covered.mean() * 100:.1f}% of the map covered, '
      f'bounds {lo.round(1)} .. {hi.round(1)}')
