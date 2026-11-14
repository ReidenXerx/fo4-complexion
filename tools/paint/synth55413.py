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
    """One of the pack's textures as float RGBA at size x size (cached). 'filled:<rel>' is its glow body texture with
    its openings filled (_filled)."""
    key = (rel, size)
    if key not in _cache:
        _need()
        from PIL import Image
        if rel.startswith(FILLED):
            im = Image.fromarray((np.clip(_filled(rel[len(FILLED):]), 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')
        else:
            im = Image.open(SOURCE / rel).convert('RGBA')
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        _cache[key] = np.asarray(im, np.float32) / 255.0
    return _cache[key]


# Glow Lines: its body textures open the knees (and spine) as solid black ovals; cut out as they are, they read in game
# as holes into nothing with a torn rim (Fo4-mcp v14 11-14). Filled with its own glowing network (the background it
# draws between its pieces), they read as lit internals. Same patch in all three colourings, so the cut-out still
# tells the network's lines (they differ by colour) from its dark.
FILLED = 'filled:'
GLOW_HOLE_PX = 25             # at 4096: solid black wider than this is an opening (its lines run ~12 px)
GLOW_HOLE_SIZE = 4096


def _network_patch():
    """(y0, x0, size) of the largest square of its texture no body piece covers, at GLOW_HOLE_SIZE."""
    if 'netpatch' not in _cache:
        from scipy import ndimage
        from body import UVMap
        import make_marks as mm
        cov = UVMap(mm.DATA, 'female', GLOW_HOLE_SIZE).covered
        free = ndimage.binary_erosion(~cov, iterations=8, border_value=0)
        d = ndimage.distance_transform_cdt(free, metric='chessboard')
        y, x = np.unravel_index(int(np.argmax(d)), d.shape)
        r = int(d[y, x])
        _cache['netpatch'] = (y - r, x - r, 2 * r)
        _cache['netcov'] = cov
    return _cache['netpatch']


def _filled(rel):
    from scipy import ndimage
    T = _tex(rel, GLOW_HOLE_SIZE).copy()
    y0, x0, P = _network_patch()
    cov = _cache['netcov']
    holes = ndimage.binary_opening((_lum(T[..., :3]) < GLOW_BLACK) & cov,
                                   structure=np.ones((GLOW_HOLE_PX, GLOW_HOLE_PX), bool))
    lab, n = ndimage.label(holes)

    def mirror(v):
        v = v % (2 * P)
        return np.where(v < P, v, 2 * P - 1 - v)
    for k, sl in enumerate(ndimage.find_objects(lab), 1):   # each opening centred on the patch's middle (its edges
        ys, xs = np.nonzero(lab[sl] == k)                    # can fall on the network's dark)
        cy, cx = ys.mean(), xs.mean()
        sy = mirror((ys - cy + P / 2).astype(np.int64))
        sx = mirror((xs - cx + P / 2).astype(np.int64))
        T[ys + sl[0].start, xs + sl[1].start] = T[y0 + sy, x0 + sx]
    return T


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


REFINE_K = 8           # neighbours a carried-over texel blends its female UV from
REFINE_ISLAND_PX = 3   # ... only those this close in the female UVs to the best match (same island, no seam jumps)
SAMPLE_SIZE = {'body': 4096, 'hands': 2048}   # the women's textures sampled (bilinear) at these sizes for the men


def _refine(cand_idx, dist, agree, pick, S):
    """Female UVs (n x 2, 0..1) for carried-over texels: the best-facing neighbour's UV blended (inverse distance)
    with its same-island neighbours'. The nearest texel alone (a 2048 map under a 4096 one) drew men's lines as
    stair steps with ragged edges (in game 11-14, LitFix); blending gives a sub-texel position to sample from."""
    n = len(pick)
    cu = np.stack(((cand_idx % S + 0.5) / S, (cand_idx // S + 0.5) / S), -1)          # n x k x 2
    best = cu[np.arange(n), pick]
    same = np.abs(cu - best[:, None]).max(-1) <= REFINE_ISLAND_PX / S
    same &= agree >= agree[np.arange(n), pick][:, None] - 0.3
    eps = max(float(np.median(dist[:, 0])) * 0.25, 1e-6)
    w = same / (dist + eps)
    return (w[..., None] * cu).sum(1) / w.sum(1)[:, None]


def _sample(T, uv):
    """Bilinear sample of T (H x W x C) at UVs (n x 2, 0..1)."""
    H, W = T.shape[:2]
    x = np.clip(uv[:, 0] * W - 0.5, 0, W - 1)
    y = np.clip(uv[:, 1] * H - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return ((T[y0, x0] * (1 - fx) + T[y0, x1] * fx) * (1 - fy)
            + (T[y1, x0] * (1 - fx) + T[y1, x1] * fx) * fy)


def _body_map(m):
    """Per covered texel of a male body map: its female UV (0..1, NaN where none matches)."""
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
    out = np.full((len(mi), 2), np.nan)
    for r in np.unique(MR):
        src = np.flatnonzero(FR == r)
        dst = np.flatnonzero(MR == r)
        if not len(src) or not len(dst):
            continue
        tree = cKDTree(FX[src])
        for a in range(0, len(dst), 400000):
            d = dst[a:a + 400000]
            _dist, nb = tree.query(MXn[d], k=REFINE_K)
            agree = np.einsum('nkc,nc->nk', FN[src[nb]], MN[d])
            pick = np.argmax(agree[:, :6] - 0.02 * _dist[:, :6], axis=1)   # the nearest that faces the same way
            out[d] = _refine(fi[src[nb]], _dist, agree, pick, f.size)
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
    out = np.full((len(mi), 2), np.nan)
    for side in (1, -1):
        fs, ms = np.flatnonzero(FX[:, 0] * side > 0), np.flatnonzero(MX[:, 0] * side > 0)
        if not len(fs) or not len(ms):
            continue
        flo, fhi = FX[fs].min(0), FX[fs].max(0)
        mlo, mhi = MX[ms].min(0), MX[ms].max(0)
        P = flo + (MX[ms] - mlo) / np.maximum(mhi - mlo, 1e-6) * (fhi - flo)
        _dist, nb = cKDTree(FX[fs]).query(P, k=REFINE_K)
        agree = np.einsum('nkc,nc->nk', FN[fs[nb]], MN[ms])
        pick = np.argmax(agree[:, :6] - 0.02 * _dist[:, :6], axis=1)
        out[ms] = _refine(fi[fs[nb]], _dist, agree, pick, f.size)
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
    out = np.zeros((m.size * m.size, 4), np.float32)
    if kind == 'head':
        T = _tex(rel, got[2]).reshape(-1, 4)
        ok = src >= 0
        out[mi[ok]] = T[src[ok]]
    else:   # body / hands: female UVs, sampled smoothly from the full-size texture
        ok = np.isfinite(src[:, 0])
        out[mi[ok]] = _sample(_tex(rel, SAMPLE_SIZE[kind]), src[ok])
    return out.reshape(m.size, m.size, 4)


def _lum(rgb):
    return rgb @ np.array((0.3, 0.59, 0.11), np.float32)


# ---------------------------------------------------------------- the painters


# Plates drawn in the pack's own colours with a fresh grain (FB_1 at 4096 measured 11-14: plates 0.69 grey, grain std
# 0.047 falling off like white noise blurred 0.8 px; lines 0.002). The knee openings' mask (Glow) is smoothed and cut
# with a soft edge.
REDRAW_SIGMA = 1.5            # px: mask smoothing
REDRAW_EDGE = (0.38, 0.62)    # the smoothed mask's soft cut
PLATE_GREY, PLATE_GRAIN, PLATE_GRAIN_PX = 0.69, 0.047, 0.8
LINE_BLACK = 0.002


# Men's lines RETRACED in 3D. Redrawn from the carried-over mask they were still "chunky ... drawn on rather
# than machined ... misaligned ... disappear randomly" (alasdairn, v16, 11-14): the texel-by-texel carry-over thickens,
# warps and breaks a line wherever the body match stretches or jumps, and loses it across UV seams. Now the women's
# own line centrelines (thinned from its clean texture) are carried onto the man's body as 3D points, and every texel
# of his is drawn by its 3D distance to them at one width in world units: even, crisp, continuous across seams.
RETRACE_W = 0.16              # world units: the men's line width (the women's pack lines run ~0.35, hand-drawn)
RETRACE_MATCH_PX = 3          # a centreline point needs a man's texel matched within this many of the women's texels
RETRACE_SPUR_PX = 10          # centreline twigs shorter than this (women's texels) are thinning noise, not lines
RETRACE_MIN_PX = 15           # ... and so are pieces this small
RETRACE_SMOOTH_PX = 1.5       # the distance field blurred this much (texels) before the cut: the centreline's 1-texel
                              # stair steps no longer show as a jagged edge (averaging the 3D points instead clumped
                              # them into beads)


def _prune(sk, k):
    """A centreline without its twigs shorter than k: ends eaten back k steps, then only the true ends regrown."""
    from scipy.ndimage import convolve, binary_dilation
    K = np.ones((3, 3), np.uint8)
    K[1, 1] = 0
    s = sk.copy()
    for _ in range(k):
        end = s & (convolve(s.astype(np.uint8), K, mode='constant') == 1)
        if not end.any():
            break
        s &= ~end
    grow = s & (convolve(s.astype(np.uint8), K, mode='constant') == 1)
    for _ in range(k):
        new = binary_dilation(grow, structure=np.ones((3, 3), bool)) & sk & ~s
        if not new.any():
            break
        s |= new
        grow = new
    return s


def _female_cov(kind):
    """The women's body or hands coverage at SAMPLE_SIZE (cached)."""
    S = SAMPLE_SIZE[kind]
    fkey = ('fmap', kind, S)
    if fkey not in _cache:
        import make_marks as mm
        if kind == 'hands':
            import hands
            _cache[fkey] = hands.HandMap(mm.DATA, 'female', S).covered
        else:
            from body import UVMap
            _cache[fkey] = UVMap(mm.DATA, 'female', S).covered
    return _cache[fkey]


def _retrace(m, rel, kind, width=RETRACE_W, fmask=None, tag='lines'):
    """Line coverage (0..1, m.size square) for a man's map m: the centrelines of the women's line mask (fmask, at
    SAMPLE_SIZE; default: texture rel's dark lines) carried onto his body in 3D, drawn width (world units) wide."""
    rkey = ('retrace', tag, rel, kind, getattr(m, 'sex', None), m.size)
    if rkey not in _cache:
        _cache[rkey] = _retrace_once(m, rel, kind, width, fmask)
    return _cache[rkey]


def _line_mask(rel, S):
    """The pack texture rel's dark lines at S, smoothed."""
    from scipy.ndimage import gaussian_filter
    T = _tex(rel, S)
    dark = 1 - np.clip((_lum(T[..., :3]) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1)
    return gaussian_filter(dark, 1.5) > 0.5


def _retrace_once(m, rel, kind, width, fmask):
    from scipy.spatial import cKDTree
    S = SAMPLE_SIZE[kind]
    if fmask is None:
        fmask = _line_mask(rel, S)
    ys, xs = np.nonzero(_centreline(fmask & _female_cov(kind)))
    fuv = np.stack(((xs + 0.5) / S, (ys + 0.5) / S), -1)
    if getattr(m, 'sex', None) == 'female':              # her own UVs: every covered texel is its own match
        mi = np.flatnonzero(m.covered)
        yy, xx = np.divmod(mi, m.size)
        src = np.stack(((xx + 0.5) / m.size, (yy + 0.5) / m.size), -1)
    else:
        _on(m, rel, kind)                                # builds the man's texel -> women's UV correspondence
        mi, src = _cache[(kind, getattr(m, 'sex', None), getattr(m, 'head', None), m.size)][:2]
    ok = np.isfinite(src[:, 0])
    mi, src = mi[ok], src[ok]
    d, j = cKDTree(src).query(fuv, distance_upper_bound=RETRACE_MATCH_PX / S)
    hit = np.isfinite(d)
    return _draw_lines(m, m.position.reshape(-1, 3)[mi[j[hit]]], width)


def _centreline(fmask):
    """The thinned, pruned centreline of a line mask (no twigs, no crumbs)."""
    from scipy.ndimage import label
    from synthskin import _thin
    sk = _prune(_thin(fmask), RETRACE_SPUR_PX)
    lab, n = label(sk, structure=np.ones((3, 3), bool))
    if n:
        size = np.bincount(lab.ravel())
        sk &= size[lab] >= RETRACE_MIN_PX
    return sk


def _draw_lines(m, P, width):
    """Coverage (0..1) of map m's texels within width/2 (world units) of the 3D centreline points P."""
    from scipy.ndimage import gaussian_filter
    from scipy.spatial import cKDTree
    cov = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[cov]
    dist, _ = cKDTree(P).query(X, distance_upper_bound=width * 3)
    G = m.position
    step = np.linalg.norm(G[:, 1:] - G[:, :-1], axis=-1)[m.covered[:, 1:] & m.covered[:, :-1]]
    aa = float(np.median(step))                           # one texel in world units: the edge's soft width
    D = np.full(m.size * m.size, width * 3, np.float32)
    D[cov] = np.minimum(dist, width * 3)
    D = D.reshape(m.size, m.size)
    c = m.covered.astype(np.float32)
    D = gaussian_filter(D * c, RETRACE_SMOOTH_PX) / np.maximum(gaussian_filter(c, RETRACE_SMOOTH_PX), 1e-3)
    return np.clip((width / 2 - D) / aa + 0.5, 0, 1) * m.covered


def _plates(line, cov, seed):
    """The women's plate grey with a fresh grain, its line black where line says."""
    from scipy.ndimage import gaussian_filter
    g = gaussian_filter(np.random.default_rng(seed).standard_normal(cov.shape).astype(np.float32), PLATE_GRAIN_PX)
    g *= PLATE_GRAIN / max(float(g.std()), 1e-6)
    v = (PLATE_GREY + g) * (1 - line) + LINE_BLACK * line
    out = np.zeros(cov.shape + (4,), np.float32)
    out[..., :3] = np.clip(v, 0, 1)[..., None]
    out[..., 3] = cov
    return out


# Women retraced too: their pack lines as they come (hand-drawn pixels, ~0.35 wide, scaled down) read "shit, the same
# as kneecap says" on a female body (ilhamitaa24, #management 11-14) -- the same bar as the men's: thin, even, machined.
def _men_panels(m, rel, kind):
    """The pack's panels texture on map m, its lines retraced in 3D (women on their own UVs, men carried over)."""
    return _plates(_retrace(m, rel, kind), m.covered, 55413 + (kind == 'hands'))


def _panels(m, rel, kind):
    T = _men_panels(m, rel, kind)
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
    T = _men_panels(m, rel, kind)
    dark = 1 - np.clip((_lum(T[..., :3]) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1)
    f = np.where(m.covered, 1 - LINE_DEPTH * dark, 1.0)
    return _multiply(m, f)


def panel_lines_body(m, rng=None):
    return _lines(m, BODY['panels'], 'body')


def panel_lines_hands(m, rng=None):
    return _lines(m, HANDS['panels'], 'hands')


def _glow_cut(Ts, colour, cov):
    """(rgb, alpha) of its cut-out from the three colourings Ts (float RGBA, same grid)."""
    rgb = Ts[colour][..., :3]
    spread = np.max(np.stack([np.abs(Ts[a][..., :3] - Ts[b][..., :3]).max(-1)
                              for a, b in (('blue', 'pink'), ('pink', 'green'), ('green', 'blue'))]), axis=0)
    lum = _lum(rgb)
    sat = rgb.max(-1) - rgb.min(-1)
    coloured = np.clip((spread - GLOW_SAT * 0.5) / (GLOW_SAT * 0.5), 0, 1)
    black = np.clip((GLOW_BLACK - lum) / (GLOW_BLACK * 0.5), 0, 1) * (sat < 0.12)
    white = np.clip((lum - GLOW_WHITE) / (1 - GLOW_WHITE), 0, 1) * (sat < 0.12)
    a = np.maximum(np.maximum(coloured, black), white) * cov
    return np.where((white > coloured)[..., None], GLOW_WHITE_LEVEL, rgb), a


# Men's Glow: its bands between the skin pieces retraced like the Panels lines (one even width, in 3D, across seams);
# its wide parts (white plates, the filled openings) kept as carried over, edges smoothed. Band texels the carry-over
# left without glow take the colour of the nearest one that has it (alasdairn's "do it all", v16 11-14).
GLOW_W = 0.22                 # world units: the glow band width
GLOW_NET_FLOOR = 0.45         # the bands' least glow, as a share of the network's vein colour


def _glow(m, table, colour, kind):
    """Its coloured lines and plates, cut out of its human skin: where its three colourings differ (the coloured
    lines), or where it is black or white (its black lines, white plates). RGBA; the skin itself is clear."""
    Ts = {c: _on(m, table[c], kind) for c in ('blue', 'pink', 'green')}
    rgb, a = _glow_cut(Ts, colour, m.covered)
    rgb, a = _glow_men(m, table, kind, rgb, a, colour)
    out = np.zeros(m.covered.shape + (4,), np.float32)
    out[..., :3] = rgb
    out[..., 3] = a
    return out


# v17 in game (Fo4-mcp 11-14): the wide parts kept as carried over still read torn and uneven, a white stripe ran down
# the back of the hand and its groin QR code came out a blue block. So for men everything but the knee openings is
# retraced: its whole cut-out (bands, white plates) becomes even network bands; the openings are carried (they read
# right); its decals (QR codes, the MK.4 label) are left out -- carried over they can only smear.
GLOW_DECALS = ((0.098, 0.256, 0.03, 0.03), (0.902, 0.256, 0.03, 0.03), (0.5, 0.933, 0.03, 0.03),
               (0.5, 0.75, 0.035, 0.015))   # women's body UV: centre u, v, half width, half height


def _female_holes(table, kind):
    """The women's openings (solid black wider than GLOW_HOLE_PX) at SAMPLE_SIZE, as a mask texture the carry-over can
    sample: registered in the texture cache under 'holes:<kind>'."""
    from scipy import ndimage
    S = SAMPLE_SIZE[kind]
    key = 'holes:' + kind
    if (key, S) not in _cache:
        raw = table['blue'][len(FILLED):] if table['blue'].startswith(FILLED) else table['blue']
        T = _tex(raw, S)
        hw = max(3, int(round(GLOW_HOLE_PX * S / 4096)))
        H = ndimage.binary_opening((_lum(T[..., :3]) < GLOW_BLACK) & _female_cov(kind), structure=np.ones((hw, hw), bool))
        if kind == 'hands':
            H[:] = False
        img = np.zeros((S, S, 4), np.float32)
        img[..., 0] = H
        img[..., 3] = 1
        _cache[(key, S)] = img
    return key, _cache[(key, S)][..., 0] > 0.5


def _glow_men(m, table, kind, rgb, a, colour):
    from scipy import ndimage
    S = SAMPLE_SIZE[kind]
    fcov = _female_cov(kind)
    # the gaps between its skin pieces, whole: not skin (the cut-out keeps only the veins and the near-black, so the
    # navy between the veins fell out and the bands were traced from scattered veins: dashes, v18 in game 11-14)
    Tb = _tex(table['blue'], S)
    r, g, b = Tb[..., 0], Tb[..., 1], Tb[..., 2]
    lum = _lum(Tb[..., :3])
    gap = (b >= r) | (lum < 0.15) | (lum > GLOW_WHITE)
    gap = ndimage.gaussian_filter(gap.astype(np.float32), 1.5) > 0.5
    hkey, holes_f = _female_holes(table, kind)
    keep = gap & fcov & ~ndimage.binary_dilation(holes_f, iterations=2)
    if kind == 'body':
        yy, xx = np.mgrid[0:S, 0:S]
        u, v = (xx + 0.5) / S, (yy + 0.5) / S
        for cu, cv, hu, hv in GLOW_DECALS:
            keep &= ~((np.abs(u - cu) < hu) & (np.abs(v - cv) < hv))
    band = _retrace(m, table['blue'], kind, width=GLOW_W, fmask=keep, tag='glow')
    female = getattr(m, 'sex', None) == 'female'
    if female:   # her own UVs: the openings mask straight, at her size
        holes = ndimage.zoom(holes_f.astype(np.float32), m.size / S, order=1)
    else:
        holes = _on(m, hkey, kind)[..., 0]
    c = m.covered.astype(np.float32)
    holes = ndimage.gaussian_filter(holes * c, REDRAW_SIGMA) / np.maximum(ndimage.gaussian_filter(c, REDRAW_SIGMA), 1e-3)
    t = np.clip((holes - REDRAW_EDGE[0]) / (REDRAW_EDGE[1] - REDRAW_EDGE[0]), 0, 1)
    holes = t * t * (3 - 2 * t)
    alpha = np.maximum(band, holes) * m.covered
    # the bands: its own glowing network (the patch the openings are filled from), in this colouring, at its scale
    y0, x0, P = _network_patch()
    T4 = _tex(BODY[colour], GLOW_HOLE_SIZE)
    k = GLOW_HOLE_SIZE / m.size

    def mirror(w):
        w = w % (2 * P)
        return np.where(w < P, w, 2 * P - 1 - w)
    yy, xx = np.mgrid[0:m.size, 0:m.size]
    net = T4[y0 + mirror((yy * k).astype(np.int64)), x0 + mirror((xx * k).astype(np.int64)), :3]
    # never black: the patch is mostly dark between its veins (median lum .03-.06), so a band this thin read as a black
    # line wherever no vein crossed it (men v19, women's preview 11-14). Floored at a share of its own vein colour.
    Pt = T4[y0:y0 + P, x0:x0 + P, :3]
    L = _lum(Pt)
    vein = Pt[L >= np.percentile(L, 95)].mean(0)
    hue = (vein - vein.min()) / max(float(vein.max() - vein.min()), 1e-3)   # its pure colour: the vein alone read slate
    net = np.maximum(net, GLOW_NET_FLOOR * (0.5 * vein + 0.5 * hue))
    # its decals are left out for women too: both sexes match (ilhamitaa24 "I'd say remove them", #management 11-14)
    return np.where((holes >= band)[..., None], rgb, net), alpha


def glow_body(m, rng, colour):
    return _glow(m, {c: FILLED + BODY[c] for c in ('blue', 'pink', 'green')}, colour, 'body')


def glow_hands(m, rng, colour):
    return _glow(m, HANDS, colour, 'hands')


FACE_BLANK_PX = 9   # at 1024: solid black wider than this on its face texture is no face (the part of the UV its own
                    # back-of-head mesh replaces), not a line -- drawn, it put black wedges on the neck and crown


FACE_BLANK_AREA = 4000   # at 1024: ... except a smaller one lower than the nose tip: there its lines widen along the
                         # jaw and neck (taken as blank, they left holes of bare skin, Fo4-mcp v14 11-14); measured on
                         # both heads, the eye corners sit 2.4-3 units above the nose tip, every line end 1.8+ below
FACE_BLANK_ABOVE_NOSE = -1.0


def _face_lines(m):
    """Line coverage on head map m: its face's line centrelines (on the vanilla female head, blanks left out) carried
    in 3D and drawn RETRACE_W wide, like the bodies' (both sexes: its own read uneven and wedged, 11-14)."""
    key = ('faceline', getattr(m, 'head', None), m.size)
    if key not in _cache:
        from scipy import ndimage
        from scipy.spatial import cKDTree
        import face
        fk = ('fhead', m.size)
        if fk not in _cache:
            _cache[fk] = face.HeadMap('human_female', m.size)
        f = _cache[fk]
        S = f.size
        blank_f = _face_blank(f, _tex(FACE, S))
        sk = _centreline(_line_mask(FACE, S) & f.covered & ~ndimage.binary_dilation(blank_f, iterations=2))
        cidx = np.flatnonzero(sk)
        if getattr(m, 'head', None) == 'human_female':
            P = m.position.reshape(-1, 3)[cidx]
        else:
            mi, fi, _ = _head_map(m)
            fy, fx = np.divmod(fi, S)
            cy, cx = np.divmod(cidx, S)
            d, j = cKDTree(np.stack((fx, fy), -1)).query(np.stack((cx, cy), -1), distance_upper_bound=RETRACE_MATCH_PX)
            P = m.position.reshape(-1, 3)[mi[j[np.isfinite(d)]]]
        _cache[key] = _draw_lines(m, P, RETRACE_W)
    return _cache[key]


def _face(m):
    from scipy import ndimage
    T = _on(m, FACE, 'head')
    blank = _face_blank(m, T)
    T = _plates(_face_lines(m), m.covered, 55413 + 7)
    return T, m.covered & ~ndimage.binary_dilation(blank, iterations=2)


def _face_blank(m, T):
    """Where its face texture T (on head map m) is no face: big solid black, or above the nose."""
    from scipy import ndimage
    import synthskin
    blank = ndimage.binary_opening(_lum(T[..., :3]) < 0.05, structure=np.ones((FACE_BLANK_PX, FACE_BLANK_PX)))
    lab, n = ndimage.label(blank)
    if n:
        idx = np.arange(1, n + 1)
        area = ndimage.sum(np.ones_like(lab), lab, index=idx)
        z = m.position[..., 2]
        mz = ndimage.mean(z, lab, index=idx)
        nose = synthskin.face_landmarks(m)['nose'][2]
        keep_blank = np.zeros(n + 1, bool)
        keep_blank[1:] = (area >= FACE_BLANK_AREA * (m.covered.shape[0] / 1024) ** 2) | (mz >= nose + FACE_BLANK_ABOVE_NOSE)
        blank = keep_blank[lab]
    return blank


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


BEVEL_SIGMA, BEVEL_K = 1.5, -2.4   # per 2048 px: fitted to the women's pack normal (corr .76 on x and y, 11-14)


def bevel_normal(rgb):
    """A tangent-space normal map (RGB 0..1) for Panels (both sexes): the plates' bevelled edges from its own lines, the way
    the women's pack normal has them. Men without it (the game's body normal) drew their lines brown and soft (in game
    11-14, LitFix); the pack normal cannot be carried over (another UV layout, other tangents)."""
    from scipy.ndimage import gaussian_filter
    s = rgb.shape[0] / 2048
    H = gaussian_filter(np.clip((_lum(rgb) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1), BEVEL_SIGMA * s)
    gy, gx = np.gradient(H)
    k = BEVEL_K * s
    n = np.stack((k * gx, k * gy, np.ones_like(H)), -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5
