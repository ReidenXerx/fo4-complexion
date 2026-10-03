"""One of each realism painter, front and back: python tools/paint/try_realism.py <female|male> <out.png>"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import realism as r  # noqa: E402
from body import UVMap  # noqa: E402
from preview import sheet  # noqa: E402

DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
sex = sys.argv[1]
m = UVMap(DATA, sex, 1024)
rng = np.random.default_rng(5)
items = [('freckles', *r.freckles(m, rng, 0.7)), ('birthmark', *r.birthmark(m, rng)), ('pores', *r.pores(m, rng, 0.8)),
         ('veins', *r.veins(m, rng)), ('stretch', *r.stretch_marks(m, rng)), ('pimples', *r.pimples(m, rng, 0.6)),
         ('nipples brown', *r.nipples(m, rng, 'brown', sex == 'female'))]
if sex == 'female':
    items += [('pubic natural', *r.pubic_female(m, rng, 'natural', 'brown', 1024)),
              ('pubic landing', *r.pubic_female(m, rng, 'landing', 'black', 1024)),
              ('stubble', *r.stubble_female(m, rng, 'brown', 1024))]
else:
    items += [('chest hair', *r.body_hair_male(m, rng, 'chest', 'brown', 1024)),
              ('limb hair', *r.body_hair_male(m, rng, 'limbs', 'black', 1024))]
print(sheet(m, items, sys.argv[2]))
