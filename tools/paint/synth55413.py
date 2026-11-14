"""Synthetic skin from Synth Looksmenu Skin Override (Nexus 55413, patrox5 / patrox6 on Nexus; its textures by Aaron4412,
Nexus 35269) as Complexion overlays -- alasdairn, 2026-11-14: "All three, see if you can make a male version too".

    The pack is a LooksMenu SKIN for women: whole body, hands and face textures in the game's own female UVs, which are
    our women's UVs exactly (checked by rendering them straight onto our body). Three looks are made from it:

    Panels       -- its grey plating with black panel lines, a lit overlay (like synthskin's Plated) over body and
                   hands, with the pack's own normal maps on women; a face tint from its synth face.
    Panel Lines  -- only its dark panel lines (and joints, rivets) multiplied into the character's own skin; a face
                   tint from the same.
    Glow Lines   -- its human versions' coloured lines (blue, pink, green) and their white plates, as an UNLIT
                   alpha-blended overlay: unlit, the colours glow, as the pack's lines are meant to.

    Men have no textures in the pack. A male texel takes the colour of the matching point on the woman's body: both
    bodies set to the same heights (feet, crotch, nipples, neck) and the torso to the same width at each height, then
    the nearest point of the same region (torso, arm, leg, ...) that faces the same way. Hands: each hand fitted into
    the other's box. Heads: nose and chin.

    The pack's files are not in this repository (third-party, permission for Complexion only): SOURCE is the unpacked
    2K archive. tools/paint/art/contrib/CREDITS.md credits them.
"""
import pathlib

import numpy as np

SOURCE = pathlib.Path(r'D:\F4Output\complexion\incoming\55413\x2k\Data\textures\actors\character\basehumanfemale\SynthSkins')
BODY = {'panels': 'Body/FB_1.dds', 'blue': 'Body/FB_2.dds', 'pink': 'Body/FB_3.dds', 'green': 'Body/FB_4.dds'}
HANDS = {'panels': 'Body/FH_1.dds', 'blue': 'Body/FH_2.dds', 'pink': 'Body/FH_3.dds', 'green': 'Body/FH_4.dds'}
FACE = 'Head/H_D1.dds'                          # the synth face (grey plates, black lines)
NORMALS = {'body': 'Normals/femalebody_n.dds', 'hands': 'Normals/basefemalehands_n.dds'}

PANELS_ALPHA = 0.96          # its plating over the person's skin: all but a breath of it
PANELS_SPEC = (0.40, 0.55)   # specular, smoothness on the plates (a soft sheen; the lines none)
LINE_DEPTH = 0.85            # Panel Lines: the skin multiplied by 1 - this at the darkest of a line
LINE_DARK, LINE_PLATE = 0.12, 0.45   # luminance of its lines and of where its plate grey begins (its plates sit ~0.7)
GLOW_SAT = 0.10              # Glow Lines: a texel that differs between its three colours by this much is a glow line
GLOW_BLACK, GLOW_WHITE = 0.14, 0.80  # ... and a grey this dark or this light is one of its black lines or white plates
GLOW_WHITE_LEVEL = 0.72      # its white plates drawn this light: unlit, full white glows like a lamp in the dark

_cache = {}


def available():
    return (SOURCE / BODY['panels']).exists()


def _need():
    if not available():
        raise SystemExit(f'Synth Looksmenu Skin Override (Nexus 55413) is not unpacked at {SOURCE}: ask '
                         'Fallout-collection for it (download only) and unpack SynthSkin2K there')


def _tex(rel, size):
    """One of the pack's textures as float RGBA at size x size (cached)."""
    key = (rel, size)
    if key not in _cache:
        _need()
        from PIL import Image
        im = Image.open(SOURCE / rel).convert('RGBA')
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        _cache[key] = np.asarray(im, np.float32) / 255.0
    return _cache[key]


# ---------------------------------------------------------------- women's textures onto men (and men's heads)


def _body_frame(m):
    """Per covered texel: (positions in a common frame, region). Heights go piecewise through the landmarks to the
    female body's; the torso is scaled to the female torso's width at its height; the rest by the height ratio."""
    from marks import landmarks
    lo, hi = m.bounds
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx].copy()
    R = m.region.reshape(-1)[idx]
    L = landmarks(m)
    h = (X[:, 2] - lo[2]) / (hi[2] - lo[2])
    return idx, X, R, h, L


def _female_frame():
    if 'ff' not in _cache:
        from body import UVMap
        import make_marks as mm
        _cache['ff'] = UVMap(mm.DATA, 'female', 2048)
    return _cache['ff']


def _torso_halfwidth(X, R, h, bins):
    from body import REGIONS
    t = R == REGIONS.index('torso')
    out = np.full(len(bins) - 1, np.nan)
    for k in range(len(bins) - 1):
        sel = t & (h >= bins[k]) & (h < bins[k + 1])
        if sel.sum() > 20:
            out[k] = np.percentile(np.abs(X[sel, 0]), 98)
    good = np.isfinite(out)
    c = (bins[:-1] + bins[1:]) / 2
    return np.interp(c, c[good], out[good])


