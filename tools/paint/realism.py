"""The realism layer (C-13): skin detail, hair and nipple detail, painted on the body in 3D like marks.py.

Every painter returns (rgb, alpha) over the skin; make_marks.py turns that into a multiplier on the skin (C-12), so
"darker" and "lighter" here mean darker or lighter than the skin under it, whatever its tone.
"""
import numpy as np
from PIL import Image, ImageDraw

from marks import Painter, blank, fbm, over


def _front(P):
    return P.n[..., 1] > 0.15


def freckles(m, rng, amount=0.6):
    """Sun freckles: hundreds of small light-brown flecks on the shoulders, upper back, chest and arms."""
    P = Painter(m)
    rgb, alpha = blank(m)
    sun = np.where(P.reg('torso') & (P.h > 0.72), 1.0, 0.0) + np.where(P.reg('arm'), 0.8, 0.0)
    sun = sun * P.cov
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, sun > 0, int(300 + 1200 * amount), sun):
        P.blob_into(a, c, n, rng.uniform(0.05, 0.13), gain=rng.uniform(0.9, 1.6), cap=0.55)
    over(rgb, alpha, (0.55, 0.36, 0.24), a)
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
    where = (P.reg('torso') & (P.h > 0.66) & (P.h < 0.82) & _front(P)) \
        | (P.reg('arm') & (P.n[..., 1] > 0.0)) | (P.reg('leg') & (P.h > 0.3) & (P.h < 0.5))
    soft = np.clip(fbm(P.p, 0.25, seed + 9, 2) * 1.6 - 0.4, 0, 1)
    a = lines * soft * where * 0.5
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
        where = P.reg('torso', 'leg') & (h > 0.46) & (h < 0.62) & (np.abs(P.n[..., 0]) > 0.25)
    elif zone == 'belly':
        where = P.reg('torso') & (h > 0.55) & (h < 0.66) & (front > 0.2)
    elif zone == 'breasts':
        where = P.reg('torso') & (h > 0.70) & (h < 0.80) & (front > 0.3)
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


def pimples(m, rng, amount=0.5):
    """Pimples and their red bases, clustered on the back, shoulders, chest and buttocks."""
    P = Painter(m)
    rgb, alpha = blank(m)
    where = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) * P.cov
    red = np.zeros(m.covered.shape)
    head = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, where > 0, int(40 + 160 * amount), where):
        r = rng.uniform(0.12, 0.28)
        P.blob_into(red, c, n, r, gain=1.3, cap=0.55)
        if rng.random() < 0.4:
            P.blob_into(head, c, n, r * 0.3, gain=1.2, cap=0.5)
    over(rgb, alpha, (0.78, 0.30, 0.28), red)
    over(rgb, alpha, (0.92, 0.85, 0.70), head)
    return rgb, alpha


