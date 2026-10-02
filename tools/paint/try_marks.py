"""One of each painter on each body, drawn front and back: python tools/paint/try_marks.py <female|male> <out.png>"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import marks  # noqa: E402
from body import UVMap  # noqa: E402
from preview import sheet  # noqa: E402

DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
sex = sys.argv[1]
m = UVMap(DATA, sex, 1024)
rng = np.random.default_rng(7)
items = [
    ('bruises fresh', *marks.bruises(m, rng, (3, 5), 'fresh')),
    ('bruises old', *marks.bruises(m, rng, (3, 5), 'old')),
    ('grime', *marks.grime(m, rng, 0.7)),
    ('dried blood', *marks.dried_blood(m, rng)),
    ('lashes fresh', *marks.lashes(m, rng)),
    ('lashes healed', *marks.lashes(m, rng, healed=True)),
    ('spank', *marks.spank(m, rng)),
]
if sex == 'male':
    items += [('moles', *marks.moles(m, rng)), ('scars', *marks.scars(m, rng, (2, 3))),
              ('scars stitched', *marks.scars(m, rng, (1, 2), True)), ('pubic full', *marks.pubic_hair(m, rng, 'full', 1024)),
              ('pubic trail', *marks.pubic_hair(m, rng, 'trail', 1024))]
print(sheet(m, items, sys.argv[2]))
