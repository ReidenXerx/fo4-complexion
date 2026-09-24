"""silhouette_gen.main() and verify_bodygen.main() are wired as their helpers promise (wave 5, lens 3 M1): the
tests of manifest_history, refuse_stamp_clash and refuse_foreign_config call those helpers directly, so the
lines of main() that hand them the game's Data -- or call them at all -- could be deleted with every one green.

What depends only on the arguments is refused before anything is measured or written: no Data needed. The
rest is one real generator run into a scratch package, the game's Data read as always but its manifests stood
in for by a scratch folder, and the verifier run as far as its history read."""
import contextlib
import io
import json
import pathlib
import shutil
import sys
import unittest
from unittest import mock

import support
import rules
import silhouette_gen as sg
import verify_bodygen

CONFIG = pathlib.Path('F4SE/Plugins/Silhouette') / rules.CONFIG_NAME
WORD = 'zzsilhouettewavefive'       # a heavy word only the package's own config holds


def run_main(module, argv):
    """(the SystemExit message, or None; stdout) of module.main() run in this process with these arguments."""
    out = io.StringIO()
    with mock.patch.object(sys, 'argv', ['main', *map(str, argv)]), contextlib.redirect_stdout(out):
        try:
            module.main()
        except SystemExit as exc:
            return str(exc), out.getvalue()
    return None, out.getvalue()


def files_under(root):
    return sorted(str(p.relative_to(root)) for p in pathlib.Path(root).rglob('*') if p.is_file())


class RefusedFirst(unittest.TestCase):
    def test_out_without_psc(self):
        with support.Scratch() as root:
            msg, _out = run_main(sg, ['--write', '--out', root / 'pkg', '--data', root / 'nodata'])
            self.assertIn('pass --psc <file> too', msg or '')
            self.assertEqual(files_under(root), [])

    def test_a_config_that_is_not_there(self):
        with support.Scratch() as root:
            msg, _out = run_main(sg, ['--write', '--out', root / 'pkg', '--psc', root / 'p.psc',
                                      '--config', root / 'nope.json', '--data', root / 'nodata'])
            self.assertIn('nope.json: no such file', msg or '')
            self.assertEqual(files_under(root), [])

    def test_another_config_in_the_output_root(self):
        with support.Scratch() as root:
            mine = root / 'pkg' / CONFIG
            mine.parent.mkdir(parents=True)
            shipped = json.loads((support.PACKAGE / CONFIG).read_text(encoding='utf-8-sig'))
            mine.write_text(json.dumps({**shipped, 'heavyWords': shipped['heavyWords'] + [WORD]}), encoding='utf-8')
            msg, _out = run_main(sg, ['--write', '--out', root / 'pkg', '--psc', root / 'p.psc',
                                      '--config', support.PACKAGE / CONFIG, '--data', root / 'nodata'])
            self.assertIn('is not the config this run compiles', msg or '')
            self.assertIn("'heavyWords'", msg or '')
            self.assertEqual(files_under(root), [str(pathlib.Path('pkg') / CONFIG)])


@support.needs_data
class Wiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = support.Scratch()
        root = cls.scratch.__enter__()
        cls.pkg = root / 'pkg'
        man = root / 'fakedata' / sg.MANIFESTS       # stands in for the game's Data's manifests
        man.mkdir(parents=True)
        (man / 'junk.json').write_text('{"templates": [', encoding='utf-8')
        # A preset whose marker today is its plain one: that marker recorded, in "Data" only, for somebody else.
        cat = json.loads((support.PACKAGE / support.CAT).read_text(encoding='utf-8-sig'))
        cls.victim = next(p for p in cat['presets'] if p['marker'] == sg.plain_marker(p['name']))
        (man / '77.json').write_text(json.dumps({'stamp': 77, 'build': '00004d000000', 'templates': {
            cls.victim['marker']: {'preset': 'Somebody Else', 'gender': cls.victim['sex'], 'values': {}}}}),
            encoding='utf-8')
        # The package's own config (S-61), holding a word no other config does.
        own = json.loads((support.PACKAGE / CONFIG).read_text(encoding='utf-8-sig'))
        own['heavyWords'] = own['heavyWords'] + [WORD]
        cls.config = json.dumps(own, indent=2) + '\n'
        (cls.pkg / CONFIG).parent.mkdir(parents=True)
        (cls.pkg / CONFIG).write_text(cls.config, encoding='utf-8')

        cls.calls = calls = []
        real_history, real_clash = sg.manifest_history, sg.refuse_stamp_clash

        def folders(out, data):
            calls.append(('folders', pathlib.Path(out), pathlib.Path(data)))
            return [pathlib.Path(out) / sg.MANIFESTS, man]

        def history(*f, **kw):
            calls.append(('history', list(f)))
            return real_history(*f, **kw)

        def clash(stamp, build, templates, *f, **kw):
            calls.append(('clash', list(f)))
            return real_clash(stamp, build, templates, *f, **kw)

        with mock.patch.object(sg, 'manifest_folders', folders), mock.patch.object(sg, 'manifest_history', history), \
                mock.patch.object(sg, 'refuse_stamp_clash', clash):
            cls.refusal, cls.out = run_main(sg, ['--write', '--out', cls.pkg, '--psc', root / 'Player.psc',
                                                 '--data', support.game_data()])
        cls.man = man

    @classmethod
    def tearDownClass(cls):
        cls.scratch.__exit__(None, None, None)

    def test_the_run_completes(self):
        self.assertIsNone(self.refusal, self.out[-2000:])

    def test_the_game_data_reaches_both_readers_through_one_list(self):
        self.assertIn(('folders', self.pkg, support.game_data()), self.calls)
        want = [self.pkg / sg.MANIFESTS, self.man]
        self.assertIn(('history', want), self.calls)
        self.assertIn(('clash', want), self.calls)

    def test_a_manifest_only_the_data_holds_keeps_a_newcomer_off_its_marker(self):
        got = json.loads((self.pkg / support.CAT).read_text(encoding='utf-8-sig'))
        marker = next(p['marker'] for p in got['presets'] if p['name'] == self.victim['name'])
        self.assertNotEqual(marker, self.victim['marker'])
        self.assertTrue(marker.startswith(self.victim['marker'] + '_'), marker)

    def test_an_unreadable_manifest_in_the_data_is_said_and_skipped(self):
        self.assertIn('junk.json: not a manifest this tool can read', self.out)
        self.assertIn("in the Silhouette mod's staging folder", self.out)

    def test_the_package_is_made_from_its_own_config(self):
        got = json.loads((self.pkg / support.CAT).read_text(encoding='utf-8-sig'))
        self.assertIn(WORD, got['orefit']['heavy']['words'])
        self.assertEqual((self.pkg / CONFIG).read_text(encoding='utf-8'), self.config)   # never replaced

    def test_the_verifier_reads_the_same_folders(self):
        seen = []

        class Stop(Exception):
            pass

        def history(*f, **kw):
            seen.append((list(f), kw))
            raise Stop()

        with mock.patch.object(sg, 'manifest_history', history), self.assertRaises(Stop):
            run_main(verify_bodygen, ['--data', support.game_data(), '--dir', support.PACKAGE / support.LOOSE,
                                      '--psc', support.PSC])
        self.assertEqual(seen[0][0], sg.manifest_folders(support.PACKAGE, support.game_data()))
        self.assertIsInstance(seen[0][1].get('notes'), list)


if __name__ == '__main__':
    unittest.main()
