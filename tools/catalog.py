"""F4SE/Plugins/Silhouette/catalog.json: what Silhouette.dll needs to know (decision S-19).

The generator stays the compiler. It has already measured which presets fit, what
each one writes, what is a runtime state (S-16) and what BodyGen rolls per NPC (S-17,
S-21); the plugin re-derives none of it and refuses a catalog that disagrees with
the BodyGen files beside it (their headers carry the same build and stamp).

The schema is the plugin's parser (src/Catalog.cpp), key for key; a catalog it cannot
read whole is refused whole, so this writer checks the same things before writing:
every rule names a preset the catalog carries for that sex, form ids carry no
load-order byte, stamps fit a float32 exactly.
"""
import json
import os
import pathlib

import plugin_forms
import rules

SCHEMA = 1
BLACKLIST_MARKER = 'Silhouette_Blacklisted'   # S-23: stored, moves nothing, keeps BodyGen away
CLOTHED_SLOTS = [33, 36, 41]                  # BODY, [U] Torso, [A] Torso (S-20)

# The built-in clothed shape for a CBBE body (S-20), used when no refit preset of the
# user's applies. Breasts pulled together and lifted a little, nipples flattened so
# they do not poke through, the seat eased. Every value is a floor, a ceiling or a
# small step from the naked value, so a modest body is left almost as it was.
BUILTIN_FEMALE = [
    ('BreastsTogether', 'max', 0.3),
    ('BreastGravity2', 'min', 0.2),
    ('PushUp', 'max', 0.2),
    ('NipBGone', 'set', 1.0),
    ('NippleLength', 'set', 0.0),
    ('NipplePerkiness', 'set', 0.0),
    ('NipplePerk2', 'set', 0.0),
    ('NippleTip', 'set', 0.0),
    ('Butt', 'add', -0.05),
    ('AppleCheeks', 'add', -0.05),
]


def is_refit(name):
    """A BodySlide preset that is a clothed shape, not a body: OBody's naming."""
    n = name.casefold()
    return n.endswith('-refit') or n in ('female-refit', 'male-refit')


def plugins_txt():
    local = os.environ.get('LOCALAPPDATA')
    return pathlib.Path(local) / 'Fallout4' / 'plugins.txt' if local else None


