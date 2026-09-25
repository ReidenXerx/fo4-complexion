"""S-72: each faction's own body pool, ten bodies per sex in the faction's look, drawn by the faction's rule.

What ships: the sidecar and the XML are of one run; every faction has 6 plain, 3 rough and 1 fine body per sex;
no woman is below the bust floor (S-65). The rules: each faction's rule lists every body as many times as its
tier weighs (69 / 23 / 8), a user's rule for the faction wins, the gangs come before the raiders, and the catalog
keeps the repeats. With the game's Data: every body still measures as its tier, and every faction is there."""
import collections
import json
import sys
import unittest

import support
import silhouette_gen as sg

sys.path.insert(0, str(support.TOOLS / 'pool'))
import factions  # noqa: E402

XML = support.PACKAGE / sg.PRESETS / 'Silhouette Factions.xml'


def side():
    return json.loads(sg.FACTIONS_SIDECAR.read_text(encoding='utf-8'))


class CommittedFactions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.side = side()
        with support.Scratch() as root:
            (root / XML.name).write_bytes(XML.read_bytes())
            cls.xml = {p['name']: p for p in sg.read_presets(root)}

    def test_the_xml_holds_every_body_of_the_sidecar_with_its_values(self):
        self.assertEqual(set(self.side['presets']), set(self.xml))
        for name, p in self.side['presets'].items():
            got = {s: round(v * 100) for s, v in self.xml[name]['sliders'].items() if v}
            self.assertEqual(got, {s: v for s, v in p['values'].items() if v}, name)

    def test_every_faction_has_six_plain_three_rough_one_fine_per_sex(self):
        counts = collections.Counter((p['faction'], p['sex'], p['tier']) for p in self.side['presets'].values())
        for key in factions.FACTIONS:
            for sex in ('female', 'male'):
                with self.subTest(f'{key} {sex}'):
                    self.assertEqual({t: counts[(key, sex, t)] for t in factions.COUNTS}, factions.COUNTS)

    def test_no_faction_woman_is_below_the_bust_floor(self):
        for name, p in self.side['presets'].items():
            if p['sex'] == 'female':
                with self.subTest(name):
                    self.assertGreaterEqual(p['values'].get('Breasts', 0), 0)
                    self.assertLessEqual(p['values'].get('BreastsSmall', 0), 30)

    def test_no_faction_range_can_draw_below_the_floor(self):
        for key in factions.FACTIONS:
            for tier, arcs in factions.archetypes_of(key, 'female').items():
                for label, (_count, ranges) in arcs.items():
                    with self.subTest(f'{key} {tier} {label}'):
                        self.assertGreaterEqual(ranges.get('Breasts', (0, 0))[0], 0)
                        self.assertLessEqual(ranges.get('BreastsSmall', (0, 0))[1], 30)

    def test_names_say_faction_tier_and_sex(self):
        for name, p in self.side['presets'].items():
            tag = self.side['factions'][p['faction']]['tag']
            letter = 'F' if p['sex'] == 'female' else 'M'
            self.assertRegex(name, rf'^{tag} {factions.TIER_NAME[p["tier"]]} {letter}\d\d$')


class Rules(unittest.TestCase):

    def test_each_rule_weighs_its_tiers_as_the_main_pool(self):
        cfg = {}
        added, kept = sg.merge_factions(cfg)
        self.assertEqual(kept, [])
        s = side()
        wanted = sum(len(f['factions']) for f in s['factions'].values()) * 2
        self.assertEqual(added, wanted)
        for key in ('factionFemale', 'factionMale'):
            for edid, names in cfg[key].items():
                with self.subTest(f'{key} {edid}'):
                    tiers = collections.Counter(s['presets'][n]['tier'] for n in names)
                    self.assertEqual(len(names), 26)
                    self.assertEqual(dict(tiers), {'middle': 18, 'ugly': 6, 'beautiful': 2})

    def test_a_users_rule_for_the_faction_wins(self):
        cfg = {'factionFemale': {'gunnerfaction': ['Mine']}}
        _added, kept = sg.merge_factions(cfg)
        self.assertEqual(cfg['factionFemale']['gunnerfaction'], ['Mine'])
        self.assertNotIn('GunnerFaction', cfg['factionFemale'])
        self.assertIn('GunnerFaction (female)', kept)
        self.assertIn('GunnerFaction', cfg['factionMale'])

    def test_the_gangs_come_before_the_raiders(self):
        cfg = {}
        sg.merge_factions(cfg)
        order = list(cfg['factionFemale'])
        for gang in ('DLC04GangDisciplesFaction', 'DLC04GangOperatorsFaction', 'DLC04GangPackFaction', 'TriggermanFaction'):
            self.assertLess(order.index(gang), order.index('RaiderFaction'), gang)

    def test_the_catalog_marks_the_pools_and_only_them(self):
        # S-73: MCM's "Faction bodies" leaves out the rules marked as Silhouette's own pools, never a user's.
        cat = json.loads((support.PACKAGE / support.CAT).read_text(encoding='utf-8'))
        ours = {f[1].casefold() for f in (x for v in side()['factions'].values() for x in v['factions'])}
        for r in cat['rules']['faction']:
            with self.subTest(f'{r["editorID"]} {r["sex"]}'):
                self.assertEqual(r.get('pool', False), r['editorID'].casefold() in ours)

    def test_the_menu_has_the_switches_with_their_defaults_on(self):
        mcm = support.PACKAGE / 'MCM/Config/Silhouette'
        cfg = json.loads((mcm / 'config.json').read_text(encoding='utf-8-sig'))
        ids = {c.get('id') for p in cfg['pages'] for c in p['content'] if c.get('type') == 'switcher'}
        ini = (mcm / 'settings.ini').read_text(encoding='utf-8-sig')
        for key in ('bFreshStart', 'bFactionPools', 'bNotices'):
            with self.subTest(key):
                self.assertIn(f'{key}:General', ids)
                self.assertIn(f'{key}=1', ini)

    def test_the_shipped_catalog_keeps_the_repeats(self):
        cat = json.loads((support.PACKAGE / support.CAT).read_text(encoding='utf-8'))
        rules = [r for r in cat['rules']['faction'] if r['editorID'] == 'GunnerFaction']
        self.assertEqual(len(rules), 2)
        for r in rules:
            self.assertEqual(len(r['presets']), 26, r['sex'])
            self.assertEqual(len(set(r['presets'])), 10, r['sex'])


@support.needs_data
class StillTheirTiers(unittest.TestCase):

    def test_every_body_measures_as_its_tier_and_every_faction_is_there(self):
        self.assertEqual(factions.check(support.game_data()), 0)


if __name__ == '__main__':
    unittest.main()
