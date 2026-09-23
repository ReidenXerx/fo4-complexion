"""Generate Silhouette.esp: one quest with one script, and one empty form list.

It exists only for the regeneration window (decision S-15), which needs a script
that runs on its own; everything else in Silhouette works without a plugin.

The shape is copied from fo4-chemistry's make_esp.py, itself read out of a real
working record: AAF.esm's AAF_MainQuest carries a VMAD whose QUST form, with no
fragments, has no trailing fragment section -- version 6, object format 2, one
script, no properties. Its DNAM (start game enabled, priority 100) is AAF's too.
Chemistry.esp, built this way, runs in the owner's game.

Flagged LIGHT (TES4 flag 0x200): it takes no load-order slot. Light plugins may
only use object ids 0x800-0xFFF, and these two are 0x800 and 0x801.

    python tools/make_esp.py data/Silhouette.esp
"""
import struct
import sys

SCRIPT_NAME = 'Silhouette:Adopter'
QUEST_EDID = 'SilhouetteAdopterQuest'
SEEN_EDID = 'SilhouetteAdopterSeen'
AUTHOR = 'Silhouette'
MASTER = 'Fallout4.esm'

QUEST_FORMID = 0x01000800      # Silhouette:Adopter reads the list back as 0x801 of
SEEN_FORMID = 0x01000801       # Silhouette.esp, and MCM's button the quest as 0x800
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


def build():
    vmad = struct.pack('<hhH', 6, 2, 1)        # version, object format, script count
    vmad += wstring(SCRIPT_NAME)
    vmad += struct.pack('<B', 0)               # status: local
    vmad += struct.pack('<H', 0)               # no properties
    dnam = bytes.fromhex('110064670000000000000000')   # AAF_MainQuest's: start game enabled

    quest = field('EDID', zstring(QUEST_EDID)) + field('VMAD', vmad) + field('DNAM', dnam)
    quest += field('NEXT', b'')                # alias section marker, empty
    seen = field('EDID', zstring(SEEN_EDID))   # filled at run time: FormList.AddForm persists

    body = group('QUST', record('QUST', QUEST_FORMID, quest))
    body += group('FLST', record('FLST', SEEN_FORMID, seen))

    hedr = struct.pack('<fiI', 1.0, 4, SEEN_FORMID + 1)   # version, records+groups, next id
    header = field('HEDR', hedr) + field('CNAM', zstring(AUTHOR))
    header += field('MAST', zstring(MASTER)) + field('DATA', struct.pack('<Q', 0))
    return record('TES4', 0, header, flags=TES4_LIGHT) + body


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    blob = build()
    with open(sys.argv[1], 'wb') as fh:
        fh.write(blob)
    print(f'wrote {sys.argv[1]} ({len(blob)} bytes): light; quest {QUEST_EDID} {QUEST_FORMID:08X} '
          f'running {SCRIPT_NAME}; form list {SEEN_EDID} {SEEN_FORMID:08X}; master {MASTER}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
