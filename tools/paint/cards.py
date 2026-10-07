"""Feature cards for the installer and the Nexus page, rendered from what Complexion really hands out.

    python tools/paint/cards.py            -> docs/img/{groups,composition,characters,marks,packs,cheap}.jpg

Looks are composed by tools/compose.py (the reference composer) from build/tags.json and data/profiles.json, the
pack textures are the ones tools/overlay_sheets.py converted (D:\\F4Output\\complexion\\png), Complexion's own are
build/marks/*.png; each look is composited in its priority order onto the body's UV map and drawn front and back
(preview.py). Nude bodies, as the overlays are worn (owner, 2026-09-30: nude renders may ship).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import compose  # noqa: E402
from body import UVMap  # noqa: E402
from preview import view  # noqa: E402

ROOT = HERE.parent.parent
DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
PNG = pathlib.Path(r'D:\F4Output\complexion\png')
SIZE = 1024
BG = (24, 24, 28)
INK = (236, 226, 200)
ACCENT = (214, 168, 92)


def font(n):
    for f in ('segoeuib.ttf', 'arialbd.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(f, n)
        except OSError:
            pass
    return ImageFont.load_default()


def pack_pngs():
    """'f:<id>' -> the converted texture, by overlay_sheets.py's own numbering (sex, then scan order)."""
    scan = json.loads((ROOT / 'build' / 'overlays.json').read_text(encoding='utf-8'))
    out = {}
    for sex in ('f', 'm'):
        items = [t for t in scan['templates'] if t['drawable'] and t['female'] == (sex == 'f') and t.get('playable', True)]
        for k, t in enumerate(items):
            folder = PNG / f'{sex}{k}'
            hits = list(folder.glob('*.png')) if folder.exists() else []
            if hits:
                out[f'{sex}:{t["id"]}'] = hits[0]
    return out


class Looks:
    def __init__(self):
        self.profiles = json.loads((ROOT / 'data' / 'profiles.json').read_text(encoding='utf-8'))
        self.catalog = compose.load_catalog(ROOT / 'build' / 'tags.json')
        self.pngs = pack_pngs()
        self.maps = {s: UVMap(DATA, s, SIZE) for s in ('female', 'male')}
        self.cache = {}

    def texture(self, key):
        if key in self.cache:
            return self.cache[key]
        path = self.pngs.get(key)
        if path is None:
            own = ROOT / 'build' / 'marks' / f'{key[2:]}_d.png'
            path = own if own.exists() else None
        if path is None:
            self.cache[key] = None
            return None
        im = Image.open(path).convert('RGBA').resize((SIZE, SIZE), Image.LANCZOS)
        arr = np.asarray(im, dtype=np.float64) / 255.0
        a = arr[..., 3]
        if a.min() >= 0.98:  # an additive effect texture without alpha: brightness is coverage
            a = arr[..., :3].mean(-1)
        self.cache[key] = (arr[..., :3], a)
        return self.cache[key]

    def look(self, group, female, seed):
        picks = compose.compose(self.profiles, self.catalog, female, group, seed)
        rgb = np.zeros((SIZE, SIZE, 3))
        alpha = np.zeros((SIZE, SIZE))
        for p in sorted(picks, key=lambda x: x['priority']):
            t = self.texture(p['key'])
            if t is None:
                continue
            c, a = t
            out = a + alpha * (1 - a)
            rgb = (c * a[..., None] + rgb * (alpha * (1 - a))[..., None]) / np.maximum(out, 1e-6)[..., None]
            alpha = out
        return picks, rgb, alpha

    def render(self, group, female, seed, side='front', height=520):
        picks, rgb, alpha = self.look(group, female, seed)
        m = self.maps['female' if female else 'male']
        return picks, view(m, rgb, alpha, side, height)


