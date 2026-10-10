"""The realism layer (C-13): skin detail, hair and nipple detail, painted on the body in 3D like marks.py.

Every painter returns (rgb, alpha) over the skin; make_marks.py turns that into a multiplier on the skin (C-12), so
"darker" and "lighter" here mean darker or lighter than the skin under it, whatever its tone.
"""
import numpy as np
from PIL import Image, ImageDraw

from marks import Painter, blank, fbm, landmarks, over


def _front(P):
    return P.n[..., 1] > 0.15


def freckles(m, rng, amount=0.6):
    """Sun freckles where the sun lands: densest on the tops of the shoulders, the upper chest above the breasts,
    the upper back and the outer arms, thinning out smoothly from there; small, pale, uneven, in clusters.
    In game (2026-10-03, Norma Gibson) the first version read as a rash: big even dots over the breasts and belly,
    stopping dead on a height line."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    h, n = P.h, P.n
    up = np.clip(n[..., 2] + 0.35, 0, 1)                          # faces the sky
    L = landmarks(m)
    top = np.clip((h - (L['nipple'] - 0.02)) / 0.08, 0, 1) ** 1.5   # shoulders and the top of the chest/back
    breasts = P.reg('torso') & (h > L['underbust'] - 0.02) & (h < L['nipple'] + 0.04) & (n[..., 1] > 0.35)
    torso = P.reg('torso') * top * (0.35 + 0.65 * up) * np.where(breasts, 0.15, 1.0)
    arm_out = np.abs(P.p[..., 0]) / max(np.abs(P.p[..., 0][P.reg('arm')]).max(), 1e-6)
    arms = P.reg('arm') * (0.45 + 0.55 * np.clip(n[..., 2] + n[..., 1] * 0.5 + 0.3, 0, 1)) * (0.5 + 0.5 * arm_out)
    clusters = np.clip(fbm(P.p, 0.35, seed, 3) * 2.2 - 0.55, 0.05, 1)
    sun = (np.maximum(torso, arms * 0.85) * clusters * P.cov) ** 1.3
    a = np.zeros(m.covered.shape)
    tone = fbm(P.p, 1.5, seed + 1, 2)
    for c, nn in P.pick_points(rng, sun > 0.01, int(500 + 1500 * amount), sun):
        P.blob_into(a, c, nn, rng.uniform(0.025, 0.07), gain=rng.uniform(0.5, 1.1), cap=rng.uniform(0.18, 0.4))
    edge = 0.6 + 0.6 * fbm(P.p, 6.0, seed + 2, 2)               # ragged, not round
    colour = np.stack([0.60 - 0.08 * tone, 0.42 - 0.06 * tone, 0.30 - 0.04 * tone], -1)
    over(rgb, alpha, colour, np.clip(a * edge, 0, 0.42))
    return rgb, alpha


def birthmark(m, rng):
    """One café-au-lait patch: irregular, soft-edged, light brown."""
    P = Painter(m)
    rgb, alpha = blank(m)
    where = P.reg('torso', 'arm', 'leg') & (P.h > 0.2)
    pts = P.pick_points(rng, where, 1)
    if not pts:
        return rgb, alpha
    c, n = pts[0]
    a = np.zeros(m.covered.shape)
    P.blob_into(a, c, n, rng.uniform(1.6, 3.2), gain=1.8, cap=1.0)
    edge = fbm(P.p, 0.9, int(rng.integers(1 << 30)), 4)
    a = np.clip((a * (0.7 + 0.8 * edge) - 0.25) * 2.2, 0, 0.6)
    over(rgb, alpha, (0.58, 0.40, 0.28), a)
    return rgb, alpha


def pores(m, rng, amount=0.5):
    """Skin texture: fine pores and faint blotching, strongest where skin is thick (back, thighs, buttocks)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    fine = fbm(P.p, 6.0, seed, 2)
    blotch = fbm(P.p, 0.35, seed + 3, 3)
    pore = np.clip((fine - 0.62) * 6, 0, 1) * 0.35
    a = (pore + np.clip((blotch - 0.55) * 1.5, 0, 1) * 0.25) * amount * P.cov
    over(rgb, alpha, (0.55, 0.38, 0.32), np.clip(a, 0, 0.35))
    return rgb, alpha


