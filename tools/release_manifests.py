"""Leave out of a release the manifests of builds made with this machine's own presets (S-74).

    python tools/release_manifests.py <release manifests folder> --current <stamp>

Every build's manifest is kept (S-6, S-12): it holds the values of every body the build could give, so a body
from an older build is still known. A build generated without --release carries the presets installed where
it was made, and its manifest carries their values -- they are the author's, never a player's, so a public
archive leaves them out. Run on the RELEASE copy only (scripts/make-release.ps1): the repo's own manifests are
the author's saves' and stay. Refuses if the current build's own manifest is one of them: that build is not a
release (silhouette_gen.py --write --release).
"""
import argparse
import json
import pathlib
import sys

import silhouette_gen as sg


def foreign_presets(manifest, own, stock):
    """The presets a manifest holds that are neither the package's own nor CBBE's or BodyTalk's stock."""
    return sorted({t['preset'] for t in manifest.get('templates', {}).values()
                   if t['preset'] not in own and t['preset'].casefold() not in stock})


def prune(folder, current, own, stock):
    """Delete from folder every manifest carrying a foreign preset -> [(file name, first foreign names)]."""
    left_out = []
    for f in sorted(folder.glob('*.json')):
        foreign = foreign_presets(json.loads(f.read_text(encoding='utf-8')), own, stock)
        if not foreign:
            continue
        if f.stem == str(current):
            raise SystemExit(f'the current build\'s manifest {f.name} carries presets that are neither Silhouette\'s '
                             f'own nor stock ({", ".join(foreign[:5])}): regenerate with silhouette_gen.py --write '
                             f'--release (S-74)')
        f.unlink()
        left_out.append((f.name, foreign[:3]))
    return left_out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('folder', type=pathlib.Path, help='the release copy\'s F4SE/Plugins/Silhouette/manifests')
    ap.add_argument('--current', required=True, help='the stamp of the build being released')
    ap.add_argument('--own', type=pathlib.Path, default=sg.ROOT / 'data' / sg.PRESETS,
                    help='the package\'s own SliderPresets folder')
    args = ap.parse_args()
    own = {p['name'] for p in sg.read_presets(args.own)}
    for name, foreign in prune(args.folder, args.current, own, sg.release_stock()):
        print(f'left out manifest {name}: a build with this machine\'s presets ({", ".join(foreign)} ...)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
