"""OBody NG's distribution rules, compiled to LooksMenu BodyGen lines.

The config is OBody's own shape, key for key, so an OBody user can read it and an
OBody include translates by renaming the file:

    data/F4SE/Plugins/Silhouette/Silhouette_presetDistributionConfig.json
    F4SE/Plugins/Silhouette/includes/*.json   (other mods' rules; alphabetical,
                                               a later file overrides an earlier)

OBody's order, from OBody::GenerateActorBody (src/Body/Body.cpp), highest first:

    1. blacklistedNpcs / blacklistedNpcsFormID          -> the NPC gets nothing
    2. npc / npcFormID                                  -> these presets
    3. blacklistedNpcsPlugin* / blacklistedRaces*       -> nothing
    4. faction*                                         -> these presets
    5. npcPlugin*                                       -> these presets
    6. race*                                            -> these presets
    7. random

BodyGen has no priorities, only "a later line overwrites an earlier one for the
same NPC" -- so the lines are written in REVERSE: random pool first, then 6, 5,
4, 3, 2, 1, and the player's own lines after everything.

What BodyGen can express, and so what is compiled today: npcFormID, npcPlugin*,
race*, and every FormID/plugin/race blacklist. `npc` and `blacklistedNpcs` match
a DISPLAY NAME and `faction*` a faction, neither of which a morphs.ini line can
name; base-game names are localised into string tables inside Fallout4 -
Interface.ba2. Those keys are read, validated and reported as pending until the
Phase 2 plugin resolves them at run time.

A blacklist is a line whose only template sets nothing. That is safe here only
because it is the ONLY option on its line: an NPC with no stored morphs is
evaluated again on every load, and evaluates to nothing again, every time.

Plugin and race lines must name a race: LooksMenu matches `npc->race == nullptr
|| npc->race == filter`, so a line with no race reaches only race-less NPCs.
"""
import json
import pathlib

KEYS_PRESET_MAP = ('npcFormID', 'npc', 'factionFemale', 'factionMale',
                   'npcPluginFemale', 'npcPluginMale', 'raceFemale', 'raceMale')
KEYS_LISTS = ('blacklistedNpcs', 'blacklistedNpcsPluginFemale', 'blacklistedNpcsPluginMale',
              'blacklistedRacesFemale', 'blacklistedRacesMale',
              'blacklistedPresetsFromRandomDistribution', 'distributeRaces')
KEYS_PENDING = ('npc', 'blacklistedNpcs', 'factionFemale', 'factionMale')
KEYS_PHASE2 = ('blacklistedOutfitsFromORefitFormID', 'blacklistedOutfitsFromORefit',
               'blacklistedOutfitsFromORefitPlugin', 'outfitsForceRefitFormID', 'outfitsForceRefit')
# OBody only lets includes carry these (JSONParser: obody_includes).
INCLUDE_KEYS = ('npc', 'npcFormID', 'npcPluginFemale', 'npcPluginMale')

CONFIG_NAME = 'Silhouette_presetDistributionConfig.json'
DEFAULT = {
    'npcFormID': {}, 'npc': {}, 'factionFemale': {}, 'factionMale': {},
    'npcPluginFemale': {}, 'npcPluginMale': {}, 'raceFemale': {}, 'raceMale': {},
    'blacklistedNpcs': [], 'blacklistedNpcsFormID': {},
    'blacklistedNpcsPluginFemale': [], 'blacklistedNpcsPluginMale': [],
    'blacklistedRacesFemale': [], 'blacklistedRacesMale': [],
    'blacklistedPresetsFromRandomDistribution': [],
    'blacklistedPresetsShowInOBodyMenu': True,
    # Silhouette's one addition: which races take part in random distribution.
    # OBody distributes to every NPC race; in Fallout 4 only races that wear the
    # human body should, and the base game has one.
    'distributeRaces': ['HumanRace'],
}


def load(config_path, include_dirs, report):
    """The merged config: defaults, then the main file, then includes."""
    cfg = json.loads(json.dumps(DEFAULT))
    if config_path.exists():
        try:
            main = json.loads(config_path.read_text(encoding='utf-8-sig'))
        except json.JSONDecodeError as exc:
            raise SystemExit(f'{config_path}: not valid JSON ({exc})')
        for k, v in main.items():
            if k not in cfg and k not in KEYS_PHASE2:
                report.append(f'config: unknown key {k!r} ignored')
                continue
            cfg[k] = v
    files = {}
    for d in include_dirs:
        if d and d.is_dir():
            for f in d.glob('*.json'):
                files[f.name.lower()] = f            # a later folder's copy wins
    for name in sorted(files):
        f = files[name]
        try:
            inc = json.loads(f.read_text(encoding='utf-8-sig'))
        except json.JSONDecodeError as exc:
            report.append(f'include {f.name}: not valid JSON, skipped ({exc})')
            continue
        for k, v in inc.items():
            if k not in INCLUDE_KEYS:
                report.append(f'include {f.name}: key {k!r} is not allowed in an include (OBody allows '
                              f'{", ".join(INCLUDE_KEYS)}), ignored')
                continue
            if k == 'npcFormID':
                for plugin, forms in v.items():
                    cfg[k].setdefault(plugin, {}).update(forms)
            else:
                cfg[k].update(v)
    for k in KEYS_PENDING:
        if cfg.get(k):
            report.append(f'config: {k} has {len(cfg[k])} entr{"y" if len(cfg[k]) == 1 else "ies"} -- '
                          f'matching by name/faction needs the Phase 2 plugin; not applied yet')
    for k in KEYS_PHASE2:
        if cfg.get(k):
            report.append(f'config: {k} is ORefit (Phase 2); not applied yet')
    return cfg


