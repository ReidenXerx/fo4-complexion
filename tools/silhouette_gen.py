"""Silhouette, Phase 1: turn your BodySlide presets into LooksMenu BodyGen files.

Every NPC gets one of your presets the first time it loads, and keeps it for the
rest of that save. The distribution itself is done by LooksMenu's own BodyGen,
which is already switched on in f4ee.ini and was simply never fed. This tool
writes what feeds it; there is no runtime code in Phase 1 at all.

WHAT MAKES IT BETTER THAN SHIPPING A FIXED BODYGEN FILE -- everything is MEASURED
against the bodies you actually have installed:

1. Which presets can do anything at all. LooksMenu applies a morph by name and
   only morphs present in the body's .tri can move a vertex, so a preset whose
   sliders are absent from your .tri is a silent no-op. On the machine this was
   written on, 27 of 120 presets (Fusion Girl, Atomic Beauty) would have done
   nothing on a CBBE body. They are left out rather than handed out.

2. What your base body already has baked into it (tools/base_body.py). BodyGen
   adds morphs ON TOP of the mesh on disk, so a body built from any preset but
   Zeroed Sliders makes every NPC preset stack on it -- the classic "why are all
   my NPCs enormous". Measured on the machine this was written on: FemaleBody was
   built from "CBBE Chubby" and MaleBody from "BT - Average", and nothing said so.
   The tool names the baked preset exactly and tells you to rebuild zeroed -- the
   owner's choice (S-5) and the standard setup. For an install that cannot be
   rebuilt, --compensate writes every template RELATIVE to what is baked (target
   minus baked, per slider), so every NPC still lands exactly on its preset:
   LooksMenu applies a morph as vertex += diff * value with no clamp
   (BodyMorphInterface.cpp ApplyMorph) and parses values with atof.

Everything below is taken from sources, not from documentation summaries:

- BodyGen grammar: LooksMenu's own parser, f4ee/BodyGenInterface.cpp.
    templates.ini   Name = Morph@value, Morph@low:high, ...   (',' = all applied)
    morphs.ini      All|Female|HumanRace = T1|T2|...          ('|' = one at random)
  A LATER line OVERWRITES an earlier one for the same NPC, so rule priority is
  simply file order. A morph that evaluates to 0 is SKIPPED before SetMorph.
- An NPC with NO stored morphs is evaluated AGAIN on every load (ActorUpdateManager
  only runs BodyGen when GetMorphMap is empty). So a template that sets nothing
  re-rolls the NPC each load: a zero template is not "keep the base", it is "roll
  again next time". Every Silhouette template therefore also sets one MARKER
  morph named after itself -- no body has it, so it moves nothing
  (BodyMorphInterface::SetMorph stores any name), but it makes the roll permanent
  and records which preset the NPC got, for Phase 2 to read back.
- The one place a re-roll is wanted is the player, who must never be given a
  body: `Fallout4.esm|7` is the Player record, and its template sets nothing.
  Without that line, a player with no LooksMenu body sliders is randomised on the
  next load -- `All|...|HumanRace` includes the Player record.
- `All|Female` WITHOUT a race matches only NPCs with no race at all
  (GetFilteredNPCList compares the NPC's race to a null filter). Always name one.
- Loose files: LooksMenu reads Data/F4SE/Plugins/F4EE/BodyGen/Loose/*_templates.ini
  and *_morphs.ini whatever plugins are loaded, AFTER the per-plugin folders. So
  Phase 1 needs no .esp, and cannot collide with another BodyGen mod's files.
- Slider values: see tools/base_body.py -- big value, else the slider set's
  default (BodyTalk 4 has 26 sliders defaulting to 100), inverted if flagged.

    python tools/silhouette_gen.py                  # measure and report only
    python tools/silhouette_gen.py --write          # also write the BodyGen files
    python tools/silhouette_gen.py --no-partial     # random pool = full fits only
    python tools/silhouette_gen.py --compensate     # for a base that is NOT zeroed
"""
import argparse
import collections
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

import base_body

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DATA = pathlib.Path(r'D:\GOGGames\Fallout 4 GOTY\Data')

FULL_FIT = 0.95      # this share of a preset's sliders must exist on the body
PARTIAL_FIT = 0.50   # below this a preset does too little to be worth handing out
BODIES = {'female': 'FemaleBody', 'male': 'MaleBody'}

