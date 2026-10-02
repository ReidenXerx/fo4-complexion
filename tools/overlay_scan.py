"""Reads every LooksMenu overlay template the game will load, the way LooksMenu loads them, and proves each one
can be drawn (docs/complexion-research.md has the source behind every rule here).

    python tools/overlay_scan.py [--data <game Data>] [--plugins <plugins.txt>] [--out build/overlays.json]

LooksMenu (f4ee OverlayInterface.cpp LoadOverlayMods / LoadOverlayTemplates):
- for every LOADED plugin, in load order: F4SE\\Plugins\\F4EE\\Overlays\\<plugin file name>\\overlays.json;
  then Overlays\\Loose\\*.json, alphabetically. A folder named after no loaded plugin is never read.
- jsoncpp's Reader allows // and /* */ comments; a file that fails to parse is skipped whole.
- per entry: gender (missing -> the entry is skipped; above 1 -> female), id (required), name, slots[{slot,
  material}], playable, transformable, sort. The same id again (same gender): later files overwrite the flags,
  the FIRST material per slot wins.
- a .bgem material is an effect layer, anything else a lighting one; a material that does not load leaves the
  layer drawing the base skin again.

What this adds, fail-closed: every template's material and its diffuse texture must be found, loose in Data or
in a BA2 the game loads (the plugin's "<name> - *.ba2", or one named in Fallout4.ini/Fallout4Custom.ini). A
template that cannot be drawn is listed under "broken" and is never handed out.
"""
import argparse
import json
import os
import pathlib
import re
import struct
import sys
import zlib

DATA = pathlib.Path(r'D:\SteamFreeGames\Fallout 4 AE\Data')  # the owner's main install since 2026-10-01
PLUGINS = pathlib.Path(os.environ.get('LOCALAPPDATA', '')) / 'Fallout4' / 'plugins.txt'
BASE_MASTERS = ['Fallout4.esm', 'DLCRobot.esm', 'DLCworkshop01.esm', 'DLCCoast.esm', 'DLCworkshop02.esm',
                'DLCworkshop03.esm', 'DLCNukaWorld.esm', 'DLCUltraHighResolution.esm']


def strip_comments(text):
    """jsoncpp's comment rules: // to end of line, /* */ blocks; never inside a string."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    return ''.join(out)


def load_order(plugins_txt, data):
    """The loaded plugins, in load order: the base masters and CC (Fallout4.ccc) first, then plugins.txt's
    active lines (a leading '*'). Only files that exist in Data load."""
    order = [p for p in BASE_MASTERS]
    ccc = data.parent / 'Fallout4.ccc'
    if ccc.exists():
        order += [l.strip() for l in ccc.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()]
    for line in plugins_txt.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if line.startswith('*'):
            order.append(line[1:])
    seen, out = set(), []
    for p in order:
        if p.lower() not in seen and (data / p).exists():
            seen.add(p.lower())
            out.append(p)
    return out


class Archives:
    """File names in every BA2 the game would load, and a reader for GNRL entries (materials)."""

    def __init__(self, data, plugins):
        self.index = {}  # lower path -> (archive, record)
        names = set()
        for p in plugins:
            stem = p.rsplit('.', 1)[0].lower()
            for f in data.glob('*.ba2'):
                if f.name.lower().startswith(stem + ' - '):
                    names.add(f.name)
        for ini in ('Fallout4.ini', 'Fallout4Custom.ini'):
            ini_path = pathlib.Path(os.environ['USERPROFILE']) / 'Documents' / 'My Games' / 'Fallout4' / ini
            if ini_path.exists():
                for line in ini_path.read_text(encoding='utf-8', errors='replace').splitlines():
                    if re.match(r'\s*sResourceArchive', line, re.I) and '=' in line:
                        names.update(x.strip() for x in line.split('=', 1)[1].split(',') if x.strip())
        self.loaded = sorted(n for n in names if (data / n).exists())
        for n in self.loaded:
            self._read(data / n)

    def _read(self, path):
        with open(path, 'rb') as f:
            head = f.read(24)
            magic, ver, kind, count, names_at = struct.unpack('<4sI4sIQ', head)
            if magic != b'BTDX':
                return
            f.seek(names_at)
            blob = f.read()
        names, off = [], 0
        for _ in range(count):
            (ln,) = struct.unpack_from('<H', blob, off)
            names.append(blob[off + 2:off + 2 + ln].decode('latin-1'))
            off += 2 + ln
        records = []
        if kind == b'GNRL':
            with open(path, 'rb') as f:
                # FO4's v1 and next-gen v7/v8 headers are 24 bytes; Starfield's v2 adds 8, v3 adds 12.
                f.seek({2: 32, 3: 36}.get(ver, 24))
                raw = f.read(36 * count)
            for i in range(count):
                _h, _e, _d, _fl, at, packed, size, _a = struct.unpack_from('<IIIIQIII', raw, 36 * i)
                records.append(('gnrl', at, packed, size))
        else:
            records = [('dx10', 0, 0, 0)] * count
        for name, rec in zip(names, records):
            self.index.setdefault(name.replace('/', '\\').lower(), (path, rec))

    def has(self, rel):
        return rel.lower() in self.index

    def read(self, rel):
        path, (kind, at, packed, size) = self.index[rel.lower()]
        if kind != 'gnrl':
            return None
        with open(path, 'rb') as f:
            f.seek(at)
            raw = f.read(packed or size)
        return zlib.decompress(raw) if packed else raw


def find(data, archives, rel):
    rel = rel.replace('/', '\\').lstrip('\\')
    loose = data / rel
    if loose.exists():
        return 'loose', loose.read_bytes()
    if archives.has(rel):
        return 'ba2', archives.read(rel)
    return None, None


def diffuse_of(material_bytes):
    """A BGEM/BGSM's first texture path is its diffuse (base) map."""
    for s in re.findall(rb'[\x20-\x7e]{4,}', material_bytes or b''):
        if s.lower().endswith(b'.dds'):
            return s.decode('latin-1')
    return None


