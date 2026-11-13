"""Synthetic skin: a synth's seam lines over a person's own skin (alasdairn, 2026-11-13).

    The lines are his: the seams he drew on his own synth skin atlas (tools/paint/art/contrib/alasdairn_synth_atlas.png,
    CREDITS.md) -- pieces of a whole synthetic body -- projected onto our meshes piece by piece, each anchored on
    landmarks the two share (nipples, nape, crotch to knee, along the arm; nose and chin for the head). The hands get a
    synth's joint lines from their own finger bones (his hand pieces are drawn palm up and carry no clean seams).

    Lines only, crisp and dark (his verdict on test v2, in game: "Lost definition in the lines, hands have nothing
    notable, applies a layer of shading over everything else. Remove the shading, darken and sharpen the lines"). His
    atlas is about 11 pixels to a game unit; sampled straight, its strokes blurred over a 4096 body. So each of his
    strokes is reduced to its centreline, and every texel draws a hard-edged line by its distance to it, in game units.
    Everything else multiplies by exactly 1: the person's own skin, its colour and its light, are untouched.

    Selectable only (lore "breaks"): body and hands in LooksMenu's overlay list (make_marks rows SynthShell,
    SynthShellHands), the face as a face tint (make_faces.py). Ace Male Race wears the vanilla male body, and has its
    own head (face.py).

What he struck out stays out: no line in the band under the women's breasts (his atlas's breasts sit lower than ours,
and drew a ghost outline there), no specks, scratches or stubs (the "random scar" on a thigh), and nothing read from
above the leg pieces at the hips (a straight dash).
"""
import pathlib

import numpy as np

from body import REGIONS
from marks import landmarks

HERE = pathlib.Path(__file__).resolve().parent
ATLAS = HERE / 'art' / 'contrib' / 'alasdairn_synth_atlas.png'

# ---- his atlas (1536 x 1024): where each piece sits, by the anchors it shares with our meshes (atlas pixels)
MALE_FRONT = dict(cx=400, nip=(300, 305))      # the torso fronts: the midline and a nipple
FEMALE_FRONT = dict(cx=1180, nip=(1110, 288))
MALE_BACK = dict(cx=935, top=165)              # the backs: the spine and the nape
FEMALE_BACK = dict(cx=1375, top=175)
LEG_FRONT = dict(cx=180, top=575, knee=897)    # his (male) leg pieces, for both sexes: crotch to the knee's V
LEG_BACK = dict(cx=327, top=575, knee=897)
ARM = dict(cx=57.0, shoulder=95.0, length=520.0)   # his long arm piece, shoulder to wrist
HEAD_SIDE = dict(nose=(382, 95), chin=(370, 140))  # the head, seen from its right side

# ---- which of his atlas's dark marks are seams
DETAIL_SIGMA = 22.0    # atlas px: the broad average a mark is measured against
LINE_ONLY_SIGMA = 2.5  # atlas px: his seams are thinner than this, his mottling broader
LINE_FLOOR = 0.035     # a mark darker than its surroundings by this much is a stroke
LINE_MIN_PX = 30       # atlas px: a stroke shorter than this is a speck, a scratch or a stub, not a seam
EDGE_PX = 10.0         # atlas px: no line within this of a piece's outline (his outlines cut strokes short)

# ---- how a seam is drawn (game units)
LINE_W = 0.06          # half-width: about 2.5 mm across (0.035 broke into dots at 2048)
LINE_SOFT = 0.025      # its edge: about a texel at 2048, so crisp but not jagged
LINE_DEPTH = 0.8       # the skin multiplied by 1 - this on the line
FACE_LINE_W = 0.06     # on the face tint (1024 over a head)
HAND_LINE_W = 0.045
SPUR_PX = 8            # atlas px: twigs this short off a centreline (thinning's leftovers, 4 left ticks) are pruned

UNDERBUST_TOP, UNDERBUST_DEPTH = 1.0, 16.0  # game units above / below the nipples: the band he struck out
UNDERBUST_FADE = 2.5

_cache = {}


# ---------------------------------------------------------------- limbs and heads


