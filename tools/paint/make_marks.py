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
import flash  # noqa: E402
import hair  # noqa: E402
import hands  # noqa: E402
import life  # noqa: E402
import marks  # noqa: E402
import realism  # noqa: E402
import seams  # noqa: E402
import skin  # noqa: E402
import traits  # noqa: E402
HAIR_RGB = realism.HAIR  # skin adds ginger, lightbrown, darkbrown
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
# Textures are BC7: BC1's 5-6-5 colours cannot hold the neutral grey. 0.1.0 stored it as (132, 130, 132)/255 and
# brightened the whole body ~3.5% per overlay; 0.1.1's base colour fixed the clean skin, but the faint soft edge of
# every mark (1-4 levels off neutral) still decoded to 126/129, a 2-5% patch around each mole, pimple and hair (a
# player's report, 2026-10-04). BC7 holds 128 exactly (patch error 0.1-0.3%, measured); 128 x 2 x 255/256 = 1.
BASE_COLOUR = (255 / 256, 255 / 256, 255 / 256)
BGEM_TAIL = bytes.fromhex(
    '0100000000' '000000000000' + struct.pack('<fff', *BASE_COLOUR).hex() + struct.pack('<f', SCALE).hex() +
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


# ---- C-15 (owner, 2026-10-03): all four new sets. Appended after everything above, so earlier seeds stay put.
ADULT = dict(ROUGH, adult=True)
# Captives and rough life
add('RopeWrists', BOTH, 'bindings', ('wrists', True), 2048, dict(ROUGH, kind='marks', regions=[], size='small', note='rope marks around the wrists'), 2)
add('RopeWristsHealed', BOTH, 'bindings', ('wrists', False), 2048, dict(ROUGH, kind='marks', regions=[], size='small', note='old rope marks on the wrists'), 1)
add('RopeAnkles', BOTH, 'bindings', ('ankles', True), 2048, dict(ROUGH, kind='marks', regions=[], size='small', note='rope marks around the ankles'), 1)
add('ShackleAnkles', BOTH, 'shackles', ('ankles',), 2048, dict(ROUGH, kind='marks', regions=[], size='small', note='shackle chafe on the ankles'), 1)
add('ShackleWrists', BOTH, 'shackles', ('wrists',), 2048, dict(ROUGH, kind='marks', regions=[], size='small', note='shackle chafe on the wrists'), 1)
add('Collar', BOTH, 'collar', (), 2048, dict(ADULT, kind='marks', regions=[], size='small', style=['degrading'], note="a collar's chafe around the neck"), 1)
add('GripArms', BOTH, 'grip_bruises', ('arms',), 2048, dict(ROUGH, kind='bruise', regions=[], size='small', note='finger bruises around the upper arms'), 2)
add('GripHips', BOTH, 'grip_bruises', ('hips',), 2048, dict(ADULT, kind='bruise', regions=[], size='small', style=['sexual', 'lewd'], note='finger bruises on the hips, held from behind'), 1)
add('CigBurns', BOTH, 'cigarette_burns', (False,), 2048, dict(ROUGH, kind='burn', regions=[], size='tiny', style=['degrading'], note='fresh cigarette burns'), 2)
add('CigBurnsHealed', BOTH, 'cigarette_burns', (True,), 2048, dict(ROUGH, kind='burn', regions=[], size='tiny', note='old cigarette burn scars'), 1)
add('BiteShoulder', BOTH, 'bites', (('shoulder',),), 2048, dict(ADULT, kind='marks', regions=[], size='small', style=['sexual'], note='a bite mark on the shoulder'), 1)
add('BiteBreast', F, 'bites', (('breast', 'neck'),), 2048, dict(ADULT, kind='marks', regions=[], size='small', style=['sexual', 'lewd'], note='bite marks on a breast and the neck'), 1)
add('BiteThigh', BOTH, 'bites', (('inner_thigh', 'butt'),), 2048, dict(ADULT, kind='marks', regions=[], size='small', style=['sexual', 'lewd'], note='bite marks on the inner thigh and a buttock'), 1)
add('HickeyNeck', BOTH, 'hickeys', (('neck', 'chest'),), 2048, dict(ADULT, kind='bruise', regions=[], size='small', style=['sexual', 'lewd'], note='hickeys on the neck and chest'), 2)
add('HickeyThigh', BOTH, 'hickeys', (('inner_thigh', 'belly'),), 2048, dict(ADULT, kind='bruise', regions=[], size='small', style=['sexual', 'lewd'], note='hickeys on the inner thighs and low on the belly'), 1)
KISS = dict(ADULT, kind='makeup', regions=[], size='small', style=['sexual', 'lewd'])
add('KissRed', F, 'kisses', ('red', (('butt', 1), ('butt', -1), ('inner_thigh', 1))), 2048, dict(KISS, note='red lipstick kisses on the buttocks and a thigh'), 1)
add('KissPink', F, 'kisses', ('pink', (('chest', 1), ('belly', 0), ('inner_thigh', -1))), 2048, dict(KISS, note='pink lipstick kisses down the body'), 1)
add('KissPlum', F, 'kisses', ('plum', (('butt', -1), ('hip', 1), ('thigh', 1))), 2048, dict(KISS, note='dark lipstick kisses'), 1)
add('KissRed', M, 'kisses', ('red', (('butt', 1), ('belly', 0), ('inner_thigh', -1))), 2048, dict(KISS, note='red lipstick kisses'), 1)
add('KissPink', M, 'kisses', ('pink', (('chest', -1), ('shoulder', 1), ('butt', -1))), 2048, dict(KISS, note='pink lipstick kisses'), 1)
SCRAWL = dict(ADULT, kind='marks', regions=[], size='small', style=['lewd', 'degrading', 'script'])
SCRAWLS = [
    (BOTH, 'MarkerNext', ((('arrow', 'NEXT', 'pubic', 0, 9),), 'marker'), '"NEXT" and an arrow down, in marker'),
    (BOTH, 'MarkerUsed', ((('word', 'USED', 'thigh', 1, 7), ('tally', '8', 'thigh', -1, 6)), 'marker'), '"USED" and a tally on the thighs, in marker'),
    (BOTH, 'MarkerTenCaps', ((('word', '10 CAPS', 'lower_back', 0, 11),), 'marker_red'), 'a price, "10 CAPS", in red marker'),
    (BOTH, 'MarkerSlave', ((('word', 'SLAVE', 'chest', 0, 10),), 'marker'), '"SLAVE" across the chest, in marker'),
    (BOTH, 'MarkerCumRag', ((('word', 'CUM RAG', 'butt', 1, 8),), 'marker_blue'), '"CUM RAG" on a buttock, in marker'),
    (F, 'MarkerFree', ((('arrow', 'FREE', 'pubic', 0, 8), ('word', 'RENT ME', 'butt', -1, 7)), 'marker'), '"FREE" with an arrow and "RENT ME", in marker'),
    (F, 'MarkerDirtyGirl', ((('word', 'DIRTY GIRL', 'belly', 0, 12),), 'marker_red'), '"DIRTY GIRL" across the belly, in red marker'),
]
for sexes, name, args, note in SCRAWLS:
    add(name, sexes, 'scrawl', args, 2048, dict(SCRAWL, note=note), 1)
# Faction flavour
add('RitualCuts', BOTH, 'ritual_cuts', (False,), 2048, dict(ROUGH, kind='scar', regions=[], size='small', emblem='disciples', note="the Disciples' ritual cuts, healed"), 2)
add('RitualCutsFresh', BOTH, 'ritual_cuts', (True,), 2048, dict(ROUGH, kind='wound', regions=[], size='small', emblem='disciples', note="the Disciples' ritual cuts, fresh"), 1)
add('BloodyHands', BOTH, 'bloody_hands', ((('chest', 1), ('belly', 0)),), 2048, dict(ROUGH, kind='blood', regions=[], size='medium', emblem='disciples', note='bloody handprints on the chest and belly'), 1)
add('BloodyHandsThigh', BOTH, 'bloody_hands', ((('chest', -1), ('thigh', 1)),), 2048, dict(ROUGH, kind='blood', regions=[], size='medium', emblem='disciples', note='bloody handprints on the chest and a thigh'), 1)
add('RadSores', BOTH, 'rad_sores', (), 2048, dict(ROUGH, kind='burn', regions=[], size='medium', emblem='atom', note='radiation sores'), 2)
add('AtomScar', BOTH, 'scar_decal', (('emblem', 'atom'), 'chest', 0, 8), 2048, dict(ROUGH, kind='scar', regions=['chest'], size='medium', emblem='atom', note='the Atom cut into the chest'), 1)
add('BulletScars', BOTH, 'bullet_scars', ((1, 3),), 2048, dict(ROUGH, kind='scar', regions=[], size='tiny', note='healed bullet wounds'), 2)
add('Shrapnel', BOTH, 'shrapnel', (), 2048, dict(ROUGH, kind='scar', regions=[], size='small', note='shrapnel scars down one side'), 1)
add('LaserBurn', BOTH, 'laser_burn', (), 2048, dict(ROUGH, kind='burn', regions=[], size='small', note='a laser burn scar'), 2)
add('BurnScar', BOTH, 'burn_scar', (), 2048, dict(ROUGH, kind='burn', regions=[], size='medium', note='an old burn scar'), 1)
for colour in ('green', 'purple', 'pink', 'blue'):
    add(f'PackPaint{colour.title()}', BOTH, 'pack_paint', (colour,), 2048, dict(ROUGH, kind='makeup', regions=[], size='large', emblem='pack', note=f"the Pack's {colour} body paint"), 1)
FLAVOUR = [
    ('GunnersTally', ('tally', 13), 'forearm', 1, 6, 'fresh', 0.5, 'small', ['military', 'crude'], 'gunners', False, 'a kill tally on the forearm'),
    ('GunnersTallyArm', ('tally', 23), 'upper_arm', -1, 7, 'faded', 0.5, 'small', ['military', 'crude'], 'gunners', False, 'a long kill tally on the upper arm'),
    ('AceSpades', ('card',), 'forearm', 1, 4.5, 'fresh', 0.0, 'small', ['gambling'], None, False, 'the ace of spades'),
    ('Dice', ('dice',), 'upper_arm', -1, 5.5, 'fresh', 0.0, 'small', ['gambling'], None, False, 'a pair of dice'),
    ('Lucky', ('lucky',), 'chest', -1, 6, 'fresh', 0.0, 'small', ['gambling', 'script'], None, False, 'a horseshoe, LUCKY'),
    ('LuckyBack', ('lucky',), 'upper_back', 0, 10, 'faded', 0.0, 'medium', ['gambling', 'script'], None, False, 'a big LUCKY horseshoe on the back'),
    ('Dollar', ('dollar',), 'shoulder', 1, 5, 'fresh', 0.0, 'small', ['gambling'], None, False, 'a dollar sign in stars'),
    ('Vault81', ('vault', 81), 'upper_arm', 1, 5.5, 'fresh', 0.0, 'small', ['emblem'], 'vault_tec', False, 'Vault 81 in the gear'),
    ('Vault81Word', ('word', 'VAULT 81', 'stencil', 0.0), 'forearm', -1, 7, 'faded', 0.0, 'small', ['script', 'emblem'], 'vault_tec', False, '"VAULT 81" on the forearm'),
]
for name, spec, spot, side, width, ink, crude, size, style, emblem, adult, note in FLAVOUR:
    region = (['arm_r'] if side > 0 else ['arm_l']) if spot in ('forearm', 'upper_arm') else [SPOT_REGION[spot]]
    add(f'Tattoo{name}', BOTH, 'decal', (spec, spot, side, width, ink, crude), 2048,
        dict(kind='tattoo', regions=region, size=size, style=style, emblem=emblem, lore='fits', adult=adult, quality='ok', note=note), 1)
# Ordinary life
add('TanTshirt', BOTH, 'tan_lines', ('tshirt',), 1024, dict(ROUGH, kind='tan', regions=[], size='full', note="a farmer's tan"), 1)
add('TanTank', BOTH, 'tan_lines', ('tank',), 1024, dict(ROUGH, kind='tan', regions=[], size='full', note='tank-top tan lines'), 1)
add('TanBikini', F, 'tan_lines', ('bikini',), 1024, dict(ROUGH, kind='tan', regions=[], size='full', note='bikini tan lines'), 1)
add('TanShorts', M, 'tan_lines', ('shorts',), 1024, dict(ROUGH, kind='tan', regions=[], size='full', note='a tan with shorts lines'), 1)
add('Sunburn', BOTH, 'sunburn', (), 1024, dict(ROUGH, kind='tan', regions=[], size='large', note='sunburn, peeling'), 2)
add('Mud', BOTH, 'mud', (0.6,), 1024, dict(ROUGH, kind='dirt', regions=[], size='medium', note='mud on the legs'), 2)
add('AgeSpots', BOTH, 'age_spots', (), 2048, dict(ROUGH, kind='skin', regions=[], size='small', note='age spots'), 2)
add('Varicose', BOTH, 'varicose', (), 2048, dict(ROUGH, kind='skin', regions=[], size='small', note='varicose and spider veins'), 1)
add('Cellulite', F, 'cellulite', (), 1024, dict(ROUGH, kind='skin', regions=[], size='medium', note='cellulite'), 2)
for which, sexes in (('appendix', BOTH), ('caesarean', F), ('sternum', BOTH), ('knee', BOTH)):
    add(f'Surgery{which.title()}', sexes, 'surgery_scar', (which,), 2048, dict(ROUGH, kind='scar', regions=[], size='small', note=f'a surgery scar ({which})'), 1)
for colour in ('brown', 'black'):
    add(f'BackHair{colour.title()}', M, 'back_hair', (colour,), 2048, dict(ROUGH, kind='body_hair', regions=['back'], size='large', note=f'back hair, {colour}'), 1)
    add(f'HappyTrail{colour.title()}', M, 'happy_trail', (colour,), 2048, dict(ROUGH, kind='body_hair', regions=[], size='small', note=f'a happy trail, {colour}'), 1)
    add(f'Underarm{colour.title()}', F, 'underarm_hair', (colour,), 2048, dict(ROUGH, kind='body_hair', regions=[], size='tiny', note=f'unshaved underarms, {colour}'), 1)
AUBURN, BLOND = (0.32, 0.15, 0.08), (0.55, 0.42, 0.26)
add('PubicFullAuburn', M, 'pubic_hair', ('full', 2048, AUBURN), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='large', note='full pubic hair, auburn'), 1)
add('PubicFullBlond', M, 'pubic_hair', ('full', 2048, BLOND), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='large', note='full pubic hair, blond'), 1)
add('PubicTrimBlond', M, 'pubic_hair', ('trim', 2048, BLOND), 2048, dict(ROUGH, kind='pubic_hair', regions=['pubic'], size='small', note='trimmed pubic hair, blond'), 1)
# Wrapped tattoos: (name, design, where, side, height, ink, crude, size, style, sexes, note)
WRAPS = [
    ('ArmbandBarbed', ('barbed',), 'upper_arm', 1, 2.2, 'fresh', 0.3, 'small', ['crude', 'tribal'], BOTH, 'a barbed-wire armband'),
    ('ArmbandTribal', ('band', 0), 'upper_arm', -1, 2.4, 'fresh', 0.0, 'small', ['tribal'], BOTH, 'a tribal armband'),
    ('ArmbandKnots', ('band', 1), 'forearm', 1, 2.0, 'faded', 0.0, 'small', ['geometric'], BOTH, 'a knotwork band on the forearm'),
    ('AnkleChain', ('chain',), 'ankle', -1, 1.2, 'fresh', 0.0, 'tiny', ['geometric'], BOTH, 'a chain round the ankle'),
    ('ThighGarter', ('garter',), 'thigh', 1, 2.6, 'fresh', 0.0, 'small', ['floral', 'pinup'], F, 'a lace garter round the thigh'),
    ('SleeveTribal', ('sleeve',), 'forearm', -1, 9, 'fresh', 0.0, 'large', ['tribal'], BOTH, 'a tribal sleeve on the forearm'),
    ('SleeveCalf', ('sleeve',), 'calf', 1, 9, 'fresh', 0.0, 'large', ['tribal'], BOTH, 'a tribal sleeve on the calf'),
]
for name, spec, where, side, height, ink, crude, size, style, sexes, note in WRAPS:
    region = (['arm_r'] if side > 0 else ['arm_l']) if where in ('upper_arm', 'forearm', 'wrist') else (['leg_r'] if side > 0 else ['leg_l'])
    add(f'Tattoo{name}', sexes, 'wrap', (spec, where, side, height, ink, crude), 2048,
        dict(kind='tattoo', regions=region, size=size, style=style, emblem=None, lore='fits', adult=False, quality='ok', note=note), 1)
