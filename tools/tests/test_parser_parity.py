"""catalog.check() against the plugin's own parser (SilhouetteTests.exe --check, src/Catalog.cpp ParseCatalog),
key by key and shape by shape: a catalog check() lets through and the game refuses is a Silhouette that does
nothing, found only in the game.

Each case doctors a copy of the committed catalog.json, runs --check on a copy of the committed package holding
it, and check() on the same document. check() may refuse MORE than the parser -- what the parser would accept
but could never mean -- only in the cases listed in STRICTER, each on purpose.
"""
import concurrent.futures
import copy
import json
import shutil
import subprocess
import unittest

import support
import catalog

ACCEPT = {'p0', 'S9', 'P33', 'PL8', 'R27', 'O31', 'O33', 'O35', 'O36', 'O37'}
# check() refuses, the parser takes: a key it would silently ignore (T22), a sex's list left out (S7), a value
# that is float32's largest only by rounding (P20), a player default naming no preset (PL7), and a range one
# float32 cannot tell from nothing (V7, V16).
STRICTER = {'T22', 'S7', 'P20', 'PL7', 'V7', 'V16'}
# The catalog parses; --check then finds the manifest does not name the preset the case added or renamed.
MANIFEST = {'P31', 'P34'}


def first(doc, sex):
    return next(p for p in doc['presets'] if p['sex'] == sex)


def fset(doc):
    return doc['orefit']['sets'][0]


def vf(doc):
    return doc['variety']['female'][0]


def one_value(doc, v):
    values = first(doc, 'female')['values']
    values[next(iter(values))] = v


def rule(doc, key, sex='female', **e):
    doc['rules'][key].append({'sex': sex, 'presets': [first(doc, 'female')['name']], **e})


class Raw(str):
    """What a case writes as the whole file instead of the document."""


