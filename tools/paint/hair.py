"""Hair colour families: one per person, matching the hair on their head (owner, 2026-10-04 -- a man with dark hair
and dark pubic hair wore a ginger chest stripe).

- family(painter, args): the family of one of Complexion's own hair templates, from the colour its painter got.
- measure(rgba): the family of another pack's hair texture, from its picture (rule 3: tags come from pictures) --
  only for packs whose material draws the texture as it is (alpha blend, white base colour: More Pubic Hair, LNR,
  TBOS). porcPubes tints one grey texture per colour in its materials: its colour is in its names (Pubic4blond,
  Pubic4brun, Pubic4ginger); its BodyHair_NN name none and stay without a family.
- python tools/paint/hair.py [--write]: every pubic_hair and body_hair tag, ours and the packs', gets "hair"; a
  pack template whose family cannot be told is left without one and never handed out (fail closed). Without
  --write it only reports, with the packs whose names state a colour as the check of the measurement.
"""
import argparse
import json
import pathlib
import re
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FAMILIES = ('black', 'darkbrown', 'brown', 'lightbrown', 'blond', 'auburn', 'ginger', 'grey')
HAIR_KINDS = ('pubic_hair', 'body_hair')
# The colours the painters are given (realism.HAIR, skin.HAIR, make_marks' constants), by family.
PAINTED = {
    'black': (0.06, 0.05, 0.04), 'darkbrown': (0.12, 0.08, 0.05), 'brown': (0.20, 0.13, 0.08),
    'lightbrown': (0.34, 0.24, 0.15), 'blond': (0.55, 0.42, 0.26), 'auburn': (0.32, 0.15, 0.08),
    'ginger': (0.42, 0.18, 0.07), 'grey': (0.45, 0.43, 0.42),
}


def family(painter, args):
    """Our template's family: a colour name among its args, else the nearest painted colour to an RGB arg, else the
    painter's default (marks.pubic_hair: near-black; the others: brown)."""
    for a in args:
        if isinstance(a, str) and a in PAINTED:
            return a
    for a in args:
        if isinstance(a, tuple) and len(a) == 3 and all(isinstance(x, float) for x in a):
            return min(PAINTED, key=lambda f: sum((x - y) ** 2 for x, y in zip(a, PAINTED[f])))
    return 'black' if painter == 'pubic_hair' else 'brown'


def measure(rgba):
    """A pack texture's family from its hair texels (alpha-weighted mean colour), or None when there is too little
    hair to tell."""
    a = rgba[..., 3].astype(np.float64) / 255
    if a.min() > 0.98:  # no alpha painted (an additive effect texture): brightness is the coverage
        a = rgba[..., :3].mean(-1) / 255
    w = np.where(a > 0.3, a, 0)
    if w.sum() < 20:
        return None
    c = (rgba[..., :3].astype(np.float64) / 255 * w[..., None]).sum((0, 1)) / w.sum()
    r, g, b = c
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    sat = (max(c) - min(c)) / max(max(c), 1e-6)
    if lum < 0.09:
        return 'black'
    if sat < 0.2 and lum > 0.3:
        return 'grey'
    if r > g * 1.5 and sat > 0.45:
        return 'ginger' if lum > 0.22 else 'auburn'
    if lum < 0.16:
        return 'darkbrown'
    if lum < 0.27:
        return 'brown'
    if lum < 0.42:
        return 'lightbrown'
    return 'blond'


NAMED = (('blond', 'blond'), ('brun', 'brown'), ('ginger', 'ginger'), ('red', 'ginger'), ('black', 'black'),
         ('grey', 'grey'), ('gray', 'grey'), ('brown', 'brown'), ('auburn', 'auburn'))


def named(tid):
    """A colour the id states as a word ("Pubic4blond_02" -> blond); never inside another word ("Mirrored")."""
    words = {w.lower() for w in re.findall(r'[A-Z]?[a-z]+', tid)}
    return next((f for token, f in NAMED if token in words), None)


