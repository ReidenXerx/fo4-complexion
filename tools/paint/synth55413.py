"""Synthetic skin from Synth Looksmenu Skin Override (Nexus 55413, patrox5 / patrox6 on Nexus; its textures by Aaron4412,
Nexus 35269) as Complexion overlays -- alasdairn, 2026-11-14: "All three, see if you can make a male version too".

    The pack is a LooksMenu SKIN for women: whole body, hands and face textures in the game's own female UVs, which are
    our women's UVs exactly (checked by rendering them straight onto our body). Three looks are made from it:

    Panels       -- its grey plating with black panel lines, a lit overlay (like synthskin's Plated) over body and
                   hands; a face tint from its synth face.
    Panel Lines  -- only its dark panel lines (and joints, rivets) multiplied into the character's own skin; a face
                   tint from the same.
    Glow Lines   -- the bands between its skin pieces filled with its glowing network (blue, pink, green), as an UNLIT
                   alpha-blended overlay: unlit, the colours glow, as the pack's lines are meant to.

    Its lines are not copied as pixels: their centrelines are taken from its textures, carried as 3D points (onto a man
    through bodywarp's one warp of her body + hands onto his) and drawn again at one width in world units on whichever
    mesh they land. Heads: matched by nose and chin.

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
GLOW_BLACK, GLOW_WHITE = 0.14, 0.80  # Glow Lines: a grey this dark or this light is one of its black lines or plates

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


# Glow Lines: its body textures open the knees (and spine) as solid black ovals; cut out as they are, they read in game
# as holes into nothing with a torn rim (Fo4-mcp v14 11-14). Filled with its own glowing network (the background it
# draws between its pieces), they read as lit internals.
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
    return _cache['netpatch']


# ---------------------------------------------------------------- women's textures onto men's heads


SAMPLE_SIZE = {'body': 4096, 'hands': 2048}   # the women's maps its lines are traced at


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


def _on(m, rel, kind='head'):
    """The pack's face texture rel as it falls on head map m (float RGBA, m.size square): straight for the vanilla
    female head, carried over from it for every other head."""
    if getattr(m, 'head', None) == 'human_female':
        return _tex(rel, m.size)
    key = (kind, getattr(m, 'sex', None), getattr(m, 'head', None), m.size)
    if key not in _cache:
        _cache[key] = _head_map(m)
    mi, src, fsize = _cache[key]
    out = np.zeros((m.size * m.size, 4), np.float32)
    T = _tex(rel, fsize).reshape(-1, 4)
    ok = src >= 0
    out[mi[ok]] = T[src[ok]]
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


def _female_map(kind):
    """The women's body or hands map at SAMPLE_SIZE (cached)."""
    S = SAMPLE_SIZE[kind]
    key = ('fmapobj', kind, S)
    if key not in _cache:
        import make_marks as mm
        if kind == 'hands':
            import hands
            _cache[key] = hands.HandMap(mm.DATA, 'female', S)
        else:
            from body import UVMap
            _cache[key] = UVMap(mm.DATA, 'female', S)
    return _cache[key]


def _female_cov(kind):
    return _female_map(kind).covered


def _frame_pos(m, kind):
    """Map m's texel positions in its body's frame: a hands map's are moved onto the body (bodywarp.hands_to_body)."""
    key = ('framepos', kind, getattr(m, 'sex', None), m.size)
    if key not in _cache:
        pos = m.position
        if kind == 'hands':
            import bodywarp
            pos = bodywarp.hands_to_body(m.sex)(pos.reshape(-1, 3)).reshape(pos.shape)
        _cache[key] = pos
    return _cache[key]


MESH = {'body': 0, 'hands': 1}