# (id, what, edit): edit changes the document in place (what it returns is ignored), or returns Raw text.
CASES = [
    ('p0', 'untouched', lambda d: None),
    # ---- top level
    ('T1', 'schema missing', lambda d: d.pop('schema')),
    ('T2', 'schema 2', lambda d: d.update(schema=2)),
    ('T3', 'schema "1"', lambda d: d.update(schema='1')),
    ('T4', 'schema 1.0', lambda d: d.update(schema=1.0)),
    ('T5', 'schema true', lambda d: d.update(schema=True)),
    ('T6', 'build missing', lambda d: d.pop('build')),
    ('T7', 'build a number', lambda d: d.update(build=5)),
    ('T8', 'stamp missing', lambda d: d.pop('stamp')),
    ('T9', 'stamp 0', lambda d: d.update(stamp=0)),
    ('T10', 'stamp 2^24', lambda d: d.update(stamp=1 << 24)),
    ('T11', 'stamp -1', lambda d: d.update(stamp=-1)),
    ('T12', 'stamp 1.5', lambda d: d.update(stamp=1.5)),
    ('T13', 'stamp "5"', lambda d: d.update(stamp='5')),
    ('T14', 'stamp true', lambda d: d.update(stamp=True)),
    ('T15', 'mode missing', lambda d: d.pop('mode')),
    ('T16', 'mode null', lambda d: d.update(mode=None)),
    ('T17', 'rulesHash missing', lambda d: d.pop('rulesHash')),
    ('T18', 'rulesHash ""', lambda d: d.update(rulesHash='')),
    ('T19', 'rulesHash a number', lambda d: d.update(rulesHash=5)),
    ('T20', 'the top level a list', lambda d: Raw('[1]')),
    ('T21', 'NaN in an unknown top-level key', lambda d: d.update(x=float('nan'))),
    ('T22', '1e39 in an unknown top-level key', lambda d: d.update(x=1e39)),
    ('T23', 'a lone surrogate in an unknown top-level key', lambda d: d.update(x='\ud800')),
    # ---- states / neverInBody
    ('S1', 'states missing', lambda d: d.pop('states')),
    ('S2', 'states a list', lambda d: d.update(states=[])),
    ('S3', 'states: an unknown key', lambda d: d['states'].update(other=[])),
    ('S4', 'states.female not a list', lambda d: d['states'].update(female='Erection')),
    ('S5', 'states.female holds a number', lambda d: d['states']['female'].append(5)),
    ('S6', 'a state missing from neverInBody',
     lambda d: d['neverInBody'].update(male=[m for m in d['neverInBody']['male'] if m != 'Erection'])),
    ('S7', 'states without "female"', lambda d: d['states'].pop('female')),
    ('S8', 'neverInBody: an unknown key', lambda d: d['neverInBody'].update(other=[])),
    ('S9', 'a state in neverInBody in another case',
     lambda d: d['neverInBody'].update(male=['erection' if m == 'Erection' else m for m in d['neverInBody']['male']])),
    # ---- presets
    ('P1', 'presets missing', lambda d: d.pop('presets')),
    ('P2', 'presets an object', lambda d: d.update(presets={})),
    ('P3', 'a preset that is a string', lambda d: d['presets'].append('x')),
    ('P4', 'a preset without a name', lambda d: first(d, 'female').pop('name')),
    ('P5', 'a preset name a number', lambda d: first(d, 'female').update(name=5)),
    ('P6', 'sex "Female"', lambda d: first(d, 'female').update(sex='Female')),
    ('P7', 'a preset without a marker', lambda d: first(d, 'female').pop('marker')),
    ('P8', 'marker "Silhouette_"', lambda d: first(d, 'female').update(marker='Silhouette_')),
    ('P9', 'a marker without the prefix', lambda d: first(d, 'female').update(marker='Body_1')),
    ('P10', 'marker Silhouette_Refit', lambda d: first(d, 'female').update(marker='Silhouette_Refit')),
    ('P11', 'marker Silhouette_Chosen', lambda d: first(d, 'female').update(marker='Silhouette_Chosen')),
    ('P12', 'marker silhouette_blacklisted', lambda d: first(d, 'female').update(marker='silhouette_blacklisted')),
    ('P13', 'two presets, one marker in another case',
     lambda d: d['presets'][1].update(marker=d['presets'][0]['marker'].upper())),
    ('P14', 'values a list', lambda d: first(d, 'female').update(values=[])),
    ('P15', 'values hold Erection', lambda d: first(d, 'female')['values'].update(Erection=1.0)),
    ('P16', 'values hold "penis width"', lambda d: first(d, 'male')['values'].update({'penis width': 1.0})),
    ('P17', 'a value "0.5"', lambda d: one_value(d, '0.5')),
    ('P18', 'a value NaN', lambda d: one_value(d, float('nan'))),
    ('P19', 'a value 1e39', lambda d: one_value(d, 1e39)),
    ('P20', 'a value 3.4028235e38 (float32\'s largest by rounding)', lambda d: one_value(d, 3.4028235e38)),
    ('P21', 'a value 10**40 as an integer', lambda d: one_value(d, 10 ** 40)),
    ('P22', 'random missing', lambda d: first(d, 'female').pop('random')),
    ('P23', 'random "true"', lambda d: first(d, 'female').update(random='true')),
    ('P24', 'menu 1', lambda d: first(d, 'female').update(menu=1)),
    ('P25', 'zeroed missing', lambda d: first(d, 'female').pop('zeroed')),
    ('P26', 'fit missing', lambda d: first(d, 'female').pop('fit')),
    ('P27', 'fit null', lambda d: first(d, 'female').update(fit=None)),
    ('P28', 'family missing', lambda d: first(d, 'female').pop('family')),
    ('P29', 'family a number', lambda d: first(d, 'female').update(family=5)),
    ('P30', 'one name twice for one sex, in another case',
     lambda d: d['presets'].append({**copy.deepcopy(first(d, 'female')), 'name': first(d, 'female')['name'].upper(),
                                    'marker': 'Silhouette_Probe_Dup'})),
    ('P31', 'one name for both sexes',
     lambda d: d['presets'].append({**copy.deepcopy(first(d, 'male')), 'name': first(d, 'female')['name'],
                                    'marker': 'Silhouette_Probe_Both'})),
    ('P32', 'a morph named with a lone surrogate', lambda d: first(d, 'female')['values'].update({'\udc00': 1.0})),
    ('P33', 'a morph named ""', lambda d: first(d, 'female')['values'].update({'': 1.0})),
    ('P34', 'a preset name ""', lambda d: first(d, 'female').update(name='')),
    # ---- player
    ('PL1', 'player missing', lambda d: d.pop('player')),
    ('PL2', 'player a list', lambda d: d.update(player=[])),
    ('PL3', 'player: an unknown key', lambda d: d['player'].update(other=d['player']['female'])),
    ('PL4', 'player.female a number', lambda d: d['player'].update(female=5)),
    ('PL5', 'player names no preset', lambda d: d['player'].update(female='No Such Preset')),
    ('PL6', 'player.female names a male preset', lambda d: d['player'].update(female=first(d, 'male')['name'])),
    ('PL7', 'player.female ""', lambda d: d['player'].update(female='')),
    ('PL8', 'player.female in another case', lambda d: d['player'].update(female=d['player']['female'].upper())),
    # ---- variety
    ('V1', 'variety missing', lambda d: d.pop('variety')),
    ('V2', 'variety: an unknown key', lambda d: d['variety'].update(other=[])),
    ('V3', 'variety.female an object', lambda d: d['variety'].update(female={})),
    ('V4', 'a variety entry without a morph', lambda d: vf(d).pop('morph')),
    ('V5', 'low and high "0" and "1"', lambda d: vf(d).update(low='0', high='1')),
    ('V6', 'low above high', lambda d: vf(d).update(low=0.5, high=0.1)),
    ('V7', 'low == high', lambda d: vf(d).update(low=0.3, high=0.3)),
    ('V8', 'group "other"', lambda d: vf(d).update(group='other')),
    ('V9', 'a variety morph Erection', lambda d: vf(d).update(morph='Erection')),
    ('V10', 'one variety morph twice, in another case',
     lambda d: d['variety']['female'].append({**copy.deepcopy(vf(d)), 'morph': vf(d)['morph'].upper()})),
    ('V11', 'low NaN', lambda d: vf(d).update(low=float('nan'))),
    ('V12', 'high 1e39', lambda d: vf(d).update(high=1e39)),
    ('V13', 'a variety morph a number', lambda d: vf(d).update(morph=5)),
    ('V14', 'group missing', lambda d: vf(d).pop('group')),
    ('V15', 'high 10**40 as an integer', lambda d: vf(d).update(high=10 ** 40)),
    ('V16', 'low 0.1, high 0.1000000001 (one float32)', lambda d: vf(d).update(low=0.1, high=0.1000000001)),
    # ---- rules
    ('R1', 'rules missing', lambda d: d.pop('rules')),
    ('R2', 'rules.races missing', lambda d: d['rules'].pop('races')),
    ('R3', 'rules.races holds a number', lambda d: d['rules']['races'].append(5)),
    ('R4', 'npcFormID: an unknown key', lambda d: d['rules']['npcFormID'].update(other=[])),
    ('R5', 'npcFormID: plugin ""', lambda d: d['rules']['npcFormID']['female'].append({'plugin': '', 'id': 1})),
    ('R6', 'npcFormID: id 0x1000000',
     lambda d: d['rules']['npcFormID']['female'].append({'plugin': 'A.esp', 'id': 0x1000000})),
    ('R7', 'npcFormID: id -1', lambda d: d['rules']['npcFormID']['female'].append({'plugin': 'A.esp', 'id': -1})),
    ('R8', 'npcFormID: id 5.0', lambda d: d['rules']['npcFormID']['female'].append({'plugin': 'A.esp', 'id': 5.0})),
    ('R9', 'npcFormID: id "5"', lambda d: d['rules']['npcFormID']['female'].append({'plugin': 'A.esp', 'id': '5'})),
    ('R10', 'npcFormID: no plugin', lambda d: d['rules']['npcFormID']['female'].append({'id': 5})),
    ('R11', 'blacklistedNpcsFormID: plugin null',
     lambda d: d['rules']['blacklistedNpcsFormID'].append({'plugin': None, 'id': 5})),
    ('R12', 'blacklistedPlugins: an unknown key', lambda d: d['rules']['blacklistedPlugins'].update(other=[])),
    ('R13', 'blacklistedPlugins.female holds a number', lambda d: d['rules']['blacklistedPlugins']['female'].append(5)),
    ('R14', 'blacklistedRaces.male holds null', lambda d: d['rules']['blacklistedRaces']['male'].append(None)),
    ('R15', 'an npcName rule without a name', lambda d: rule(d, 'npcName')),
    ('R16', 'an npcName name a number', lambda d: rule(d, 'npcName', name=5)),
    ('R17', 'npcName sex "x", presets []',
     lambda d: d['rules']['npcName'].append({'name': 'Piper', 'sex': 'x', 'presets': []})),
    ('R18', 'npcName names a missing preset',
     lambda d: d['rules']['npcName'].append({'name': 'Piper', 'sex': 'female', 'presets': ['No Such Preset']})),
    ('R19', 'npcName presets a string',
     lambda d: d['rules']['npcName'].append({'name': 'Piper', 'sex': 'female', 'presets': 'X'})),
    ('R20', 'blacklistedNpcNames holds a number', lambda d: d['rules']['blacklistedNpcNames'].append(5)),
    ('R21', 'a faction rule without editorID', lambda d: rule(d, 'faction', plugin='Fallout4.esm', id=0x1234)),
    ('R22', 'a faction id 0x1000000',
     lambda d: rule(d, 'faction', plugin='Fallout4.esm', id=0x1000000, editorID='X')),
    ('R23', 'a faction plugin ""', lambda d: rule(d, 'faction', plugin='', id=5, editorID='X')),
    ('R24', 'a faction sex "x", presets []',
     lambda d: d['rules']['faction'].append({'plugin': 'Fallout4.esm', 'id': 5, 'editorID': 'X', 'sex': 'x',
                                             'presets': []})),
    ('R25', 'a faction names a missing preset',
     lambda d: d['rules']['faction'].append({'plugin': 'Fallout4.esm', 'id': 5, 'editorID': 'X', 'sex': 'female',
                                             'presets': ['No Such Preset']})),
    ('R26', 'npcName names a preset of the other sex',
     lambda d: d['rules']['npcName'].append({'name': 'Piper', 'sex': 'female', 'presets': [first(d, 'male')['name']]})),
    ('R27', 'npcName names a preset in another case',
     lambda d: d['rules']['npcName'].append({'name': 'Piper', 'sex': 'female',
                                             'presets': [first(d, 'female')['name'].upper()]})),
    ('R28', 'a faction editorID a number', lambda d: rule(d, 'faction', plugin='Fallout4.esm', id=5, editorID=7)),
    # ---- orefit
    ('O1', 'orefit missing', lambda d: d.pop('orefit')),
    ('O2', 'slots: 29', lambda d: d['orefit']['slots'].append(29)),
    ('O3', 'slots: 33.0', lambda d: d['orefit']['slots'].append(33.0)),
    ('O4', 'slots: 2**32 + 33', lambda d: d['orefit']['slots'].append(2 ** 32 + 33)),
    ('O5', 'blacklist: plugin ""', lambda d: d['orefit']['blacklist'].append({'plugin': '', 'id': 5})),
    ('O6', 'blacklistNames holds a number', lambda d: d['orefit']['blacklistNames'].append(5)),
    ('O7', 'force: id 0x1000000', lambda d: d['orefit']['force'].append({'plugin': 'A.esp', 'id': 0x1000000})),
    ('O8', 'an outfit without a name',
     lambda d: d['orefit']['outfits'].append({'sex': 'female', 'set': fset(d)['name']})),
    ('O9', 'an outfit names a set that is not there',
     lambda d: d['orefit']['outfits'].append({'name': 'Dress', 'sex': 'female', 'set': 'No-Refit'})),
    ('O10', 'an outfit sex "x"',
     lambda d: d['orefit']['outfits'].append({'name': 'Dress', 'sex': 'x', 'set': fset(d)['name']})),
    ('O11', 'a set without a name', lambda d: fset(d).pop('name')),
    ('O12', 'a set sex "x"', lambda d: fset(d).update(sex='x')),
    ('O13', 'two sets, one name in another case',
     lambda d: d['orefit']['sets'].append({**copy.deepcopy(fset(d)), 'name': fset(d)['name'].upper()})),
    ('O14', 'floors an object', lambda d: fset(d).update(floors={})),
    ('O15', 'a floor morph ""', lambda d: fset(d)['floors'][0].update(morph='')),
    ('O16', 'a floor morph Silhouette_Refit', lambda d: fset(d)['floors'][0].update(morph='Silhouette_Refit')),
    ('O17', 'a floor morph Silhouette_Chosen', lambda d: fset(d)['floors'][0].update(morph='Silhouette_Chosen')),
    ('O18', 'a floor morph Silhouette_Foo', lambda d: fset(d)['floors'][0].update(morph='Silhouette_Foo')),
    ('O19', 'a floor morph Erection', lambda d: fset(d)['floors'][0].update(morph='Erection')),
    ('O20', 'a floor value 0', lambda d: fset(d)['floors'][0].update(value=0.0)),
    ('O21', 'a floor value -0.1', lambda d: fset(d)['floors'][0].update(value=-0.1)),
    ('O22', 'a floor value 1e-50 (0 as a float32)', lambda d: fset(d)['floors'][0].update(value=1e-50)),
    ('O23', 'a floor value "0.3"', lambda d: fset(d)['floors'][0].update(value='0.3')),
    ('O24', 'a floor without heavyOnly', lambda d: fset(d)['floors'][0].pop('heavyOnly')),
    ('O25', 'a floor heavyOnly 1', lambda d: fset(d)['floors'][0].update(heavyOnly=1)),
    ('O26', 'heavy.words: "---"', lambda d: d['orefit']['heavy']['words'].append('---')),
    ('O27', 'heavy.words holds a number', lambda d: d['orefit']['heavy']['words'].append(5)),
    ('O28', 'heavy.items: id 0x1000000',
     lambda d: d['orefit']['heavy']['items'].append({'plugin': 'A.esp', 'id': 0x1000000})),
    ('O29', 'light.names holds null', lambda d: d['orefit']['light']['names'].append(None)),
    ('O30', 'orefit.heavy missing', lambda d: d['orefit'].pop('heavy')),
    ('O31', 'a floor morph "Silhouette_"', lambda d: fset(d)['floors'][0].update(morph='Silhouette_')),
    ('O32', 'a floor morph SILHOUETTE_REFIT', lambda d: fset(d)['floors'][0].update(morph='SILHOUETTE_REFIT')),
    ('O33', 'a floor value 1e-40 (a float32 denormal)', lambda d: fset(d)['floors'][0].update(value=1e-40)),
    ('O34', 'a floor value 10**40 as an integer', lambda d: fset(d)['floors'][0].update(value=10 ** 40)),
    ('O35', 'a set with no floors', lambda d: fset(d).update(floors=[])),
    ('O36', 'heavy.words: "é" (beyond ASCII only)', lambda d: d['orefit']['heavy']['words'].append('é')),
    ('O37', 'an outfit names its set in another case',
     lambda d: d['orefit']['outfits'].append({'name': 'Dress', 'sex': 'female', 'set': fset(d)['name'].upper()})),
    ('O38', 'an outfit name a number',
     lambda d: d['orefit']['outfits'].append({'name': 5, 'sex': 'female', 'set': fset(d)['name']})),
]


