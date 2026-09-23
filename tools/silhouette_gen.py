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
import hashlib
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

import base_body
import rules

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

PLAYER_GUARD = rules.UNSHAPED


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


def template_text(name, values, stamp):
    """A template's right-hand side: the morphs LooksMenu must add to the base body
    to reach the preset, then the marker. `values` comes from morph_values().

    Only morphs the body has (others move nothing and only bloat the co-save) and
    only non-zero differences. The marker's VALUE is the generation stamp: LooksMenu
    stores any non-zero value and moves no vertex for a name no .tri has, so the
    value is free to say which generation of the files rolled this NPC -- the
    manifest of that generation names the exact preset and its values (S-12).
    """
    return [f'{m}@{fmt(v)}' for m, v in values] + [f'{name}@{stamp}']


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
    """[(morph, value)] LooksMenu must add to the base body to reach `target`,
    without the marker. Shared by the BodyGen templates and the player picker so
    the two can never disagree about what a preset is. A morph whose NAME holds a
    BodyGen separator (= / , | @) would be cut in two by LooksMenu's parser and is
    skipped with a warning; spaces are fine ("7B Lower" is a real master slider)."""
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
    return out


# --------------------------------------------------------------------------
# the player picker: an MCM menu and the script it calls
# --------------------------------------------------------------------------

MOD = 'Silhouette'
SCRIPT = 'Silhouette:Player'


def papyrus_string(s):
    return '"' + s.replace('\\', '/').replace('"', "'") + '"'


def list_hash(entries):
    """8 hex digits naming one exact option list. It goes into the MCM setting id,
    so a choice saved against a different list is never read as an index into
    this one (MCM keeps changed values in Data/MCM/Settings/<mod>.ini forever)."""
    text = '\n'.join(f'{e["marker"]}|{e["display"]}' for e in entries)
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:8]


def setting_id(g, entries):
    return f'i{g.capitalize()}_{list_hash(entries)}'


def write_mcm(folder, picker, default_index, average, build):
    """MCM/Config/Silhouette: a dropdown per sex and buttons that call global
    functions of Silhouette:Player -- so no plugin is needed. The dropdown shape
    (ModSettingInt + options) and CallGlobalFunction buttons are the ones already
    working in this install (CommonwealthEncounterDirector, Rapport)."""
    def button(text, help_, function):
        return {'type': 'button', 'text': text, 'help': help_,
                'action': {'type': 'CallGlobalFunction', 'script': SCRIPT, 'function': function,
                           'params': []}}

    content = [
        {'type': 'text', 'text': 'Every NPC gets one of your BodySlide presets the first time you '
                                 'meet them, and keeps it. Your own character gets the most average '
                                 'of them unless you choose one here.'},
        {'type': 'section', 'text': 'Your character'},
    ]
    for g, label in (('female', 'If your character is female'), ('male', 'If your character is male')):
        if not picker[g]:
            continue
        content.append({
            'type': 'dropdown', 'id': f'{setting_id(g, picker[g])}:Player', 'text': label,
            'help': f'{len(picker[g])} presets that fit your {g} body. Nothing changes until you '
                    f'press "Apply to my character".',
            'valueOptions': {'sourceType': 'ModSettingInt',
                             'options': [e['display'] for e in picker[g]]},
        })
    avg = ' / '.join(average[g] for g in ('female', 'male') if average.get(g))
    content += [
        button('Apply to my character',
               'Gives your character the preset chosen above for their sex. It replaces the body '
               'sliders LooksMenu and BodyGen set, including ones you set in LooksMenu yourself; '
               'body morphs other mods add are left alone. Close the menu to see it.',
               'ApplyChosen'),
        button('Back to the default', f'The most average body of your presets: {avg}.', 'ApplyDefault'),
        button('Which body do I have?', 'Names the preset Silhouette last gave your character.',
               'ShowCurrent'),
        {'type': 'section', 'text': 'Everyone else'},
        button('Count the bodies around me',
               'How many people nearby have a Silhouette body, and in how many different presets. '
               'Each one, with its preset, is written to the Papyrus log.', 'Census'),
        button('Refresh the people around me',
               'Everyone nearby keeps their preset but gets its values from this build again -- for '
               'after you edited a preset or rebuilt your bodies. Body morphs other mods add are '
               'left alone.', 'Refresh'),
        button('Give the people around me new bodies',
               'Everyone nearby (never your character) rolls a new body, as if met for the first '
               'time. This clears ALL their body sliders, other mods\' included, and cannot be undone.',
               'Reroll'),
    ]
    config = {'modName': MOD, 'displayName': MOD, 'minMcmVersion': 1,
              'pages': [{'pageDisplayName': 'Bodies', 'content': content}]}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    ini = ['; GENERATED by tools/silhouette_gen.py. The defaults are the most average preset.',
           '[Player]', f'sBuild={build}']
    ini += [f'{setting_id(g, picker[g])}={default_index.get(g, 0)}' for g in ('female', 'male')
            if picker[g]]
    (folder / 'settings.ini').write_text('\n'.join(ini) + '\n', encoding='utf-8')


