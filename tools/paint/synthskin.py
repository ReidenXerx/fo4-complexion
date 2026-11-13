"""Synthetic skin: a see-through overlay that gives a person a synth's skin (alasdairn, 2026-11-13; his v9 approved).

    It is made of his own art (tools/paint/art/contrib, CREDITS.md):
    - his texture pack (alasdairn_synthpack/*_d.dds): a weathered synthetic material he painted on the meshes we sent
      him, so a texel of his texture IS a texel of ours -- the material;
    - his synth skin atlas (alasdairn_synth_atlas.png): pieces of a whole synthetic body, seams and muscle definition
      drawn in -- projected onto our meshes piece by piece, each anchored on landmarks the two share (nipples, nape,
      crotch to knee, along the arm; nose and chin for the head), for its LINES and its MUSCLE SHADING.

    See-through, as he asked ("Make it transparent, we just want the material, and the linings"): only each layer's
    detail relative to its broad average multiplies the person's own skin (make_marks' multiply overlay, x2; the face
    tint's "Overlay" blend), so every skin tone keeps its colour and the game's light stays the game's.

    Selectable only (lore "breaks"): body and hands in LooksMenu's overlay list (make_marks rows SynthShell,
    SynthShellHands), the face as a face tint (make_faces.py). Ace Male Race wears the vanilla male body, and has its
    own head (face.py).

What he struck out stays out: no atlas shading over the women's breasts (his atlas's breasts sit lower than ours), and
none of the atlas's strokes or shading in the band under them (the ghost outline he marked on v8).
"""
import pathlib

import numpy as np

from body import REGIONS
from marks import landmarks

HERE = pathlib.Path(__file__).resolve().parent
ATLAS = HERE / 'art' / 'contrib' / 'alasdairn_synth_atlas.png'
PACK = HERE / 'art' / 'contrib' / 'alasdairn_synthpack'

# ---- his atlas (1536 x 1024): where each piece sits, by the anchors it shares with our meshes (atlas pixels)
MALE_FRONT = dict(cx=400, nip=(300, 305))      # the torso fronts: the midline and a nipple
FEMALE_FRONT = dict(cx=1180, nip=(1110, 288))
MALE_BACK = dict(cx=935, top=165)              # the backs: the spine and the nape
FEMALE_BACK = dict(cx=1375, top=175)
LEG_FRONT = dict(cx=180, top=575, knee=897)    # his (male) leg pieces, for both sexes: crotch to the knee's V
LEG_BACK = dict(cx=327, top=575, knee=897)
ARM = dict(cx=57.0, shoulder=95.0, length=520.0)   # his long arm piece, shoulder to wrist
HEAD_SIDE = dict(nose=(382, 95), chin=(370, 140))  # the head, seen from its right side

EDGE_PX = 6.0          # a piece's lines fade in over its outline's last pixels (atlas px)
DETAIL_SIGMA = 22.0    # atlas px: "broad" for the lines (his shading, not his surface)
DETAIL_GAIN = 1.25
LINE_ONLY_SIGMA = 2.5  # atlas px: his seams are thinner than this, his mottling broader
SHADE_FINE, SHADE_BROAD = 2.5, 45.0   # atlas px: muscle shading is between his grain and the light on a whole piece
SHADE_GAIN = 1.0
PACK_SIGMA = 0.03      # of the texture's width: "broad" for his pack's material
PACK_GAIN = 1.6        # his mottling is soft: a little stronger, or a skin hardly changes
BREAST_R, BREAST_FADE = 5.5, 2.0            # game units round a nipple: no atlas shading, then fading back in
UNDERBUST_TOP, UNDERBUST_DEPTH = 1.0, 16.0  # game units above / below the nipples: the band he struck out
UNDERBUST_GRAIN = 0.93                      # in that band, line values under this are his strokes (gone)
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


# ---------------------------------------------------------------- his atlas, mapped onto our meshes


def _atlas():
    if 'img' not in _cache:
        from PIL import Image
        from scipy import ndimage
        img = np.asarray(Image.open(ATLAS).convert('RGB'), dtype=np.float32) / 255.0
        lum = img @ np.array((0.3, 0.59, 0.11), np.float32)
        inside = ndimage.binary_erosion(lum > 0.10, iterations=2)
        _cache['lum'] = lum
        _cache['inside'] = ndimage.distance_transform_edt(inside).astype(np.float32)
    return _cache['lum'], _cache['inside']