class _Limb:
    """A limb as an axis, a centreline along it and an angle round it, from points on its surface (texels: the male
    body has few vertices, and a centreline from them leans towards wherever the mesh is dense)."""

    def __init__(self, P, axis_hint, ref):
        P = P[::max(1, len(P) // 40000)]
        c = P.mean(0)
        a = np.linalg.svd(P - c, full_matrices=False)[2][0]
        if a @ axis_hint < 0:
            a = -a
        self.c, self.a = c, a
        t = (P - c) @ a
        self.tmin, self.tmax = float(t.min()), float(t.max())
        edges = np.arange(self.tmin, self.tmax + 1.0, 1.0)
        which = np.digitize(t, edges) - 1
        cen_t, cen = [], []
        for k in range(len(edges) - 1):
            sel = which == k
            if sel.sum() >= 3:
                cen_t.append((edges[k] + edges[k + 1]) / 2)
                cen.append(P[sel].mean(axis=0))
        self.cen_t, self.cen = np.array(cen_t), np.array(cen)
        e1 = ref - (ref @ a) * a
        self.e1 = e1 / np.linalg.norm(e1)
        self.e2 = np.cross(a, self.e1)

    def coords(self, X):
        """t along the axis, r and theta round the centreline (theta 0 towards ref)."""
        t = (X - self.c) @ self.a
        C = np.stack([np.interp(t, self.cen_t, self.cen[:, k]) for k in range(3)], axis=1)
        d = X - C
        d -= np.outer(d @ self.a, self.a)
        return t, np.linalg.norm(d, axis=1), np.arctan2(d @ self.e2, d @ self.e1)


def face_landmarks(m):
    """Measured on a head mesh (face.HeadMap; local units, face towards +y, z up): the nose tip and the chin."""
    V = m.vertices
    nose = V[np.argmax(V[:, 1])]
    front = V[(np.abs(V[:, 0]) < 0.4) & (V[:, 1] > nose[1] - 3.5)]
    return {'nose': nose, 'chin': front[np.argmin(front[:, 2])]}


# ---------------------------------------------------------------- his seams, as centrelines


def _thin(mask):
    """Zhang-Suen thinning: a stroke mask to its one-pixel centreline."""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            P = [img[1:-1, 1:-1], img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:], img[2:, 2:], img[2:, 1:-1],
                 img[2:, :-2], img[1:-1, :-2], img[:-2, :-2]]
            p1, p2, p3, p4, p5, p6, p7, p8, p9 = P
            nb = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            trans = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(np.uint8) for k in range(8))
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            rm = (p1 == 1) & (nb >= 2) & (nb <= 6) & (trans == 1) & c
            if rm.any():
                img[1:-1, 1:-1][rm] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)


def _prune(skel, n):
    """Spurs off a centreline: its end pixels peeled n times, then the long lines grown back along themselves, so
    only twigs no longer than n go."""
    from scipy import ndimage
    k = np.ones((3, 3))
    s = skel.copy()
    ends_all = []
    for _ in range(n):
        nb = ndimage.convolve(s.astype(np.uint8), k, mode='constant') - s
        ends = s & (nb <= 1)
        ends_all.append(ends)
        s = s & ~ends
    for ends in reversed(ends_all):       # grow back only from what survived (main lines), not into lost twigs
        grown = ndimage.binary_dilation(s, structure=k) & ends
        s = s | grown
    return s


def _atlas():
    """(distance in atlas px from each pixel to the nearest seam centreline, distance inside a piece's outline)."""
    if 'dist' not in _cache:
        from PIL import Image
        from scipy import ndimage
        img = np.asarray(Image.open(ATLAS).convert('RGB'), dtype=np.float32) / 255.0
        lum = img @ np.array((0.3, 0.59, 0.11), np.float32)
        inside = ndimage.distance_transform_edt(ndimage.binary_erosion(lum > 0.10, iterations=2)).astype(np.float32)
        valid = inside > 0
        w = valid.astype(np.float32)
        avg = ndimage.gaussian_filter(lum * w, DETAIL_SIGMA) / np.maximum(ndimage.gaussian_filter(w, DETAIL_SIGMA), 1e-3)
        det = np.where(valid, lum / np.maximum(avg, 1e-3), 1.0)
        hp = np.where(valid, det / np.maximum(ndimage.gaussian_filter(det, LINE_ONLY_SIGMA), 1e-3), 1.0)
        dark = ((1 - hp) > LINE_FLOOR) & (inside > EDGE_PX)
        lab, n = ndimage.label(dark, structure=np.ones((3, 3)))
        keep = np.zeros(n + 1, bool)
        for i, sl in enumerate(ndimage.find_objects(lab), 1):
            if max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) >= LINE_MIN_PX:
                keep[i] = True
        skel = _prune(_thin(keep[lab]), SPUR_PX)
        _cache['dist'] = ndimage.distance_transform_edt(~skel).astype(np.float32)   # (a blurred field lifted the
        # centreline off 0 by most of a line's width: v3's first draft lost its lines)
        _cache['inside'] = inside
    return _cache['dist'], _cache['inside']