def _carried(tag, masks, sex):
    """{kind: 3D points, 'bridges': 3D points} in sex's body frame: the women's texels set in masks ({kind: callable ->
    mask at SAMPLE_SIZE}), thinned to centrelines unless tag ends in ':fill', carried onto sex through bodywarp; the
    bridges join line ends across seams (both meshes')."""
    key = ('carried', tag, sex)
    if key not in _cache:
        import bodywarp
        out, ends = {}, []
        for kind, mask in masks.items():
            ck = ('centre', tag, kind)
            if ck not in _cache:
                msk = mask() & _female_cov(kind)
                _cache[ck] = msk if tag.endswith(':fill') else _centreline(msk)
            sk = _cache[ck]
            idx = np.flatnonzero(sk)
            X = bodywarp.carry(_frame_pos(_female_map(kind), kind).reshape(-1, 3)[idx], MESH[kind], sex)
            if sex == 'male' and kind == 'body':   # lines and the openings on them alike (left behind, the
                from scipy.ndimage import label   # moved glow band had gaps where its ports were cut out, v24)
                X = _to_his_anatomy(X, label(sk, structure=np.ones((3, 3), bool))[0].ravel()[idx])
            out[kind] = X
            if not tag.endswith(':fill'):
                out[kind] = np.concatenate([X, _densify(sk, idx, X)])
                cut = _decal_cut(kind) if tag == 'glow' else None
                ends.append(_seam_ends(sk, idx, X, _female_cov(kind), len(ends), cut))
        out['bridges'] = _stitch(ends, None) if ends else np.zeros((0, 3))
        if 'body' in out and 'hands' in out:
            _overlap(out, sex)
        _cache[key] = out
    return _cache[key]


# Men: his anatomy, not hers ("The layout for men should follow male anatomy", alasdairn v23 11-15). Carried by the
# warp alone her front layout sat on her landmarks: the arch she draws under her breasts ran across his stomach (0,-26.6
# down to +-10.8,-32.3) and her abdominal panel began below it. On him the arch is his pec bottoms (measured on his
# mesh: the crease at -24 on the nipple line, rising to the armpit), the panel his rectus from there to the pubis, the
# side panels his obliques up under the armpit. A thin-plate spline in (x, z) over his torso's front carries each of
# her landmarks to his (read off a gridded 3D render of the v23 men's lines, 11-15); navel, groin, collarbones, nipples
# and the sides stay put; the back is untouched.
HIS_TORSO = (   # (x, z) where her line lies on him -> (x, z) where his anatomy has it; mirrored for -x
    ((0.0, -26.6), (0.0, -23.8)),     # arch apex -> his pec bottoms meeting at the sternum
    ((4.5, -28.5), (4.6, -23.6)),     # arch / abdominal panel junction -> pec bottom, top of his rectus
    ((6.5, -29.6), (6.5, -23.4)),     # arch -> his crease rising under the pec
    ((8.0, -30.4), (8.5, -23.2)),     # arch under the breast -> his pec bottom crease on the nipple line
    ((10.8, -32.3), (12.2, -21.8)),   # arch's outer end -> his pec's lower corner at the armpit
    # v24 in game (Fo4-mcp 11-15): ~1 unit low and straight; his crease curves up under each pec
    ((6.9, -39.7), (6.5, -39.7)),     # the panel's side at the navel -> his rectus edge
)
HIS_TORSO_FIXED = ((0.0, -39.7), (0.0, -16.3), (5.0, -16.0), (10.0, -14.8), (14.0, -17.0), (8.7, -21.5),
                   (13.0, -36.0), (12.0, -44.0), (9.0, -48.0), (4.0, -50.0), (0.0, -48.0), (0.0, -54.0), (6.0, -56.0))


RIVET_MAX = 1.0   # world units: a line piece smaller than this (a rivet ring) moves whole, so it stays round


