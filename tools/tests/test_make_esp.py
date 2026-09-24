"""tools/make_esp.py: check() refuses a Silhouette.esp the plugin, its scripts and LooksMenu cannot live with --
first of all one without the refit keyword, which would move every refit value into a body for good (S-40)."""
import struct
import subprocess
import sys
import unittest

import support
import make_esp


class Check(unittest.TestCase):
    def check(self, blob):
        with support.Scratch() as root:
            esp = root / 'Silhouette.esp'
            esp.write_bytes(blob)
            return make_esp.check(esp)

    def test_what_build_writes_passes(self):
        self.assertEqual(self.check(make_esp.build()), [])

    def test_the_committed_esp_is_what_build_writes(self):
        self.assertEqual((support.PACKAGE / 'Silhouette.esp').read_bytes(), make_esp.build())

    def test_an_esp_without_the_refit_keyword_is_refused_first(self):
        problems = self.check(support.esp_without(make_esp.build(), make_esp.REFIT_FORMID))
        self.assertTrue(problems)
        self.assertIn('no refit keyword (KYWD 0x803)', problems[0])
        self.assertIn('into her own body at the next load, for good', problems[0])

    def test_the_phase_1_esp_is_refused(self):
        # What the game ran before Silhouette 2: no keyword, no list of who the window healed.
        problems = self.check(support.esp_without(make_esp.build(), make_esp.REFIT_FORMID, make_esp.HEALED_FORMID))
        self.assertEqual(len(problems), 2)
        self.assertIn('no refit keyword', problems[0])
        self.assertIn('no FLST 804', problems[1])

    def test_each_quest_and_list_is_required(self):
        for form_id, words in ((make_esp.QUEST_FORMID, 'no QUST 800 (the regeneration window)'),
                               (make_esp.SEEN_FORMID, 'no FLST 801'), (make_esp.BRIDGE_FORMID, 'no QUST 802 (the bridge)'),
                               (make_esp.HEALED_FORMID, 'no FLST 804')):
            with self.subTest(form_id=f'{form_id:08X}'):
                problems = self.check(support.esp_without(make_esp.build(), form_id))
                self.assertTrue(any(words in p for p in problems), problems)

    def test_an_esp_not_flagged_light_is_refused(self):
        blob = bytearray(make_esp.build())
        (flags,) = struct.unpack_from('<I', blob, 8)
        struct.pack_into('<I', blob, 8, flags & ~make_esp.TES4_LIGHT)
        self.assertTrue(any('not flagged light' in p for p in self.check(bytes(blob))))

    def test_what_is_no_plugin_is_refused_not_a_crash(self):
        for blob in (b'', b'not a plugin at all', make_esp.build()[:30]):
            with self.subTest(blob=blob[:12]):
                problems = self.check(blob)
                self.assertTrue(problems)

    def test_the_command_line_refuses_with_exit_1(self):
        with support.Scratch() as root:
            good, bad = root / 'good.esp', root / 'bad.esp'
            good.write_bytes(make_esp.build())
            bad.write_bytes(support.esp_without(make_esp.build(), make_esp.REFIT_FORMID))
            tool = str(support.TOOLS / 'make_esp.py')
            ok = subprocess.run([sys.executable, tool, '--check', str(good)], capture_output=True, text=True,
                                env=support.ENV)
            no = subprocess.run([sys.executable, tool, '--check', str(bad)], capture_output=True, text=True,
                                env=support.ENV)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(no.returncode, 1, no.stdout + no.stderr)
        self.assertIn('REFUSED', no.stdout)
        self.assertIn('no refit keyword', no.stdout)


if __name__ == '__main__':
    unittest.main()
