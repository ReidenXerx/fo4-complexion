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
    """std::explode as LooksMenu's Utilities.cpp has it: empty pieces are dropped."""
    return [p for p in s.split(sep) if p]


def engine_lines(path, problems):
    """[(line number, text)] exactly as LooksMenu gets them.

    Both parsers loop `while (textFile.ReadLine(&str))`, and ReadLine is the
    engine's BSResourceTextFile::ReadLine: it returns the number of bytes before
    the '\n', and the loop stops on 0. So with LF endings the first EMPTY line
    ends the file -- every template and rule after it is silently never read.
    With CRLF an "empty" line is '\r' and survives. So: every line must end
    CRLF, and a zero-length line fails the file.
    """
    raw = path.read_bytes()
    segments = raw.split(b'\n')
    tail = segments.pop()                 # after the last '\n': EOF, or an unterminated line
    out = []
    for i, seg in enumerate(segments, 1):
        if len(seg) == 0:
            rest = sum(1 for x in segments[i:] if x.strip()) + (1 if tail.strip() else 0)
            problems.append(f'{path.name}:{i}: an EMPTY line -- LooksMenu stops reading here, and the '
                            f'{rest} line(s) with content after it are never read')
            return out
        if not seg.endswith(b'\r'):
            problems.append(f'{path.name}:{i}: a bare LF line ending -- one blank line away from '
                            f'ending the file for LooksMenu; write CRLF')
        if len(seg) >= LINE_LIMIT:
            problems.append(f'{path.name}:{i}: line is {len(seg)} bytes, LooksMenu reads it in '
                            f'{LINE_LIMIT - 1}-byte pieces')
        out.append((i, seg.rstrip(b'\r').decode('ascii', errors='replace')))
    if tail:
        out.append((len(segments) + 1, tail.rstrip(b'\r').decode('ascii', errors='replace')))
    return out


def parse_templates(path, problems):
    """{name: [alternative sets]}, each set a list of selectors, each selector a
    list of (morph, low, high). A template with any bad entry is DROPPED, as
    LooksMenu drops it."""
    out = {}
    for n, raw in engine_lines(path, problems):
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
        if name.casefold() in {k.casefold() for k in out}:
            problems.append(f'{path.name}:{n}: template {name!r} defined twice (LooksMenu compares '
                            f'names case-insensitively); the later wins')
        out[name] = sets
    return out


def parse_morphs(path, templates, problems):
    """[(left side tokens, [[template names]])] in file order."""
    rules = []
    for n, raw in engine_lines(path, problems):
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


def same_values(a, b):
    if a is None:
        return False
    return set(a) == set(b) and all(abs(a[k] - b[k]) <= 1e-6 for k in a)


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


def parse_picker_script(path):
    """{gender: {'markers': [...], 'names': [...], 'apply': {index: {morph: value}}}}
    read back out of the generated Silhouette:Player source."""
    import re
    out = {'female': {'markers': [], 'names': [], 'apply': {}},
           'male': {'markers': [], 'names': [], 'apply': {}}}
    current, branch = None, None
    for line in path.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if s.startswith('String[] Function') or s.startswith('String Function Apply'):
            m = re.match(r'String\[\] Function (Female|Male)(Markers|Names)\(', s)
            if m:
                current = (m.group(1).lower(), m.group(2).lower())
                continue
            m = re.match(r'String Function Apply(Female|Male)\(', s)
            current = (m.group(1).lower(), 'apply') if m else None
            branch = None
            continue
        if s == 'EndFunction':
            current = None
            continue
        if not current:
            continue
        g, kind = current
        if kind in ('markers', 'names'):
            m = re.match(r'a\.Add\("(.*)", 1\)$', s)
            if m:
                out[g][kind].append(m.group(1))
        else:
            m = re.match(r'(?:If|ElseIf) index == (\d+)$', s)
            if m:
                branch = int(m.group(1))
                out[g]['apply'][branch] = {}
                continue
            m = re.match(r'BodyGen\.SetMorph\(a, (True|False), "(.*)", None, (\S+)\)$', s)
            if m and branch is not None:
                out[g]['apply'][branch][m.group(2)] = float(m.group(3))
    return out


