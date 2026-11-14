"""Complexion's face tints: the synthetic skin's face (alasdairn, 11-13: "All at once", for the vanilla male and
female heads and Ace Male Race's head).

    python tools/paint/make_faces.py

Writes, all generated (never edit by hand):
- data/Textures/Complexion/Face/<name>.dds   BC7 with mipmaps, 1024 (TCD's face tints are 1024), two looks per head:
  SynthSkin_* (synthskin.pack_face, blend "Multiply": the seams darken the face) and SynthPlated_*
  (synthskin.plated_face, blend "Default": his synthetic surface laid over it)
- data/F4SE/Plugins/F4EE/Tints/Complexion.esp/categories.json, templates.json   LooksMenu's face tints, one
  category of Complexion's own (a reused category name once turned women's faces pale: shared memory
  looksmenu-tint-json-unique-category-names), a "FaceDetail" texture set per head
- build/faces/<name>.png   the painted RGBA, for review sheets

A race LooksMenu cannot find is skipped silently (f4ee CharGenInterface.cpp: `if(race)`), so the Ace Male entry is
harmless where Ace Male Race is not installed.
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import face  # noqa: E402
import make_marks as mm  # noqa: E402
import synth55413
import synthskin  # noqa: E402

ROOT = HERE.parent.parent
SIZE = 1024
CATEGORY = 'Complexion Synthetic Skin'
# Tint ids are per race and saved with the character; the game keeps them in 16 bits. Kept clear of the vanilla
# range and of TCD's (1411..., 14102...).
CATEGORY_ID = 60968
HEADS = ('human_male', 'human_female', 'ace_male')
HEAD_NAMES = {'human_male': 'HumanMale', 'human_female': 'HumanFemale', 'ace_male': 'AceMale'}
# Two looks, each a texture per head, picked by hand in the same category:
# Seams -- his seam lines only, darkening the face (blend Multiply: white leaves it as it is);
# Plated -- his synthetic surface with darker, wider seams, laid over the face (blend Default).
VARIANTS = (   # (prefix, painter, blend, first tint id, name in LooksMenu)
    ('SynthSkin', synthskin.pack_face, 'Multiply', 60969, 'Complexion - Synthetic Skin (Seams)'),
    ('SynthPlated', synthskin.plated_face, 'Default', 60972, 'Complexion - Synthetic Skin (Plated)'),
    # from Synth Looksmenu Skin Override (Nexus 55413; textures Aaron4412): its synth face, and its lines only
    ('SynthPanels', synth55413.panels_face, 'Default', 60975, 'Complexion - Synthetic Skin (Panels)'),
    ('SynthPanelLines', synth55413.panel_lines_face, 'Multiply', 60978, 'Complexion - Synthetic Skin (Panel Lines)'),
)


def main():
    tex_dir = ROOT / 'data' / 'Textures' / 'Complexion' / 'Face'
    json_dir = ROOT / 'data' / 'F4SE' / 'Plugins' / 'F4EE' / 'Tints' / 'Complexion.esp'
    work = ROOT / 'build' / 'faces'
    for d in (tex_dir, json_dir, work):
        d.mkdir(parents=True, exist_ok=True)
    tool = mm.texconv()
    races = {}
    templates = {}
    for prefix, painter, blend, first_id, label in VARIANTS:
        for k, head in enumerate(HEADS):
            name, tid = f'{prefix}_{HEAD_NAMES[head]}', first_id + k
            m = face.HeadMap(head, SIZE)
            rgba = painter(m)
            rgb = mm.bleed(Image.fromarray((np.clip(rgba[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB'), m.covered)
            alpha = rgba[..., 3]
            png = work / f'{name}.png'
            a = Image.fromarray((np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8), 'L')
            Image.merge('RGBA', (*rgb.split(), a)).save(png)
            r = mm.subprocess.run([str(tool), '-nologo', '-y', '-ft', 'dds', '-f', 'BC7_UNORM', '-bcmax', '-m', '0', '-o', str(tex_dir), str(png)],
                                  capture_output=True, text=True)
            made = next((f for f in tex_dir.iterdir() if f.name.lower() == f'{name}.dds'.lower()), None)
            if r.returncode or not made:
                sys.exit(f'texconv failed on {png}: {r.stdout[-300:]} {r.stderr[-300:]}')
            if made.name != f'{name}.dds':
                made.rename(tex_dir / f'{name}.dds')
            races.setdefault(m.race, set()).add(m.gender)
            templates.setdefault(m.race, []).append({
                'BlendOp': blend, 'FixedCategory': CATEGORY, 'Diffuse': f'Complexion\\Face\\{name}.dds',
                'Flags': ['ChargenDetail'], 'Gender': m.gender, 'Id': tid, 'Name': label, 'Normal': None,
                'Slot': 'FaceDetail', 'Specular': None, 'Type': 'TextureSet'})
            print(f'  {head}: {name}.dds ({m.race}, gender {m.gender}, {blend})')
    categories = [{'Entries': [{'Gender': 2, 'Id': CATEGORY_ID, 'Name': CATEGORY, 'Type': 'Category'}], 'Race': race}
                  for race in races]
    tmpl = [{'Entries': entries, 'Race': race} for race, entries in templates.items()]
    (json_dir / 'categories.json').write_text(json.dumps(categories, indent=1), encoding='utf-8', newline='\n')
    (json_dir / 'templates.json').write_text(json.dumps(tmpl, indent=1), encoding='utf-8', newline='\n')
    print(f'face tints -> {json_dir}')


if __name__ == '__main__':
    main()
