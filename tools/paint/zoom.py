"""A close look at one painter at full texture size: python tools/paint/zoom.py <sex> <painter> <out.png> [args]
Draws the front and back at 1000 px so a 2048 texture's detail shows."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import marks  # noqa: E402
from body import UVMap  # noqa: E402
from preview import sheet  # noqa: E402

DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
sex, name, out = sys.argv[1:4]
args = [eval(a) for a in sys.argv[4:]]
m = UVMap(DATA, sex, 2048)
rng = np.random.default_rng(11)
items = [(f'{name} {k}', *getattr(marks, name)(m, rng, *args)) for k in range(2)]
print(sheet(m, items, out, height=1000))