def _seam_distance(U, V):
    """Per point: distance (atlas px) to his nearest seam centreline; inf off the atlas (NaN U)."""
    dist, inside = _atlas()
    d = np.full(len(U), np.inf)
    ok = np.isfinite(U)
    if ok.any():
        h, w = dist.shape
        u = np.clip(U[ok], 0, w - 1.001)
        v = np.clip(V[ok], 0, h - 1.001)
        x0, y0 = np.floor(u).astype(int), np.floor(v).astype(int)
        fx, fy = u - x0, v - y0
        a = (dist[y0, x0] * (1 - fx) * (1 - fy) + dist[y0, x0 + 1] * fx * (1 - fy) +
             dist[y0 + 1, x0] * (1 - fx) * fy + dist[y0 + 1, x0 + 1] * fx * fy)
        a[inside[np.rint(v).astype(int), np.rint(u).astype(int)] <= 0] = np.inf   # outside his pieces
        d[ok] = a
    return d


def _line(d_units, half_width):
    """1 - depth on a line of that half-width (game units), 1 off it; crisp edge."""
    t = np.clip((half_width - d_units) / LINE_SOFT + 0.5, 0, 1)
    return 1 - LINE_DEPTH * t * t * (3 - 2 * t)


# ---------------------------------------------------------------- his atlas, mapped onto our meshes


def atlas_uv(m):
    """Per covered texel of a body (body.UVMap): (idx, positions, U, V, S) -- the atlas pixel it takes and the atlas
    pixels per game unit there; NaN U where no piece is meant to reach (hands, feet, the gaps between pieces)."""
    L = landmarks(m)
    lo, hi = m.bounds

    def Z(h):
        return lo[2] + h * (hi[2] - lo[2])
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx]
    R = m.region.reshape(-1)[idx]
    x, y, z = X[:, 0], X[:, 1], X[:, 2]
    U = np.full(len(idx), np.nan)
    V = np.full(len(idx), np.nan)
    S = np.ones(len(idx))
    # the torso, unrolled round its middle: front and back parted by the plane through its depth's middle per height
    torso = R == REGIONS.index('torso')
    mid = torso & (np.abs(x) < 1.5)
    zc, ym = [], []
    for z0 in np.arange(z[torso].min(), z[torso].max(), 1.0):
        sel = mid & (z >= z0) & (z < z0 + 1.0)
        if (sel & (y > 0)).any() and (sel & (y < 0)).any():
            zc.append(z0 + 0.5)
            ym.append((y[sel].max() + y[sel].min()) / 2)
    ymid = np.interp(z, zc, np.convolve(np.pad(ym, 2, mode='edge'), np.ones(5) / 5, mode='valid'))
    r = np.hypot(x, y - ymid)
    female = m.sex == 'female'
    F = FEMALE_FRONT if female else MALE_FRONT
    B = FEMALE_BACK if female else MALE_BACK
    s = (F['cx'] - F['nip'][0]) / abs(L['nipples'][1][0])        # atlas px per game unit: his nipples on ours
    front = torso & (y > ymid)
    U[front] = (F['cx'] - np.arctan2(x, y - ymid) * r * s)[front]   # drawn facing us: his left is the body's right
    V[front] = (F['nip'][1] + (Z(L['nipple']) - z) * s)[front]
    back = torso & (y <= ymid)
    U[back] = (B['cx'] + np.arctan2(x, ymid - y) * r * s)[back]     # from behind: his left is the body's left
    V[back] = (B['top'] + (Z(L['top']) - z) * s)[back]
    S[torso] = s
    # the legs: front and back halves round each leg's own centre, crotch to knee as his pieces
    zcr, zk = Z(L['crotch']), Z(0.285)
    leg = R == REGIONS.index('leg')
    for side in (1, -1):
        lm = leg & (x * side > 0)
        limb = _Limb(X[lm & (z < zcr - 1.0)], np.array((0.0, 0.0, -1.0)), np.array((side, 0.0, 0.0)))
        _t, rl, th = limb.coords(X[lm])          # theta 0 = out to the side; the front is -side * pi/2
        out = rl * np.cos(th)
        frontish = np.cos(th - side * np.pi / 2) < 0
        sub = np.flatnonzero(lm)
        for piece, half, sign in ((LEG_FRONT, frontish, -1), (LEG_BACK, ~frontish, 1)):
            sv = (piece['knee'] - piece['top']) / (zcr - zk)
            # the outer hip is the leg's (by bone) but above the crotch: it would read the atlas above the leg
            # piece's top -- the torso piece's bottom seam, a straight dash at each hip -- so it takes none
            sel = half & (z[sub] < zcr)
            k = sub[sel]
            U[k] = piece['cx'] + sign * out[sel] * sv
            V[k] = piece['top'] + (zcr - z[k]) * sv
            S[k] = sv
    # the arms: his long arm piece, shoulder to wrist, unrolled round the arm from its underside
    arm = R == REGIONS.index('arm')
    for side in (1, -1):
        am = arm & (x * side > 0)
        limb = _Limb(X[am], np.array((side, 0.0, -0.5)), np.array((0.0, 0.0, -1.0)))
        t, ra, tha = limb.coords(X[am])
        sa = ARM['length'] / (limb.tmax - limb.tmin)
        k = np.flatnonzero(am)
        U[k] = ARM['cx'] + side * ra * (np.abs(tha) - np.pi / 2) * sa
        V[k] = ARM['shoulder'] + (t - limb.tmin) * sa
        S[k] = sa
    return idx, X, U, V, S


