"""Complexion's own overlays: painted, compressed and registered with LooksMenu (C-5, C-7).

    python tools/paint/make_marks.py [--data <game Data>] [--only <id prefix>]

Writes, all generated (never edit by hand):
- data/Textures/Overlays/Complexion/<id>_d.dds   BC3 with mipmaps (texconv)
- data/Materials/Overlays/Complexion/<id>.bgem   an effect material
- data/F4SE/Plugins/F4EE/Overlays/Complexion.esp/overlays.json   LooksMenu's templates (the folder named after
  the plugin, as LooksMenu loads them -- the scar Rapport's sweat carried for three releases)
- data/tags/complexion.json   their tags, for the composer
and build/marks_preview_<sex>.png, every template front and back.

The material is byte for byte a BGEM the game already draws (INVB's M_Back_Abraxo: alpha blending SRC_ALPHA /
INV_SRC_ALPHA, version 2, a 63-byte header), with the diffuse and the body normal swapped in -- not a header
re-derived from a format description (Rapport's make_overlays.py notes why: one byte off shifts every field).
"""
import argparse
import json
import pathlib
import shutil
import struct
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decals  # noqa: E402
import marks  # noqa: E402
import realism  # noqa: E402
from body import UVMap  # noqa: E402
from preview import sheet  # noqa: E402

ROOT = HERE.parent.parent
DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
TEXCONV = [pathlib.Path(r'D:\xEdit.4.1.5f\Edit Scripts\Texconvx64.exe'), pathlib.Path(r'D:\DynDOLOD\Edit Scripts\Texconvx64.exe')]
NORMAL = {'female': 'actors/character/basehumanfemale/FemaleBody_n.dds',
          'male': 'actors/character/basehumanmale/BaseMaleBody_n.dds'}
# The material MULTIPLIES the skin, as porcOverlays' moles and scars do (their BGEMs, read 2026-10-03): blend
# source DEST_COLOR (4), destination ZERO (1), so the frame becomes skin x texture x base colour x scale. A texel
# at NEUTRAL leaves the skin alone, darker darkens it, lighter lightens it -- and it is lit and shadowed with the
# skin, on any skin tone. Measured in game the same day: INVB's alpha blending (SRC_ALPHA / INV_SRC_ALPHA) draws
# unlit, so pale scars glowed in a dark corner; with "effect lighting" switched on the marks did not show at all.
# Header: porc's Moles_01.BGEM (blend 1/4/1, alpha test, z write, z test, SSR); base colour 1,1,1, scale 2.
SCALE = 2.0
NEUTRAL = 1.0 / SCALE
BGEM_HEAD = bytes.fromhex(
    '4247454d020000000300000000000000000000000000803f0000803f0000803f01040000000100000000010101010000000000000000'
    '000000000000803f00')
BGEM_MID = bytes.fromhex('01000000000100000000')
BGEM_TAIL = bytes.fromhex(
    '0100000000' '000000000000' '0000803f0000803f0000803f' + struct.pack('<f', SCALE).hex() +
    '00000000000000000000000000000000' '00000000' '00' '00000000')
assert len(BGEM_HEAD) == 63 and len(BGEM_TAIL) == 52

# id, sex, painter, args, texture size, tags
MARKS = []


def add(prefix, sexes, painter, args, size, tags, count):
    for sex in sexes:
        for k in range(count):
            MARKS.append((f'Complexion_{prefix}_{"F" if sex == "female" else "M"}{k + 1:02d}', sex, painter, args, size, tags))


