"""Review sheet for the hands' templates (nails, C-15), from the FINISHED textures: each multiplier applied to a hands
diffuse texture, in the hands' UV layout (there is no 3D preview for the hands).

    python tools/paint/review_hands.py <female|male> <id prefix> <out.png> [hands_d.png]

The diffuse defaults to a plain skin colour; pass a PNG of the game's hands texture (texconv it from
Textures/Actors/Character/BaseHuman*/Base*Hands_d.dds) to see the nails on it.
"""
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SKIN = np.array((0.80, 0.64, 0.54))
sex, prefix, out = sys.argv[1:4]
tag = 'F' if sex == 'female' else 'M'
size = 512
if len(sys.argv) > 4:
    base = np.asarray(Image.open(sys.argv[4]).convert('RGB').resize((size, size)), dtype=np.float64) / 255.0
    base = np.clip(base / max(base.mean(), 1e-3) * 0.55, 0, 1)
else:
    base = np.ones((size, size, 3)) * SKIN
tiles = []
for png in sorted((ROOT / 'build' / 'marks').glob(f'{prefix}*_{tag}0*_d.png')):
    tex = np.asarray(Image.open(png).convert('RGB').resize((size, size)), dtype=np.float64) / 255.0
    img = Image.fromarray((np.clip(base * tex * 2.0, 0, 1) * 255).astype(np.uint8))
    ImageDraw.Draw(img).text((6, 6), png.stem.replace('Complexion_', '').replace('_d', ''), fill=(255, 255, 0))
    tiles.append(img)
if not tiles:
    sys.exit('none')
cols = min(4, len(tiles))
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new('RGB', (cols * size, rows * size), (20, 20, 20))
for k, t in enumerate(tiles):
    sheet.paste(t, ((k % cols) * size, (k // cols) * size))
sheet.save(out)
print(len(tiles), out)
