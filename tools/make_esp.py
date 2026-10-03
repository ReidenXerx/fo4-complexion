"""Generate Complexion.esp: one quest running Complexion:Bridge, the hands of Complexion.dll.

The shape is Silhouette's make_esp.py (itself fo4-chemistry's, read out of a real working record: AAF.esm's
AAF_MainQuest carries a VMAD whose QUST form, with no fragments, has no trailing fragment section -- version 6,
object format 2, one script, no properties; its DNAM is start game enabled, priority 100). Silhouette.esp, built
this way, runs in the owner's game.

Flagged LIGHT (TES4 flag 0x200): no load-order slot. The quest is 0x800; MCM's buttons call it as
Complexion.esp|0x800.

    python tools/make_esp.py data/Complexion.esp
    python tools/make_esp.py --check <Complexion.esp>
"""
import pathlib
import struct
import sys

BRIDGE_SCRIPT = 'Complexion:Bridge'
# Rapport's persona (C-14), a script of its own on the same quest: without Rapport only it fails to load.
PERSONA_SCRIPT = 'Complexion:Persona'
BRIDGE_EDID = 'ComplexionBridgeQuest'
AUTHOR = 'Complexion'
MASTER = 'Fallout4.esm'
BRIDGE_FORMID = 0x01000800
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
    return (sig.encode('ascii') + struct.pack('<III', len(fields_blob), flags, form_id)
            + struct.pack('<IHH', 0, 131, 0) + fields_blob)


def group(label, records_blob):
    return (b'GRUP' + struct.pack('<I', 24 + len(records_blob)) + label.encode('ascii')
            + struct.pack('<I', 0) + struct.pack('<IHH', 0, 0, 0) + records_blob)


def quest_fields(edid, scripts):
    vmad = struct.pack('<hhH', 6, 2, len(scripts))   # version, object format, script count
    for script in scripts:
        vmad += wstring(script)
        vmad += struct.pack('<B', 0)               # status: local
        vmad += struct.pack('<H', 0)               # no properties
    dnam = bytes.fromhex('110064670000000000000000')   # AAF_MainQuest's: start game enabled
    return field('EDID', zstring(edid)) + field('VMAD', vmad) + field('DNAM', dnam) + field('NEXT', b'')


def build():
    body = group('QUST', record('QUST', BRIDGE_FORMID, quest_fields(BRIDGE_EDID, [BRIDGE_SCRIPT, PERSONA_SCRIPT])))
    hedr = struct.pack('<fiI', 1.0, 2, BRIDGE_FORMID + 1)   # version, records + groups, next free id
    header = field('HEDR', hedr) + field('CNAM', zstring(AUTHOR))
    header += field('MAST', zstring(MASTER)) + field('DATA', struct.pack('<Q', 0))
    return record('TES4', 0, header, flags=TES4_LIGHT) + body


def check(path):
    """[] when this is the Complexion.esp the scripts need."""
    try:
        blob = pathlib.Path(path).read_bytes()
    except OSError as exc:
        return [f'{path} cannot be read ({exc})']
    if blob[:4] != b'TES4':
        return [f'{path} is not a plugin']
    problems = []
    if not struct.unpack_from('<I', blob, 8)[0] & TES4_LIGHT:
        problems.append('it is not flagged light')
    if BRIDGE_SCRIPT.encode('ascii') not in blob or b'QUST' not in blob:
        problems.append('it has no quest running Complexion:Bridge')
    if PERSONA_SCRIPT.encode('ascii') not in blob:
        problems.append('its quest has no Complexion:Persona (Rapport personas)')
    return problems


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if sys.argv[1] == '--check':
        problems = check(sys.argv[2]) if len(sys.argv) > 2 else ['no path']
        if problems:
            print(f'REFUSED {sys.argv[-1]}: ' + '; '.join(problems))
            return 1
        print(f'ok {sys.argv[2]}: light, the bridge quest is there')
        return 0
    blob = build()
    pathlib.Path(sys.argv[1]).write_bytes(blob)
    print(f'wrote {sys.argv[1]} ({len(blob)} bytes): light; quest {BRIDGE_EDID} {BRIDGE_FORMID:08X} running {BRIDGE_SCRIPT}; master {MASTER}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