def head_uv(m):
    """Per covered texel of a head (face.HeadMap): (idx, U, V, s) on his head piece seen from the side, the face's
    front left out (no piece sees it squarely)."""
    L = face_landmarks(m)
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx]
    N = m.normal.reshape(-1, 3)[idx]
    yn, zn, zc = L['nose'][1], L['nose'][2], L['chin'][2]
    H = HEAD_SIDE
    s = (H['chin'][1] - H['nose'][1]) / (zn - zc)
    U = H['nose'][0] - (yn - X[:, 1]) * s
    V = H['nose'][1] + (zn - X[:, 2]) * s
    U[np.abs(N[:, 0]) < 0.45] = np.nan
    return idx, U, V, s


def _underbust_keep(m, X):
    """1 everywhere but the band under a woman's breasts he struck out (0 there, soft-edged)."""
    zn = float(np.mean([p[2] for p in landmarks(m)['nipples'].values()]))
    z = X[:, 2]
    inside = np.minimum((zn + UNDERBUST_TOP) - z, z - (zn - UNDERBUST_DEPTH))   # right across: a midline left in it
                                                                               # kept a mark at the sternum
    return np.where(X[:, 1] > 0, np.clip(1 - inside / UNDERBUST_FADE, 0, 1), 1.0)


def _multiply(m, f):
    """(rgb, alpha) for make_marks' multiply path: the colour that, over its SKIN, multiplies by f."""
    from preview import SKIN
    return np.clip(SKIN[None, None, :] * f[..., None], 0, 1), m.covered.astype(np.float64)


# ---------------------------------------------------------------- the hands' joint lines

HAND_RING_REACH = 1.1      # game units off a finger's axis a ring reaches (the finger, not its neighbours)
WRIST_RING = 0.9           # game units up the hand from the wrist's open edge


