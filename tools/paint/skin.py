"""The realism layer, extended (owner, 2026-10-03: "the accent on the realistic module" -- every kind of skin detail
in real variety, and the kinds still missing).

Painted on the body in 3D like realism.py (C-9, C-13), placed by the measured landmarks (C-18), multiplied onto the
skin (C-12), faded out before the neck and wrist seams (C-16). Every painter here takes parameters, so one painter
gives many genuinely different templates: counts, sizes, tones, zones, ages.
"""
import numpy as np

from marks import Painter, blank, fbm, landmarks, over
from realism import HAIR, chest_density, hair, soft_bumps

HAIR.update({'ginger': (0.42, 0.18, 0.07), 'lightbrown': (0.34, 0.24, 0.15), 'darkbrown': (0.12, 0.08, 0.05)})

MOLE = {'dark': (0.20, 0.12, 0.08), 'brown': (0.34, 0.21, 0.14), 'light': (0.50, 0.34, 0.24), 'red': (0.55, 0.14, 0.14)}


def _unit(v):
    return v / max(np.linalg.norm(v), 1e-9)


def _zone(P, m, zone):
    """A weight field over the body for a named zone."""
    L = landmarks(m)
    h, n = P.h, P.n
    torso, arm, leg = P.reg('torso'), P.reg('arm'), P.reg('leg')
    if zone == 'back':
        w = torso * (n[..., 1] < -0.1) * (h > L['crotch'] + 0.03)
    elif zone == 'front':
        w = torso * (n[..., 1] > 0.1) * (h > L['crotch'] + 0.03)
    elif zone == 'upper':
        w = (torso * (h > L['underbust'] - 0.02)) + arm * 0.7
    elif zone == 'shoulders':
        w = (torso | arm) * np.clip((h - (L['nipple'] + 0.01)) / 0.05, 0, 1) * np.clip(n[..., 2] + 0.5, 0, 1)
    elif zone == 'arms':
        w = arm * 1.0
    elif zone == 'legs':
        w = leg * (h > 0.08)
    elif zone == 'chest':
        w = torso * (n[..., 1] > 0.2) * (h > L['underbust'] - 0.03)
    elif zone == 'buttocks':
        w = (torso | leg) * (n[..., 1] < -0.2) * (h > L['crotch'] - 0.04) * (h < L['crotch'] + 0.12)
    else:  # everywhere
        w = (torso * 1.0 + arm * 0.8 + leg * 0.6) * (h > 0.06)
    return w * P.cov


# ---------------------------------------------------------------- moles, spots, marks of the skin itself


def moles(m, rng, count=(20, 40), size=(0.07, 0.2), tone='brown', zone='everywhere', clusters=0, raised=False):
    """Moles: count and size ranges, a tone, a zone, optionally gathered in a few clusters; raised moles get a
    darker core and a soft halo."""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = _zone(P, m, zone)
    if clusters:
        bias = np.zeros(m.covered.shape)
        for c, n in P.pick_points(rng, w > 0, clusters, w):
            bias += np.exp(-((P.p - c) ** 2).sum(-1) / (2 * 3.5 ** 2))
        w = w * (0.08 + bias)
    a = np.zeros(m.covered.shape)
    core = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0, int(rng.integers(count[0], count[1] + 1)), w):
        r = rng.uniform(*size)
        P.blob_into(a, c, n, r, gain=rng.uniform(1.4, 2.4), cap=rng.uniform(0.55, 0.9))
        if raised:
            P.blob_into(core, c, n, r * 0.5, gain=2.0, cap=0.9)
    edge = 0.75 + 0.4 * fbm(P.p, 5.0, int(rng.integers(1 << 30)), 2)
    col = np.array(MOLE[tone])
    over(rgb, alpha, col, np.clip(a * edge, 0, 0.9))
    if raised:
        over(rgb, alpha, col * 0.7, np.clip(core, 0, 0.8))
    return rgb, alpha


def cherry_angiomas(m, rng, count=(15, 40)):
    """Cherry angiomas: tiny bright red dots, mostly on the trunk."""
    return moles(m, rng, count=count, size=(0.035, 0.08), tone='red', zone='front' if rng.random() < 0.6 else 'back')