def main():
    from PIL import Image
    sys.path.insert(0, str(HERE))
    import make_marks as mm

    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    ours = {('f:' if sex == 'female' else 'm:') + tid: family(painter, args)
            for tid, sex, painter, args, _size, tags in mm.MARKS if tags['kind'] in HAIR_KINDS}
    # The packs' own textures, read as the game reads them: loose in Data or unpacked from their BA2
    # (tools/overlay_sheets.py's PNG conversions came out empty for some packs: never measure those).
    sys.path.insert(0, str(ROOT / 'tools'))
    import overlay_scan
    import overlay_sheets
    scan = json.loads((ROOT / 'build' / 'overlays.json').read_text(encoding='utf-8'))
    data = pathlib.Path(scan['data'])
    archives = overlay_scan.Archives(data, overlay_scan.load_order(overlay_scan.PLUGINS, data))
    work = pathlib.Path(r'D:\F4Output\complexion')
    diffuse = {('f:' if t['female'] else 'm:') + t['id']: t['slots'][0]['diffuse'] for t in scan['templates'] if t['slots']}

    def texture(key):
        rel = diffuse.get(key)
        if not rel:
            return None
        rel = 'Textures\\' + rel.replace('/', '\\').lstrip('\\')
        if rel.lower().startswith('textures\\textures\\'):
            rel = rel[len('textures\\'):]
        if (data / rel).exists():
            return data / rel
        return overlay_sheets.unpack(archives, rel, work) if rel.lower() in archives.index else None

    agree = disagree = unknown = 0
    sheet = []
    changes = {}
    for f in sorted((ROOT / 'data' / 'tags').glob('*.json')):
        tags = json.loads(f.read_text(encoding='utf-8'))
        dirty = False
        for key, t in tags.items():
            if not isinstance(t, dict) or t.get('kind') not in HAIR_KINDS:
                continue
            if key in ours:
                fam = ours[key]
            else:
                name = named(key[2:])
                fam = None
                dds = None if key[2:].startswith(('Pubic4', 'BodyHair_')) else texture(key)  # porcPubes: tinted by material
                if dds:
                    im = Image.open(dds).convert('RGBA')
                    fam = measure(np.asarray(im))
                    sheet.append((key, fam, dds))
                if name and fam:
                    ok = fam == name or {fam, name} <= {'auburn', 'ginger'} or {fam, name} <= {'brown', 'darkbrown'}
                    agree += ok
                    disagree += not ok
                    if not ok:
                        print(f'  named {name}, measured {fam}: {key}')
                fam = name or fam
                if not fam:
                    unknown += 1
                    print(f'  no family: {key} ({t.get("note", "")})')
            changes[key] = fam
            if fam and t.get('hair') != fam:
                t['hair'] = fam
                dirty = True
            elif not fam and 'hair' in t:
                del t['hair']
                dirty = True
        if dirty and a.write:
            # Each file as it was written: make_marks' indent=1 and LF; overlay_tags' indent=0 and the line ends it
            # has (CRLF on the pack files), so the diff is only "hair".
            raw = f.read_bytes()
            second = raw.split(b'\n')[1] if b'\n' in raw else b''
            text = json.dumps(tags, indent=len(second) - len(second.lstrip(b' ')))
            f.write_bytes(text.replace('\n', '\r\n' if b'\r\n' in raw else '\n').encode('utf-8'))
    if sheet:  # the measured ones, to check by eye
        tiles = []
        for key, fam, pic in sheet:
            im = Image.open(pic).convert('RGBA').resize((256, 256))
            bg = Image.new('RGBA', im.size, (196, 160, 132, 255))
            bg.alpha_composite(im)
            from PIL import ImageDraw
            ImageDraw.Draw(bg).text((4, 4), f'{fam} {key[2:][:26]}', fill=(0, 0, 0, 255))
            tiles.append(bg)
        cols = 10
        out = Image.new('RGB', (cols * 256, -(-len(tiles) // cols) * 256), (40, 40, 40))
        for i, t in enumerate(tiles):
            out.paste(t.convert('RGB'), ((i % cols) * 256, (i // cols) * 256))
        out.save(ROOT / 'build' / 'hair_measured.jpg', quality=85)
    counts = {fam: sum(1 for v in changes.values() if v == fam) for fam in FAMILIES}
    print(f'{len(changes)} hair template(s): {counts}; {unknown} without a family; '
          f'named packs: {agree} measured the same, {disagree} not' + ('' if a.write else ' (report only: --write)'))


if __name__ == '__main__':
    main()
