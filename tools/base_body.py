"""What is baked into the installed base body -- measured, not assumed.

BodyGen morphs are added ON TOP of the mesh on disk. BodySlide builds that mesh as

    built = reference + sum(value_i * diff_i)

over the sliders of whatever preset was selected, so a body built from anything
but zeroed sliders makes every NPC preset stack on top of it. BodySlide keeps no
record of which preset that was, and "build your body with Zeroed Sliders" is a
requirement BodyGen users are simply told to remember.

It can be measured instead. The reference mesh is in ShapeData, the built mesh is
in Meshes, and the .tri written by "Build Morphs" holds every diff_i at 100% --
BodySlideApp::WriteMorphTRI applies each slider at 1.0 into an empty vector, so
the .tri does not depend on the preset. Every preset on disk therefore predicts
a displacement, and the one that leaves nothing unexplained is the one that was
built. Measured on the machine this was written on:

    FemaleBody.nif  = CBBE Body Physics + "CBBE Chubby"   (0.005% unexplained)
    MaleBody.nif    = BodyTalk4 (Nude)  + "BT - Average"  (0.015% unexplained)

The unexplained part is the half-float rounding of the built mesh. The next-best
candidates leave 29% and 91%; there is no near miss to confuse with a match.

How BodySlide turns a preset into slider values, from its own source:

- SliderPresets.cpp LoadPresetFile: size="big" sets the big value, "both" sets
  both, "small" sets only the small one, and a SetSlider with no size is ignored.
  Files are gathered recursively and the FIRST preset with a given name wins.
- BodySlideApp.cpp BuildBodies: a slider the preset does not name is built at the
  slider set's `default`, NOT at 0. BodyTalk 4 has 26 sliders that default to
  100. Then `invert="true"` turns v into 1 - v, default included.
- Zap, UV and clamp sliders never reach the .tri, so BodyGen cannot express them.
"""
import pathlib
import re
import struct
import xml.etree.ElementTree as ET

from nif_geometry import read_shapes

# Share of the displacement a preset may leave unexplained and still be THE preset
# the body was built from. Measured matches leave 0.005% and 0.015%. A share alone
# has less margin than it looks: the right preset on the wrong reference mesh
# ("CBBE Body" instead of "CBBE Body Physics") leaves only 0.105%. What separates
# them cleanly is the WORST vertex: 0.0313 for a true match -- half the 1/16 step
# of a half float between |64| and |128| -- against 0.164 for the wrong mesh.
MATCH = 0.005
MATCH_MAX = 0.035
# A zeroed build IS its reference: measured, both rebuilt bodies and every zeroed
# outfit differ from theirs by exactly 0.0. A tolerance only lets real slider
# values through (BTAMBackAdjust at 100% moves the male body by RMS 0.004).
ZEROED_MAX = 1e-4
ZEROED_RMS = ZEROED_MAX

BODY_OUTPUT = r'meshes\actors\character\characterassets'


def locate(roots, rel):
    """The first of `roots` holding `rel`, else None. BodySlide can write its
    builds outside Data (Config.xml OutputDataPath -- on the machine this was
    written on, D:\\F4Output\\Bodyslides\\woman and \\man, copied into a Vortex mod
    by hand), so a build can be measured before it is ever deployed."""
    for root in roots:
        p = pathlib.Path(root) / rel
        if p.exists():
            return p
    return None


def norm_path(p):
    return (p or '').strip().replace('/', '\\').lower().rstrip('\\')


def output_of(slider_set_element):
    """The output a SliderSet writes, lower-cased, without extension.

    The FILE name is taken exactly as written: BodySlide does not trim it, and
    neither do the plugins that reference it. Measured: "Obi's CozyClassic_Full"
    writes "CozyClassic_Full .nif" -- with the space -- and the outfit's ARMA
    references that same name. Trimming it (as this tool once did) looks for a
    file that does not exist and reports a built outfit as never built.
    """
    of = slider_set_element.find('OutputFile')
    name = (of.text or '') if of is not None else ''
    path = norm_path(slider_set_element.findtext('OutputPath') or '')
    return f'{path}\\{name.lower()}' if name.strip() else ''


def truthy(v):
    return (v or '').strip().lower() == 'true'


