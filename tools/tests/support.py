"""What every test here shares: where the tools, the committed package and the game's Data are, and the
plugin's own parser.

    python -m unittest discover -s tools/tests -v       (scripts/build-plugin.ps1 runs it after the C++ tests)

The environment can point a run elsewhere:
    SILHOUETTE_TOOLS_DIR   another copy of tools/ -- a deliberately broken one, to see a test fail (GP-2);
                           its parent must hold papyrus/Silhouette/{API,Bridge}.psc, which the verifier reads
    SILHOUETTE_DATA        the game's Data folder (default: the generator's)
    SILHOUETTE_TESTS_EXE   SilhouetteTests.exe (default: build/Release)
    SILHOUETTE_TEST_JOBS   how many verifier runs at once (default: half the processors)
    SILHOUETTE_REQUIRE_DATA=1   a test that needs the game's Data FAILS without it instead of being skipped
                           (scripts/make-release.ps1: a release never passes with the verifier's refusals untested)
"""
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

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
    return f'{NO_DATA} ({", ".join(missing)})' if missing else None


REQUIRE_DATA = os.environ.get('SILHOUETTE_REQUIRE_DATA') == '1'
# What a skipped class says, word for word: scripts/build-plugin.ps1 looks for it to say so on its last line.
NO_DATA = 'no game Data with the bodies here'


def needs_data(cls):
    """A test class that needs the game's Data: skipped without it -- or, under SILHOUETTE_REQUIRE_DATA=1, failed."""
    why = bodies_missing()
    if not why:
        return cls
    if not REQUIRE_DATA:
        return unittest.skip(why)(cls)

    def refuse(klass):
        raise AssertionError(f'SILHOUETTE_REQUIRE_DATA=1, and {why}')
    cls.setUpClass = classmethod(refuse)
    return cls


def esp_without(blob, *form_ids):
    """The plugin's bytes with those records left out -- a group they leave empty goes too, as the esp of an
    older Silhouette had no keyword group at all."""
    (size,) = struct.unpack_from('<I', blob, 4)
    out = bytearray(blob[:24 + size])
    o = 24 + size
    while o < len(blob):
        (gsize,) = struct.unpack_from('<I', blob, o + 4)
        kept, p = b'', o + 24
        while p < o + gsize:
            dsize, _flags, form_id = struct.unpack_from('<III', blob, p + 4)
            if form_id not in form_ids:
                kept += blob[p:p + 24 + dsize]
            p += 24 + dsize
        if kept:
            out += blob[o:o + 4] + struct.pack('<I', 24 + len(kept)) + blob[o + 8:o + 24] + kept
        o += gsize
    return bytes(out)


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
