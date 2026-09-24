"""Find records by editor id in Fallout 4 plugins, read straight from the files.

The runtime keeps no editor ids for most forms (a TESFaction has none), so OBody's
`faction*` rules -- written with editor ids -- are resolved here, offline, into the
plugin that DEFINES the record and its id without the load-order byte (decision
S-19). Silhouette.dll then looks the form up with TESDataHandler::LookupForm.

Enough of the format for this and nothing more (UESP's Mod File Format pages):

  record   char[4] type, uint32 data size, uint32 flags, uint32 form id,
           uint32 version control, uint16 form version, uint16 unknown  (24 bytes)
  group    "GRUP", uint32 size INCLUDING its 24-byte header, char[4] label,
           int32 group type (0 = top group, label = the record type), 8 bytes
  field    char[4] type, uint16 size -- or, after an XXXX field, the uint32 that
           XXXX carried (a field over 64 KB states its size in a preceding XXXX)
  flags    0x40000: the record's data is zlib-compressed after a uint32 size
  form id  high byte = index into the plugin's MAST list; one past the last
           master means the plugin itself defines the record
"""
import pathlib
import struct
import zlib

COMPRESSED = 0x40000


def _fields(data):
    out = []
    o = 0
    big = None
    while o + 6 <= len(data):
        sig = data[o:o + 4]
        (size,) = struct.unpack_from('<H', data, o + 4)
        o += 6
        if sig == b'XXXX':
            (big,) = struct.unpack_from('<I', data, o)
            o += size
            continue
        if big is not None:
            size, big = big, None
        out.append((sig, data[o:o + size]))
        o += size
    return out


def _zstring(raw):
    return raw.split(b'\0', 1)[0].decode('cp1252', errors='replace')


def header(path):
    """(masters, light) of a plugin."""
    with open(path, 'rb') as f:
        head = f.read(24)
        if head[:4] != b'TES4':
            raise ValueError(f'{path}: not a plugin')
        size, flags = struct.unpack_from('<II', head, 4)
        data = f.read(size)
    masters = [_zstring(v) for sig, v in _fields(data) if sig == b'MAST']
    light = bool(flags & 0x200) or str(path).lower().endswith('.esl')
    return masters, light


def editor_ids(path, record_type):
    """{editor id: (owner plugin, local id)} for every record of this type the
    plugin carries -- its own and its overrides of its masters' records."""
    path = pathlib.Path(path)
    masters, _light = header(path)
    rtype = record_type.encode('ascii')
    out = {}
    with open(path, 'rb') as f:
        head = f.read(24)
        f.seek(24 + struct.unpack_from('<I', head, 4)[0])
        while True:
            g = f.read(24)
            if len(g) < 24:
                break
            if g[:4] != b'GRUP':
                raise ValueError(f'{path}: expected a top group at {f.tell() - 24}')
            (size,) = struct.unpack_from('<I', g, 4)
            label = g[8:12]
            if label != rtype:
                f.seek(size - 24, 1)
                continue
            end = f.tell() + size - 24
            while f.tell() < end:
                rh = f.read(24)
                if rh[:4] == b'GRUP':      # a top FACT group holds no subgroups, but be safe
                    (sub,) = struct.unpack_from('<I', rh, 4)
                    f.seek(sub - 24, 1)
                    continue
                dsize, flags, form_id = struct.unpack_from('<III', rh, 4)
                data = f.read(dsize)
                if flags & COMPRESSED:
                    data = zlib.decompress(data[4:])
                edid = next((_zstring(v) for sig, v in _fields(data) if sig == b'EDID'), None)
                if not edid:
                    continue
                index = form_id >> 24
                owner = masters[index] if index < len(masters) else path.name
                out[edid] = (owner, form_id & 0xFFFFFF)
            # no break: a type can have more than one top group -- Fallout4.esm has two of NPC_, LVLN,
            # WEAP and eleven more (measured 2026-09-24), and the first NPC_ one lacks Piper and Preston
    return out


def load_order(data, plugins_txt):
    """Plugins in load order: the base game's masters, the Creation Club plugins the
    game loads by itself (Fallout4.ccc beside the executable, in its order), then the
    active ones in plugins.txt ('*' marks active). Missing files are left out."""
    base = ['Fallout4.esm', 'DLCRobot.esm', 'DLCworkshop01.esm', 'DLCCoast.esm', 'DLCworkshop02.esm',
            'DLCworkshop03.esm', 'DLCNukaWorld.esm', 'DLCUltraHighResolution.esm']
    ccc = pathlib.Path(data).parent / 'Fallout4.ccc'
    if ccc.exists():
        base += [line.strip() for line in ccc.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip()]
    order = []
    for p in base:
        if (data / p).exists() and p not in order:
            order.append(p)
    if plugins_txt and pathlib.Path(plugins_txt).exists():
        for line in pathlib.Path(plugins_txt).read_text(encoding='utf-8', errors='replace').splitlines():
            line = line.strip()
            if line.startswith('*'):
                name = line[1:]
                if name not in order and (data / name).exists():
                    order.append(name)
    return order


def _fold(text):
    """ASCII letters in lower case, as the game compares editor ids."""
    return ''.join(c.lower() if 'A' <= c <= 'Z' else c for c in text)


def resolve(data, plugins_txt, record_type, wanted, report):
    """{editor id: (owner plugin, local id)} for the wanted ids, the last plugin in
    load order that carries each one winning, as the game's own lookup does. Editor ids
    match in any case, as the game matches them; the answer is keyed by the spelling
    that was asked for."""
    by_fold = {}
    for w in set(wanted):
        by_fold.setdefault(_fold(w), []).append(w)
    found = {}
    if not by_fold:
        return found
    for plugin in load_order(data, plugins_txt):
        try:
            ids = editor_ids(data / plugin, record_type)
        except (OSError, ValueError, zlib.error, struct.error) as exc:
            report.append(f'rules: could not read {plugin} for {record_type} editor ids ({exc})')
            continue
        for edid, where in ids.items():
            for w in by_fold.get(_fold(edid), ()):
                found[w] = where
    for edid in sorted(set(wanted) - set(found)):
        report.append(f'rules: no {record_type} with editor id {edid!r} in the load order - that rule is skipped')
    return found


def find_inactive(data, plugins_txt, record_type, wanted):
    """{editor id: plugin} for wanted ids that a plugin in Data defines while it is NOT in the load order
    (disabled in plugins.txt, or never enabled) -- so a refusal can say "enable X" instead of "check the
    spelling". Only asked after resolve() missed, so the slower scan of every file runs only then."""
    active = {p.lower() for p in load_order(data, plugins_txt)}
    by_fold = {}
    for w in set(wanted):
        by_fold.setdefault(_fold(w), []).append(w)
    found = {}
    if not by_fold:
        return found
    for path in sorted(pathlib.Path(data).iterdir(), key=lambda p: p.name.lower()):
        if path.suffix.lower() not in ('.esm', '.esp', '.esl') or path.name.lower() in active or not path.is_file():
            continue
        try:
            ids = editor_ids(path, record_type)
        except (OSError, ValueError, zlib.error, struct.error):
            continue
        for edid in ids:
            for w in by_fold.get(_fold(edid), ()):
                found.setdefault(w, path.name)
    return found
