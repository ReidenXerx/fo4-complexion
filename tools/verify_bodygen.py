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
import re
import sys

import base_body
import catalog
import silhouette_gen as sg

# Morph names are compared in any case, as LooksMenu and the plugin compare them.
STATES = {m.casefold() for m in sg.STATE_MORPHS}
SHAFT = {m.casefold() for m in sg.SHAFT_MORPHS}


def papyrus_unescape(s):
    """The text a Papyrus string literal holds (sg.papyrus_string, read back)."""
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t'}.get(m.group(1), m.group(1)), s)

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
        out.append((i, seg.rstrip(b'\r').decode('cp1252', errors='replace')))
    if tail:
        out.append((len(segments) + 1, tail.rstrip(b'\r').decode('cp1252', errors='replace')))
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


def split_template(sets):
    """(fixed {morph: value}, ranges [(morph, low, high)] in file order, ranges_last) for a template
    of one set of one-choice selectors -- the only shape Silhouette writes -- else None. ranges_last:
    no morph has a fixed value AFTER its own range, so LooksMenu (a later entry for the same morph
    wins) lets the range replace the preset's own value (S-21). The marker, last of all, is no range's."""
    if len(sets) != 1:
        return None
    fixed, ranges, ranges_last, ranged = {}, [], True, set()
    for selector in sets[0]:
        if len(selector) != 1:
            return None
        morph, low, high = selector[0]
        if low != high:
            ranges.append((morph, low, high))
            ranged.add(morph)
        else:
            fixed[morph] = low
            if morph in ranged:
                ranges_last = False
    return fixed, ranges, ranges_last


def fixed_values(sets):
    """The body a template describes: its fixed values. The ranges are rolled per NPC on purpose
    (S-17, S-21) and checked against catalog.json on their own."""
    split = split_template(sets)
    return split[0] if split else None


def same_ranges(got, want):
    return len(got) == len(want) and all(
        a[0] == b[0] and abs(a[1] - b[1]) <= 1e-6 and abs(a[2] - b[2]) <= 1e-6 for a, b in zip(got, want))


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
                out[g][kind].append(papyrus_unescape(m.group(1)))
        else:
            m = re.match(r'(?:If|ElseIf) index == (\d+)$', s)
            if m:
                branch = int(m.group(1))
                out[g]['apply'][branch] = {}
                continue
            m = re.match(r'BodyGen\.SetMorph\(a, (True|False), "(.*)", None, (\S+)\)$', s)
            if m and branch is not None:
                out[g]['apply'][branch][papyrus_unescape(m.group(2))] = float(m.group(3))
    return out