def sun_spots(m, rng, amount=0.6):
    """Solar lentigines: larger, flat, irregular light-brown spots where years of sun landed -- the shoulders, the
    upper back, the backs of the forearms."""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = _zone(P, m, 'shoulders') + P.reg('arm') * np.clip(P.n[..., 2] + 0.3, 0, 1) * 0.6
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0.05, int(20 + 60 * amount), w):
        P.blob_into(a, c, n, rng.uniform(0.2, 0.55), gain=rng.uniform(0.9, 1.4), cap=rng.uniform(0.35, 0.55))
    edge = 0.55 + 0.7 * fbm(P.p, 2.5, int(rng.integers(1 << 30)), 3)
    over(rgb, alpha, (0.55, 0.38, 0.25), np.clip(a * edge, 0, 0.55))
    return rgb, alpha


def port_wine(m, rng, size=4.0):
    """A port-wine stain: a large flat red-purple patch with ragged, map-like edges."""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = _zone(P, m, 'everywhere')
    (c, n), = P.pick_points(rng, w > 0, 1, w)
    a = np.zeros(m.covered.shape)
    P.blob_into(a, c, n, size, gain=1.8, cap=1.0)
    seed = int(rng.integers(1 << 30))
    shape = np.clip((a * (0.5 + 0.9 * fbm(P.p, 0.7, seed, 4)) - 0.45) * 4, 0, 1)
    mott = 0.85 + 0.3 * fbm(P.p, 2.0, seed + 1, 2)
    over(rgb, alpha, np.array((0.62, 0.20, 0.30)) * mott[..., None], np.clip(shape * 0.6, 0, 0.6))
    return rgb, alpha


def cafe_au_lait(m, rng, count=(2, 5)):
    """Café-au-lait spots: several smooth-edged, flat, milky light-brown patches of different sizes."""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = _zone(P, m, 'everywhere')
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0, int(rng.integers(count[0], count[1] + 1)), w):
        P.blob_into(a, c, n, rng.uniform(0.8, 2.2), gain=2.4, cap=1.0)
    shape = np.clip((a * (0.75 + 0.4 * fbm(P.p, 0.8, int(rng.integers(1 << 30)), 2)) - 0.5) * 5, 0, 1)
    over(rgb, alpha, (0.60, 0.44, 0.32), np.clip(shape * 0.5, 0, 0.5))
    return rgb, alpha


def mongolian_spot(m, rng):
    """A slate-blue birthmark low on the back and over the buttocks, soft-edged."""
    P = Painter(m)
    rgb, alpha = blank(m)
    L = landmarks(m)
    w = P.reg('torso') * (P.n[..., 1] < -0.3) * (np.abs(P.h - (L['crotch'] + 0.06)) < 0.06) * (np.abs(P.p[..., 0]) < 6)
    (c, n), = P.pick_points(rng, w > 0, 1, w)
    a = np.zeros(m.covered.shape)
    P.blob_into(a, c, n, rng.uniform(2.0, 3.2), gain=1.4, cap=1.0)
    shape = np.clip((a * (0.6 + 0.7 * fbm(P.p, 0.9, int(rng.integers(1 << 30)), 3)) - 0.3) * 2.2, 0, 1)
    over(rgb, alpha, (0.42, 0.46, 0.58), np.clip(shape * 0.5, 0, 0.5))
    return rgb, alpha


def linea_nigra(m, rng, strength=0.35):
    """The pregnancy line: a dark vertical line from the navel (or above) down to the pubic hair."""
    P = Painter(m)
    rgb, alpha = blank(m)
    L = landmarks(m)
    top = L['navel'] + rng.uniform(-0.01, 0.04)
    x = np.abs(P.p[..., 0])
    width = rng.uniform(0.18, 0.32)
    line = np.exp(-(x / width) ** 2) * (P.n[..., 1] > 0.3) * P.reg('torso') \
        * np.clip((top - P.h) / 0.015, 0, 1) * np.clip((P.h - L['crotch'] - 0.02) / 0.015, 0, 1)
    line = line * (0.75 + 0.4 * fbm(P.p, 1.5, int(rng.integers(1 << 30)), 2))
    over(rgb, alpha, (0.38, 0.24, 0.17), np.clip(line * strength * 1.6, 0, 0.6))
    return rgb, alpha


