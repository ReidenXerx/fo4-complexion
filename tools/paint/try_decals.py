"""A sampler of drawn tattoos on one body: python tools/paint/try_decals.py <female|male> <out.png>"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import decals as d  # noqa: E402
from body import UVMap  # noqa: E402
from preview import sheet  # noqa: E402

DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
sex = sys.argv[1]
m = UVMap(DATA, sex, 2048)
rng = np.random.default_rng(3)
items = [
    ('NO MERCY chest', *d.project(m, d.word('No Mercy', 'blackletter', arc=0.08), 'chest', 0, width=12)),
    ('RUST forearm', *d.project(m, d.word('RUST', 'stencil'), 'forearm', 1, width=6, ink='faded', crude=0.8, seed=2)),
    ('Hope script', *d.project(m, d.word('Hope', 'script'), 'hip', 1, width=6)),
    ('barcode neck', *d.project(m, d.barcode(rng), 'neck_back', 0, width=5)),
    ('mandala back', *d.project(m, d.mandala(rng), 'upper_back', 0, width=12)),
    ('tribal lower back', *d.project(m, d.tribal(rng), 'lower_back', 0, width=16)),
    ('band upper arm', *d.project(m, d.band(rng), 'upper_arm', -1, width=10)),
    ('atom', *d.project(m, d.emblem('atom'), 'shoulder', 1, width=6)),
    ('vault-tec', *d.project(m, d.emblem('vault_tec'), 'forearm', -1, width=5)),
    ('BoS', *d.project(m, d.emblem('bos'), 'upper_back', 0, width=12)),
    ('raider skull', *d.project(m, d.emblem('raiders'), 'chest', 1, width=6, crude=0.6, seed=4)),
    ('prison dots', *d.project(m, d.prison_dots(), 'forearm', 1, width=2, ink='faded')),
]
print(sheet(m, items, sys.argv[2], height=420))