def _norm_blur(lum, valid, s):
    from scipy import ndimage
    w = valid.astype(np.float32)
    return ndimage.gaussian_filter(lum * w, s) / np.maximum(ndimage.gaussian_filter(w, s), 1e-3)


def _layers():
    """His atlas's two layers, each 1 where it does nothing: LINES (the seams and his finest strokes, darker only)
    and SHADE (the muscle definition)."""
    if 'lines' not in _cache:
        from scipy import ndimage
        lum, inside = _atlas()
        valid = inside > 0
        det = np.where(valid, lum / np.maximum(_norm_blur(lum, valid, DETAIL_SIGMA), 1e-3), 1.0)
        hp = det / np.maximum(ndimage.gaussian_filter(det, LINE_ONLY_SIGMA), 1e-3)
        _cache['lines'] = np.where(valid, np.minimum(hp, 1.0), 1.0).astype(np.float32)
        sh = _norm_blur(lum, valid, SHADE_FINE) / np.maximum(_norm_blur(lum, valid, SHADE_BROAD), 1e-3)
        _cache['shade'] = np.where(valid, sh, 1.0).astype(np.float32)
    return _cache['lines'], _cache['shade']


def _sample(layer, U, V, edge_px):
    """A layer at atlas (U, V) per point, bilinear; 1 off the atlas (NaN U) and fading to 1 at a piece's outline."""
    _, inside = _atlas()
    f = np.ones(len(U), np.float32)
    ok = np.isfinite(U)
    if ok.any():
        h, w = layer.shape
        u = np.clip(U[ok], 0, w - 1.001)
        v = np.clip(V[ok], 0, h - 1.001)
        x0, y0 = np.floor(u).astype(int), np.floor(v).astype(int)
        fx, fy = u - x0, v - y0
        a = (layer[y0, x0] * (1 - fx) * (1 - fy) + layer[y0, x0 + 1] * fx * (1 - fy) +
             layer[y0 + 1, x0] * (1 - fx) * fy + layer[y0 + 1, x0 + 1] * fx * fy)
        wt = np.clip(inside[np.rint(v).astype(int), np.rint(u).astype(int)] / edge_px, 0, 1)
        f[ok] = 1 + (a - 1) * wt
    return f


def lines_at(U, V):
    return np.clip(1 + (_sample(_layers()[0], U, V, EDGE_PX) - 1) * DETAIL_GAIN, 0.3, 1.0)


def shade_at(U, V):
    return np.clip(1 + (_sample(_layers()[1], U, V, EDGE_PX * 3) - 1) * SHADE_GAIN, 0.5, 1.4)


def atlas_uv(m):
    """Per covered texel of a body (body.UVMap): (idx, positions, U, V), the atlas pixel it takes; NaN where no
    piece is meant to reach (hands, feet, the gaps between pieces)."""
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
            k = sub[half]
            U[k] = piece['cx'] + sign * out[half] * sv
            V[k] = piece['top'] + (zcr - z[k]) * sv
    # the arms: his long arm piece, shoulder to wrist, unrolled round the arm from its underside
    arm = R == REGIONS.index('arm')
    for side in (1, -1):
        am = arm & (x * side > 0)
        limb = _Limb(X[am], np.array((side, 0.0, -0.5)), np.array((0.0, 0.0, -1.0)))
        t, ra, tha = limb.coords(X[am])
        sa = ARM['length'] / (limb.tmax - limb.tmin)
        U[np.flatnonzero(am)] = ARM['cx'] + side * ra * (np.abs(tha) - np.pi / 2) * sa
        V[np.flatnonzero(am)] = ARM['shoulder'] + (t - limb.tmin) * sa
    return idx, X, U, V