ROUGH = dict(style=[], emblem=None, lore='fits', adult=False, quality='ok')
add('BruiseFresh', ('female', 'male'), 'bruises', ((2, 4), 'fresh'), 1024, dict(ROUGH, kind='bruise', regions=[], size='small', note='fresh bruises'), 3)
add('BruiseOld', ('female', 'male'), 'bruises', ((2, 4), 'old'), 1024, dict(ROUGH, kind='bruise', regions=[], size='small', note='fading yellow bruises'), 2)
add('GrimeLight', ('female', 'male'), 'grime', (0.35,), 1024, dict(ROUGH, kind='dirt', regions=[], size='medium', note='light ground-in dirt'), 2)
add('GrimeHeavy', ('female', 'male'), 'grime', (0.85,), 1024, dict(ROUGH, kind='dirt', regions=[], size='medium', note='heavy grime'), 2)
add('Blood', ('female', 'male'), 'dried_blood', (), 1024, dict(ROUGH, kind='blood', regions=[], size='medium', note='dried blood, drips, spatter'), 3)
add('LashesFresh', ('female', 'male'), 'lashes', ((4, 8), False), 2048, dict(ROUGH, kind='marks', regions=['back'], size='large', note='fresh whip welts'), 2)
add('LashesHealed', ('female', 'male'), 'lashes', ((4, 8), True), 2048, dict(ROUGH, kind='scar', regions=['back'], size='large', note='healed whip scars'), 1)
add('Spank', ('female', 'male'), 'spank', (), 1024, dict(ROUGH, kind='marks', regions=['butt'], size='medium', note='reddened buttocks, handprints'), 2)
add('Moles', ('male',), 'moles', ((15, 40),), 2048, dict(ROUGH, kind='mole', regions=[], size='tiny', note='moles'), 3)
add('Scar', ('male',), 'scars', ((2, 4), False), 2048, dict(ROUGH, kind='scar', regions=[], size='small', note='healed scars'), 2)
add('ScarStitched', ('male',), 'scars', ((1, 2), True), 2048, dict(ROUGH, kind='scar', regions=[], size='small', note='stitched scars'), 2)
add('PubicFull', ('male',), 'pubic_hair', ('full', 2048), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='large', note='full pubic hair'), 2)
add('PubicTrim', ('male',), 'pubic_hair', ('trim', 2048), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='small', note='trimmed pubic hair'), 1)
add('PubicTrail', ('male',), 'pubic_hair', ('trail', 2048), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='medium', note='pubic hair and a trail'), 1)
# 2026-10-03: more men's variety -- every man in Diamond City shared 4 pubic and 3 mole sheets. Appended last,
# so the seeds of everything above (their place in this list) stay as they were.
BROWN, GREY = (0.16, 0.10, 0.06), (0.42, 0.40, 0.38)
add('PubicFullBrown', ('male',), 'pubic_hair', ('full', 2048, BROWN), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='large', note='full pubic hair, brown'), 2)
add('PubicFullGrey', ('male',), 'pubic_hair', ('full', 2048, GREY), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='large', note='full pubic hair, greying'), 1)
add('PubicTrimBrown', ('male',), 'pubic_hair', ('trim', 2048, BROWN), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='small', note='trimmed pubic hair, brown'), 2)
add('PubicTrailBrown', ('male',), 'pubic_hair', ('trail', 2048, BROWN), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='medium', note='pubic hair and a trail, brown'), 1)
add('MolesMore', ('male',), 'moles', ((10, 30),), 2048, dict(ROUGH, kind='mole', regions=[], size='tiny', note='moles'), 3)

# ---- C-13 (2026-10-03): the realism layer
BOTH, F, M = ('female', 'male'), ('female',), ('male',)
add('Freckles', F, 'freckles', (0.7,), 2048, dict(ROUGH, kind='freckles', regions=[], size='medium', note='sun freckles'), 3)
add('Freckles', M, 'freckles', (0.6,), 2048, dict(ROUGH, kind='freckles', regions=[], size='medium', note='sun freckles'), 2)
add('Birthmark', BOTH, 'birthmark', (), 2048, dict(ROUGH, kind='birthmark', regions=[], size='small', note='a birthmark'), 2)
add('Pores', BOTH, 'pores', (0.7,), 2048, dict(ROUGH, kind='skin', regions=[], size='full', note='skin texture'), 2)
add('Veins', F, 'veins', (), 2048, dict(ROUGH, kind='skin', regions=[], size='small', note='faint veins'), 2)
add('Veins', M, 'veins', (), 2048, dict(ROUGH, kind='skin', regions=[], size='small', note='faint veins'), 1)
add('Stretch', F, 'stretch_marks', (), 2048, dict(ROUGH, kind='skin', regions=[], size='small', note='stretch marks'), 3)
add('Stretch', M, 'stretch_marks', (), 2048, dict(ROUGH, kind='skin', regions=[], size='small', note='stretch marks'), 1)
add('Pimples', BOTH, 'pimples', (0.5,), 2048, dict(ROUGH, kind='acne', regions=[], size='small', note='pimples'), 2)
for tone in ('pink', 'brown', 'dark'):
    add(f'Nipples{tone.title()}', F, 'nipples', (tone, True), 2048, dict(ROUGH, kind='nipple', regions=['breasts'], size='small', note=f'{tone} areolas'), 1)
    add(f'Nipples{tone.title()}', M, 'nipples', (tone, False), 2048, dict(ROUGH, kind='nipple', regions=['chest'], size='tiny', note=f'{tone} nipples'), 1)
