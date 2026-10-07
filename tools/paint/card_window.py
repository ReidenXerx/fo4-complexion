"""The overlay window's feature card (C-19), from the window's own pictures.

    python tools/paint/card_window.py      -> docs/img/window.jpg

The tiles are cells of the atlases the window shows (tools/paint/thumbs.py), labelled with the tag notes the window
shows under them; the numbers are counted from thumbs.json, not typed.
"""
import json
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cards import card  # noqa: E402

ROOT = HERE.parent.parent
CELL, COLS = 128, 32
# One of each, from the realism layer up (the owner's accent): what a player scrolls through.
# Close-ups (marks with a measured spot): a body-wide mark's picture is the whole figure, small.
WANT = ['f:Complexion_NipplesRose_F01', 'f:Complexion_CigBurns_F01', 'f:Complexion_BulletScars_F01',
        'f:Complexion_PubicBikiniBlond_F01', 'f:Complexion_LineaNigra_F01', 'f:Complexion_ScarThin_F02',
        'f:Complexion_Keloid_F01', 'f:Complexion_FlashSwallowPair_F01', 'f:Complexion_BruiseFresh_F01',
        'f:Complexion_PortWine_F01', 'f:Complexion_BiteShoulder_F01', 'f:Complexion_TattooMandalaThigh_F01']


def main():
    index = json.loads((ROOT / 'data' / 'F4SE' / 'Plugins' / 'Complexion' / 'thumbs.json').read_text(encoding='utf-8'))
    tags = json.loads((ROOT / 'data' / 'tags' / 'complexion.json').read_text(encoding='utf-8'))
    notes = {k: t.get('note', '') for k, t in tags.items()}
    atlas = Image.open(ROOT / 'data' / 'Textures' / 'Complexion' / f"ThumbsFemale_{index['build']}_0.dds").convert('RGB')
    cells = index['cells']
    keys = [k for k in WANT if k in cells]
    if len(keys) < 8:  # names moved: the first pictured ones instead
        keys += [k for k in cells if k.startswith('f:') and k not in keys][:12 - len(keys)]
    tiles = []
    for k in keys[:12]:
        n = cells[k][1]
        pic = atlas.crop(((n % COLS) * CELL, (n // COLS) * CELL, (n % COLS + 1) * CELL, (n // COLS + 1) * CELL))
        label = (notes.get(k) or k.split('_', 1)[1]).split(',')[0]
        while len(label) > 24 or label.rsplit(' ', 1)[-1] in ('on', 'the', 'of', 'in', 'a'):
            label = label.rsplit(' ', 1)[0]
        tiles.append((label, pic.resize((300, 300), Image.LANCZOS)))
    total = len(cells)
    spots = len(index.get('focus', {}))
    # No counts in the picture: they change with every overlay release, and the page text carries them (the
    # owner's rule, 10-04; the 699 baked here went stale at 0.1.6).
    del total, spots
    card('Choose by hand', 'Aim, press the hotkey, click: Complexion\'s own with pictures, every pack\'s by name, '
         'live on them. A pick takes the camera to where the mark sits.',
         tiles, ROOT / 'docs' / 'img' / 'window.jpg', cols=6)


if __name__ == '__main__':
    main()
