"""Which of your BodySlide builds are zeroed -- bodies AND outfits, measured.

BodyGen morphs every piece of an NPC's outfit that has a .tri, by the same slider
names as the body. So an outfit built from a different preset than the body is
off by the difference: built from a fuller preset it floats, from a slimmer one
the body pokes through. With zeroed bodies (decision S-5) every outfit has to be
zeroed too, and a batch build that skipped one leaves no trace anywhere -- except
in the mesh.

For every OUTPUT that exists (a mesh BodySlide wrote), this compares it with the
reference mesh of the slider set that wrote it, the same way tools/base_body.py
does for the bodies. Several sets can write one output (five write FemaleBody
here); BodySlide's recorded choice (BuildSelection.xml) is used when there is
one, else whichever candidate the mesh actually matches.

    zeroed        the built mesh IS the reference (RMS offset < 0.01 units)
    <preset>      the body presets' preset reproduces the difference exactly
    not zeroed    moved, and neither of the body presets explains it
                  (--identify tries every preset of the set's slider groups)
    unverifiable  no candidate's reference matches the mesh (zapped, renamed)

    python tools/audit_builds.py                                   # Data
    python tools/audit_builds.py --built D:/F4Output/Bodyslides/woman --built D:/F4Output/Bodyslides/man
"""
import argparse
import collections
import pathlib
import struct
import sys
import xml.etree.ElementTree as ET

import base_body
import silhouette_gen as sg


def slider_groups(bodyslide):
    """{slider set name: {group names}} from SliderGroups/*.xml -- the groups
    BodySlide filters its preset list by."""
    out = collections.defaultdict(set)
    for f in (bodyslide / 'SliderGroups').glob('*.xml'):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for g in root.iter('Group'):
            for m in g.iter('Member'):
                out[m.get('name')].add(g.get('name'))
    return out


# What is left unexplained may be as large as the rounding of the built mesh and
# still be an exact match. Half floats step 1/16 of a unit between |64| and |128|,
# and uniform rounding to a step s has an RMS of s/sqrt(12) = 0.018. A SHARE alone
# is the wrong test for a mesh that barely moves: measured, a helmet whose whole
# offset is 0.011 units RMS was "1% unexplained" -- all of it rounding.
ROUNDING_RMS = 0.02


