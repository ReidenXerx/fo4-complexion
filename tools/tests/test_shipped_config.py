"""tools/silhouette_gen.py: the package ships the config it was made from, and never replaces one it did not
read (owner, 2026-09-24; wave 4 L8)."""
import unittest

import support
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


if __name__ == '__main__':
    unittest.main()