def card(title, line, tiles, path, cols=None):
    """A card: title, one line, then labelled tiles [(label, image)]."""
    cols = cols or len(tiles)
    tw = max(t.width for _, t in tiles)
    th = max(t.height for _, t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    W = max(1600, cols * (tw + 16) + 48)
    H = 150 + rows * (th + 46) + 30
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 30), title, fill=ACCENT, font=font(52))
    d.text((40, 96), line, fill=INK, font=font(26))
    x0 = (W - cols * (tw + 16)) // 2
    for i, (label, t) in enumerate(tiles):
        x = x0 + (i % cols) * (tw + 16)
        y = 150 + (i // cols) * (th + 46)
        img.paste(t, (x + (tw - t.width) // 2, y))
        d.text((x + 8, y + th + 6), label, fill=INK, font=font(24))
    img.save(path, quality=88)
    print(path)


def best_seed(looks, group, female, want, tries=60):
    """A seed whose look is typical of the group -- the wanted number of overlays -- and, among those, shows the
    most: a card of six near-bare bodies tells nothing. Every look shown is one the composer really gives."""
    best, best_cover = 1000, -1.0
    for s in range(tries):
        picks, _, alpha = looks.look(group, female, 1000 + s)
        if len(picks) != want:
            continue
        cover = float(alpha.sum())
        if cover > best_cover:
            best, best_cover = 1000 + s, cover
    return best


def pair(looks, group, female, seed, height):
    """Front and back side by side."""
    _, f = looks.render(group, female, seed, 'front', height)
    _, b = looks.render(group, female, seed, 'back', height)
    im = Image.new('RGB', (f.width + b.width, max(f.height, b.height)), BG)
    im.paste(f, (0, 0))
    im.paste(b, (f.width, 0))
    return im


def main():
    looks = Looks()
    out = ROOT / 'docs' / 'img'
    out.mkdir(parents=True, exist_ok=True)

    # groups: the same woman as four different people
    tiles = []
    for label, group, n in (('Settler', 'settlers', 2), ('Raider', 'raiders', 5), ('Brotherhood', 'bos', 2),
                            ('Institute', 'institute', 1), ('Disciple', 'disciples', 5), ('Captive', 'captives', 4)):
        seed = best_seed(looks, group, True, n)
        tiles.append((label, pair(looks, group, True, seed, 460)))
    card('Who they are decides', 'The same body, six people: a group\'s own odds, kinds and styles pick every overlay.',
         tiles, out / 'groups.jpg', cols=3)

    # composition: one raider, front and back, with what was picked
    seed = best_seed(looks, 'raiders', True, 5)
    picks, f = looks.render('raiders', True, seed, 'front', 640)
    _, b = looks.render('raiders', True, seed, 'back', 640)
    names = ', '.join(p['kind'].replace('_', ' ') for p in sorted(picks, key=lambda x: x['priority']))
    card('One look, not a pile', f'A raider: {len(picks)} overlays, one style, no two on one spot -- {names}.',
         [('front', f), ('back', b)], out / 'composition.jpg')

    # characters
    tiles = []
    for name, female in (('Cait', True), ('Piper Wright', True), ('Fahrenheit', True), ('Nisha', True),
                         ('Paladin Danse', False), ('Porter Gage', False)):
        seed = best_seed(looks, 'npc:' + name, female, {'Piper Wright': 2}.get(name, 4))
        tiles.append((name, pair(looks, 'npc:' + name, female, seed, 460)))
    card('The named people', 'Looks from their stories, not dice: the cage fighter, the reporter, the bodyguard, the knife.',
         tiles, out / 'characters.jpg', cols=3)

    # marks: Complexion's own, on their own
    tiles = []
    m = {'female': looks.maps['female'], 'male': looks.maps['male']}
    for label, key, sex, side in (('bruises', 'f:Complexion_BruiseFresh_F02', 'female', 'back'),
                                  ('grime', 'f:Complexion_GrimeHeavy_F01', 'female', 'front'),
                                  ('dried blood', 'f:Complexion_Blood_F01', 'female', 'front'),
                                  ('whip welts', 'm:Complexion_LashesFresh_M01', 'male', 'back'),
                                  ('handprints', 'f:Complexion_Spank_F01', 'female', 'back'),
                                  ('his basics', 'm:Complexion_PubicFull_M01', 'male', 'front')):
        t = looks.texture(key)
        if t is None:
            continue
        rgb, a = t
        if key.endswith('PubicFull_M01'):
            for extra in ('m:Complexion_Moles_M01', 'm:Complexion_Scar_M01'):
                e = looks.texture(extra)
                if e:
                    na = e[1] + a * (1 - e[1])
                    rgb = (e[0] * e[1][..., None] + rgb * (a * (1 - e[1]))[..., None]) / np.maximum(na, 1e-6)[..., None]
                    a = na
        tiles.append((label, view(m[sex], rgb, a, side, 520)))
    card('Its own marks', 'Painted on the body in 3D and baked into its own UV map: bruises, grime, blood, welts -- and men\'s basics.',
         tiles, out / 'marks.jpg')

    # packs: what it reads, by kind
    kinds = {}
    for t in looks.catalog:
        kinds[t['kind']] = kinds.get(t['kind'], 0) + 1
    tiles = []
    for group, female, label in (('settlers', True, 'settler'), ('pack', True, 'the Pack'), ('operators', True, 'Operator'),
                                 ('gunners', False, 'Gunner')):
        seed = best_seed(looks, group, female, 3)
        tiles.append((label, pair(looks, group, female, seed, 460)))
    # Kinds, no counts: numbers in a picture go stale with every release (the owner's rule, 10-04).
    top = ', '.join(k.replace('_', ' ') for k, n in sorted(kinds.items(), key=lambda x: -x[1])[:6])
    card('Your packs, read as LooksMenu reads them', f'Every template tagged from its picture: {top}.',
         tiles, out / 'packs.jpg', cols=2)

    # cheap: the measured comparison, as a text card
    img = Image.new('RGB', (1600, 900), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 30), 'Cheap, and kind to other mods', fill=ACCENT, font=font(52))
    rows = [('', 'Random Overlay Framework', 'Complexion'),
            ('decides', 'in Papyrus, every load of every NPC', 'once, in the plugin, kept'),
            ('waits per NPC', 'random 0.1-2.5 s waits, several', 'none'),
            ('rebuilds per NPC', 'one LooksMenu Update per category', 'one, ever'),
            ('faction lookup', 'an IsInFaction chain, every load', 'by record, in C++'),
            ('stacking', 'the done-check never passes: re-adds', 'one look, checked with GetAll'),
            ('other mods\' overlays', 'removed one uid at a time', 'kept, drawn on top'),
            ('AAF scenes', 'not looked at', 'nobody is touched in one')]
    y = 130
    for i, (a, b, c) in enumerate(rows):
        f = font(30 if i == 0 else 27)
        colour = ACCENT if i == 0 else INK
        d.text((40, y), a, fill=colour, font=f)
        d.text((420, y), b, fill=colour, font=f)
        d.text((1060, y), c, fill=colour, font=f)
        y += 82 if i == 0 else 88
    d.text((40, 840), 'From Random Overlay Framework 2.483\'s own scripts, decompiled (docs/complexion-research.md).', fill=(150, 150, 150), font=font(22))
    img.save(out / 'cheap.jpg', quality=88)
    print(out / 'cheap.jpg')


if __name__ == '__main__':
    main()