for style, colours, size in (('natural', ('brown', 'black', 'auburn', 'blond'), 'large'), ('trimmed', ('brown', 'black', 'blond'), 'small'),
                             ('triangle', ('brown', 'black'), 'medium'), ('landing', ('brown', 'black'), 'small')):
    for colour in colours:
        add(f'Pubic{style.title()}{colour.title()}', F, 'pubic_female', (style, colour), 2048,
            dict(ROUGH, kind='pubic_hair', regions=['pubic'], size=size, note=f'{style} pubic hair, {colour}'), 1)
add('Stubble', F, 'stubble_female', ('brown',), 2048, dict(ROUGH, kind='body_hair', regions=[], size='small', note='leg and underarm stubble'), 2)
for colour in ('brown', 'black', 'grey'):
    add(f'ChestHair{colour.title()}', M, 'body_hair_male', ('chest', colour), 2048, dict(ROUGH, kind='body_hair', regions=['chest'], size='medium', note=f'chest hair, {colour}'), 1)
for colour in ('brown', 'black'):
    add(f'LimbHair{colour.title()}', M, 'body_hair_male', ('limbs', colour), 2048, dict(ROUGH, kind='body_hair', regions=[], size='medium', note=f'arm and leg hair, {colour}'), 1)

# ---- C-13: drawn tattoos -- (name, design, spot, side, width, ink, crude, size, style, emblem, adult, note)
SPOT_REGION = {'chest': 'chest', 'belly': 'belly', 'upper_back': 'back', 'lower_back': 'lower_back', 'neck_back': 'neck',
               'shoulder': 'shoulders', 'thigh': None, 'thigh_back': None, 'calf': None, 'hip': 'pelvis', 'butt': 'butt'}
