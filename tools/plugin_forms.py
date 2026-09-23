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
            break                           # one top group per type
    return out


def load_order(data, plugins_txt):
    """Plugins in load order: the base game's masters, then the active ones in
    plugins.txt ('*' marks active). Missing files are left out."""
    base = ['Fallout4.esm', 'DLCRobot.esm', 'DLCworkshop01.esm', 'DLCCoast.esm', 'DLCworkshop02.esm',
            'DLCworkshop03.esm', 'DLCNukaWorld.esm', 'DLCUltraHighResolution.esm']
    order = [p for p in base if (data / p).exists()]
    if plugins_txt and pathlib.Path(plugins_txt).exists():
        for line in pathlib.Path(plugins_txt).read_text(encoding='utf-8', errors='replace').splitlines():
            line = line.strip()
            if line.startswith('*'):
                name = line[1:]
                if name not in order and (data / name).exists():
                    order.append(name)
    return order


def resolve(data, plugins_txt, record_type, wanted, report):
    """{editor id: (owner plugin, local id)} for the wanted ids, the last plugin in
    load order that carries each one winning, as the game's own lookup does."""
    wanted = set(wanted)
    found = {}
    if not wanted:
        return found
    for plugin in load_order(data, plugins_txt):
        try:
            ids = editor_ids(data / plugin, record_type)
        except (OSError, ValueError, zlib.error, struct.error) as exc:
            report.append(f'rules: could not read {plugin} for {record_type} editor ids ({exc})')
            continue
        for edid, where in ids.items():
            if edid in wanted:
                found[edid] = where
    for edid in sorted(wanted - set(found)):
        report.append(f'rules: no {record_type} with editor id {edid!r} in the load order - that rule is skipped')
    return found
