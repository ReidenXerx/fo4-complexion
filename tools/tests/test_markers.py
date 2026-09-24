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

    def test_an_unreadable_manifest_of_the_output_root_is_refused(self):
        with support.Scratch() as root:
            write_manifest(root / 'out', 5, {'A': 'Silhouette_A'})
            (root / 'data').mkdir()
            (root / 'out' / '9.json').write_text('{"templates": [', encoding='utf-8')
            with self.assertRaises(SystemExit) as caught:
                sg.manifest_history(root / 'out', root / 'data', notes=[])
            self.assertIn('9.json: not a manifest this tool can read', str(caught.exception))
            self.assertIn('restore it (git)', str(caught.exception))

    def test_an_unreadable_manifest_only_the_game_data_holds_is_skipped_and_said(self):
        # Only the mod manager puts files in Data, and the plugin skips such a file too: the package is not at
        # fault, and nothing that reads the history may stop over it (wave 5, lens 3 L3).
        for junk in ('{"templates": [', '[1, 2]', '{"templates": {"Silhouette_B": "junk"}}'):
            with self.subTest(junk=junk), support.Scratch() as root:
                write_manifest(root / 'out', 5, {'A': 'Silhouette_A'})
                write_manifest(root / 'data', 6, {'C': 'Silhouette_C'})
                (root / 'data' / '9.json').write_text(junk, encoding='utf-8')
                notes = []
                history = sg.manifest_history(root / 'out', root / 'data', notes=notes)
                self.assertEqual(sorted(history), ['a', 'c'])
                self.assertEqual(len(notes), 1, notes)
                self.assertIn('9.json: not a manifest this tool can read', notes[0])
                self.assertIn("in the Silhouette mod's staging folder", notes[0])

    def test_a_manifest_that_fails_half_way_adds_nothing(self):
        # Its readable entries are no history: a skipped file is skipped whole.
        with support.Scratch() as root:
            (root / 'out').mkdir()
            (root / 'data').mkdir()
            (root / 'data' / '9.json').write_text(json.dumps({'templates': {'Silhouette_A': {'preset': 'A'},
                                                                            'Silhouette_B': 'junk'}}), encoding='utf-8')
            self.assertEqual(dict(sg.manifest_history(root / 'out', root / 'data', notes=[])), {})

    def test_the_folders_every_reader_takes(self):
        self.assertEqual(sg.manifest_folders('R', 'D'), [sg.pathlib.Path('R') / sg.MANIFESTS,
                                                         sg.pathlib.Path('D') / sg.MANIFESTS])

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

    def test_a_damaged_entry_is_named_never_a_traceback(self):
        # A damaged copy in the game's Data reaches this (wave 5, lens 3 L4).
        self.assertEqual(sg.first_difference({'templates': {'Silhouette_X': 'junk'}}, {}),
                         "the manifest names Silhouette_X ('junk', no body at all), which this run no longer gives")
        self.assertEqual(sg.first_difference({'templates': {'Silhouette_Zeta': 'junk'}}, {'Silhouette_Zeta': entry('Zeta')}),
                         "Silhouette_Zeta ('Zeta'): the manifest holds 'junk' there, not a body")
        damaged = {'templates': {'Silhouette_Zeta': {**entry('Zeta'), 'values': [1, 2]}}}
        self.assertEqual(sg.first_difference(damaged, {'Silhouette_Zeta': entry('Zeta')}),
                         "Silhouette_Zeta ('Zeta'): the manifest's values are [1, 2], not a body's sliders")


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

    def copies(self, out=None, data=None, templates=None):
        """(refusal or None, notes) with these texts as the output root's and Data's copies of stamp 1234."""
        notes = []
        with support.Scratch() as root:
            for folder, text in (('out', out), ('data', data)):
                (root / folder).mkdir()
                if text is not None:
                    (root / folder / '1234.json').write_text(text, encoding='utf-8')
            try:
                sg.refuse_stamp_clash(1234, '0004d2abcdef', templates or self.templates, root / 'out', root / 'data',
                                      notes=notes)
            except SystemExit as exc:
                return str(exc), notes
        return None, notes

    def doc(self, templates):
        return json.dumps({'stamp': 1234, 'build': '0004d2abcdef', 'templates': templates})

    def test_a_damaged_copy_in_data_is_said_never_a_traceback(self):
        # Scenarios H and I of wave 5's lens 3: a truncated file, a list, an entry that is no body.
        for text in ('{"stamp": 1234, "templa', '[1, 2]'):
            with self.subTest(text=text):
                refusal, notes = self.copies(out=self.doc(self.templates), data=text)
                self.assertIsNone(refusal)
                self.assertEqual(len(notes), 1, notes)
                self.assertIn('the next deploy writes this build\'s over it', notes[0])
        refusal, _notes = self.copies(data=self.doc({'Silhouette_CBBE_Curvy': 'junk'}))
        self.assertIn("the manifest holds 'junk' there, not a body", refusal or '')

    def test_a_damaged_copy_in_the_output_root_is_refused(self):
        refusal, _notes = self.copies(out='{"stamp": 12')
        self.assertIn('restore it (git)', refusal or '')
        self.assertIn('Nothing was written', refusal or '')

    def test_copies_that_disagree_are_said_when_the_output_root_agrees_with_this_run(self):
        # Scenario E: whatever case the preset has, one copy disagrees -- "rename it back" could never help.
        refusal, notes = self.copies(out=self.doc(self.templates), data=self.doc({'Silhouette_CBBE_Curvy': entry('cbbe curvy')}))
        self.assertIsNone(refusal)
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('are two manifests of stamp 1234 that differ', notes[0])
        self.assertIn('the next deploy writes it over the one in Data', notes[0])

    def test_the_output_roots_copy_that_disagrees_is_refused_naming_the_copy_that_agrees(self):
        refusal, _notes = self.copies(out=self.doc({'Silhouette_CBBE_Curvy': entry('cbbe curvy')}),
                                      data=self.doc(self.templates))
        self.assertIn('only the case of the name differs, so rename it back', refusal or '')
        self.assertIn("names exactly these bodies: restore the checkout's copy from it", refusal or '')