# Nails: the hands mesh, LooksMenu slot 4 (hands.py)
NAILS = dict(ROUGH, kind='nails', regions=['hand_l', 'hand_r'], size='tiny')
for style, chipped, sexes in (('red', False, F), ('black', False, F), ('purple', False, F), ('pink', False, F),
                              ('red', True, F), ('black', True, BOTH), ('dirty', False, BOTH)):
    note = 'dirty nails' if style == 'dirty' else f'{"chipped " if chipped else ""}{style} nails'
    add(f'Nails{style.title()}{"Chipped" if chipped else ""}', sexes, 'nails', (style, chipped), 1024, dict(NAILS, note=note), 1)
HAND_PAINTERS = {'nails'}
# Marks that belong AT a seam with the head or hands (seams.py): every other body mark fades out before them.
SEAM_EXEMPT = {'collar', 'bindings', 'shackles'}

# ---- C-17 (owner, 2026-10-03): our own art tattoos, traditional flash (flash.py), so every faction's tattoo styles
# have our own art and the LoversLab packs are optional extra variety. Appended last: earlier seeds stay put.
# (name, motif, motif args, spot, side, width, faded, crude, size, styles)
FLASH = [
    ('Rose', 'rose', (), 'forearm', 1, 5.0, False, 0.0, 'small', ['floral']),
    ('RoseChest', 'rose', (), 'chest', -1, 5.0, False, 0.0, 'small', ['floral']),
    ('RoseThigh', 'rose', (), 'thigh', 1, 6.5, True, 0.0, 'medium', ['floral']),
    ('RoseYellow', 'rose', ((226, 178, 44),), 'shoulder', -1, 5.0, False, 0.0, 'small', ['floral']),
    ('Skull', 'skull', (), 'forearm', -1, 4.5, False, 0.2, 'small', ['skull']),
    ('SkullBack', 'skull', (), 'upper_back', 0, 9.0, True, 0.2, 'medium', ['skull']),
    ('SkullBones', 'skull_bones', (), 'chest', 0, 8.0, False, 0.3, 'medium', ['skull', 'crude']),
    ('SkullCalf', 'skull', ((170, 28, 32),), 'calf', 1, 5.0, False, 0.0, 'small', ['skull']),
    ('Dagger', 'dagger', (), 'forearm', 1, 3.2, False, 0.0, 'small', ['crude', 'military']),
    ('DaggerCalf', 'dagger', ((36, 72, 150),), 'calf', -1, 3.6, True, 0.0, 'small', ['crude']),
    ('HeartMom', 'heart_banner', ('MOM',), 'upper_arm', 1, 5.5, True, 0.0, 'small', ['script', 'floral']),
    ('HeartTrueLove', 'heart_banner', ('TRUE LOVE',), 'chest', 1, 6.0, False, 0.0, 'small', ['script', 'pinup']),
    ('HeartNuka', 'heart_banner', ('NUKA',), 'hip', -1, 5.0, False, 0.0, 'small', ['script', 'cartoon']),
    ('SwallowPair', 'swallow_pair', (), 'chest', 0, 12.0, False, 0.0, 'medium', ['animal']),
    ('Swallow', 'swallow', (), 'hip', 1, 5.0, False, 0.0, 'small', ['animal']),
    ('SwallowNeck', 'swallow', ((170, 28, 32),), 'neck_back', 0, 4.0, False, 0.0, 'tiny', ['animal']),
    ('Anchor', 'anchor', (), 'forearm', -1, 4.0, True, 0.0, 'small', ['military']),
    ('AnchorCalf', 'anchor', (), 'calf', -1, 4.5, False, 0.0, 'small', ['military']),
    ('Snake', 'snake', (), 'forearm', 1, 5.5, False, 0.0, 'small', ['animal']),
    ('SnakeThigh', 'snake', ((36, 72, 150),), 'thigh', -1, 7.0, False, 0.0, 'medium', ['animal']),
    ('Web', 'web', (), 'upper_arm', 1, 5.0, True, 0.3, 'small', ['crude']),
    ('WebShoulder', 'web', (), 'shoulder', -1, 6.0, False, 0.2, 'small', ['crude', 'geometric']),
    ('Spider', 'spider', (), 'neck_back', 0, 3.0, False, 0.2, 'tiny', ['animal', 'crude']),
    ('SpiderArm', 'spider', (), 'forearm', -1, 3.0, False, 0.0, 'tiny', ['animal']),
    ('NauticalStar', 'nautical_star', (), 'shoulder', 1, 4.0, False, 0.0, 'small', ['geometric', 'military']),
    ('NauticalStarHip', 'nautical_star', ((36, 72, 150),), 'hip', -1, 3.6, False, 0.0, 'tiny', ['geometric']),
    ('Lightning', 'lightning', (), 'forearm', -1, 3.0, False, 0.0, 'tiny', ['geometric']),
    ('MushroomCloud', 'mushroom_cloud', (), 'upper_back', 0, 9.0, False, 0.0, 'medium', ['religious', 'cartoon']),
    ('MushroomCloudArm', 'mushroom_cloud', (), 'upper_arm', -1, 5.0, True, 0.2, 'small', ['religious', 'crude']),
    ('Radiation', 'radiation', (), 'shoulder', -1, 4.5, False, 0.0, 'small', ['geometric', 'religious']),
    ('NukaCap', 'nuka_cap', (), 'forearm', 1, 4.0, False, 0.0, 'small', ['cartoon']),
    ('Cherries', 'cherries', (), 'hip', 1, 4.0, False, 0.0, 'small', ['pinup', 'cartoon']),
    ('Eye', 'eye', (), 'upper_back', 0, 7.0, False, 0.0, 'medium', ['religious', 'geometric']),
    ('Flames', 'flames', (), 'calf', -1, 7.0, False, 0.0, 'small', ['tribal', 'crude']),
    ('FlamesArm', 'flames', (), 'forearm', 1, 6.0, False, 0.0, 'small', ['tribal']),
    ('Wolf', 'wolf', (), 'upper_arm', -1, 5.5, False, 0.0, 'small', ['animal', 'geometric']),
    ('WolfBack', 'wolf', (), 'upper_back', 0, 10.0, False, 0.0, 'medium', ['animal', 'geometric']),
    ('Eagle', 'eagle', (), 'chest', 0, 11.0, False, 0.0, 'medium', ['animal', 'military']),
    ('EagleBack', 'eagle', (), 'upper_back', 0, 14.0, True, 0.0, 'large', ['animal', 'military']),
    ('Koi', 'koi', (), 'thigh', 1, 7.0, False, 0.0, 'medium', ['animal', 'floral']),
    ('KoiCalf', 'koi', ((170, 28, 32),), 'calf', -1, 5.0, False, 0.0, 'small', ['animal']),
    ('Butterfly', 'butterfly', (), 'lower_back', 0, 6.0, False, 0.0, 'small', ['animal', 'floral']),
    ('ButterflyHip', 'butterfly', ((96, 46, 130),), 'hip', 1, 4.0, False, 0.0, 'small', ['animal', 'floral']),
    ('Revolver', 'revolver', (), 'hip', -1, 6.0, False, 0.2, 'small', ['military', 'crude']),
    ('Grenade', 'grenade', (), 'forearm', -1, 3.5, False, 0.0, 'tiny', ['military']),
    ('Tombstone', 'tombstone', (), 'calf', 1, 4.5, True, 0.0, 'small', ['skull', 'script']),
    ('EightBall', 'eight_ball', (), 'forearm', 1, 3.5, False, 0.0, 'tiny', ['gambling', 'cartoon']),
    ('Compass', 'compass', (), 'forearm', -1, 4.5, False, 0.0, 'small', ['geometric']),
    ('CompassBack', 'compass', (), 'upper_back', 0, 9.0, True, 0.0, 'medium', ['geometric']),
]
for name, motif, margs, spot, side, width, faded, crude, size, style in FLASH:
    region = (['arm_r'] if side > 0 else ['arm_l']) if spot in ('forearm', 'upper_arm') else \
        ((['leg_r'] if side > 0 else ['leg_l']) if spot in ('thigh', 'calf') else [SPOT_REGION[spot]])
    add(f'Flash{name}', BOTH, 'flash', (motif, margs, spot, side, width, faded, crude), 2048,
        dict(kind='tattoo', regions=region, size=size, style=style, emblem=None, lore='fits', adult=False, quality='ok',
             note=f'flash: {motif.replace("_", " ")}'), 1)

