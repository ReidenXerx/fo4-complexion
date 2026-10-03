"""C-15 (owner, 2026-10-03): the marks of a hard life, faction flavour and ordinary wasteland skin, painted on the
body in 3D like marks.py and realism.py.

- Captives and rough life: rope and shackle marks around wrists and ankles, a collar's chafe, grip bruises,
  cigarette burns, bite marks, hickeys, lipstick kisses, words scrawled in marker.
- Faction flavour: the Disciples' ritual cuts and bloody handprints, the Children of Atom's radiation sores and
  scarred Atom, bullet, shrapnel and laser-burn scars, the Pack's body paint.
- Ordinary life: tan lines, sunburn, mud on the legs, age spots, varicose veins, cellulite, surgery scars, men's
  back hair and happy trail, women's underarm hair.

Every painter returns (rgb, alpha) over the skin; make_marks.py turns it into a multiplier (C-12).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import decals
from decals import limb, limb_end, ring_coords
from marks import Painter, blank, fbm, landmarks, over
from realism import HAIR, hair

FRESH_BRUISE = ((0.55, 0.12, 0.17), (0.38, 0.09, 0.22), (0.22, 0.06, 0.20))


# ---------------------------------------------------------------- helpers


def _unit(v):
    return v / max(np.linalg.norm(v), 1e-9)


def spot(P, mask, x, h, facing=0.0):
    """The body point (position, normal) in mask nearest to x (game units, + = the character's right) and height h
    (0..1), preferring texels whose normal's y (front +) is at least `facing` when facing > 0, at most it when < 0."""
    idx = np.flatnonzero(mask & P.cov)
    pts = P.p.reshape(-1, 3)[idx]
    nrm = P.n.reshape(-1, 3)[idx]
    hh = P.h.reshape(-1)[idx]
    score = np.abs(pts[:, 0] - x) + 40 * np.abs(hh - h)
    if facing > 0:
        score = score + 20 * np.clip(facing - nrm[:, 1], 0, None)
    elif facing < 0:
        score = score + 20 * np.clip(nrm[:, 1] - facing, 0, None)
    k = np.argmin(score)
    return pts[k], nrm[k]


def torso_width(P):
    torso = P.reg('torso')
    return np.abs(P.p[..., 0][torso & (np.abs(P.h - 0.75) < 0.02)]).max()  # (kept: every x offset was tuned to it)


def crotch_h(P):
    front = P.reg('torso') & (P.n[..., 1] > 0.3)
    return P.h[front].min()


def segment(P, c, n, t, half, width, facing=0.3):
    """A soft line on the skin through c along tangent t, half long, width wide; cut where the surface turns
    away. Returns (alpha, along) per texel."""
    t = _unit(t - n * (t @ n))
    d = P.p - c
    along = d @ t
    across = np.linalg.norm(d - along[..., None] * t - (d @ n)[..., None] * n, axis=-1)
    face = np.clip((P.n @ n - facing) * 3, 0, 1)
    taper = np.clip(1 - (np.abs(along) / half) ** 2, 0, 1)
    return np.exp(-(across / width) ** 2) * taper * face * P.cov, along


def scar_line(P, a_pale, a_rim, c, n, t, half, width, stitched=False):
    line, _ = segment(P, c, n, t, half, width)
    rim, _ = segment(P, c, n, t, half * 1.05, width * 2.2)
    np.maximum(a_pale, line, out=a_pale)
    np.maximum(a_rim, rim, out=a_rim)
    if stitched:
        side = _unit(np.cross(n, t))
        tt = _unit(t - n * (t @ n))
        for s in np.linspace(-half * 0.8, half * 0.8, max(int(half * 1.3), 3)):
            st, _ = segment(P, c + tt * s, n, side, width * 3.0, 0.09)
            np.maximum(a_pale, st * 0.7, out=a_pale)


def paint_scars(rgb, alpha, a_pale, a_rim, pale=(0.94, 0.72, 0.68), rim=(0.55, 0.24, 0.24)):
    over(rgb, alpha, rim, np.clip(a_rim * 0.6, 0, 0.5))
    over(rgb, alpha, pale, np.clip(a_pale * 0.9, 0, 0.8))


# ---------------------------------------------------------------- captives and rough life


def bindings(m, rng, where='wrists', fresh=True):
    """Rope marks: two or three twisted bands around both wrists (or ankles), raw and red when fresh, brown when
    healing; with a reddened, scuffed halo."""
    P = Painter(m)
    rgb, alpha = blank(m)
    which = 'arm' if where == 'wrists' else 'leg'
    a_core = np.zeros(m.covered.shape)
    a_halo = np.zeros(m.covered.shape)
    seed = int(rng.integers(1 << 30))
    for side in (1, -1):
        mask, c, a = limb(P, which, side)
        if not mask.any():
            continue
        t0 = limb_end(P, mask, c, a) - (2.7 if which == "arm" else 2.4)
        t, theta, r = ring_coords(P, mask, c, a, t0)
        twist = rng.uniform(5, 8)
        strands = int(rng.integers(2, 4))
        for k in range(strands):
            off = (k - (strands - 1) / 2) * 0.62 + 0.25 * np.sin(theta * 2 + k)
            band = np.exp(-((t - off) / 0.24) ** 2)
            stri = 0.55 + 0.45 * np.cos(theta * twist * 2 + (t - off) * 14)
            a_core = np.maximum(a_core, band * stri * mask)
        a_halo = np.maximum(a_halo, np.exp(-(t / (0.62 * strands)) ** 4) * mask)
    scuff = 0.6 + 0.6 * fbm(P.p, 2.0, seed, 2)
    if fresh:
        over(rgb, alpha, (0.80, 0.30, 0.28), np.clip(a_halo * 0.35 * scuff, 0, 0.4))
        over(rgb, alpha, (0.55, 0.10, 0.12), np.clip(a_core * 0.75 * scuff, 0, 0.8))
    else:
        over(rgb, alpha, (0.60, 0.42, 0.36), np.clip(a_halo * 0.2 * scuff, 0, 0.25))
        over(rgb, alpha, (0.48, 0.30, 0.26), np.clip(a_core * 0.45 * scuff, 0, 0.5))
    return rgb, alpha


def shackles(m, rng, where='ankles'):
    """Shackle chafe: one wide band around both ankles (or wrists), bruised at the edges, rubbed raw in the middle."""
    P = Painter(m)
    rgb, alpha = blank(m)
    which = 'arm' if where == 'wrists' else 'leg'
    raw = np.zeros(m.covered.shape)
    bruise = np.zeros(m.covered.shape)
    seed = int(rng.integers(1 << 30))
    for side in (1, -1):
        mask, c, a = limb(P, which, side)
        if not mask.any():
            continue
        t0 = limb_end(P, mask, c, a) - (2.6 if which == "arm" else 2.4)
        t, theta, r = ring_coords(P, mask, c, a, t0)
        wob = 0.25 * np.sin(theta + rng.uniform(0, 6))
        raw = np.maximum(raw, np.exp(-((t - wob) / 0.55) ** 4) * mask)
        bruise = np.maximum(bruise, np.exp(-((t - wob) / 1.05) ** 2) * mask)
    mott = 0.55 + 0.7 * fbm(P.p, 1.6, seed, 3)
    rim, mid, deep = FRESH_BRUISE
    over(rgb, alpha, mid, np.clip(bruise * 0.55 * mott, 0, 0.6))
    over(rgb, alpha, (0.62, 0.16, 0.14), np.clip(raw * 0.6 * mott, 0, 0.7))
    return rgb, alpha


def collar(m, rng):
    """A collar's chafe at the base of the neck: a reddened band all the way round, darker where it rubbed."""
    P = Painter(m)
    rgb, alpha = blank(m)
    # The body mesh stops at the neck seam (the head mesh carries the throat): measured 2026-10-03, its neck bones'
    # texels are only the nape. So the collar follows the seam all the way round, a little below it: per angle about
    # the neck, the highest covered texel is the seam.
    top_z = P.p[..., 2][P.cov].max()
    near = P.cov & (np.abs(P.p[..., 0]) < 7) & (P.p[..., 2] > top_z - 6)
    cx, cy = P.p[..., 0][near].mean(), P.p[..., 1][near].mean()
    theta = np.arctan2(P.p[..., 0] - cx, P.p[..., 1] - cy)
    bins = np.clip(((theta + np.pi) / (2 * np.pi) * 72).astype(int), 0, 71)
    seam = np.full(72, -np.inf)
    np.maximum.at(seam, bins[near], P.p[..., 2][near])
    for _ in range(3):  # smooth the seam's height round the neck
        seam = (np.roll(seam, 1) + seam * 2 + np.roll(seam, -1)) / 4
    below = seam[bins] - P.p[..., 2]
    wob = 0.2 * np.sin(theta * 2 + rng.uniform(0, 6))
    dz = below - rng.uniform(1.0, 1.4) - wob
    neck = near & (np.abs(P.p[..., 0] - cx) < 6.5)
    band = np.exp(-(dz / 0.75) ** 4) * neck
    edge = np.exp(-((np.abs(dz) - 0.75) / 0.25) ** 2) * neck
    mott = 0.6 + 0.6 * fbm(P.p, 1.8, int(rng.integers(1 << 30)), 3)
    over(rgb, alpha, (0.78, 0.30, 0.28), np.clip(band * 0.35 * mott, 0, 0.45))
    over(rgb, alpha, (0.45, 0.12, 0.18), np.clip(edge * 0.55 * mott, 0, 0.6))
    return rgb, alpha


def _finger_bruises(P, a, c, n, across, rng, spacing=1.05, r=0.5, thumb=None):
    across = _unit(across - n * (across @ n))
    down = _unit(np.cross(n, across))
    for k in range(4):
        q = c + across * (k - 1.5) * spacing + down * (0.35 * ((k - 1.5) ** 2) - 0.4)
        P.blob_into(a, q, n, r * rng.uniform(0.85, 1.15), gain=1.4, cap=0.9)
    if thumb is not None:
        P.blob_into(a, thumb[0], thumb[1], r * 1.2, gain=1.3, cap=0.85)


def grip_bruises(m, rng, where='arms'):
    """Finger-shaped bruises where someone held on hard: four fingertips in a curve, and the thumb on the other
    side -- around the upper arms, or on the hips from behind (fingers on the hip bones, thumbs on the lower back)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    a = np.zeros(m.covered.shape)
    tw = torso_width(P)
    for side in (1, -1):
        if where == 'arms':
            c, n, _ = decals.anchor(m, 'upper_arm', side)
            # the thumb: the texel across the arm from c
            idx = P.near(c, 6)
            Q = P.p.reshape(-1, 3)[idx]
            Nn = P.n.reshape(-1, 3)[idx]
            k = idx[np.argmin(((Q - (c - n * 3.0)) ** 2).sum(-1) + 10 * np.clip(Nn @ n + 0.5, 0, None))]
            thumb = (P.p.reshape(-1, 3)[k], P.n.reshape(-1, 3)[k])
            _finger_bruises(P, a, c, n, np.array((0.0, 0.0, 1.0)) if abs(n[2]) < 0.8 else np.array((0.0, 1.0, 0.0)),
                            rng, thumb=thumb)
        else:
            ch = crotch_h(P)
            c, n = spot(P, P.reg('torso', 'leg'), side * 0.8 * tw, ch + 0.06, 0.25)
            t_c, t_n = spot(P, P.reg('torso'), side * 0.25 * tw, ch + 0.1, -0.5)
            _finger_bruises(P, a, c, n, np.array((0.0, 0.0, 1.0)), rng, thumb=(t_c, t_n))
    mott = 0.6 + 0.6 * fbm(P.p, 1.2, int(rng.integers(1 << 30)), 3)
    rim, mid, deep = FRESH_BRUISE
    t = np.clip(a * 1.3, 0, 1)[..., None]
    colour = np.where(t > 0.6, np.asarray(deep), np.where(t > 0.3, np.asarray(mid), np.asarray(rim)))
    over(rgb, alpha, colour, np.clip(a * 0.8 * mott, 0, 0.8))
    return rgb, alpha


def cigarette_burns(m, rng, healed=False):
    """Cigarette burns in a cluster: round, crusted dark at the rim (fresh) or pale and shiny (healed) -- on the
    inner forearm, a thigh, or the chest."""
    P = Painter(m)
    rgb, alpha = blank(m)
    zone = rng.choice(['forearm', 'thigh', 'chest', 'belly'])
    side = 1 if rng.random() < 0.5 else -1
    c0, n0, _ = decals.anchor(m, zone, side if zone != 'belly' else 0)
    core = np.zeros(m.covered.shape)
    ring = np.zeros(m.covered.shape)
    t = _unit(np.cross(n0, (0.0, 0.0, 1.0)) if abs(n0[2]) < 0.9 else np.cross(n0, (1.0, 0.0, 0.0)))
    b = np.cross(n0, t)
    for _ in range(int(rng.integers(3, 8))):
        q = c0 + t * rng.normal(0, 1.6) + b * rng.normal(0, 1.6)
        r = rng.uniform(0.28, 0.4)
        inner = np.zeros(m.covered.shape)
        outer = np.zeros(m.covered.shape)
        P.blob_into(inner, q, n0, r * 0.55, gain=2.5, cap=1.0)
        P.blob_into(outer, q, n0, r, gain=2.5, cap=1.0)
        np.maximum(core, inner, out=core)
        np.maximum(ring, np.clip(outer - inner * 0.8, 0, 1), out=ring)
    if healed:
        over(rgb, alpha, (0.60, 0.36, 0.32), np.clip(ring * 0.5, 0, 0.5))
        over(rgb, alpha, (0.95, 0.78, 0.74), np.clip(core * 0.75, 0, 0.75))
    else:
        over(rgb, alpha, (0.80, 0.30, 0.25), np.clip(ring * 0.6, 0, 0.6))
        over(rgb, alpha, (0.25, 0.10, 0.07), np.clip(core * 0.85, 0, 0.85))
    return rgb, alpha


def _bite(P, a_dent, a_bruise, c, n, rng, size=1.0):
    """One human bite: the upper and lower dental arches as two facing arcs of separate tooth marks -- the front
    teeth short and straight, wider apart toward the sides -- with a gap where the jaws' corners were, and a suction
    bruise filling the middle. (The first version was one even ring of dots: in review it read as a necklace.)"""
    t = _unit(np.cross(n, (0.0, 0.0, 1.0)) if abs(n[2]) < 0.9 else np.cross(n, (1.0, 0.0, 0.0)))
    ang = rng.uniform(-0.6, 0.6)
    t, b = t * np.cos(ang) + np.cross(n, t) * np.sin(ang), np.cross(n, t) * np.cos(ang) - t * np.sin(ang)
    ax = 1.5 * size
    for arch, bx, sign in (('upper', 0.95 * size, 1), ('lower', 0.80 * size, -1)):
        for k, th in enumerate(np.linspace(0.42, np.pi - 0.42, 6)):
            ctr = c + t * np.cos(th) * ax + b * np.sin(th) * bx * sign
            radial = _unit(t * np.cos(th) * ax / ax + b * np.sin(th) * sign)
            tang = _unit(np.cross(n, radial))
            width = 0.30 * size if 1 <= k <= 4 else 0.22 * size     # incisors broad, canines narrow
            mark, _ = segment(P, ctr, n, tang, width * 0.5, 0.075 * size, facing=0.2)
            np.maximum(a_dent, mark * rng.uniform(0.75, 1.0), out=a_dent)
    P.blob_into(a_bruise, c, n, 0.95 * size, gain=0.9, cap=0.55)


def bites(m, rng, places=('shoulder',)):
    """Human bite marks: two arcs of tooth dents, bruised around and inside."""
    P = Painter(m)
    rgb, alpha = blank(m)
    dent = np.zeros(m.covered.shape)
    bruise = np.zeros(m.covered.shape)
    ch = crotch_h(P)
    tw = torso_width(P)
    for place in places:
        side = 1 if rng.random() < 0.5 else -1
        L = landmarks(m)
        if place == 'breast':  # the upper inner breast, off the areola
            tip = L['nipples'][side]
            c, n = spot(P, P.reg('torso'), tip[0] - side * 2.5, L['nipple'] + 0.03, 0.4)
        elif place == 'inner_thigh':
            c, n, _ = decals.anchor(m, 'inner_thigh', side)
        elif place == 'butt':
            c, n = spot(P, P.reg('torso', 'leg'), side * 0.45 * tw, ch + 0.06, -0.4)
        elif place == 'neck':  # the side of the neck's base, clear of the seam's fade
            c, n = spot(P, P.reg('torso', 'head'), side * 0.3 * tw, L['top'] - 0.035, 0.0)
        else:
            c, n, _ = decals.anchor(m, 'shoulder', side)
        _bite(P, dent, bruise, c, n, rng, rng.uniform(0.9, 1.1))
    mott = 0.6 + 0.6 * fbm(P.p, 1.5, int(rng.integers(1 << 30)), 3)
    over(rgb, alpha, (0.48, 0.12, 0.22), np.clip(bruise * 0.45 * mott, 0, 0.5))
    over(rgb, alpha, (0.40, 0.06, 0.10), np.clip(dent * 0.85, 0, 0.85))
    return rgb, alpha


def hickeys(m, rng, places=('neck', 'chest')):
    """Love bites: purple-red blotches, speckled with burst capillaries."""
    P = Painter(m)
    rgb, alpha = blank(m)
    a = np.zeros(m.covered.shape)
    speck = np.zeros(m.covered.shape)
    ch = crotch_h(P)
    tw = torso_width(P)
    for place in places:
        for _ in range(int(rng.integers(1, 3))):
            side = 1 if rng.random() < 0.5 else -1
            L = landmarks(m)
            if place == 'neck':
                c, n = spot(P, P.reg('torso', 'head'), side * rng.uniform(0.15, 0.4) * tw, L['top'] - rng.uniform(0.03, 0.045), 0.0)
            elif place == 'chest':  # the upper chest and the tops of the breasts
                c, n = spot(P, P.reg('torso'), side * rng.uniform(0.2, 0.6) * tw, rng.uniform(L['nipple'] + 0.02, L['chest']), 0.4)
            elif place == 'inner_thigh':
                c, n, _ = decals.anchor(m, 'inner_thigh', side)
                c = c + np.array((0.0, 0.0, rng.uniform(-1.5, 1.5)))
            else:  # belly, low
                c, n = spot(P, P.reg('torso'), side * rng.uniform(0.1, 0.4) * tw, ch + rng.uniform(0.05, 0.1), 0.5)
            r = rng.uniform(0.7, 1.1)
            P.blob_into(a, c, n, r, gain=1.3, cap=0.9)
            for _ in range(40):
                q = c + rng.normal(0, r * 0.7, 3)
                P.blob_into(speck, q, n, 0.05, gain=1.4, cap=0.7)
    edge = 0.65 + 0.6 * fbm(P.p, 2.2, int(rng.integers(1 << 30)), 3)
    over(rgb, alpha, (0.55, 0.16, 0.26), np.clip(a * 0.7 * edge, 0, 0.7))
    over(rgb, alpha, (0.32, 0.05, 0.15), np.clip(speck * a * 1.2, 0, 0.6))
    return rgb, alpha


def lips(w=440, h=230):
    """A lipstick print: the upper lip with its bow, the lower lip fuller, pointed corners, a gap between them and
    the lips' vertical creases left bare."""
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    mid, half = h * 0.50, w / 2 - 12
    xs = np.linspace(-1, 1, 61)
    upper = [(w / 2 + u * half, mid - h * 0.30 * (1 - abs(u) ** 1.7) ** 0.9 + h * 0.09 * np.exp(-(u / 0.13) ** 2)) for u in xs]
    lower = [(w / 2 + u * half, mid + h * 0.38 * (1 - abs(u) ** 1.9) ** 0.75) for u in xs]
    d.polygon(upper + [(w / 2 + half, mid - 4), (w / 2 - half, mid - 4)], fill=255)
    d.polygon(lower + [(w / 2 + half, mid + 4), (w / 2 - half, mid + 4)], fill=255)
    d.line([(w / 2 + u * half, mid + 3 * np.sin(u * 3)) for u in xs], fill=0, width=9)
    for k in range(-12, 13):
        x = w / 2 + k * half / 13
        d.line((x, mid - 8, x + k * 0.8, mid - h * 0.20 * (1 - abs(k / 13) ** 2)), fill=0, width=3)
        d.line((x, mid + 10, x + k * 0.9, mid + h * 0.28 * (1 - abs(k / 13) ** 2)), fill=0, width=3)
    return im.filter(ImageFilter.GaussianBlur(1.5))


LIPSTICK = {'red': (0.62, 0.05, 0.12), 'pink': (0.82, 0.32, 0.45), 'plum': (0.38, 0.06, 0.16)}


def kisses(m, rng, colour='red', spots=(('butt', 1), ('butt', -1), ('inner_thigh', 1))):
    """Lipstick prints, a few, at angles: on the buttocks, the inner thighs, the chest, the belly, the neck."""
    rgb, alpha = blank(m)
    for spot_, side in spots:
        r, a = decals.project(m, lips(), spot_, side, width=rng.uniform(2.4, 3.0), rotate=rng.uniform(-0.6, 0.6),
                              alpha=0.85, ink='fresh', crude=0.5, seed=int(rng.integers(1 << 30)))
        over(rgb, alpha, LIPSTICK[colour], a)
    return rgb, alpha


def scrawl(m, rng, items=(('word', 'NEXT', 'belly', 0, 8),), ink='marker'):
    """Words in marker pen on the skin, slightly smudged."""
    rgb, alpha = blank(m)
    for kind, text, spot_, side, width in items:
        if kind == 'arrow':
            design = decals.arrow_word(text, 'marker', 'down')
        elif kind == 'tally':
            design = decals.tally(int(text))
        else:
            design = decals.word(text, 'marker')
        r, a = decals.project(m, design, spot_, side, width=width, rotate=rng.uniform(-0.25, 0.25), alpha=0.9,
                              ink='fresh', crude=0.45, seed=int(rng.integers(1 << 30)))
        over(rgb, alpha, decals.INK[ink], a)
    return rgb, alpha


# ---------------------------------------------------------------- faction flavour


def ritual_cuts(m, rng, fresh=False):
    """The Disciples' cutting: sets of short parallel cuts -- forearms, chest, thighs -- healed pale, or a newer set
    still red."""
    P = Painter(m)
    rgb, alpha = blank(m)
    pale = np.zeros(m.covered.shape)
    rim = np.zeros(m.covered.shape)
    for zone, side in (('forearm', 1), ('forearm', -1), (rng.choice(['chest', 'thigh', 'belly']), 1 if rng.random() < 0.5 else -1)):
        c, n, up = decals.anchor(m, zone, side if zone != 'belly' else 0)
        t = _unit(np.cross(n, up)) if zone != 'forearm' else _unit(np.cross(n, (side, 0.0, 0.0)))
        along = _unit(np.cross(t, n))
        count = int(rng.integers(3, 7))
        for k in range(count):
            q = c + along * (k - (count - 1) / 2) * rng.uniform(0.5, 0.7)
            scar_line(P, pale, rim, q, n, t + along * rng.uniform(-0.15, 0.15), rng.uniform(1.0, 1.8), 0.13)
    if fresh:
        over(rgb, alpha, (0.75, 0.25, 0.25), np.clip(rim * 0.6, 0, 0.6))
        over(rgb, alpha, (0.45, 0.06, 0.08), np.clip(pale * 0.85, 0, 0.85))
    else:
        paint_scars(rgb, alpha, pale, rim)
    return rgb, alpha


def hand_design(w=360, h=460, smear=True):
    """A hand print: palm, four fingers, a thumb; smeared downward when it was dragged."""
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    d.ellipse((80, 210, 290, 410), fill=255)
    for fx, fl, tilt in ((92, 140, -0.18), (152, 170, -0.05), (212, 162, 0.06), (268, 120, 0.2)):
        pts = []
        for t in np.linspace(0, 1, 12):
            pts.append((fx + np.sin(tilt) * fl * t, 245 - np.cos(tilt) * fl * t))
        for x, y in pts:
            d.ellipse((x - 19, y - 19, x + 19, y + 19), fill=255)
    for t in np.linspace(0, 1, 10):
        x, y = 85 - 60 * t, 300 - 50 * t
        d.ellipse((x - 24, y - 24, x + 24, y + 24), fill=255)
    if smear:
        arr = np.asarray(im, dtype=np.float64)
        out = arr.copy()
        for y in range(h):
            if y > 300:
                out[y] = np.maximum(out[y], out[y - 1] * 0.97)
        im = Image.fromarray(out.astype(np.uint8))
    return im.filter(ImageFilter.GaussianBlur(3))


def bloody_hands(m, rng, spots=(('chest', 1), ('belly', 0))):
    """Dried blood handprints, some dragged, as the Disciples wear them."""
    rgb, alpha = blank(m)
    for spot_, side in spots:
        r, a = decals.project(m, hand_design(smear=rng.random() < 0.6), spot_, side, width=rng.uniform(4.2, 5.0),
                              rotate=rng.uniform(-0.5, 0.5), alpha=0.85, ink='fresh', crude=0.7, seed=int(rng.integers(1 << 30)))
        over(rgb, alpha, (0.28, 0.04, 0.03), a)
    return rgb, alpha


def rad_sores(m, rng):
    """Radiation sores: raw, blotchy lesions in two or three patches, peeling at the edges."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm', 'leg'), 0.7, 0.0)
    patch = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, weight > 0, int(rng.integers(2, 4)), weight):
        P.blob_into(patch, c, n, rng.uniform(1.8, 3.2), gain=1.4, cap=1.0)
    seed = int(rng.integers(1 << 30))
    les = np.clip((fbm(P.p, 1.4, seed, 4) - 0.5) * 4, 0, 1) * patch
    halo = np.clip((fbm(P.p, 0.9, seed + 1, 3) - 0.35) * 2, 0, 1) * patch
    peel = np.clip((fbm(P.p, 3.5, seed + 2, 2) - 0.66) * 6, 0, 1) * halo
    over(rgb, alpha, (0.70, 0.30, 0.36), np.clip(halo * 0.7, 0, 0.65))
    over(rgb, alpha, (0.38, 0.12, 0.11), np.clip(les * 1.3, 0, 0.88))
    over(rgb, alpha, (0.95, 0.85, 0.78), np.clip(peel * 0.6, 0, 0.6))
    return rgb, alpha


def scar_decal(m, rng, design, spot_, side, width):
    """A design cut or burned in as a scar: a pale raised core with a darker rim."""
    rgb, alpha = blank(m)
    rim_img = design.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(6))
    seed = int(rng.integers(1 << 30))
    _, a_rim = decals.project(m, rim_img, spot_, side, width=width, alpha=1.0, crude=0.4, seed=seed)
    _, a_core = decals.project(m, design.filter(ImageFilter.GaussianBlur(2)), spot_, side, width=width, alpha=1.0,
                               crude=0.3, seed=seed)
    paint_scars(rgb, alpha, a_core, a_rim)
    return rgb, alpha


def bullet_scars(m, rng, count=(1, 3)):
    """Healed gunshot wounds: a puckered pale round scar, creased toward the middle, a dark rim."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm', 'leg') & (P.h > 0.25), 0.6, 0.0)
    pale = np.zeros(m.covered.shape)
    rim = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, weight > 0, int(rng.integers(count[0], count[1] + 1)), weight):
        r = rng.uniform(0.4, 0.6)
        P.blob_into(pale, c, n, r, gain=1.8, cap=1.0, mod=0.6 + 0.6 * fbm(P.p, 3.0, int(rng.integers(1 << 30)), 2))
        P.blob_into(rim, c, n, r * 1.7, gain=1.2, cap=0.9)
        t = _unit(np.cross(n, rng.normal(size=3)))
        for k in range(6):
            ang = k * np.pi / 3 + rng.uniform(-0.3, 0.3)
            d = t * np.cos(ang) + np.cross(n, t) * np.sin(ang)
            line, _ = segment(P, c + d * r * 1.3, n, d, r * 0.9, 0.08)
            np.maximum(pale, line * 0.7, out=pale)
    paint_scars(rgb, alpha, pale, rim)
    return rgb, alpha