def veins(m, rng):
    """Faint blue-green veins on the breasts or chest, inner arms and inner thighs."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    ridge = np.abs(fbm(P.p * np.array([1.0, 1.0, 0.6]), 0.55, seed, 4) - 0.5)
    lines = np.clip(1 - ridge / 0.05, 0, 1) ** 1.5
    L = landmarks(m)
    chest = P.reg('torso') & _front(P) & (P.h > L['underbust']) & (P.h < L['nipple'] + 0.05)
    if m.sex == 'female':  # on the breasts, around (not over) the areolas
        tipd = np.min([np.sqrt(((P.p - t) ** 2).sum(-1)) for t in L['nipples'].values()], axis=0)
        chest = chest & (tipd > 2.2) & (tipd < 6.5)
    else:
        chest = chest & False
    where = chest | (P.reg('arm') & (P.n[..., 1] > 0.3)) \
        | (P.reg('leg') & (P.h > L['crotch'] - 0.15) & (P.h < L['crotch'] - 0.03) & (np.abs(P.n[..., 0]) > 0.4))
    soft = np.clip(fbm(P.p, 0.25, seed + 9, 2) * 1.6 - 0.4, 0, 1)
    a = lines * soft * where * 0.45
    over(rgb, alpha, (0.40, 0.48, 0.62), a)
    return rgb, alpha


def stretch_marks(m, rng):
    """Stretch marks: pale, slightly pink parallel streaks on the hips, belly sides, thighs or breasts."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    zone = rng.choice(['hips', 'belly', 'breasts', 'thighs'])
    h, x, front = P.h, P.p[..., 0], P.n[..., 1]
    if zone == 'hips':
        L = landmarks(m)
        where = P.reg('torso', 'leg') & (h > L['crotch'] - 0.10) & (h < L['crotch'] + 0.06) & (np.abs(P.n[..., 0]) > 0.25)
    elif zone == 'belly':
        L = landmarks(m)
        where = P.reg('torso') & (h > L['crotch'] + 0.01) & (h < L['navel'] + 0.02) & (front > 0.2)
    elif zone == 'breasts':
        L = landmarks(m)
        tipd = np.min([np.sqrt(((P.p - t) ** 2).sum(-1)) for t in L['nipples'].values()], axis=0)
        where = P.reg('torso') & (h > L['underbust'] - 0.01) & (h < L['nipple'] + 0.05) & (front > 0.2) & (tipd > 2.5)
    else:
        where = P.reg('leg') & (h > 0.32) & (h < 0.48)
    # Streaks: thin lines along a direction, broken and wavy.
    ang = rng.uniform(-0.6, 0.6)
    coord = x * np.cos(ang) + P.p[..., 2] * np.sin(ang)
    wave = coord * 2.6 + 3.0 * fbm(P.p, 0.4, seed, 2)
    streak = np.clip(np.cos(wave) * 1.8 - 0.9, 0, 1)
    broken = np.clip(fbm(P.p, 0.8, seed + 1, 3) * 2.2 - 0.8, 0, 1)
    fade = np.clip(fbm(P.p, 0.3, seed + 2, 2) * 2.0 - 0.5, 0, 1)
    a = streak * broken * fade * where * 0.7
    over(rgb, alpha, (0.95, 0.72, 0.70), a)
    return rgb, alpha


def soft_bumps(m, rng, where, amount):
    """Acne as alasdairn approved it for the light set (2026-10-09): small, soft, flat-red bumps, a few faded dark
    marks of old ones, hardly a whitehead -- never the ringed discs of the first recipe ("light acne ain't light").
    amount 0..1 sets how many and how big; the look stays the same."""
    P = Painter(m)
    rgb, alpha = blank(m)
    red = np.zeros(m.covered.shape)
    head = np.zeros(m.covered.shape)
    old = np.zeros(m.covered.shape)
    count = int(20 + 48 * amount) if amount < 0.4 else int(20 + 120 * amount)
    big = 0.16 + (0.0 if amount < 0.4 else 0.06 * amount)
    cap = 0.40 if amount < 0.4 else min(0.40 + 0.12 * amount, 0.50)
    for c, n in P.pick_points(rng, where > 0, count, where):
        r = rng.uniform(0.08, big)
        roll = rng.random()
        if roll < 0.15:
            P.blob_into(old, c, n, r * 0.8, gain=1.0, cap=0.28)
            continue
        P.blob_into(red, c, n, r, gain=1.1, cap=cap)
        if roll > (0.92 if amount < 0.4 else 0.88):
            P.blob_into(head, c, n, r * 0.22, gain=1.0, cap=0.22)
    over(rgb, alpha, (0.52, 0.32, 0.28), old)
    over(rgb, alpha, (0.82, 0.42, 0.40), red)
    over(rgb, alpha, (0.90, 0.80, 0.70), head)
    return rgb, alpha