# ---- 2026-10-03 (owner: "especially important"): areolas centred on the measured nipple, in four tones and in
# small and large; the earlier three keep their random size. Appended last: earlier seeds stay put.
add('NipplesRose', F, 'nipples', ('rose', True), 2048, dict(ROUGH, kind='nipple', regions=['breasts'], size='small', note='rose areolas'), 1)
for tone in ('pink', 'rose', 'brown', 'dark'):
    for label, size in (('Small', 1.35), ('Large', 2.15)):
        add(f'Nipples{tone.title()}{label}', F, 'nipples', (tone, True, size), 2048,
            dict(ROUGH, kind='nipple', regions=['breasts'], size='small' if label == 'Small' else 'medium',
                 note=f'{label.lower()} {tone} areolas'), 1)

# ---- 2026-10-03 (owner: "the accent on the realistic module"): the realism layer in real variety, and the kinds
# still missing -- skin.py. Appended last: earlier seeds stay put. Painter names 'skin.<fn>' (paint() dispatch).
R = ROUGH
MOLE_VARIANTS = [  # name, args (count, size, tone, zone, clusters, raised), note
    ('MolesScattered', ((25, 50), (0.06, 0.16), 'brown', 'everywhere', 0, False), 'scattered small moles'),
    ('MolesFewLarge', ((4, 9), (0.18, 0.32), 'dark', 'everywhere', 0, True), 'a few large raised moles'),
    ('MolesClustered', ((25, 45), (0.06, 0.18), 'brown', 'everywhere', 4, False), 'moles in clusters'),
    ('MolesBack', ((20, 40), (0.06, 0.2), 'dark', 'back', 0, False), 'moles over the back'),
    ('MolesFront', ((12, 28), (0.06, 0.18), 'brown', 'front', 0, False), 'moles on the chest and belly'),
    ('MolesLight', ((20, 45), (0.07, 0.2), 'light', 'everywhere', 0, False), 'light-brown flat moles'),
    ('MolesMany', ((60, 110), (0.04, 0.13), 'brown', 'everywhere', 0, False), 'many small moles'),
    ('MolesRaisedDark', ((8, 18), (0.12, 0.24), 'dark', 'upper', 0, True), 'dark raised moles, upper body'),
]
for name, args, note in MOLE_VARIANTS:
    add(name, F, 'skin.moles', args, 2048, dict(R, kind='mole', regions=[], size='tiny', note=note), 2)
    add(name, M, 'skin.moles', args, 2048, dict(R, kind='mole', regions=[], size='tiny', note=note), 1)