def flush(m, rng, zone='chest'):
    """Blotchy redness, rosacea-like: uneven red patches over the upper chest and neck (or the cheeks of the
    buttocks, or the backs of the upper arms -- keratosis pilaris)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    if zone == 'arms':
        w = P.reg('arm') * (P.n[..., 1] < 0.2) * (np.abs(P.p[..., 0]) < np.abs(P.p[..., 0][P.reg('arm')]).max() * 0.6)
    else:
        w = _zone(P, m, zone)
    blot = np.clip((fbm(P.p, 0.8, seed, 3) - 0.45) * 3, 0, 1)
    speck = np.clip((fbm(P.p, 6.0, seed + 1, 2) - 0.6) * 5, 0, 1)
    over(rgb, alpha, (0.80, 0.34, 0.33), np.clip(w * blot * 0.35, 0, 0.35))
    over(rgb, alpha, (0.70, 0.25, 0.25), np.clip(w * speck * blot * 0.35, 0, 0.3))
    return rgb, alpha


def goosebumps(m, rng, zone='arms'):
    """Goose flesh: thousands of tiny bumps, each a lit top and a shadowed foot (light and dark specks paired)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = _zone(P, m, zone if zone != 'arms_legs' else 'arms') + (_zone(P, m, 'legs') * 0.8 if zone == 'arms_legs' else 0)
    lit = np.zeros(m.covered.shape)
    dark = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0, 6000, w):
        P.blob_into(lit, c + np.array((0, 0, 0.02)), n, 0.03, gain=1.0, cap=0.35)
        P.blob_into(dark, c - np.array((0, 0, 0.03)), n, 0.03, gain=1.0, cap=0.3)
    over(rgb, alpha, (0.62, 0.48, 0.42), dark)
    over(rgb, alpha, (0.95, 0.82, 0.74), lit)
    return rgb, alpha


# ---------------------------------------------------------------- scars


def _scar_line(P, a_pale, a_rim, c, n, t, half, width, stitched=False):
    t = _unit(t - n * (t @ n))
    d = P.p - c
    along = d @ t
    across = np.linalg.norm(d - along[..., None] * t - (d @ n)[..., None] * n, axis=-1)
    face = np.clip((P.n @ n - 0.3) * 3, 0, 1)
    taper = np.clip(1 - (np.abs(along) / half) ** 2, 0, 1)
    np.maximum(a_pale, np.exp(-(across / width) ** 2) * taper * face * P.cov, out=a_pale)
    np.maximum(a_rim, np.exp(-(across / (width * 2.2)) ** 2) * taper * face * P.cov, out=a_rim)
    if stitched:
        side = _unit(np.cross(n, t))
        for s in np.linspace(-half * 0.8, half * 0.8, max(int(half * 1.3), 3)):
            q = c + t * s
            dq = P.p - q
            st = np.abs(dq @ t)
            mark = np.exp(-(st / 0.14) ** 2) * (np.abs(dq @ side) < width * 3.5) * face * P.cov
            np.maximum(a_pale, mark * 0.75, out=a_pale)


def scars(m, rng, count=(1, 3), length=(3.5, 8.0), width=(0.25, 0.45), stitched=False, zone='everywhere', age='old'):
    """Healed scars with lengths, widths and a zone; 'old' is pale and flat, 'newer' still pink."""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = _zone(P, m, zone)
    pale = np.zeros(m.covered.shape)
    rim = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0, int(rng.integers(count[0], count[1] + 1)), w):
        _scar_line(P, pale, rim, c, n, np.cross(n, rng.normal(size=3)), rng.uniform(*length), rng.uniform(*width), stitched)
    import real
    real.scar_shade(rgb, alpha, pale, rim, 'old_pr', opacity=0.7)   # alasdairn's pick for every healed scar set, 10-10
    return rgb, alpha