def _body_map(m):
    """Per covered texel of a male body map: the flat index of the matching texel of the female map at 2048, or -1."""
    from scipy.spatial import cKDTree
    from body import REGIONS
    f = _female_frame()
    fi, FX, FR, fh, FL = _body_frame(f)
    mi, MX, MR, mh, ML = _body_frame(m)
    keys = ('crotch', 'nipple', 'top')
    hm = np.interp(mh, [0.0] + [ML[k] for k in keys] + [1.0], [0.0] + [FL[k] for k in keys] + [1.0])
    flo, fhi = f.bounds
    mlo, mhi = m.bounds
    s = (fhi[2] - flo[2]) / (mhi[2] - mlo[2])
    MXn = MX * s
    MXn[:, 2] = flo[2] + hm * (fhi[2] - flo[2])
    bins = np.linspace(0, 1, 51)
    wf = _torso_halfwidth(FX, FR, fh, bins)
    wm = _torso_halfwidth(MX * s, MR, hm, bins)
    c = (bins[:-1] + bins[1:]) / 2
    torso = MR == REGIONS.index('torso')
    MXn[torso, 0] *= np.interp(hm[torso], c, wf / wm)
    FN = f.normal.reshape(-1, 3)[fi]
    MN = m.normal.reshape(-1, 3)[mi]
    out = np.full(len(mi), -1, np.int64)
    for r in np.unique(MR):
        src = np.flatnonzero(FR == r)
        dst = np.flatnonzero(MR == r)
        if not len(src) or not len(dst):
            continue
        tree = cKDTree(FX[src])
        for a in range(0, len(dst), 400000):
            d = dst[a:a + 400000]
            _dist, nb = tree.query(MXn[d], k=6)
            agree = np.einsum('nkc,nc->nk', FN[src[nb]], MN[d])
            pick = np.argmax(agree - 0.02 * _dist, axis=1)   # the nearest that faces the same way
            out[d] = fi[src[nb[np.arange(len(d)), pick]]]
    return mi, out


def _hands_map(m):
    """Per covered texel of a male hands map: the matching texel of the female hands map at 1024."""
    from scipy.spatial import cKDTree
    import hands
    import make_marks as mm
    if 'fh' not in _cache:
        _cache['fh'] = hands.HandMap(mm.DATA, 'female', 1024)
    f = _cache['fh']
    fi = np.flatnonzero(f.covered)
    mi = np.flatnonzero(m.covered)
    FX, MX = f.position.reshape(-1, 3)[fi], m.position.reshape(-1, 3)[mi]
    FN, MN = f.normal.reshape(-1, 3)[fi], m.normal.reshape(-1, 3)[mi]
    out = np.full(len(mi), -1, np.int64)
    for side in (1, -1):
        fs, ms = np.flatnonzero(FX[:, 0] * side > 0), np.flatnonzero(MX[:, 0] * side > 0)
        if not len(fs) or not len(ms):
            continue
        flo, fhi = FX[fs].min(0), FX[fs].max(0)
        mlo, mhi = MX[ms].min(0), MX[ms].max(0)
        P = flo + (MX[ms] - mlo) / np.maximum(mhi - mlo, 1e-6) * (fhi - flo)
        _dist, nb = cKDTree(FX[fs]).query(P, k=6)
        agree = np.einsum('nkc,nc->nk', FN[fs[nb]], MN[ms])
        pick = np.argmax(agree - 0.02 * _dist, axis=1)
        out[ms] = fi[fs[nb[np.arange(len(ms)), pick]]]
    return mi, out


def _head_map(m):
    """Per covered texel of a head map: the matching texel of the vanilla female head map at its size."""
    from scipy.spatial import cKDTree
    import face
    import synthskin
    key = ('fhead', m.size)
    if key not in _cache:
        _cache[key] = face.HeadMap('human_female', m.size)
    f = _cache[key]
    fi, mi = np.flatnonzero(f.covered), np.flatnonzero(m.covered)
    FX, MX = f.position.reshape(-1, 3)[fi], m.position.reshape(-1, 3)[mi]
    FN, MN = f.normal.reshape(-1, 3)[fi], m.normal.reshape(-1, 3)[mi]
    Lf, Lm = synthskin.face_landmarks(f), synthskin.face_landmarks(m)
    s = (Lf['nose'][2] - Lf['chin'][2]) / (Lm['nose'][2] - Lm['chin'][2])
    P = Lf['nose'] + (MX - Lm['nose']) * s
    _dist, nb = cKDTree(FX).query(P, k=6)
    agree = np.einsum('nkc,nc->nk', FN[nb], MN)
    pick = np.argmax(agree - 0.02 * _dist, axis=1)
    return mi, fi[nb[np.arange(len(mi)), pick]], f.size


