"""Complexion's own overlays, painted on the body in 3D and baked into its UV map (C-5, C-7).

Every painter works on UVMap's per-texel 3D position and normal, never on UV coordinates: a bruise is a blob
around a point ON the body, so it crosses UV seams whole and lands on ribs, not on a guess of where ribs sit in
the texture. Units are the game's (about 1.43 cm each); the body faces +y, z is up.

Each painter returns (rgb HxWx3 in 0..1, alpha HxW in 0..1) for one template. A painter takes a numpy Generator,
so every template is reproducible from its seed.
"""
import os

import numpy as np

from body import REGIONS


# ---------------------------------------------------------------- noise


def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def value_noise(p, scale, seed):
    """Smooth 3D value noise in 0..1 at points p (...x3), features about 1/scale units across."""
    q = p * scale
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[..., 0] if dx else 1 - f[..., 0]) * (f[..., 1] if dy else 1 - f[..., 1]) * (f[..., 2] if dz else 1 - f[..., 2])
                out = out + w * _hash3(i[..., 0] + dx, i[..., 1] + dy, i[..., 2] + dz, seed)
    return out


def fbm(p, scale, seed, octaves=4):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + amp * value_noise(p, scale * (2 ** o), seed + 101 * o)
        norm += amp
        amp *= 0.5
    return total / norm


# ---------------------------------------------------------------- body helpers


class Painter:
    def __init__(self, m):
        self.m = m
        self.p = m.position
        self.n = m.normal
        self.h = m.height()
        self.cov = m.covered & (m.region != REGIONS.index('genital'))
        lo, hi = m.bounds
        self.lo, self.hi = lo, hi
        self.region = m.region
        if not hasattr(m, '_zorder'):
            flat = np.flatnonzero(m.covered & (m.region != REGIONS.index('genital')))
            z = m.position.reshape(-1, 3)[flat, 2]
            order = np.argsort(z)
            m._zorder, m._zsorted = flat[order], z[order]
        self.zorder, self.zsorted = m._zorder, m._zsorted

    def near(self, centre, reach):
        """Flat indices of the covered texels within reach of centre's height."""
        lo = np.searchsorted(self.zsorted, centre[2] - reach)
        hi = np.searchsorted(self.zsorted, centre[2] + reach)
        return self.zorder[lo:hi]

    def blob_into(self, a, centre, normal, radius, gain=1.0, cap=1.0, mod=None):
        """np.maximum of a (in place) and a blob around centre, computed only near it."""
        idx = self.near(centre, radius * 4)
        if not len(idx):
            return
        P = self.p.reshape(-1, 3)[idx]
        N = self.n.reshape(-1, 3)[idx]
        d2 = ((P - centre) ** 2).sum(-1)
        v = np.exp(-d2 / (2 * radius * radius)) * np.clip((N @ normal - 0.15) / 0.5, 0, 1) * gain
        if mod is not None:
            v = v * mod.reshape(-1)[idx]
        flat = a.reshape(-1)
        flat[idx] = np.maximum(flat[idx], np.clip(v, 0, cap))

    def genital_distance(self, mask):
        """For the texels in mask: the 3D distance to the nearest genital vertex (inf without any)."""
        g = self.m.vertices[self.m.vertex_region == REGIONS.index('genital')]
        out = np.full(self.cov.shape, np.inf)
        if not len(g):
            return out
        idx = np.flatnonzero(mask)
        P = self.p.reshape(-1, 3)[idx]
        best = np.full(len(idx), np.inf)
        for j in range(0, len(P), 32768):  # texels in chunks too: back hair is ~900k texels (5 GB at once)
            q = P[j:j + 32768]
            for k in range(0, len(g), 256):
                d = np.sqrt(((q[:, None, :] - g[None, k:k + 256, :]) ** 2).sum(-1)).min(axis=1)
                best[j:j + 32768] = np.minimum(best[j:j + 32768], d)
        out.reshape(-1)[idx] = best
        return out

    def reg(self, *names):
        mask = np.zeros(self.cov.shape, bool)
        for name in names:
            mask |= self.region == REGIONS.index(name)
        return mask & self.cov

    def pick_points(self, rng, mask, count, weight=None):
        """count body points (position, normal) drawn from the texels in mask, weighted."""
        idx = np.flatnonzero(mask)
        if not len(idx):
            return []
        w = None
        if weight is not None:
            w = weight.ravel()[idx]
            w = w / w.sum()
        sel = rng.choice(idx, size=count, replace=True, p=w)
        P = self.p.reshape(-1, 3)
        N = self.n.reshape(-1, 3)
        return [(P[k], N[k]) for k in sel]

    def blob(self, centre, normal, radius):
        """A soft blob around a body point: gaussian of 3D distance, cut where the surface turns away (the other
        side of a limb must not get the same bruise)."""
        d2 = ((self.p - centre) ** 2).sum(-1)
        facing = np.clip((self.n @ normal - 0.15) / 0.5, 0, 1)
        return np.exp(-d2 / (2 * radius * radius)) * facing * self.cov


