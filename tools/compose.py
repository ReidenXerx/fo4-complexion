"""Complexion's composition: which overlays one NPC gets (C-2, C-5, C-7; data/profiles.json).

This is the REFERENCE implementation. The plugin's C++ composer must give the same picks for the same inputs
(tests/compose_parity checks it), so every step here is deterministic and spelled out:

    rng      SplitMix64 seeded with the NPC's seed; percent() = next() % 100; pick(n) = next() % n
    0. the hair family (hair_colours): the head hair's, else -- when it is not one "accept" lists -- a percent roll
       walked through "unknown"; from then on a pubic_hair or body_hair template is a candidate only when its
       tagged hair is one the family accepts (one colour per person, owner 2026-10-04)
    0b. squalor (C-21): one percent roll against the group's squalor -- only a person who lives rough gets a nasty
       template; and the person's age (old = grey hair) and skin tone keep templates that do not suit them out
    1. the universal layer: for each entry of the sex, in file order, a percent roll; on success one template of
       that kind (pubic hair limited to the group's hair sizes)
    2. the feature count: a percent roll walked through the group's count table, cut to the cap
    3. the style: one of the group's styles that has a candidate, drawn once per NPC
    4. each feature: a kind by weight (each earlier pick of the same kind multiplies its weight by
       same_kind_decay), then a template of that kind that passes every rule, preferring the style
    5. priorities by layer, all negative (C-6): skin detail, scars, hair, tattoos, brands, grime, nails

    python tools/compose.py --simulate 20000      odds, caps and rules over many rolls, per group and sex
"""
import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MASK = (1 << 64) - 1
LAYERS = {'skin': -100, 'mole': -100, 'freckles': -100, 'acne': -100, 'birthmark': -100, 'nipple': -100, 'tan': -100,
          'scar': -90, 'wound': -90, 'burn': -90, 'bruise': -90, 'marks': -90,
          'pubic_hair': -80, 'body_hair': -80,
          'tattoo': -70, 'brand': -65, 'makeup': -62, 'dirt': -60, 'blood': -55, 'nails': -50}
SIZE_ORDER = ['tiny', 'small', 'medium', 'large', 'full']


