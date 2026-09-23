"""F4SE/Plugins/Silhouette/catalog.json: what Silhouette.dll needs to know (decision S-19).

The generator stays the compiler. It has already measured which presets fit, what
each one writes, what is a runtime state (S-16) or the shaft (S-29) and what BodyGen
rolls per NPC (S-17, S-21); the plugin re-derives none of it and refuses a catalog
that disagrees with the BodyGen files beside it (their headers carry the same build,
stamp and rules hash).

The schema is the plugin's parser (src/Catalog.cpp), key for key; a catalog it cannot
read whole is refused whole, so check() below refuses the same things first, and the
build scripts run the parser itself on the written files (SilhouetteTests.exe --check).
"""
import hashlib
import json
import math
import os
import pathlib
import string

import plugin_forms
import rules

SCHEMA = 1
MARKER_PREFIX = 'Silhouette_'
BLACKLIST_MARKER = 'Silhouette_Blacklisted'   # S-23: stored unkeyed, moves nothing, keeps BodyGen away
REFIT_MARKER = 'Silhouette_Refit'             # S-40: under the refit keyword, names the set that is on
CHOICE_MARKER = 'Silhouette_Chosen'           # S-51: unkeyed, beside a picked or API-given body
RESERVED_MARKERS = (BLACKLIST_MARKER, REFIT_MARKER, CHOICE_MARKER)
CLOTHED_SLOTS = [33, 36, 41]                  # BODY, [U] Torso, [A] Torso (S-20)
FLOAT32_MAX = 3.4028234663852886e38

# The built-in clothed shape for a CBBE body (S-40, S-48): FLOORS under Silhouette's refit keyword.
# While she is dressed she has at least these; every other slider is her own body, so the clothed shape
# follows her body wherever it goes. NipBGone only under heavy clothes.
BUILTIN_FEMALE = [
    ('BreastsTogether', 0.3, False),
    ('PushUp', 0.2, False),
    ('NipBGone', 1.0, True),
]

# std::tolower in the "C" locale, as the plugin compares names: ASCII letters only.
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def ifold(s):
    return str(s).translate(_ASCII_LOWER)


def is_refit(name):
    """A BodySlide preset that is a clothed shape, not a body: OBody's naming."""
    n = name.casefold()
    return n.endswith('-refit') or n in ('female-refit', 'male-refit')


def plugins_txt():
    local = os.environ.get('LOCALAPPDATA')
    return pathlib.Path(local) / 'Fallout4' / 'plugins.txt' if local else None


def resolve_races(cfg, data, report):
    """Every race editor id the rules name, found in the load order -- or the run is refused. A race
    no plugin defines matches nobody: a typo in distributeRaces would give no NPC a body, and every
    check would still pass. Matched in any case, as the game and LooksMenu match them."""
    wanted = set(cfg.get('distributeRaces') or ['HumanRace'])
    for key in ('blacklistedRacesFemale', 'blacklistedRacesMale'):
        wanted.update(cfg.get(key, []))
    for key in ('raceFemale', 'raceMale'):
        wanted.update(cfg.get(key, {}))
    missing = []
    found = plugin_forms.resolve(data, plugins_txt(), 'RACE', wanted, missing)
    unknown = sorted(w for w in wanted if w not in found)
    if unknown:
        raise SystemExit(f'rules: no race with the editor id {", ".join(map(repr, unknown))} in the load order -- '
                         f'a rule naming it would match nobody. Check the spelling (HumanRace, GhoulRace, ...)')
    report.extend(m for m in missing if 'could not read' in m)