def read_slider_sets(bodyslide):
    """Every SliderSet in every .osp: where it builds from, where it builds to,
    and each slider's default, inversion and kind."""
    sets = []
    # As BodySlide's LoadSliderSets: wxDir::GetAllFiles is RECURSIVE, and both
    # *.osp and *.xml are slider sets. Measured: 30 sets live in subfolders here
    # (Enclave Recon Corps Armor, DX Naughty Secretary) -- a top-level glob missed
    # them, and with them 61 built meshes.
    folder = bodyslide / 'SliderSets'
    for osp in sorted(list(folder.rglob('*.osp')) + list(folder.rglob('*.xml'))):
        try:
            root = ET.parse(osp).getroot()
        except ET.ParseError:
            continue
        for s in root.iter('SliderSet'):
            of = s.find('OutputFile')
            sliders = {}
            for sl in s.findall('Slider'):
                # Newer BodySlide writes `default`; sets that generate weights
                # write `small` and `big` instead (SliderSet.cpp WriteSliderSet).
                raw = sl.get('big', sl.get('default', '0'))
                try:
                    default = float(raw) / 100.0
                except ValueError:
                    default = 0.0
                sliders[sl.get('name')] = {
                    'default': default,
                    'invert': truthy(sl.get('invert')),
                    'morph': not (truthy(sl.get('zap')) or truthy(sl.get('uv'))
                                  or truthy(sl.get('clamp'))),
                }
            sets.append({
                'name': s.get('name'),
                'osp': osp.name,
                'data_folder': s.findtext('DataFolder') or '',
                'source_file': s.findtext('SourceFile') or '',
                'output': output_of(s),
                'sliders': sliders,
            })
    return sets


def build_choice(bodyslide, output):
    """The slider set the user picked for this output in BodySlide, if recorded."""
    f = bodyslide / 'BuildSelection.xml'
    if not f.exists():
        return None
    try:
        root = ET.parse(f).getroot()
    except ET.ParseError:
        return None
    for oc in root.iter('OutputChoice'):
        if norm_path(oc.get('path')) == output:
            return oc.get('choice')
    return None


def read_tri(path):
    """{shape: {morph: {vertex index: (dx, dy, dz)}}}, multiplier applied.

        char[4] "PIRT", uint16 shapes, then per shape: uint8 len + name,
        uint16 morphs, and per morph: uint8 len + name, float multiplier,
        uint16 vertex count, then per vertex uint16 index + int16 x, y, z.
    """
    b = pathlib.Path(path).read_bytes()
    if b[:4] != b'PIRT':
        raise ValueError(f'{path}: not a BodySlide .tri (starts {b[:4]!r})')
    o = 4
    (shapes,) = struct.unpack_from('<H', b, o); o += 2
    out = {}
    for _ in range(shapes):
        n = b[o]; o += 1
        shape = b[o:o + n].decode('latin1'); o += n
        (morphs,) = struct.unpack_from('<H', b, o); o += 2
        out[shape] = {}
        for _ in range(morphs):
            n = b[o]; o += 1
            name = b[o:o + n].decode('latin1'); o += n
            (mult,) = struct.unpack_from('<f', b, o); o += 4
            (verts,) = struct.unpack_from('<H', b, o); o += 2
            offs = {}
            for _ in range(verts):
                i, x, y, z = struct.unpack_from('<H3h', b, o); o += 8
                offs[i] = (x * mult, y * mult, z * mult)
            out[shape][name] = offs
    return out


def resolve(preset, slider_set):
    """The value each MORPH slider of this set is built at for this preset, 0..1:
    the preset's big value, else the set's default, then inverted if flagged."""
    out = {}
    for name, sl in slider_set['sliders'].items():
        if not sl['morph']:
            continue
        v = preset['sliders'].get(name, sl['default'])
        if sl['invert']:
            v = 1.0 - v
        out[name] = v
    return out


def _predict(values, tri_shape):
    pred = {}
    for name, w in values.items():
        if w == 0:
            continue
        offs = tri_shape.get(name)
        if not offs:
            continue
        for i, (x, y, z) in offs.items():
            px, py, pz = pred.get(i, (0.0, 0.0, 0.0))
            pred[i] = (px + w * x, py + w * y, pz + w * z)
    return pred


