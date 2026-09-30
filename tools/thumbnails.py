"""The picker window's thumbnails (S-79): every preset the pickers offer, drawn front and side on the installed
body, one 2048x2048 atlas per sex, BC1 DDS for Data/Textures/Silhouette.

    python tools/thumbnails.py [--data <game Data>] [--jobs 4]

Cell k of a sex's atlas is the k-th preset the catalog offers that sex in its menu (its order in catalog.json),
which is also the k-th entry of the NPC picker's list and of Silhouette:Player's: the window finds a preset's
picture by its place in the list, so the order is checked against the picker script before anything is
written. The player's own presets (S-76) are read in game and have none.

Shaded like the review sheets (tools/pool/render.py) and nude -- the owner, 2026-09-30: nude renders can ship.
Every body of a sex is drawn at one scale, so widths compare across the grid. Needs Pillow and texconv
(DirectXTex; xEdit and DynDOLOD ship it).
"""
import argparse
import json
import math
import pathlib
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'tools' / 'pool'), str(ROOT / 'tools')]

CATALOG = ROOT / 'data' / 'F4SE' / 'Plugins' / 'Silhouette' / 'catalog.json'
PLAYER = ROOT / 'papyrus' / 'Silhouette' / 'Player.psc'
OUT = ROOT / 'build' / 'textures' / 'Silhouette'
WORK = ROOT / 'build' / 'thumbnails'
TEXCONV = [pathlib.Path(r'D:\xEdit.4.1.5f\Edit Scripts\Texconvx64.exe'),
           pathlib.Path(r'D:\DynDOLOD\Edit Scripts\Texconvx64.exe')]

CELL_W, CELL_H, SS = 96, 160, 3  # one thumbnail, and the supersampling it is drawn at
ATLAS = 2048
COLS, ROWS = ATLAS // CELL_W, ATLAS // CELL_H
BACK = (22, 22, 26)
SKIN = (214, 176, 156)
FILE = {'female': 'ThumbsFemale', 'male': 'ThumbsMale'}

_body = {}


def menu_presets(catalog, sex):
    return [p for p in catalog['presets'] if p.get('menu') and p['sex'] == sex]


def script_names(sex):
    """The names Silhouette:Player lists for a sex, in its order (its Names0, Names1 ... functions)."""
    text = PLAYER.read_text(encoding='utf-8')
    names = []
    for part in range(8):
        m = re.search(rf'String\[\] Function {sex.capitalize()}Names{part}\(\) Global(.*?)EndFunction', text, re.S)
        if not m:
            break
        names += re.findall(r'a\.Add\("((?:[^"\\]|\\.)*)", 1\)', m.group(1))
    return names


def _load(data, sex):
    if sex not in _body:
        from mesh import Body
        body = Body(data, sex)
        arms = {i for i, r in enumerate(body.region) if r == 'arm'}
        body.side_tris = [t for t in body.tris if not arms.intersection(t)]
        _body[sex] = body
    return _body[sex]