def keloid(m, rng, zone='chest'):
    """A keloid: a raised, glossy, lumpy scar that overgrew its wound -- curved, swelling into nodules along its
    length, with a few claw-like runners off its edges; pink-brown, lit on one side and shadowed on the other so
    it reads raised. (The first one was a straight even band: "a straight line with magic marker", alasdairn,
    2026-10-09.)"""
    P = Painter(m)
    rgb, alpha = blank(m)
    w = _zone(P, m, zone)
    (c, n), = P.pick_points(rng, w > 0, 1, w)
    t = _unit(np.cross(n, rng.normal(size=3)))
    b = _unit(np.cross(n, t))
    half, width = rng.uniform(1.6, 3.2), rng.uniform(0.40, 0.55)
    bend = rng.uniform(-0.6, 0.6)
    d = P.p - c
    along = d @ t
    side = d @ b - bend * (along / half) ** 2          # across, from a curved centre line
    u = np.clip(along / half, -1.5, 1.5)
    seed = int(rng.integers(1 << 30))
    # width swells into nodules and narrows between them; rounded ends
    nod = 0.7 + 0.45 * np.sin(u * rng.uniform(4.0, 6.5) + rng.uniform(0, 6.3)) ** 2 + 0.35 * fbm(P.p, 2.2, seed, 2)
    wid = width * nod * np.clip(1 - u ** 2, 0, 1) ** 0.35
    ragged = 0.06 * fbm(P.p, 5.0, seed + 1, 2)
    face = np.clip((P.n @ n - 0.3) * 3, 0, 1) * P.cov
    body = np.clip((wid + ragged - np.abs(side)) / 0.07, 0, 1) * (np.abs(u) < 1.0) * face
    # claw-like runners: short tapering spurs off the edges
    for _ in range(int(rng.integers(2, 5))):
        at = rng.uniform(-0.7, 0.7) * half
        sgn = rng.choice((-1.0, 1.0))
        length = width * rng.uniform(0.8, 1.6)
        lean = rng.uniform(-0.6, 0.6)
        out = sgn * side - width * 0.6
        spur_w = width * 0.32 * np.clip(1 - out / length, 0, 1)
        spur = np.clip((spur_w - np.abs(along - at - lean * np.clip(out, 0, None))) / 0.05, 0, 1) * (out > -0.2) * (out < length) * face
        body = np.maximum(body, spur * 0.85)
    lit = np.exp(-((side + wid * 0.35) / (wid * 0.30 + 1e-6)) ** 2) * body       # the crest, on the lit side
    shade = np.clip((side - wid * 0.25) / (wid * 0.5 + 1e-6), 0, 1) * body        # the far edge, in shadow
    over(rgb, alpha, (0.60, 0.33, 0.31), np.clip(body * 0.72, 0, 0.72))
    over(rgb, alpha, (0.40, 0.20, 0.20), np.clip(shade * 0.35, 0, 0.35))
    over(rgb, alpha, (0.88, 0.64, 0.60), np.clip(lit * 0.45, 0, 0.45))
    return rgb, alpha