add('CherryAngiomas', BOTH, 'skin.cherry_angiomas', (), 2048, dict(R, kind='mole', regions=[], size='tiny', note='tiny red cherry angiomas'), 2)
add('SunSpots', BOTH, 'skin.sun_spots', (0.5,), 2048, dict(R, kind='freckles', regions=[], size='small', note='sun spots on the shoulders'), 1)
add('SunSpotsHeavy', BOTH, 'skin.sun_spots', (1.0,), 2048, dict(R, kind='freckles', regions=[], size='medium', note='heavy sun spots'), 1)
add('PortWine', BOTH, 'skin.port_wine', (3.5,), 2048, dict(R, kind='birthmark', regions=[], size='medium', note='a port-wine stain'), 2)
add('PortWineLarge', BOTH, 'skin.port_wine', (6.0,), 2048, dict(R, kind='birthmark', regions=[], size='large', note='a large port-wine stain'), 1)
add('CafeAuLait', BOTH, 'skin.cafe_au_lait', ((2, 5),), 2048, dict(R, kind='birthmark', regions=[], size='small', note='cafe-au-lait spots'), 2)
add('MongolianSpot', BOTH, 'skin.mongolian_spot', (), 2048, dict(R, kind='birthmark', regions=['lower_back'], size='medium', note='a slate-blue birthmark low on the back'), 1)
add('LineaNigra', F, 'skin.linea_nigra', (0.30,), 2048, dict(R, kind='skin', regions=[], size='small', note='a faint pregnancy line'), 1)
add('LineaNigraDark', F, 'skin.linea_nigra', (0.5,), 2048, dict(R, kind='skin', regions=[], size='small', note='a dark pregnancy line'), 1)
add('FlushChest', BOTH, 'skin.flush', ('chest',), 1024, dict(R, kind='skin', regions=[], size='medium', note='blotchy redness on the chest'), 2)
add('FlushButtocks', BOTH, 'skin.flush', ('buttocks',), 1024, dict(R, kind='skin', regions=[], size='medium', note='blotchy redness on the buttocks'), 1)
add('KeratosisArms', BOTH, 'skin.flush', ('arms',), 2048, dict(R, kind='skin', regions=[], size='small', note='rough red bumps on the upper arms'), 1)
add('Goosebumps', BOTH, 'skin.goosebumps', ('arms',), 2048, dict(R, kind='skin', regions=[], size='medium', note='goosebumps on the arms'), 1)
add('GoosebumpsAll', BOTH, 'skin.goosebumps', ('arms_legs',), 2048, dict(R, kind='skin', regions=[], size='large', note='goosebumps on arms and legs'), 1)
# scars -- women had none of ours; both get lengths, widths, ages
for name, args, n_f, n_m, note in (
        ('Scar', ((1, 3), (3.5, 8.0), (0.25, 0.45), False, 'everywhere', 'old'), 3, 0, 'healed scars'),
        ('ScarStitched', ((1, 2), (3.0, 6.0), (0.25, 0.4), True, 'everywhere', 'old'), 2, 0, 'stitched scars'),
        ('ScarThin', ((2, 5), (2.0, 5.0), (0.12, 0.2), False, 'everywhere', 'old'), 2, 2, 'thin pale scars'),
        ('ScarLong', ((1, 1), (9.0, 14.0), (0.3, 0.5), False, 'upper', 'old'), 1, 2, 'one long scar'),
        ('ScarNewer', ((1, 2), (3.0, 7.0), (0.25, 0.4), False, 'everywhere', 'newer'), 2, 2, 'newer pink scars'),
        ('ScarArms', ((2, 4), (1.5, 4.0), (0.15, 0.3), False, 'arms', 'old'), 1, 2, 'scars on the arms'),
        ('ScarLegs', ((2, 4), (2.0, 5.0), (0.2, 0.35), False, 'legs', 'old'), 1, 1, 'scars on the legs')):
    if n_f:
        add(name, F, 'skin.scars', args, 2048, dict(R, kind='scar', regions=[], size='small', note=note), n_f)
    if n_m:
        add(name if name not in ('Scar', 'ScarStitched') else name + 'More', M, 'skin.scars', args, 2048,
            dict(R, kind='scar', regions=[], size='small', note=note), n_m)
