"""The protocol the DLL speaks and the one its scripts expect are one number, written in three places:
Papyrus.cpp's kProtocol, Silhouette:Bridge's Protocol property and Silhouette:API.Protocol(). S-68 moved two
of them to 4 and left the API at 3, so API.Loaded() said False to every mod asking -- found by fo4-mcp's pack,
not by a test. Now a test."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def number(path, pattern):
    text = (ROOT / path).read_text(encoding='utf-8')
    found = re.findall(pattern, text, re.MULTILINE)
    if len(found) != 1:
        raise AssertionError(f'{path}: expected one match of {pattern!r}, found {len(found)}')
    return int(found[0])


class Protocol(unittest.TestCase):
    def test_the_dll_and_both_scripts_speak_one_protocol(self):
        dll = number('src/Papyrus.cpp', r'^\s*constexpr std::int32_t kProtocol = (\d+);')
        bridge = number('papyrus/Silhouette/Bridge.psc', r'^Int Property Protocol = (\d+) AutoReadOnly')
        api = number('papyrus/Silhouette/API.psc', r'^Int Function Protocol\(\) Global\s*\n\s*Return (\d+)')
        self.assertEqual((bridge, api), (dll, dll), f'DLL {dll}, Bridge {bridge}, API {api}')


if __name__ == '__main__':
    unittest.main()