def nipples(m, rng, tone='brown', female=True):
    """Areola detail: a darker areola with a soft edge, Montgomery bumps, a darker tip; size varies."""
    P = Painter(m)
    rgb, alpha = blank(m)
    chest = P.reg('torso') & (P.h > 0.68) & (P.h < 0.92) & (P.n[..., 1] > 0.2)
    if not chest.any():
        return rgb, alpha
    colours = {'pink': (0.80, 0.50, 0.48), 'brown': (0.55, 0.36, 0.28), 'dark': (0.36, 0.23, 0.18)}
    col = np.array(colours[tone])
    size = rng.uniform(1.2, 2.2)
    a = np.zeros(m.covered.shape)
    tip = np.zeros(m.covered.shape)
    bumps = np.zeros(m.covered.shape)
    for side in (1, -1):
        half = chest & (P.p[..., 0] * side > 1.0)
        if not half.any():
            continue
        idx = np.flatnonzero(half)
        Pf = P.p.reshape(-1, 3)[idx]
        if female:
            # The breast's tip: the most forward point of that side.
            k = idx[np.argmax(Pf[:, 1])]
        else:
            # A man's chest is flat, but the mesh models the nipple as a small bump: the vertex that stands out
            # most from the skin around it (its forward offset over the mean of its neighbours within 2.5 units),
            # on that side of the chest. Neither "most forward" (the pec's underside) nor a fixed height (0.775: some
            # 40 cm low on the owner's screen, 2026-10-03) finds it.
            V = m.vertices
            hv = (V[:, 2] - m.bounds[0][2]) / (m.bounds[1][2] - m.bounds[0][2])
            cand = np.flatnonzero((V[:, 0] * side > 1.0) & (hv > 0.7) & (hv < 0.95) & (m.vertex_region == 0))
            C = V[cand]
            front = C[:, 1] > C[:, 1].max() - 3.0  # the front of the chest, not the ribcage's sides
            cand, C = cand[front], C[front]
            d2 = ((C[:, None, :] - C[None, :, :]) ** 2).sum(-1)
            near = d2 < 1.2 ** 2  # the bump is small: a wider ring averages it away
            mean_y = (near * C[None, :, 1]).sum(1) / near.sum(1)
            bump = C[:, 1] - mean_y
            peak = C[np.argsort(-bump)[:5]].mean(axis=0)  # the ring of bump vertices: its centre is the tip
            k = idx[np.argmin(((Pf - peak) ** 2).sum(-1))]
        c, n = P.p.reshape(-1, 3)[k], P.n.reshape(-1, 3)[k]
        P.blob_into(a, c, n, size * 0.55, gain=2.4, cap=0.85)
        P.blob_into(tip, c, n, size * 0.18, gain=2.0, cap=0.8)
        for _ in range(int(rng.integers(6, 14))):
            ang = rng.uniform(0, 2 * np.pi)
            t = np.cross(n, (0, 0, 1.0))
            t = t / (np.linalg.norm(t) or 1)
            b = np.cross(n, t)
            q = c + (t * np.cos(ang) + b * np.sin(ang)) * size * rng.uniform(0.6, 0.9)
            P.blob_into(bumps, q, n, 0.07, gain=1.5, cap=0.6)
    edge = 0.7 + 0.5 * fbm(P.p, 3.0, int(rng.integers(1 << 30)), 2)
    over(rgb, alpha, col, np.clip(a * edge, 0, 0.8))
    over(rgb, alpha, col * 0.75, bumps)
    over(rgb, alpha, col * 0.8, tip)
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
        d = ((uz > 1.0) & (uz < 6.0) & (np.abs(ux) < 0.55 * uz)).astype(float) * np.exp(-((uz - 3.5) / 3.0) ** 6)
    else:  # landing strip
        d = np.exp(-(ux / 0.75) ** 4) * np.exp(-((uz - 3.8) / 2.9) ** 6)
    return hair(m, rng, d * front, HAIR[colour], length=(2, 6), share=0.22, base=0.4, size=size)


def body_hair_male(m, rng, where='chest', colour='brown', size=2048):
    """Men's body hair: a chest (with a belly trail), or forearms and shins."""
    P = Painter(m)
    front = P.n[..., 1] > 0.1
    if where == 'chest':
        x, h = np.abs(P.p[..., 0]), P.h
        ragged = 0.6 + 0.6 * fbm(P.p, 0.7, int(rng.integers(1 << 30)), 3)
        pecs = np.exp(-(((x - 4.5) / 4.2) ** 2 + ((h - 0.775) / 0.05) ** 2) ** 2) * ragged
        sternum = np.exp(-((x / 2.0) ** 2 + ((h - 0.76) / 0.05) ** 2) ** 2)
        trail = np.exp(-(x / 0.7) ** 2) * np.clip((0.74 - h) / 0.04, 0, 1) * (h > 0.56)
        d = np.clip(np.maximum(np.maximum(pecs * 0.7, sternum * 0.45), trail * 0.5), 0, 1) * front * P.reg('torso')
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
    pits = P.reg('torso', 'arm') & (P.h > 0.80) & (P.h < 0.88) & (np.abs(P.n[..., 0]) > 0.5)
    where = np.where(legs, 0.6, 0.0) + np.where(pits, 1.0, 0.0)
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, where > 0, 2500, where):
        P.blob_into(a, c, n, 0.035, gain=1.5, cap=0.5)
    over(rgb, alpha, HAIR[colour], a)
    return rgb, alpha