# FO4 caps a script-built array at 128 elements.
ARRAY_LIMIT = 128


def write_papyrus(path, picker, default_index, stamp, build):
    """Silhouette:Player -- the functions the MCM buttons call. The preset values
    are generated into it because Papyrus cannot read the preset files; the same
    morph_values() made the BodyGen templates, so a preset means one thing in both.

    Only the unkeyed morph layer is ever cleared (RemoveMorphsByKeyword with None:
    the key BodyGen, LooksMenu's own sliders and Silhouette all write), so body
    morphs another mod keeps under its own keyword survive. The one exception is
    Reroll, which has to go through RegenerateMorphs and says so in its help.
    """
    for g in ('female', 'male'):
        if len(picker[g]) > ARRAY_LIMIT:
            raise SystemExit(f'{len(picker[g])} {g} presets: the picker holds at most {ARRAY_LIMIT} '
                             f'(a Papyrus array limit). Hold some back with '
                             f'blacklistedPresetsShowInOBodyMenu=false.')
    ids = {g: setting_id(g, picker[g]) for g in ('female', 'male')}
    L = [
        'Scriptname Silhouette:Player Hidden',
        '{GENERATED by tools/silhouette_gen.py from your BodySlide presets. Do not edit:',
        ' run the generator again after adding presets or rebuilding a body.',
        ' Called by the MCM menu. Needs LooksMenu (BodyGen) and MCM.}',
        '',
        '; Every argument is passed explicitly: the decompiled base sources carry no defaults.',
        f'; Build {build}; marker stamp {stamp}.',
        '',
        f'String Function Build() Global',
        f'    Return "{build}"',
        'EndFunction',
        '',
        f'Float Function Stamp() Global',
        f'    Return {stamp}.0',
        'EndFunction',
        '',
        'Bool Function IsFemale(Actor akActor) Global',
        '    Return akActor.GetLeveledActorBase().GetSex() == 1',
        'EndFunction',
        '',
        'Int Function Count(Bool female) Global',
        '    If female',
        f'        Return {len(picker["female"])}',
        '    EndIf',
        f'    Return {len(picker["male"])}',
        'EndFunction',
        '',
        '; Clears the unkeyed layer only, applies preset `index`, reshapes the 3D.',
        '; Returns the preset name, or "" for an index this build does not have.',
        'String Function Give(Actor akActor, Bool female, Int index) Global',
        '    If index < 0 || index >= Count(female)',
        '        Return ""',
        '    EndIf',
        '    BodyGen.RemoveMorphsByKeyword(akActor, female, None)',
        '    String name = ""',
        '    If female',
        '        name = ApplyFemale(akActor, index)',
        '    Else',
        '        name = ApplyMale(akActor, index)',
        '    EndIf',
        '    BodyGen.UpdateMorphs(akActor)',
        '    Return name',
        'EndFunction',
        '',
        'Function ApplyChosen() Global',
        '    If !MCM.IsInstalled()',
        '        Debug.MessageBox("Silhouette: MCM\'s script is missing, so the choice cannot be read. Install F4SE Menu Framework or MCM.")',
        '        Return',
        '    EndIf',
        f'    String menu = MCM.GetModSettingString("{MOD}", "sBuild:Player")',
        '    If menu != "" && menu != Build()',
        '        Debug.MessageBox("Silhouette: the menu and the script come from different builds. Install the generated files together, then choose again.")',
        '        Return',
        '    EndIf',
        '    Actor player = Game.GetPlayer()',
        '    Bool female = IsFemale(player)',
        '    Int index = -1',
        '    If female',
        f'        index = MCM.GetModSettingInt("{MOD}", "{ids["female"]}:Player")',
        '    Else',
        f'        index = MCM.GetModSettingInt("{MOD}", "{ids["male"]}:Player")',
        '    EndIf',
        '    If index < 0 || index >= Count(female)',
        '        Debug.MessageBox("Silhouette: that choice is not in this build of the menu. Nothing was changed.")',
        '        Return',
        '    EndIf',
        '    Debug.MessageBox("Your body is now " + Give(player, female, index) + ".")',
        'EndFunction',
        '',
        '; The most average preset -- the same one the Fallout4.esm|7 lines in',
        '; Silhouette_morphs.ini give a character with no body sliders.',
        'Function ApplyDefault() Global',
        '    Actor player = Game.GetPlayer()',
        '    Bool female = IsFemale(player)',
        '    Int index = ' + str(default_index.get('male', 0)),
        '    If female',
        '        index = ' + str(default_index.get('female', 0)),
        '    EndIf',
        '    Debug.MessageBox("Your body is now " + Give(player, female, index) + ".")',
        'EndFunction',
        '',
        '; The preset Silhouette last gave an actor, read back from its marker: the name,',
        '; "" when it holds no body sliders at all, or "*" when it holds sliders that',
        '; Silhouette did not set. A marker counts only while it holds a value: removing',
        '; a keyword empties a morph but leaves its name listed until the next load.',
        'String Function PresetOf(Actor akActor, Bool female, String[] markers, String[] names) Global',
        '    String[] morphs = BodyGen.GetMorphs(akActor, female)',
        '    Int count = 0',
        '    If morphs',
        '        count = morphs.Length',
        '    EndIf',
        '    If count == 0',
        '        Return ""',
        '    EndIf',
        '    Int i = 0',
        '    While i < count',
        '        Int k = markers.Find(morphs[i], 0)',
        '        If k >= 0 && BodyGen.GetMorph(akActor, female, morphs[i], None) > 0.0',
        '            Return names[k]',
        '        EndIf',
        '        i += 1',
        '    EndWhile',
        '    Return "*"',
        'EndFunction',
        '',
        'Function ShowCurrent() Global',
        '    Actor player = Game.GetPlayer()',
        '    Bool female = IsFemale(player)',
        '    String preset = ""',
        '    If female',
        '        preset = PresetOf(player, True, FemaleMarkers(), FemaleNames())',
        '    Else',
        '        preset = PresetOf(player, False, MaleMarkers(), MaleNames())',
        '    EndIf',
        '    If preset == ""',
        '        Debug.MessageBox("Your character has no body sliders: the bare body you built in BodySlide.")',
        '    ElseIf preset == "*"',
        '        Debug.MessageBox("Your body was not set by Silhouette: it holds LooksMenu body sliders of its own.")',
        '    Else',
        '        Debug.MessageBox("Silhouette last gave you: " + preset + ".")',
        '    EndIf',
        'EndFunction',
        '',
        '; Everyone nearby, never the player.',
        'Actor[] Function Nearby() Global',
        '    Actor player = Game.GetPlayer()',
        '    Keyword npc = Game.GetFormFromFile(0x13794, "Fallout4.esm") as Keyword  ; ActorTypeNPC',
        '    ObjectReference[] found = player.FindAllReferencesWithKeyword(npc, 4096.0)',
        '    Actor[] out = new Actor[0]',
        '    Int count = 0',
        '    If found',
        '        count = found.Length',
        '    EndIf',
        '    Int i = 0',
        '    While i < count',
        '        Actor a = found[i] as Actor',
        '        If a && a != player && out.Length < 128',
        '            out.Add(a, 1)',
        '        EndIf',
        '        i += 1',
        '    EndWhile',
        '    Return out',
        'EndFunction',
        '',
        '; Who around the player has which body: a summary in a message box, and one',
        '; line per actor in the Papyrus log ("Silhouette census: <ref form id, decimal>',
        '; <F|M> <preset>"). From the console: cgf "Silhouette:Player.Census"',
        'Function Census() Global',
        '    Actor[] people = Nearby()',
        '    String[] fm = FemaleMarkers()',
        '    String[] fn = FemaleNames()',
        '    String[] mm = MaleMarkers()',
        '    String[] mn = MaleNames()',
        '    Int shaped = 0',
        '    Int own = 0',
        '    String[] distinct = new String[0]',
        '    Int i = 0',
        '    While i < people.Length',
        '        Actor a = people[i]',
        '        Bool female = IsFemale(a)',
        '        String preset = ""',
        '        String sex = "M"',
        '        If female',
        '            preset = PresetOf(a, True, fm, fn)',
        '            sex = "F"',
        '        Else',
        '            preset = PresetOf(a, False, mm, mn)',
        '        EndIf',
        '        Debug.Trace("Silhouette census: " + a.GetFormID() + " " + sex + " " + preset, 0)',
        '        If preset == "*"',
        '            own += 1',
        '        ElseIf preset != ""',
        '            shaped += 1',
        '            If distinct.Find(preset, 0) < 0 && distinct.Length < 128',
        '                distinct.Add(preset, 1)',
        '            EndIf',
        '        EndIf',
        '        i += 1',
        '    EndWhile',
        '    Debug.MessageBox("Silhouette: " + people.Length + " people around you. " + shaped + " have a Silhouette body, in " + distinct.Length + " different presets. " + own + " hold body sliders of their own. The rest have none: not a race Silhouette shapes, blacklisted, or not generated yet.")',
        'EndFunction',
        '',
        '; Everyone nearby keeps the preset Silhouette gave them, with its values from this build.',
        'Function Refresh() Global',
        '    Actor[] people = Nearby()',
        '    String[] fm = FemaleMarkers()',
        '    String[] fn = FemaleNames()',
        '    String[] mm = MaleMarkers()',
        '    String[] mn = MaleNames()',
        '    Int done = 0',
        '    Int i = 0',
        '    While i < people.Length',
        '        Actor a = people[i]',
        '        Bool female = IsFemale(a)',
        '        String preset = ""',
        '        Int index = -1',
        '        If female',
        '            preset = PresetOf(a, True, fm, fn)',
        '            index = fn.Find(preset, 0)',
        '        Else',
        '            preset = PresetOf(a, False, mm, mn)',
        '            index = mn.Find(preset, 0)',
        '        EndIf',
        '        If index >= 0 && Give(a, female, index) != ""',
        '            done += 1',
        '        EndIf',
        '        i += 1',
        '    EndWhile',
        '    Debug.MessageBox("Silhouette: " + done + " of " + people.Length + " people around you refreshed. The rest have no Silhouette body, or one this build no longer has.")',
        'EndFunction',
        '',
        '; Everyone nearby rolls again, as if met for the first time. RegenerateMorphs is',
        '; the only way to run BodyGen for an actor again, and it clears every key.',
        'Function Reroll() Global',
        '    Actor[] people = Nearby()',
        '    Int i = 0',
        '    While i < people.Length',
        '        BodyGen.RegenerateMorphs(people[i], True)',
        '        i += 1',
        '    EndWhile',
        '    Debug.MessageBox("Silhouette: " + people.Length + " people around you rolled a new body.")',
        'EndFunction',
    ]
    for g, cap, female in (('female', 'Female', 'True'), ('male', 'Male', 'False')):
        entries = picker[g]
        for kind, key in (('Markers', 'marker'), ('Names', 'display')):
            L += ['', f'String[] Function {cap}{kind}() Global', '    String[] a = new String[0]']
            L += [f'    a.Add({papyrus_string(e[key])}, 1)' for e in entries]
            L += ['    Return a', 'EndFunction']
        L += ['', '; Sets the values only; Give() clears the layer first and reshapes after.',
              f'String Function Apply{cap}(Actor a, Int index) Global']
        for i, e in enumerate(entries):
            L.append(f'    {"If" if i == 0 else "ElseIf"} index == {i}')
            for morph, v in e['values']:
                L.append(f'        BodyGen.SetMorph(a, {female}, {papyrus_string(morph)}, None, {fmt(v)})')
            L.append(f'        BodyGen.SetMorph(a, {female}, {papyrus_string(e["marker"])}, None, {stamp}.0)')
            L.append(f'        Return {papyrus_string(e["display"])}')
        if entries:
            L.append('    EndIf')
        L += ['    Return ""', 'EndFunction']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(L) + '\n', encoding='utf-8')


