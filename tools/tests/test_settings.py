"""tools/verify_bodygen.py reads settings.ini as MCM types it -- by each key's first letter: i a whole number, b 0 or
1, f any number, s text (wave 5, lens 3 L9). Other mods in this Data ship fGlobal=1.0 and sGoodConditionColor=666666:
reading every key as a whole number would fail the first float setting Silhouette ever adds."""
import unittest

import support
import verify_bodygen


def parse(text):
    problems = []
    defaults, build = verify_bodygen.parse_settings(text, problems)
    return defaults, build, problems


class Settings(unittest.TestCase):
    def test_each_type_by_its_letter(self):
        defaults, build, problems = parse('[General]\niCount=3\nbOn=1\nfScale=0.5\nsColor=666666\nsBuild=abc\n')
        self.assertEqual(problems, [])
        self.assertEqual(defaults, {'iCount:General': 3, 'bOn:General': 1, 'fScale:General': 0.5,
                                    'sColor:General': '666666'})
        self.assertEqual(build, 'abc')

    def test_a_value_mcm_cannot_read_as_its_type(self):
        for line, words in (('iCount=0.5', 'iCount=0.5: not a whole number'), ('bOn=2', 'bOn=2: not 0 or 1'),
                            ('bOn=yes', 'bOn=yes: not 0 or 1'), ('fScale=half', 'fScale=half: not a number')):
            with self.subTest(line=line):
                defaults, _build, problems = parse(f'[General]\n{line}\n')
                self.assertEqual(defaults, {})
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(words, problems[0])
                self.assertIn('MCM would read the setting as 0', problems[0])

    def test_a_key_with_no_type_letter(self):
        _d, _b, problems = parse('[General]\nCount=3\n')
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('MCM types a setting by its first letter', problems[0])

    def test_comments_and_sections(self):
        defaults, _b, problems = parse('; a comment = with an equals sign\n[Meta]\niDefaults=1\n')
        self.assertEqual((defaults, problems), ({'iDefaults:Meta': 1}, []))

    def test_the_committed_settings_read_clean(self):
        text = (support.PACKAGE / support.MCM / 'settings.ini').read_text(encoding='utf-8-sig')
        defaults, build, problems = parse(text)
        self.assertEqual(problems, [])
        self.assertEqual(defaults.get('iDefaults:Meta'), 1)
        self.assertTrue(build)


if __name__ == '__main__':
    unittest.main()