def shrapnel(m, rng):
    """Shrapnel scars: dozens of small ragged scars peppering one side -- a shoulder, an arm and that side of the
    chest."""
    P = Painter(m)
    rgb, alpha = blank(m)
    side = 1 if rng.random() < 0.5 else -1
    zone = (P.reg('torso', 'arm') & (P.p[..., 0] * side > 1.0) & (P.h > 0.6))
    c0, _, _ = decals.anchor(m, 'shoulder', side)
    weight = np.exp(-((P.p - c0) ** 2).sum(-1) / (2 * 7.0 ** 2)) * zone
    pale = np.zeros(m.covered.shape)
    rim = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, weight > 0.02, int(rng.integers(18, 40)), weight):
        scar_line(P, pale, rim, c, n, rng.normal(size=3), rng.uniform(0.2, 0.7), rng.uniform(0.07, 0.14))
    paint_scars(rgb, alpha, pale, rim)
    return rgb, alpha


def laser_burn(m, rng):
    """A laser or plasma burn: a long glossy streak, pink and pale in the middle, mottled brown at the edges."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm', 'leg'), 0.5, 0.0)
    (c, n), = P.pick_points(rng, weight > 0, 1, weight)
    t = rng.normal(size=3)
    half = rng.uniform(4, 8)
    width = rng.uniform(0.45, 0.75)
    seed = int(rng.integers(1 << 30))
    core, along = segment(P, c, n, t, half, width, facing=0.1)
    edge, _ = segment(P, c, n, t, half * 1.05, width * 2.0, facing=0.1)
    mott = 0.5 + 0.8 * fbm(P.p, 1.8, seed, 3)
    over(rgb, alpha, (0.48, 0.30, 0.24), np.clip(edge * 0.55 * mott, 0, 0.6))
    over(rgb, alpha, (0.95, 0.66, 0.66), np.clip(core * 0.8, 0, 0.8))
    return rgb, alpha


def burn_scar(m, rng):
    """An old burn scar: a large patch of shiny, mottled skin, pale and pink with darker brown islands."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm', 'leg') & (P.h > 0.2), 0.8, 0.0)
    (c, n), = P.pick_points(rng, weight > 0, 1, weight)
    patch = np.zeros(m.covered.shape)
    P.blob_into(patch, c, n, rng.uniform(2.5, 4.0), gain=1.6, cap=1.0)
    seed = int(rng.integers(1 << 30))
    shape = np.clip((patch * (0.6 + 0.8 * fbm(P.p, 0.8, seed, 4)) - 0.35) * 3, 0, 1)
    mix = fbm(P.p, 1.6, seed + 1, 3)
    over(rgb, alpha, (0.93, 0.68, 0.64), np.clip(shape * (mix > 0.45) * 0.7, 0, 0.7))
    over(rgb, alpha, (0.50, 0.30, 0.25), np.clip(shape * (mix <= 0.45) * 0.55, 0, 0.6))
    return rgb, alpha


