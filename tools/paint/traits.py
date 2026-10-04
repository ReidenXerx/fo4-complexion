"""Who a template suits, beyond its kind (owner, 2026-10-04: nasty marks belong to marginal people; age; skin tone).

- nasty: grime, blood, open wounds, pustules, fresh bruises and burns, chafe and welts -- handed out only to people
  who live rough (each group's squalor: the elite of the Commonwealth almost never, raiders and drifters often).
- age: "young" (acne, pimples) never on the old; "old" (age spots, varicose veins, cherry angiomas) only on the
  old. Old = grey hair (C-20).
- tones: the skin tones a mark shows on as painted (freckles, sunburn, redness on lighter skin; tan lines up to
  olive; the slate-blue birthmark on olive and darker skin). No tones = any.

They are read from what a tag already says (its kind and its note, which were written from the pictures, rule 3).

    python tools/paint/traits.py [--write]     every tag file, ours and the packs'; without --write a report
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TONES = ('pale', 'light', 'olive', 'dark')
NASTY_KINDS = ('dirt', 'blood', 'wound')
NASTY_NOTES = ('fresh bruises', 'fading yellow bruises', 'finger bruises', 'acne', 'pimples', 'large blemishes',
               'fresh cigarette burns', 'radiation sores', 'grunge', 'grime', 'whip welts', 'chafe', 'rope marks',
               'pustule', 'infected', 'scab', 'sore')
YOUNG_NOTES = ('acne', 'pimple', 'blemish')
OLD_NOTES = ('age spots', 'heavy sun spots', 'varicose', 'cherry angioma')
LIGHT_ONLY = ('freckle', 'sunburn', 'blotchy redness', 'sun spots')
UP_TO_OLIVE = ('tan lines', "farmer's tan", 'tan with')
DARKER_ONLY = ('slate-blue',)


def of(tag):
    """The traits for one tag (kind + note): a dict of the fields to set; absent fields are cleared."""
    kind, note = tag.get('kind', ''), (tag.get('note') or '').lower()
    out = {}
    if kind in NASTY_KINDS or (kind in ('bruise', 'acne', 'burn', 'skin', 'marks') and any(n in note for n in NASTY_NOTES)):
        if 'faint speckled' not in note:  # a few faint pimples are just skin
            out['nasty'] = True
    if kind == 'acne' or any(n in note for n in YOUNG_NOTES):
        if 'faint speckled' not in note:
            out['age'] = 'young'
    if any(n in note for n in OLD_NOTES):
        out['age'] = 'old'
    if kind in ('freckles', 'tan', 'skin') and any(n in note for n in LIGHT_ONLY):
        out['tones'] = ['pale', 'light']
    elif kind == 'tan' and any(n in note for n in UP_TO_OLIVE):
        out['tones'] = ['pale', 'light', 'olive']
    elif any(n in note for n in DARKER_ONLY):
        out['tones'] = ['olive', 'dark']
    return out


def write(f, tags):
    """A tag file written back as it was (indent and line ends kept), so a diff shows only what changed."""
    raw = f.read_bytes()
    second = raw.split(b'\n')[1] if b'\n' in raw else b''
    text = json.dumps(tags, indent=len(second) - len(second.lstrip(b' ')))
    f.write_bytes(text.replace('\n', '\r\n' if b'\r\n' in raw else '\n').encode('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    counts = {'nasty': 0, 'young': 0, 'old': 0, 'tones': 0}
    for f in sorted((ROOT / 'data' / 'tags').glob('*.json')):
        tags = json.loads(f.read_text(encoding='utf-8'))
        dirty = False
        for key, t in tags.items():
            if not isinstance(t, dict):
                continue
            want = of(t)
            for field in ('nasty', 'age', 'tones'):
                if field in want and t.get(field) != want[field]:
                    t[field] = want[field]
                    dirty = True
                elif field not in want and field in t:
                    del t[field]
                    dirty = True
            counts['nasty'] += 'nasty' in want
            counts['young'] += want.get('age') == 'young'
            counts['old'] += want.get('age') == 'old'
            counts['tones'] += 'tones' in want
        if dirty and a.write:
            write(f, tags)
    print(f'traits: {counts}' + ('' if a.write else ' (report only: --write)'))


if __name__ == '__main__':
    sys.exit(main())