def _to_his_anatomy(X, comp=None):
    """Her front torso lines (on his body, Nx3; comp: their centreline piece per point) moved onto his landmarks
    (HIS_TORSO), laid back on his surface."""
    from scipy.interpolate import RBFInterpolator
    from scipy.spatial import cKDTree
    import bodywarp
    from body import REGIONS
    src, dst = [], []
    for (a, b) in HIS_TORSO:
        for s in ((1, -1) if a[0] else (1,)):
            src.append((a[0] * s, a[1])); dst.append((b[0] * s, b[1]))
    for a in HIS_TORSO_FIXED:
        for s in ((1, -1) if a[0] else (1,)):
            src.append((a[0] * s, a[1])); dst.append((a[0] * s, a[1]))
    src, dst = np.array(src), np.array(dst)
    f = RBFInterpolator(src, dst - src, kernel='thin_plate_spline', smoothing=0.0)
    V, N, R, _A, I = bodywarp._mesh('male')
    body = np.flatnonzero(I == 0)
    tree = cKDTree(V[body])
    _d, j = tree.query(X)
    torso = R[body[j]] == REGIONS.index('torso')
    w = np.clip((X[:, 1] + 1.0) / 3.0, 0, 1) * torso          # his front (+y), fading out round his sides
    w *= np.clip((X[:, 2] + 12.0) / -2.0, 0, 1) * np.clip((X[:, 2] + 62.0) / 4.0, 0, 1)   # under the neck, above the thighs
    sel = np.flatnonzero(w > 0)
    if not len(sel):
        return X
    d = f(X[sel][:, [0, 2]]) * w[sel, None]
    if comp is not None:   # rivets whole: stretched with the panels they came out as tall ellipses (11-15)
        c = comp[sel]
        for k in np.unique(c):
            m = c == k
            P = X[sel[m]]
            if np.ptp(P, axis=0).max() < RIVET_MAX:
                d[m] = d[m].mean(0)
    Y = X.copy()
    Y[sel, 0] += d[:, 0]
    Y[sel, 2] += d[:, 1]
    _d, j = tree.query(Y[sel])                                # back onto his surface
    v, n = V[body[j]], N[body[j]]
    Y[sel] -= np.einsum('nc,nc->n', Y[sel] - v, n)[:, None] * n
    _cache.setdefault('anatomy_log', []).append((len(sel), float(np.abs(d).max())))
    return Y


# The pack draws a wrist band on the body right at its edge, and another on the hands right at theirs: across the seam
# the two ran side by side, a double band (Fo4-mcp v22 11-15, Panels, both sexes). The hands' lines near the body's
# are drawn onto them: within MERGE_IN all the way, fading out by MERGE_OUT, so the lines leaving the band bend in.
MERGE_IN, MERGE_OUT = 0.35, 0.8   # world units


def _overlap(out, sex):
    from scipy.spatial import cKDTree
    B, H = out['body'], out['hands']
    if not len(B) or not len(H):
        return
    d, j = cKDTree(B).query(H, distance_upper_bound=MERGE_OUT)
    ok = np.isfinite(d)
    w = np.zeros(len(H))
    w[ok] = np.clip((MERGE_OUT - d[ok]) / (MERGE_OUT - MERGE_IN), 0, 1)
    H = H.copy()
    H[ok] += w[ok, None] * (B[j[ok]] - H[ok])
    full = w >= 0.999   # merged all the way: on the body's band now, past the hands' edge -- left to the body (on the
    _cache.setdefault('overlap_log', []).append((int((w > 0).sum()), int(full.sum())))   # hands they snapped back to
    out['hands'] = H[~full]                                                              # its edge: the double again)


# Its lines break at its own UV seams: a line drawn on two texture islands ends a little apart on each (the shin line
# above the ankle, "same on female body", ilhamitaa24 v21 11-14). In 3D the two ends are close and face each other:
# each end on an island's edge is bridged to the end (or, failing one, the line) it continues into.
SEAM_PX = 24        # at 4096: a line end this close to its island's edge ends at a seam (the pack stops them 14-19 short)
STITCH_R = 2.0      # world units: the furthest a seam gap is bridged
STITCH_CONE = 0.5   # the bridge must leave the end within ~60 degrees of the line's own direction


TEE_REACH = 1.0     # world units: any line end this close short of a line ahead of it is joined to it (his abdominal
                    # panel's sides stopped ~0.8 short of the moved pec line, v24 offline 11-15)
