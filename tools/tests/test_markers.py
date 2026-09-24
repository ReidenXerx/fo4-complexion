"""A preset's marker is its bodies' name in every save, so it must go on meaning the preset it always meant
(L4 F2): silhouette_gen.assign_markers with the history of the manifests -- the output root's and the game's
Data's (wave 4 L6) -- and the never-rewrite rule a build meets its own manifest by (L5). Synthetic presets
and manifests in a temporary folder: no game Data needed."""
import copy
import hashlib
import json
import unittest

import support
import silhouette_gen as sg

OLD = ['CBBE Curvy', 'BT - Average', 'Zeta Body']
NEWCOMERS = ['CBBE-Curvy', 'BT_Average']       # the same plain marker as an old one, in another spelling
# The markers spelled out, never derived with the tool under test (a derived one agrees with any break of it).
PLAIN = {'CBBE Curvy': 'Silhouette_CBBE_Curvy', 'BT - Average': 'Silhouette_BT_Average',
         'Zeta Body': 'Silhouette_Zeta_Body'}
WITH_NEWCOMERS = {**PLAIN, 'CBBE-Curvy': 'Silhouette_CBBE_Curvy_849a22', 'BT_Average': 'Silhouette_BT_Average_52cd75'}


def presets(names):
    return [{'name': n} for n in names]


def markers(names, history):
    ps = presets(names)
    sg.assign_markers(ps, history)
    return {p['name']: p['marker'] for p in ps}


def suffixed(name):
    return f'{sg.plain_marker(name)}_{hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]}'


def write_manifest(folder, stamp, marker_of, build=None):
    folder.mkdir(parents=True, exist_ok=True)
    doc = {'stamp': stamp, 'build': build or f'{stamp:06x}000000',
           'templates': {m: {'preset': n, 'gender': 'female', 'values': {}} for n, m in marker_of.items()}}
    (folder / f'{stamp}.json').write_text(json.dumps(doc), encoding='utf-8')


class History(unittest.TestCase):
    def setUp(self):
        self.scratch = support.Scratch()
        self.root = self.scratch.__enter__()
        # Three builds before the newcomers arrived, each recording the old presets' plain markers.
        for stamp in (11, 12, 13):
            write_manifest(self.root / 'repo', stamp, PLAIN)

    def tearDown(self):
        self.scratch.__exit__(None, None, None)

    def history(self, *folders):
        return sg.manifest_history(*(self.root / f for f in folders))

    def test_A1_without_a_newcomer_no_marker_depends_on_the_history(self):
        self.assertEqual(markers(OLD, self.history('repo')), PLAIN)
        self.assertEqual(markers(OLD, {}), PLAIN)

    def test_A2_a_newcomer_never_takes_the_marker_history_gives_another(self):
        self.assertEqual(markers(OLD + NEWCOMERS, self.history('repo')), WITH_NEWCOMERS)

    def test_A2_the_game_data_remembers_what_the_output_root_lost(self):
        # Every manifest deleted here (or a fresh --out) while Data still holds them: nothing moves (L6).
        (self.root / 'repo').rename(self.root / 'data')
        (self.root / 'repo').mkdir()
        self.assertEqual(markers(OLD + NEWCOMERS, self.history('repo', 'data')), WITH_NEWCOMERS)

    def test_A3_the_newest_manifest_alone_keeps_every_marker(self):
        # The build after the newcomers arrived recorded all five; every older manifest is then deleted.
        write_manifest(self.root / 'newest', 14, WITH_NEWCOMERS)
        self.assertEqual(markers(OLD + NEWCOMERS, self.history('newest')), WITH_NEWCOMERS)

    def test_A4_the_order_of_the_presets_does_not_matter(self):
        names = OLD + NEWCOMERS
        for history in (self.history('repo'), {}):
            with self.subTest(history=bool(history)):
                self.assertEqual(markers(list(reversed(names)), history), markers(names, history))

    def test_a_preset_renamed_in_case_only_keeps_its_marker(self):
        got = markers(['cbbe curvy', 'BT - Average', 'Zeta Body'], self.history('repo'))
        self.assertEqual(got['cbbe curvy'], 'Silhouette_CBBE_Curvy')

    def test_a_recorded_marker_that_is_not_the_plain_one_is_kept(self):
        write_manifest(self.root / 'repo', 15, {'Zeta Body': 'Silhouette_Zeta_Body_0a1b2c'})
        write_manifest(self.root / 'repo', 16, {'Zeta Body': 'Silhouette_Zeta_Body_0a1b2c'})
        write_manifest(self.root / 'repo', 17, {'Zeta Body': 'Silhouette_Zeta_Body_0a1b2c'})
        write_manifest(self.root / 'repo', 18, {'Zeta Body': 'Silhouette_Zeta_Body_0a1b2c'})
        # 4 manifests say the suffixed one, 3 the plain one: the plain one is preferred while it is recorded.
        self.assertEqual(markers(OLD, self.history('repo'))['Zeta Body'], 'Silhouette_Zeta_Body')
        other = self.root / 'other'
        write_manifest(other, 21, {'Zeta Body': 'Silhouette_Zeta_Body_0a1b2c'})
        self.assertEqual(markers(OLD, sg.manifest_history(other))['Zeta Body'], 'Silhouette_Zeta_Body_0a1b2c')

    def test_one_marker_recorded_for_two_presets_stays_with_the_one_most_manifests_name(self):
        write_manifest(self.root / 'two', 31, {'Body 1': 'Silhouette_Body_1'})
        write_manifest(self.root / 'two', 32, {'Body 1': 'Silhouette_Body_1'})
        write_manifest(self.root / 'two', 33, {'Body-1': 'Silhouette_Body_1'})
        got = markers(['Body-1', 'Body 1'], self.history('two'))
        self.assertEqual(got['Body 1'], 'Silhouette_Body_1')
        self.assertEqual(got['Body-1'], suffixed('Body-1'))

    def test_a_name_silhouette_reserves_is_never_a_marker(self):
        names = ['Refit', 'chosen', 'BLACKLISTED', 'Unshaped', 'PlayerFemale', 'playermale']
        got = markers(names, {})
        for n in names:
            self.assertEqual(got[n], suffixed(n), n)
        # ...not even when an old manifest recorded one.
        write_manifest(self.root / 'res', 41, {'Refit': 'Silhouette_Refit'})
        self.assertEqual(markers(['Refit'], self.history('res'))['Refit'], suffixed('Refit'))

    def test_a_name_with_nothing_plain_in_it_gets_the_hash(self):
        name = 'Тело'
        self.assertEqual(markers([name], {})[name], f'Silhouette_{hashlib.sha1(name.encode()).hexdigest()[:6]}')

    def test_every_marker_stands_for_one_preset_in_any_case(self):
        # 'CBBE Curvy 849a22' is plainly the marker 'CBBE-Curvy' was given with its hash.
        got = markers(OLD + NEWCOMERS + ['cbbe_curvy', 'Body 1', 'body-1', 'CBBE Curvy 849a22'], self.history('repo'))
        folded = [m.casefold() for m in got.values()]
        self.assertEqual(len(folded), len(set(folded)), got)