def fit(ss, shapes, disp, total, tri, presets):
    """Best (share unexplained, preset name, unexplained RMS) among `presets`."""
    count = sum(len(disp[n]) for n in shapes)
    best = None
    for p in presets:
        values = base_body.resolve(p, ss)
        resid = 0.0
        for n in shapes:
            pred = base_body._predict(values, tri[n])
            for i, (x, y, z) in enumerate(disp[n]):
                px, py, pz = pred.get(i, (0.0, 0.0, 0.0))
                resid += (x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2
        share = resid / total
        if best is None or share < best[0]:
            best = (share, p['name'], (resid / count) ** 0.5)
        if matches(best):
            break
    return best


def matches(best):
    return best is not None and (best[0] <= base_body.MATCH or best[2] <= ROUNDING_RMS)


def judge(ss, nif, ref_path, presets, likely, groups, identify):
    """One candidate slider set against one built mesh -> a verdict dict."""
    try:
        built, ref = base_body.read_shapes(nif), base_body.read_shapes(ref_path)
    except (ValueError, IndexError, KeyError, struct.error) as exc:
        return {'status': 'unverifiable', 'note': f'unreadable: {exc}'}
    shapes = [n for n in built if n in ref and len(built[n]) == len(ref[n])]
    if not shapes:
        return {'status': 'unverifiable', 'note': 'no shape matches the reference'}
    disp = {n: [(a[0] - r[0], a[1] - r[1], a[2] - r[2]) for a, r in zip(built[n], ref[n])]
            for n in shapes}
    total = sum(x * x + y * y + z * z for n in shapes for x, y, z in disp[n])
    rms = (total / sum(len(disp[n]) for n in shapes)) ** 0.5
    if rms < base_body.ZEROED_RMS:
        return {'status': 'zeroed', 'rms': rms}
    tri_path = nif.with_suffix('.tri')
    if not tri_path.exists():
        return {'status': 'not zeroed', 'rms': rms,
                'note': 'no .tri (built without Build Morphs), so BodyGen cannot move it either'}
    tri = base_body.read_tri(tri_path)
    shapes = [n for n in shapes if n in tri]
    if not shapes:
        return {'status': 'not zeroed', 'rms': rms, 'note': 'its .tri has none of its shapes'}
    first = [p for p in presets if p['name'] in likely]
    best = fit(ss, shapes, disp, total, tri, first)
    if matches(best):
        return {'status': best[1], 'rms': rms}
    if identify:
        own = groups.get(ss['name'], set())
        rest = [p for p in presets if p['name'] not in likely and set(p['families']) & own]
        other = fit(ss, shapes, disp, total, tri, rest)
        if other and (best is None or other[0] < best[0]):
            best = other
        if matches(best):
            return {'status': best[1], 'rms': rms}
    note = (f'closest "{best[1]}", {100 * best[0]:.0f}% unexplained ({best[2]:.3f} rms)' if best
            else 'no preset to compare')
    return {'status': 'not zeroed', 'rms': rms, 'note': note}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--data', type=pathlib.Path, default=sg.DEFAULT_DATA)
    ap.add_argument('--built', type=pathlib.Path, action='append', default=None,
                    help='a folder BodySlide built into (repeatable), searched before Data')
    ap.add_argument('--all', action='store_true', help='list every output, not only the problems')
    ap.add_argument('--identify', action='store_true',
                    help='name the preset of builds the body presets do not explain (slow)')
    args = ap.parse_args()
    roots = sg.built_roots(args)
    bodyslide = args.data / 'Tools/BodySlide'

    presets = sg.read_presets(bodyslide / 'SliderPresets')
    likely = set()
    for body in sg.BODIES.values():
        m = base_body.measure(args.data, body, presets, roots)
        print(f'{body}: {sg.describe(m)}')
        if m['preset']:
            likely.add(m['preset'])
    groups = slider_groups(bodyslide)

    by_output = collections.defaultdict(list)
    for ss in base_body.read_slider_sets(bodyslide):
        if ss['output']:
            by_output[ss['output']].append(ss)

    rows = []
    for output, candidates in sorted(by_output.items()):
        nif = base_body.locate(roots, output + '.nif')
        if nif is None:
            continue                                    # never built
        chosen = base_body.build_choice(bodyslide, output)
        if chosen:
            picked = [s for s in candidates if s['name'] == chosen] or candidates
        else:
            picked = candidates
        verdicts = []
        for ss in picked:
            ref_path = bodyslide / 'ShapeData' / ss['data_folder'] / ss['source_file']
            if not ref_path.exists():
                verdicts.append((ss, {'status': 'unverifiable', 'note': 'reference mesh missing'}))
                continue
            v = judge(ss, nif, ref_path, presets, likely, groups, args.identify)
            verdicts.append((ss, v))
            if v['status'] == 'zeroed' or v['status'] in likely:
                break
        # The verdict of the candidate that fits best: zeroed, then a named
        # preset, then the smallest offset; unverifiable only if all are.
        def rank(item):
            v = item[1]
            if v['status'] == 'zeroed':
                return (0, 0.0)
            if v['status'] not in ('not zeroed', 'unverifiable'):
                return (1, 0.0)
            if v['status'] == 'not zeroed':
                return (2, v.get('rms', 0.0))
            return (3, 0.0)
        ss, v = min(verdicts, key=rank)
        rows.append({'output': output, 'set': ss['name'], 'where': str(nif.parent), **v})

    by = collections.Counter(r['status'] for r in rows)
    print(f'\n{len(rows)} built outputs measured:')
    for status, n in by.most_common():
        print(f'  {n:4}  {status}')

    shown = rows if args.all else [r for r in rows if r['status'] != 'zeroed']
    if shown:
        print()
        for r in sorted(shown, key=lambda r: (r['status'], r['output'])):
            extra = f'  rms {r["rms"]:.3f}' if 'rms' in r else ''
            note = f'  -- {r["note"]}' if r.get('note') else ''
            print(f'  {r["status"][:24]:24} {r["output"]}{extra}{note}')
    bad = [r for r in rows if r['status'] not in ('zeroed', 'unverifiable')]
    print()
    if bad:
        print(f'{len(bad)} of {len(rows)} builds are NOT zeroed. With zeroed bodies they will not fit the '
              f'NPCs Silhouette shapes: rebuild them with the zeroed preset (BodySlide Batch Build).')
        return 1
    print(f'Every measurable build is zeroed ({by["zeroed"]} of {len(rows)}).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
