"""Prove the written BodyGen files do what they claim.

Reads Silhouette_templates.ini and Silhouette_morphs.ini the way LooksMenu reads
them (f4ee/BodyGenInterface.cpp, ReadBodyMorphTemplates and ReadBodyMorphs), then
builds every body those files can put on an NPC and compares it with the body the
preset describes:

    what LooksMenu shows  = installed base mesh + sum(template value * diff)
    what the preset means = BodySlide reference mesh + sum(preset value * diff)

They must agree to within the half-float rounding of the installed mesh. The
same comparison is made for the naive, uncompensated file, which shows how far
off every NPC would be if the templates ignored what the base has baked in.

It tests the ARTIFACT, not the generator: a template LooksMenu would drop, a
reference it would not resolve, a line longer than its 0x7FFF buffer, a missing
marker or a player guard that sets something is a failure here even if the
generator believes it wrote something correct.

    python tools/verify_bodygen.py                # the files in this repo
    python tools/verify_bodygen.py --dir <Loose>  # any other copy
"""
import argparse
import math
import pathlib
import sys

import base_body
import silhouette_gen as sg

LINE_LIMIT = 0x7FFF        # BSResourceTextFile<0x7FFF>
MAX_ERROR = 0.1            # game units; half floats step 0.0625 above |64|
RMS_ERROR = 0.01


def explode(s, sep):
    """std::explode as LooksMenu uses it: plain split, empty pieces kept."""
    return s.split(sep)


def parse_templates(path, problems):
    """{name: [alternative sets]}, each set a list of selectors, each selector a
    list of (morph, low, high). A template with any bad entry is DROPPED, as
    LooksMenu drops it."""
    out = {}
    for n, raw in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
        if len(raw) >= LINE_LIMIT:
            problems.append(f'{path.name}:{n}: line is {len(raw)} chars, LooksMenu reads {LINE_LIMIT - 1}')
        line = raw.strip()
        if not line or line[0] == '#':
            continue
        side = explode(line, '=')
        if len(side) < 2:
            problems.append(f'{path.name}:{n}: no "=", LooksMenu logs an error')
            continue
        name, rside = side[0].strip(), side[1].strip()
        sets, error = [], None
        for s in explode(rside, '/'):
            morphs = []
            for m in explode(s.strip(), ','):
                selector = []
                for sel in explode(m.strip(), '|'):
                    pair = explode(sel.strip(), '@')
                    if len(pair) < 2:
                        error = f'no "@" in {sel.strip()!r}'
                        break
                    morph, values = pair[0].strip(), pair[1].strip()
                    if not morph or not values:
                        error = f'empty morph or value in {sel.strip()!r}'
                        break
                    rng = explode(values, ':')
                    try:
                        low = float(rng[0]) if len(rng) > 1 else float(values)
                        high = float(rng[1]) if len(rng) > 1 else low
                    except ValueError:
                        error = f'value {values!r} is not a number (atof would read garbage)'
                        break
                    selector.append((morph, low, high))
                if error:
                    break
                morphs.append(selector)
            if error:
                break
            sets.append(morphs)
        if error:
            problems.append(f'{path.name}:{n}: template {name!r} DROPPED by LooksMenu: {error}')
            continue
        if name in out:
            problems.append(f'{path.name}:{n}: template {name!r} defined twice; the later wins')
        out[name] = sets
    return out


def parse_morphs(path, templates, problems):
    """[(left side tokens, [[template names]])] in file order."""
    rules = []
    for n, raw in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
        if len(raw) >= LINE_LIMIT:
            problems.append(f'{path.name}:{n}: line is {len(raw)} chars, LooksMenu reads {LINE_LIMIT - 1}')
        line = raw.strip()
        if not line or line[0] == '#':
            continue
        side = explode(line, '=')
        if len(side) < 2:
            problems.append(f'{path.name}:{n}: no "="')
            continue
        form = [t.strip() for t in explode(side[0].strip(), '|')]
        if len(form) < 2:
            problems.append(f'{path.name}:{n}: left side needs a mod name or All, and more')
            continue
        groups = []
        for g in explode(side[1].strip(), ','):
            names = [t.strip() for t in explode(g.strip(), '|')]
            for t in names:
                if t not in templates:
                    problems.append(f'{path.name}:{n}: template {t!r} not found (LooksMenu skips it)')
            groups.append([t for t in names if t in templates])
        rules.append((form, groups, n))
    return rules


def fixed_values(sets):
    """The morph values of a template that has one set of one-choice, fixed-value
    selectors -- the only shape Silhouette writes."""
    if len(sets) != 1:
        return None
    out = {}
    for selector in sets[0]:
        if len(selector) != 1:
            return None
        morph, low, high = selector[0]
        if low != high:
            return None
        out[morph] = low
    return out


def apply(mesh, values, tri_shape):
    out = [list(v) for v in mesh]
    for morph, w in values.items():
        if w == 0:
            continue
        for i, (x, y, z) in tri_shape.get(morph, {}).items():
            out[i][0] += w * x
            out[i][1] += w * y
            out[i][2] += w * z
    return out