PAINT = {'green': (0.30, 0.78, 0.30), 'purple': (0.58, 0.22, 0.68), 'pink': (0.92, 0.36, 0.62), 'blue': (0.25, 0.45, 0.85)}


def pack_paint(m, rng, colour='green'):
    """The Pack's body paint: bold animal stripes across the forearms, the flanks and the thighs."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    zones = (P.reg('arm') & (P.h > 0.55)) | (P.reg('torso') & (np.abs(P.n[..., 0]) > 0.35) & (P.h > 0.5) & (P.h < 0.8)) \
        | (P.reg('leg') & (P.h > 0.3) & (P.h < 0.48) & (P.n[..., 1] > -0.2))
    # Stripes across the limbs and the flanks: bands of height, bent by noise, each tapering to a point at one end
    # -- tiger stripes, painted on with fingers.
    coord = P.p[..., 2] + 4.0 * (fbm(P.p, 0.18, seed, 3) - 0.5)
    period = rng.uniform(4.5, 6.0)
    phase = (coord / period) % 1.0
    width = 0.22 + 0.16 * fbm(P.p, 0.35, seed + 1, 2)
    stripe = np.clip((width - np.abs(phase - 0.5)) / 0.04, 0, 1)
    gaps = np.clip(fbm(P.p, 0.3, seed + 3, 2) * 3.0 - 0.8, 0, 1)
    brush = 0.8 + 0.25 * fbm(P.p, 4.0, seed + 2, 2)
    over(rgb, alpha, PAINT[colour], np.clip(stripe * gaps * brush * zones * 0.9, 0, 0.9))
    return rgb, alpha


# ---------------------------------------------------------------- ordinary life


def tan_lines(m, rng, cut='tshirt'):
    """A working tan: darker skin where the sun reached, a sharp-ish line where the clothes stopped -- a T-shirt
    (forearms and the V of the neck), a tank top (arms, shoulders, upper chest and back), a bikini or shorts
    (everything but the bikini or the shorts)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    x, h, n = P.p[..., 0], P.h, P.n
    seed = int(rng.integers(1 << 30))
    edge = 0.012 + 0.006 * fbm(P.p, 0.5, seed, 2)
    arm_out = np.abs(x) / max(np.abs(x[P.reg('arm')]).max(), 1e-6)
    tw = torso_width(P)
    ch = crotch_h(P)

    def soft(v):
        return np.clip(v / edge + 0.5, 0, 1)

    if cut == 'tshirt':
        sleeve = soft((arm_out - 0.42) * 0.25) * P.reg('arm')
        L = landmarks(m)
        neck_v = soft((h - (L['top'] - 0.035 - 0.04 * np.clip(1 - np.abs(x) / (0.35 * tw), 0, 1) * (n[..., 1] > 0))) * 1.0) * P.reg('torso', 'head')
        sun = np.maximum(sleeve, neck_v)
    elif cut == 'tank':
        strap = np.exp(-((np.abs(x) - 0.55 * tw) / (0.12 * tw)) ** 4)
        L = landmarks(m)
        neckline = L['nipple'] + 0.035 + 0.025 * (1 - strap)
        sun = np.maximum(P.reg('arm') * 1.0, soft(h - neckline) * (1 - strap * (h < L['top'] + 0.01)) * P.reg('torso', 'head'))
    elif cut == 'bikini':
        L = landmarks(m)
        tips = list(L['nipples'].values())
        top = np.zeros(m.covered.shape)
        band_h = L['underbust'] + 0.01
        apex_h = L['nipple'] + 0.05
        for tip in tips:  # a triangle cup: wide along the band under the breast, narrowing to its apex above
            frac = np.clip((apex_h - h) / (apex_h - band_h), 0, 1)
            half_w = 0.6 + 3.6 * frac
            cup = (h > band_h) & (h < apex_h) & (np.abs(x - tip[0]) < half_w) & (n[..., 1] > 0.1)
            top = np.maximum(top, cup.astype(float))
        # the band under the breasts, and a halter strap from each cup's apex up and in to the neck
        straps = (np.abs(h - band_h) < 0.006) & P.reg('torso')
        for tip in tips:
            t = np.clip((h - apex_h) / max(L['top'] - apex_h, 1e-6), 0, 1)
            sx = tip[0] + (np.sign(tip[0]) * 0.18 * tw - tip[0]) * t
            straps = straps | ((np.abs(x - sx) < 0.35) & (h > apex_h - 0.005) & (n[..., 1] > 0) & P.reg('torso', 'head'))
        # the bottom: a front triangle down to the crotch, and at the back the seat of the buttocks
        # the bottom: a front triangle from the hip line down to the crotch, the seat over the buttocks behind
        # (their middle is at crotch + 0.075, decals' 'butt'), and the ties round the hips joining them
        waist = ch + 0.06
        front = (n[..., 1] > 0.0) & (h > ch - 0.035) & (h < waist) & \
            (np.abs(x) < 0.12 * tw + np.clip((h - ch + 0.035) / (waist - ch + 0.035), 0, 1) * 0.68 * tw)
        # the line rises toward the back: the hip line in front, the top of the buttocks behind
        line_h = waist + 0.05 * np.clip(-n[..., 1], 0, 1)
        seat = (n[..., 1] <= 0.0) & (h > ch - 0.01) & (h < line_h) & \
            (np.abs(x) < 0.12 * tw + np.clip((h - ch + 0.01) / (waist + 0.05 - ch + 0.01), 0, 1) * 0.78 * tw)
        ties = (np.abs(h - line_h + 0.005) < 0.006)
        bottom = (front | seat | ties) & P.reg('torso', 'leg')
        cover = np.clip(top + straps + bottom, 0, 1)
        sun = (1 - cover) * P.cov
    else:  # shorts
        cover = (h > ch - 0.13) & (h < ch + 0.08) & P.reg('torso', 'leg')
        sun = (1 - cover) * P.cov
    tan = 0.75 + 0.35 * fbm(P.p, 0.3, seed + 1, 2)
    over(rgb, alpha, (0.52, 0.36, 0.25), np.clip(sun * P.cov * 0.32 * tan, 0, 0.38))
    return rgb, alpha


