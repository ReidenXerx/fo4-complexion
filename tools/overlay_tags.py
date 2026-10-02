"""Merges and checks the overlay tags (docs/overlay-tags.md), and counts what there is to hand out.

    python tools/overlay_tags.py [--scan build/overlays.json] [--out build/tags.json]

Fails (exit 1) when a drawable, playable template has no tag, a tag names a template that is not installed, or
a field holds a value outside the schema. Families -- ids that differ only in a trailing colour or variant
(F_Chest_Institute_B_BR / _R_C, Neon_..._Blue) -- are made consistent: the strictest adult/lore/quality of the
family wins, so one variant cannot slip through where its twin is held back.
"""
import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAGS = ROOT / 'data' / 'tags'
KINDS = {'tattoo', 'scar', 'wound', 'burn', 'bruise', 'marks', 'dirt', 'blood', 'mole', 'freckles', 'skin', 'acne',
         'birthmark', 'pubic_hair', 'body_hair', 'nipple', 'nails', 'makeup', 'brand', 'other'}
REGIONS = {'face', 'neck', 'shoulders', 'chest', 'breasts', 'belly', 'back', 'lower_back', 'pelvis', 'pubic', 'butt',
           'arm_l', 'arm_r', 'hand_l', 'hand_r', 'leg_l', 'leg_r', 'feet', 'full_body'}
SIZES = ['tiny', 'small', 'medium', 'large', 'full']
STYLES = {'tribal', 'crude', 'military', 'emblem', 'skull', 'animal', 'floral', 'geometric', 'script', 'religious',
          'pinup', 'sexual', 'degrading', 'cartoon', 'realistic_art'}
EMBLEMS = {None, 'bos', 'minutemen', 'vault_tec', 'atom', 'institute', 'railroad', 'gunners', 'raiders', 'nuka',
           'other_fo', 'real_world'}
LORE = ['fits', 'stretch', 'breaks']
VARIANT = re.compile(r'(_(BL|BR|C|L|R|B|O|G|Y|P|W|Red|Blue|Green|Pink|Purple|Yellow|White|Black|Orange|Gold|'
                     r'Silver|Cyan|[A-Z]))+$|\d+[a-z]?$', re.I)


def family(key):
    return VARIANT.sub('', key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', type=pathlib.Path, default=ROOT / 'build' / 'overlays.json')
    ap.add_argument('--out', type=pathlib.Path, default=ROOT / 'build' / 'tags.json')
    a = ap.parse_args()
    scan = json.loads(a.scan.read_text(encoding='utf-8'))
    wanted = {('f:' if t['female'] else 'm:') + t['id']: t for t in scan['templates']
              if t['drawable'] and t.get('playable', True)}
    # Complexion's own templates (tools/paint/make_marks.py) ship with it: wanted whether or not this machine's Data
    # has them deployed yet.
    own = ROOT / 'data' / 'F4SE' / 'Plugins' / 'F4EE' / 'Overlays' / 'Complexion.esp' / 'overlays.json'
    if own.exists():
        for e in json.loads(own.read_text(encoding='utf-8')):
            wanted.setdefault(('f:' if e['gender'] >= 1 else 'm:') + e['id'], {'pack': 'Complexion.esp'})
    tags, errors = {}, []
    for f in sorted(TAGS.glob('*.json')):
        for k, v in json.loads(f.read_text(encoding='utf-8')).items():
            if k in tags:
                errors.append(f'{f.name}: {k} tagged twice')
            v['pack'] = wanted.get(k, {}).get('pack')
            tags[k] = v
    for k in sorted(set(wanted) - set(tags)):
        errors.append(f'untagged: {k}')
    for k in sorted(set(tags) - set(wanted)):
        errors.append(f'tagged but not installed and drawable: {k}')
    for k, v in tags.items():
        v['style'] = [s for s in (v.get('style') or [])]
        v['regions'] = [r for r in (v.get('regions') or [])]
        bad = []
        if v.get('kind') not in KINDS: bad.append(f'kind {v.get("kind")}')
        bad += [f'region {r}' for r in v['regions'] if r not in REGIONS]
        if v.get('size') not in SIZES: bad.append(f'size {v.get("size")}')
        bad += [f'style {s}' for s in v['style'] if s not in STYLES]
        if v.get('emblem') not in EMBLEMS: bad.append(f'emblem {v.get("emblem")}')
        if v.get('lore') not in LORE: bad.append(f'lore {v.get("lore")}')
        if not isinstance(v.get('adult'), bool): bad.append('adult not a bool')
        if v.get('quality') not in ('ok', 'poor'): bad.append(f'quality {v.get("quality")}')
        if bad:
            errors.append(f'{k}: ' + ', '.join(bad))
    # Families: the strictest variant decides.
    fams = collections.defaultdict(list)
    for k in tags:
        fams[family(k)].append(k)
    evened = 0
    for members in fams.values():
        if len(members) < 2:
            continue
        adult = any(tags[k].get('adult') for k in members)
        lore = max((tags[k].get('lore', 'fits') for k in members), key=lambda x: LORE.index(x) if x in LORE else 0)
        for k in members:
            if tags[k].get('adult') != adult or tags[k].get('lore') != lore:
                evened += 1
            tags[k]['adult'], tags[k]['lore'] = adult, lore
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(tags, indent=1, sort_keys=True), encoding='utf-8')

    usable = {k: v for k, v in tags.items() if v.get('quality') == 'ok' and v.get('lore') != 'breaks'}
    for sex in ('f', 'm'):
        mine = {k: v for k, v in usable.items() if k.startswith(sex + ':')}
        print(f'== {"female" if sex == "f" else "male"}: {len(mine)} usable '
              f'({sum(1 for k in tags if k.startswith(sex + ":"))} tagged)')
        kinds = collections.Counter(v['kind'] for v in mine.values())
        print('  kinds: ' + ', '.join(f'{k} {n}' for k, n in kinds.most_common()))
        tat = [v for v in mine.values() if v['kind'] == 'tattoo']
        print('  tattoo styles: ' + ', '.join(f'{k} {n}' for k, n in collections.Counter(
            s for v in tat for s in v['style']).most_common()))
        print('  tattoo sizes: ' + ', '.join(f'{k} {n}' for k, n in collections.Counter(
            v['size'] for v in tat).most_common()))
        print('  emblems: ' + ', '.join(f'{k} {n}' for k, n in collections.Counter(
            v['emblem'] for v in mine.values() if v['emblem']).most_common()))
        print(f'  adult: {sum(1 for v in mine.values() if v["adult"])}, '
              f'stretch: {sum(1 for v in mine.values() if v["lore"] == "stretch")}')
    held = collections.Counter(('poor' if v.get('quality') != 'ok' else 'breaks') for v in tags.values()
                               if v not in usable.values())
    print(f'held back: {dict(held)}; families evened: {evened}')
    for e in errors[:40]:
        print('  ERROR ' + e)
    print(f'{len(errors)} error(s) -> {a.out}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
