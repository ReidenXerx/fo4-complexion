"""Generate Silhouette.esp: two quests, one script each, two empty form lists and a keyword.

0x800 runs the regeneration window (decision S-15), Silhouette:Adopter. 0x802 runs
Silhouette:Bridge (S-18): the hands of Silhouette.dll -- rules by name and faction,
ORefit, the NPC picker, the API's events. Each quest has one script, so MCM's
CallFunction and Game.GetFormFromFile(...) as <script> can never pick the wrong one.
0x803 is the keyword ORefit's floors live under in LooksMenu (S-40): a keyword of its
own keeps the clothed shape apart from the body, and when this plugin is removed
LooksMenu drops every value under it at the next load.
0x801 and 0x804 are the window's memory: who it rolled, and who its heal (without
Silhouette.dll) has looked at -- once, so a value set by hand afterwards stays.
Random distribution itself needs no plugin at all: that is LooksMenu's BodyGen.

The shape is copied from fo4-chemistry's make_esp.py, itself read out of a real
working record: AAF.esm's AAF_MainQuest carries a VMAD whose QUST form, with no
fragments, has no trailing fragment section -- version 6, object format 2, one
script, no properties. Its DNAM (start game enabled, priority 100) is AAF's too.
Chemistry.esp, built this way, runs in the owner's game.

Flagged LIGHT (TES4 flag 0x200): it takes no load-order slot. Light plugins may
only use object ids 0x800-0xFFF, and these are 0x800 to 0x804.

    python tools/make_esp.py data/Silhouette.esp
    python tools/make_esp.py --check <Silhouette.esp>   # refuse one the game must never load

--check exists for one hazard above all (wave 3 L5-H1). LooksMenu keeps a keyed morph value under
"Silhouette.esp|803", and when it loads a save it resolves only the plugin's NAME: an esp of that
name WITHOUT the keyword form makes the keyword null, and every refit value lands in the unkeyed
layer -- her own body -- for good (f4ee BodyMorphInterface.cpp, MorphValueMap::Load). Removing the
esp is safe (its values are dropped); loading a keyword-less one, such as an older build restaged,
is not. The deploy and release scripts run it before anything is copied.
"""
import pathlib
import struct
import sys

SCRIPT_NAME = 'Silhouette:Adopter'
QUEST_EDID = 'SilhouetteAdopterQuest'
SEEN_EDID = 'SilhouetteAdopterSeen'
BRIDGE_SCRIPT = 'Silhouette:Bridge'
BRIDGE_EDID = 'SilhouetteBridgeQuest'
REFIT_EDID = 'SilhouetteRefitKeyword'
HEALED_EDID = 'SilhouetteAdopterHealed'
AUTHOR = 'Silhouette'
MASTER = 'Fallout4.esm'

QUEST_FORMID = 0x01000800      # Silhouette:Adopter reads the list back as 0x801 of
SEEN_FORMID = 0x01000801       # Silhouette.esp, and MCM's button the quest as 0x800
BRIDGE_FORMID = 0x01000802     # MCM's hotkeys and NPC page call the bridge as 0x802
REFIT_FORMID = 0x01000803      # Silhouette:Bridge and Silhouette:API read the refit keyword as 0x803
HEALED_FORMID = 0x01000804     # Silhouette:Adopter's heal reads it back as 0x804
TES4_LIGHT = 0x200


def field(sig, data):
    if len(data) > 0xFFFF:
        raise ValueError(f'{sig} too large for a plain field')
    return sig.encode('ascii') + struct.pack('<H', len(data)) + data


def zstring(text):
    return text.encode('ascii') + b'\0'


def wstring(text):
    raw = text.encode('ascii')
    return struct.pack('<H', len(raw)) + raw


def record(sig, form_id, fields_blob, flags=0):
    # 24-byte header: sig, data size, flags, form id, VCS1, form version, VCS2
    return (sig.encode('ascii') + struct.pack('<III', len(fields_blob), flags, form_id)
            + struct.pack('<IHH', 0, 131, 0) + fields_blob)


def group(label, records_blob):
    return (b'GRUP' + struct.pack('<I', 24 + len(records_blob)) + label.encode('ascii')
            + struct.pack('<I', 0) + struct.pack('<IHH', 0, 0, 0) + records_blob)


def quest_fields(edid, script):
    vmad = struct.pack('<hhH', 6, 2, 1)        # version, object format, script count
    vmad += wstring(script)
    vmad += struct.pack('<B', 0)               # status: local
    vmad += struct.pack('<H', 0)               # no properties
    dnam = bytes.fromhex('110064670000000000000000')   # AAF_MainQuest's: start game enabled
    quest = field('EDID', zstring(edid)) + field('VMAD', vmad) + field('DNAM', dnam)
    return quest + field('NEXT', b'')          # alias section marker, empty