def head_uv(m):
    """Per covered texel of a head (face.HeadMap): (idx, U, V) on his head piece seen from the side, the face's
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
    return idx, U, V


# ---------------------------------------------------------------- his pack


def _pack_png(name):
    """His DDS decoded once (texconv) into build/alasdairn_synthpack/<name>.png; RGBA float."""
    import subprocess
    from PIL import Image
    import make_marks as mm
    cache = mm.ROOT / 'build' / 'alasdairn_synthpack'
    png = cache / f'{name}.png'
    if not png.exists():
        cache.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([str(mm.texconv()), '-nologo', '-y', '-ft', 'png', '-f', 'R8G8B8A8_UNORM', '-m', '1',
                            '-o', str(cache), str(PACK / f'{name}.dds')], capture_output=True, text=True)
        made = next((p for p in cache.iterdir() if p.stem.lower() == name.lower()), None)
        if r.returncode or not made:
            raise SystemExit(f'texconv could not decode {name}: {r.stdout[-300:]}')
        if made.name != png.name:
            made.rename(png)
    return np.asarray(Image.open(png).convert('RGBA'), dtype=np.float32) / 255.0


def pack_factor(name, size):
    """Per texel of a size x size map (his UVs = ours): the factor his material multiplies the skin by, grey (his
    grey-green tinted the body yellower than the face, and showed the skin's own colour as a band where the overlay
    fades at the neck)."""
    from PIL import Image
    a = _pack_png(name)
    rgba = np.asarray(Image.fromarray((a * 255).astype(np.uint8), 'RGBA').resize((size, size), Image.BICUBIC),
                      np.float32) / 255.0
    valid = rgba[..., 3] > 0.5
    lum = rgba[..., :3] @ np.array((0.3, 0.59, 0.11), np.float32)
    detail = np.where(valid, lum / np.maximum(_norm_blur(lum, valid, PACK_SIGMA * size), 1e-3), 1.0)
    return np.clip(1 + (detail - 1) * PACK_GAIN, 0.35, 1.8)


def _underbust_keep(m, X):
    """1 everywhere but the band under a woman's breasts he struck out (0 there, soft-edged)."""
    zn = float(np.mean([p[2] for p in landmarks(m)['nipples'].values()]))
    z = X[:, 2]
    inside = np.minimum(np.minimum((zn + UNDERBUST_TOP) - z, z - (zn - UNDERBUST_DEPTH)), np.abs(X[:, 0]))
    return np.where(X[:, 1] > 0, np.clip(1 - inside / UNDERBUST_FADE, 0, 1), 1.0)


def _multiply(m, f):
    """(rgb, alpha) for make_marks' multiply path: the colour that, over its SKIN, multiplies by f."""
    from preview import SKIN
    return np.clip(SKIN[None, None, :] * f[..., None], 0, 1), m.covered.astype(np.float64)


# ---------------------------------------------------------------- the painters


def pack_body(m, rng=None):
    f = pack_factor('FemaleBody_d' if m.sex == 'female' else 'MaleBody_d', m.size)
    idx, X, U, V = atlas_uv(m)
    ln, sh = lines_at(U, V), shade_at(U, V)
    if m.sex == 'female':
        keep = _underbust_keep(m, X)
        strokes = np.clip((UNDERBUST_GRAIN - ln) / 0.05, 0, 1)       # in his band the strokes go, the grain stays
        ln = 1 + (ln - 1) * (1 - strokes * (1 - keep))
        nip = np.array(list(landmarks(m)['nipples'].values()))
        d = np.min(np.linalg.norm(X[:, None, :] - nip[None, :, :], axis=2), axis=1)
        sh = 1 + (sh - 1) * keep * np.clip((d - BREAST_R) / BREAST_FADE, 0, 1)
    f.reshape(-1)[idx] *= ln * sh
    return _multiply(m, f)


def pack_hands(m, rng=None):
    return _multiply(m, pack_factor('FemaleHands_d' if m.sex == 'female' else 'MaleHands_d', m.size))


def pack_face(m):
    """The face tint, blend "Overlay" (0.5 leaves the face as it is): RGBA, 0.5 x the factor."""
    name = {'human_male': 'MaleHead_d', 'human_female': 'FemaleHead_d', 'ace_male': 'AceMaleHead_d'}[m.head]
    f = pack_factor(name, m.size)
    idx, U, V = head_uv(m)
    f.reshape(-1)[idx] *= lines_at(U, V) * shade_at(U, V)
    out = np.zeros(m.covered.shape + (4,))
    out[..., :3] = np.clip(0.5 * f, 0, 1)[..., None]
    out[..., 3] = m.covered
    return out