TATTOOS = [
    ('NoMercy', ('word', 'No Mercy', 'blackletter', 0.0), 'chest', 0, 12, 'fresh', 0.0, 'medium', ['script', 'crude'], 'raiders', False, '"No Mercy" across the chest'),
    ('Rust', ('word', 'RUST', 'stencil', 0.0), 'forearm', 1, 6, 'faded', 0.8, 'small', ['script', 'crude'], None, False, '"RUST" on the forearm'),
    ('Kill', ('word', 'KILL', 'pirate', 0.0), 'forearm', -1, 6, 'fresh', 0.5, 'small', ['script', 'crude'], None, False, '"KILL" on the forearm'),
    ('Wasteland', ('word', 'Wasteland', 'blackletter', 0.06), 'upper_back', 0, 16, 'fresh', 0.0, 'large', ['script'], None, False, '"Wasteland" across the back'),
    ('RaiderWord', ('word', 'Raider', 'pirate', 0.0), 'lower_back', 0, 12, 'fresh', 0.3, 'medium', ['script', 'crude'], 'raiders', False, '"Raider" on the lower back'),
    ('Love', ('word', 'LOVE', 'stencil', 0.0), 'forearm', -1, 6, 'faded', 0.9, 'small', ['script', 'crude'], None, False, 'prison "LOVE"'),
    ('Hate', ('word', 'HATE', 'stencil', 0.0), 'forearm', 1, 6, 'faded', 0.9, 'small', ['script', 'crude'], None, False, 'prison "HATE"'),
    ('Mom', ('word', 'Mom', 'western', 0.0), 'upper_arm', 1, 5, 'faded', 0.4, 'small', ['script'], None, False, '"Mom" on the upper arm'),
    ('Thirteen', ('word', '13', 'pirate', 0.0), 'neck_back', 0, 3, 'faded', 0.7, 'tiny', ['script', 'crude'], None, False, '"13" on the neck'),
    ('Hope', ('word', 'Hope', 'script', 0.0), 'hip', 1, 6, 'fresh', 0.0, 'small', ['script', 'floral'], None, False, '"Hope" on the hip'),
    ('Faith', ('word', 'Faith', 'script', 0.0), 'lower_back', 0, 10, 'fresh', 0.0, 'small', ['script', 'floral'], None, False, '"Faith" on the lower back'),
    ('Forever', ('word', 'Forever', 'script', 0.0), 'thigh', -1, 8, 'fresh', 0.0, 'small', ['script', 'floral'], None, False, '"Forever" on the thigh'),
    ('Steel', ('word', 'STEEL', 'stencil', 0.0), 'upper_arm', 1, 7, 'fresh', 0.0, 'small', ['script', 'military'], 'bos', False, '"STEEL" on the upper arm'),
    ('AtomPraised', ('word', 'Atom Be Praised', 'blackletter', 0.08), 'upper_back', 0, 16, 'faded', 0.2, 'large', ['script', 'religious'], 'atom', False, '"Atom Be Praised" across the back'),
    ('MinutemenWord', ('word', 'Minutemen', 'western', 0.0), 'upper_arm', -1, 8, 'fresh', 0.0, 'small', ['script', 'military'], 'minutemen', False, '"Minutemen" on the upper arm'),
    ('Property', ('word', 'PROPERTY', 'stencil', 0.0), 'lower_back', 0, 12, 'fresh', 0.4, 'medium', ['script', 'degrading', 'crude'], None, True, '"PROPERTY" on the lower back'),
    ('Sold', ('word', 'SOLD', 'stencil', 0.0), 'butt', 1, 6, 'red', 0.3, 'small', ['script', 'degrading', 'crude'], None, True, '"SOLD" on a buttock'),
    ('Owned', ('word', 'OWNED', 'pirate', 0.0), 'thigh_back', -1, 7, 'fresh', 0.3, 'small', ['script', 'degrading', 'crude'], None, True, '"OWNED" on the back of the thigh'),
    ('MandalaBack', ('mandala',), 'upper_back', 0, 12, 'fresh', 0.0, 'large', ['geometric'], None, False, 'a mandala between the shoulders'),
    ('MandalaThigh', ('mandala',), 'thigh', 1, 8, 'fresh', 0.0, 'medium', ['geometric', 'floral'], None, False, 'a mandala on the thigh'),
    ('TribalLowerBack', ('tribal',), 'lower_back', 0, 16, 'fresh', 0.0, 'medium', ['tribal'], None, False, 'a tribal piece on the lower back'),
    ('TribalShoulder', ('tribal',), 'shoulder', -1, 10, 'fresh', 0.0, 'medium', ['tribal'], None, False, 'a tribal piece on the shoulder'),
    ('TribalChest', ('tribal',), 'chest', 0, 14, 'fresh', 0.0, 'medium', ['tribal'], None, False, 'a tribal piece across the chest'),
    ('BarcodeNeck', ('barcode',), 'neck_back', 0, 5, 'fresh', 0.0, 'tiny', ['geometric'], None, False, 'a barcode on the neck'),
    ('BarcodeArm', ('barcode',), 'forearm', 1, 5, 'fresh', 0.0, 'small', ['geometric'], None, False, 'a barcode on the forearm'),
    ('PrisonDots', ('dots',), 'forearm', -1, 2.4, 'faded', 0.5, 'tiny', ['crude'], None, False, 'five prison dots'),
    ('AtomShoulder', ('emblem', 'atom'), 'shoulder', 1, 6, 'fresh', 0.0, 'small', ['emblem', 'religious'], 'atom', False, 'the Atom on the shoulder'),
    ('AtomChest', ('emblem', 'atom'), 'chest', 0, 9, 'faded', 0.2, 'medium', ['emblem', 'religious'], 'atom', False, 'the Atom on the chest'),
    ('VaultTecArm', ('emblem', 'vault_tec'), 'forearm', -1, 5, 'fresh', 0.0, 'small', ['emblem'], 'vault_tec', False, 'the Vault-Tec gear on the forearm'),
    ('VaultTecUpperArm', ('emblem', 'vault_tec'), 'upper_arm', 1, 6, 'faded', 0.0, 'small', ['emblem'], 'vault_tec', False, 'the Vault-Tec gear on the upper arm'),
    ('BoSBack', ('emblem', 'bos'), 'upper_back', 0, 12, 'fresh', 0.0, 'large', ['emblem', 'military'], 'bos', False, 'the Brotherhood on the back'),
    ('BoSArm', ('emblem', 'bos'), 'upper_arm', -1, 6, 'fresh', 0.0, 'small', ['emblem', 'military'], 'bos', False, 'the Brotherhood on the upper arm'),
    ('MinutemenShoulder', ('emblem', 'minutemen'), 'shoulder', 1, 6, 'fresh', 0.0, 'small', ['emblem', 'military'], 'minutemen', False, 'the Minutemen star on the shoulder'),
    ('MinutemenChest', ('emblem', 'minutemen'), 'chest', -1, 6, 'faded', 0.0, 'small', ['emblem', 'military'], 'minutemen', False, 'the Minutemen star on the chest'),
    ('RailroadWrist', ('emblem', 'railroad'), 'forearm', 1, 3, 'faded', 0.0, 'tiny', ['emblem', 'geometric'], 'railroad', False, 'a tiny Railroad lantern'),
    ('RaiderSkullChest', ('emblem', 'raiders'), 'chest', 1, 7, 'fresh', 0.6, 'small', ['emblem', 'skull', 'crude'], 'raiders', False, 'a crude raider skull on the chest'),
    ('RaiderSkullBack', ('emblem', 'raiders'), 'upper_back', 0, 12, 'fresh', 0.5, 'large', ['emblem', 'skull', 'crude'], 'raiders', False, 'a raider skull on the back'),
    ('GunnersShoulder', ('emblem', 'gunners'), 'shoulder', -1, 6, 'fresh', 0.0, 'small', ['emblem', 'military', 'skull'], 'gunners', False, 'the Gunners crosshair on the shoulder'),
    ('GunnersArm', ('emblem', 'gunners'), 'forearm', 1, 5, 'fresh', 0.0, 'small', ['emblem', 'military'], 'gunners', False, 'the Gunners crosshair on the forearm'),
]
for name, spec, spot, side, width, ink, crude, size, style, emblem, adult, note in TATTOOS:
    if spot in ('forearm', 'upper_arm'):
        region = ['arm_r'] if side > 0 else ['arm_l']
    elif spot in ('thigh', 'thigh_back', 'calf'):
        region = ['leg_r'] if side > 0 else ['leg_l']
    else:
        region = [SPOT_REGION[spot]]
    tag = dict(kind='tattoo', regions=region, size=size, style=style, emblem=emblem, lore='fits', adult=adult,
               quality='ok', note=note)
    add(f'Tattoo{name}', BOTH, 'decal', (spec, spot, side, width, ink, crude), 2048, tag, 1)

