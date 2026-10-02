"""Picture sheets of every drawable overlay, for tagging what each one depicts (by eye, never by its name alone).

    python tools/overlay_sheets.py [--scan build/overlays.json] [--work D:\\F4Output\\complexion]

For each template of build/overlays.json (tools/overlay_scan.py): its diffuse texture is taken loose from Data
or unpacked from its BA2 (BSArch), converted to PNG by texconv, and drawn twice on a skin-coloured tile:
- left, the whole UV map, small -- WHERE on the body it sits (the body's UV layout is the same for every
  overlay of a sex);
- right, the painted part cropped and enlarged -- WHAT it is.
Sheets of 4 x 4 tiles, each labelled with its index, go to <work>\\sheets\\<f|m>_NNN.png, with an index file
<work>\\sheets\\index.json mapping tile number -> (sex, template id, pack).
"""
import argparse
import json
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import overlay_scan  # noqa: E402

BSARCH = pathlib.Path(r'D:\bsarch\BSArch.exe')
TEXCONV = [pathlib.Path(r'D:\xEdit.4.1.5f\Edit Scripts\Texconvx64.exe'),
           pathlib.Path(r'D:\DynDOLOD\Edit Scripts\Texconvx64.exe')]
SKIN = (196, 160, 136)
TILE_W, TILE_H, COLS, ROWS = 512, 300, 4, 4


def texconv():
    for t in TEXCONV:
        if t.exists():
            return t
    sys.exit('texconv not found')


_UNPACKED = {}


def unpack(archives, rel, work):
    """The DDS for <rel> on disk: unpacked once per archive, its files indexed once."""
    path, _ = archives.index[rel.lower()]
    if path not in _UNPACKED:
        out = work / 'unpacked' / path.stem
        if not out.exists():
            out.mkdir(parents=True)
            r = subprocess.run([str(BSARCH), 'unpack', str(path), str(out)], capture_output=True, text=True)
            if r.returncode:
                print(f'  BSArch cannot unpack {path.name}: {(r.stdout + r.stderr).strip()[-200:]}')
                for p in sorted(out.rglob('*'), reverse=True):
                    p.unlink() if p.is_file() else p.rmdir()
                out.rmdir()
                _UNPACKED[path] = {}
                return None
        _UNPACKED[path] = {str(p.relative_to(out)).lower(): p for p in out.rglob('*.dds')}
    return _UNPACKED[path].get(rel.lower())


def to_png(dds, key, work, tool):
    """One texture to a 1024 px PNG, in its own folder (stems repeat across packs)."""
    out = work / 'png' / key
    png = out / (dds.stem + '.png')
    if not png.exists():
        out.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([str(tool), '-nologo', '-y', '-ft', 'png', '-w', '1024', '-h', '1024', '-m', '1',
                            '-f', 'R8G8B8A8_UNORM', '-o', str(out), str(dds)], capture_output=True, text=True)
        if r.returncode or not png.exists():
            return None
    return png


def layer(png, effect):
    """The overlay as RGBA over skin. Effect (BGEM) textures without a real alpha are additive: brightness
    is the coverage."""
    im = Image.open(png).convert('RGBA')
    alpha = im.getchannel('A')
    if alpha.getextrema()[0] >= 250:  # no alpha painted: use brightness
        alpha = im.convert('L')
    im.putalpha(alpha)
    return im


def tile(im, label, font):
    t = Image.new('RGB', (TILE_W, TILE_H), (40, 40, 40))
    whole = Image.new('RGBA', im.size, SKIN + (255,))
    whole.alpha_composite(im)
    t.paste(whole.convert('RGB').resize((240, 240)), (4, 30))
    box = im.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()
    if box:
        crop = im.crop(box)
        bg = Image.new('RGBA', crop.size, SKIN + (255,))
        bg.alpha_composite(crop)
        crop = bg.convert('RGB')
        crop.thumbnail((256, 256))
        t.paste(crop, (252 + (256 - crop.width) // 2, 30 + (256 - crop.height) // 2))
    ImageDraw.Draw(t).text((6, 4), label, fill=(255, 255, 160), font=font)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', type=pathlib.Path, default=pathlib.Path('build/overlays.json'))
    ap.add_argument('--work', type=pathlib.Path, default=pathlib.Path(r'D:\F4Output\complexion'))
    a = ap.parse_args()
    scan = json.loads(a.scan.read_text(encoding='utf-8'))
    data = pathlib.Path(scan['data'])
    plugins = overlay_scan.load_order(overlay_scan.PLUGINS, data)
    archives = overlay_scan.Archives(data, plugins)
    tool = texconv()
    try:
        font = ImageFont.truetype('arial.ttf', 18)
    except OSError:
        font = ImageFont.load_default()
    sheets = a.work / 'sheets'
    sheets.mkdir(parents=True, exist_ok=True)
    index, missing = {}, []
    for sex in ('f', 'm'):
        items = [t for t in scan['templates'] if t['drawable'] and t['female'] == (sex == 'f')
                 and t.get('playable', True)]
        jobs = []
        for k, t in enumerate(items):
            s = t['slots'][0]
            rel = 'Textures\\' + s['diffuse'].replace('/', '\\').lstrip('\\')
            if rel.lower().startswith('textures\\textures\\'):
                rel = rel[len('textures\\'):]
            dds = data / rel if (data / rel).exists() else unpack(archives, rel, a.work)
            jobs.append((t, s, rel, dds, f'{sex}{k}'))
        with ThreadPoolExecutor(max(2, (os.cpu_count() or 4) - 2)) as pool:
            pngs = list(pool.map(lambda j: to_png(j[3], j[4], a.work, tool) if j[3] else None, jobs))
        tiles = []
        for (t, s, rel, dds, _key), png in zip(jobs, pngs):
            if not png:
                missing.append(f'{sex} {t["id"]} ({t["pack"]}): {rel}')
                continue
            n = len(tiles)
            index[f'{sex}{n}'] = {'female': sex == 'f', 'id': t['id'], 'pack': t['pack'], 'slot': s['slot']}
            tiles.append(tile(layer(png, s['effect']), f'{sex}{n}  {t["id"]}'[:44], font))
        per = COLS * ROWS
        for k in range(0, len(tiles), per):
            sheet = Image.new('RGB', (COLS * TILE_W, ROWS * TILE_H), (20, 20, 20))
            for i, tl in enumerate(tiles[k:k + per]):
                sheet.paste(tl, ((i % COLS) * TILE_W, (i // COLS) * TILE_H))
            sheet.save(sheets / f'{sex}_{k // per:03d}.png')
        print(f'{sex}: {len(tiles)} tiles, {(len(tiles) + per - 1) // per} sheets')
    (sheets / 'index.json').write_text(json.dumps(index, indent=1), encoding='utf-8')
    for m in missing[:20]:
        print('  no picture: ' + m)
    print(f'{len(missing)} without a picture; sheets in {sheets}')


if __name__ == '__main__':
    main()