def build(*, stamp, build_id, mode, presets, player, states, variety, cfg, data, refit_presets, report):
    """The catalog as a dict.

    presets:  [{name, sex, marker, values: [(morph, v)], random, menu, fit, family}] in
              the order the pickers list them first (the NPC hotkeys walk this order)
    player:   {sex: preset name}          states: {sex: [morph]}
    variety:  {sex: [(morph, low, high, group)]}, only morphs the body carries
    refit_presets: [{name, sex, values: [(morph, v)]}] -- "<Preset>-Refit", "Female-Refit"...
    """
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
        for key, wanted in forms.items():
            r = ref(plugin, key, 'npcFormID')
            if r:
                for s in sexes_of(wanted):
                    npc_form[s].append(r)
    blacklisted_form = []
    for plugin, keys in cfg.get('blacklistedNpcsFormID', {}).items():
        for key in keys:
            r = ref(plugin, key, 'blacklistedNpcsFormID')
            if r:
                blacklisted_form.append(r)

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

    # ---- ORefit (S-20), OBody's keys
    def refs(key):
        out = []
        for plugin, keys in cfg.get(key, {}).items():
            for k in keys:
                r = ref(plugin, k, key)
                if r:
                    out.append(r)
        return out

    sets = [{'name': 'builtin:female', 'sex': 'female',
             'entries': [{'morph': m, 'op': op, 'value': v} for m, op, v in BUILTIN_FEMALE]}]
    for p in refit_presets:
        sets.append({'name': p['name'], 'sex': p['sex'],
                     'entries': [{'morph': m, 'op': 'set', 'value': round(v, 6)} for m, v in p['values']]})
    set_names = {(s['sex'], s['name'].casefold()) for s in sets}
    outfits = []
    for sex, key in (('female', 'refitOutfitPresetsFemale'), ('male', 'refitOutfitPresetsMale')):
        for outfit, preset in cfg.get(key, {}).items():
            if (sex, str(preset).casefold()) in set_names:
                outfits.append({'name': outfit, 'sex': sex, 'set': preset})
            else:
                report.append(f'catalog: {key} {outfit!r} names {preset!r}, which is not a {sex} refit preset '
                              f'(a BodySlide preset named "<something>-Refit") - left out')

    doc = {
        'schema': SCHEMA, 'build': build_id, 'stamp': stamp, 'mode': mode,
        'presets': [{'name': p['name'], 'sex': p['sex'], 'marker': p['marker'],
                     'values': {m: round(v, 6) for m, v in p['values']},
                     'random': p['random'], 'menu': p['menu'], 'zeroed': not p['values'],
                     'fit': p['fit'], 'family': p['family']} for p in presets],
        'player': {s: player[s] for s in ('female', 'male') if player.get(s)},
        'states': {s: list(states.get(s, [])) for s in ('female', 'male')},
        'variety': {s: [{'morph': m, 'low': lo, 'high': hi, 'group': grp} for m, lo, hi, grp in variety.get(s, [])]
                    for s in ('female', 'male')},
        'blacklistMarker': BLACKLIST_MARKER,
        'rules': {
            'races': list(cfg.get('distributeRaces') or ['HumanRace']),
            'npcFormID': npc_form,
            'blacklistedNpcsFormID': blacklisted_form,
            'blacklistedPlugins': {'female': list(cfg.get('blacklistedNpcsPluginFemale', [])),
                                   'male': list(cfg.get('blacklistedNpcsPluginMale', []))},
            'blacklistedRaces': {'female': list(cfg.get('blacklistedRacesFemale', [])),
                                 'male': list(cfg.get('blacklistedRacesMale', []))},
            'npcName': npc_name,
            'blacklistedNpcNames': list(cfg.get('blacklistedNpcs', [])),
            'faction': faction,
        },
        'orefit': {
            'enabled': True, 'slots': CLOTHED_SLOTS,
            'blacklist': refs('blacklistedOutfitsFromORefitFormID'),
            'blacklistNames': list(cfg.get('blacklistedOutfitsFromORefit', [])),
            'blacklistPlugins': list(cfg.get('blacklistedOutfitsFromORefitPlugin', [])),
            'force': refs('outfitsForceRefitFormID'),
            'forceNames': list(cfg.get('outfitsForceRefit', [])),
            'outfits': outfits,
            'sets': sets,
        },
    }
    check(doc)
    return doc


def check(doc):
    """What the plugin's parser would refuse, refused here first."""
    if not (0 < doc['stamp'] < 1 << 24):
        raise SystemExit(f'catalog: stamp {doc["stamp"]} does not fit a float32 exactly')
    seen = set()
    for p in doc['presets']:
        key = (p['sex'], p['name'])
        if key in seen:
            raise SystemExit(f'catalog: preset {p["name"]!r} listed twice for {p["sex"]}')
        seen.add(key)
    for s, name in doc['player'].items():
        if (s, name) not in seen:
            raise SystemExit(f'catalog: the {s} player default {name!r} is not a preset of this build')
    for r in doc['rules']['npcName'] + doc['rules']['faction']:
        for n in r['presets']:
            if (r['sex'], n) not in seen:
                raise SystemExit(f'catalog: a rule names {n!r}, not a {r["sex"]} preset of this build')
    for group in ('npcFormID',):
        for s in ('female', 'male'):
            for r in doc['rules'][group][s]:
                if r['id'] > 0xFFFFFF:
                    raise SystemExit(f'catalog: {group} id {r["id"]:X} carries a load-order byte')
    for s in ('female', 'male'):
        for v in doc['variety'][s]:
            if v['morph'] in doc['states'][s]:
                raise SystemExit(f'catalog: variety {v["morph"]!r} is a runtime state (S-16)')
            if v['low'] > v['high']:
                raise SystemExit(f'catalog: variety {v["morph"]!r} has low above high')


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=False) + '\n', encoding='utf-8')