DECAL_REACH = 4.5   # world units: a band cut by a left-out decal (the MK.4 label on her sternum lies on the band under
                    # her breasts: on him the pec line came out in dashes, v24) is bridged across its box


def _decal_cut(kind):
    """The decal boxes Glow leaves out of its bands (women's UV, SAMPLE_SIZE)."""
    S = SAMPLE_SIZE[kind]
    if kind != 'body':
        return np.zeros((S, S), bool)
    yy, xx = np.mgrid[0:S, 0:S]
    u, v = (xx + 0.5) / S, (yy + 0.5) / S
    cut = np.zeros((S, S), bool)
    for cu, cv, hu, hv in GLOW_DECALS:
        cut |= (np.abs(u - cu) < hu) & (np.abs(v - cv) < hv)
    return cut


def _seam_ends(sk, idx, X, cov, k, cut=None):
    """(positions, outward directions, component ids, ..., reach) of the centreline sk's ends that lie on its island's
    edge or on the edge of a box cut out of it (cut)."""
    from scipy import ndimage
    S = sk.shape[0]
    K = np.ones((3, 3), np.uint8)
    K[1, 1] = 0
    deg = ndimage.convolve(sk.astype(np.uint8), K, mode='constant')
    # an end: its neighbours one run of at most two round its ring, all on one side. A tip thinned to a two-texel
    # clump has two neighbours touching each other: on deg == 1 alone his Glow abdominal sides never closed onto the
    # pec band (~0.6 short, Fo4-mcp v25 11-15)
    ring = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    pad = np.pad(sk, 1)
    nb = [pad[1 + dy:1 + dy + S, 1 + dx:1 + dx + sk.shape[1]] for dy, dx in ring]
    runs = sum((nb[i] & ~nb[i - 1]).astype(np.uint8) for i in range(8))
    end = sk & ((deg == 1) | ((deg == 2) & (runs == 1)))
    it = max(2, int(round(SEAM_PX * S / 4096)))
    edge = ndimage.binary_dilation(~cov, iterations=it)
    near_cut = ndimage.binary_dilation(cut, iterations=it) if cut is not None else np.zeros_like(sk)
    on_edge = edge | near_cut   # every other end may still close a T-junction a step ahead (TEE_REACH)
    lab, _ = ndimage.label(sk, structure=np.ones((3, 3), bool))
    at = np.full(sk.size, -1, np.int64)
    at[idx] = np.arange(len(idx))
    pos, out, comp, reach = [], [], [], []
    r = max(4, int(round(12 * S / 4096)))
    for e in np.flatnonzero(end.ravel()):
        y, x = divmod(int(e), S)
        win = lab[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] == lab[y, x]
        wy, wx = np.nonzero(win)
        nb = at[(wy + max(0, y - r)) * S + wx + max(0, x - r)]
        back = X[nb[nb >= 0]].mean(0) - X[at[e]]
        n = np.linalg.norm(back)
        if n < 1e-6:
            continue
        pos.append(X[at[e]]); out.append(-back / n); comp.append(k * 10_000_000 + lab[y, x])
        reach.append(DECAL_REACH if near_cut[y, x] else STITCH_R if on_edge[y, x] else TEE_REACH)
    if not pos:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0, np.int64), lab, at, X, k, np.zeros(0)
    return np.array(pos), np.array(out), np.array(comp), lab, at, X, k, np.array(reach)