def pimples(m, rng, amount=0.5):
    """Pimples on the back, shoulders, chest and buttocks, as soft bumps (soft_bumps)."""
    P = Painter(m)
    where = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) * P.cov
    return soft_bumps(m, rng, where, amount)


AREOLA = {'pink': (0.84, 0.50, 0.49), 'rose': (0.70, 0.38, 0.37), 'brown': (0.54, 0.35, 0.27),
          'dark': (0.33, 0.21, 0.17)}


def nipples(m, rng, tone='brown', female=True, size=None):
    """Areola and nipple, centred on the nipple tip measured on the mesh (marks.landmarks: the vertex ring standing
    out most from its neighbourhood). The first version took a woman's "most forward point", which is the front of
    the breast, not the nipple: in review (2026-10-03) every areola sat off-centre, its Montgomery bumps a dark dotted
    ring like a gear.

    The areola: a defined but slightly irregular edge, colour deepening toward the nipple, fine wrinkles; a few small
    Montgomery glands, LIGHTER than the areola, scattered in its outer half; the nipple itself darker and denser.
    size: the areola's radius in game units (about 1.43 cm each); random within the sex's range when None."""
    P = Painter(m)
    rgb, alpha = blank(m)
    col = np.array(AREOLA[tone])
    if size is None:
        size = rng.uniform(1.3, 2.0) if female else rng.uniform(0.7, 1.0)
    seed = int(rng.integers(1 << 30))
    a_areola = np.zeros(m.covered.shape)
    a_tip = np.zeros(m.covered.shape)
    a_gland = np.zeros(m.covered.shape)
    shade = np.ones(m.covered.shape)
    for side, tip in landmarks(m)['nipples'].items():
        idx = P.near(tip, size * 2.5)
        if not len(idx):
            continue
        Q = P.p.reshape(-1, 3)[idx]
        Nq = P.n.reshape(-1, 3)[idx]
        k = np.argmin(((Q - tip) ** 2).sum(-1))
        n0 = Nq[k]
        d = np.sqrt(((Q - Q[k]) ** 2).sum(-1))
        facing = np.clip((Nq @ n0 - 0.1) / 0.3, 0, 1)
        wobble = 1 + 0.045 * (fbm(Q, 0.9, seed + side, 2) - 0.5) * 2 + 0.02 * (fbm(Q, 3.0, seed + side + 5, 2) - 0.5)
        r = d / (size * wobble)
        edge = np.clip((1.0 - r) / 0.14, 0, 1) ** 1.3
        a_areola.reshape(-1)[idx] = np.maximum(a_areola.reshape(-1)[idx], edge * facing)
        # deeper toward the nipple, lighter through the middle, a little deeper again at the rim
        prof = 0.82 + 0.16 * np.clip(r / 0.55, 0, 1) - 0.10 * np.clip((r - 0.75) / 0.2, 0, 1) * np.clip((1.05 - r) / 0.1, 0, 1)
        shade.reshape(-1)[idx] = np.minimum(shade.reshape(-1)[idx], prof)
        tip_r = size * (0.24 if female else 0.32)
        a_tip.reshape(-1)[idx] = np.maximum(a_tip.reshape(-1)[idx], np.clip((tip_r - d) / (tip_r * 0.35), 0, 1) * facing)
        t = np.cross(n0, (0.0, 0.0, 1.0))
        t = t / (np.linalg.norm(t) or 1)
        b = np.cross(n0, t)
        for _ in range(int(rng.integers(4, 10)) if female else int(rng.integers(0, 4))):
            ang = rng.uniform(0, 2 * np.pi)
            q = Q[k] + (t * np.cos(ang) + b * np.sin(ang)) * size * rng.uniform(0.5, 0.85)
            P.blob_into(a_gland, q, n0, rng.uniform(0.09, 0.14), gain=1.6, cap=rng.uniform(0.45, 0.65))
    wrinkle = 0.88 + 0.24 * fbm(P.p, 7.0, seed + 7, 2)
    colour = col[None, None, :] * (shade * wrinkle)[..., None]
    over(rgb, alpha, colour, np.clip(a_areola * (0.62 if female else 0.5), 0, 0.7))
    over(rgb, alpha, col * 0.70, np.clip(a_tip * 0.75, 0, 0.8))
    over(rgb, alpha, np.clip(col * 1.22 + 0.08, 0, 1), np.clip(a_gland * a_areola, 0, 0.6))
    return rgb, alpha