def sunburn(m, rng):
    """Sunburn: reddened shoulders, upper back, nape and forearms, peeling in places."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    L = landmarks(m)
    up = np.clip((P.h - (L['nipple'] + 0.01)) / 0.05, 0, 1) * P.reg('torso', 'arm', 'head') * np.clip(P.n[..., 2] + 0.6, 0, 1)
    arms = P.reg('arm') * 0.6
    burn = np.clip(np.maximum(up, arms) * (0.7 + 0.5 * fbm(P.p, 0.4, seed, 3)), 0, 1)
    peel = np.clip((fbm(P.p, 3.0, seed + 1, 3) - 0.68) * 7, 0, 1) * burn * (P.h > L['nipple'] + 0.03)
    over(rgb, alpha, (0.86, 0.36, 0.30), np.clip(burn * 0.4, 0, 0.45))
    over(rgb, alpha, (0.97, 0.88, 0.82), np.clip(peel * 0.45, 0, 0.45))
    return rgb, alpha


def mud(m, rng, amount=0.6):
    """Mud on the legs: caked on the feet and shins, splashed in drops up to the knees and thighs."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    low = np.clip((0.33 - P.h) / 0.3, 0, 1) * P.reg('leg', 'foot')
    caked = np.clip((fbm(P.p, 0.5, seed, 4) - (0.62 - 0.3 * amount)) * 4, 0, 1) * low ** 0.7
    a = caked * 0.8
    legs = P.reg('leg') & (P.h < 0.45)
    for c, n in P.pick_points(rng, legs, int(80 + 200 * amount), np.clip(0.5 - P.h, 0, None) * legs):
        P.blob_into(a, c, n, rng.uniform(0.08, 0.3), gain=2.5, cap=0.8)
    col = np.stack([0.28 + 0.06 * fbm(P.p, 2, seed + 1, 2)] * 3, -1) * np.array((1.0, 0.78, 0.52))
    over(rgb, alpha, col, np.clip(a, 0, 0.82))
    return rgb, alpha