# ---- C-14 (owner, 2026-10-03): lewd marks for NPCs whose Rapport persona is vulgar -- crude, explicit, around the
# genitals and the arse ("don't be too soft"). Adult: the MCM adult switch turns every one of them off. Style "lewd"
# is what the persona step draws from (data/profiles.json "personas").
LEWD = ['lewd', 'sexual', 'script']
LEWD_F = [
    ('LewdEntry', ('arrow', 'ENTRY', 'stencil', 'down'), 'pubic', 0, 9, 'fresh', 0.3, 'small', LEWD, '"ENTRY" and an arrow down to her cunt'),
    ('LewdInsertHere', ('arrow', 'INSERT HERE', 'pirate', 'down'), 'pubic', 0, 11, 'fresh', 0.0, 'small', LEWD, '"INSERT HERE" and an arrow down'),
    ('LewdCumHere', ('arrow', 'CUM HERE', 'blackletter', 'down'), 'pubic', 0, 11, 'fresh', 0.0, 'small', LEWD, '"CUM HERE" and an arrow down'),
    ('LewdOpen247', ('arrow', 'OPEN 24/7', 'stencil', 'down'), 'pubic', 0, 11, 'faded', 0.5, 'small', LEWD, '"OPEN 24/7" over her cunt'),
    ('LewdBackDoor', ('arrow', 'Back Door', 'script', 'down'), 'tailbone', 0, 12, 'fresh', 0.0, 'small', LEWD, 'a "Back Door" tramp stamp, arrow down to her arse'),
    ('LewdSpreadMe', ('word', 'SPREAD ME', 'pirate', 0.0), 'butt', -1, 8, 'fresh', 0.3, 'small', LEWD, '"SPREAD ME" on a buttock'),
    ('LewdRideMe', ('word', 'RIDE ME', 'western', 0.0), 'inner_thigh', 1, 7, 'fresh', 0.0, 'small', LEWD, '"RIDE ME" on the inner thigh'),
    ('LewdFuckMe', ('arrow', 'FUCK ME', 'stencil', 'left'), 'inner_thigh', -1, 9, 'fresh', 0.5, 'small', LEWD, '"FUCK ME" and an arrow up the inner thigh'),
]
LEWD_M = [
    ('LewdSuck', ('arrow', 'SUCK', 'stencil', 'down'), 'pubic', 0, 8, 'fresh', 0.4, 'small', LEWD, '"SUCK" and an arrow down to his cock'),
    ('LewdCumDump', ('arrow', 'CUM DUMP', 'pirate', 'down'), 'tailbone', 0, 11, 'fresh', 0.3, 'small', LEWD, '"CUM DUMP" over his arse'),
    ('LewdBitch', ('word', 'BITCH', 'blackletter', 0.0), 'butt', 1, 7, 'fresh', 0.0, 'small', LEWD, '"BITCH" on a buttock'),
]
LEWD_BOTH = [
    ('LewdFreeUse', ('arrow', 'FREE USE', 'stencil', 'down'), 'pubic', 0, 11, 'fresh', 0.4, 'small', LEWD, '"FREE USE" and an arrow down'),
    ('LewdSlut', ('word', 'SLUT', 'stencil', 0.0), 'butt', 1, 7, 'fresh', 0.4, 'small', LEWD + ['degrading'], '"SLUT" on a buttock'),
    ('LewdWhore', ('word', 'WHORE', 'blackletter', 0.0), 'butt', -1, 8, 'fresh', 0.0, 'small', LEWD + ['degrading'], '"WHORE" on a buttock'),
    ('LewdTipJar', ('arrow', 'TIP JAR', 'western', 'down'), 'tailbone', 0, 10, 'faded', 0.3, 'small', LEWD, '"TIP JAR" over the arse'),
    ('LewdTally', ('tally', 17), 'hip', 1, 8, 'fresh', 0.7, 'small', LEWD, 'tally marks: seventeen so far'),
]
for sexes, rows in ((('female',), LEWD_F), (('male',), LEWD_M), (('female', 'male'), LEWD_BOTH)):
    for name, spec, spot, side, width, ink, crude, size, style, note in rows:
        region = {'pubic': ['pubic'], 'tailbone': ['butt'], 'butt': ['butt'], 'hip': ['pelvis'],
                  'inner_thigh': ['leg_r' if side > 0 else 'leg_l']}[spot]
        add(f'Tattoo{name}', sexes, 'decal', (spec, spot, side, width, ink, crude), 2048,
            dict(kind='tattoo', regions=region, size=size, style=style, emblem=None, lore='fits', adult=True,
                 quality='ok', note=note), 1)