def _stitch(ends, _unused=None):
    """Bridge points across the seam gaps: each seam end joined to the nearest other line's seam end ahead of it within
    STITCH_R (both facing each other), else to the nearest point of another line ahead of it."""
    from scipy.spatial import cKDTree
    E = np.concatenate([e[0] for e in ends])
    O = np.concatenate([e[1] for e in ends])
    C = np.concatenate([e[2] for e in ends])
    RE = np.concatenate([e[7] for e in ends])
    if not len(E):
        return np.zeros((0, 3))
    # every carried line point with its component, for end-to-line joins
    LP, LC = [], []
    for _pos, _out, _comp, lab, at, X, k, _r in ends:
        idx = np.flatnonzero(at >= 0)
        LP.append(X[at[idx]]); LC.append(k * 10_000_000 + lab.ravel()[idx])
    LP, LC = np.concatenate(LP), np.concatenate(LC)
    ltree = cKDTree(LP)
    etree = cKDTree(E)
    used = np.zeros(len(E), bool)
    bridges = []
    order = np.argsort([min((np.linalg.norm(E - E[i], axis=1) + (C == C[i]) * 1e9).min(), 1e9) for i in range(len(E))])
    for i in order:
        if used[i]:
            continue
        best, bd = None, RE[i]
        for j in etree.query_ball_point(E[i], RE[i]):
            if j == i or used[j] or C[j] == C[i]:
                continue
            v = E[j] - E[i]
            d = np.linalg.norm(v)
            if d < 1e-6:
                best, bd = j, 0.0
                break
            if v @ O[i] > STITCH_CONE * d and -v @ O[j] > 0 and d < bd:
                best, bd = j, d
        if best is not None:
            used[i] = used[best] = True
            bridges.append((E[i], E[best]))
            continue
        cand = ltree.query_ball_point(E[i], RE[i])
        best, bd = None, RE[i]
        for j in cand:
            if LC[j] == C[i]:
                continue
            v = LP[j] - E[i]
            d = np.linalg.norm(v)
            if d > 1e-6 and v @ O[i] > STITCH_CONE * d and d < bd:
                best, bd = j, d
        if best is not None:
            used[i] = True
            bridges.append((E[i], LP[best]))
    out = []
    for a, b in bridges:
        n = max(2, int(np.ceil(np.linalg.norm(b - a) / DENSE_STEP)))
        t = np.linspace(0, 1, n)[:, None]
        out.append(a * (1 - t) + b * t)
    _cache.setdefault('stitch_log', []).append(len(bridges))
    return np.concatenate(out) if out else np.zeros((0, 3))


DENSE_STEP = 0.03   # world units: carried centrelines are filled in to this spacing (the warp stretches them apart)


def _densify(sk, idx, X):
    """Points along each centreline step (8-connected texel pairs) between their carried 3D positions X, at most
    DENSE_STEP apart: where the warp stretched her texels further apart than a line's half width, his lines beaded."""
    S = sk.shape[1]
    at = np.full(sk.size, -1, np.int64)
    at[idx] = np.arange(len(idx))
    y, x = np.divmod(idx, S)
    out = []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        ny, nx = y + dy, x + dx
        ok = (ny < sk.shape[0]) & (nx >= 0) & (nx < S)
        j = np.full(len(idx), -1, np.int64)
        j[ok] = at[ny[ok] * S + nx[ok]]
        a = np.flatnonzero(j >= 0)
        if not len(a):
            continue
        A, B = X[a], X[j[a]]
        n = np.ceil(np.linalg.norm(B - A, axis=1) / DENSE_STEP).astype(np.int64)
        n = np.minimum(n, 64)   # a step longer than ~2 units is a seam jump, not a line
        far = np.linalg.norm(B - A, axis=1) > 2.0
        for k in range(1, int(n.max()) if len(n) else 1):
            sel = (n > k) & ~far
            if not sel.any():
                break
            t = (k / n[sel])[:, None]
            out.append(A[sel] * (1 - t) + B[sel] * t)
    return np.concatenate(out) if out else np.zeros((0, 3))


def _retrace(m, kind, tag, masks, width=RETRACE_W):
    """Line coverage (0..1, m.size square) on map m (body or hands): the women's line centrelines of masks for this
    mesh, carried in 3D onto m's sex, plus the seam bridges, drawn width (world units) wide. Only its own mesh's lines:
    with the other mesh's drawn too, the hands' wrist band ran beside the body's -- a double band (Fo4-mcp v22 11-14)."""
    key = ('retrace', tag, kind, getattr(m, 'sex', None), m.size, width)
    if key not in _cache:
        got = _carried(tag, masks, m.sex)
        P = np.concatenate([got.get(kind, np.zeros((0, 3))), got['bridges']])
        _cache[key] = _draw_lines(m, P, width, _frame_pos(m, kind)) if len(P) else np.zeros(m.covered.shape)
    return _cache[key]