def age_spots(m, rng):
    """Age spots: flat light-brown spots on the forearms, shoulders and upper chest."""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = np.where(P.reg('arm'), 1.0, 0.0) + np.where(P.reg('torso') & (P.h > landmarks(m)['nipple'] + 0.02), 0.6, 0.0)
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0, int(rng.integers(30, 80)), w):
        P.blob_into(a, c, n, rng.uniform(0.15, 0.45), gain=rng.uniform(0.8, 1.3), cap=0.55)
    edge = 0.7 + 0.5 * fbm(P.p, 3.0, int(rng.integers(1 << 30)), 2)
    over(rgb, alpha, (0.56, 0.38, 0.24), np.clip(a * edge, 0, 0.55))
    return rgb, alpha


def varicose(m, rng):
    """Varicose and spider veins: twisting blue-purple veins down the calves and behind the knees, fine red-purple
    webs around them."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    legs = P.reg('leg') & (P.h > 0.08) & (P.h < 0.38)
    back = np.clip(0.3 - P.n[..., 1], 0, 1)
    ridge = np.abs(fbm(P.p * np.array([1.0, 1.0, 0.35]), 0.45, seed, 4) - 0.5)
    vein = np.clip(1 - ridge / 0.045, 0, 1) ** 1.4 * legs * back
    fine = np.abs(fbm(P.p, 2.2, seed + 1, 3) - 0.5)
    web = np.clip(1 - fine / 0.03, 0, 1) * legs * np.clip(fbm(P.p, 0.5, seed + 2, 2) * 3 - 1.4, 0, 1)
    over(rgb, alpha, (0.36, 0.32, 0.55), np.clip(vein * 0.55, 0, 0.55))
    over(rgb, alpha, (0.55, 0.22, 0.38), np.clip(web * 0.5, 0, 0.5))
    return rgb, alpha


def cellulite(m, rng):
    """Cellulite: soft dimpling on the backs and outsides of the thighs and on the buttocks."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    ch = crotch_h(P)
    zone = (P.reg('leg', 'torso') & (P.h > ch - 0.17) & (P.h < ch + 0.1) & (P.n[..., 1] < 0.25))
    fade = np.clip(fbm(P.p, 0.3, seed, 2) * 2.5 - 0.7, 0, 1)
    dimple = np.clip((fbm(P.p, 1.3, seed + 1, 3) - 0.55) * 4, 0, 1)
    over(rgb, alpha, (0.58, 0.44, 0.38), np.clip(dimple * fade * zone * 0.35, 0, 0.35))
    return rgb, alpha