def _views(img_size, verts, tris, side_tris, scale, zmin):
    """Front (left) and side (right, from the body's left: it faces +y), shaded, far triangles first. The side
    view leaves the arms off: one hangs across the profile the side view is there to show."""
    from PIL import Image, ImageDraw
    w, h = img_size
    img = Image.new('RGB', (w, h), BACK)
    d = ImageDraw.Draw(img)
    for cx, view in ((0.27, 'front'), (0.74, 'side')):
        V = (0.0, 1.0, 0.0) if view == 'front' else (1.0, 0.0, 0.0)
        L = (0.4 * V[0] + 0.3, 0.8 * V[1] + 0.4 * V[0], 0.55)
        ll = math.sqrt(sum(c * c for c in L))
        L = tuple(c / ll for c in L)
        polys = []
        for a, b, c in (tris if view == 'front' else side_tris):
            A, B, C = verts[a], verts[b], verts[c]
            ux, uy, uz = B[0] - A[0], B[1] - A[1], B[2] - A[2]
            vx, vy, vz = C[0] - A[0], C[1] - A[1], C[2] - A[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            depth = sum(P[0] * V[0] + P[1] * V[1] for P in (A, B, C))
            if view == 'front':
                pts = [(w * cx - P[0] * scale, h - 6 * SS - (P[2] - zmin) * scale) for P in (A, B, C)]
            else:
                pts = [(w * cx + P[1] * scale, h - 6 * SS - (P[2] - zmin) * scale) for P in (A, B, C)]
            lit = abs(nx * L[0] + ny * L[1] + nz * L[2]) / nl
            polys.append((depth, pts, 0.3 + 0.7 * lit))
        polys.sort(key=lambda t: t[0])
        for _d, pts, sh in polys:
            d.polygon(pts, fill=tuple(int(c * sh) for c in SKIN))
    return img


def render(job):
    """(data, sex, index, values, scale, zmin) -> (sex, index, PNG bytes of one cell)"""
    import io
    from PIL import Image
    data, sex, index, values, scale, zmin = job
    body = _load(data, sex)
    img = _views((CELL_W * SS, CELL_H * SS), body.build(values), body.tris, body.side_tris, scale, zmin)
    buf = io.BytesIO()
    img.resize((CELL_W, CELL_H), Image.LANCZOS).save(buf, 'PNG')
    return sex, index, buf.getvalue()


def texconv():
    for t in TEXCONV:
        if t.exists():
            return t
    sys.exit('no texconv: install DirectXTex texconv, or point TEXCONV at it')


def main():
    import generate
    from PIL import Image
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(generate.DATA))
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    jobs, lists = [], {}
    for sex in ('female', 'male'):
        presets = menu_presets(catalog, sex)
        names = [p['name'] for p in presets]
        script = script_names(sex)
        if names != script:
            first = next((i for i, (x, y) in enumerate(zip(names, script)) if x != y), min(len(names), len(script)))
            sys.exit(f'{sex}: the catalog offers {len(names)} presets, Silhouette:Player {len(script)}, first '
                     f'difference at {first} -- regenerate (tools/silhouette_gen.py --write) and try again')
        if len(names) > COLS * ROWS:
            sys.exit(f'{sex}: {len(names)} presets, the atlas holds {COLS * ROWS}')
        lists[sex] = names
        body = _load(a.data, sex)
        zs = [p[2] for p in body.ref]
        zmin, zmax = min(zs), max(zs)
        scale = (CELL_H - 12) * SS / (zmax - zmin)
        jobs += [(a.data, sex, i, p['values'], scale, zmin) for i, p in enumerate(presets)]

    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    atlas = {sex: Image.new('RGB', (ATLAS, ATLAS), BACK) for sex in lists}
    import io
    with ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for n, (sex, i, png) in enumerate(pool.map(render, jobs, chunksize=4), 1):
            atlas[sex].paste(Image.open(io.BytesIO(png)), ((i % COLS) * CELL_W, (i // COLS) * CELL_H))
            if n % 50 == 0:
                print(f'  {n}/{len(jobs)}', flush=True)
    tool = texconv()
    for sex, img in atlas.items():
        png = WORK / f'{FILE[sex]}.png'
        img.save(png)
        # BC1, one mip: the window shows each cell at about its own size, and Scaleform does no mip selection.
        subprocess.run([str(tool), '-nologo', '-y', '-f', 'BC1_UNORM', '-m', '1', '-o', str(OUT), str(png)],
                       check=True, stdout=subprocess.DEVNULL)
        written = OUT / f'{FILE[sex]}.DDS'  # texconv keeps the case it likes; the game's paths are lower-case
        if written.exists():
            written.replace(OUT / f'{FILE[sex]}.dds')
        print(f'{sex}: {len(lists[sex])} thumbnails -> {OUT / (FILE[sex] + ".dds")}')
    # The build the pictures were drawn from: a release refuses them for any other (scripts/make-release.ps1),
    # since a cell is found by its place in that build's lists.
    (WORK / 'index.json').write_text(json.dumps({'build': catalog['build'], 'cell': [CELL_W, CELL_H], 'cols': COLS,
                                                 'lists': lists}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
