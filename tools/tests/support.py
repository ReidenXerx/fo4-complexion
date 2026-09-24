"""What every test here shares: where the tools, the committed package and the game's Data are, and the
plugin's own parser.

    python -m unittest discover -s tools/tests -v       (scripts/build-plugin.ps1 runs it after the C++ tests)

The environment can point a run elsewhere:
    SILHOUETTE_TOOLS_DIR   another copy of tools/ -- a deliberately broken one, to see a test fail (GP-2);
                           its parent must hold papyrus/Silhouette/{API,Bridge}.psc, which the verifier reads
    SILHOUETTE_DATA        the game's Data folder (default: the generator's)
    SILHOUETTE_TESTS_EXE   SilhouetteTests.exe (default: build/Release)
    SILHOUETTE_TEST_JOBS   how many verifier runs at once (default: half the processors)
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
TOOLS = pathlib.Path(os.environ.get('SILHOUETTE_TOOLS_DIR') or REPO / 'tools').resolve()
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import silhouette_gen  # noqa: E402  (after the path: the tools under test)

PACKAGE = REPO / 'data'                                   # the generated package, as committed
PSC = REPO / 'papyrus/Silhouette/Player.psc'
LOOSE = pathlib.Path('F4SE/Plugins/F4EE/BodyGen/Loose')
CAT = pathlib.Path('F4SE/Plugins/Silhouette/catalog.json')
MANIFESTS = pathlib.Path('F4SE/Plugins/Silhouette/manifests')
MCM = pathlib.Path('MCM/Config/Silhouette')
ENV = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
# A test run shares the machine with whatever else runs on it -- a game, say: the heavy subprocesses go below it.
LOW_PRIORITY = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)


def game_data():
    return pathlib.Path(os.environ.get('SILHOUETTE_DATA') or silhouette_gen.DEFAULT_DATA)


def bodies_missing(data=None):
    """Why the verifier cannot run against this Data -- None when it can: both bodies built with their
    morphs, and BodySlide's presets."""
    data = data or game_data()
    need = [data / 'Tools/BodySlide/SliderPresets']
    for body in silhouette_gen.BODIES.values():
        need += [data / f'Meshes/Actors/Character/CharacterAssets/{body}{ext}' for ext in ('.nif', '.tri')]
    missing = [str(p) for p in need if not p.exists()]
    return f'no game Data with the bodies here ({", ".join(missing)})' if missing else None


def tests_exe():
    """SilhouetteTests.exe, whose --check is the plugin's own parser -- None when it is not built."""
    exe = pathlib.Path(os.environ.get('SILHOUETTE_TESTS_EXE') or REPO / 'build/Release/SilhouetteTests.exe')
    return exe if exe.exists() else None


def jobs():
    return max(1, int(os.environ.get('SILHOUETTE_TEST_JOBS') or (os.cpu_count() or 2) // 2))


class Scratch:
    """A temporary folder, removed afterwards: `with Scratch() as root:`."""
    def __enter__(self):
        self.path = pathlib.Path(tempfile.mkdtemp(prefix='sil-'))
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)