def landmarks(m):
    """Heights (0 feet .. 1 the neck seam, as Painter.h) and points of the body's landmarks, MEASURED on the mesh.
    The first anchors assumed heights instead (a chest at 0.80, a shoulder at 0.83, a nape at 0.875), and on these
    bodies 0.80 is under the bust and 0.875 between the shoulder blades (measured 2026-10-03: CBBE nipples at 0.856,
    the torso's top at 0.968, the crotch at 0.566). Everything that places a mark by height uses these.

    nipples: per side (+1 the character's right, -1 left), the tip -- the vertex ring that stands out most from its
    neighbourhood along the local normal (the same on women's breasts and men's flat chests)."""
    if hasattr(m, '_landmarks'):
        return m._landmarks
    V, T = m.vertices, m.triangles
    lo, hi = m.bounds[0][2], m.bounds[1][2]

    def H(z):
        return (z - lo) / (hi - lo)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, T[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    torso = m.vertex_region == REGIONS.index('torso')
    hv = H(V[:, 2])
    top = float(hv[torso & (np.abs(V[:, 0]) < 2.0)].max())
    front_mid = torso & (vn[:, 1] > 0.3)
    crotch = float(hv[front_mid].min())
    nipples = {}
    for side in (1, -1):
        cand = np.flatnonzero((V[:, 0] * side > 1.0) & (hv > 0.70) & (hv < 0.95) & torso & (vn[:, 1] > 0.2))
        C, N = V[cand], vn[cand]
        C, N = C[C[:, 1] > C[:, 1].max() - 3.0], N[C[:, 1] > C[:, 1].max() - 3.0]  # the front, not the ribcage sides
        d2 = ((C[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        near = d2 < 1.2 ** 2
        mean = (near[..., None] * C[None, :, :]).sum(1) / near.sum(1)[:, None]
        nmean = (near[..., None] * N[None, :, :]).sum(1) / near.sum(1)[:, None]
        nmean /= np.linalg.norm(nmean, axis=1, keepdims=True)
        bump = ((C - mean) * nmean).sum(1)
        k = np.argsort(-bump)[:5]
        nipples[side] = C[k].mean(axis=0)
    nip = float(np.mean([H(p[2]) for p in nipples.values()]))
    out = {
        'top': top, 'crotch': crotch, 'nipple': nip, 'nipples': nipples,
        'neck': top - 0.02,                     # the nape / the base of the throat, below the seam's fade
        'chest': (nip + top) / 2 + 0.005,       # the upper chest: above the breasts, below the collarbones
        'upper_back': nip + 0.03,               # between the shoulder blades
        'shoulder': top - 0.045,                # the shoulder cap
        'underbust': nip - 0.055 if m.sex == 'female' else nip - 0.03,
        'navel': crotch + 0.08,
        'belly': crotch + 0.065,
        'lower_back': crotch + 0.06,
        'hip': crotch + 0.035,
        'thigh': crotch - 0.12,
        'calf': 0.16,
    }
    m._landmarks = out
    return out


def over(rgb, alpha, c, a):
    """Composites colour c (3,) or (...,3) at alpha a onto (rgb, alpha), premultiplied 'over'."""
    a = np.clip(a, 0, 1)
    out_a = a + alpha * (1 - a)
    safe = np.maximum(out_a, 1e-6)[..., None]
    rgb[:] = (np.asarray(c) * a[..., None] + rgb * (alpha * (1 - a))[..., None]) / safe
    alpha[:] = out_a


def blank(m):
    return np.zeros(m.covered.shape + (3,)), np.zeros(m.covered.shape)


# ---------------------------------------------------------------- painters


def bruises(m, rng, count=(2, 4), age='fresh'):
    """Bruises on ribs, flanks, upper arms, thighs and shins: blotchy, darker at the core."""
    P = Painter(m)
    rgb, alpha = blank(m)
    torso = P.reg('torso') & (P.h > 0.5) & (P.h < 0.85)
    weight = np.where(torso, 1.0, 0.0) + np.where(P.reg('arm') & (P.h > 0.7), 0.7, 0.0) \
        + np.where(P.reg('leg') & (P.h > 0.15), 0.9, 0.0)
    pts = P.pick_points(rng, weight > 0, int(rng.integers(count[0], count[1] + 1)), weight)
    mottle = fbm(P.p, 0.7, int(rng.integers(1 << 30)), 3)
    for c, n in pts:
        r = rng.uniform(2.0, 4.5)
        core = np.zeros(m.covered.shape)
        P.blob_into(core, c, n, r)
        a = np.clip(core * (0.55 + 0.75 * mottle) * rng.uniform(0.7, 0.95) * (1.0 if age == 'fresh' else 1.25), 0, 0.85)
        if age == 'fresh':
            rim, mid, deep = (0.55, 0.12, 0.17), (0.38, 0.09, 0.22), (0.22, 0.06, 0.20)
        else:
            rim, mid, deep = (0.55, 0.52, 0.16), (0.50, 0.40, 0.18), (0.38, 0.22, 0.24)
        t = np.clip(core * 1.4, 0, 1)[..., None]
        colour = np.where(t > 0.66, np.asarray(deep), np.where(t > 0.33, np.asarray(mid), np.asarray(rim)))
        colour = colour * (0.85 + 0.3 * mottle[..., None])
        over(rgb, alpha, colour, a)
    return rgb, alpha


def grime(m, rng, amount=0.5, legs_only=False):
    """Ground-in dirt: heaviest on the feet, shins and knees, then hands and elbows, patchy on the torso."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    base = fbm(P.p, 0.18, seed, 5)
    streak = fbm(P.p * np.array([1.0, 1.0, 0.35]), 0.5, seed + 7, 3)
    low = np.clip((0.42 - P.h) / 0.42, 0, 1)                      # 1 at the feet, 0 above the thighs
    where = 0.35 + 0.65 * low
    if legs_only:
        where = low
    else:
        where = where + np.where(P.reg('arm') & (P.h < 0.75), 0.25, 0.0)
    cover = np.clip((base * 0.65 + streak * 0.35 - (0.62 - 0.25 * amount)) * 3.2, 0, 1) * where * P.cov
    a = np.clip(cover * (0.35 + 0.35 * amount), 0, 0.6)
    colour = np.stack([0.20 + 0.08 * base, 0.16 + 0.06 * base, 0.12 + 0.04 * base], -1)
    over(rgb, alpha, colour, a)
    return rgb, alpha


def dried_blood(m, rng, sources=(1, 2)):
    """Dried blood: a smear where it came from, drips running down from it, and spatter around."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.6), 1.0, 0.0) + np.where(P.reg('arm'), 0.5, 0.0)
    dark = np.array((0.26, 0.04, 0.03))
    for c, n in P.pick_points(rng, weight > 0, int(rng.integers(sources[0], sources[1] + 1)), weight):
        seed = int(rng.integers(1 << 30))
        smear = P.blob(c, n, rng.uniform(2.5, 4.5)) * (0.4 + 0.9 * fbm(P.p, 0.9, seed, 3))
        a = np.clip(smear * 1.3, 0, 0.9)
        # Drips: thin runs straight down (-z) from the smear, on the same side of the body.
        for _ in range(int(rng.integers(2, 6))):
            x0 = c + rng.normal(0, 0.9, 3) * np.array([1, 1, 0])
            length = rng.uniform(4, 14)
            width = rng.uniform(0.18, 0.4)
            dz = x0[2] - P.p[..., 2]
            lateral = np.sqrt((P.p[..., 0] - x0[0]) ** 2 + (P.p[..., 1] - x0[1]) ** 2)
            along = np.clip(dz / length, 0, 1)
            w = width * (1 - 0.6 * along)
            run = (dz > 0) & (dz < length) & (lateral < w * 2.5)
            drip = np.exp(-(lateral / np.maximum(w, 1e-3)) ** 2) * (1 - along ** 3) * run
            drip *= np.clip((P.n @ n) * 2, 0, 1) * P.cov
            a = np.maximum(a, drip * 0.85)
        # Spatter: small drops around the source.
        for _ in range(int(rng.integers(30, 70))):
            off = rng.normal(0, 4.0, 3)
            P.blob_into(a, c + off, n, rng.uniform(0.12, 0.35), gain=3, cap=0.8)
        colour = dark * (0.8 + 0.5 * fbm(P.p, 1.3, seed + 3, 2))[..., None]
        over(rgb, alpha, colour, a)
    return rgb, alpha


def lashes(m, rng, count=(4, 8), healed=False):
    """Whip marks across the back: long diagonal welts (fresh) or pale lines (healed)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    back = P.reg('torso') & (P.n[..., 1] < -0.15) & (P.h > 0.55) & (P.h < 0.9)
    if not back.any():
        return rgb, alpha
    pts = P.p[back]
    cx, cz = pts[:, 0].mean(), pts[:, 2].mean()
    zr = (pts[:, 2].max() - pts[:, 2].min()) / 2
    a = np.zeros(m.covered.shape)
    for _ in range(int(rng.integers(count[0], count[1] + 1))):
        ang = rng.uniform(-0.6, 0.6) + (np.pi if rng.random() < 0.5 else 0)
        dx, dz = np.cos(ang), np.sin(ang)
        z0 = cz + rng.uniform(-0.85, 0.85) * zr
        x0 = cx + rng.uniform(-6, 6)
        # Distance from the line through (x0, z0) along (dx, dz), in the back's x-z plane.
        dist = np.abs((P.p[..., 0] - x0) * dz - (P.p[..., 2] - z0) * dx)
        along = (P.p[..., 0] - x0) * dx + (P.p[..., 2] - z0) * dz
        half = rng.uniform(7, 14)
        width = rng.uniform(0.35, 0.6)
        taper = np.clip(1 - (np.abs(along) / half) ** 4, 0, 1)
        wiggle = 0.25 * (fbm(P.p, 0.5, int(rng.integers(1 << 30)), 2) - 0.5)
        broken = 0.55 + 0.6 * fbm(P.p, 0.8, int(rng.integers(1 << 30)), 3)
        line = np.exp(-((dist + wiggle) / width) ** 2) * taper * back * np.clip(broken, 0, 1)
        halo = np.exp(-((dist + wiggle) / (width * 3.0)) ** 2) * taper * back
        a = np.maximum(a, np.maximum(line * rng.uniform(0.65, 0.9), halo * 0.22))
    if healed:
        over(rgb, alpha, (0.90, 0.72, 0.66), np.clip(a * 0.75, 0, 0.6))
    else:
        core = np.clip(a * 1.3, 0, 1)
        colour = np.where(core[..., None] > 0.75, np.asarray((0.50, 0.08, 0.10)), np.asarray((0.72, 0.22, 0.20)))
        over(rgb, alpha, colour, np.clip(a * 0.8, 0, 0.8))
    return rgb, alpha


def spank(m, rng, sides=('l', 'r')):
    """A reddened buttock with a handprint in it: palm, four fingers, a thumb."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seat = P.reg('torso', 'leg') & (P.n[..., 1] < -0.2) & (P.h > 0.47) & (P.h < 0.63)
    if not seat.any():
        return rgb, alpha
    a = np.zeros(m.covered.shape)
    for side in sides:
        half = seat & ((P.p[..., 0] > 1.5) if side == 'l' else (P.p[..., 0] < -1.5))
        if not half.any():
            continue
        pts = P.p[half]
        c = pts.mean(axis=0) + np.array([0, 0, rng.uniform(-0.5, 1.5)])
        flush = np.exp(-(((P.p[..., 0] - c[0]) / 5.0) ** 2 + ((P.p[..., 2] - c[2]) / 4.0) ** 2)) * half
        a = np.maximum(a, flush * rng.uniform(0.25, 0.35))
        # The hand, in the buttock's x-z plane, tilted a little.
        tilt = rng.uniform(-0.5, 0.5)
        ux = (P.p[..., 0] - c[0]) * np.cos(tilt) - (P.p[..., 2] - c[2]) * np.sin(tilt)
        uz = (P.p[..., 0] - c[0]) * np.sin(tilt) + (P.p[..., 2] - c[2]) * np.cos(tilt)
        palm = np.exp(-((ux / 2.6) ** 2 + ((uz + 1.0) / 2.2) ** 2) ** 2)
        hand = palm
        for k, fx in enumerate((-1.9, -0.65, 0.65, 1.9)):
            flen = (2.6, 3.3, 3.1, 2.4)[k]
            fz = uz - 1.0
            finger = np.exp(-((ux - fx) / 0.5) ** 4) * (fz > 0) * np.exp(-(fz / flen) ** 6)
            hand = np.maximum(hand, finger)
        thumb = np.exp(-(((ux + 3.0 + 0.4 * (uz + 1)) / 0.55) ** 4)) * np.exp(-(((uz + 1.5) / 1.6) ** 4))
        hand = np.maximum(hand, thumb) * half
        a = np.maximum(a, hand * rng.uniform(0.5, 0.65))
    over(rgb, alpha, (0.75, 0.20, 0.20), a)
    return rgb, alpha


def moles(m, rng, count=(15, 40)):
    """Moles and small dark spots over the torso, back and arms."""
    P = Painter(m)
    rgb, alpha = blank(m)
    where = P.reg('torso', 'arm') & (P.h > 0.45)
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, where, int(rng.integers(count[0], count[1] + 1))):
        P.blob_into(a, c, n, rng.uniform(0.08, 0.22), gain=2.2, cap=0.9)
    over(rgb, alpha, (0.22, 0.13, 0.09), a)
    return rgb, alpha


def scars(m, rng, count=(1, 3), stitched=False):
    """Healed scars: pale raised lines with a darker rim; stitched ones have cross-marks."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm'), 0.8, 0.0) \
        + np.where(P.reg('leg') & (P.h > 0.2), 0.5, 0.0)
    a_pale = np.zeros(m.covered.shape)
    a_rim = np.zeros(m.covered.shape)
    dots = None
    for c, n in P.pick_points(rng, weight > 0, int(rng.integers(count[0], count[1] + 1)), weight):
        # A direction in the surface's tangent plane.
        t = np.cross(n, rng.normal(size=3))
        t /= np.linalg.norm(t)
        half = rng.uniform(3.5, 8.0)
        width = rng.uniform(0.25, 0.45)
        d = P.p - c
        along = d @ t
        across = np.linalg.norm(d - along[..., None] * t - (d @ n)[..., None] * n, axis=-1)
        facing = np.clip((P.n @ n - 0.3) * 3, 0, 1)
        taper = np.clip(1 - (np.abs(along) / half) ** 2, 0, 1)
        line_w = width * 0.4 if stitched else width   # a stitched incision heals thin (alasdairn's reference, 10-10)
        line = np.exp(-(across / line_w) ** 2) * taper * facing * P.cov
        rim = np.exp(-(across / (line_w * 2.2)) ** 2) * taper * facing * P.cov
        a_pale = np.maximum(a_pale, line)
        a_rim = np.maximum(a_rim, rim)
        if stitched:
            import real
            if dots is None:
                dots = np.zeros(m.covered.shape)
            real.stitch_dots(P, dots, c, n, t, half, width)
    import real
    if dots is not None:
        real.stitch_shade(P, rgb, alpha, a_pale, a_rim, dots, rng)
        return rgb, alpha
    real.scar_shade(rgb, alpha, a_pale, a_rim, 'old_pr', opacity=0.7)   # alasdairn's pick, 10-10: purple-red at 70%
    return rgb, alpha


def pubic_hair(m, rng, shape='full', size=2048, colour=(0.07, 0.05, 0.04)):
    """Male pubic hair: thousands of short dark curved strokes, densest at the centre, the outline by shape."""
    P = Painter(m)
    rgb, alpha = blank(m)
    front = P.reg('torso', 'leg') & (P.n[..., 1] > 0.1)
    # The crotch: the lowest front torso point between the legs.
    tor = P.reg('torso') & front
    if not tor.any():
        return rgb, alpha
    pts = P.p[tor]
    cz = pts[:, 2].min()
    cx = 0.0
    ux = P.p[..., 0] - cx
    uz = P.p[..., 2] - cz
    if shape == 'full':
        outline = np.exp(-((ux / 6.5) ** 2 + ((uz - 5.5) / 5.0) ** 2) ** 2)
    elif shape == 'trim':
        outline = np.exp(-((ux / 3.6) ** 2 + ((uz - 4.0) / 3.6) ** 2) ** 2)
    else:  # 'trail': trimmed with a line up to the navel
        outline = np.maximum(np.exp(-((ux / 4.2) ** 2 + ((uz - 4.0) / 3.8) ** 2) ** 2),
                             np.exp(-(ux / 0.9) ** 4) * (uz > 4) * (uz < 15) * 0.8)
    density = outline * front
    # Strokes in UV space: each hair is a short line between two texels, drawn where density allows.
    from PIL import Image, ImageDraw
    canvas = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(canvas)
    idx = np.flatnonzero(density > 0.05)
    if not len(idx):
        return rgb, alpha
    w = density.ravel()[idx]
    sel = rng.choice(idx, size=int(len(idx) * 0.25) + 1500, p=w / w.sum())
    ys, xs = np.unravel_index(sel, density.shape)
    scale = density.shape[0] / size
    for y, x in zip(ys, xs):
        ang = rng.uniform(0, np.pi * 2)
        ln = rng.uniform(3, 9) / scale
        bend = rng.uniform(-0.6, 0.6)
        pts_ = []
        for k in range(4):
            t = k / 3
            a_ = ang + bend * t
            pts_.append((x / scale + np.cos(a_) * ln * t, y / scale + np.sin(a_) * ln * t))
        draw.line(pts_, fill=int(rng.uniform(170, 245)), width=2 if rng.random() < 0.35 else 1)
    a = np.asarray(canvas.resize(density.shape[::-1]), dtype=np.float64) / 255.0 * P.cov
    base = np.clip(density * 1.3, 0, 1) ** 1.5 * (0.45 + 0.4 * fbm(P.p, 2.5, int(rng.integers(1 << 30)), 2))
    a = np.maximum(a * np.clip(density * 3, 0, 1), base)
    # The genitals are left bare (body.py), and hair stopping dead at their edge showed as a hard ring around the
    # base in game (2026-10-03, Solomon): it thins out over the last ~2 units (3 cm) before them instead.
    near = P.genital_distance(density > 0.02)
    a = a * np.clip(near / 2.0, 0.0, 1.0) ** 1.5
    over(rgb, alpha, colour, np.clip(a, 0, 0.92))
    return rgb, alpha
