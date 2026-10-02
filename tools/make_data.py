"""Writes what Complexion.dll reads, into data/F4SE/Plugins/Complexion/ (shipped as it is).

    python tools/make_data.py [--data <game Data>]

- profiles.json: data/profiles.json with every group's factions resolved to [plugin, editor id, local form id].
  The game keeps no editor id for a faction at run time, so the plugin looks factions up by id (as Silhouette
  resolves OBody's faction rules, S-19). A faction that cannot be resolved fails the run.
- tags.json: build/tags.json (tools/overlay_tags.py), every template's tags. The plugin hands out only those with
  quality "ok" and lore not "breaks", and only templates LooksMenu actually loads on the player's machine.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin_forms  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'F4SE' / 'Plugins' / 'Complexion'
DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=pathlib.Path, default=DATA)
    a = ap.parse_args()
    profiles = json.loads((ROOT / 'data' / 'profiles.json').read_text(encoding='utf-8'))
    ids = {}
    errors = []
    for name, group in profiles['groups'].items():
        resolved = []
        for plugin, edid in [f[:2] for f in group['factions']]:
            if plugin not in ids:
                path = a.data / plugin
                if not path.exists():
                    errors.append(f'{name}: {plugin} is not in {a.data}')
                    continue
                ids[plugin] = plugin_forms.editor_ids(path, 'FACT')
            hit = ids[plugin].get(edid)
            if not hit:
                errors.append(f'{name}: no faction {edid} in {plugin}')
                continue
            resolved.append([hit[0], edid, hit[1]])
        group['factions'] = resolved
    if errors:
        sys.exit('\n'.join(errors))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'profiles.json').write_text(json.dumps(profiles, indent=1), encoding='utf-8', newline='\n')
    tags = json.loads((ROOT / 'build' / 'tags.json').read_text(encoding='utf-8'))
    (OUT / 'tags.json').write_text(json.dumps(tags, indent=0, sort_keys=True), encoding='utf-8', newline='\n')
    print(f'profiles: {len(profiles["groups"])} groups, '
          f'{sum(len(g["factions"]) for g in profiles["groups"].values())} factions resolved; tags: {len(tags)} -> {OUT}')


if __name__ == '__main__':
    main()