def check_picker(args, templates, player, problems, stamp):
    import json
    mcm = args.dir.parent.parent.parent.parent.parent / 'MCM/Config/Silhouette'
    psc = args.psc
    if not (mcm / 'config.json').exists() or not psc.exists():
        problems.append(f'picker files missing ({mcm}\\config.json or {psc})')
        return
    config = json.loads((mcm / 'config.json').read_text(encoding='utf-8'))
    options, buttons = {}, []
    for page in config['pages']:
        for c in page['content']:
            if c.get('type') == 'dropdown':
                options[c['id']] = c['valueOptions']['options']
            if c.get('type') == 'button':
                buttons.append(c['action'])
    defaults, menu_build = {}, None
    for line in (mcm / 'settings.ini').read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.startswith(';'):
            k, v = line.split('=', 1)
            if k.strip() == 'sBuild':
                menu_build = v.strip()
            else:
                defaults[f'{k.strip()}:Player'] = int(v)
    import re as _re
    text = psc.read_text(encoding='utf-8')
    m = _re.search(r'String Function Build\(\) Global\s+Return "([^"]*)"', text)
    script_build = m.group(1) if m else None
    m = _re.search(r'Float Function Stamp\(\) Global\s+Return (\d+)\.0', text)
    script_stamp = float(m.group(1)) if m else None
    if script_build is None or script_build != menu_build:
        problems.append(f'the script is build {script_build}, the menu {menu_build}: ApplyChosen would '
                        f'refuse -- install the generated files together')
    if stamp is not None and script_stamp != stamp:
        problems.append(f'the script stamps markers {script_stamp}, the BodyGen files {stamp}')
    script = parse_picker_script(psc)
    for g in ('female', 'male'):
        sid = next((k for k in options if k.startswith(f'i{g.capitalize()}_')), f'i{g.capitalize()}_?:Player')
        s = script[g]
        if options.get(sid) != s['names']:
            problems.append(f'MCM {sid} lists {len(options.get(sid, []))} presets, the script {len(s["names"])} '
                            f'-- the menu would apply a different preset than it shows')
        if len(s['markers']) != len(s['names']) or sorted(s['apply']) != list(range(len(s['names']))):
            problems.append(f'{g} picker script: markers, names and branches do not line up')
            continue
        d = defaults.get(sid)
        if d is None or not 0 <= d < len(s['names']):
            problems.append(f'MCM default {sid}={d} is not an entry of the menu')
        elif g in player and [x for grp in player[g][1] for x in grp]:
            t = [x for grp in player[g][1] for x in grp][0]
            if s['markers'][d] != t:
                problems.append(f'MCM default {sid} is {s["markers"][d]!r}, BodyGen gives the player {t!r}')
        agree = 0
        for i, marker in enumerate(s['markers']):
            if s['apply'][i].get(marker) != script_stamp:
                problems.append(f'picker {g} #{i} {s["names"][i]!r}: sets no marker with the build\'s '
                                f'stamp')
            if marker in templates:
                want = fixed_values(templates[marker])
                got = s['apply'][i]
                if want is None or set(want) != set(got) or any(
                        abs(want[k] - got[k]) > 1e-6 for k in want):
                    problems.append(f'picker {g} {s["names"][i]!r} applies different values than '
                                    f'its BodyGen template {marker}')
                else:
                    agree += 1
        print(f'{g} picker: {len(s["names"])} presets in the menu; {agree} match their BodyGen '
              f'template exactly; default {s["names"][d] if d is not None else "?"!r}')
    for a in buttons:
        if a.get('type') != 'CallGlobalFunction' or a.get('script') != 'Silhouette:Player':
            problems.append(f'MCM button calls {a} -- not a Silhouette:Player global')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--data', type=pathlib.Path, default=sg.DEFAULT_DATA)
    ap.add_argument('--built', type=pathlib.Path, action='append', default=None,
                    help='a folder BodySlide built into (repeatable), searched before Data')
    ap.add_argument('--dir', type=pathlib.Path,
                    default=sg.ROOT / 'data/F4SE/Plugins/F4EE/BodyGen/Loose')
    ap.add_argument('--psc', type=pathlib.Path, default=sg.ROOT / 'papyrus/Silhouette/Player.psc',
                    help='the generated picker script source to check against the menu')
    args = ap.parse_args()
    roots = sg.built_roots(args)
    body_file = {b: base_body.locate(roots, f'Meshes/Actors/Character/CharacterAssets/{b}.nif')
                 for b in sg.BODIES.values()}
    for b, f in body_file.items():
        if f is None or not f.with_suffix('.tri').exists():
            raise SystemExit(f'no {b}.nif + .tri in {", ".join(map(str, roots))}')
        print(f'{b}: {f.parent}')

    problems = []
    templates = parse_templates(args.dir / 'Silhouette_templates.ini', problems)
    rules = parse_morphs(args.dir / 'Silhouette_morphs.ini', templates, problems)
    print(f'{len(templates)} templates parse, {len(rules)} rules')

    # A runtime state in a template lands in the unkeyed layer, where nothing ever takes it
    # away again: a permanent erection, a permanently opened body (decision S-16).
    for t, sets in templates.items():
        states = sorted({m for s in sets for sel in s for m, _, _ in sel if m in sg.STATE_MORPHS})
        if states:
            problems.append(f'template {t} sets {", ".join(states)}: a runtime state baked into a body for good')

    # ---- which templates each gender's pool holds, and what the player gets.
    # LooksMenu lets a later line overwrite an earlier one per NPC, so the player's
    # table entry is whatever the LAST line naming them says.
    def sets_nothing(t):
        vals = fixed_values(templates[t])
        return vals is not None and not any(vals.values())

    # Every marker carries the build's stamp (its value); the manifest of that
    # stamp says what each marker means.
    stamps = {fixed_values(v).get(k) for k, v in templates.items()
              if fixed_values(v) and fixed_values(v).get(k)}
    stamp = next(iter(stamps)) if len(stamps) == 1 else None
    if len(stamps) != 1:
        problems.append(f'markers carry {len(stamps)} different stamps ({sorted(stamps)[:4]}): one build '
                        f'writes one stamp')
    manifest = None
    if stamp:
        mroot = args.dir.parent.parent.parent.parent.parent
        mfile = mroot / 'F4SE/Plugins/Silhouette/manifests' / f'{int(stamp)}.json'
        if not mfile.exists():
            problems.append(f'no manifest for stamp {int(stamp)} ({mfile}): NPCs rolled by these files '
                            f'could never be interpreted')
        else:
            import json as _json
            manifest = _json.loads(mfile.read_text(encoding='utf-8'))
            print(f'stamp {int(stamp)}, build {manifest.get("build")}, {manifest.get("mode")}, '
                  f'{len(manifest.get("templates", {}))} templates in its manifest')

    handed_out = set()          # every template any line can give an NPC
    player, dummies = {}, {}
    for form, groups, n in rules:
        low = [x.lower() for x in form]
        for grp in groups:
            if len(grp) > 1 and any(sets_nothing(t) for t in grp):
                problems.append(f'morphs line {n}: a template that sets nothing shares a choice with '
                                f'others -- an NPC that rolls it is rolled again on the next load, and '
                                f'again, until it lands on one that sets something')
            handed_out.update(t for t in grp if not sets_nothing(t))
        # The two character-creation dummies: LooksMenu clones the chosen one's
        # body onto the player on confirm, so they must get what the player gets.
        if low[0] == 'fallout4.esm' and len(low) >= 3 and low[1].lstrip('0') in ('a7d35', 'a7d34'):
            dummies[{'a7d35': 'female', 'a7d34': 'male'}[low[1].lstrip('0')]] = (n, groups)
        # Lines that reach the Player record: All|G|HumanRace, Fallout4.esm|All|G|HumanRace
        # and Fallout4.esm|7[|G]. The last one per gender is what the player gets.
        genders = None
        if low[0].startswith('all') and len(low) >= 3 and low[-1] == 'humanrace':
            genders = [low[1]]
        elif low[0] == 'fallout4.esm' and len(low) >= 4 and low[1] == 'all' and low[-1] == 'humanrace':
            genders = [low[2]]
        elif low[0] == 'fallout4.esm' and len(low) >= 2 and low[1] == '7':
            genders = [low[2]] if len(low) > 2 else ['female', 'male']
        for g in genders or []:
            if g in ('female', 'male'):
                player[g] = (n, groups)
    for g in ('female', 'male'):
        if g not in player:
            continue
        n, groups = player[g]
        options = [t for grp in groups for t in grp]
        if len(groups) != 1 or len(options) != 1:
            problems.append(f'morphs line {n}: a {g} player is RANDOMISED among {len(options)} templates')
            continue
        vals = fixed_values(templates[options[0]])
        if vals is None:
            problems.append(f'morphs line {n}: the {g} player template is not fixed-valued')
        elif any(vals.values()) and vals.get(options[0]) != stamp:
            problems.append(f'morphs line {n}: the {g} player template has no marker and would re-roll')
        else:
            print(f'{g} player: {options[0]} (line {n})')
        d = dummies.get(g)
        mine = options[0]
        if d is None:
            problems.append(f'no line for the {g} character-creation dummy: a new game would clone its '
                            f'RANDOM roll onto the player')
        elif [t for grp in d[1] for t in grp] != [mine]:
            problems.append(f'morphs line {d[0]}: the {g} dummy gets {[t for grp in d[1] for t in grp]}, '
                            f'the player {mine!r} -- a new game would clone the dummy\'s')

    # ---- every template handed out must be fixed-valued and carry its own marker
    tris = {g: base_body.read_tri(body_file[b].with_suffix('.tri')) for g, b in sg.BODIES.items()}
    morphs_of = {g: set().union(*t.values()) for g, t in tris.items()}
    presets = sg.read_presets(args.data / 'Tools/BodySlide/SliderPresets')
    for p in presets:
        p.update(sg.classify(p, morphs_of['female'], morphs_of['male']))
    by_template = {sg.template_name(p): p for p in presets}
    pool = {'female': [], 'male': []}
    for t in sorted(handed_out):
        vals = fixed_values(templates[t])
        p = by_template.get(t)
        if vals is None:
            problems.append(f'{t}: not a single fixed-value set; cannot verify')
        elif vals.get(t) != stamp:
            problems.append(f'{t}: no marker "{t}@<stamp>" -- a roll that sets nothing re-rolls every load')
        elif manifest is not None and not same_values(manifest.get('templates', {}).get(t, {}).get('values'),
                                                      {k: v for k, v in vals.items() if k != t}):
            problems.append(f'{t}: its values differ from the manifest of stamp {int(stamp)}')
        elif p is None or p['gender'] not in pool:
            problems.append(f'{t}: no preset of that name to compare with')
        elif t in morphs_of[p['gender']]:
            problems.append(f'{t}: the marker names a real morph and would move the body')
        else:
            pool[p['gender']].append(t)

    # ---- build every body and compare it with its preset

    worst = {}
    for g, body in sg.BODIES.items():
        own = [p for p in presets if p['gender'] == g and p['kind'] != 'empty']
        base = base_body.measure(args.data, body, own, roots)
        print(f'\n{g}: {sg.describe(base)}')
        if base['set'] is None:
            problems.append(f'{g}: base body cannot be measured, so nothing can be verified')
            continue
        ref_all = base_body.read_shapes(args.data / 'Tools/BodySlide/ShapeData'
                                        / base['set']['data_folder'] / base['set']['source_file'])
        built_all = base_body.read_shapes(body_file[body])
        shapes = [n for n in built_all if n in ref_all and n in tris[g]]
        rows = []
        for t in pool[g]:
            p = by_template.get(t)
            vals = fixed_values(templates[t])
            if p is None or vals is None:
                problems.append(f'{t}: no preset of that name to compare with')
                continue
            # the BODY a preset describes: a runtime state it happens to set is not part of it (S-16)
            target = {m: v for m, v in base_body.resolve(p, base['set']).items() if m not in sg.STATE_MORPHS}
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
            # Every body off by exactly the uncompensated error means one cause, not
            # 58: absolute files on a base that still has a preset baked in.
            if base['status'] == 'preset' and bad and all(abs(r[0] - r[2]) < 1e-3 for r in bad):
                problems.append(f'{g}: all {len(bad)} bodies land rms {bad[0][0]:.3f} off because {body} '
                                f'still has "{base["preset"]}" baked in and these files are absolute. '
                                f'Rebuild {body} zeroed (the generator prints how), then verify again.')
                bad = []
            for r in bad:
                problems.append(f'{r[4]}: lands {r[1]:.3f} units (rms {r[0]:.4f}) off its preset')
            print(f'  {len(rows)} bodies built; worst lands {rows[0][1]:.4f} units off (rms {rows[0][0]:.4f}); '
                  f'uncompensated, the average NPC would be off by rms '
                  f'{sum(r[2] for r in rows) / len(rows):.3f}')

    # ---- the player picker: the MCM menu, its defaults and the generated script
    # must agree with each other and with the templates above.
    check_picker(args, templates, player, problems, stamp)

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
