"""Synthetic skin: a selectable body overlay that makes the body read as a synth's plated shell (alasdairn, 11-13).

    Asked for: "A synthetic skin Looks Menu overlay for Male, Female, and Ace Male, using our bodies". Ace Male Race
    has no body mesh of its own (AceMaleRace.esp names none, its BA2s carry a head and materials pointing at the
    vanilla male body textures), so the male texture fits it as is: two textures, female and male.

What it paints, in 3D on the body (marks.py's rule: never on UV coordinates, so every line runs on across UV seams):
- panel seams: thin dark grooves with a raised light lip on both sides, laid where a shell would part -- the
  sternum and spine, the flanks, under the chest, a waist band, a V over the hips, the collarbones, rings round
  the shoulders, elbows, forearms, thighs, knees and calves, and a lengthwise seam inside each arm and down each
  leg's inner and outer side;
- the shell: a cool, faintly grey tint, a little lighter than skin, with a short shadow band along each seam (the
  material runs at scale x2, so lighter is possible as well as darker);
- service details: two ports under the collarbones, a jointed strip down the spine ending on an access panel at
  the small of the back, vents on each forearm and an oval cap over each knee.

It is only ever put on by hand, in LooksMenu's own overlay list: tagged lore "breaks", which the composers
(compose.py, Compose.cpp), Complexion's window and make_data.py's signature looks all leave out (alasdairn,
11-13: "Only selectable").
"""
import numpy as np

from body import REGIONS
from marks import Painter, landmarks
from preview import SKIN   # the skin make_marks.multiplier divides by

GROOVE_W = 0.085    # game units: the groove's half-width (gaussian), about 1.2 mm
LIP_AT = 0.23       # the lip's distance from the groove's centre
LIP_W = 0.075
GROOVE_DEPTH = 0.62  # the skin is multiplied by 1 - depth at the groove's centre
LIP_GAIN = 0.20      # ... and by 1 + gain on the lip
PILLOW = (0.93, 1.04)  # brightness at a structural seam, and on the shell away from one
PILLOW_REACH = 1.0     # game units: the shadow band's reach either side of a seam
TINT = np.array((0.95, 0.985, 1.04))   # cool, faintly grey


def _bins(values, keys, lo, hi, step=1.0):
    """Mean of values per bin of keys (lo..hi), interpolable: (bin centres, means), empty bins dropped."""
    edges = np.arange(lo, hi + step, step)
    which = np.digitize(keys, edges) - 1
    cen, out = [], []
    for k in range(len(edges) - 1):
        sel = which == k
        if sel.sum() >= 3:
            cen.append((edges[k] + edges[k + 1]) / 2)
            out.append(values[sel].mean(axis=0))
    return np.array(cen), np.array(out)