class MarkerMoves(unittest.TestCase):
    def test_a_marker_that_moves_is_named_with_its_votes(self):
        ps = [{'name': 'ALSL Body 1.0', 'marker': 'Silhouette_ALSL_Body_1_0_74a510'},
              {'name': 'CBBE Curvy', 'marker': 'Silhouette_CBBE_Curvy'}]
        previous = {'alsl body 1.0': 'Silhouette_ALSL_Body_1_0', 'cbbe curvy': 'Silhouette_CBBE_Curvy'}
        history = {'alsl body 1.0': {'Silhouette_ALSL_Body_1_0': 5}}
        self.assertEqual(sg.marker_moves(ps, previous, history),
                         [('ALSL Body 1.0', 'Silhouette_ALSL_Body_1_0', 'Silhouette_ALSL_Body_1_0_74a510', 5, 0)])

    def test_nothing_moves_nothing_is_said(self):
        ps = [{'name': 'CBBE Curvy', 'marker': 'Silhouette_CBBE_Curvy'}, {'name': 'New One', 'marker': 'Silhouette_New_One'}]
        self.assertEqual(sg.marker_moves(ps, {'cbbe curvy': 'Silhouette_CBBE_Curvy'}, {}), [])

    def test_the_build_a_package_holds_now(self):
        with support.Scratch() as root:
            write_manifest(root / 'data' / sg.MANIFESTS, 7, {'A': 'Silhouette_A'})
            (root / 'out' / sg.CATALOG).parent.mkdir(parents=True)
            (root / 'out' / sg.CATALOG).write_text(json.dumps({'stamp': 7}), encoding='utf-8')
            folders = sg.manifest_folders(root / 'out', root / 'data')
            got, where = sg.previous_markers(folders, [root / 'out' / sg.CATALOG, root / 'data' / sg.CATALOG])
            self.assertEqual(got, {'a': 'Silhouette_A'})
            self.assertEqual(where, root / 'data' / sg.MANIFESTS / '7.json')
            self.assertEqual(sg.previous_markers(folders, [root / 'nowhere.json']), ({}, None))


if __name__ == '__main__':
    unittest.main()