def build(*, stamp, build_id, mode, presets, player, states, never_in_body, variety, cfg, data,
          refit_presets, body_morphs, baked, report):
    """The catalog as a dict, without its rulesHash (rules_hash() below, once the BodyGen lines exist).

    presets:  [{name, sex, marker, values: [(morph, v)], random, menu, zeroed, fit, family}] in
              the order the pickers list them first (the NPC hotkeys walk this order)
    player:   {sex: preset name}          states, never_in_body: {sex: [morph]}
    variety:  {sex: [(morph, low, high, group)]}, only morphs the body carries
    refit_presets: [{name, sex, values: [(morph, v)]}] -- "<Preset>-Refit", "Female-Refit"...
    body_morphs: {sex: set of morphs the installed body carries}
    baked:    {sex: {morph: value}} the base body already has (compensated mode; empty when zeroed):
              every value here is written relative to it, the built-in floors too
    """
    resolve_races(cfg, data, report)
    have = {(p['sex'], p['name'].casefold()): p['name'] for p in presets}

    def names_for(sex, wanted, what):
        out = []
        for n in wanted if isinstance(wanted, list) else [wanted]:
            got = have.get((sex, str(n).casefold()))
            if got is None:
                report.append(f'catalog: {what} names {n!r}, which is not a {sex} preset of this build - left out')
            elif got not in out:
                out.append(got)
        return out

    def sexes_of(wanted):
        return [s for s in ('female', 'male')
                if any((s, str(n).casefold()) in have for n in (wanted if isinstance(wanted, list) else [wanted]))]

    def bodygen_plugin(plugin, what):
        # LooksMenu reads a line whose plugin starts with "All" as an All line (tools/rules.py): BodyGen
        # never applies such a rule, so the plugin must not believe it does either.
        if str(plugin).lower().startswith('all'):
            report.append(f'catalog: {what} names plugin {plugin!r}, which starts with "All" - left out, as BodyGen leaves it')
            return False
        return True

    def ref(plugin, key, what):
        light = rules.is_light(data, plugin)
        fid = rules.form_key(key, light)
        if fid is None:
            report.append(f'catalog: {what} {plugin} {key!r} is not a form id - left out')
            return None
        return {'plugin': plugin, 'id': int(fid, 16)}

    # ---- rules: the tiers BodyGen carries (so the plugin leaves them alone) and the
    # ones only the runtime can see (S-23)
    npc_form = {'female': [], 'male': []}
    for plugin, forms in cfg.get('npcFormID', {}).items():
        if not bodygen_plugin(plugin, 'npcFormID'):
            continue
        for key, wanted in forms.items():
            r = ref(plugin, key, 'npcFormID')
            if r:
                for s in sexes_of(wanted):
                    npc_form[s].append(r)
    blacklisted_form = []
    for plugin, keys in cfg.get('blacklistedNpcsFormID', {}).items():
        if not bodygen_plugin(plugin, 'blacklistedNpcsFormID'):
            continue
        for key in keys:
            r = ref(plugin, key, 'blacklistedNpcsFormID')
            if r:
                blacklisted_form.append(r)
    blacklisted_plugins = {s: [p for p in cfg.get(key, []) if bodygen_plugin(p, key)]
                           for s, key in (('female', 'blacklistedNpcsPluginFemale'), ('male', 'blacklistedNpcsPluginMale'))}

    npc_name = []
    for name, wanted in cfg.get('npc', {}).items():
        for s in ('female', 'male'):
            got = [have[(s, str(n).casefold())] for n in (wanted if isinstance(wanted, list) else [wanted])
                   if (s, str(n).casefold()) in have]
            if got:
                npc_name.append({'name': name, 'sex': s, 'presets': list(dict.fromkeys(got))})
        if not sexes_of(wanted):
            report.append(f'catalog: npc {name!r} names no preset of this build - left out')

    faction = []
    wanted_factions = {e for key in ('factionFemale', 'factionMale') for e in cfg.get(key, {})}
    found = plugin_forms.resolve(data, plugins_txt(), 'FACT', wanted_factions, report)
    for sex, key in (('female', 'factionFemale'), ('male', 'factionMale')):
        for edid, wanted in cfg.get(key, {}).items():
            if edid not in found:
                continue
            got = names_for(sex, wanted, f'{key} {edid!r}')
            if got:
                plugin, local = found[edid]
                faction.append({'plugin': plugin, 'id': local, 'editorID': edid, 'sex': sex, 'presets': got})

    # ---- ORefit (S-20, S-40, S-42), OBody's keys and Silhouette's heavy/light lists
    def refs(key):
        out = []
        for plugin, keys in cfg.get(key, {}).items():
            for k in keys:
                r = ref(plugin, k, key)
                if r:
                    out.append(r)
        return out

    sets = []
    female_body = body_morphs.get('female', set())
    # A floor is a value of the morph layer, which a compensated body adds to what its mesh has baked
    # in: the floor that lands the body AT the built-in value is that value minus the baked one.
    female_baked = (baked or {}).get('female', {})
    builtin = [(m, round(v - female_baked.get(m, 0.0), 6), h) for m, v, h in BUILTIN_FEMALE if m in female_body]
    lower = [m for m, v, _h in builtin if v <= 0]
    if lower:
        report.append(f'catalog: the base body already has {", ".join(lower)} at or above the built-in clothed '
                      f'shape: no floor needed there')
    builtin = [(m, v, h) for m, v, h in builtin if v > 0]
    missing = [m for m, _v, _h in BUILTIN_FEMALE if m not in female_body]
    if missing:
        report.append(f'catalog: the installed female body has no {", ".join(missing)}: the built-in clothed shape '
                      f'leaves {"it" if len(missing) == 1 else "them"} out')
    if builtin:
        sets.append({'name': 'builtin:female', 'sex': 'female',
                     'floors': [{'morph': m, 'value': v, 'heavyOnly': h} for m, v, h in builtin]})
    for p in refit_presets:
        if (p['sex'], ifold(p['name'])) in {(s['sex'], ifold(s['name'])) for s in sets}:
            report.append(f'catalog: refit preset {p["name"]!r} is there twice for {p["sex"]} - the first one is used')
            continue
        floors = [{'morph': m, 'value': round(v, 6), 'heavyOnly': False} for m, v in p['values'] if v > 0]
        lower = [m for m, v in p['values'] if v <= 0]
        if lower:
            report.append(f'catalog: refit preset {p["name"]!r}: {len(lower)} slider(s) at or below the body\'s zero '
                          f'cannot be floors (a refit only raises, S-40) - left out: {", ".join(lower[:6])}'
                          f'{" ..." if len(lower) > 6 else ""}')
        if not floors:
            report.append(f'catalog: refit preset {p["name"]!r} raises nothing on this body - left out, so the next '
                          f'set in line applies')
            continue
        sets.append({'name': p['name'], 'sex': p['sex'], 'floors': floors})
    set_names = {(s['sex'], ifold(s['name'])): s['name'] for s in sets}
    outfits = []
    for sex, key in (('female', 'refitOutfitPresetsFemale'), ('male', 'refitOutfitPresetsMale')):
        for outfit, preset in cfg.get(key, {}).items():
            got = set_names.get((sex, ifold(preset)))
            if got:
                outfits.append({'name': outfit, 'sex': sex, 'set': got})   # the set's own spelling
            else:
                report.append(f'catalog: {key} {outfit!r} names {preset!r}, which is not a {sex} refit set of this '
                              f'build (a BodySlide preset named "<something>-Refit" that raises something) - left out')

    doc = {
        'schema': SCHEMA, 'build': build_id, 'stamp': stamp, 'mode': mode,
        'presets': [{'name': p['name'], 'sex': p['sex'], 'marker': p['marker'],
                     'values': {m: round(v, 6) for m, v in p['values']},
                     'random': p['random'], 'menu': p['menu'], 'zeroed': bool(p.get('zeroed', not p['values'])),
                     'fit': p['fit'], 'family': p['family']} for p in presets],
        'player': {s: player[s] for s in ('female', 'male') if player.get(s)},
        'states': {s: list(states.get(s, [])) for s in ('female', 'male')},
        'neverInBody': {s: list(never_in_body.get(s, [])) for s in ('female', 'male')},
        'variety': {s: [{'morph': m, 'low': lo, 'high': hi, 'group': grp} for m, lo, hi, grp in variety.get(s, [])]
                    for s in ('female', 'male')},
        'rules': {
            'races': list(cfg.get('distributeRaces') or ['HumanRace']),
            'npcFormID': npc_form,
            'blacklistedNpcsFormID': blacklisted_form,
            'blacklistedPlugins': blacklisted_plugins,
            'blacklistedRaces': {'female': list(cfg.get('blacklistedRacesFemale', [])),
                                 'male': list(cfg.get('blacklistedRacesMale', []))},
            'npcName': npc_name,
            'blacklistedNpcNames': list(cfg.get('blacklistedNpcs', [])),
            'faction': faction,
        },
        'orefit': {
            'slots': CLOTHED_SLOTS,
            'blacklist': refs('blacklistedOutfitsFromORefitFormID'),
            'blacklistNames': list(cfg.get('blacklistedOutfitsFromORefit', [])),
            'blacklistPlugins': list(cfg.get('blacklistedOutfitsFromORefitPlugin', [])),
            'force': refs('outfitsForceRefitFormID'),
            'forceNames': list(cfg.get('outfitsForceRefit', [])),
            'outfits': outfits,
            'sets': sets,
            'heavy': {'words': list(cfg.get('heavyWords', rules.DEFAULT['heavyWords'])),
                      'items': refs('heavyOutfitsFormID'), 'names': list(cfg.get('heavyOutfits', []))},
            'light': {'items': refs('lightOutfitsFormID'), 'names': list(cfg.get('lightOutfits', []))},
        },
    }
    return doc