class Rng:
    def __init__(self, seed):
        self.s = seed & MASK

    def next(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & MASK
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def percent(self):
        return self.next() % 100

    def pick(self, n):
        return self.next() % n


def load_catalog(tags_path):
    """Usable templates: quality ok, not lore-breaking. Keyed 'f:<id>' / 'm:<id>', sorted (a stable order is part
    of the contract: the C++ side sorts the same way)."""
    tags = json.loads(pathlib.Path(tags_path).read_text(encoding='utf-8'))
    out = []
    for key in sorted(tags):
        t = tags[key]
        if t.get('quality') != 'ok' or t.get('lore') == 'breaks':
            continue
        out.append(dict(t, key=key, female=key.startswith('f:'), id=key[2:]))
    return out


def adultish(t):
    return t['adult'] or 'degrading' in t['style'] or 'sexual' in t['style']


def group_def(profiles, name):
    """A faction group, or a named character ("npc:<name>", data/profiles.json "characters")."""
    if name.startswith('npc:'):
        return profiles['characters'][name[4:]]
    return profiles['groups'][name]


def group_names(profiles):
    """Every group in the order the plugin keeps them: the faction groups, the characters, the default last."""
    return profiles['order'] + ['npc:' + n for n in profiles.get('characters', {})] + [profiles['default']]


HAIR_KINDS = ('pubic_hair', 'body_hair')


def compose(profiles, catalog, female, group, seed, adult_allowed=True, persona='', hair='', tone=''):
    g = group_def(profiles, group)
    if g.get('untouched'):
        return []
    rules = profiles['rules']
    rng = Rng(seed)
    # 0. one hair family per person
    hc = profiles.get('hair_colours')
    accepted = None
    if hc:
        assert all(f in hc['accept'] for f, _ in hc['unknown']), 'hair_colours: unknown rolls a family accept does not list'
        if hair not in hc['accept']:
            roll, hair = rng.percent(), hc['unknown'][-1][0]
            for fam, w in hc['unknown']:
                if roll < w:
                    hair = fam
                    break
                roll -= w
        accepted = set(hc['accept'][hair])
    # 0b. who they are: rough living, age, skin tone
    squalid = rng.percent() < g.get('squalor', profiles.get('squalor_default', 30))
    old = hair == 'grey'

    def suits(t):
        if accepted is not None and t['kind'] in HAIR_KINDS and t.get('hair') not in accepted:
            return False
        if t.get('nasty') and not squalid:
            return False
        if t.get('age') == ('young' if old else 'old'):
            return False
        return not (tone and t.get('tones') and tone not in t['tones'])

    mine = [t for t in catalog if t['female'] == female and suits(t)]
    picks, used_regions, large = [], set(), False

    def take(t, kind):
        nonlocal large
        picks.append({'key': t['key'], 'kind': kind, 'priority': LAYERS.get(t['kind'], -70) + len(picks)})
        if t['kind'] in ('tattoo', 'brand', 'scar', 'wound', 'burn'):
            used_regions.update(t['regions'] or [])
        if t['size'] in ('large', 'full'):
            large = True

    # 1. universal
    for u in profiles['universal']['female' if female else 'male']:
        if len(picks) >= profiles['cap']:
            break
        roll = rng.percent()
        if roll >= u['percent'] * g.get('universal', {}).get(u['kind'], 100) // 100:
            continue
        # Emblems only for members here too: some pubic hair is trimmed into a faction's mark.
        cands = [t for t in mine if t['kind'] == u['kind'] and not adultish(t)
                 and (not t['emblem'] or t['emblem'] in g['emblems'])]
        if u['kind'] == 'pubic_hair':
            sizes = profiles['hair'][g['hair']]
            cands = [t for t in cands if t['size'] in sizes] or cands
        if cands:
            take(cands[rng.pick(len(cands))], u['kind'])

    # 1b. the persona (C-14): a Rapport persona listed in "personas" adds marks of its style, drawn before the
    #     features so the cap cannot crowd them out. Adult content only, so only while adult is allowed.
    pz = profiles.get('personas', {}).get(persona)
    if pz and adult_allowed and len(picks) < profiles['cap']:
        if rng.percent() < pz['percent']:
            roll, k = rng.percent(), 0
            for i, p in enumerate(pz['count']):
                if roll < p:
                    k = i
                    break
                roll -= p
            k = min(k, profiles['cap'] - len(picks))
            for _ in range(k):
                cands = []
                for t in mine:
                    # Any kind wearing the persona's style: lewd ink, and since C-15 hickeys, lipstick and marker too.
                    if pz['style'] not in t['style'] or any(q['key'] == t['key'] for q in picks):
                        continue
                    regions = set(t['regions'] or [])
                    if profiles['rules']['regions_unique'] and regions and (regions & used_regions or
                                                                            ('full_body' in regions and used_regions) or
                                                                            'full_body' in used_regions):
                        continue
                    cands.append(t)
                if not cands:
                    break
                t = cands[rng.pick(len(cands))]
                take(t, t['kind'])

    # 2. count
    roll, n = rng.percent(), 0
    for i, p in enumerate(g['count']):
        if roll < p:
            n = i
            break
        roll -= p
    n = min(n, profiles['cap'] - len(picks))

    # 3. style
    def style_ok(t, style):
        return style in t['style']

    feature_kinds = profiles['kinds']
    allowed_emblems = set(g['emblems'])

    def candidates(kind, adult_ok):
        out = []
        for t in mine:
            if t['kind'] not in feature_kinds[kind] or any(p['key'] == t['key'] for p in picks):
                continue
            if t['emblem'] and t['emblem'] not in allowed_emblems:
                continue
            if adultish(t) and not adult_ok:
                continue
            if kind in ('tattoo', 'brand'):
                if t['size'] not in g['sizes']:
                    continue
                if t['size'] in ('large', 'full') and large and rules['one_large']:
                    continue
            regions = set(t['regions'] or [])
            if rules['regions_unique'] and regions and (regions & used_regions or
                                                        ('full_body' in regions and used_regions) or
                                                        'full_body' in used_regions):
                continue
            out.append(t)
        return out

    styles = [s for s in g['styles'] if any(style_ok(t, s) for t in candidates('tattoo', True))]
    style = styles[rng.pick(len(styles))] if styles else None

    # 4. features
    times = collections.Counter()
    for _ in range(n):
        adult_ok = adult_allowed and g['adult'] > 0 and rng.percent() < g['adult']
        weights = []
        for kind, w in g['kinds'].items():
            if candidates(kind, adult_ok):
                weights.append((kind, w * (rules['same_kind_decay'] ** times[kind])))
        if not weights:
            break
        total = sum(w for _, w in weights)
        r = (rng.next() % 1_000_000) / 1_000_000 * total
        kind = weights[-1][0]
        for k, w in weights:
            if r < w:
                kind = k
                break
            r -= w
        cands = candidates(kind, adult_ok)
        if kind in ('tattoo', 'brand'):
            fitting = [t for t in cands if (t['emblem'] in allowed_emblems) or
                       any(s in g['styles'] for s in t['style']) or (adult_ok and adultish(t))]
            cands = fitting or ([] if g['styles'] or g['emblems'] else cands)
            if style and rng.percent() < rules['style_share'] * 100:
                cands = [t for t in cands if style_ok(t, style)] or cands
        if not cands:
            continue
        take(cands[rng.pick(len(cands))], kind)
        times[kind] += 1
    return picks


def simulate(profiles, catalog, rolls):
    bad = 0
    nasty = {t['key'] for t in catalog if t.get('nasty')}
    for group in group_names(profiles):
        for female in (True, False):
            counts, kinds, sizes = collections.Counter(), collections.Counter(), collections.Counter()
            rough = 0
            violations = collections.Counter()
            for s in range(rolls):
                picks = compose(profiles, catalog, female, group, (hash(group) & 0xFFFF) << 32 | s)
                counts[len(picks)] += 1
                rough += any(p['key'] in nasty for p in picks)
                for p in picks:
                    kinds[p['kind']] += 1
                if len(picks) > profiles['cap']:
                    violations['over cap'] += 1
                if len({p['key'] for p in picks}) != len(picks):
                    violations['duplicate'] += 1
            dist = ' '.join(f'{k}:{counts[k] * 100 // rolls}%' for k in sorted(counts))
            top = ', '.join(f'{k} {v / rolls:.2f}' for k, v in kinds.most_common(6))
            print(f'{group:11} {"F" if female else "M"}  nasty {rough * 100 // rolls:3}%  overlays {dist:44} per NPC: {top}')
            for v, c in violations.items():
                print(f'   VIOLATION {v}: {c}')
                bad += c
    return bad


HAIR_DUMP = ('', 'black', 'darkbrown', 'brown', 'lightbrown', 'blond', 'auburn', 'ginger', 'grey')
TONE_DUMP = ('', 'pale', 'light', 'olive', 'dark')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profiles', type=pathlib.Path, default=ROOT / 'data' / 'profiles.json')
    ap.add_argument('--tags', type=pathlib.Path, default=ROOT / 'build' / 'tags.json')
    ap.add_argument('--simulate', type=int, default=0)
    ap.add_argument('--dump', type=int, default=0,
                    help='picks for seeds 0..N-1 per group and sex, one line each: the parity file the C++ '
                         'composer must reproduce (ComplexionTests --parity)')
    a = ap.parse_args()
    profiles = json.loads(a.profiles.read_text(encoding='utf-8'))
    catalog = load_catalog(a.tags)
    if a.dump:
        for group in group_names(profiles):
            for female in (True, False):
                for s in range(a.dump):
                    seed = (s * 0x9E3779B97F4A7C15 + 12345) & MASK
                    for adult in (True, False):
                        for persona in ('', 'vulgar'):
                            # The hair families in turn, and "" (unknown: rolled), one per seed so the file stays
                            # its size while every family is covered across the seeds.
                            hair = HAIR_DUMP[s % len(HAIR_DUMP)]
                            tone = TONE_DUMP[(s // 3) % len(TONE_DUMP)]
                            picks = compose(profiles, catalog, female, group, seed, adult, persona, hair, tone)
                            # Tab-separated: group names ("npc:Piper Wright") and template ids have spaces.
                            print(f'{group}\t{"f" if female else "m"}\t{seed}\t{int(adult)}\t{persona}\t{hair}\t{tone}\t' +
                                  ','.join(f'{p["key"]}@{p["priority"]}' for p in picks))
        for group in group_names(profiles)[:3] + [profiles['default']]:
            for female in (True, False):
                for s in range(30):
                    seed = (s * 0xD1B54A32D192ED03 + 777) & MASK
                    for hair in HAIR_DUMP + ('purple',):
                        for tone in TONE_DUMP:
                            picks = compose(profiles, catalog, female, group, seed, True, '', hair, tone)
                            print(f'{group}\t{"f" if female else "m"}\t{seed}\t1\t\t{hair}\t{tone}\t' +
                                  ','.join(f'{p["key"]}@{p["priority"]}' for p in picks))
        return
    if a.simulate:
        sys.exit(1 if simulate(profiles, catalog, a.simulate) else 0)


if __name__ == '__main__':
    main()