add('Keloid', BOTH, 'skin.keloid', ('chest',), 2048, dict(R, kind='scar', regions=['chest'], size='small', note='a keloid scar on the chest'), 1)
add('KeloidArm', BOTH, 'skin.keloid', ('arms',), 2048, dict(R, kind='scar', regions=[], size='small', note='a keloid scar on an arm'), 1)
add('Vaccination', BOTH, 'skin.vaccination', (-1, 1), 2048, dict(R, kind='scar', regions=['arm_l'], size='tiny', note='a smallpox vaccination scar'), 1)
add('VaccinationTwo', BOTH, 'skin.vaccination', (-1, 2), 2048, dict(R, kind='scar', regions=['arm_l'], size='tiny', note='two vaccination scars'), 1)
add('BiteScarDog', BOTH, 'skin.bite_scar', ('dog',), 2048, dict(R, kind='scar', regions=[], size='small', note='a healed dog bite'), 2)
add('BiteScarHuman', BOTH, 'skin.bite_scar', ('human',), 2048, dict(R, kind='scar', regions=[], size='small', note='a healed human bite'), 1)
# freckles, pores, stretch marks, acne -- in variety
for name, args, note in (('FrecklesShoulders', (0.5, 'shoulders'), 'freckles on the shoulders'),
                         ('FrecklesDense', (1.0, 'upper'), 'dense freckles'),
                         ('FrecklesFaint', (0.25, 'upper'), 'a few faint freckles'),
                         ('FrecklesArms', (0.6, 'arms'), 'freckled arms'),
                         ('FrecklesEverywhere', (0.9, 'everywhere'), 'freckles all over'),
                         ('FrecklesGinger', (1.0, 'everywhere', (0.03, 0.08), 'ginger'), 'ginger freckles all over'),
                         ('FrecklesDark', (0.6, 'upper', (0.03, 0.07), 'medium'), 'darker freckles')):
    add(name, BOTH, 'skin.freckles', args, 2048, dict(R, kind='freckles', regions=[], size='medium', note=note), 1)
