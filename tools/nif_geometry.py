"""Read vertex positions out of a Fallout 4 .nif -- just enough of the format to
compare a BodySlide-built body against the reference mesh it was built from.

Layout from NifTools' nif.xml (the reference every NIF library is generated from),
for version 20.2.0.7 / user version 12 / Bethesda stream version 130:

  header   "Gamebryo File Format, Version 20.2.0.7\\n"
           uint32 version, uint8 endian, uint32 user version, uint32 block count
           BSStreamHeader: uint32 bs version, ExportString author,
                           ExportString process script, ExportString export script,
                           ExportString max filepath          (ExportString = uint8 len + bytes)
           uint16 block-type count, SizedString block types    (SizedString = uint32 len + bytes)
           uint16 block-type index per block (high bit is a flag, mask 0x7FFF)
           uint32 block size per block
           uint32 string count, uint32 max length, SizedString strings
           uint32 group count, uint32 groups

  BSTriShape (and BSSubIndexTriShape, which only appends segment data):
           NiObjectNET  int32 name (string index), uint32 extra count + int32 refs,
                        int32 controller
           NiAVObject   uint32 flags, float[3] translation, float[9] rotation,
                        float scale, int32 collision object
           float[4] bounding sphere, int32 skin, int32 shader, int32 alpha,
           uint64 vertex desc, uint32 triangle count, uint16 vertex count,
           uint32 data size, then vertex data when data size > 0

  vertex desc: low 4 bits = vertex size in 4-byte units; bits 44.. = attribute
           flags, where bit 0 = has position and bit 10 = FULL PRECISION.
           Position is the first thing in every vertex: 3 floats when full
           precision, else 3 half floats.

Block sizes are in the header, so everything that is not a shape is skipped
without being understood.
"""
import pathlib
import struct

SHAPE_TYPES = {'BSTriShape', 'BSSubIndexTriShape', 'BSMeshLODTriShape'}
VA_VERTEX = 1 << 0
VA_FULL_PRECISION = 1 << 10


class Reader:
    def __init__(self, data):
        self.b = data
        self.o = 0

    def take(self, fmt):
        v = struct.unpack_from('<' + fmt, self.b, self.o)
        self.o += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]

    def export_string(self):
        n = self.take('B')
        s = self.b[self.o:self.o + n]
        self.o += n
        return s.rstrip(b'\0').decode('latin1')

    def sized_string(self):
        n = self.take('I')
        s = self.b[self.o:self.o + n]
        self.o += n
        return s.decode('latin1')


def read_shapes(path):
    """{shape name: [(x, y, z), ...]} for every tri-shape in the file, in the
    shape's own local space (the space BodySlide's diffs are written in)."""
    r = Reader(pathlib.Path(path).read_bytes())
    end = r.b.index(b'\n')
    banner = r.b[:end].decode('latin1')
    if not banner.startswith('Gamebryo File Format'):
        raise ValueError(f'{path}: not a NIF ({banner[:40]!r})')
    r.o = end + 1
    version = r.take('I')
    if version != 0x14020007:
        raise ValueError(f'{path}: NIF version {version:#x}, expected 20.2.0.7 (Fallout 4)')
    r.take('B')                      # endian
    user_version = r.take('I')
    blocks = r.take('I')
    bs_version = r.take('I')
    if bs_version != 130:
        raise ValueError(f'{path}: Bethesda stream {bs_version}, expected 130 (Fallout 4)')
    r.export_string()                # author
    r.export_string()                # process script
    r.export_string()                # export script
    r.export_string()                # max filepath
    types = [r.sized_string() for _ in range(r.take('H'))]
    type_of = [types[r.take('H') & 0x7FFF] for _ in range(blocks)]
    sizes = [r.take('I') for _ in range(blocks)]
    string_count = r.take('I')
    r.take('I')                      # max string length
    strings = [r.sized_string() for _ in range(string_count)]
    for _ in range(r.take('I')):     # groups
        r.take('I')

    shapes = {}
    start = r.o
    for kind, size in zip(type_of, sizes):
        if kind in SHAPE_TYPES:
            name, verts = _shape(Reader(r.b[start:start + size]), strings, path)
            shapes[name] = verts
        start += size
    return shapes


def _shape(r, strings, path):
    name_index = r.take('i')
    name = strings[name_index] if 0 <= name_index < len(strings) else f'#{name_index}'
    for _ in range(r.take('I')):     # extra data refs
        r.take('i')
    r.take('i')                      # controller
    r.take('I')                      # flags
    r.take('3f')                     # translation
    r.take('9f')                     # rotation
    r.take('f')                      # scale
    r.take('i')                      # collision object
    r.take('4f')                     # bounding sphere
    r.take('i'); r.take('i'); r.take('i')   # skin, shader, alpha
    desc = r.take('Q')
    r.take('I')                      # triangle count
    count = r.take('H')
    data_size = r.take('I')
    if data_size == 0:
        raise ValueError(f'{path}: shape {name!r} keeps its geometry outside the .nif')
    stride = (desc & 0xF) * 4
    attrs = (desc >> 44) & 0xFFF
    if not attrs & VA_VERTEX:
        raise ValueError(f'{path}: shape {name!r} has no vertex positions')
    fmt = '<3f' if attrs & VA_FULL_PRECISION else '<3e'
    verts = []
    base = r.o
    for i in range(count):
        verts.append(struct.unpack_from(fmt, r.b, base + i * stride))
    if base + count * stride > len(r.b):
        raise ValueError(f'{path}: shape {name!r} vertex data runs past its block')
    return name, verts
