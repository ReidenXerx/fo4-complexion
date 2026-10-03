"""Review sheets from the FINISHED textures (build/marks/<id>_d.png, the multiplier the game multiplies the skin by),
front and back: python tools/paint/review.py <female|male> <id prefix> <out.png> [height]"""
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from body import UVMap  # noqa: E402
from preview import SKIN, sheet  # noqa: E402

ROOT = HERE.parent.parent
DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
sex, prefix, out = sys.argv[1:4]
height = int(sys.argv[4]) if len(sys.argv) > 4 else 360
m = UVMap(DATA, sex, 2048)
tag = 'F' if sex == 'female' else 'M'
items = []
for png in sorted((ROOT / 'build' / 'marks').glob(f'{prefix}*_{tag}0*_d.png')):
    tex = np.asarray(Image.open(png).convert('RGB').resize((2048, 2048)), dtype=np.float64) / 255.0
    factor = tex * 2.0  # make_marks: texel = factor x 1/2
    # what the game draws: the skin times the factor; shown as colour over skin at full alpha
    rgb = np.clip(SKIN * factor, 0, 1)
    items.append((png.stem.replace('Complexion_', '').replace('_d', ''), rgb, np.ones(m.covered.shape)))
print(len(items), sheet(m, items, out, height=height) if items else 'none')