def surgery_scar(m, rng, which='appendix'):
    """Surgery scars where surgeons cut: the appendix (low on the right of the belly, slanting), a Caesarean (low
    across the belly), the breastbone (down the middle of the chest), a knee."""
    P = Painter(m)
    rgb, alpha = blank(m)
    pale = np.zeros(m.covered.shape)
    rim = np.zeros(m.covered.shape)
    tw = torso_width(P)
    ch = crotch_h(P)
    if which == 'appendix':
        c, n = spot(P, P.reg('torso'), 0.45 * tw, ch + 0.07, 0.4)
        scar_line(P, pale, rim, c, n, np.array((1.0, 0.0, 0.7)), 2.6, 0.2, stitched=rng.random() < 0.5)
    elif which == 'caesarean':
        c, n = spot(P, P.reg('torso'), 0.0, ch + 0.03, 0.5)
        scar_line(P, pale, rim, c, n, np.array((1.0, 0.0, 0.0)), 4.8, 0.17)
    elif which == 'sternum':
        L = landmarks(m)
        c, n = spot(P, P.reg('torso'), 0.0, (L['nipple'] + L['chest']) / 2 - 0.01, 0.5)
        scar_line(P, pale, rim, c, n, np.array((0.0, 0.0, 1.0)), 6.0, 0.24, stitched=True)
    else:  # knee
        side = 1 if rng.random() < 0.5 else -1
        c, n = spot(P, P.reg('leg'), side * 0.42 * tw, 0.27, 0.5)
        scar_line(P, pale, rim, c, n, np.array((0.0, 0.0, 1.0)), 3.2, 0.22, stitched=rng.random() < 0.5)
    paint_scars(rgb, alpha, pale, rim)
    return rgb, alpha