def vaccination(m, rng, side=-1, count=1):
    """The smallpox vaccination scar: a round, slightly sunken pale mark with a pitted floor, high on the outer
    upper arm (usually the left)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    L = landmarks(m)
    arm = P.reg('arm') & (P.p[..., 0] * side > 0)
    if not arm.any():
        return rgb, alpha
    reach = np.abs(P.p[..., 0][arm]).max()
    w = arm * np.exp(-((np.abs(P.p[..., 0]) - reach * 0.38) / 1.5) ** 2) * np.clip(P.n[..., 2] + 0.2, 0, 1) * (np.abs(P.n[..., 0]) > 0.2)
    pale = np.zeros(m.covered.shape)
    rim = np.zeros(m.covered.shape)
    pits = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0.05, count, w):
        r = rng.uniform(0.35, 0.55)
        P.blob_into(pale, c, n, r * 0.7, gain=2.6, cap=0.9)
        ring = np.zeros(m.covered.shape)
        P.blob_into(ring, c, n, r, gain=2.0, cap=1.0)
        np.maximum(rim, np.clip(ring - pale * 1.1, 0, 1), out=rim)
        for _ in range(int(rng.integers(5, 10))):
            P.blob_into(pits, c + rng.normal(0, r * 0.3, 3), n, 0.04, gain=1.3, cap=0.5)
    over(rgb, alpha, (0.60, 0.40, 0.34), np.clip(rim * 0.45, 0, 0.45))
    over(rgb, alpha, (0.94, 0.80, 0.74), np.clip(pale * 0.7, 0, 0.7))
    over(rgb, alpha, (0.55, 0.40, 0.35), np.clip(pits * pale, 0, 0.4))
    return rgb, alpha


def bite_scar(m, rng, kind='dog'):
    """A healed bite: two facing arcs of pale puncture scars (a dog's: fewer, deeper, the canines' holes bigger),
    on a forearm or a calf."""
    P = Painter(m)
    rgb, alpha = blank(m)
    zone = P.reg('arm') * (np.abs(P.p[..., 0]) > np.abs(P.p[..., 0][P.reg('arm')]).max() * 0.55) if rng.random() < 0.6 \
        else P.reg('leg') * (P.h > 0.1) * (P.h < 0.3)
    (c, n), = P.pick_points(rng, zone > 0, 1, zone * 1.0)
    t = _unit(np.cross(n, rng.normal(size=3)))
    b = np.cross(n, t)
    pale = np.zeros(m.covered.shape)
    rim = np.zeros(m.covered.shape)
    ax, bx = (1.6, 1.0) if kind == 'dog' else (1.3, 0.9)
    teeth = 5 if kind == 'dog' else 7
    for sign in (1, -1):
        for k, th in enumerate(np.linspace(0.3, np.pi - 0.3, teeth)):
            q = c + t * np.cos(th) * ax + b * np.sin(th) * bx * sign
            r = (0.16 if k in (0, teeth - 1) else 0.09) if kind == 'dog' else 0.08
            P.blob_into(pale, q, n, r, gain=2.2, cap=0.85)
            P.blob_into(rim, q, n, r * 1.9, gain=1.4, cap=0.6)
    import real
    real.scar_shade(rgb, alpha, pale, rim, 'old')
    return rgb, alpha


# ---------------------------------------------------------------- the existing kinds, in variety


def freckles(m, rng, amount=0.6, zone='upper', size=(0.025, 0.07), tone='light'):
    """Freckles by zone (shoulders, upper, arms, everywhere), density, size and tone; clustered and ragged."""
    P = Painter(m)
    rgb, alpha = blank(m)
    L = landmarks(m)
    seed = int(rng.integers(1 << 30))
    w = _zone(P, m, zone)
    if zone in ('upper', 'shoulders'):
        tipd = np.min([np.sqrt(((P.p - t) ** 2).sum(-1)) for t in L['nipples'].values()], axis=0)
        w = w * np.where((tipd < 5.5) & (P.h < L['nipple'] + 0.04), 0.15, 1.0)
    clusters = np.clip(fbm(P.p, 0.35, seed, 3) * 2.2 - 0.55, 0.05, 1)
    w = (w * clusters) ** 1.3
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, w > 0.01, int(400 + 2200 * amount), w):
        P.blob_into(a, c, n, rng.uniform(*size), gain=rng.uniform(0.5, 1.1), cap=rng.uniform(0.18, 0.42))
    edge = 0.6 + 0.6 * fbm(P.p, 6.0, seed + 2, 2)
    base = {'light': (0.60, 0.42, 0.30), 'medium': (0.50, 0.32, 0.21), 'ginger': (0.62, 0.36, 0.20)}[tone]
    tn = fbm(P.p, 1.5, seed + 1, 2)
    colour = np.stack([base[0] - 0.08 * tn, base[1] - 0.06 * tn, base[2] - 0.04 * tn], -1)
    over(rgb, alpha, colour, np.clip(a * edge, 0, 0.45))
    return rgb, alpha


def pores(m, rng, amount=0.6, scale=6.0):
    """Skin texture: pores (fine at high scale, coarse at low) and faint blotching."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    fine = fbm(P.p, scale, seed, 2)
    blotch = fbm(P.p, 0.35, seed + 3, 3)
    a = (np.clip((fine - 0.62) * 6, 0, 1) * 0.35 + np.clip((blotch - 0.55) * 1.5, 0, 1) * 0.25) * amount * P.cov
    over(rgb, alpha, (0.55, 0.38, 0.32), np.clip(a, 0, 0.38))
    return rgb, alpha