add('PoresFine', BOTH, 'skin.pores', (0.6, 9.0), 2048, dict(R, kind='skin', regions=[], size='full', note='fine skin texture'), 1)
add('PoresCoarse', BOTH, 'skin.pores', (0.9, 4.0), 2048, dict(R, kind='skin', regions=[], size='full', note='coarse skin texture'), 1)
for zone in ('hips', 'belly', 'breasts', 'thighs', 'buttocks', 'shoulders'):
    sexes = F if zone == 'breasts' else (M if zone == 'shoulders' else BOTH)
    for fresh in (False, True):
        add(f'Stretch{zone.title()}{"Fresh" if fresh else "Old"}', sexes, 'skin.stretch', (zone, fresh), 2048,
            dict(R, kind='skin', regions=[], size='small', note=f'{"fresh" if fresh else "old"} stretch marks, {zone}'), 1)
for zone, amount in (('back', 0.7), ('chest', 0.5), ('buttocks', 0.5), ('shoulders', 0.6), ('back', 0.25)):
    add(f'Acne{zone.title()}{"Light" if amount < 0.4 else ""}', BOTH, 'skin.acne', (zone, amount), 2048,
        dict(R, kind='acne', regions=[], size='small', note=f'acne, {zone}'), 1)
# pubic hair: more colours and styles
for colour in ('ginger', 'lightbrown', 'darkbrown', 'grey'):
    add(f'PubicNatural{colour.title()}', F, 'pubic_female', ('natural', colour), 2048, dict(R, kind='pubic_hair', regions=['pubic'], size='large', note=f'natural pubic hair, {colour}'), 1)
for style, colours, size in (('bushy', ('brown', 'black', 'ginger', 'darkbrown'), 'large'),
                             ('bikini', ('brown', 'black', 'blond', 'ginger'), 'small'),
                             ('stubble', ('darkbrown', 'lightbrown'), 'small'),
                             ('heart', ('brown', 'black'), 'small')):
    for colour in colours:
        add(f'Pubic{style.title()}{colour.title()}', F, 'skin.pubic_female', (style, colour), 2048,
            dict(R, kind='pubic_hair', regions=['pubic'], size=size, note=f'{style} pubic hair, {colour}'), 1)
