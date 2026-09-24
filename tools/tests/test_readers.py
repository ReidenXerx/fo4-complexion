"""Two readers of what the game holds: the census takes the game's copy of a manifest over this checkout's (the game
reads Data's), and a race only a plugin enables says where the load order was looked for -- under Mod Organizer
there is no plugins.txt where this tool looks, and "enable it" would be wrong advice (wave 5, lens 3 N14)."""
import json
import unittest
from unittest import mock

import support
import catalog
import cosave_census


class CensusManifests(unittest.TestCase):
    def test_the_game_datas_copy_wins(self):
        with support.Scratch() as root:
            for folder, preset in (('data', 'as deployed'), ('repo', 'as in the checkout')):
                (root / folder).mkdir()
                (root / folder / '5.json').write_text(json.dumps({'stamp': 5, 'templates': {'M': {'preset': preset}}}),
                                                      encoding='utf-8')
            with mock.patch.object(cosave_census, 'MANIFESTS', [root / 'data', root / 'repo']):
                got = cosave_census.manifests()
        self.assertEqual(got[5]['templates']['M']['preset'], 'as deployed')


class RaceNotLoaded(unittest.TestCase):
    def refusal(self, txt):
        with mock.patch.object(catalog, 'plugins_txt', return_value=txt), \
                mock.patch.object(catalog.plugin_forms, 'resolve', return_value={}), \
                mock.patch.object(catalog.plugin_forms, 'find_inactive', return_value={'LykaiosRace': 'Lykaios.esp'}):
            with self.assertRaises(SystemExit) as caught:
                catalog.resolve_races({'distributeRaces': ['LykaiosRace']}, support.REPO, [])
        return str(caught.exception)

    def test_with_a_plugins_txt_the_plugin_is_not_enabled(self):
        with support.Scratch() as root:
            txt = root / 'plugins.txt'
            txt.write_text('*Fallout4.esm\n', encoding='utf-8')
            msg = self.refusal(txt)
        self.assertIn(f'which is not active in the load order in {txt} -- enable it', msg)

    def test_without_one_it_may_be_enabled_where_this_tool_did_not_look(self):
        for txt in (None, support.REPO / 'no' / 'plugins.txt'):
            with self.subTest(txt=txt):
                msg = self.refusal(txt)
                self.assertIn('no plugins.txt was found', msg)
                self.assertIn('Under Mod Organizer, run this from Mod Organizer', msg)
                self.assertNotIn('which is not active', msg)


if __name__ == '__main__':
    unittest.main()