class _Limb:
    """A limb (one arm or leg) as an axis, a centreline along it and an angle round it: t along the axis (from the
    body outward), r and theta round the centreline, theta 0 facing ref."""

    def __init__(self, P, axis_hint, ref):
        """P: points on the limb's surface -- texels, not vertices: the male body has few vertices, and a
        centreline from them leans towards wherever the mesh is dense (seams strayed onto the backs of the thighs)."""
        P = P[::max(1, len(P) // 40000)]
        c = P.mean(0)
        a = np.linalg.svd(P - c, full_matrices=False)[2][0]
        if a @ axis_hint < 0:
            a = -a
        self.c, self.a = c, a
        t = (P - c) @ a
        self.tmin, self.tmax = float(t.min()), float(t.max())
        self.cen_t, self.cen = _bins(P, t, self.tmin, self.tmax)
        e1 = ref - (ref @ a) * a
        self.e1 = e1 / np.linalg.norm(e1)
        self.e2 = np.cross(a, self.e1)

    def frac(self, f):
        return self.tmin + f * (self.tmax - self.tmin)

    def coords(self, X):
        t = (X - self.c) @ self.a
        C = np.stack([np.interp(t, self.cen_t, self.cen[:, k]) for k in range(3)], axis=1)
        d = X - C
        d -= np.outer(d @ self.a, self.a)
        r = np.linalg.norm(d, axis=1)
        th = np.arctan2(d @ self.e2, d @ self.e1)
        return t, r, th


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def synth_skin(m, rng):
    P = Painter(m)
    L = landmarks(m)
    lo, hi = m.bounds

    def Z(h):
        return lo[2] + h * (hi[2] - lo[2])

    idx = np.flatnonzero(P.cov)
    X = m.position.reshape(-1, 3)[idx]
    R = m.region.reshape(-1)[idx]
    x, y, z = X[:, 0], X[:, 1], X[:, 2]
    n = len(idx)
    dmin = np.full(n, np.inf)
    groove = np.zeros(n)
    lip = np.zeros(n)
    fill = np.zeros(n)      # port and vent interiors: darker than a groove's shoulders

    def seam(mask, s, width=1.0, detail=False):
        """A seam where s (signed game units) crosses 0, on the texels in mask. A detail (a port, a vent, a lid)
        casts no shadow band: its mask is a box, and a band cut off at the box's edge showed as a pale square."""
        sel = np.flatnonzero(mask)
        if not len(sel):
            return
        a = np.abs(s[sel] if np.ndim(s) and len(s) == n else s)
        if not detail:
            dmin[sel] = np.minimum(dmin[sel], a)
        groove[sel] = np.maximum(groove[sel], np.exp(-(a / (GROOVE_W * width)) ** 2))
        lip[sel] = np.maximum(lip[sel], np.exp(-((a - LIP_AT * width) / LIP_W) ** 2))

    def between(v, a, b):
        return (v >= min(a, b)) & (v <= max(a, b))

    reg = {name: R == REGIONS.index(name) for name in REGIONS}
    # ---- torso: the plane y = ymid(z) parts front from back (it meets the surface only at the flanks). ymid is
    # the middle of the torso's depth at the midline per height -- from the texels' extremes, not a mean (the bust
    # pulls a mean forward) and not the vertices (too few on the male body: the plane crossed his back)
    torso = reg['torso']
    mid = torso & (np.abs(x) < 1.5)
    zc, ym = [], []
    for z0 in np.arange(z[torso].min(), z[torso].max(), 1.0):
        sel = mid & (z >= z0) & (z < z0 + 1.0)
        if (sel & (y > 0)).any() and (sel & (y < 0)).any():
            zc.append(z0 + 0.5)
            ym.append((y[sel].max() + y[sel].min()) / 2)
    ym = np.convolve(np.pad(ym, 2, mode='edge'), np.ones(5) / 5, mode='valid')
    ymid = np.interp(z, zc, ym)
    front, back = torso & (y > ymid), torso & (y <= ymid)
    zcrotch, zhip = Z(L['crotch']), Z(L['hip'])
    z_collar = Z(L['chest'] + 0.012)
    z_under = Z(L['underbust'] - 0.006)
    z_waist = Z(L['navel'] + 0.035)
    z_blade = Z(L['upper_back'] - 0.05)
    z_pit = Z(L['nipple'] + 0.025)
    v_apex, v_slope = zcrotch + 2.0, 0.9

    # flanks, on down over the hip to where the leg's outer seam takes over -- on the leg only its outer half (the
    # plane cuts the thigh's inner side too: short ticks beside the crotch)
    seam((torso | (reg['leg'] & (np.abs(x) > 9.5))) & between(z, z_pit, zcrotch - 1.0) & (np.abs(x) > 5.0), y - ymid)
    seam(front & between(z, z_collar + 1.0, v_apex), x)                               # sternum, down to the V
    z_spine_top, z_spine_end = Z(L['top'] - 0.03), Z(L['lower_back']) + 1.7   # ends on the access panel's lid
    for edge in (-0.9, 0.9):                                                          # the spine: a jointed strip
        seam(back & between(z, z_spine_top, z_spine_end), x - edge)
    zs = z_spine_top
    while zs > z_spine_end + 1.0:
        seam(back & (np.abs(x) < 0.9) & (np.abs(z - zs) < 1.0), z - zs, width=0.8, detail=True)
        zs -= 2.4
    seam(front, z - z_collar)                                                         # collarbones
    seam(front, z - z_under)                                                          # under the chest
    seam(torso & (z > v_apex), z - z_waist)                                           # waist band, all round
    seam(back, z - z_blade)                                                           # below the shoulder blades
    seam(front & (z < z_waist), (z - (v_apex + v_slope * np.abs(x))) / np.hypot(1, v_slope))   # the V over the hips

    # ---- arms: rings at the shoulder, a pair at the elbow, one round the forearm; a seam along the inside
    for side in (1, -1):
        am = (reg['arm'] | reg['hand']) & (x * side > 0)
        limb = _Limb(X[reg['arm'] & (x * side > 0)], np.array((side, 0.0, -0.5)), np.array((0.0, 0.0, -1.0)))
        t, r, th = limb.coords(X[am])
        full = np.zeros(n)
        full[am] = t
        T = full
        arm = am
        seam(arm, T - limb.frac(0.17))
        seam(arm, T - (limb.frac(0.5) - 1.1))
        seam(arm, T - (limb.frac(0.5) + 1.3))
        seam(arm, T - limb.frac(0.75))
        arc = np.zeros(n)
        arc[am] = r * _wrap(th)      # theta 0: the underside (world down, across the arm)
        seam(arm & (T > limb.frac(0.17)), arc)
        # vents: short slots across the top of the forearm
        top = np.zeros(n)
        top[am] = r * _wrap(th - np.pi)
        for k in range(4):
            tk = limb.frac(0.82) + k * 0.75
            slot = arm & (np.abs(top) < 1.1) & (np.abs(T - tk) < 0.6)
            seam(slot, T - tk, width=1.4, detail=True)
            fill[slot] = np.maximum(fill[slot], np.exp(-((T[slot] - tk) / 0.12) ** 2) * np.clip((1.1 - np.abs(top[slot])) / 0.3, 0, 1))

    # ---- legs: rings at mid thigh, round the knee, mid calf and the ankle; seams down the outer and inner side
    knee_h = 0.285
    for side in (1, -1):
        lm = (reg['leg'] | reg['foot']) & (x * side > 0)
        limb = _Limb(X[reg['leg'] & (x * side > 0) & (z < zcrotch - 1.0)], np.array((0.0, 0.0, -1.0)), np.array((side, 0.0, 0.0)))
        t, r, th = limb.coords(X[lm])
        arc_out = np.zeros(n)
        arc_out[lm] = r * _wrap(th)
        arc_in = np.zeros(n)
        arc_in[lm] = r * _wrap(th - np.pi)
        leg = lm
        z_top = zcrotch - 1.0
        z_ankle = Z(0.075)
        for h in (L['thigh'], knee_h + 0.045, knee_h - 0.04, 0.17):
            seam(leg & (z < z_top), z - Z(h))
        seam(leg, z - z_ankle)
        seam(leg & between(z, z_top, z_ankle), arc_out)
        seam(leg & between(z, z_top, z_ankle), arc_in)
        # knee cap: an oval on the front of the knee
        zk = Z(knee_h)
        near = leg & (np.abs(z - zk) < 1.0)
        if near.any():
            fx = x[near][np.argmax(y[near])]
            s = 2.4 * (np.sqrt(((x - fx) / 2.2) ** 2 + ((z - zk) / 2.9) ** 2) - 1.0)
            seam(leg & (y > np.median(y[leg])) & (np.abs(z - zk) < 4.0), s, detail=True)

    # ---- service details
    for side in (1, -1):    # ports under the collarbones
        zp = Z(L['chest'] - 0.012)
        cand = front & (np.abs(z - zp) < 0.4)
        if cand.any():
            k = np.flatnonzero(cand)[np.argmin(np.abs(x[cand] - side * 5.0))]
            d = np.linalg.norm(X - X[k], axis=1)
            seam(d < 2.0, d - 0.85, width=0.9, detail=True)
            seam(d < 2.0, d - 0.42, width=0.6, detail=True)
            fill = np.maximum(fill, np.clip((0.40 - d) / 0.08, 0, 1) * 0.8)
    zb = Z(L['lower_back'])                 # access panel at the small of the back
    s = 1.4 * ((np.abs(x / 1.9) ** 6 + np.abs((z - zb) / 1.4) ** 6) ** (1 / 6) - 1.0)
    seam(back & (np.abs(x) < 4) & (np.abs(z - zb) < 3), s, detail=True)

    # ---- the colour: tint x pillow x groove x lip, then darker fills. The pillow is a short shadow band along the
    # structural seams on a lighter shell: a band that reached a panel's centre stepped wherever a seam's mask ended
    pillow = PILLOW[1] - (PILLOW[1] - PILLOW[0]) * np.exp(-(np.where(np.isfinite(dmin), dmin, 9.0) / PILLOW_REACH) ** 2)
    f = pillow * (1 - GROOVE_DEPTH * groove) * (1 + LIP_GAIN * lip * (1 - groove))
    f = f * (1 - 0.55 * np.clip(fill, 0, 1))
    F = f[:, None] * TINT[None, :]
    # leave the genitals as they are, fading over 2 units
    fade = np.clip((P.genital_distance(P.cov).reshape(-1)[idx] - 0.5) / 2.0, 0, 1)
    rgb = np.zeros(m.covered.shape + (3,))
    alpha = np.zeros(m.covered.shape)
    rgb.reshape(-1, 3)[idx] = np.clip(SKIN[None, :] * F, 0, 1)
    alpha.reshape(-1)[idx] = fade
    return rgb, alpha


# ---------------------------------------------------------------- the face (a LooksMenu face tint, face.py)

FACE_DEPTH = 0.52    # a face tint multiplies (blend "Multiply"): it can only darken, so the face's seams are grooves
FACE_BAND = 0.10      # ... with a faint shadow band beside them, and no light lip


def _polyline_distance(Q, pts):
    """Distance from 2D points Q (n x 2) to the polyline through pts."""
    best = np.full(len(Q), np.inf)
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = np.asarray(a, float), np.asarray(b, float)
        ab = b - a
        t = np.clip(((Q - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        best = np.minimum(best, np.linalg.norm(Q - (a + t[:, None] * ab), axis=1))
    return best


def face_landmarks(m):
    """Measured on the head mesh (local units, face towards +y, z up): the nose tip, an ear's outermost point, the
    chin (the lowest point of the front midline) and the neck's bottom edge."""
    V = m.vertices
    nose = V[np.argmax(V[:, 1])]
    ears = V[np.abs(V[:, 0]) > np.abs(V[:, 0]).max() - 0.3]
    ear = np.array((np.abs(ears[:, 0]).mean(), ears[:, 1].mean(), ears[:, 2].mean()))
    front = V[(np.abs(V[:, 0]) < 0.4) & (V[:, 1] > nose[1] - 3.5)]
    chin = front[np.argmin(front[:, 2])]
    return {'nose': nose, 'ear': ear, 'chin': chin, 'neck': float(V[:, 2].min()), 'top': float(V[:, 2].max())}


def synth_face(m):
    """The face's half of the synthetic skin: (multiplier HxWx3, alpha HxW) for a face tint, white = untouched.
    A face plate whose edge runs from the temple down in front of the ear, round the jaw's angle and under the jaw
    to the chin; a brow seam across the forehead; a cheek seam under each cheekbone; a ring round each ear; the
    throat's midline. Everything fades out above the hairline and towards the neck's bottom edge, where the body
    overlay has faded too (the head is another mesh: a seam cannot run on across it)."""
    L = face_landmarks(m)
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx]
    x, y, z = X[:, 0], X[:, 1], X[:, 2]
    n = len(idx)
    dmin = np.full(n, np.inf)
    ye, ze = L['ear'][1], L['ear'][2]
    yc, zc = L['chin'][1], L['chin'][2]
    yn, zn = L['nose'][1], L['nose'][2]
    side_pts = [(ye + 2.7, ze + 3.4), (ye + 2.15, ze + 1.0), (ye + 2.1, ze - 1.8), (ye + 2.6, zc + 1.6),
                (ye + 4.2, zc + 0.6), (yc - 1.2, zc - 0.15)]
    YZ = np.stack([y, z], axis=1)

    def between(v, a, b):
        return (v >= a) & (v <= b)

    def seam(mask, d):
        sel = np.flatnonzero(mask)
        dmin[sel] = np.minimum(dmin[sel], d[sel] if np.ndim(d) and len(d) == n else d)

    seam(np.abs(x) > 1.2, _polyline_distance(YZ, side_pts))                         # the face plate's edge
    seam((y > ye + 2.4) & (np.abs(x) < L['ear'][0] - 1.0), np.abs(z - (zn + 4.9)))  # the brow seam
    cheek = [(ye + 2.1, zn - 0.5), (ye + 4.6, zn - 1.25), (yn - 2.7, zn - 1.0)]
    seam(np.abs(x) > 2.3, _polyline_distance(YZ, cheek))                            # under the cheekbones
    er = np.hypot(y - ye, z - ze)                                                   # round each ear's root, on
    seam(between(np.abs(x), L['ear'][0] - 2.4, L['ear'][0] - 0.6), np.abs(er - 2.05))   # the skull, not the flap
    seam((y > 0) & (z < zc - 0.6) & (z > L['neck'] + 1.0), np.abs(x))              # the throat
    groove = np.exp(-(np.where(np.isfinite(dmin), dmin, 9.0) / 0.062) ** 2)
    band = np.exp(-(np.where(np.isfinite(dmin), dmin, 9.0) / 0.45) ** 2)
    dark = np.clip(FACE_DEPTH * groove + FACE_BAND * band, 0, 1)
    # fade above the hairline (about the brow seam plus 2.5) and over the lowest 3 units of the neck
    fade = np.clip(((zn + 7.4) - z) / 1.2, 0, 1) * np.clip((z - (L['neck'] + 1.0)) / 2.5, 0, 1)
    dark = dark * fade
    tex = np.ones(m.covered.shape + (3,))
    alpha = np.zeros(m.covered.shape)
    tex.reshape(-1, 3)[idx] = (1.0 - dark)[:, None] * np.array((0.97, 0.985, 1.0))[None, :] ** dark[:, None]
    alpha.reshape(-1)[idx] = np.clip(dark / FACE_DEPTH, 0, 1)
    return tex, alpha