# A preset's `set` attribute is NOT what the preset is for. It is whichever slider
# set happened to be open in BodySlide when the preset was saved. Measured: seven
# CBBE body presets on the machine this was written on carry sets like
# "POP AR Vest D" and "Jumpsuit_Vault" while declaring <Group name="CBBE"/> --
# they are bodies whose authors had an outfit open. An earlier version of this
# tool classed them as outfits by set name and threw seven good bodies away.
#
# The authored signal is <Group>: 116 of 120 presets declare the body families
# they are for. A group naming an outfit or a clothing pack is not a family.
NOT_A_FAMILY = re.compile(
    r'outfit|clothing|costume|dress|corset|suit|jumpsuit|armor|armour|\bxy -|2pac', re.I)

# A preset tuned for BUILDING OUTFITS rather than for a nude body: a second copy
# of a body style with the shape eased off. Handing them out as well would double
# the weight of every style that ships one. Kept aside -- ORefit may want them.
CLOTHED_VARIANT = re.compile(r'\(outfit\)|clothing|clothed|for outfit|\boutfit\b', re.I)

# Every character LooksMenu's template parser splits on (BodyGenInterface.cpp:
# '=' then '/' then ',' then '|' then '@').
BODYGEN_SEPARATORS = re.compile(r'[=/,|@]')

PLAYER_GUARD = 'Silhouette_KeepBase'


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def read_presets(folder):
    """Every <Preset>, read the way BodySlide reads it (SliderPresets.cpp):
    recursive, first preset of a name wins, size="big" or "both" gives the big
    value, and a SetSlider with no size is ignored. Values come out 0..1."""
    out, seen_names = [], set()
    for f in sorted(folder.rglob('*.xml')):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError as exc:
            print(f'  skipped unparseable preset file {f.name}: {exc}')
            continue
        for p in root.iter('Preset'):
            name = p.get('name')
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            big, small_only = {}, set()
            for s in p.iter('SetSlider'):
                slider, size = s.get('name'), (s.get('size') or '').lower()
                try:
                    value = float(s.get('value')) / 100.0
                except (TypeError, ValueError):
                    continue
                if size in ('big', 'both'):
                    big[slider] = value
                elif size == 'small':
                    small_only.add(slider)
            groups = [g.get('name', '') for g in p.findall('Group')]
            out.append({
                'name': name,
                'set': p.get('set', ''),
                'families': sorted({g for g in groups if g and not NOT_A_FAMILY.search(g)}),
                'file': str(f.relative_to(folder)),
                'sliders': big,
                # BodySlide builds these at the set's default for Fallout 4.
                'small_only': len(small_only - set(big)),
            })
    return out


# --------------------------------------------------------------------------
# classifying
# --------------------------------------------------------------------------

def classify(preset, female_morphs, male_morphs):
    """-> gender, fit (0..1) and kind (body | clothed-variant | empty)."""
    sliders = set(preset['sliders'])
    if not sliders:
        return {'gender': None, 'fit': 0.0, 'kind': 'empty'}
    f_fit = len(sliders & female_morphs) / len(sliders)
    m_fit = len(sliders & male_morphs) / len(sliders)
    gender = 'female' if f_fit >= m_fit else 'male'
    kind = 'clothed-variant' if CLOTHED_VARIANT.search(preset['name']) else 'body'
    return {'gender': gender, 'fit': max(f_fit, m_fit), 'kind': kind}


def installed_family(presets, gender):
    """The body family the installed body belongs to, read off the data.

    Whichever family the FULL-fit body presets of this gender most often declare.
    On the machine this was written on that is "CBBE" for women and a BodyTalk
    family for men -- but nothing here names a body, so a Fusion Girl or Atomic
    Beauty install gets the right answer with no configuration.
    """
    counts = collections.Counter()
    for p in presets:
        if p['gender'] == gender and p['kind'] == 'body' and p['fit'] >= FULL_FIT:
            counts.update(p['families'])
    return counts.most_common(1)[0][0] if counts else None