for colour in ('ginger', 'darkbrown', 'lightbrown'):
    add(f'PubicFull{colour.title()}', M, 'pubic_hair', ('full', 2048, HAIR_RGB[colour]), 2048, dict(R, kind='pubic_hair', regions=['pubic'], size='large', note=f'full pubic hair, {colour}'), 1)
    add(f'PubicTrim{colour.title()}', M, 'pubic_hair', ('trim', 2048, HAIR_RGB[colour]), 2048, dict(R, kind='pubic_hair', regions=['pubic'], size='small', note=f'trimmed pubic hair, {colour}'), 1)
# body hair: chest patterns and colours, limbs, backs; women's fine trail
for pattern in ('light', 'sternum', 'heavy', 'full'):
    for colour in (('brown', 'black', 'ginger', 'blond') if pattern != 'full' else ('ginger', 'blond', 'darkbrown')):
        add(f'Chest{pattern.title()}{colour.title()}', M, 'skin.chest_hair', (pattern, colour), 2048,
            dict(R, kind='body_hair', regions=['chest'], size='medium', note=f'{pattern} chest hair, {colour}'), 1)
for colour, amount in (('blond', 1.0), ('ginger', 1.0), ('black', 1.4), ('brown', 0.5)):
    add(f'LimbHair{colour.title()}{"Heavy" if amount > 1.2 else ("Light" if amount < 0.8 else "")}', M, 'skin.limb_hair', (colour, amount), 2048,
        dict(R, kind='body_hair', regions=[], size='medium', note=f'arm and leg hair, {colour}'), 1)
for colour, amount in (('brown', 0.5), ('black', 1.0), ('grey', 0.7)):
    add(f'BackHair{colour.title()}{"Light" if amount < 0.8 else "Heavy"}', M, 'skin.back_hair', (colour, amount), 2048,
        dict(R, kind='body_hair', regions=['back'], size='large', note=f'back hair, {colour}'), 1)
for colour in ('brown', 'blond', 'ginger'):
    add(f'Underarm{colour.title()}More', F, 'underarm_hair', (colour,), 2048, dict(R, kind='body_hair', regions=[], size='tiny', note=f'unshaved underarms, {colour}'), 1)
add('TrailFemale', F, 'skin.female_trail', ('brown',), 2048, dict(R, kind='body_hair', regions=[], size='tiny', note='a faint line of hair below the navel'), 1)
add('TrailFemaleDark', F, 'skin.female_trail', ('darkbrown',), 2048, dict(R, kind='body_hair', regions=[], size='tiny', note='a darker line of hair below the navel'), 1)
# sun: strengths and cuts
for cut, strengths, sexes in (('tshirt', (0.2, 0.45), BOTH), ('sleeve34', (0.32,), BOTH), ('tank', (0.2, 0.45), BOTH),
                              ('bikini', (0.2, 0.45), F), ('onepiece', (0.32, 0.45), F), ('shorts', (0.45,), M)):
    for k, st in enumerate(strengths):
        add(f'Tan{cut.title()}{"Light" if st < 0.3 else ("Dark" if st > 0.4 else "")}', sexes, 'tan_lines', (cut, st), 1024,
            dict(R, kind='tan', regions=[], size='full', note=f'{cut} tan lines'), 1)
add('SunburnMild', BOTH, 'sunburn', (0.55, False), 1024, dict(R, kind='tan', regions=[], size='large', note='mild sunburn'), 1)
add('SunburnSevere', BOTH, 'sunburn', (1.4, True), 1024, dict(R, kind='tan', regions=[], size='large', note='severe sunburn, peeling'), 1)
# the rest, heavier and lighter
add('AgeSpotsHeavy', BOTH, 'skin.sun_spots', (1.3,), 2048, dict(R, kind='skin', regions=[], size='medium', note='heavy age spots'), 1)
add('VaricoseHeavy', BOTH, 'varicose', (), 2048, dict(R, kind='skin', regions=[], size='small', note='varicose veins'), 1)
add('CelluliteMore', F, 'cellulite', (), 1024, dict(R, kind='skin', regions=[], size='medium', note='cellulite'), 2)
for tone in ('pink', 'rose', 'brown', 'dark'):
    for label, size in (('Small', 0.6), ('Large', 1.15)):
        add(f'Nipples{tone.title()}{label}', M, 'nipples', (tone, False, size), 2048,
            dict(R, kind='nipple', regions=['chest'], size='tiny', note=f'{label.lower()} {tone} nipples'), 1)


def design(spec, rng):
    kind, *rest = spec
    if kind == 'vault':
        return decals.vault_number(rest[0])
    if kind in ('card', 'dice', 'lucky', 'dollar'):
        return getattr(decals, kind)()
    if kind == 'band':
        return decals.band(rng, kind=rest[0])
    if kind in ('barbed', 'chain', 'garter', 'sleeve'):
        return getattr(decals, kind)(rng)
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
    if painter == 'wrap':
        spec, where, side, height, ink, crude = args
        return decals.wrap(m, design(spec, rng), where, side, height=height, ink=ink, crude=crude, seed=int(rng.integers(1 << 30)))
    if painter == 'flash':
        motif, margs, spot, side, width, faded, crude = args
        return flash.project_rgba(m, flash.MOTIFS[motif](*margs), spot, side, width=width, faded=faded, crude=crude,
                                  rotate=float(rng.uniform(-0.15, 0.15)), seed=int(rng.integers(1 << 30)))
    if painter == 'scar_decal':
        spec, spot, side, width = args
        return life.scar_decal(m, rng, design(spec, rng), spot, side, width)
    if painter.startswith('skin.'):
        return getattr(skin, painter[5:])(m, rng, *args)
    for module in (marks, realism, life, hands):
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