def scan(data, plugins_txt):
    plugins = load_order(plugins_txt, data)
    archives = Archives(data, plugins)
    root = data / 'F4SE' / 'Plugins' / 'F4EE' / 'Overlays'
    files = [(p, root / p / 'overlays.json') for p in plugins]
    loose = root / 'Loose'
    if loose.exists():
        files += [('Loose', f) for f in sorted(loose.glob('*.json'), key=lambda f: f.name.lower())]
    unread = sorted(d.name for d in root.iterdir() if d.is_dir() and d.name.lower() != 'loose'
                    and d.name.lower() not in {p.lower() for p in plugins}) if root.exists() else []
    templates, problems = {}, []
    for pack, path in files:
        if not path.exists():
            continue
        try:
            entries = json.loads(strip_comments(path.read_text(encoding='utf-8-sig', errors='replace')))
        except ValueError as e:
            problems.append(f'{pack}: overlays.json does not parse, LooksMenu skips it whole ({e})')
            continue
        for item in entries if isinstance(entries, list) else []:
            if not isinstance(item, dict) or 'gender' not in item or 'id' not in item:
                problems.append(f'{pack}: an entry without gender or id is skipped: {str(item)[:80]}')
                continue
            female = 1 if int(item['gender']) >= 1 else 0
            key = (female, item['id'])
            t = templates.setdefault(key, {'id': item['id'], 'female': bool(female), 'pack': pack, 'slots': {}})
            for k in ('name', 'playable', 'transformable', 'sort'):
                if k in item:
                    t[k] = item[k]
            for s in item.get('slots', []):
                t['slots'].setdefault(int(s['slot']), s['material'])
    out = []
    for (female, tid), t in templates.items():
        slots = []
        for slot, material in sorted(t['slots'].items()):
            mat_rel = 'Materials\\' + material.replace('/', '\\').lstrip('\\')
            where, raw = find(data, archives, mat_rel)
            diffuse = diffuse_of(raw)
            tex_where = None
            if diffuse:
                tex_rel = 'Textures\\' + diffuse.replace('/', '\\').lstrip('\\')
                if tex_rel.lower().startswith('textures\\textures\\'):
                    tex_rel = tex_rel[len('textures\\'):]
                tex_where, _ = (('loose', None) if (data / tex_rel).exists() else
                                ('ba2', None) if archives.has(tex_rel) else (None, None))
            slots.append({'slot': slot, 'material': mat_rel, 'effect': material.lower().endswith('.bgem'),
                          'material_in': where, 'diffuse': diffuse, 'diffuse_in': tex_where})
        t['slots'] = slots
        t['drawable'] = bool(slots) and all(s['material_in'] and s['diffuse_in'] for s in slots)
        out.append(t)
    out.sort(key=lambda t: (t['pack'].lower(), not t['female'], t['id'].lower()))
    return {'data': str(data), 'plugins': len(plugins), 'archives': len(archives.loaded),
            'unread_folders': unread, 'problems': problems, 'templates': out}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--data', type=pathlib.Path, default=DATA)
    ap.add_argument('--plugins', type=pathlib.Path, default=PLUGINS)
    ap.add_argument('--out', type=pathlib.Path, default=pathlib.Path('build/overlays.json'))
    a = ap.parse_args()
    result = scan(a.data, a.plugins)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=1), encoding='utf-8')
    t = result['templates']
    broken = [x for x in t if not x['drawable']]
    packs = {}
    for x in t:
        packs.setdefault(x['pack'], [0, 0, 0])
        packs[x['pack']][0 if x['female'] else 1] += 1
        packs[x['pack']][2] += 0 if x['drawable'] else 1
    for p, (f, m, b) in packs.items():
        print(f'  {p:55} female {f:4}  male {m:4}' + (f'  NOT DRAWABLE {b}' if b else ''))
    for u in result['unread_folders']:
        print(f'  never read by LooksMenu (no loaded plugin of that name): Overlays\\{u}')
    for p in result['problems'][:20]:
        print('  ' + p)
    print(f'{len(t)} templates from {len(packs)} packs; {len(broken)} cannot be drawn; '
          f'{result["plugins"]} plugins, {result["archives"]} archives -> {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