def back_hair(m, rng, colour='brown', size=2048):
    """A man's back hair: across the shoulders and upper back, thinning down."""
    P = Painter(m)
    ragged = 0.6 + 0.6 * fbm(P.p, 0.6, int(rng.integers(1 << 30)), 3)
    d = np.clip((P.h - 0.66) / 0.14, 0, 1) * (P.n[..., 1] < -0.15) * P.reg('torso') * ragged
    return hair(m, rng, np.clip(d * 0.7, 0, 1), HAIR[colour], length=(3, 7), share=0.06, base=0.1, size=size)


def happy_trail(m, rng, colour='brown', size=2048):
    """A line of hair from the pubic hair up to the navel: in game units above the crotch (a height fraction cut it
    short on the men's body, 2026-10-03 review), wide at the bottom, thinning to a line, fading at both ends."""
    P = Painter(m)
    front = P.reg('torso') & (P.n[..., 1] > 0.3)
    cz = P.p[..., 2][front].min()
    uz = P.p[..., 2] - cz
    x = np.abs(P.p[..., 0])
    width = 0.55 + 1.1 * np.clip((15.0 - uz) / 8.0, 0, 1)
    ends = np.clip((uz - 7.0) / 2.0, 0, 1) * np.clip((17.5 - uz) / 3.0, 0, 1)
    d = np.exp(-(x / width) ** 2) * ends * (P.n[..., 1] > 0.2) * P.reg('torso')
    return hair(m, rng, np.clip(d * 0.95, 0, 1), HAIR[colour], length=(2, 5), share=0.18, base=0.22, size=size)


def underarm_hair(m, rng, colour='brown', size=2048):
    """Unshaved underarms: a patch in each armpit -- found as the underside of the upper arm (normal facing down)
    nearest the body. (A band down the torso's sides painted the whole flank, 2026-10-03 review.)"""
    P = Painter(m)
    d = np.zeros(m.covered.shape)
    for side in (1, -1):
        under = P.reg('arm') & (P.p[..., 0] * side > 0) & (P.n[..., 2] < -0.45) & (P.h > 0.72) & (P.h < 0.92)
        if not under.any():
            continue
        idx = np.flatnonzero(under)
        pts = P.p.reshape(-1, 3)[idx]
        k = idx[np.argmin(np.abs(pts[:, 0]))]
        c = P.p.reshape(-1, 3)[k]
        dist2 = ((P.p - c) ** 2).sum(-1)
        d = np.maximum(d, np.exp(-dist2 / (2 * 1.4 ** 2)) * (P.n[..., 2] < 0.2))
    return hair(m, rng, np.clip(d * 0.95, 0, 1) * P.cov, HAIR[colour], length=(2, 6), share=0.35, base=0.3, size=size)