def check_picker(args, templates, player, problems, stamp, cat):
    import json
    cat_by_marker = {p['marker'].casefold(): p for p in (cat or {}).get('presets', [])}
    mcm = args.dir.parent.parent.parent.parent.parent / 'MCM/Config/Silhouette'
    psc = args.psc
    if not (mcm / 'config.json').exists() or not psc.exists():
        problems.append(f'picker files missing ({mcm}\\config.json or {psc})')
        return
    config = json.loads((mcm / 'config.json').read_text(encoding='utf-8'))
    options, buttons, hotkeys = {}, [], []
    for page in config['pages']:
        for c in page['content']:
            if c.get('type') == 'dropdown':
                options[c['id']] = c['valueOptions']['options']
            if c.get('type') == 'button':
                buttons.append(c['action'])
            if c.get('type') == 'hotkey':
                hotkeys.append(c['id'])
    # MCM ids are "<key>:<section>", as settings.ini is laid out
    defaults, menu_build, section = {}, None, None
    for line in (mcm / 'settings.ini').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
        elif '=' in line and not line.startswith(';'):
            k, v = line.split('=', 1)
            if k.strip() == 'sBuild':
                menu_build = v.strip()
            else:
                defaults[f'{k.strip()}:{section}'] = int(v)
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
        sid = next((k for k in options if k.startswith(f'i{g.capitalize()}_')), None)
        # (the NPC page's dropdowns, iNpc<Sex>_..., are checked below)
        s = script[g]
        if sid is None and not s['names']:
            print(f'{g} picker: no preset of this sex fits the body, so the menu offers none')
            continue
        sid = sid or f'i{g.capitalize()}_?:Player'
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
            fixed = fixed_values(templates[t]) or {}
            # With no preset that fits fully the player gets the bare body (the template that sets
            # nothing), and the menu's default is simply its first entry (L4 F7).
            if any(fixed.values()) and s['markers'][d] not in fixed:
                problems.append(f'MCM default {sid} is {s["markers"][d]!r}, but the player template {t!r} '
                                f'BodyGen gives carries {[k for k in fixed if k.startswith("Silhouette_")]}')
        agree = 0
        for i, marker in enumerate(s['markers']):
            got = s['apply'][i]
            if got.get(marker) != script_stamp:
                problems.append(f'picker {g} #{i} {s["names"][i]!r}: sets no marker with the build\'s '
                                f'stamp')
            # Every branch, not only the ones the random pool has a template for: a picker-only preset
            # (a zeroed one) is compared with the body the plugin gives by the same marker.
            cp = cat_by_marker.get(marker.casefold())
            if cat is not None and (cp is None or cp['sex'] != g or cp['name'] != s['names'][i] or not same_values(
                    cp['values'], {k: v for k, v in got.items() if k != marker})):
                problems.append(f'picker {g} {s["names"][i]!r} ({marker}) is not the catalog\'s preset of that marker: '
                                f'the menu would give another body than the plugin does')
            if marker in templates:
                want = fixed_values(templates[marker])
                if want is None or set(want) != set(got) or any(
                        abs(want[k] - got[k]) > 1e-6 for k in want):
                    problems.append(f'picker {g} {s["names"][i]!r} applies different values than '
                                    f'its BodyGen template {marker}')
                else:
                    agree += 1
        print(f'{g} picker: {len(s["names"])} presets in the menu; {agree} match their BodyGen '
              f'template exactly; default {s["names"][d] if d is not None else "?"!r}')
    # Every button and hotkey calls something that exists, with no arguments: a global of the
    # generated Silhouette:Player, or a method of Silhouette:Bridge on Silhouette.esp's 0x802.
    globals_ = set(_re.findall(r'^Function (\w+)\(\) Global$', text, _re.M))
    api_src = (sg.ROOT / 'papyrus/Silhouette/API.psc').read_text(encoding='utf-8')
    api_globals = set(_re.findall(r'^Function (\w+)\(\) Global$', api_src, _re.M))
    bridge_src = (sg.ROOT / 'papyrus/Silhouette/Bridge.psc').read_text(encoding='utf-8')
    methods = set(_re.findall(r'^Function (\w+)\(\)\s*$', bridge_src, _re.M))

    def callable_(a):
        if a.get('params'):
            return False
        if a.get('type') == 'CallGlobalFunction' and a.get('script') == 'Silhouette:Player':
            return a.get('function') in globals_
        if a.get('type') == 'CallGlobalFunction' and a.get('script') == 'Silhouette:API':
            return a.get('function') in api_globals
        if a.get('type') == 'CallFunction' and a.get('form') == sg.BRIDGE_FORM:
            return a.get('function') in methods
        return False

    for a in buttons:
        if not callable_(a):
            problems.append(f'MCM button calls {a} -- neither a Silhouette:Player global nor a '
                            f'Silhouette:Bridge method on {sg.BRIDGE_FORM}')
    keyfile = mcm / 'keybinds.json'
    keybinds = json.loads(keyfile.read_text(encoding='utf-8'))['keybinds'] if keyfile.exists() else []
    bound = {k['id']: k['action'] for k in keybinds}
    for h in hotkeys:
        if h not in bound:
            problems.append(f'MCM hotkey {h!r} has no keybind in keybinds.json: pressing it would do nothing')
    for kid, a in bound.items():
        if not callable_(a):
            problems.append(f'keybind {kid!r} calls {a} -- not a Silhouette:Bridge method on {sg.BRIDGE_FORM}')

    # The NPC page offers exactly the player's lists, and NpcChoice reads the same ids.
    for g in ('female', 'male'):
        nid = next((k for k in options if k.startswith(f'iNpc{g.capitalize()}_')), None)
        if nid is None:
            if script[g]['names']:
                problems.append(f'the NPC page has no {g} dropdown, but {len(script[g]["names"])} {g} presets '
                                f'fit: "Give them this preset" could never offer one')
            continue
        if options[nid] != script[g]['names']:
            problems.append(f'MCM {nid} lists other presets than the player picker: NpcChoice would give '
                            f'a different preset than the menu shows')
        d = defaults.get(nid)
        if d is None or not 0 <= d < len(script[g]['names']):
            problems.append(f'MCM default {nid}={d} is not an entry of the menu')
        if f'"{nid}")' not in text:
            problems.append(f'Silhouette:Player.NpcChoice does not read {nid}')
    for key in ('bORefit:General', 'bNippleRand:General', 'bGenitalRand:General'):
        if key not in defaults:
            problems.append(f'settings.ini has no default for {key}: MCM would read it as off')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--data', type=pathlib.Path, default=sg.DEFAULT_DATA)
    ap.add_argument('--built', type=pathlib.Path, action='append', default=None,
                    help='a folder BodySlide built into (repeatable), searched before Data')
    ap.add_argument('--dir', type=pathlib.Path,
                    default=sg.ROOT / 'data/F4SE/Plugins/F4EE/BodyGen/Loose',
                    help='the folder holding Silhouette_templates.ini -- or a mod folder / Data '
                         'folder above it, where F4SE/Plugins/F4EE/BodyGen/Loose is looked for')
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

    # A mod folder or Data given instead of the BodyGen folder itself (the first plumbing pass
    # crashed on exactly that): look below it before giving up with a sentence, not a traceback.
    if not (args.dir / 'Silhouette_templates.ini').exists():
        below = args.dir / 'F4SE/Plugins/F4EE/BodyGen/Loose'
        if (below / 'Silhouette_templates.ini').exists():
            args.dir = below
        else:
            raise SystemExit(f'no Silhouette_templates.ini in {args.dir} or in {below}')
    print(f'checking {args.dir}')

    problems = []
    templates = parse_templates(args.dir / 'Silhouette_templates.ini', problems)
    rules = parse_morphs(args.dir / 'Silhouette_morphs.ini', templates, problems)
    print(f'{len(templates)} templates parse, {len(rules)} rules')

    # A runtime state in a template lands in the unkeyed layer, where nothing ever takes it
    # away again: a permanent erection, a permanently opened body (decision S-16). In any case:
    # "erection" is Erection to LooksMenu.
    for t, sets in templates.items():
        states = sorted({m for s in sets for sel in s for m, _, _ in sel if m.casefold() in STATES})
        if states:
            problems.append(f'template {t} sets {", ".join(states)}: a runtime state baked into a body for good')
        shaft = sorted({m for s in sets for sel in s for m, _, _ in sel if m.casefold() in SHAFT})
        if shaft:
            problems.append(f'template {t} sets {", ".join(shaft)}: the shaft is never part of a body (S-29)')

    # The catalog the plugin reads, and what both files' headers say about the run that wrote them.
    import json as _json
    groot = args.dir.parent.parent.parent.parent.parent
    cfile = groot / 'F4SE/Plugins/Silhouette/catalog.json'
    cat = _json.loads(cfile.read_text(encoding='utf-8')) if cfile.exists() else None
    if cat is None:
        problems.append(f'no catalog.json ({cfile}): Silhouette.dll would refuse to start')
    headers = {}
    for name in ('Silhouette_templates.ini', 'Silhouette_morphs.ini'):
        import re as _re0
        head = (args.dir / name).read_text(encoding='ascii', errors='replace').splitlines()[:12]
        found = next((_re0.search(r'Build (\w+), marker stamp (\d+) \(\w+\), rules (\w+)\.', h) for h in head
                      if 'Build ' in h and 'marker stamp ' in h), None)
        if not found:
            problems.append(f'{name}: its header states no build, stamp and rules: the plugin refuses it')
            continue
        headers[name] = (found.group(1), int(found.group(2)), found.group(3))
    if cat is not None:
        for name, (b, st, r) in headers.items():
            if (b, st, r) != (cat['build'], cat['stamp'], cat.get('rulesHash')):
                problems.append(f'{name} is build {b} stamp {st} rules {r}, catalog.json build {cat["build"]} '
                                f'stamp {cat["stamp"]} rules {cat.get("rulesHash")}: the plugin refuses the pair')
        # The hash names what the rules ARE: recomputed from the lines LooksMenu reads and the catalog the
        # plugin reads, a file edited after the generator wrote it no longer agrees with its header.
        lines = [text for _n, text in engine_lines(args.dir / 'Silhouette_morphs.ini', [])]
        if catalog.rules_hash(cat, lines) != cat.get('rulesHash'):
            problems.append('catalog.json or Silhouette_morphs.ini changed after the generator wrote them: their rules '
                            'no longer hash to the rules the headers name -- run the generator again')
        # The strict checks the generator ran, run on what is on disk.
        try:
            catalog.check(cat)
        except SystemExit as exc:
            problems.append(f'catalog.json: {exc}')
        for p in cat.get('presets', []):
            bad = sorted(m for m in p.get('values', {}) if m.casefold() in STATES | SHAFT)
            if bad:
                problems.append(f'catalog.json preset {p["name"]!r} carries {", ".join(bad)}: never part of a body (S-16, S-29)')

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
            # Every entry is what the plugin will believe a body of this build IS: the catalog's preset of
            # the same marker, value for value -- the heal (S-29) reads its morphs from here.
            if cat is not None:
                if manifest.get('build') != cat['build']:
                    problems.append(f'the manifest of stamp {int(stamp)} is build {manifest.get("build")}, the catalog '
                                    f'{cat["build"]}')
                by_marker = {p['marker'].casefold(): p for p in cat.get('presets', [])}
                for marker, entry in manifest.get('templates', {}).items():
                    cp = by_marker.get(marker.casefold())
                    bad = sorted(m for m in entry.get('values', {}) if m.casefold() in STATES | SHAFT)
                    if bad:
                        problems.append(f'manifest {marker}: carries {", ".join(bad)}, never part of a body (S-16, S-29)')
                    if cp is None or cp['name'] != entry.get('preset') or not same_values(entry.get('values'), cp['values']):
                        problems.append(f'manifest {marker}: not the catalog\'s preset of that marker -- the plugin would '
                                        f'name or heal bodies of this build wrongly')

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
    player_templates = set()
    for g in ('female', 'male'):
        if g not in player:
            continue
        n, groups = player[g]
        options = [t for grp in groups for t in grp]
        if len(groups) != 1 or len(options) != 1:
            problems.append(f'morphs line {n}: a {g} player is RANDOMISED among {len(options)} templates')
            continue
        player_templates.add(options[0])
        split = split_template(templates[options[0]])
        vals = split[0] if split else None
        markers = [k for k in (vals or {}) if k.startswith('Silhouette_')]
        default = next((p for p in (cat or {}).get('presets', []) if p['sex'] == g
                        and p['name'] == (cat or {}).get('player', {}).get(g)), None)
        if vals is None:
            problems.append(f'morphs line {n}: the {g} player template is not fixed-valued')
        elif split[1]:
            problems.append(f'morphs line {n}: the {g} player template rolls {", ".join(r[0] for r in split[1])} '
                            f'-- the player is never randomised (S-45)')
        elif not any(vals.values()):
            print(f'{g} player: {options[0]}, the bare body (no preset fits fully) (line {n})')
        elif len(markers) != 1 or vals[markers[0]] != stamp:
            problems.append(f'morphs line {n}: the {g} player template has no marker and would re-roll')
        elif default is None or default['marker'] != markers[0] or not same_values(
                default['values'], {k: v for k, v in vals.items() if k != markers[0]}):
            problems.append(f'morphs line {n}: the {g} player template is not the catalog\'s player default '
                            f'{(cat or {}).get("player", {}).get(g)!r} exactly')
        else:
            print(f'{g} player: {options[0]} = {default["name"]!r}, no ranges (line {n})')
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
    sg.assign_markers(presets)
    for p in presets:
        p.update(sg.classify(p, morphs_of['female'], morphs_of['male']))
    by_template = {sg.template_name(p): p for p in presets}
    cat_by_marker = {p['marker']: p for p in (cat or {}).get('presets', [])}
    want_ranges = {g: [(v['morph'], v['low'], v['high']) for v in (cat or {}).get('variety', {}).get(g, [])]
                   for g in ('female', 'male')}
    pool = {'female': [], 'male': []}
    for t in sorted(handed_out - player_templates):
        split = split_template(templates[t])
        vals = split[0] if split else None
        p = by_template.get(t)
        g = p['gender'] if p else None
        cp = cat_by_marker.get(t)
        if split and g in want_ranges and cat is not None:
            got = split[1]
            if not same_ranges(got, want_ranges[g]):
                problems.append(f'{t}: rolls {[r[0] for r in got]}, catalog.json says a {g} body rolls '
                                f'{[r[0] for r in want_ranges[g]]} (S-17, S-21)')
            elif not split[2]:
                problems.append(f'{t}: a range comes before a fixed value, so the preset\'s own value would '
                                f'win over the roll (S-21)')
        if vals is not None and cat is not None and (cp is None or not same_values(
                cp['values'], {k: v for k, v in vals.items() if k != t})):
            problems.append(f'{t}: catalog.json gives this body other values than BodyGen does -- a body the '
                            f'plugin gives would differ from the same preset rolled by BodyGen')
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
            # the BODY a preset describes: a runtime state or the shaft it happens to set is not part
            # of it (S-16, S-29)
            target = {m: v for m, v in base_body.resolve(p, base['set']).items() if m not in sg.NEVER_IN_BODY}
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
    check_picker(args, templates, player, problems, stamp, cat)

    print()
    if problems:
        print(f'FAIL - {len(problems)} problem(s):')
        for pr in problems:
            print(f'  {pr}')
        return 1
    print('PASS - every template parses as LooksMenu reads it, every reference resolves, every roll is '
          'permanent, the player is never rolled, no body holds a state or the shaft, each sex rolls exactly '
          'its catalog ranges, the plugin gives the same bodies BodyGen does, and every body lands on its preset.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
