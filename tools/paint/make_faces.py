"""Complexion's face tints: the synthetic skin's face (alasdairn, 11-13: "All at once", for the vanilla male and
female heads and Ace Male Race's head).

    python tools/paint/make_faces.py

Writes, all generated (never edit by hand):
- data/Textures/Complexion/Face/<name>.dds   BC7 with mipmaps, 1024 (TCD's face tints are 1024): synthskin.pack_face,
  laid over the face with blend "Overlay" (0.5 grey leaves the face as it is, so it keeps its own colour)
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
import synthskin  # noqa: E402

ROOT = HERE.parent.parent
SIZE = 1024
CATEGORY = 'Complexion Synthetic Skin'
# Tint ids are per race and saved with the character; the game keeps them in 16 bits. Kept clear of the vanilla
# range and of TCD's (1411..., 14102...).
CATEGORY_ID = 60968
TEXTURES = {   # head -> (texture name, tint id, name in LooksMenu)
    'human_male': ('SynthSkin_HumanMale', 60969, 'Complexion - Synthetic Skin'),
    'human_female': ('SynthSkin_HumanFemale', 60970, 'Complexion - Synthetic Skin'),
    'ace_male': ('SynthSkin_AceMale', 60971, 'Complexion - Synthetic Skin'),
}


def main():
    tex_dir = ROOT / 'data' / 'Textures' / 'Complexion' / 'Face'
    json_dir = ROOT / 'data' / 'F4SE' / 'Plugins' / 'F4EE' / 'Tints' / 'Complexion.esp'
    work = ROOT / 'build' / 'faces'
    for d in (tex_dir, json_dir, work):
        d.mkdir(parents=True, exist_ok=True)
    tool = mm.texconv()
    races = {}
    templates = {}
    for head, (name, tid, label) in TEXTURES.items():
        m = face.HeadMap(head, SIZE)
        rgba = synthskin.pack_face(m)
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
            'BlendOp': 'Overlay', 'FixedCategory': CATEGORY, 'Diffuse': f'Complexion\\Face\\{name}.dds',
            'Flags': ['ChargenDetail'], 'Gender': m.gender, 'Id': tid, 'Name': label, 'Normal': None,
            'Slot': 'FaceDetail', 'Specular': None, 'Type': 'TextureSet'})
        print(f'  {head}: {name}.dds ({m.race}, gender {m.gender}), {float((alpha > 0.05).mean()) * 100:.1f}% of the map')
    categories = [{'Entries': [{'Gender': 2, 'Id': CATEGORY_ID, 'Name': CATEGORY, 'Type': 'Category'}], 'Race': race}
                  for race in races]
    tmpl = [{'Entries': entries, 'Race': race} for race, entries in templates.items()]
    (json_dir / 'categories.json').write_text(json.dumps(categories, indent=1), encoding='utf-8', newline='\n')
    (json_dir / 'templates.json').write_text(json.dumps(tmpl, indent=1), encoding='utf-8', newline='\n')
    print(f'face tints -> {json_dir}')


if __name__ == '__main__':
    main()
