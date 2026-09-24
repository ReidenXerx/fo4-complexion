"""plugin_forms.editor_ids reads EVERY top group of a type: Fallout4.esm has two of NPC_, LVLN, WEAP and eleven
more, and reading only the first loses Piper, Preston and a third of the game's NPCs."""
import struct
import unittest

import support
import plugin_forms


def field(sig, data):
    return sig + struct.pack('<H', len(data)) + data


def record(rtype, form_id, edid):
    data = field(b'EDID', edid.encode('ascii') + b'\0')
    return rtype + struct.pack('<IIIIHH', len(data), 0, form_id, 0, 131, 0) + data


def group(label, *records):
    body = b''.join(records)
    return b'GRUP' + struct.pack('<I', 24 + len(body)) + label + struct.pack('<iII', 0, 0, 0) + body


def plugin(*groups):
    head = field(b'HEDR', struct.pack('<fII', 1.0, 0, 0))
    return b'TES4' + struct.pack('<IIIIHH', len(head), 0, 0, 0, 131, 0) + head + b''.join(groups)


class TwoTopGroups(unittest.TestCase):
    def test_both_groups_of_a_type_are_read(self):
        with support.Scratch() as root:
            p = root / 'Two.esm'
            p.write_bytes(plugin(group(b'NPC_', record(b'NPC_', 0x800, 'First')),
                                 group(b'FACT', record(b'FACT', 0x900, 'AFaction')),
                                 group(b'NPC_', record(b'NPC_', 0x2F1E, 'CompanionPiper'))))
            self.assertEqual(plugin_forms.editor_ids(p, 'NPC_'),
                             {'First': ('Two.esm', 0x800), 'CompanionPiper': ('Two.esm', 0x2F1E)})
            self.assertEqual(plugin_forms.editor_ids(p, 'FACT'), {'AFaction': ('Two.esm', 0x900)})


if __name__ == '__main__':
    unittest.main()
