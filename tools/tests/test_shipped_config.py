"""tools/silhouette_gen.py: the package ships the config it was made from, and never replaces one it did not
read (owner, 2026-09-24; wave 4 L8)."""
import json
import unittest

import support
import rules
import silhouette_gen


def refusal(out_cfg, cfg_file):
    """The message refuse_foreign_config() refuses with -- None when the run may go on."""
    try:
        silhouette_gen.refuse_foreign_config(out_cfg, cfg_file)
    except SystemExit as exc:
        return str(exc)
    return None


class ShippedConfig(unittest.TestCase):
    def test_a_root_without_a_config_takes_the_compiled_one(self):
        with support.Scratch() as root:
            cfg = root / 'mine.json'
            cfg.write_text('{"a": 1}', encoding='utf-8')
            self.assertIsNone(refusal(root / 'out/config.json', cfg))
            self.assertIsNone(refusal(root / 'out/config.json', root / 'absent.json'))

    def test_the_roots_own_config_when_that_is_what_was_compiled(self):
        with support.Scratch() as root:
            cfg = root / 'config.json'
            cfg.write_text('{"a": 1}', encoding='utf-8')
            self.assertIsNone(refusal(cfg, cfg))

    def test_a_copy_of_the_compiled_config(self):
        with support.Scratch() as root:
            cfg, out = root / 'mine.json', root / 'config.json'
            cfg.write_text('{"a": 1}', encoding='utf-8')
            out.write_bytes(cfg.read_bytes())
            self.assertIsNone(refusal(out, cfg))

    def test_another_config_in_the_root_is_refused_not_replaced(self):
        with support.Scratch() as root:
            cfg, out = root / 'mine.json', root / 'config.json'
            cfg.write_text('{"a": 1}', encoding='utf-8')
            out.write_text('{"a": 2}', encoding='utf-8')
            msg = refusal(out, cfg)
            self.assertIsNotNone(msg)
            self.assertIn(f'--config {out}', msg)
            self.assertIn('Nothing was written', msg)
            self.assertEqual(out.read_text(encoding='utf-8'), '{"a": 2}')

    def test_a_config_in_the_root_when_only_the_defaults_were_compiled(self):
        with support.Scratch() as root:
            out = root / 'config.json'
            out.write_text('{"a": 2}', encoding='utf-8')
            msg = refusal(out, root / 'absent.json')
            self.assertIsNotNone(msg)
            self.assertIn('every key at its default', msg)

    def test_the_defaults_written_out_are_the_defaults_compiled(self):
        with support.Scratch() as root:
            out = root / 'config.json'
            rules.write_default(out)
            self.assertIsNone(refusal(out, root / 'absent.json'))

    def test_the_same_config_in_another_layout_is_no_hand_edit(self):
        # git's autocrlf, an editor's indent: the same settings are the same config (wave 5, lens 3 N12).
        with support.Scratch() as root:
            cfg, out = root / 'mine.json', root / 'config.json'
            cfg.write_bytes(b'{\r\n  "a": 1,\r\n  "b": [1, 2]\r\n}\r\n')
            out.write_bytes(b'{"b": [1, 2], "a": 1}\n')
            self.assertIsNone(refusal(out, cfg))

    def test_the_refusal_names_the_first_setting_that_differs(self):
        with support.Scratch() as root:
            cfg, out = root / 'mine.json', root / 'config.json'
            cfg.write_text('{"a": 1, "b": 2, "c": 3}', encoding='utf-8')
            out.write_text('{"a": 1, "b": 5, "c": 4}', encoding='utf-8')
            self.assertIn(f"'b' is 5 there and 2 in {cfg}", refusal(out, cfg) or '')
            out.write_text('{"a": 1, "b": ', encoding='utf-8')
            self.assertIn('it is not a JSON object like the one compiled', refusal(out, cfg) or '')


class ShippedWithEveryKey(unittest.TestCase):
    """S-61: the package's config lists every key, written out -- a key added to the defaults and not to the
    shipped file would ship missing with every other test green (wave 5, lens 3 N13)."""

    def test_the_shipped_config_holds_exactly_the_default_keys(self):
        shipped = json.loads((support.PACKAGE / 'F4SE/Plugins/Silhouette' / rules.CONFIG_NAME).read_text(encoding='utf-8-sig'))
        self.assertEqual(sorted(shipped), sorted(rules.DEFAULT))

    def test_the_shipped_config_loads(self):
        report = []
        cfg = rules.load(support.PACKAGE / 'F4SE/Plugins/Silhouette' / rules.CONFIG_NAME, [], report)
        self.assertEqual(sorted(cfg), sorted(rules.DEFAULT))


if __name__ == '__main__':
    unittest.main()
