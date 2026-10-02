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
import marks  # noqa: E402
from body import UVMap  # noqa: E402
from preview import sheet  # noqa: E402

ROOT = HERE.parent.parent
DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')
TEXCONV = [pathlib.Path(r'D:\xEdit.4.1.5f\Edit Scripts\Texconvx64.exe'), pathlib.Path(r'D:\DynDOLOD\Edit Scripts\Texconvx64.exe')]
NORMAL = {'female': 'actors/character/basehumanfemale/FemaleBody_n.dds',
          'male': 'actors/character/basehumanmale/BaseMaleBody_n.dds'}
BGEM_HEAD = bytes.fromhex(
    '4247454d020000000300000000000000000000000000803f0000803f0000803f01060000000700000000010101010000000000000000'
    '000000000000803f00')
BGEM_MID = bytes.fromhex('01000000000100000000')
# The tail after the normal map: the empty envmap-mask string (5), then six flags -- blood, EFFECT LIGHTING,
# falloff, falloff colour, greyscale-to-palette alpha, soft -- then the base colour (3 floats) and its scale,
# falloff start/stop angle and opacity (4 floats), LIGHTING INFLUENCE, envmap min LOD (1 byte), soft depth.
# INVB's has effect lighting off: an effect material is then unlit, and anything pale glows in the dark.
BGEM_TAIL = bytes.fromhex(
    '0100000000' '000100000000' '0000803f0000803f0000803f' '0000803f' '00000000000000000000000000000000'
    '0000803f' '00' '00000000')
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
        if (sex, size) not in maps:
            maps[(sex, size)] = UVMap(a.data, sex, size)
        m = maps[(sex, size)]
        rng = np.random.default_rng(1000 + n)
        rgb, alpha = getattr(marks, painter)(m, rng, *args)
        rgb = dilate(rgb, alpha, m.covered)
        img = Image.fromarray(np.dstack([np.clip(rgb, 0, 1) * 255, np.clip(alpha, 0, 1) * 255]).astype(np.uint8), 'RGBA')
        png = work / f'{tid}_d.png'
        img.save(png)
        r = subprocess.run([str(tool), '-nologo', '-y', '-ft', 'dds', '-f', 'BC3_UNORM', '-m', '0', '-o', str(tex_dir), str(png)],
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
