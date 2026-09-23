"""Who has which Silhouette body in a save -- read from its F4SE co-save, without
touching the running game.

LooksMenu stores every actor's body morphs in the co-save (f4ee main.cpp:
SetUniqueID 'F4EE'; records STTB = string table, MRPH / MRPM = one female / male
actor's form id, each followed by MRVM = that actor's morphs). A Silhouette body
is recognised by its MARKER morph, whose value is the stamp of the build that
rolled it (decision S-12); the manifest of that stamp names the exact preset.

F4SE's co-save (Serialization.cpp): a header (signature 'F4SE', format version,
F4SE version, runtime version, plugin count), then per plugin a header (unique
id, chunk count, byte length) and its chunks (type, version, length, data).
Multi-character constants are stored as little-endian integers, so 'F4SE' is the
bytes "ES4F".

    python tools/cosave_census.py                    # the newest save
    python tools/cosave_census.py <file.f4se>
"""
import collections
import json
import pathlib
import struct
import sys

SAVES = pathlib.Path.home() / 'Documents/My Games/Fallout4/Saves'
MANIFESTS = [pathlib.Path(r'D:\GOGGames\Fallout 4 GOTY\Data\F4SE\Plugins\Silhouette\manifests'),
             pathlib.Path(__file__).resolve().parent.parent / 'data/F4SE/Plugins/Silhouette/manifests']


def fourcc(v):
    return struct.pack('>I', v).decode('latin1')


def read_cosave(path):
    """{plugin id: [(chunk type, version, bytes)]}"""
    b = path.read_bytes()
    # Measured on a real co-save: the HEADER signature is the literal bytes "F4SE",
    # while plugin ids and chunk types are little-endian integers ("EE4F" is F4EE,
    # "BTTS" is STTB) -- the two are not written the same way.
    if b[:4] != b'F4SE':
        raise ValueError(f'{path}: not an F4SE co-save ({b[:4]!r})')
    _sig, fmt, f4se, runtime, nplugins = struct.unpack_from('<5I', b, 0)
    o, plugins = 20, {}
    for _ in range(nplugins):
        uid, nchunks, length = struct.unpack_from('<3I', b, o)
        o += 12
        end = o + length
        chunks = []
        while o < end:
            t, ver, ln = struct.unpack_from('<3I', b, o)
            o += 12
            chunks.append((fourcc(t), ver, b[o:o + ln]))
            o += ln
        plugins[fourcc(uid)] = chunks
        o = end
    return plugins


def looksmenu_bodies(chunks):
    """-> ({(sex, actor form id): {morph: {keyword form id: value}}}, strings)"""
    strings, bodies, current = [], {}, None
    for kind, ver, data in chunks:
        if kind == 'STTB':
            (n,) = struct.unpack_from('<I', data, 0)
            o = 4
            for _ in range(n):
                (ln,) = struct.unpack_from('<H', data, o)
                o += 2
                strings.append(data[o:o + ln].decode('latin1'))
                o += ln
        elif kind in ('MRPH', 'MRPM'):
            (fid,) = struct.unpack_from('<I', data, 0)
            current = ('F' if kind == 'MRPH' else 'M', fid)
        elif kind == 'MRVM' and current:
            (n,) = struct.unpack_from('<I', data, 0)
            o, morphs = 4, {}
            for _ in range(n):
                sid, nkeys = struct.unpack_from('<2I', data, o)
                o += 8
                keys = {}
                for _ in range(nkeys):
                    kw, val = struct.unpack_from('<If', data, o)
                    o += 8
                    keys[kw] = val
                name = strings[sid] if sid < len(strings) else f'#{sid}'
                morphs[name] = keys
            bodies[current] = morphs
            current = None
    return bodies, strings


def manifests():
    out = {}
    for d in MANIFESTS:
        for f in d.glob('*.json') if d.exists() else []:
            m = json.loads(f.read_text(encoding='utf-8'))
            out[int(m['stamp'])] = m
    return out


def main():
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else max(SAVES.glob('*.f4se'), key=lambda p: p.stat().st_mtime)
    plugins = read_cosave(path)
    if 'F4EE' not in plugins:
        print(f'{path.name}: no LooksMenu data in this co-save')
        return 1
    bodies, _ = looksmenu_bodies(plugins['F4EE'])
    known = manifests()
    rows, per_preset, other = [], collections.Counter(), 0
    for (sex, fid), morphs in sorted(bodies.items()):
        marks = [(n, keys.get(0, 0.0)) for n, keys in morphs.items()
                 if n.startswith('Silhouette_') and keys.get(0, 0.0) > 0]
        if not marks:
            other += 1
            rows.append((fid, sex, None, None, len(morphs)))
            continue
        name, stamp = marks[0]
        m = known.get(int(stamp))
        preset = m['templates'].get(name, {}).get('preset') if m else None
        per_preset[preset or name] += 1
        rows.append((fid, sex, preset or name, int(stamp), len(morphs)))
    print(f'{path.name}  ({path.stat().st_size} bytes): {len(bodies)} actors hold LooksMenu body morphs')
    print(f'  Silhouette bodies: {sum(per_preset.values())} in {len(per_preset)} presets; '
          f'other body sliders: {other}')
    stamps = collections.Counter(r[3] for r in rows if r[3])
    for st, n in stamps.items():
        print(f'  stamp {st}: {n} actor(s) -- manifest {"found" if st in known else "MISSING"}')
    player = [r for r in rows if r[0] == 0x14]
    if player:
        print(f'  the player (00000014): {player[0][2] or "no Silhouette marker"} '
              f'({player[0][4]} morphs)')
    print('  most common presets:')
    for p, n in per_preset.most_common(12):
        print(f'    {n:3}  {p}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