def _on(m, rel, kind):
    """The pack texture rel as it falls on map m (float RGBA, m.size square): straight for a woman's body or hands
    and the vanilla female head, carried over from the woman's for everyone else."""
    female = getattr(m, 'sex', None) == 'female' or getattr(m, 'head', None) == 'human_female'
    if female:
        return _tex(rel, m.size)
    key = (kind, getattr(m, 'sex', None), getattr(m, 'head', None), m.size)
    if key not in _cache:
        _cache[key] = {'body': _body_map, 'hands': _hands_map}.get(kind, _head_map)(m)
    got = _cache[key]
    mi, src = got[0], got[1]
    fsize = got[2] if kind == 'head' else (2048 if kind == 'body' else 1024)
    T = _tex(rel, fsize).reshape(-1, 4)
    out = np.zeros((m.size * m.size, 4), np.float32)
    ok = src >= 0
    out[mi[ok]] = T[src[ok]]
    return out.reshape(m.size, m.size, 4)


def _lum(rgb):
    return rgb @ np.array((0.3, 0.59, 0.11), np.float32)


# ---------------------------------------------------------------- the painters


def _panels(m, rel, kind):
    T = _on(m, rel, kind)
    cov = m.covered
    D = np.zeros(cov.shape + (4,), np.float32)
    D[..., :3] = T[..., :3]
    D[..., 3] = np.where(cov, PANELS_ALPHA, 0.0)
    plate = np.clip((_lum(T[..., :3]) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1)
    S = np.zeros(cov.shape + (2,), np.float32)
    S[..., 0] = PANELS_SPEC[0] * plate
    S[..., 1] = PANELS_SPEC[1] * plate
    return D, S


def panels_body(m, rng=None):
    return _panels(m, BODY['panels'], 'body')


def panels_hands(m, rng=None):
    return _panels(m, HANDS['panels'], 'hands')


def _lines(m, rel, kind):
    from synthskin import _multiply
    T = _on(m, rel, kind)
    dark = 1 - np.clip((_lum(T[..., :3]) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1)
    f = np.where(m.covered, 1 - LINE_DEPTH * dark, 1.0)
    return _multiply(m, f)


def panel_lines_body(m, rng=None):
    return _lines(m, BODY['panels'], 'body')


def panel_lines_hands(m, rng=None):
    return _lines(m, HANDS['panels'], 'hands')


def _glow(m, table, colour, kind):
    """Its coloured lines and plates, cut out of its human skin: where its three colourings differ (the coloured
    lines), or where it is black or white (its black lines, white plates). RGBA; the skin itself is clear."""
    Ts = {c: _on(m, table[c], kind) for c in ('blue', 'pink', 'green')}
    T = Ts[colour]
    rgb = T[..., :3]
    spread = np.max(np.stack([np.abs(Ts[a][..., :3] - Ts[b][..., :3]).max(-1)
                              for a, b in (('blue', 'pink'), ('pink', 'green'), ('green', 'blue'))]), axis=0)
    lum = _lum(rgb)
    sat = rgb.max(-1) - rgb.min(-1)
    coloured = np.clip((spread - GLOW_SAT * 0.5) / (GLOW_SAT * 0.5), 0, 1)
    black = np.clip((GLOW_BLACK - lum) / (GLOW_BLACK * 0.5), 0, 1) * (sat < 0.12)
    white = np.clip((lum - GLOW_WHITE) / (1 - GLOW_WHITE), 0, 1) * (sat < 0.12)
    a = np.maximum(np.maximum(coloured, black), white) * m.covered
    out = np.zeros(m.covered.shape + (4,), np.float32)
    out[..., :3] = np.where((white > coloured)[..., None], GLOW_WHITE_LEVEL, rgb)
    out[..., 3] = a
    return out


def glow_body(m, rng, colour):
    return _glow(m, BODY, colour, 'body')


def glow_hands(m, rng, colour):
    return _glow(m, HANDS, colour, 'hands')


FACE_BLANK_PX = 9   # at 1024: solid black wider than this on its face texture is no face (the part of the UV its own
                    # back-of-head mesh replaces), not a line -- drawn, it put black wedges on the neck and crown


def _face(m):
    from scipy import ndimage
    T = _on(m, FACE, 'head')
    blank = ndimage.binary_opening(_lum(T[..., :3]) < 0.05, structure=np.ones((FACE_BLANK_PX, FACE_BLANK_PX)))
    return T, m.covered & ~ndimage.binary_dilation(blank, iterations=2)


def panels_face(m):
    """Face tint (blend Default): its synth face over the person's."""
    T, keep = _face(m)
    out = np.zeros(m.covered.shape + (4,), np.float32)
    out[..., :3] = T[..., :3]
    out[..., 3] = np.where(keep, PANELS_ALPHA, 0.0)
    return out


def panel_lines_face(m):
    """Face tint (blend Multiply): its synth face's dark lines only."""
    T, keep = _face(m)
    dark = 1 - np.clip((_lum(T[..., :3]) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1)
    f = np.where(keep, 1 - LINE_DEPTH * dark, 1.0)
    out = np.ones(m.covered.shape + (4,), np.float32)
    out[..., :3] = f[..., None]
    out[..., 3] = 1.0
    return out


def normal_texture(kind):
    """The pack's own normal map for a woman's body or hands (same UVs), or None for a man (its normals do not carry
    over to another UV layout)."""
    return SOURCE / NORMALS[kind]