def form_key(text):
    """OBody writes FormIDs as hex, with or without 0x, sometimes with the load-order
    byte; LooksMenu wants the id WITHOUT it (it adds the plugin's own). -> 6 hex
    digits, or None if the key is not hex. For a light (ESL) plugin give the
    local id; LooksMenu composes 0xFE with the plugin's light index itself."""
    try:
        v = int(str(text).strip().lower().removeprefix('0x'), 16)
    except ValueError:
        return None
    v &= 0xFFFFFF
    return f'{v:06X}' if v else None


def compile_lines(cfg, resolve_presets, data, report):
    """-> (lines, needed_templates): BodyGen lines in the order they must be
    written (after the random pool), and the template names they reference.

    resolve_presets(names, gender or None) -> {'female': [template], 'male': [...]}
    of templates for the preset names that exist and fit that gender's body,
    reporting the ones that do not.
    """
    lines, needed = [], set()
    distribute = cfg.get('distributeRaces') or ['HumanRace']

    def plugin_ok(plugin):
        if not (data / plugin).exists():
            report.append(f'rules: plugin {plugin!r} is not in Data -- LooksMenu will skip its lines')
        return True

    def emit(left, templates):
        if templates:
            lines.append(f'{left}=' + '|'.join(templates))
            needed.update(templates)

    # 6. race presets
    for g, key, label in (('female', 'raceFemale', 'Female'), ('male', 'raceMale', 'Male')):
        for race, names in cfg.get(key, {}).items():
            emit(f'All|{label}|{race}', resolve_presets(names, g).get(g))
    # 5. plugin presets -- every race that takes part, since a line needs one
    for g, key, label in (('female', 'npcPluginFemale', 'Female'), ('male', 'npcPluginMale', 'Male')):
        for plugin, names in cfg.get(key, {}).items():
            plugin_ok(plugin)
            races = sorted(set(distribute) | set(cfg.get(f'race{label}', {})))
            for race in races:
                emit(f'{plugin}|All|{label}|{race}', resolve_presets(names, g).get(g))
    # 4. faction presets: pending (reported by load)
    # 3. plugin and race blacklists
    for g, key, label in (('female', 'blacklistedNpcsPluginFemale', 'Female'),
                          ('male', 'blacklistedNpcsPluginMale', 'Male')):
        for plugin in cfg.get(key, []):
            plugin_ok(plugin)
            races = sorted(set(distribute) | set(cfg.get(f'race{label}', {})))
            for race in races:
                emit(f'{plugin}|All|{label}|{race}', [KEEP])
    for g, key, label in (('female', 'blacklistedRacesFemale', 'Female'),
                          ('male', 'blacklistedRacesMale', 'Male')):
        for race in cfg.get(key, []):
            emit(f'All|{label}|{race}', [KEEP])
    # 2. per-NPC presets by FormID. A preset list may hold both sexes' presets;
    # each sex's table gets its own.
    for plugin, forms in cfg.get('npcFormID', {}).items():
        plugin_ok(plugin)
        for key, names in forms.items():
            fid = form_key(key)
            if fid is None:
                report.append(f'rules: npcFormID {plugin} {key!r} is not a FormID, skipped')
                continue
            by_g = resolve_presets(names, None)
            for g, label in (('female', 'Female'), ('male', 'Male')):
                emit(f'{plugin}|{fid}|{label}', by_g.get(g))
    # 1. per-NPC blacklists by FormID
    for plugin, keys in cfg.get('blacklistedNpcsFormID', {}).items():
        plugin_ok(plugin)
        for key in keys:
            fid = form_key(key)
            if fid is None:
                report.append(f'rules: blacklistedNpcsFormID {plugin} {key!r} is not a FormID, skipped')
                continue
            emit(f'{plugin}|{fid}', [KEEP])
    return lines, needed


KEEP = 'Silhouette_KeepBase'


def write_default(path):
    """The shipped config: every key present and empty, as OBody ships its own."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT, indent=2) + '\n', encoding='utf-8')