def stretch(m, rng, zone='hips', fresh=False, amount=0.7):
    """Stretch marks by zone -- hips, belly, breasts, thighs, buttocks, or the shoulders and biceps (men, from
    muscle) -- fresh (red-purple) or old (silvery pale)."""
    P = Painter(m)
    rgb, alpha = blank(m)
    L = landmarks(m)
    seed = int(rng.integers(1 << 30))
    h, x, n = P.h, P.p[..., 0], P.n
    if zone == 'hips':
        where = P.reg('torso', 'leg') & (h > L['crotch'] - 0.10) & (h < L['crotch'] + 0.06) & (np.abs(n[..., 0]) > 0.25)
        ang = rng.uniform(-0.5, 0.5)
    elif zone == 'belly':
        where = P.reg('torso') & (h > L['crotch'] + 0.01) & (h < L['navel'] + 0.02) & (n[..., 1] > 0.2)
        ang = rng.uniform(1.2, 1.9)
    elif zone == 'breasts':
        tipd = np.min([np.sqrt(((P.p - t) ** 2).sum(-1)) for t in L['nipples'].values()], axis=0)
        where = P.reg('torso') & (h > L['underbust'] - 0.01) & (h < L['nipple'] + 0.05) & (n[..., 1] > 0.2) & (tipd > 2.5) & (tipd < 7)
        ang = None  # radial from the nipple
    elif zone == 'thighs':
        where = P.reg('leg') & (h > L['crotch'] - 0.16) & (h < L['crotch'] - 0.02) & (np.abs(n[..., 0]) > 0.3)
        ang = rng.uniform(-0.4, 0.4)
    elif zone == 'buttocks':
        where = P.reg('torso', 'leg') & (h > L['crotch'] - 0.04) & (h < L['crotch'] + 0.11) & (n[..., 1] < -0.2) & (np.abs(x) > 3)
        ang = rng.uniform(-0.3, 0.3)
    else:  # shoulders and biceps
        where = (P.reg('arm') | (P.reg('torso') & (h > L['nipple']))) & (n[..., 1] > -0.2) & (np.abs(x) > 5) & \
            (np.abs(x) < np.abs(x[P.reg('arm')]).max() * 0.45)
        ang = rng.uniform(1.2, 1.9)
    if ang is None:
        rel = np.arctan2(P.p[..., 2] - L['nipples'][1][2], P.p[..., 0] - np.sign(x) * abs(L['nipples'][1][0]))
        coord = rel * 9.0
    else:
        coord = x * np.cos(ang) + P.p[..., 2] * np.sin(ang)
    wave = coord * 2.6 + 3.0 * fbm(P.p, 0.4, seed, 2)
    streak = np.clip(np.cos(wave) * 1.8 - 0.9, 0, 1)
    broken = np.clip(fbm(P.p, 0.8, seed + 1, 3) * 2.2 - 0.8, 0, 1)
    fade = np.clip(fbm(P.p, 0.3, seed + 2, 2) * 2.0 - 0.5, 0, 1)
    a = streak * broken * fade * where * amount
    over(rgb, alpha, (0.66, 0.30, 0.42) if fresh else (0.95, 0.74, 0.72), np.clip(a, 0, 0.7))
    return rgb, alpha


def acne(m, rng, zone='back', amount=0.5):
    """Acne by zone (back, chest, buttocks, shoulders), every amount as soft bumps (realism.soft_bumps): alasdairn
    approved the light set's look and asked for it on all of them (2026-10-09). The light set keeps to the upper
    back."""
    P = Painter(m)
    w = _zone(P, m, zone)
    if amount < 0.4:
        w = w * np.clip((P.h - landmarks(m)['navel']) / 0.10, 0, 1)
    return soft_bumps(m, rng, w, amount)