class ManifestFiles(unittest.TestCase):
    def test_the_first_folder_wins_a_name_in_any_case(self):
        with support.Scratch() as root:
            write_manifest(root / 'out', 5, {'A': 'Silhouette_A'})
            write_manifest(root / 'data', 5, {'B': 'Silhouette_A'})
            (root / 'data' / '5.json').rename(root / 'data' / '5.JSON')
            write_manifest(root / 'data', 6, {'C': 'Silhouette_C'})
            files = sg.manifest_files(root / 'out', root / 'data', root / 'missing', None)
            self.assertEqual(sorted(files), ['5.json', '6.json'])
            self.assertEqual(files['5.json'].parent.name, 'out')
            self.assertEqual(sorted(sg.manifest_history(root / 'out', root / 'data')), ['a', 'c'])

    def test_a_manifest_that_cannot_be_read_is_refused_in_either_folder(self):
        for where in ('out', 'data'):
            with self.subTest(where=where), support.Scratch() as root:
                write_manifest(root / 'out', 5, {'A': 'Silhouette_A'})
                (root / 'data').mkdir()
                (root / where / '9.json').write_text('{"templates": [', encoding='utf-8')
                with self.assertRaises(SystemExit) as caught:
                    sg.manifest_history(root / 'out', root / 'data')
                self.assertIn('9.json: not a manifest this tool can read', str(caught.exception))

    def test_a_byte_order_mark_is_not_a_new_format(self):
        with support.Scratch() as root:
            write_manifest(root, 5, {'A': 'Silhouette_A'})
            f = root / '5.json'
            f.write_bytes(b'\xef\xbb\xbf' + f.read_bytes())
            self.assertEqual(dict(sg.manifest_history(root)['a']), {'Silhouette_A': 1})


def entry(preset, values=None, gender='female', file='x.xml'):
    return {'preset': preset, 'gender': gender, 'file': file, 'values': dict(values or {'Breasts': 0.5})}