def band(preset, family):
    """full | partial | other-family | none.

    A PARTIAL fit counts only when the preset is for this body's family, or
    declares no family at all and so leaves it to measurement. Sharing a slider
    NAME with a different body is not sharing a SHAPE: measured, a Fusion Girl
    preset overlaps a CBBE body by 53% through coincident names. True Wasteland
    Body presets overlap 77-83% and declare CBBE, because TWB is built on CBBE --
    those names do mean the same shapes.
    """
    fit = preset['fit']
    if fit >= FULL_FIT:
        return 'full'
    if fit < PARTIAL_FIT:
        return 'none'
    declared = preset['families']
    if declared and family not in declared:
        return 'other-family'
    return 'partial'


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def template_name(preset):
    # A template name is split on '=' and looked up as an exact string. Keep it to
    # characters that survive both files: letters, digits and underscores.
    safe = re.sub(r'[^A-Za-z0-9]+', '_', preset['name']).strip('_')
    return f'Silhouette_{safe}'


def target_values(preset, base):
    """{morph: value 0..1} this preset puts the body at, as BodySlide would build it."""
    if base['set']:
        return base_body.resolve(preset, base['set'])
    return dict(preset['sliders'])      # no set to read defaults from: as written


def template_line(name, target, baked, morphs_on_body, preset_name):
    """What LooksMenu must add to the base body to reach `target`, as BodyGen text.

    Only morphs the body has (others move nothing and only bloat the co-save),
    only non-zero differences, and always the marker -- see the module docstring.
    LooksMenu splits a template on '/', ',', '|', '@' and '=', so a morph whose
    NAME holds one would be cut in two; those are skipped with a warning. Spaces
    are fine ("7B Lower" is a real master slider).
    """
    return [f'{m}@{fmt(v)}' for m, v in morph_values(name, target, baked, morphs_on_body, preset_name)]


def describe(base):
    if base['status'] == 'zeroed':
        return f'{base["note"]} -- nothing baked in'
    if base['status'] == 'preset':
        return f'{base["note"]}  ({100 * base["unexplained"]:.3f}% unexplained)'
    return base['note']


def built_roots(args):
    """Where the built bodies are looked for: every --built folder, then Data."""
    return list(args.built or []) + [args.data]


def fmt(v):
    """A float both LooksMenu (atof) and the Papyrus compiler read: fixed point,
    never exponent notation, no trailing zeros."""
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s


def morph_values(name, target, baked, morphs_on_body, preset_name):
    """[(morph, value)] LooksMenu must add to the base body to reach `target`, the
    marker last. Shared by the BodyGen templates and the player picker so the two
    can never disagree about what a preset is."""
    out = []
    for morph in sorted(set(target) | set(baked)):
        if morph not in morphs_on_body:
            continue
        if BODYGEN_SEPARATORS.search(morph):
            print(f'  skipped morph {morph!r} in {preset_name!r}: its name holds a BodyGen separator')
            continue
        v = target.get(morph, 0.0) - baked.get(morph, 0.0)
        if abs(v) < 5e-5:
            continue
        out.append((morph, v))
    out.append((name, 1.0))
    return out


# --------------------------------------------------------------------------
# the player picker: an MCM menu and the script it calls
# --------------------------------------------------------------------------

MOD = 'Silhouette'
SCRIPT = 'Silhouette:Player'


def papyrus_string(s):
    return '"' + s.replace('\\', '/').replace('"', "'") + '"'