def bleed(img, covered, steps=16):
    """Spreads the finished multiplier past the UV islands' edges: every texel off the islands, out to `steps`
    texels, takes the mean of its already-filled neighbours. Without it the off-island texels are neutral, and
    filtering and mipmaps blend that neutral into a dark mark wherever it meets an island's edge -- a pale line
    through the pubic hair, in game 2026-10-03. Only off-island texels change, recomputed from the islands each
    time, so running it twice gives the same texture."""
    tex = np.asarray(img, dtype=np.float64).copy()
    have = covered.copy()
    for _ in range(steps):
        acc = np.zeros_like(tex)
        cnt = np.zeros(have.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(have, (dy, dx), (0, 1))
            acc += np.roll(tex, (dy, dx), (0, 1)) * sh[..., None]
            cnt += sh
        new = (~have) & (cnt > 0)
        tex[new] = acc[new] / cnt[new][:, None]
        have = have | new
    return Image.fromarray(np.clip(tex + 0.5, 0, 255).astype(np.uint8), 'RGB')


def encode(tool, png, tex_dir, tid):
    """The PNG to BC7 with mipmaps, named as the material names it (BC7: see BASE_COLOUR)."""
    r = subprocess.run([str(tool), '-nologo', '-y', '-ft', 'dds', '-f', 'BC7_UNORM', '-bcmax', '-m', '0', '-o', str(tex_dir), str(png)],
                       capture_output=True, text=True)
    made = next((f for f in tex_dir.iterdir() if f.name.lower() == f'{tid}_d.dds'.lower()), None)
    if r.returncode or not made:
        sys.exit(f'texconv failed on {png}: {r.stdout[-300:]} {r.stderr[-300:]}')
    if made.name != f'{tid}_d.dds':
        made.rename(tex_dir / f'{tid}_d.dds')  # texconv writes .DDS; the material names .dds


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
    ap.add_argument('--shard', default='', help='k/N: paint only every Nth template from the k-th (run N at once)')
    ap.add_argument('--rebleed', action='store_true', help='apply bleed() to the finished PNGs and re-encode (no repaint)')
    a = ap.parse_args()
    tex_dir = ROOT / 'data' / 'Textures' / 'Overlays' / 'Complexion'
    mat_dir = ROOT / 'data' / 'Materials' / 'Overlays' / 'Complexion'
    json_dir = ROOT / 'data' / 'F4SE' / 'Plugins' / 'F4EE' / 'Overlays' / 'Complexion.esp'
    work = ROOT / 'build' / 'marks'
    for d in (tex_dir, mat_dir, json_dir, work):
        d.mkdir(parents=True, exist_ok=True)
    tool = texconv()
    maps = {}
    if a.rebleed:
        for tid, sex, painter, args, size, tag in MARKS:
            png = work / f'{tid}_d.png'
            if a.only and not tid.startswith(a.only):
                continue
            if not png.exists():
                print(f'  {tid}: no PNG, repaint it')
                continue
            on_hands = painter in HAND_PAINTERS
            img = Image.open(png).convert('RGB')
            key = (sex, img.size[0], on_hands)
            if key not in maps:
                maps[key] = hands.HandMap(a.data, sex, img.size[0]) if on_hands else UVMap(a.data, sex, img.size[0])
            bleed(img, maps[key].covered).save(png)
            encode(tool, png, tex_dir, tid)
        print('re-bled')
        return
    entries, tags = [], {}
    for n, (tid, sex, painter, args, size, tag) in enumerate(MARKS):
        female = sex == 'female'
        on_hands = painter in HAND_PAINTERS
        # The body is LooksMenu slot 3, the hands slot 4 (as the packs' nails, LMNSOverlays f_nails_1).
        entries.append({'id': tid, 'name': f'Complexion - {tag["note"]}',
                        'slots': [{'slot': 4 if on_hands else 3, 'material': f'overlays\\Complexion\\{tid}.bgem'}],
                        'playable': True, 'transformable': not on_hands, 'sort': 0, 'gender': 1 if female else 0})
        if tag['kind'] in hair.HAIR_KINDS:
            tag = dict(tag, hair=hair.family(painter, args))  # one colour per person: the composer matches it
        tag = dict(tag, **traits.of(tag))  # nasty / age / tones (tools/paint/traits.py)
        tags[('f:' if female else 'm:') + tid] = tag
        if a.only and not tid.startswith(a.only):
            continue
        if a.shard and n % int(a.shard.split('/')[1]) != int(a.shard.split('/')[0]):
            continue
        if a.missing and (tex_dir / f'{tid}_d.dds').exists():
            continue
        key = (sex, size, on_hands)
        if key not in maps:
            maps[key] = hands.HandMap(a.data, sex, size) if on_hands else UVMap(a.data, sex, size)
        m = maps[key]
        rng = np.random.default_rng(1000 + n)
        rgb, alpha = paint(painter, m, rng, args)
        if not on_hands and painter not in SEAM_EXEMPT:
            alpha = alpha * seams.seam_fade(m)  # no hard line against the head or hands (owner, 10-03)
        rgb = dilate(rgb, alpha, m.covered)
        img = bleed(multiplier(rgb, alpha), m.covered)
        png = work / f'{tid}_d.png'
        img.save(png)
        encode(tool, png, tex_dir, tid)
        (mat_dir / f'{tid}.bgem').write_bytes(bgem(f'overlays/Complexion/{tid}_d.dds', (hands.NORMAL if on_hands else NORMAL)[sex]))
        print(f'  {tid}: {painter}{args} {size}px, {float((alpha > 0.05).mean()) * 100:.1f}% of the map')
        del rgb, alpha, img  # the full-res arrays: kept for a preview sheet they grew ~130 MB per template (every OOM, 10-03)
    (json_dir / 'overlays.json').write_text(json.dumps(entries, indent=1), encoding='utf-8', newline='\n')
    (ROOT / 'data' / 'tags' / 'complexion.json').write_text(json.dumps(tags, indent=1), encoding='utf-8', newline='\n')
    # Review sheets come from the finished textures: tools/paint/review.py (and review_hands.py).
    print(f'{len(entries)} templates; textures in {tex_dir}')


if __name__ == '__main__':
    main()