class FirstDifference(unittest.TestCase):
    manifest = {'templates': {'Silhouette_CBBE_Curvy': entry('CBBE Curvy'), 'Silhouette_Zeta': entry('Zeta')}}

    def run_(self, **changes):
        templates = copy.deepcopy(self.manifest['templates'])
        for marker, e in changes.items():
            if e is None:
                del templates[marker]
            else:
                templates[marker] = e
        return sg.first_difference(self.manifest, templates)

    def test_the_same_bodies_whatever_the_descriptions(self):
        self.assertIsNone(self.run_(Silhouette_Zeta=entry('Zeta', file='elsewhere.xml')))
        self.assertTrue(sg.same_bodies(self.manifest, copy.deepcopy(self.manifest['templates'])))

    def test_a_rename_in_case_only_is_named_and_the_way_back_said(self):
        why = self.run_(Silhouette_CBBE_Curvy=entry('CBBE curvy'))
        self.assertEqual(why, "Silhouette_CBBE_Curvy: the manifest says preset 'CBBE Curvy', this run 'CBBE curvy' -- "
                              "only the case of the name differs, so rename it back")
        self.assertFalse(sg.same_bodies(self.manifest, {**self.manifest['templates'],
                                                        'Silhouette_CBBE_Curvy': entry('CBBE curvy')}))

    def test_another_name(self):
        self.assertEqual(self.run_(Silhouette_Zeta=entry('Zeta 2')),
                         "Silhouette_Zeta: the manifest says preset 'Zeta', this run 'Zeta 2' -- rename it back")

    def test_another_sex_and_other_values(self):
        self.assertEqual(self.run_(Silhouette_Zeta=entry('Zeta', gender='male')),
                         "Silhouette_Zeta ('Zeta'): the manifest says female, this run male")
        self.assertEqual(self.run_(Silhouette_Zeta=entry('Zeta', {'Breasts': 0.6})),
                         "Silhouette_Zeta ('Zeta'): Breasts is 0.5 in the manifest, 0.6 in this run")

    def test_a_body_more_or_less(self):
        self.assertEqual(self.run_(Silhouette_New=entry('New')),
                         "this run gives Silhouette_New ('New'), which the manifest does not name")
        self.assertEqual(self.run_(Silhouette_Zeta=None),
                         "the manifest names Silhouette_Zeta ('Zeta'), which this run no longer gives")

    def test_a_manifest_of_no_known_shape(self):
        for manifest in ([], {'templates': []}, {}):
            with self.subTest(manifest=manifest):
                self.assertEqual(sg.first_difference(manifest, self.manifest['templates']),
                                 'the manifest names no bodies it can be compared by')


class StampClash(unittest.TestCase):
    templates = {'Silhouette_CBBE_Curvy': entry('CBBE Curvy')}

    def clash(self, folder, build, templates=None):
        with support.Scratch() as root:
            (root / 'out').mkdir()
            where = root / folder
            where.mkdir(exist_ok=True)
            (where / '1234.json').write_text(json.dumps({'stamp': 1234, 'build': build, 'templates': self.templates}),
                                             encoding='utf-8')
            try:
                sg.refuse_stamp_clash(1234, '0004d2abcdef', templates or self.templates, root / 'out', root / 'data')
            except SystemExit as exc:
                return str(exc)
        return None

    def test_another_build_with_this_stamp_is_refused_in_the_output_root_and_in_data(self):
        for folder in ('out', 'data'):
            with self.subTest(folder=folder):
                self.assertIn('and so has build 0004d2000000', self.clash(folder, '0004d2000000') or '')

    def test_this_build_with_other_bodies_is_refused_with_the_first_difference(self):
        for folder in ('out', 'data'):
            with self.subTest(folder=folder):
                msg = self.clash(folder, '0004d2abcdef', {'Silhouette_CBBE_Curvy': entry('CBBE curvy')}) or ''
                self.assertIn("only the case of the name differs, so rename it back", msg)
                self.assertIn('A manifest is never rewritten, and nothing was written', msg)
                self.assertIn('change anything in the presets or the ranges to get a new build', msg)

    def test_this_build_again_with_the_same_bodies_goes_ahead(self):
        for folder in ('out', 'data'):
            with self.subTest(folder=folder):
                self.assertIsNone(self.clash(folder, '0004d2abcdef'))

    def test_no_manifest_of_this_stamp_anywhere(self):
        with support.Scratch() as root:
            self.assertIsNone(sg.refuse_stamp_clash(1234, '0004d2abcdef', self.templates, root / 'a', root / 'b'))


if __name__ == '__main__':
    unittest.main()