def expected(cid):
    if cid in ACCEPT:
        return 'accept', 'accept'
    if cid in STRICTER:
        return 'accept', 'refuse'
    if cid in MANIFEST:
        return 'manifest', 'accept'
    return 'refuse', 'refuse'


def parser_verdict(exe, root):
    p = subprocess.run([str(exe), '--check', str(root)], capture_output=True, timeout=120,
                       creationflags=support.LOW_PRIORITY)
    out = (p.stdout + p.stderr).decode('utf-8', 'replace').strip()
    if p.returncode == 0:
        return 'accept', out
    if 'would refuse catalog.json' in out:
        return 'refuse', out
    if 'manifest' in out and 'does not name' in out:
        return 'manifest', out
    return 'error', out


def check_verdict(doc):
    try:
        catalog.check(doc)
    except SystemExit as exc:
        return 'refuse', str(exc)
    except Exception as exc:          # a crash is no refusal: verify_bodygen reports a SystemExit, not a traceback
        return f'crash {type(exc).__name__}', str(exc)
    return 'accept', ''


@unittest.skipIf(support.tests_exe() is None, 'SilhouetteTests.exe is not built (scripts/build-plugin.ps1)')
class ParserParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads((support.PACKAGE / support.CAT).read_text(encoding='utf-8-sig'))

    def verdicts(self, cases):
        """{id: (what, (parser, check), parser output, check message)} -- the parser runs on one copy of the
        package per worker, the doctored catalog written over its catalog.json."""
        exe = support.tests_exe()
        workers = min(support.jobs(), len(cases))
        out = {}
        with support.Scratch() as scratch:
            def run(slot):
                root = scratch / str(slot)
                shutil.copytree(support.PACKAGE / 'F4SE', root / 'F4SE')
                for cid, what, edit in cases[slot::workers]:
                    doc = copy.deepcopy(self.base)
                    raw = edit(doc)
                    if isinstance(raw, Raw):
                        text, doc = raw, json.loads(raw)
                    else:
                        text = json.dumps(doc, indent=1, allow_nan=True)
                    (root / support.CAT).write_text(text + '\n', encoding='utf-8')
                    (pv, pout), (cv, cmsg) = parser_verdict(exe, root), check_verdict(doc)
                    out[cid] = (what, (pv, cv), pout, cmsg)
            with concurrent.futures.ThreadPoolExecutor(workers) as pool:
                for f in [pool.submit(run, slot) for slot in range(workers)]:
                    f.result()
        return out

    def test_check_refuses_whatever_the_parser_refuses(self):
        got = self.verdicts(CASES)
        # GP-4: the untouched catalog must pass both, or no verdict below means anything.
        self.assertEqual(got['p0'][1], ('accept', 'accept'), f'the committed package fails its own check: {got["p0"]}')
        for cid, what, _edit in CASES:
            what_, verdicts, pout, cmsg = got[cid]
            with self.subTest(case=cid, what=what):
                self.assertEqual(verdicts, expected(cid), f'\n  parser: {pout[-300:]}\n  check(): {cmsg[:300]}')

    def test_every_case_is_named_once(self):
        ids = [cid for cid, _w, _e in CASES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertLessEqual(ACCEPT | STRICTER | MANIFEST, set(ids))


# ---- manifests: the plugin's ParseManifest (src/Catalog.cpp) against the verifier's check_manifests, the same
# way (wave 5, lens 3 L8). Each case doctors an OLD manifest -- the current one must stay whole for --check.
def entry0(doc):
    return next(iter(doc['templates'].values()))


def value0(doc, v):
    values = next(e['values'] for e in doc['templates'].values() if e.get('values'))
    values[next(iter(values))] = v


MCASES = [
    ('m0', 'untouched', lambda d: None),
    ('M1', 'gender "Female"', lambda d: entry0(d).update(gender='Female')),
    ('M2', 'gender 5', lambda d: entry0(d).update(gender=5)),
    ('M3', 'gender null', lambda d: entry0(d).update(gender=None)),
    ('M4', 'gender missing', lambda d: entry0(d).pop('gender')),
    ('M5', 'a preset a number', lambda d: entry0(d).update(preset=5)),
    ('M6', 'an entry a string', lambda d: d['templates'].update({next(iter(d['templates'])): 'CBBE Curvy'})),
    ('M7', 'templates a list', lambda d: d.update(templates=[])),
    ('M8', 'stamp missing', lambda d: d.pop('stamp')),
    ('M9', 'stamp 0', lambda d: d.update(stamp=0)),
    ('M10', 'stamp "5"', lambda d: d.update(stamp='5')),
    ('M11', 'not JSON', lambda d: Raw('{"stamp": 5, "templates": {')),
    ('M12', 'the top level a list', lambda d: Raw('[1]')),
    ('M13', 'a preset named with a lone surrogate', lambda d: entry0(d).update(preset='\ud800')),
    ('M14', 'a value "0.5"', lambda d: value0(d, '0.5')),
    ('M15', 'values a list', lambda d: entry0(d).update(values=[1, 2])),
    ('M16', 'build missing', lambda d: d.pop('build')),
]
MACCEPT = {'m0', 'M4'}
# The verifier refuses, the parser takes: it reads only a manifest's markers, presets and sexes, while the
# verifier compares the values as numbers and a stamp with its build.
MSTRICTER = {'M14', 'M15', 'M16'}


def manifest_expected(cid):
    if cid in MACCEPT:
        return 'accept', 'accept'
    if cid in MSTRICTER:
        return 'accept', 'refuse'
    return 'refuse', 'refuse'


@unittest.skipIf(support.tests_exe() is None, 'SilhouetteTests.exe is not built (scripts/build-plugin.ps1)')
class ManifestParity(unittest.TestCase):
    def test_the_verifier_refuses_whatever_the_parser_refuses(self):
        import verify_bodygen
        cat = json.loads((support.PACKAGE / support.CAT).read_text(encoding='utf-8-sig'))
        olds = sorted(f for f in (support.PACKAGE / support.MANIFESTS).glob('*.json') if f.stem != str(cat['stamp']))
        if not olds:
            self.skipTest('the committed package holds no old manifest to doctor')
        old = olds[0]
        base = json.loads(old.read_text(encoding='utf-8-sig'))
        exe = support.tests_exe()
        with support.Scratch() as scratch:
            root = scratch / 'm'
            shutil.copytree(support.PACKAGE / 'F4SE', root / 'F4SE')
            target = root / support.MANIFESTS / old.name
            got = {}
            for cid, what, edit in MCASES:
                doc = copy.deepcopy(base)
                raw = edit(doc)
                text = raw if isinstance(raw, Raw) else json.dumps(doc, indent=1)
                target.write_text(text + '\n', encoding='utf-8')
                p = subprocess.run([str(exe), '--check', str(root)], capture_output=True, timeout=120,
                                   creationflags=support.LOW_PRIORITY)
                out = (p.stdout + p.stderr).decode('utf-8', 'replace').strip()
                pv = 'accept' if p.returncode == 0 else 'refuse' if f'CHECK FAIL: manifest {old.name}' in out else 'error'
                problems = []
                try:
                    verify_bodygen.check_manifests(root, cat, cat['stamp'], problems)
                    vv = 'refuse' if problems else 'accept'
                except Exception as exc:        # a crash is no refusal
                    vv, problems = f'crash {type(exc).__name__}', [str(exc)]
                got[cid] = (what, (pv, vv), out, problems)
        self.assertEqual(got['m0'][1], ('accept', 'accept'), f'the committed package fails its own check: {got["m0"]}')
        for cid, what, _edit in MCASES:
            what_, verdicts, out, problems = got[cid]
            with self.subTest(case=cid, what=what):
                self.assertEqual(verdicts, manifest_expected(cid), f'\n  parser: {out[-300:]}\n  verifier: {problems[:2]}')

    def test_every_case_is_named_once(self):
        ids = [cid for cid, _w, _e in MCASES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertLessEqual(MACCEPT | MSTRICTER, set(ids))


if __name__ == '__main__':
    unittest.main()