def design(spec, rng):
    kind, *rest = spec
    if kind == 'word':
        text, font, arc = rest
        return decals.word(text, font, arc)
    if kind == 'emblem':
        return decals.emblem(rest[0])
    if kind == 'arrow':
        text, font, direction = rest
        return decals.arrow_word(text, font, direction)
    if kind == 'tally':
        return decals.tally(rest[0])
    return {'mandala': decals.mandala, 'tribal': decals.tribal, 'barcode': decals.barcode}.get(kind, None)(rng) \
        if kind != 'dots' else decals.prison_dots()


def paint(painter, m, rng, args):
    if painter == 'decal':
        spec, spot, side, width, ink, crude = args
        return decals.project(m, design(spec, rng), spot, side, width=width, ink=ink, crude=crude, seed=int(rng.integers(1 << 30)))
    for module in (marks, realism):
        if hasattr(module, painter):
            return getattr(module, painter)(m, rng, *args)
    raise SystemExit(f'no painter {painter}')


def dilate(rgb, alpha, covered, steps=6):
    """Spreads colour (not opacity) a few texels past the UV islands, so filtering at a seam does not pull in
    black. Alpha outside the islands stays 0."""
    rgb = rgb.copy()
    have = covered.copy()
    for _ in range(steps):
        grown = have.copy()
        acc = np.zeros_like(rgb)
        cnt = np.zeros(have.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(have, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * sh[..., None]
            cnt += sh
        new = (~have) & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        grown |= new
        have = grown
    return rgb


SKIN = np.array((0.80, 0.64, 0.54))  # the skin the painters (and preview.py) paint over


def multiplier(rgb, alpha):
    """What the multiply material needs: per texel, the factor the skin is multiplied by -- 1 where nothing is
    painted, colour/skin where the mark is opaque -- stored as factor x NEUTRAL (the material scales it back).
    Everywhere off the marks, and off the UV islands, it is exactly NEUTRAL: no seam, no tint."""
    factor = 1.0 + alpha[..., None] * (rgb / SKIN - 1.0)
    tex = np.clip(factor * NEUTRAL, 0.0, 1.0)
    return Image.fromarray((tex * 255 + 0.5).astype(np.uint8), 'RGB')


def texconv():
    for t in TEXCONV:
        if t.exists():
            return t
    found = shutil.which('texconv')
    if found:
        return pathlib.Path(found)
    sys.exit('texconv not found')


def bgem(diffuse, normal):
    def s(path):
        raw = path.encode('ascii') + b'\0'
        return struct.pack('<I', len(raw)) + raw
    return BGEM_HEAD + s(diffuse) + BGEM_MID + s(normal) + BGEM_TAIL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=pathlib.Path, default=DATA)
    ap.add_argument('--only', default='')
    ap.add_argument('--missing', action='store_true', help='paint only templates with no texture yet')
    a = ap.parse_args()
    tex_dir = ROOT / 'data' / 'Textures' / 'Overlays' / 'Complexion'
    mat_dir = ROOT / 'data' / 'Materials' / 'Overlays' / 'Complexion'
    json_dir = ROOT / 'data' / 'F4SE' / 'Plugins' / 'F4EE' / 'Overlays' / 'Complexion.esp'
    work = ROOT / 'build' / 'marks'
    for d in (tex_dir, mat_dir, json_dir, work):
        d.mkdir(parents=True, exist_ok=True)
    tool = texconv()
    maps = {}
    entries, tags, previews = [], {}, {'female': [], 'male': []}
    for n, (tid, sex, painter, args, size, tag) in enumerate(MARKS):
        female = sex == 'female'
        entries.append({'id': tid, 'name': f'Complexion - {tag["note"]}', 'slots': [{'slot': 3, 'material': f'overlays\\Complexion\\{tid}.bgem'}],
                        'playable': True, 'transformable': True, 'sort': 0, 'gender': 1 if female else 0})
        tags[('f:' if female else 'm:') + tid] = tag
        if a.only and not tid.startswith(a.only):
            continue
        if a.missing and (tex_dir / f'{tid}_d.dds').exists():
            continue
        if (sex, size) not in maps:
            maps[(sex, size)] = UVMap(a.data, sex, size)
        m = maps[(sex, size)]
        rng = np.random.default_rng(1000 + n)
        rgb, alpha = paint(painter, m, rng, args)
        rgb = dilate(rgb, alpha, m.covered)
        img = multiplier(rgb, alpha)
        png = work / f'{tid}_d.png'
        img.save(png)
        r = subprocess.run([str(tool), '-nologo', '-y', '-ft', 'dds', '-f', 'BC1_UNORM', '-m', '0', '-o', str(tex_dir), str(png)],
                           capture_output=True, text=True)
        made = next((f for f in tex_dir.iterdir() if f.name.lower() == f'{tid}_d.dds'.lower()), None)
        if r.returncode or not made:
            sys.exit(f'texconv failed on {png}: {r.stdout[-300:]} {r.stderr[-300:]}')
        if made.name != f'{tid}_d.dds':
            made.rename(tex_dir / f'{tid}_d.dds')  # texconv writes .DDS; the material names .dds
        (mat_dir / f'{tid}.bgem').write_bytes(bgem(f'overlays/Complexion/{tid}_d.dds', NORMAL[sex]))
        previews[sex].append((tid.replace('Complexion_', ''), rgb, alpha, m))
        print(f'  {tid}: {painter}{args} {size}px, {float((alpha > 0.05).mean()) * 100:.1f}% of the map')
    (json_dir / 'overlays.json').write_text(json.dumps(entries, indent=1), encoding='utf-8', newline='\n')
    (ROOT / 'data' / 'tags' / 'complexion.json').write_text(json.dumps(tags, indent=1), encoding='utf-8', newline='\n')
    for sex, items in previews.items():
        for size in sorted({it[3].size for it in items}):
            group = [it[:3] for it in items if it[3].size == size]
            print(sheet(maps[(sex, size)], group, ROOT / 'build' / f'marks_preview_{sex}_{size}.png', height=360))
    print(f'{len(entries)} templates; textures in {tex_dir}')


if __name__ == '__main__':
    main()