def error(a, b):
    d = [math.dist(p, q) for p, q in zip(a, b)]
    return max(d), math.sqrt(sum(x * x for x in d) / len(d))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--data', type=pathlib.Path, default=sg.DEFAULT_DATA)
    ap.add_argument('--dir', type=pathlib.Path,
                    default=sg.ROOT / 'data/F4SE/Plugins/F4EE/BodyGen/Loose')
    args = ap.parse_args()

    problems = []
    templates = parse_templates(args.dir / 'Silhouette_templates.ini', problems)
    rules = parse_morphs(args.dir / 'Silhouette_morphs.ini', templates, problems)
    print(f'{len(templates)} templates parse, {len(rules)} rules')

    # ---- which templates each gender's pool holds, and the player guard
    pool = {'female': [], 'male': []}
    guard_ok = False
    for form, groups, n in rules:
        head = form[0].lower()
        if head.startswith('all') and len(form) >= 3:
            gender = form[1].lower()
            if gender in pool:
                pool[gender] += [t for g in groups for t in g]
        elif form[0].lower() == 'fallout4.esm' and form[1] == '7':
            for g in groups:
                for t in g:
                    vals = fixed_values(templates[t])
                    if vals is None or any(vals.values()):
                        problems.append(f'morphs line {n}: the player guard {t!r} sets something')
                    else:
                        guard_ok = True
    if not guard_ok:
        problems.append('no player guard: a player with no LooksMenu body sliders gets randomised')

    # ---- every pooled template must be fixed-valued and carry its own marker
    assets = args.data / 'Meshes/Actors/Character/CharacterAssets'
    tris = {g: base_body.read_tri(assets / f'{b}.tri') for g, b in sg.BODIES.items()}
    morphs_of = {g: set().union(*t.values()) for g, t in tris.items()}
    for g in pool:
        for t in pool[g]:
            vals = fixed_values(templates[t])
            if vals is None:
                problems.append(f'{t}: not a single fixed-value set; cannot verify')
            elif vals.get(t) != 1.0:
                problems.append(f'{t}: no marker "{t}@1" -- a roll that sets nothing re-rolls every load')
            elif t in morphs_of[g]:
                problems.append(f'{t}: the marker names a real morph and would move the body')

    # ---- build every body and compare it with its preset
    presets = sg.read_presets(args.data / 'Tools/BodySlide/SliderPresets')
    for p in presets:
        p.update(sg.classify(p, morphs_of['female'], morphs_of['male']))
    by_template = {sg.template_name(p): p for p in presets}

    worst = {}
    for g, body in sg.BODIES.items():
        own = [p for p in presets if p['gender'] == g and p['kind'] != 'empty']
        base = base_body.measure(args.data, body, own)
        print(f'\n{g}: {sg.describe(base)}')
        if base['set'] is None:
            problems.append(f'{g}: base body cannot be measured, so nothing can be verified')
            continue
        ref_all = base_body.read_shapes(args.data / 'Tools/BodySlide/ShapeData'
                                        / base['set']['data_folder'] / base['set']['source_file'])
        built_all = base_body.read_shapes(assets / f'{body}.nif')
        shapes = [n for n in built_all if n in ref_all and n in tris[g]]
        rows = []
        for t in pool[g]:
            p = by_template.get(t)
            vals = fixed_values(templates[t])
            if p is None or vals is None:
                problems.append(f'{t}: no preset of that name to compare with')
                continue
            target = base_body.resolve(p, base['set'])
            e_max = e_rms = n_max = n_rms = 0.0
            for s in shapes:
                shown = apply(built_all[s], vals, tris[g][s])
                meant = apply(ref_all[s], target, tris[g][s])
                naive = apply(built_all[s], target, tris[g][s])
                a, b = error(shown, meant)
                c, d = error(naive, meant)
                e_max, e_rms = max(e_max, a), max(e_rms, b)
                n_max, n_rms = max(n_max, c), max(n_rms, d)
            rows.append((e_rms, e_max, n_rms, n_max, t, p['name']))
        rows.sort(reverse=True)
        print(f'  {"template":44} {"max":>7} {"rms":>7}   uncompensated max / rms')
        for e_rms, e_max, n_rms, n_max, t, name in rows[:6]:
            print(f'  {t[:44]:44} {e_max:7.4f} {e_rms:7.4f}   {n_max:7.3f} / {n_rms:5.3f}')
        if len(rows) > 6:
            print(f'  ... {len(rows) - 6} more, all better than the rows above')
        if rows:
            worst[g] = rows[0]
            bad = [r for r in rows if r[1] > MAX_ERROR or r[0] > RMS_ERROR]
            for r in bad:
                problems.append(f'{r[4]}: lands {r[1]:.3f} units (rms {r[0]:.4f}) off its preset')
            print(f'  {len(rows)} bodies built; worst lands {rows[0][1]:.4f} units off (rms {rows[0][0]:.4f}); '
                  f'uncompensated, the average NPC would be off by rms '
                  f'{sum(r[2] for r in rows) / len(rows):.3f}')

    print()
    if problems:
        print(f'FAIL - {len(problems)} problem(s):')
        for pr in problems:
            print(f'  {pr}')
        return 1
    print('PASS - every template parses as LooksMenu reads it, every reference resolves, '
          'every roll is permanent, the player is untouched, and every body lands on its preset.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