def rules_hash(doc, morph_lines):
    """12 hex digits naming everything the rules do: the BodyGen lines (who BodyGen gives what) and
    the catalog (what the plugin does). Both BodyGen files' headers and the catalog carry it, and the
    plugin refuses files whose hashes differ: the build names the bodies, this names the rules (S-19)."""
    body = {k: v for k, v in doc.items() if k != 'rulesHash'}
    text = json.dumps({'lines': [line for line in morph_lines if not line.startswith('#')], 'catalog': body},
                      sort_keys=True)
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]


def check(doc):
    """What the plugin's parser (src/Catalog.cpp ParseCatalog) refuses, refused here first -- and a
    little more: what it would accept but could never mean (a range of one value)."""
    def fail(msg):
        raise SystemExit(f'catalog: {msg}')

    def need(v, kind, where):
        if not isinstance(v, kind) or isinstance(v, bool) and kind is not bool:
            fail(f'{where}: expected {kind.__name__}, got {type(v).__name__}')
        return v

    def strings(v, where):
        for x in need(v, list, where):
            need(x, str, where)
        return v

    def ref_list(v, where):
        for r in need(v, list, where):
            if not need(r.get('plugin'), str, where):
                fail(f'{where}: an empty plugin name')
            i = need(r.get('id'), int, where)
            if not 0 <= i <= 0xFFFFFF:
                fail(f'{where}: id {i:X} carries a load-order byte')
        return v

    # Everywhere: text the plugin can read back (JSON is UTF-8; a lone surrogate is refused whole), and
    # numbers finite as the float the plugin keeps (it refuses 1e39 and NaN).
    def walk(v, where):
        if isinstance(v, str):
            if not rules.encodable(v):
                fail(f'{where}: {v!r} is not valid Unicode')
        elif isinstance(v, float):
            if not math.isfinite(v) or abs(v) > FLOAT32_MAX:
                fail(f'{where}: {v!r} is not a finite float32')
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(k, where)
                walk(x, f'{where}.{k}')
        elif isinstance(v, list):
            for x in v:
                walk(x, where)

    walk(doc, 'catalog')
    if doc.get('schema') != SCHEMA:
        fail(f'schema must be {SCHEMA}')
    if not (0 < need(doc.get('stamp'), int, 'stamp') < 1 << 24):
        fail(f'stamp {doc["stamp"]} does not fit a float32 exactly')
    for k in ('build', 'mode', 'rulesHash'):
        need(doc.get(k), str, k)
    if not doc['rulesHash']:
        fail('rulesHash is empty')
    never = {s: {ifold(m) for m in strings(doc['neverInBody'][s], 'neverInBody')} for s in ('female', 'male')}
    for s in ('female', 'male'):
        for m in strings(doc['states'][s], 'states'):
            if ifold(m) not in never[s]:
                fail(f'the runtime state {m!r} is missing from neverInBody (S-16)')
    seen, markers = set(), set()
    for p in need(doc['presets'], list, 'presets'):
        where = f'preset {p.get("name")!r}'
        need(p.get('name'), str, where)
        if p.get('sex') not in ('female', 'male'):
            fail(f'{where}: sex must be "female" or "male"')
        marker = need(p.get('marker'), str, where)
        if len(marker) <= len(MARKER_PREFIX) or ifold(marker[:len(MARKER_PREFIX)]) != ifold(MARKER_PREFIX) \
                or ifold(marker) in {ifold(r) for r in RESERVED_MARKERS}:
            fail(f'{where}: marker {marker!r} is not a body marker ("{MARKER_PREFIX}...", not a reserved one)')
        if ifold(marker) in markers:
            fail(f'{where}: marker {marker!r} is used by another preset too')
        markers.add(ifold(marker))
        for m, v in need(p.get('values'), dict, where).items():
            if ifold(m) in never[p['sex']]:
                fail(f'{where}: {m!r} is never part of a body (S-16, S-29)')
            need(v, (int, float), where)
        for k in ('random', 'menu', 'zeroed'):
            need(p.get(k), bool, where)
        # The engine's string pool keeps one spelling per name, whatever the case (L3 F12): two
        # names that differ only in case are one preset to the plugin.
        key = (p['sex'], ifold(p['name']))
        if key in seen:
            fail(f'{where} listed twice for {p["sex"]} (names are compared in any case)')
        seen.add(key)
    for s, name in doc['player'].items():
        if (s, ifold(name)) not in seen:
            fail(f'the {s} player default {name!r} is not a preset of this build')
    for s in ('female', 'male'):
        names = set()
        for v in need(doc['variety'][s], list, 'variety'):
            if not v['low'] < v['high']:
                fail(f'variety {v["morph"]!r}: the range {v["low"]}..{v["high"]} rolls nothing (low must be below high)')
            if v['group'] not in ('nipples', 'genitals'):
                fail(f'variety {v["morph"]!r}: group {v["group"]!r}')
            if ifold(v['morph']) in never[s]:
                fail(f'variety {v["morph"]!r} is never part of a body, so never rolled (S-16, S-29)')
            if ifold(v['morph']) in names:
                fail(f'variety {v["morph"]!r} listed twice for {s}')
            names.add(ifold(v['morph']))
    r = doc['rules']
    strings(r['races'], 'rules.races')
    for s in ('female', 'male'):
        ref_list(r['npcFormID'][s], 'rules.npcFormID')
        strings(r['blacklistedPlugins'][s], 'rules.blacklistedPlugins')
        strings(r['blacklistedRaces'][s], 'rules.blacklistedRaces')
    ref_list(r['blacklistedNpcsFormID'], 'rules.blacklistedNpcsFormID')
    strings(r['blacklistedNpcNames'], 'rules.blacklistedNpcNames')
    for rule in r['npcName'] + r['faction']:
        for n in strings(rule['presets'], 'rule presets'):
            if (rule['sex'], ifold(n)) not in seen:
                fail(f'a rule names {n!r}, not a {rule["sex"]} preset of this build')
    ref_list(r['faction'], 'rules.faction')
    o = doc['orefit']
    for slot in need(o['slots'], list, 'orefit.slots'):
        if not isinstance(slot, int) or not 30 <= slot <= 61:
            fail(f'orefit.slots: {slot!r} is not a biped slot 30..61')
    for k in ('blacklist', 'force'):
        ref_list(o[k], f'orefit.{k}')
    for k in ('blacklistNames', 'blacklistPlugins', 'forceNames'):
        strings(o[k], f'orefit.{k}')
    set_keys = set()
    for st in need(o['sets'], list, 'orefit.sets'):
        where = f'refit set {st.get("name")!r}'
        key = (st['sex'], ifold(need(st.get('name'), str, where)))
        if key in set_keys:
            fail(f'{where} listed twice for {st["sex"]}')
        set_keys.add(key)
        for f in need(st.get('floors'), list, where):
            m = need(f.get('morph'), str, where)
            if not m or ifold(m) == ifold(REFIT_MARKER) or (len(m) > len(MARKER_PREFIX) and ifold(m[:len(MARKER_PREFIX)]) == ifold(MARKER_PREFIX)):
                fail(f'{where}: {m!r} is not a body slider')
            if ifold(m) in never[st['sex']]:
                fail(f'{where}: {m!r} is never part of a body (S-16, S-29)')
            if not need(f.get('value'), (int, float), where) > 0:
                fail(f'{where}: {m!r} at {f["value"]}: a floor must be above 0, a refit only raises (S-40)')
            need(f.get('heavyOnly'), bool, where)
    for ot in o['outfits']:
        if (ot['sex'], ifold(ot['set'])) not in set_keys:
            fail(f'orefit.outfits {ot["name"]!r}: refit set {ot["set"]!r} is not in this catalog')
    for w in strings(o['heavy']['words'], 'orefit.heavy.words'):
        if not rules.has_word(w):
            fail(f'orefit.heavy.words: {w!r} holds no word (S-48)')
    for k in ('heavy', 'light'):
        ref_list(o[k]['items'], f'orefit.{k}.items')
        strings(o[k]['names'], f'orefit.{k}.names')


def write(path, doc):
    check(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=False, allow_nan=False) + '\n', encoding='utf-8')