def _line_mask(rel, S):
    """The pack texture rel's dark lines at S, smoothed."""
    from scipy.ndimage import gaussian_filter
    T = _tex(rel, S)
    dark = 1 - np.clip((_lum(T[..., :3]) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1)
    return gaussian_filter(dark, 1.5) > 0.5


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


SNAP_MAX = 0.6   # world units: a point this close to a map's surface is laid on it; further ones are another mesh's


def _draw_lines(m, P, width, pos=None):
    """Coverage (0..1) of map m's texels within width/2 (world units) of the 3D centreline points P (texel positions
    pos, default m.position)."""
    from scipy.ndimage import gaussian_filter
    from scipy.spatial import cKDTree
    G = m.position if pos is None else pos
    cov = np.flatnonzero(m.covered)
    X = G.reshape(-1, 3)[cov]
    # each point onto this map's own surface first (its nearest texel): laid on the tangent plane of his nearest (sparse)
    # vertex, a point on a curved limb sat up to ~0.1 off it -- more than half a line -- and the lines beaded (11-14)
    sd, sj = cKDTree(X).query(P, distance_upper_bound=SNAP_MAX)
    near = np.isfinite(sd)
    P = np.concatenate([X[sj[near]], P[~near]])
    dist, _ = cKDTree(P).query(X, distance_upper_bound=width * 3)
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
LINES = {'body': lambda: _line_mask(BODY['panels'], SAMPLE_SIZE['body']),
         'hands': lambda: _line_mask(HANDS['panels'], SAMPLE_SIZE['hands'])}


def _men_panels(m, rel, kind):
    """The pack's panels on map m: its plates, its lines retraced in 3D."""
    return _plates(_retrace(m, kind, 'lines', LINES), m.covered, 55413 + (kind == 'hands'))


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


# Glow: the bands between its skin pieces, retraced like the Panels lines (one even width, in 3D, across seams) and
# filled with its own glowing network; its knee (and spine) openings carried as filled shapes; its decals (QR codes,
# the MK.4 label) left out (carried they smear; ilhamitaa24 "I'd say remove them" for women too, 11-14).
GLOW_W = 0.22                 # world units: the glow band width
# Glow drawn on the Panel Lines layout (its plates' lines and rivets), not the pack's own sparser glow network: "Why is
# the male glow lines different from the seam lines?" (alasdairn v26 11-15). The openings (knees, spine) stay its own.
GLOW_ON_LINES = True
GLOW_NET_FLOOR = 0.45         # the bands' least glow, as a share of the network's vein colour
GLOW_FILL_W = 0.35            # world units: an opening is drawn wherever one of her opening texels lies within half this
                              # (the warp stretches them apart; at 4 of her texels his knees showed skin stripes)
GLOW_DECALS = ((0.098, 0.256, 0.03, 0.03), (0.902, 0.256, 0.03, 0.03), (0.5, 0.933, 0.03, 0.03),
               (0.5, 0.75, 0.035, 0.015))   # women's body UV: centre u, v, half width, half height
GLOW_TABLE = {'body': BODY['blue'], 'hands': HANDS['blue']}


def _female_holes(kind):
    """The women's openings (solid black wider than GLOW_HOLE_PX) at SAMPLE_SIZE; none on the hands."""
    from scipy import ndimage
    S = SAMPLE_SIZE[kind]
    key = ('holes', kind, S)
    if key not in _cache:
        if kind == 'hands':
            H = np.zeros((S, S), bool)
        else:
            T = _tex(GLOW_TABLE[kind], S)
            hw = max(3, int(round(GLOW_HOLE_PX * S / 4096)))
            H = ndimage.binary_opening((_lum(T[..., :3]) < GLOW_BLACK) & _female_cov(kind), structure=np.ones((hw, hw), bool))
        _cache[key] = H
    return _cache[key]


def _glow_bands(kind):
    """The women's band mask at SAMPLE_SIZE: the gaps between its skin pieces, whole -- not skin (bluer than red, or
    near black or white); the cut-out of its veins alone traced as dashes (v18 in game 11-14) -- minus the openings
    and the decals."""
    from scipy import ndimage
    S = SAMPLE_SIZE[kind]
    T = _tex(GLOW_TABLE[kind], S)
    r, b = T[..., 0], T[..., 2]
    lum = _lum(T[..., :3])
    gap = (b >= r) | (lum < 0.15) | (lum > GLOW_WHITE)
    gap = ndimage.gaussian_filter(gap.astype(np.float32), 1.5) > 0.5
    keep = gap & ~ndimage.binary_dilation(_female_holes(kind), iterations=2)
    if kind == 'body':
        yy, xx = np.mgrid[0:S, 0:S]
        u, v = (xx + 0.5) / S, (yy + 0.5) / S
        for cu, cv, hu, hv in GLOW_DECALS:
            keep &= ~((np.abs(u - cu) < hu) & (np.abs(v - cv) < hv))
    return keep


BANDS = {'body': lambda: _glow_bands('body'), 'hands': lambda: _glow_bands('hands')}
HOLES = {'body': lambda: _female_holes('body')}


def _network(m, colour):
    """(raw, floored) its glowing network patch in this colouring, tiled (mirrored) over map m at its own scale."""
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
    return net, np.maximum(net, GLOW_NET_FLOOR * (0.5 * vein + 0.5 * hue))


def _glow(m, colour, kind):
    """RGBA: its bands (floored network) and openings (the network as it is: lit internals); the skin itself clear."""
    from scipy import ndimage
    band = (_retrace(m, kind, 'lines', LINES, width=GLOW_W) if GLOW_ON_LINES
            else _retrace(m, kind, 'glow', BANDS, width=GLOW_W))
    if kind == 'body':
        f = _female_map('body')
        step = np.linalg.norm(f.position[:, 1:] - f.position[:, :-1], axis=-1)[f.covered[:, 1:] & f.covered[:, :-1]]
        holes = _retrace(m, kind, "holes:fill", HOLES, width=max(4 * float(np.median(step)), GLOW_FILL_W))   # filled solid
        c = m.covered.astype(np.float32)
        holes = ndimage.gaussian_filter(holes * c, REDRAW_SIGMA) / np.maximum(ndimage.gaussian_filter(c, REDRAW_SIGMA), 1e-3)
        t = np.clip((holes - REDRAW_EDGE[0]) / (REDRAW_EDGE[1] - REDRAW_EDGE[0]), 0, 1)
        holes = t * t * (3 - 2 * t) * m.covered
    else:
        holes = np.zeros_like(band)
    raw, net = _network(m, colour)
    # each opening its own copy of the patch, centred on it: tiled over the map as one, one knee fell on its dark and
    # read solid black while the other was all wires (Fo4-mcp v22 11-14, women)
    y0, x0, Pn = _network_patch()
    T4 = _tex(BODY[colour], GLOW_HOLE_SIZE)
    k = GLOW_HOLE_SIZE / m.size
    lab, n = ndimage.label(holes > 0.02)
    for c, sl in enumerate(ndimage.find_objects(lab), 1):
        ys, xs = np.nonzero(lab[sl] == c)
        ys, xs = ys + sl[0].start, xs + sl[1].start
        sy = np.clip(((ys - ys.mean()) * k + Pn / 2).astype(np.int64), 0, Pn - 1)
        sx = np.clip(((xs - xs.mean()) * k + Pn / 2).astype(np.int64), 0, Pn - 1)
        raw[ys, xs] = T4[y0 + sy, x0 + sx, :3]
    out = np.zeros(m.covered.shape + (4,), np.float32)
    out[..., :3] = np.where((holes >= band)[..., None], raw, net)
    out[..., 3] = np.maximum(band, holes) * m.covered
    return out


def glow_body(m, rng, colour):
    return _glow(m, colour, 'body')


def glow_hands(m, rng, colour):
    return _glow(m, colour, 'hands')


FACE_BLANK_PX = 9   # at 1024: solid black wider than this on its face texture is no face (the part of the UV its own
                    # back-of-head mesh replaces), not a line -- drawn, it put black wedges on the neck and crown


# Kept blank only above the nose tip (minus 1): measured on both heads, the eye corners sit 2.4-3 units above it, every
# line end 1.8+ below (blanks lower down left holes of bare skin, Fo4-mcp v14 and v20 11-14)
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
        blank_f = _no_lines(f, _tex(FACE, S))
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
    T = _on(m, FACE, 'head')
    blank = _face_blank(m, T)
    T = _plates(_face_lines(m), m.covered, 55413 + 7)
    return T, m.covered & ~blank


def _solid_black(T):
    from scipy import ndimage
    return ndimage.binary_opening(_lum(T[..., :3]) < 0.05, structure=np.ones((FACE_BLANK_PX, FACE_BLANK_PX)))


FACE_BLANK_AREA = 4000   # at 1024: a solid black this big, or above the nose, is no line; a smaller one lower down is
                         # where its lines widen along the jaw and neck (left out, the lines broke there)


def _no_lines(m, T):
    """Its face texture T's solid black that is not a line (on the woman's head map m)."""
    from scipy import ndimage
    import synthskin
    blank = _solid_black(T)
    lab, n = ndimage.label(blank)
    if n:
        idx = np.arange(1, n + 1)
        area = ndimage.sum(np.ones_like(lab), lab, index=idx)
        mz = ndimage.mean(m.position[..., 2], lab, index=idx)
        nose = synthskin.face_landmarks(m)['nose'][2]
        keep = np.zeros(n + 1, bool)
        keep[1:] = (area >= FACE_BLANK_AREA * (m.size / 1024) ** 2) | (mz >= nose + FACE_BLANK_ABOVE_NOSE)
        blank = keep[lab]
    return blank


def _face_blank(m, T):
    """Where its face texture T (on head map m) is no face: its solid black above the nose (the crown, under the hair).
    Below the nose everything is drawn: a man's neck reaches lower than the woman's head the texture was made for, and
    its base fell on her solid black -- left bare, a skin-coloured band ringed his neck (Fo4-mcp v20 11-14; 83% of the
    texels lower than 11 units under the nose). Per texel: on the ace head one solid black ran from the crown down the
    back of the neck, and judged whole by its mean height it bared the neck too."""
    from scipy import ndimage
    import synthskin
    high = m.position[..., 2] >= synthskin.face_landmarks(m)['nose'][2] + FACE_BLANK_ABOVE_NOSE
    # grown 2 texels past its edge, but only up there: in the UV layout the neck's lowest rim sits beside the crown
    return ndimage.binary_dilation(_solid_black(T) & high, iterations=2) & high


def panels_face(m):
    """Face tint (blend Default): its synth face over the person's."""
    T, keep = _face(m)
    out = np.zeros(m.covered.shape + (4,), np.float32)
    out[..., :3] = T[..., :3]
    out[..., 3] = np.where(keep, PANELS_ALPHA, 0.0)
    return out


FACE_LINE_DEPTH = 1.0   # a face tint multiplies weaker than the body's overlay: at LINE_DEPTH its lines read brown
                        # against the body's black (Fo4-mcp v20 11-14)


def panel_lines_face(m):
    """Face tint (blend Multiply): its synth face's dark lines only."""
    T, keep = _face(m)
    dark = 1 - np.clip((_lum(T[..., :3]) - LINE_DARK) / (LINE_PLATE - LINE_DARK), 0, 1)
    f = np.where(keep, 1 - FACE_LINE_DEPTH * dark, 1.0)
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