def hand_distance(m):
    """Per covered texel of a hands map (hands.HandMap): distance (game units) to its nearest joint line -- a ring
    where each finger bone begins (the knuckles included) and one round the wrist."""
    import collections
    import hands
    from scipy.spatial import cKDTree
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx]
    d = np.full(len(idx), np.inf)
    for side in ('L', 'R'):
        for f in range(1, 6):
            if f'{side}Arm_Finger{f}3' not in m.bone_names:
                continue
            axis = hands.finger_frame(m, side, f)[0]
            bones = [hands._bone_vertices(m, f'{side}Arm_Finger{f}{k}') for k in (1, 2, 3)]
            c = np.concatenate(bones).mean(axis=0)
            rel = X - c
            near = np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1) < HAND_RING_REACH
            for B in bones:
                t0 = (B @ axis).min() + 0.08
                d[near] = np.minimum(d[near], np.abs(X[near] @ axis - t0))
    V, T = m.vertices, m.triangles
    uniq, inv = np.unique(np.round(V, 3), axis=0, return_inverse=True)
    inv = inv.ravel()
    count = collections.Counter()
    for t in T:
        a, b, cc = inv[t]
        for e in ((a, b), (b, cc), (cc, a)):
            count[(min(e), max(e))] += 1
    ends = np.array([e for e, k in count.items() if k == 1]).reshape(-1, 2)
    if len(ends):
        A, Bv = uniq[ends[:, 0]], uniq[ends[:, 1]]
        P = (A[:, None, :] + np.linspace(0, 1, 8)[None, :, None] * (Bv - A)[:, None, :]).reshape(-1, 3)
        d = np.minimum(d, np.abs(cKDTree(P).query(X)[0] - WRIST_RING))
    return idx, d


# ---------------------------------------------------------------- the painters


def pack_body(m, rng=None):
    idx, X, U, V, S = atlas_uv(m)
    f = _line(_seam_distance(U, V) / S, LINE_W)
    if m.sex == 'female':
        f = 1 - (1 - f) * _underbust_keep(m, X)
    out = np.ones(m.covered.shape)
    out.reshape(-1)[idx] = f
    return _multiply(m, out)


def pack_hands(m, rng=None):
    idx, d = hand_distance(m)
    out = np.ones(m.covered.shape)
    out.reshape(-1)[idx] = _line(d, HAND_LINE_W)
    return _multiply(m, out)


# ---------------------------------------------------------------- variant B: plated (his material, opaque-ish)
#
# alasdairn after test v2: "I can also add the material back, have it darken the lines and boom we're back in
# business ... do this as a secondary option actually". So a second, separately selectable look: his atlas's own pale
# synthetic surface, projected as above (a clean patch of his skin wherever no piece reaches), mostly opaque -- a lit
# overlay (.bgsm, make_marks' LIT_PAINTERS), the same on every skin tone -- with his seams over it as wider, darker
# panel gaps (the testers' Gen 1 synth / SyntheticZombies mood). The face: a face tint laid on with blend "Default".

PATCH = (845, 220, 915, 300)    # a clean patch of his skin (the male back's left shoulder blade, clear of seams)
PATCH_TILE = 9.0                # game units the patch covers before it mirrors
PLATED_ALPHA = 0.92             # mostly his surface; a little of the person's own skin under it
PLATED_LINE_W = 0.11            # half-width: a panel gap, not a hairline
PLATED_LINE_DEPTH = 0.86
PLATED_FACE_LINE_W = 0.09
PLATED_HAND_LINE_W = 0.07
PLATED_SPEC = (0.45, 0.6)       # specular, smoothness: a soft synthetic sheen


def _colour():
    if 'rgb' not in _cache:
        from PIL import Image
        _cache['rgb'] = np.asarray(Image.open(ATLAS).convert('RGB'), dtype=np.float32) / 255.0
        x0, y0, x1, y1 = PATCH
        _cache['patch'] = _cache['rgb'][y0:y1, x0:x1]
    return _cache['rgb'], _cache['patch']


def _triplanar(tile, X, N, size):
    """tile laid over points X with normals N, mirrored every `size` game units along each plane, blended by how
    squarely the surface faces it (normal^4); z up, so each plane's image stands upright."""
    h, w = tile.shape[:2]

    def sample(u, v):
        fu, fv = np.mod(u / size, 2.0), np.mod(v / size, 2.0)
        fu = np.where(fu > 1, 2 - fu, fu)
        fv = np.where(fv > 1, 2 - fv, fv)
        return tile[np.clip((fv * (h - 1)).astype(int), 0, h - 1), np.clip((fu * (w - 1)).astype(int), 0, w - 1)]
    wts = np.abs(N) ** 4
    wts = (wts / np.maximum(wts.sum(axis=1, keepdims=True), 1e-9))[:, :, None]
    return (wts[:, 0] * sample(X[:, 1], -X[:, 2]) + wts[:, 1] * sample(X[:, 0], -X[:, 2]) +
            wts[:, 2] * sample(X[:, 0], X[:, 1]))