def write_manifest(folder, stamp, build, mode, base, pools, extra, picker, player):
    """F4SE/Plugins/Silhouette/manifests/<stamp>.json: what every marker of this
    generation means -- the exact preset name (the marker only keeps a sanitised
    one), its file, and the values written. Never deleted: an NPC rolled by this
    generation carries this stamp for the rest of that save."""
    templates = {}
    for g in ('female', 'male'):
        for name, values, p in pools[g]:
            templates[name] = {'preset': p['name'], 'gender': g, 'file': p['file'], 'values': dict(values)}
    for name, (values, p) in extra.items():
        templates[name] = {'preset': p['name'], 'gender': p['gender'], 'file': p['file'],
                           'values': dict(values)}
    for g in ('female', 'male'):
        for e in picker[g]:
            templates.setdefault(e['marker'], {'preset': e['display'], 'gender': g,
                                               'values': dict(e['values'])})
    doc = {'format': MANIFEST_FORMAT, 'stamp': stamp, 'build': build, 'mode': mode,
           'bases': {g: describe(base[g]) for g in ('female', 'male')},
           'player': player, 'templates': templates}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{stamp}.json').write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n',
                                           encoding='utf-8')


MANIFEST_FORMAT = 1


def generation(mode, pools, extra, picker):
    """(stamp, build). The build is a hash of everything the files say -- mode and
    every template's values; the stamp is its first 24 bits as an integer, exact
    in the float32 LooksMenu stores (every integer below 2^24 is)."""
    parts = {'format': MANIFEST_FORMAT, 'mode': mode, 't': {}}
    for g in ('female', 'male'):
        for name, values, _p in pools[g]:
            parts['t'][name] = values
        for e in picker[g]:
            parts['t'].setdefault(e['marker'], e['values'])
    for name, (values, _p) in extra.items():
        parts['t'][name] = values
    text = json.dumps(parts, sort_keys=True, default=lambda v: round(v, 6))
    build = hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]
    stamp = int(build[:6], 16) or 1
    return stamp, build


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
    ap.add_argument('--config', type=pathlib.Path, default=None,
                    help='the rules file (default: data/F4SE/Plugins/Silhouette/'
                         'Silhouette_presetDistributionConfig.json; includes/ beside it)')
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

    # ---- the rules (OBody's config keys; tools/rules.py)
    report = []
    cfg_file = args.config or (ROOT / 'data/F4SE/Plugins/Silhouette' / rules.CONFIG_NAME)
    cfg = rules.load(cfg_file, [cfg_file.parent / 'includes',
                                args.data / 'F4SE/Plugins/Silhouette/includes'], report)
    not_random = {n.casefold() for n in cfg.get('blacklistedPresetsFromRandomDistribution', [])}

    # ---- the pools
    pools = {'female': [], 'male': []}
    buckets = collections.defaultdict(list)
    zeroed, held_back = [], []
    for p in presets:
        if p['kind'] != 'empty':
            p['band'] = band(p, family[p['gender']])
    for p in presets:
        if p['kind'] == 'empty':
            buckets['empty'].append(p)
            continue
        if p['kind'] == 'clothed-variant':
            buckets['clothed-variant'].append(p)
            continue
        g = p['gender']
        b = p['band']
        buckets[f'{g}-{b}'].append(p)
        if not (b == 'full' or (b == 'partial' and not args.no_partial)):
            continue
        if p['name'].casefold() in not_random:
            held_back.append(p)
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
        pools[g].append((name, morph_values(name, target, baked[g], morphs_of[g], p['name']), p))

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

    if held_back:
        print('held back from random distribution by the config: ' + ', '.join(p['name'] for p in held_back))

    for g in BODIES:
        print(f'\n{g} random pool: {len(pools[g])} template(s)')

    # ---- rule lines, and templates for presets only the rules name
    by_name = {p['name'].casefold(): p for p in presets if p['kind'] != 'empty'}
    extra = {}                                       # template name -> (values, preset)

    def resolve_presets(names, gender):
        out = {'female': [], 'male': []}
        for n in names if isinstance(names, list) else [names]:
            p = by_name.get(str(n).casefold())
            if p is None:
                report.append(f'rules: no preset named {n!r}, skipped')
                continue
            g = p['gender']
            if gender and g != gender:
                report.append(f'rules: {p["name"]!r} is a {g} preset, not usable for {gender} NPCs')
                continue
            if p['band'] not in ('full', 'partial'):
                report.append(f'rules: {p["name"]!r} does not fit the installed {g} body '
                              f'({p["band"]}), skipped')
                continue
            name = template_name(p)
            if not any(name == n2 for n2, _l, _p in pools[g]) and name not in extra:
                target = {k: v for k, v in target_values(p, base[g]).items() if k in morphs_of[g]}
                extra[name] = (morph_values(name, target, baked[g], morphs_of[g], p['name']), p)
            out[g].append(name)
        return out

    rule_lines, _needed = rules.compile_lines(cfg, resolve_presets, args.data, report)
    distribute = cfg.get('distributeRaces') or ['HumanRace']
    print(f'\nrules: {len(rule_lines)} line(s), {len(extra)} extra template(s); random distribution '
          f'races: {", ".join(distribute)}')
    for r in report:
        print(f'  {r}')

    # LooksMenu looks template names up case-insensitively (F4EEFixedString ==
    # is _stricmp), so two names that differ only in case are one template.
    seen = collections.defaultdict(set)
    for n in [PLAYER_GUARD] + [n for g in BODIES for n, _v, _p in pools[g]] + list(extra):
        seen[n.casefold()].add(n)
    for g in BODIES:
        names = collections.Counter(n.casefold() for n, _v, _p in pools[g])
        seen.update({k: seen[k] | {f'{k} (twice in the {g} pool)'} for k, c in names.items() if c > 1})
    clash = sorted(v for v in seen.values() if len(v) > 1)
    if clash:
        raise SystemExit(f'template names that LooksMenu would read as one: {clash}')

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
            if p['name'].casefold() in not_random and not cfg.get('blacklistedPresetsShowInOBodyMenu', True):
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
        else:
            print(f'{g}: no full-fit preset to be the player default -- the player keeps the base body')

    mode = 'compensated' if any(baked[g] for g in BODIES) else 'absolute'
    stamp, build = generation(mode, pools, extra, picker)
    print(f'\nbuild {build}, marker stamp {stamp} ({mode})')

    if not args.write:
        print('\n(measure only - pass --write to produce the BodyGen files)')
    else:
        root = args.out or (ROOT / 'data')
        out = root / 'F4SE/Plugins/F4EE/BodyGen/Loose'
        out.mkdir(parents=True, exist_ok=True)
        tfile = out / 'Silhouette_templates.ini'
        mfile = out / 'Silhouette_morphs.ini'

        # NO EMPTY LINES, and CRLF. LooksMenu reads each line with the engine's own
        # BSResourceTextFile::ReadLine, which returns the number of bytes before the
        # '\n'; its loop stops on 0. With LF, the first empty line ENDS THE FILE.
        # (With CRLF an "empty" line is '\r' and survives, which is the only reason
        # it ever worked.) Spacing is done with '#'.
        t = ['# Silhouette - generated by tools/silhouette_gen.py. Do not edit by hand:',
             '# regenerate after adding presets or rebuilding a body in BodySlide.',
             f'# {len(pools["female"])} female, {len(pools["male"])} male templates. '
             f'Build {build}, marker stamp {stamp} ({mode}).',
             '#',
             '# Measured base bodies:']
        for g in BODIES:
            t.append(f'#   {g}: {describe(base[g])}')
        if mode == 'compensated':
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
              '# The last morph of every template is a marker named after the template. No',
              '# body has it, so it moves nothing; it makes the roll permanent (an NPC with',
              '# no stored morphs is re-rolled on every load). Its VALUE is this build\'s',
              f'# stamp: F4SE/Plugins/Silhouette/manifests/{stamp}.json says what it means.',
              '#',
              f'{PLAYER_GUARD}={PLAYER_GUARD}@0',
              '#']
        for g in BODIES:
            t.append(f'# --- {g} ---')
            for name, values, p in pools[g]:
                t.append(f'# {p["name"]}  {100*p["fit"]:.0f}% fit  families={p["families"]}')
                t.append(f'{name}={", ".join(template_text(name, values, stamp))}')
            t.append('#')
        if extra:
            t.append('# --- presets only the rules hand out ---')
            for name, (values, p) in sorted(extra.items()):
                t.append(f'# {p["name"]}  {p["gender"]}  {100*p["fit"]:.0f}% fit')
                t.append(f'{name}={", ".join(template_text(name, values, stamp))}')
        assert all(line.strip() for line in t), 'an empty line would end the file for LooksMenu'
        tfile.write_text('\n'.join(t) + '\n', encoding='ascii', errors='replace', newline='\r\n')

        # Order IS priority: LooksMenu lets a later line overwrite an earlier one.
        # The broad random pool goes first; rules and blacklists go below it, in
        # the reverse of OBody's priority (tools/rules.py).
        m = ['# Silhouette - generated. Later lines override earlier ones for the same NPC.',
             '# Always name a race: "All|Female" alone matches only NPCs that have none.',
             '#']
        for g, label in (('female', 'Female'), ('male', 'Male')):
            if pools[g]:
                for race in distribute:
                    m.append(f'All|{label}|{race}=' + '|'.join(n for n, _v, _p in pools[g]))
        if rule_lines:
            m += ['#', '# Rules from Silhouette_presetDistributionConfig.json and includes,',
                  '# lowest priority first: race, plugin, blacklists, FormID, FormID blacklists.']
            m += rule_lines
        chosen = {g: (template_name({'name': average[g]}) if g in average else PLAYER_GUARD)
                  for g in BODIES}
        m += ['#',
              '# The player (Fallout4.esm 0x7) is NEVER randomised: without these lines',
              '# the All lines above would include them. A character with no body sliders',
              '# gets the most average of your presets; MCM > Silhouette picks another.',
              '# LooksMenu itself skips a character that already has body sliders.',
              f'Fallout4.esm|7|Female={chosen["female"]}',
              f'Fallout4.esm|7|Male={chosen["male"]}',
              '#',
              '# ...and neither are the two character-creation dummies. A new game shows',
              '# MQ101PlayerSpouseMale (A7D34) and MQ101PlayerSpouseFemale (A7D35) at the',
              '# mirror; on confirm, LooksMenu CLONES the chosen one\'s body morphs onto the',
              '# player (CloneBodyMorphs -> CloneMorphs), past the player line above. Both',
              '# are HumanRace with no template, so the All lines would roll them. They get',
              '# the player\'s default, and the spouse in the intro wears it too.',
              f'Fallout4.esm|0A7D35|Female={chosen["female"]}',
              f'Fallout4.esm|0A7D34|Male={chosen["male"]}']
        assert all(line.strip() for line in m), 'an empty line would end the file for LooksMenu'
        mfile.write_text('\n'.join(m) + '\n', encoding='ascii', errors='replace', newline='\r\n')
        print(f'\nwrote {tfile}\nwrote {mfile}')

        cfg_file = root / 'F4SE/Plugins/Silhouette' / rules.CONFIG_NAME
        if not cfg_file.exists():
            rules.write_default(cfg_file)
            print(f'wrote {cfg_file} (every OBody key, empty)')
        write_mcm(root / 'MCM/Config' / MOD, picker, default_index, average, build)
        write_papyrus(args.psc, picker, default_index, stamp, build)
        write_manifest(root / 'F4SE/Plugins/Silhouette/manifests', stamp, build, mode, base, pools,
                       extra, picker, chosen)
        print(f'wrote {root / "MCM/Config" / MOD}\\config.json + settings.ini')
        print(f'wrote {root / "F4SE/Plugins/Silhouette/manifests"}\\{stamp}.json')
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
