"""Strip from a release's manifests the presets of the machine the builds were made on (S-74).

    python tools/release_manifests.py <release manifests folder> --current <stamp>

Every build's manifest is kept (S-6, S-12): it names the preset of every body the build could give, so a body
from an older build is still named, touched up and healed -- without it the plugin cannot name the body at all
(Catalog::PresetForMarker). A build generated without --release carries the presets installed where it was
made, and its manifest carries their values: those entries are the author's, never a player's, so a public
archive strips them and keeps the rest -- every body of Silhouette's own presets, from any build, stays named.
Run on the RELEASE copy only (scripts/make-release.ps1): the repo's own manifests are the author's saves' and
stay whole. Refuses if the current build's own manifest carries any: that build is not a release
(silhouette_gen.py --write --release).
"""
import argparse
import json
import pathlib
import sys

import silhouette_gen as sg


def foreign(preset, own, stock):
    return preset not in own and preset.casefold() not in stock


def foreign_presets(manifest, own, stock):
    """The presets a manifest holds that are neither the package's own nor CBBE's or BodyTalk's stock."""
    return sorted({t['preset'] for t in manifest.get('templates', {}).values() if foreign(t['preset'], own, stock)})


def strip(folder, current, own, stock):
    """Take every foreign preset's entry out of each manifest in folder, keeping the rest of it
    -> [(file name, entries stripped, entries kept)]."""
    stripped = []
    for f in sorted(folder.glob('*.json')):
        m = json.loads(f.read_text(encoding='utf-8'))
        names = foreign_presets(m, own, stock)
        if not names:
            continue
        if f.stem == str(current):
            raise SystemExit(f'the current build\'s manifest {f.name} carries presets that are neither Silhouette\'s '
                             f'own nor stock ({", ".join(names[:5])}): regenerate with silhouette_gen.py --write '
                             f'--release (S-74)')
        before = len(m['templates'])
        m['templates'] = {k: t for k, t in m['templates'].items() if not foreign(t['preset'], own, stock)}
        # An early build's player default was a preset of this machine's (S-10's first medoid): its name goes too.
        # The plugin reads only stamp and templates; the player record is the generator's, from the repo's copy.
        # Older manifests record the player's default as the preset name alone, later ones as {preset, template}.
        m['player'] = {sex: p for sex, p in (m.get('player') or {}).items()
                       if not foreign(p.get('preset', '') if isinstance(p, dict) else str(p), own, stock)}
        f.write_text(json.dumps(m, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        stripped.append((f.name, before - len(m['templates']), len(m['templates'])))
    return stripped


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('folder', type=pathlib.Path, help='the release copy\'s F4SE/Plugins/Silhouette/manifests')
    ap.add_argument('--current', required=True, help='the stamp of the build being released')
    ap.add_argument('--own', type=pathlib.Path, default=sg.ROOT / 'data' / sg.PRESETS,
                    help='the package\'s own SliderPresets folder')
    args = ap.parse_args()
    own = {p['name'] for p in sg.read_presets(args.own)}
    for name, gone, kept in strip(args.folder, args.current, own, sg.release_stock()):
        print(f'manifest {name}: {gone} entries of this machine\'s presets stripped, {kept} kept')
    return 0


if __name__ == '__main__':
    sys.exit(main())