def write_mcm(folder, picker, default_index, average):
    """MCM/Config/Silhouette: a dropdown per sex and three buttons, all calling
    global functions of Silhouette:Player -- so no plugin is needed. Both the
    dropdown shape (ModSettingInt + options) and CallGlobalFunction buttons are
    the ones already working in this install (CommonwealthEncounterDirector,
    Rapport)."""
    content = [
        {'type': 'text', 'text': 'Every NPC gets one of your BodySlide presets the first time you '
                                 'meet them. Your own character gets the most average of them '
                                 'unless you choose one here.'},
        {'type': 'section', 'text': 'Your character'},
    ]
    for g, label in (('female', 'If your character is female'), ('male', 'If your character is male')):
        if not picker[g]:
            continue
        content.append({
            'type': 'dropdown', 'id': f'i{g.capitalize()}:Player', 'text': label,
            'help': f'{len(picker[g])} presets that fit your {g} body. Nothing changes until you '
                    f'press "Apply to my character".',
            'valueOptions': {'sourceType': 'ModSettingInt',
                             'options': [e['display'] for e in picker[g]]},
        })
    avg = ' / '.join(average[g] for g in ('female', 'male') if average.get(g))
    content += [
        {'type': 'button', 'text': 'Apply to my character',
         'help': 'Gives your character the preset chosen above for their sex. It REPLACES their '
                 'body sliders, including any you set in LooksMenu yourself. Close the menu to see it.',
         'action': {'type': 'CallGlobalFunction', 'script': SCRIPT, 'function': 'ApplyChosen',
                    'params': []}},
        {'type': 'button', 'text': 'Back to the default',
         'help': f'The most average body of your presets: {avg}.',
         'action': {'type': 'CallGlobalFunction', 'script': SCRIPT, 'function': 'ApplyDefault',
                    'params': []}},
        {'type': 'button', 'text': 'Which body do I have?',
         'help': 'Names the preset your character has now.',
         'action': {'type': 'CallGlobalFunction', 'script': SCRIPT, 'function': 'ShowCurrent',
                    'params': []}},
    ]
    config = {'modName': MOD, 'displayName': MOD, 'minMcmVersion': 1,
              'pages': [{'pageDisplayName': 'Your character', 'content': content}]}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    ini = ['; GENERATED by tools/silhouette_gen.py. The defaults are the most average preset.', '[Player]']
    ini += [f'i{g.capitalize()}={default_index[g]}' for g in ('female', 'male') if picker[g]]
    (folder / 'settings.ini').write_text('\n'.join(ini) + '\n', encoding='utf-8')