def hair(m, rng, density, colour, length=(3, 8), share=0.2, base=0.45, size=2048):
    """Hair strokes where density (a texel field 0..1) says, drawn in UV space as short curved lines, over a
    soft base so it reads as hair rather than dirt. Shared by pubic and body hair."""
    P = Painter(m)
    rgb, alpha = blank(m)
    idx = np.flatnonzero(density > 0.05)
    if not len(idx):
        return rgb, alpha
    canvas = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(canvas)
    w = density.ravel()[idx]
    sel = rng.choice(idx, size=int(len(idx) * share) + 300, p=w / w.sum())
    ys, xs = np.unravel_index(sel, density.shape)
    scale = density.shape[0] / size
    for y, x in zip(ys, xs):
        ang = rng.uniform(0, np.pi * 2)
        ln = rng.uniform(*length) / scale
        bend = rng.uniform(-0.6, 0.6)
        pts = [(x / scale + np.cos(ang + bend * t / 3) * ln * t / 3, y / scale + np.sin(ang + bend * t / 3) * ln * t / 3) for t in range(4)]
        draw.line(pts, fill=int(rng.uniform(170, 245)), width=2 if rng.random() < 0.3 else 1)
    strokes = np.asarray(canvas.resize(density.shape[::-1]), dtype=np.float64) / 255.0 * P.cov
    soft = np.clip(density * 1.3, 0, 1) ** 1.5 * (base + 0.35 * fbm(P.p, 2.5, int(rng.integers(1 << 30)), 2))
    a = np.maximum(strokes * np.clip(density * 3, 0, 1), soft)
    near = P.genital_distance(density > 0.02)
    a = a * np.clip(near / 2.0, 0.0, 1.0) ** 1.5
    over(rgb, alpha, colour, np.clip(a, 0, 0.92))
    return rgb, alpha


HAIR = {'black': (0.06, 0.05, 0.04), 'brown': (0.20, 0.13, 0.08), 'auburn': (0.32, 0.15, 0.08),
        'blond': (0.55, 0.42, 0.26), 'grey': (0.45, 0.43, 0.42)}


def pubic_female(m, rng, style='natural', colour='brown', size=2048):
    """Women's pubic hair: natural, trimmed, landing strip, triangle; on the mons, above the vulva."""
    P = Painter(m)
    front = P.reg('torso', 'leg') & (P.n[..., 1] > 0.1)
    tor = P.reg('torso') & front
    if not tor.any():
        return blank(m)
    cz = P.p[tor][:, 2].min()
    ux, uz = P.p[..., 0], P.p[..., 2] - cz
    if style == 'natural':
        d = np.exp(-((ux / (2.2 + 0.45 * np.clip(uz, 0, 9))) ** 2 + ((uz - 3.5) / 3.6) ** 2) ** 2)
    elif style == 'trimmed':
        d = np.exp(-((ux / (1.4 + 0.3 * np.clip(uz, 0, 6))) ** 2 + ((uz - 3.0) / 2.6) ** 2) ** 2)
    elif style == 'triangle':
        # trimmed to a triangle, but hair, not a stencil: the edges soft and ragged (a hard mask read as a sticker
        # in the 2026-10-03 collage)
        ragged = 0.35 * (fbm(P.p, 1.6, int(rng.integers(1 << 30)), 2) - 0.5)
        inside = np.clip((0.55 * uz - np.abs(ux) + ragged) / 0.55, 0, 1) * np.clip((uz - 0.8) / 0.6, 0, 1) \
            * np.clip((6.2 - uz + ragged) / 0.8, 0, 1)
        d = inside ** 1.5
    else:  # landing strip
        d = np.exp(-(ux / 0.75) ** 4) * np.exp(-((uz - 3.8) / 2.9) ** 6)
    return hair(m, rng, d * front, HAIR[colour], length=(2, 6), share=0.22, base=0.4, size=size)