def build():
    adopter = quest_fields(QUEST_EDID, SCRIPT_NAME)
    bridge = quest_fields(BRIDGE_EDID, BRIDGE_SCRIPT)
    seen = field('EDID', zstring(SEEN_EDID))   # filled at run time: FormList.AddForm persists
    healed = field('EDID', zstring(HEALED_EDID))
    # A keyword as the base game writes one (AAF.esm's and Fallout4.esm's, read back): its editor id,
    # white (CNAM, RGBA) and type 0 (TNAM).
    keyword = field('EDID', zstring(REFIT_EDID)) + field('CNAM', bytes.fromhex('ffffff00')) + field('TNAM', struct.pack('<I', 0))

    # Top groups in the game's own order: KYWD first, QUST before FLST.
    body = group('KYWD', record('KYWD', REFIT_FORMID, keyword))
    body += group('QUST', record('QUST', QUEST_FORMID, adopter) + record('QUST', BRIDGE_FORMID, bridge))
    body += group('FLST', record('FLST', SEEN_FORMID, seen) + record('FLST', HEALED_FORMID, healed))

    # version, records + groups (3 groups, 5 records), the next free id
    hedr = struct.pack('<fiI', 1.0, 8, HEALED_FORMID + 1)
    header = field('HEDR', hedr) + field('CNAM', zstring(AUTHOR))
    header += field('MAST', zstring(MASTER)) + field('DATA', struct.pack('<Q', 0))
    return record('TES4', 0, header, flags=TES4_LIGHT) + body


def _records(blob):
    """(masters, light, {form id: (record type, editor id)}) of a plugin's bytes: enough of the format to
    see which forms it defines (tools/plugin_forms.py reads the same layout)."""
    def fields(data):
        o = 0
        while o + 6 <= len(data):
            sig = data[o:o + 4]
            (size,) = struct.unpack_from('<H', data, o + 4)
            yield sig, data[o + 6:o + 6 + size]
            o += 6 + size

    if blob[:4] != b'TES4':
        raise ValueError('not a plugin (no TES4 header)')
    size, flags = struct.unpack_from('<II', blob, 4)
    masters = [v.split(b'\0', 1)[0].decode('cp1252', errors='replace')
               for sig, v in fields(blob[24:24 + size]) if sig == b'MAST']
    found = {}
    o = 24 + size
    while o + 24 <= len(blob):
        if blob[o:o + 4] != b'GRUP':
            raise ValueError(f'expected a top group at byte {o}')
        end = o + struct.unpack_from('<I', blob, o + 4)[0]
        p = o + 24
        while p + 24 <= end:
            sig = blob[p:p + 4]
            dsize, rflags, form_id = struct.unpack_from('<III', blob, p + 4)
            if sig == b'GRUP':
                p += dsize                       # a group's size counts its own header
                continue
            data = blob[p + 24:p + 24 + dsize]
            edid = ''
            if not rflags & 0x40000:             # compressed records keep their EDID inside the zlib block
                edid = next((v.split(b'\0', 1)[0].decode('cp1252', errors='replace')
                             for s, v in fields(data) if s == b'EDID'), '')
            found[form_id] = (sig.decode('ascii', errors='replace'), edid)
            p += 24 + dsize
        o = end
    return masters, bool(flags & TES4_LIGHT), found


def check(path):
    """Why this is not a Silhouette.esp the plugin, its scripts and LooksMenu can live with: [] when it is.
    The refit keyword comes first -- see the module notes: without it LooksMenu moves every refit value into
    her own body for good."""
    try:
        masters, light, found = _records(pathlib.Path(path).read_bytes())
    except (OSError, ValueError, struct.error) as exc:
        return [f'{path} cannot be read as a plugin ({exc})']
    own = len(masters) << 24                     # a plugin's own records carry its master count as index
    problems = []
    kind = found.get(own | (REFIT_FORMID & 0xFFFFFF), ('', ''))[0]
    if kind != 'KYWD':
        problems.append('it has no refit keyword (KYWD 0x803): LooksMenu would move every refit value it keeps under '
                        'Silhouette.esp|803 into her own body at the next load, for good -- an esp without it must '
                        'never be loaded once Silhouette 2 has run')
    for sig, form_id, what in (('QUST', QUEST_FORMID, 'the regeneration window'), ('QUST', BRIDGE_FORMID, 'the bridge'),
                               ('FLST', SEEN_FORMID, 'the window\'s list of who it rolled'),
                               ('FLST', HEALED_FORMID, 'the window\'s list of who it healed')):
        if found.get(own | (form_id & 0xFFFFFF), ('', ''))[0] != sig:
            problems.append(f'it has no {sig} {form_id & 0xFFFFFF:X} ({what})')
    if not light:
        problems.append('it is not flagged light: its forms 0x800..0x804 are meant for a light plugin')
    if masters != [MASTER]:
        problems.append(f'its masters are {masters}, not [{MASTER!r}]')
    return problems


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if sys.argv[1] == '--check':
        if len(sys.argv) < 3:
            print(__doc__)
            return 1
        problems = check(sys.argv[2])
        if problems:
            print(f'REFUSED {sys.argv[2]}: ' + '; '.join(problems))
            return 1
        print(f'ok {sys.argv[2]}: the refit keyword, both quests and both lists are there')
        return 0
    blob = build()
    with open(sys.argv[1], 'wb') as fh:
        fh.write(blob)
    print(f'wrote {sys.argv[1]} ({len(blob)} bytes): light; quest {QUEST_EDID} {QUEST_FORMID:08X} '
          f'running {SCRIPT_NAME}; quest {BRIDGE_EDID} {BRIDGE_FORMID:08X} running {BRIDGE_SCRIPT}; '
          f'form lists {SEEN_EDID} {SEEN_FORMID:08X}, {HEALED_EDID} {HEALED_FORMID:08X}; '
          f'keyword {REFIT_EDID} {REFIT_FORMID:08X}; master {MASTER}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