def write_papyrus(path, picker):
    """Silhouette:Player -- the functions the MCM buttons call. The preset values
    are generated into it because Papyrus cannot read the preset files; the same
    morph_values() made the BodyGen templates, so a preset means one thing in both."""
    L = [
        'Scriptname Silhouette:Player Hidden',
        '{GENERATED by tools/silhouette_gen.py from your BodySlide presets. Do not edit:',
        ' run the generator again after adding presets or rebuilding a body.',
        ' Called by the MCM menu. Needs LooksMenu (BodyGen) and MCM.}',
        '',
        '; Every argument is passed explicitly: the decompiled base sources carry no defaults.',
        '',
        'Bool Function IsFemale(Actor akActor) Global',
        '    Return akActor.GetLeveledActorBase().GetSex() == 1',
        'EndFunction',
        '',
        'Function ApplyChosen() Global',
        '    Actor player = Game.GetPlayer()',
        '    Bool female = IsFemale(player)',
        '    Int index = 0',
        '    If female',
        f'        index = MCM.GetModSettingInt("{MOD}", "iFemale:Player")',
        '    Else',
        f'        index = MCM.GetModSettingInt("{MOD}", "iMale:Player")',
        '    EndIf',
        '    BodyGen.RemoveAllMorphs(player, female)',
        '    String name = ""',
        '    If female',
        '        name = ApplyFemale(player, index)',
        '    Else',
        '        name = ApplyMale(player, index)',
        '    EndIf',
        '    BodyGen.UpdateMorphs(player)',
        '    If name == ""',
        '        Debug.MessageBox("Silhouette: that choice is not in this build of the menu. Run the generator again.")',
        '    Else',
        '        Debug.MessageBox("Your body is now " + name + ".")',
        '    EndIf',
        'EndFunction',
        '',
        '; Back to what BodyGen gives a character with no sliders: the most average',
        '; preset, from the Fallout4.esm|7 lines in Silhouette_morphs.ini.',
        'Function ApplyDefault() Global',
        '    Actor player = Game.GetPlayer()',
        '    BodyGen.RegenerateMorphs(player, True)',
        '    ShowCurrent()',
        'EndFunction',
        '',
        'Function ShowCurrent() Global',
        '    Actor player = Game.GetPlayer()',
        '    Bool female = IsFemale(player)',
        '    String[] morphs = BodyGen.GetMorphs(player, female)',
        '    String[] markers',
        '    String[] names',
        '    If female',
        '        markers = FemaleMarkers()',
        '        names = FemaleNames()',
        '    Else',
        '        markers = MaleMarkers()',
        '        names = MaleNames()',
        '    EndIf',
        '    Int count = 0',
        '    If morphs',
        '        count = morphs.Length',
        '    EndIf',
        '    Int i = 0',
        '    While i < count',
        '        Int k = markers.Find(morphs[i], 0)',
        '        If k >= 0',
        '            Debug.MessageBox("Your body: " + names[k] + ".")',
        '            Return',
        '        EndIf',
        '        i += 1',
        '    EndWhile',
        '    If count == 0',
        '        Debug.MessageBox("Your character has no body sliders: the bare body you built in BodySlide.")',
        '    Else',
        '        Debug.MessageBox("Your body was not set by Silhouette: it has " + count + " LooksMenu body sliders of its own.")',
        '    EndIf',
        'EndFunction',
    ]
    for g, cap, female in (('female', 'Female', 'True'), ('male', 'Male', 'False')):
        entries = picker[g]
        for kind, key in (('Markers', 'marker'), ('Names', 'display')):
            L += ['', f'String[] Function {cap}{kind}() Global', '    String[] a = new String[0]']
            L += [f'    a.Add({papyrus_string(e[key])}, 1)' for e in entries]
            L += ['    Return a', 'EndFunction']
        L += ['', f'; Returns the preset name, or "" for an index this build does not have.',
              f'String Function Apply{cap}(Actor a, Int index) Global']
        for i, e in enumerate(entries):
            L.append(f'    {"If" if i == 0 else "ElseIf"} index == {i}')
            for morph, v in e['values']:
                L.append(f'        BodyGen.SetMorph(a, {female}, {papyrus_string(morph)}, None, {fmt(v)})')
            L.append(f'        Return {papyrus_string(e["display"])}')
        if entries:
            L.append('    EndIf')
        L += ['    Return ""', 'EndFunction']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(L) + '\n', encoding='utf-8')


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--data', type=pathlib.Path, default=DEFAULT_DATA)
    ap.add_argument('--built', type=pathlib.Path, action='append', default=None,
                    help='a folder BodySlide built into (repeatable), searched before Data for '
                         'the body meshes -- to check a rebuild before it is deployed')
    ap.add_argument('--write', action='store_true',
                    help='write the BodyGen files, the MCM menu and the picker script')
    ap.add_argument('--out', type=pathlib.Path, default=None,
                    help='the mod folder to write into (default: this repo\'s data/)')
    ap.add_argument('--psc', type=pathlib.Path, default=ROOT / 'papyrus/Silhouette/Player.psc',
                    help='where the generated picker script source goes')
    ap.add_argument('--no-partial', action='store_true',
                    help='random pool uses full fits only (owner default: include partial)')
    ap.add_argument('--compensate', action='store_true',
                    help='write templates relative to what the base has baked in, for a base '
                         'that is NOT zeroed (default: absolute, for a zeroed base - S-5)')
    ap.add_argument('--report', type=pathlib.Path, default=None, help='also write a JSON report')
    args = ap.parse_args()

    roots = built_roots(args)
    tris = {}
    for g, b in BODIES.items():
        tri = base_body.locate(roots, f'Meshes/Actors/Character/CharacterAssets/{b}.tri')
        if tri is None:
            raise SystemExit(f'no {b}.tri in {", ".join(map(str, roots))} -- build the body with '
                             f'"Build Morphs" ticked')
        print(f'{b}: {tri.parent}')
        tris[g] = base_body.read_tri(tri)
    morphs_of = {g: set().union(*t.values()) for g, t in tris.items()}
    presets = read_presets(args.data / 'Tools/BodySlide/SliderPresets')

    for p in presets:
        p.update(classify(p, morphs_of['female'], morphs_of['male']))
    family = {g: installed_family(presets, g) for g in BODIES}

    print(f'installed bodies: female {len(morphs_of["female"])} morphs, '
          f'male {len(morphs_of["male"])} morphs')
    print(f'installed family, read off the full-fit presets: '
          f'female={family["female"]!r} male={family["male"]!r}')
    print(f'presets read: {len(presets)}\n')

    # ---- what is baked into each base body
    base = {}
    print('base bodies, measured against BodySlide\'s reference meshes:')
    for g, body in BODIES.items():
        own = [p for p in presets if p['gender'] == g and p['kind'] != 'empty']
        base[g] = base_body.measure(args.data, body, own, roots)
        print(f'  {g:6} {describe(base[g])}')
    baked, unready = {}, []
    for g in BODIES:
        b = base[g]
        baked[g] = {}
        if b['status'] == 'zeroed':
            continue
        if args.compensate and b['baked'] is not None:
            baked[g] = b['baked']
            continue
        unready.append(g)
        zero = next((p['name'] for p in presets if p['gender'] == g and p['kind'] == 'body'
                     and b['set'] and not any(base_body.resolve(p, b['set']).values())), None)
        print(f'  !! {g}: {BODIES[g]} is NOT zeroed, and BodyGen adds every preset on top of it.')
        print(f'     Rebuild it in BodySlide BEFORE deploying: body "{b["set"]["name"] if b["set"] else "?"}", '
              f'preset "{zero or "a Zeroed Sliders preset"}", "Build Morphs" ticked -- and batch-build')
        print(f'     your outfits with the same preset. Then run this and verify_bodygen.py again.')
        if args.compensate:
            print(f'     (--compensate cannot help: the baked shape matches no preset on disk.)')
    print()

    # ---- the pools
    pools = {'female': [], 'male': []}
    buckets = collections.defaultdict(list)
    zeroed = []
    for p in presets:
        if p['kind'] == 'empty':
            buckets['empty'].append(p)
            continue
        if p['kind'] == 'clothed-variant':
            buckets['clothed-variant'].append(p)
            continue
        g = p['gender']
        b = band(p, family[g])
        p['band'] = b
        buckets[f'{g}-{b}'].append(p)
        if not (b == 'full' or (b == 'partial' and not args.no_partial)):
            continue
        target = {k: v for k, v in target_values(p, base[g]).items() if k in morphs_of[g]}
        if not any(target.values()):
            # A zeroed preset. OBody NG blacklists these from random distribution
            # by default ("Zeroed Sliders", "HIMBO Zero for OBody"); here that is
            # decided by the values, not the name, so "CBBE Zeroed Sliders" and
            # "BT - Zero" are caught too.
            zeroed.append(p)
            continue
        name = template_name(p)
        pools[g].append((name, template_line(name, target, baked[g], morphs_of[g], p['name']), p))

    order = ['female-full', 'female-partial', 'female-other-family', 'female-none',
             'male-full', 'male-partial', 'male-other-family', 'male-none',
             'clothed-variant', 'empty']
    for key in order:
        rows = buckets.get(key, [])
        if not rows:
            continue
        print(f'{key:20} {len(rows):3}')
        for p in rows[:5]:
            fams = ','.join(p.get('families', [])[:2]) or '-'
            print(f'    {100*p["fit"]:5.1f}%  {p["name"][:46]:46}  [{fams}]')
        if len(rows) > 5:
            print(f'    ... and {len(rows) - 5} more')

    if zeroed:
        print('\nleft out of random distribution as zeroed presets (OBody does the same): '
              + ', '.join(p['name'] for p in zeroed))
    small_only = sum(p['small_only'] for p in presets)
    if small_only:
        print(f'sliders with only a "small" value (a FO4 build uses the default): {small_only}')

    for g in BODIES:
        names = collections.Counter(n for n, _l, _p in pools[g])
        clash = [n for n, c in names.items() if c > 1]
        if clash:
            raise SystemExit(f'two presets reduce to the same template name: {clash}')
        print(f'\n{g} random pool: {len(pools[g])} template(s)')

    # ---- the player: never randomised; the most average body unless they pick
    # one in MCM (owner, 2026-09-23). The picker offers every preset that fits,
    # zeroed ones included -- OBody shows blacklisted presets in its menu too.
    picker, average, default_index = {}, {}, {}
    for g in BODIES:
        entries = []
        for p in presets:
            if p['gender'] != g or p['kind'] != 'body':
                continue
            if not (p['band'] == 'full' or (p['band'] == 'partial' and not args.no_partial)):
                continue
            target = {k: v for k, v in target_values(p, base[g]).items() if k in morphs_of[g]}
            name = template_name(p)
            entries.append({'display': p['name'], 'marker': name, 'band': p['band'], 'target': target,
                            'values': morph_values(name, target, baked[g], morphs_of[g], p['name'])})
        entries.sort(key=lambda e: e['display'].casefold())
        picker[g] = entries
        shape = max(tris[g], key=lambda s: len(tris[g][s]))
        pool_values = [(p['name'], {k: v for k, v in target_values(p, base[g]).items()
                                    if k in morphs_of[g]}) for _n, _l, p in pools[g]]
        full = [(n, v) for n, v in pool_values
                if next(p for p in presets if p['name'] == n)['band'] == 'full']
        best = base_body.most_average(pool_values, tris[g][shape], full)
        if best:
            average[g] = best[0]
            default_index[g] = next(i for i, e in enumerate(entries) if e['display'] == best[0])
            print(f'{g} player default, the most average full fit: {best[0]!r} '
                  f'({best[1]:.3f} rms from the pool\'s mean body)')

    if not args.write:
        print('\n(measure only - pass --write to produce the BodyGen files)')
    else:
        root = args.out or (ROOT / 'data')
        out = root / 'F4SE/Plugins/F4EE/BodyGen/Loose'
        out.mkdir(parents=True, exist_ok=True)
        tfile = out / 'Silhouette_templates.ini'
        mfile = out / 'Silhouette_morphs.ini'

        t = ['# Silhouette - generated by tools/silhouette_gen.py. Do not edit by hand:',
             '# regenerate after adding presets or rebuilding a body in BodySlide.',
             f'# {len(pools["female"])} female, {len(pools["male"])} male templates.',
             '#',
             '# Measured base bodies:']
        for g in BODIES:
            t.append(f'#   {g}: {describe(base[g])}')
        if any(baked[g] for g in BODIES):
            t += ['#',
                  '# --compensate: values are RELATIVE to that baked shape (target minus',
                  '# baked), so every NPC ends at exactly its preset. Rebuild a body with a',
                  '# different preset and these values are wrong until this tool is run again.']
        else:
            t += ['#',
                  '# Values are ABSOLUTE: written for bodies built with zeroed sliders.']
        for g in unready:
            t.append(f'# !! {BODIES[g]} is NOT zeroed yet: rebuild it zeroed before deploying.')
        t += ['#',
              '# The last morph of every template is a marker named after the template.',
              '# No body has it, so it moves nothing; it makes the roll permanent (an NPC',
              '# with no stored morphs is re-rolled on every load) and records the preset.',
              '']
        t.append(f'{PLAYER_GUARD}={PLAYER_GUARD}@0')
        t.append('')
        for g in BODIES:
            t.append(f'# --- {g} ---')
            for name, line, p in pools[g]:
                t.append(f'# {p["name"]}  {100*p["fit"]:.0f}% fit  families={p["families"]}')
                t.append(f'{name}={", ".join(line)}')
            t.append('')
        tfile.write_text('\n'.join(t) + '\n', encoding='ascii', errors='replace')

        # Order IS priority: LooksMenu lets a later line overwrite an earlier one.
        # The broad random pool goes first; rules and blacklists go below it.
        m = ['# Silhouette - generated. Later lines override earlier ones for the same NPC.',
             '# Always name a race: "All|Female" alone matches only NPCs that have none.', '']
        for g, label in (('female', 'Female'), ('male', 'Male')):
            if pools[g]:
                m.append(f'All|{label}|HumanRace=' + '|'.join(n for n, _l, _p in pools[g]))
        m += ['',
              '# The player (Fallout4.esm 0x7) is NEVER randomised: without these lines',
              '# the All lines above would include them. A character with no body sliders',
              '# gets the most average of your presets; MCM > Silhouette picks another.',
              '# LooksMenu itself skips a character that already has body sliders.']
        for g, label in (('female', 'Female'), ('male', 'Male')):
            chosen = template_name({'name': average[g]}) if g in average else PLAYER_GUARD
            m.append(f'Fallout4.esm|7|{label}={chosen}')
        mfile.write_text('\n'.join(m) + '\n', encoding='ascii', errors='replace')
        print(f'\nwrote {tfile}\nwrote {mfile}')

        write_mcm(root / 'MCM/Config' / MOD, picker, default_index, average)
        write_papyrus(args.psc, picker)
        print(f'wrote {root / "MCM/Config" / MOD}\\config.json + settings.ini')
        print(f'wrote {args.psc}  (compile: scripts/build-papyrus.ps1)')

    if args.report:
        args.report.write_text(json.dumps({
            'base': {g: {k: (v['name'] if k == 'set' and v else v)
                         for k, v in base[g].items() if k != 'baked'} for g in BODIES},
            'presets': [{k: p.get(k) for k in
                         ('name', 'set', 'families', 'file', 'gender', 'fit', 'kind', 'band')}
                        for p in presets],
        }, indent=2), encoding='utf-8')
        print(f'wrote {args.report}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