def _surface(X, N, U, V):
    """His surface per point: the atlas's colour where a piece maps (bilinear), his clean patch elsewhere, the two
    cross-faded over a piece's outline."""
    rgb, patch = _colour()
    _, inside = _atlas()
    col = _triplanar(patch, X, N, PATCH_TILE)
    ok = np.isfinite(U)
    if ok.any():
        h, w = inside.shape
        u = np.clip(U[ok], 0, w - 1.001)
        v = np.clip(V[ok], 0, h - 1.001)
        x0, y0 = np.floor(u).astype(int), np.floor(v).astype(int)
        fx, fy = (u - x0)[:, None], (v - y0)[:, None]
        c = (rgb[y0, x0] * (1 - fx) * (1 - fy) + rgb[y0, x0 + 1] * fx * (1 - fy) +
             rgb[y0 + 1, x0] * (1 - fx) * fy + rgb[y0 + 1, x0 + 1] * fx * fy)
        wt = np.clip(inside[np.rint(v).astype(int), np.rint(u).astype(int)] / EDGE_PX, 0, 1)[:, None]
        col[ok] = c * wt + col[ok] * (1 - wt)
    return col


def _plated_line(d_units, half_width):
    t = np.clip((half_width - d_units) / LINE_SOFT + 0.5, 0, 1)
    return 1 - PLATED_LINE_DEPTH * t * t * (3 - 2 * t)


def _lit(m, idx, col):
    diffuse = np.zeros(m.covered.shape + (4,))
    spec = np.zeros(m.covered.shape + (2,))
    diffuse.reshape(-1, 4)[idx, :3] = np.clip(col, 0, 1)
    diffuse.reshape(-1, 4)[idx, 3] = PLATED_ALPHA
    spec.reshape(-1, 2)[idx] = PLATED_SPEC
    return diffuse, spec


def plated_body(m, rng=None):
    """(diffuse RGBA, spec RG) for make_marks' lit path."""
    idx, X, U, V, S = atlas_uv(m)
    N = m.normal.reshape(-1, 3)[idx]
    line = _plated_line(_seam_distance(U, V) / S, PLATED_LINE_W)
    if m.sex == 'female':
        line = 1 - (1 - line) * _underbust_keep(m, X)
    return _lit(m, idx, _surface(X, N, U, V) * line[:, None])


def plated_hands(m, rng=None):
    idx, d = hand_distance(m)
    X = m.position.reshape(-1, 3)[idx]
    N = m.normal.reshape(-1, 3)[idx]
    n = len(idx)
    col = _surface(X, N, np.full(n, np.nan), np.full(n, np.nan)) * _plated_line(d, PLATED_HAND_LINE_W)[:, None]
    return _lit(m, idx, col)


def plated_face(m):
    """The face tint, blend "Default" (laid over the face): RGBA, his surface with his head band's seams."""
    idx, U, V, s = head_uv(m)
    X = m.position.reshape(-1, 3)[idx]
    N = m.normal.reshape(-1, 3)[idx]
    col = _surface(X, N, U, V) * _plated_line(_seam_distance(U, V) / s, PLATED_FACE_LINE_W)[:, None]
    out = np.zeros(m.covered.shape + (4,))
    out.reshape(-1, 4)[idx, :3] = np.clip(col, 0, 1)
    out.reshape(-1, 4)[idx, 3] = PLATED_ALPHA
    return out


def pack_face(m):
    """The face tint, blend "Multiply" (white leaves the face as it is; lines only now, so a plain darkening -- the
    "Overlay" blend turned a dark line orange on light skin): RGBA."""
    idx, U, V, s = head_uv(m)
    f = np.ones(m.covered.shape)
    f.reshape(-1)[idx] = _line(_seam_distance(U, V) / s, FACE_LINE_W)
    out = np.zeros(m.covered.shape + (4,))
    out[..., :3] = np.clip(f, 0, 1)[..., None]
    out[..., 3] = m.covered
    return out