def chest_density(P, m, rng, pattern='full'):
    """Where a man's chest hair grows: ONE broad patch across the chest, densest over the breastbone and round the
    nipples, thinning toward the shoulders and armpits; heavy chests continue down the belly, widening to the pubic
    hair. (Two round pads on the pecs, and a separate disc on the belly, read as stickers in the 2026-10-03
    collage.) Returns 0..1 per texel."""
    L = landmarks(m)
    x, h = np.abs(P.p[..., 0]), P.h
    hc = L['nipple'] - 0.005
    ragged = 0.55 + 0.7 * fbm(P.p, 0.6, int(rng.integers(1 << 30)), 3)
    chest = np.exp(-((x / 7.2) ** 2 + ((h - hc) / 0.052) ** 2) ** 1.4) * ragged
    core = np.exp(-((x / 2.6) ** 2 + ((h - hc + 0.006) / 0.06) ** 2))
    trail = np.exp(-(x / 0.8) ** 2) * np.clip((hc - 0.04 - h) / 0.04, 0, 1) * (h > L['navel'] - 0.02)
    span = max(hc - 0.03 - (L['crotch'] + 0.05), 1e-6)
    widen = np.clip((hc - 0.03 - h) / span, 0, 1)
    abdomen = np.exp(-(x / (1.0 + 6.0 * widen ** 1.5)) ** 2) * (h < hc - 0.03) * (h > L['crotch'] + 0.05) * ragged
    if pattern == 'light':
        d = chest * 0.42
    elif pattern == 'sternum':
        # A patch across the breastbone that spreads between the pecs, ragged, thinning below them into a faint
        # trail. (A narrow even band from chest to navel read as a painted stripe: the owner's photo, 2026-10-04.)
        spread = np.exp(-((x / 4.6) ** 2 + ((h - hc + 0.004) / 0.042) ** 2) ** 1.25) * ragged
        below = np.clip((h - (hc - 0.075)) / 0.06, 0, 1)
        d = np.maximum(np.maximum(spread * 0.62, core * ragged * 0.5 * below), trail * 0.22)
    elif pattern == 'heavy':
        d = np.maximum(np.maximum(chest * 0.9, core * 0.75), abdomen * 0.6)
    else:
        d = np.maximum(np.maximum(chest * 0.72, core * 0.55), trail * 0.5)
    front = (P.n[..., 1] > 0.1) * P.reg('torso')
    return np.clip(d, 0, 1) * front


def body_hair_male(m, rng, where='chest', colour='brown', size=2048):
    """Men's body hair: a chest (with a belly trail), or forearms and shins."""
    P = Painter(m)
    front = P.n[..., 1] > 0.1
    if where == 'chest':
        d = chest_density(P, m, rng, 'full')
        return hair(m, rng, d, HAIR[colour], length=(3, 7), share=0.07, base=0.12, size=size)
    # Arms reach out sideways in the bind pose: the forearm is the outer half, by distance from the middle.
    arm_out = np.abs(P.p[..., 0]) / max(np.abs(P.p[..., 0][P.reg('arm')]).max(), 1e-6)
    forearm = P.reg('arm') & (arm_out > 0.5) & (arm_out < 0.93)
    shin = P.reg('leg') & (P.h < 0.27) & (P.h > 0.06)
    patch = np.clip(fbm(P.p, 0.4, int(rng.integers(1 << 30)), 2) * 2 - 0.5, 0, 1)
    d = (forearm * 0.5 + shin * 0.4) * patch
    return hair(m, rng, d, HAIR[colour], length=(2, 5), share=0.035, base=0.05, size=size)


def stubble_female(m, rng, colour='brown', size=2048):
    """Leg and underarm stubble: tiny dark dots, light."""
    P = Painter(m)
    rgb, alpha = blank(m)
    legs = P.reg('leg') & (P.h > 0.05) & (P.h < 0.45)
    pits = np.zeros(m.covered.shape, bool)
    for side in (1, -1):
        under = P.reg('arm') & (P.p[..., 0] * side > 0) & (P.n[..., 2] < -0.45) & (P.h > 0.72) & (P.h < 0.95)
        if under.any():
            idx = np.flatnonzero(under)
            c = P.p.reshape(-1, 3)[idx[np.argmin(np.abs(P.p.reshape(-1, 3)[idx, 0]))]]
            pits |= (((P.p - c) ** 2).sum(-1) < 1.6 ** 2) & (P.n[..., 2] < 0.2) & P.cov
    where = np.where(legs, 0.6, 0.0) + np.where(pits, 1.0, 0.0)
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, where > 0, 2500, where):
        P.blob_into(a, c, n, 0.035, gain=1.5, cap=0.5)
    over(rgb, alpha, HAIR[colour], a)
    return rgb, alpha
