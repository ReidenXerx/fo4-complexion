"""S-74: a public build carries Silhouette's own presets and the stock ones CBBE and BodyTalk ship -- never the
presets installed on the machine it was generated on. 0.1.0's first archive carried 68 of them (the author's
Rocket Bomb Body, Josie, SevenBase ...), baked into the templates and every picker.
"""
import json
import pathlib
import tempfile
import unittest

import support
import silhouette_gen as sg
import verify_bodygen


def preset_file(folder, names):
    folder.mkdir(parents=True, exist_ok=True)
    body = ''.join(f'<Preset name="{n}" set="CBBE Body"><Group name="CBBE"/>'
                   f'<SetSlider name="Breasts" size="big" value="40"/></Preset>' for n in names)
    (folder / 'presets.xml').write_text(f'<SliderPresets>{body}</SliderPresets>', encoding='utf-8')


class ReleaseReading(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self.tmp.name)
        self.own, self.game = t / 'own', t / 'game'
        preset_file(self.own, ['Plain F01'])
        preset_file(self.game, ['CBBE Curvy', 'The Rocket Bomb Body CBBE', 'BT - Zero', 'plain f01'])

    def tearDown(self):
        self.tmp.cleanup()

    def names(self, release):
        return [p['name'] for p in sg.read_all_presets([self.own, self.game], release=release)]

    def test_a_release_keeps_its_own_and_the_stock_presets_only(self):
        self.assertEqual(self.names(True), ['Plain F01', 'CBBE Curvy', 'BT - Zero'])

    def test_a_build_for_this_machine_keeps_everything_installed(self):
        self.assertEqual(self.names(False), ['Plain F01', 'CBBE Curvy', 'The Rocket Bomb Body CBBE', 'BT - Zero'])


class ReleaseCheck(unittest.TestCase):
    STOCK = {'cbbe curvy', 'bt - zero'}

    def test_a_foreign_preset_is_named(self):
        cat = {'presets': [{'name': 'Plain F01'}, {'name': 'CBBE Curvy'}, {'name': 'The Rocket Bomb Body CBBE'}]}
        problems = verify_bodygen.release_problems(cat, {'Plain F01'}, self.STOCK)
        self.assertEqual(len(problems), 1)
        self.assertIn('The Rocket Bomb Body CBBE', problems[0])
        self.assertNotIn('CBBE Curvy,', problems[0])

    def test_own_and_stock_pass(self):
        cat = {'presets': [{'name': 'Plain F01'}, {'name': 'CBBE Curvy'}, {'name': 'BT - Zero'}]}
        self.assertEqual(verify_bodygen.release_problems(cat, {'Plain F01'}, self.STOCK), [])


class ReleaseManifests(unittest.TestCase):
    STOCK = {'cbbe curvy'}

    def write(self, folder, stamp, presets):
        templates = {f'Silhouette_{i}': {'gender': 'female', 'preset': p, 'values': {}} for i, p in enumerate(presets)}
        (folder / f'{stamp}.json').write_text(json.dumps({'stamp': stamp, 'templates': templates}), encoding='utf-8')

    def test_an_old_build_with_this_machines_presets_is_left_out_and_the_rest_kept(self):
        import release_manifests
        with tempfile.TemporaryDirectory() as t:
            folder = pathlib.Path(t)
            self.write(folder, 1, ['Plain F01', 'The Rocket Bomb Body CBBE'])
            self.write(folder, 2, ['Plain F01', 'CBBE Curvy'])
            left = release_manifests.prune(folder, 2, {'Plain F01'}, self.STOCK)
            self.assertEqual([n for n, _ in left], ['1.json'])
            self.assertEqual(sorted(f.name for f in folder.iterdir()), ['2.json'])

    def test_a_current_build_with_this_machines_presets_is_refused(self):
        import release_manifests
        with tempfile.TemporaryDirectory() as t:
            folder = pathlib.Path(t)
            self.write(folder, 3, ['The Rocket Bomb Body CBBE'])
            with self.assertRaises(SystemExit):
                release_manifests.prune(folder, 3, set(), self.STOCK)
            self.assertTrue((folder / '3.json').exists())


class CommittedPackage(unittest.TestCase):
    def test_the_committed_package_is_a_release(self):
        cat = json.loads((support.PACKAGE / support.CAT).read_text(encoding='utf-8'))
        own = {p['name'] for p in sg.read_presets(support.PACKAGE / sg.PRESETS)}
        self.assertEqual(verify_bodygen.release_problems(cat, own, sg.release_stock()), [])

    def test_the_stock_list_reads(self):
        stock = sg.release_stock()
        self.assertIn('cbbe zeroed sliders', stock)
        self.assertIn('bt - zero', stock)


if __name__ == '__main__':
    unittest.main()