def most_average(pool, tri_shape, candidates):
    """The candidate whose body is closest to the MEAN body of the pool.

    Every preset's body is reference + D.v (D = the .tri diffs), so the pool's
    mean body is reference + D.mean(v), and the reference cancels: this compares
    displacements only, RMS over the vertices. Measured on the machine this was
    written on: for men it picks "BT - Average", which is what its author named
    it -- the check that the definition means what "average" means. For women,
    among full fits, "xy - Type 3DCG (Blessed)(2)(a)".

    pool, candidates: [(name, {morph: value})]. -> (name, rms) or None.
    """
    if not pool or not candidates:
        return None
    morphs = {m for _n, v in pool for m in v}
    mean = {m: sum(v.get(m, 0.0) for _n, v in pool) / len(pool) for m in morphs}
    mean_d = _predict(mean, tri_shape)
    # RMS over every vertex any slider can move; the rest never differ.
    touched = len(set().union(*(offs.keys() for offs in tri_shape.values()))) or 1
    best = None
    for name, values in candidates:
        d = _predict(values, tri_shape)
        ss = 0.0
        for i in set(d) | set(mean_d):
            a = d.get(i, (0.0, 0.0, 0.0))
            b = mean_d.get(i, (0.0, 0.0, 0.0))
            ss += (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
        rms = (ss / touched) ** 0.5
        if best is None or rms < best[1]:
            best = (name, rms)
    return best


def measure(data, body, presets, built_roots=None):
    """Which slider set and preset built Meshes/.../<body>.nif.

    -> {'status': 'zeroed' | 'preset' | 'unknown' | 'unmeasurable',
        'set': slider set dict or None, 'preset': name or None,
        'unexplained': share 0..1 or None, 'baked': {slider: value} or None,
        'note': str}
    'baked' is what every NPC template has to be measured against; it is None
    when that cannot be established. `built_roots` are searched in order for the
    built mesh (default: Data); the reference and the presets always come from
    Data's Tools/BodySlide.
    """
    bodyslide = data / 'Tools/BodySlide'
    rel = f'Meshes/Actors/Character/CharacterAssets/{body}'
    output = f'{BODY_OUTPUT}\\{body.lower()}'
    nif = locate(built_roots or [data], rel + '.nif')
    tri_path = nif.with_suffix('.tri') if nif else None
    if not nif or not tri_path.exists():
        return {'status': 'unmeasurable', 'set': None, 'preset': None, 'unexplained': None,
                'baked': None, 'note': f'{body}.nif or {body}.tri is missing'}

    built = read_shapes(nif)
    tri = read_tri(tri_path)
    sets = [s for s in read_slider_sets(bodyslide) if s['output'] == output]
    chosen = build_choice(bodyslide, output)
    sets.sort(key=lambda s: s['name'] != chosen)       # BodySlide's own choice first

    best = None
    for ss in sets:
        ref_path = bodyslide / 'ShapeData' / ss['data_folder'] / ss['source_file']
        if not ref_path.exists():
            continue
        try:
            ref = read_shapes(ref_path)
        except ValueError:
            continue
        shapes = [n for n in built if n in ref and n in tri and len(built[n]) == len(ref[n])]
        if not shapes:
            continue
        disp = {n: [(a[0] - r[0], a[1] - r[1], a[2] - r[2]) for a, r in zip(built[n], ref[n])]
                for n in shapes}
        total = sum(x * x + y * y + z * z for n in shapes for x, y, z in disp[n])
        worst = max(max(abs(x), abs(y), abs(z)) for n in shapes for x, y, z in disp[n])
        if worst <= ZEROED_MAX:
            return {'status': 'zeroed', 'set': ss, 'preset': None, 'unexplained': 0.0,
                    'baked': {}, 'note': f'{body} is the bare {ss["name"]} reference mesh'}

        candidates = [(p['name'], resolve(p, ss)) for p in presets]
        candidates.append(('(slider set defaults, no preset)',
                           resolve({'sliders': {}}, ss)))
        for name, values in candidates:
            resid, far = 0.0, 0.0
            for n in shapes:
                pred = _predict(values, tri[n])
                for i, (x, y, z) in enumerate(disp[n]):
                    px, py, pz = pred.get(i, (0.0, 0.0, 0.0))
                    d2 = (x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2
                    resid += d2
                    far = max(far, d2)
            share = resid / total
            if best is None or share < best[0]:
                best = (share, ss, name, values, far ** 0.5)

    if best is None:
        return {'status': 'unmeasurable', 'set': None, 'preset': None, 'unexplained': None,
                'baked': None,
                'note': f'no BodySlide reference mesh on disk matches {body}.nif'}
    share, ss, name, values, far = best
    if share <= MATCH and far <= MATCH_MAX:
        return {'status': 'preset', 'set': ss, 'preset': name, 'unexplained': share,
                'baked': values,
                'note': f'{body} was built from "{name}" on {ss["name"]}'}
    return {'status': 'unknown', 'set': ss, 'preset': name, 'unexplained': share,
            'baked': None,
            'note': (f'{body} matches no preset on disk: the closest, "{name}", leaves '
                     f'{100 * share:.2f}% of its shape unexplained, {far:.3f} units at the worst '
                     f'vertex. It was probably built with sliders moved by hand and never saved '
                     f'as a preset.')}