def pubic_female(m, rng, style='bushy', colour='brown', size=2048):
    """More women's styles: bushy (full and spreading onto the thighs' creases), bikini (trimmed at the sides),
    stubble (shaved, growing back), heart (trimmed into a heart)."""
    P = Painter(m)
    front = P.reg('torso', 'leg') & (P.n[..., 1] > 0.1)
    tor = P.reg('torso') & front
    cz = P.p[tor][:, 2].min()
    ux, uz = P.p[..., 0], P.p[..., 2] - cz
    if style == 'bushy':
        d = np.exp(-((ux / (3.0 + 0.55 * np.clip(uz, 0, 9))) ** 2 + ((uz - 3.8) / 4.4) ** 2) ** 2)
        return hair(m, rng, np.clip(d * 1.1, 0, 1) * front, HAIR[colour], length=(3, 8), share=0.3, base=0.5, size=size)
    if style == 'bikini':
        d = np.exp(-((ux / (1.8 + 0.30 * np.clip(uz, 0, 9))) ** 2 + ((uz - 3.4) / 3.2) ** 2) ** 3)
        return hair(m, rng, d * front, HAIR[colour], length=(2, 5), share=0.25, base=0.42, size=size)
    if style == 'heart':
        hx, hz = ux / 2.4, (uz - 4.2) / 2.4
        heart = (hx ** 2 + hz ** 2 - 1) ** 3 - hx ** 2 * hz ** 3 < 0
        d = heart.astype(float) * np.clip(uz / 1.0, 0, 1)
        return hair(m, rng, d * front, HAIR[colour], length=(2, 4), share=0.3, base=0.45, size=size)
    # stubble: tiny dark dots over the shaved area
    rgb, alpha = blank(m)
    area = np.exp(-((ux / (2.6 + 0.45 * np.clip(uz, 0, 9))) ** 2 + ((uz - 3.5) / 3.8) ** 2) ** 2) * front
    near = P.genital_distance(area > 0.05)
    area = area * np.clip(near / 2.0, 0, 1)
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, area > 0.05, 5000, area):
        P.blob_into(a, c, n, 0.03, gain=1.6, cap=0.6)
    over(rgb, alpha, HAIR[colour], np.clip(a * 0.9, 0, 0.6))
    over(rgb, alpha, HAIR[colour], np.clip(area * 0.12, 0, 0.12))
    return rgb, alpha


def chest_hair(m, rng, pattern='full', colour='brown', size=2048):
    """Men's chest hair patterns (realism.chest_density): light, full, sternum, heavy -- each in a colour."""
    P = Painter(m)
    d = chest_density(P, m, rng, pattern)
    share, base = {'light': (0.04, 0.05), 'sternum': (0.07, 0.1), 'heavy': (0.09, 0.15)}.get(pattern, (0.07, 0.12))
    return hair(m, rng, d, HAIR[colour], length=(3, 7), share=share, base=base, size=size)


def limb_hair(m, rng, colour='brown', amount=1.0, size=2048):
    """Arm and leg hair, by amount."""
    P = Painter(m)
    arm_out = np.abs(P.p[..., 0]) / max(np.abs(P.p[..., 0][P.reg('arm')]).max(), 1e-6)
    forearm = P.reg('arm') & (arm_out > 0.45) & (arm_out < 0.93)
    shin = P.reg('leg') & (P.h < 0.3) & (P.h > 0.06)
    thigh = P.reg('leg') & (P.h > 0.3) & (P.h < landmarks(m)['crotch'] - 0.04) & (P.n[..., 1] > -0.2)
    patch = np.clip(fbm(P.p, 0.4, int(rng.integers(1 << 30)), 2) * 2 - 0.5, 0, 1)
    d = (forearm * 0.5 + shin * 0.45 + thigh * 0.25 * amount) * patch * amount
    return hair(m, rng, np.clip(d, 0, 1), HAIR[colour], length=(2, 5), share=0.03 + 0.025 * amount, base=0.04, size=size)


def back_hair(m, rng, colour='brown', amount=1.0, size=2048):
    """A man's back hair: shoulders and upper back, by amount."""
    P = Painter(m)
    L = landmarks(m)
    ragged = 0.6 + 0.6 * fbm(P.p, 0.6, int(rng.integers(1 << 30)), 3)
    reach = (L['nipple'] - 0.10) if amount > 0.8 else (L['nipple'] - 0.02)
    d = np.clip((P.h - reach) / 0.12, 0, 1) * (P.n[..., 1] < -0.15) * P.reg('torso') * ragged
    return hair(m, rng, np.clip(d * 0.7 * amount, 0, 1), HAIR[colour], length=(3, 7), share=0.06, base=0.1, size=size)


def female_trail(m, rng, colour='brown', size=2048):
    """A faint line of fine hair from the navel down -- common, rarely painted."""
    P = Painter(m)
    L = landmarks(m)
    x = np.abs(P.p[..., 0])
    d = np.exp(-(x / 0.45) ** 2) * (P.n[..., 1] > 0.3) * P.reg('torso') * \
        np.clip((L['navel'] - 0.005 - P.h) / 0.01, 0, 1) * np.clip((P.h - L['crotch'] - 0.04) / 0.01, 0, 1)
    return hair(m, rng, np.clip(d * 0.5, 0, 1), HAIR[colour], length=(1, 3), share=0.12, base=0.08, size=size)
