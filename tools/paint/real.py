"""Marks that read as real (alasdairn's full review, 2026-10-09: blood, grime and dirt "look more real"; the first
painters were soft gaussian blobs -- airbrush, not matter).

What real dried blood is, studied from decal textures in the installed Dried Blood pack (looked at, never copied):
a dense core with a CRISP ragged edge; droplets around it in every size (many tiny, few large), stretched along the
way they flew, some with a tail; fine streaks thrown out from the core; drips running DOWN from it, thin, uneven,
broken, ending in a bead; smears dragged by a hand, a sharp edge where the stroke began and streaky dry-brush
striations fading along it; thick blood darker than thin, the rim darker still where it dried first.

So these are painted as 2D stamps at high resolution (crisp shapes are cheap in 2D) and projected on the body at a
point, with image-down = world-down so drips run the way gravity runs (flash.project_rgba_at).
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
from scipy.spatial import cKDTree

import decals
import flash
import seams
from marks import Painter, blank, fbm, landmarks, over

THICK = np.array((0.24, 0.035, 0.03))   # dried blood where it pooled: near black red-brown
THIN = np.array((0.52, 0.14, 0.10))     # a thin film: lighter, redder


def _noise2(h, w, scale, rng, octaves=4):
    """Smooth 2D noise 0..1 (value noise, bilinear upsampled octaves)."""
    out = np.zeros((h, w))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        cells = max(int(scale * 2 ** o), 2)
        g = rng.random((cells + 1, int(cells * w / h) + 2))
        im = Image.fromarray(np.uint8(g * 255)).resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(im, np.float64) / 255.0
        norm += amp
        amp *= 0.5
    return out / norm


def _finish(thick, size, thick_col=THICK, thin_col=THIN):
    """thick (0..1 per pixel, 0 = none) -> RGBA: colour from thickness, a darker rim where it dried first."""
    mask = thick > 0.02
    dist = ndimage.distance_transform_edt(mask)
    rim = np.clip(1 - dist / max(size * 0.004, 1.5), 0, 1) * mask
    t = np.clip(thick, 0, 1)[..., None]
    col = np.asarray(thin_col) * (1 - t) + np.asarray(thick_col) * t
    col = col * (1 - 0.35 * rim[..., None])
    alpha = np.clip(0.45 + 0.5 * t[..., 0] + 0.15 * rim, 0, 0.95) * mask
    out = Image.fromarray(np.uint8(np.clip(col, 0, 1) * 255)).convert('RGBA')
    out.putalpha(Image.fromarray(np.uint8(alpha * 255)))
    out.info['prefilter'] = True
    return out


def splatter(rng, size=1400, drips=True, spread=1.0):
    """An impact: a ragged core, droplets flung out (biased one way), fine streaks, and drips running down."""
    H = W = size
    thick = np.zeros((H, W))
    cx, cy = W * 0.5, H * 0.32
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    # the core: a lumpy disc cut crisply out of noise
    r0 = size * rng.uniform(0.07, 0.11)
    d = np.sqrt((xx - cx) ** 2 + ((yy - cy) * 1.15) ** 2) / r0
    n = _noise2(H, W, 7, rng, 6)
    core = (1.0 - d + 1.5 * (n - 0.5)) > 0.0
    body = np.clip((1.0 - d) * 1.4 + 0.5 * (_noise2(H, W, 10, rng, 3) - 0.5), 0, 1)
    thick = np.maximum(thick, core * (0.55 + 0.45 * body))
    im = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(im)
    lean = rng.uniform(0, 2 * np.pi)                    # the way it was flung
    # droplets: power-law sizes, farther ones smaller and more stretched, a tail on the bigger far ones
    for _ in range(int(rng.integers(500, 900) * spread)):
        ang = lean + rng.normal(0, 1.1) if rng.random() < 0.7 else rng.uniform(0, 2 * np.pi)
        dist = r0 * (0.7 + rng.exponential(1.1) * spread)
        rad = min(size * 0.0007 * rng.pareto(1.8) + size * 0.0007, size * 0.009) * (1.5 - 0.7 * min(dist / (r0 * 5), 1))
        px, py = cx + np.cos(ang) * dist, cy + np.sin(ang) * dist
        if not (0 < px < W and 0 < py < H):
            continue
        stretch = 1 + min(dist / (r0 * 3), 2.5) * rng.uniform(0.3, 1.0)
        ux, uy = np.cos(ang), np.sin(ang)
        pts = [(px + ux * rad * stretch * np.cos(t) - uy * rad * np.sin(t),
                py + uy * rad * stretch * np.cos(t) + ux * rad * np.sin(t)) for t in np.linspace(0, 2 * np.pi, 14)]
        dr.polygon(pts, fill=int(rng.uniform(150, 255)))
        if rad > size * 0.004 and rng.random() < 0.5:
            tail = rad * stretch * rng.uniform(1.5, 4)
            dr.line([(px + ux * rad * stretch, py + uy * rad * stretch), (px + ux * (rad * stretch + tail), py + uy * (rad * stretch + tail))],
                    fill=180, width=max(1, int(rad * 0.5)))
    # fine streaks thrown from the core's edge
    for _ in range(int(rng.integers(6, 16) * spread)):
        ang = lean + rng.normal(0, 0.9)
        a0 = r0 * rng.uniform(0.8, 1.1)
        a1 = a0 + r0 * rng.uniform(0.3, 1.2)
        dr.line([(cx + np.cos(ang) * a0, cy + np.sin(ang) * a0), (cx + np.cos(ang) * a1, cy + np.sin(ang) * a1)],
                fill=140, width=max(1, int(size * rng.uniform(0.0007, 0.0015))))
    # drips: from the bottom of the core, down; thin, uneven, sometimes broken, a bead at the end
    if drips:
        for _ in range(int(rng.integers(3, 9))):
            x = cx + rng.uniform(-0.85, 0.85) * r0
            y = cy + r0 * rng.uniform(0.3, 0.8)
            w = size * rng.uniform(0.0022, 0.005)
            length = size * rng.uniform(0.12, 0.6)
            steps = int(length / 3)
            gap = rng.random() < 0.35
            for k in range(steps):
                t = k / steps
                x += rng.normal(0, 0.35)
                y += 3
                if gap and 0.55 < t < 0.6:
                    continue
                ww = w * (1 - 0.55 * t) * (0.8 + 0.4 * rng.random())
                dr.ellipse([x - ww, y - ww * 1.3, x + ww, y + ww * 1.3], fill=200)
            dr.ellipse([x - w * 1.1, y - w * 1.2, x + w * 1.1, y + w * 1.6], fill=235)
    thick = np.maximum(thick, np.asarray(im, np.float64) / 255.0 * 0.85)
    return _finish(thick, size)


def smear(rng, size=1400, thick_col=THICK, thin_col=THIN):
    """Blood dragged by a hand or a sleeve: a crisp ragged edge where the stroke began, dry-brush striations along
    it over a mottled film, thinning and breaking up toward the end."""
    H, W = int(size * 0.5), size
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    u = xx / W                                    # along the stroke
    v = (yy - H / 2) / (H / 2)                    # across it, -1..1
    curve = 0.2 * np.sin(u * np.pi * rng.uniform(0.6, 1.4) + rng.uniform(0, 3))
    edge = _noise2(H, W, 9, rng, 4)
    # inside the image with room to spare (a stroke as tall as the image was cut into a rectangle): a rounded press
    # where it began, swelling, then thinning out along the drag
    env = np.clip(u / 0.12, 0, 1) ** 0.5 * (1 - u) ** 0.6
    width = (0.12 + 0.5 * env) * (0.75 + 0.6 * (edge - 0.5)) + 0.03
    inside = np.abs(v - curve) < width
    stri = np.asarray(Image.fromarray(np.uint8(rng.random((int(H / 3), 16)) * 255)).resize((W, H), Image.BICUBIC), np.float64) / 255.0
    mottle = _noise2(H, W, 14, rng, 4)
    load = np.clip(1.05 - u * 1.3 + 0.5 * (_noise2(H, W, 4, rng, 3) - 0.5), 0, 1)    # the blood runs out along it
    film = 0.55 * stri + 0.45 * mottle
    thick = inside * np.clip((film - (1 - load)) * 2.0, 0, 1)
    lead = np.clip((u - 0.02 - 0.08 * ((v - curve) / 0.6) ** 2 - 0.05 * (edge - 0.5)) / 0.015, 0, 1)  # crisp, rounded, ragged
    thick = thick * lead * (0.75 + 0.25 * np.clip(1 - u * 3, 0, 1))
    thick[thick < 0.15] = 0
    return _finish(thick * 0.85, size, thick_col, thin_col)


def _hand_shape(rng, smeared, W=720, H=920):
    """A hand as it prints: a palm, four tapering fingers in proportion (the old shape's were sausages), a thumb
    angled off the side; the joints' and palm's creases print as gaps; dragged down when it slid."""
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    s = W / 720
    d.ellipse([170 * s, 430 * s, 560 * s, 800 * s], fill=255)                                # palm
    d.ellipse([175 * s, 445 * s, 555 * s, 640 * s], fill=255)                                # the knuckle line, rounded
    fingers = ((222, 500, 230, -0.14, 29), (302, 485, 275, -0.04, 31), (384, 488, 262, 0.04, 30), (460, 505, 205, 0.15, 26))
    for x0, y0, ln, tilt, w in fingers:
        for t in np.linspace(0, 1, 40):
            x, y = (x0 + np.sin(tilt) * ln * t) * s, (y0 - np.cos(tilt) * ln * t) * s
            r = w * (1 - 0.18 * t) * s
            d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    for t in np.linspace(0, 1, 30):                                                        # thumb
        x, y = (185 - 120 * t) * s, (650 - 120 * t - 60 * t * t) * s
        r = (40 - 8 * t) * s
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    def crease(pts, width):   # wavy, broken, thin: the skin's lines print as gaps
        q = np.array(pts, np.float64) * s
        line = []
        for k in range(len(q) - 1):
            for t in np.linspace(0, 1, 12, endpoint=False):
                line.append(q[k] * (1 - t) + q[k + 1] * t + rng.normal(0, 1.2 * s, 2))
        line.append(q[-1])
        for k in range(len(line) - 1):
            if rng.random() < 0.82:
                d.line([tuple(line[k]), tuple(line[k + 1])], fill=0, width=max(1, int(width * s)))
    for x0, y0, ln, tilt, w in fingers:                                                    # joint creases
        for t in (0.42, 0.72):
            x, y = x0 + np.sin(tilt) * ln * t, y0 - np.cos(tilt) * ln * t
            dx, dy = np.cos(tilt) * w * 1.05, np.sin(tilt) * w * 1.05
            crease(((x - dx, y - dy), (x, y + 3), (x + dx, y + dy)), 3.5)
    crease(((185, 585), (300, 610), (420, 600), (525, 570)), 4)                             # the palm's lines
    crease(((195, 655), (290, 662), (365, 700), (410, 745)), 4)
    crease(((290, 505), (300, 590), (285, 690), (262, 790)), 3.5)
    a = np.asarray(im, np.float64) / 255.0
    if smeared:
        out = a.copy()
        for y in range(int(700 * s), H):
            out[y] = np.maximum(out[y], out[y - 1] * 0.985)
        a = out
    return Image.fromarray(np.uint8(a * 255)).filter(ImageFilter.GaussianBlur(1.5))


def handprint(rng, smeared):
    """A bloody hand pressed on, as blood actually prints: heavy at the palm's heel and the finger pads, broken
    and skin-textured where less blood touched, dragged down when it slid."""
    shape = np.asarray(_hand_shape(rng, smeared), np.float64) / 255.0
    H, W = shape.shape
    press = _noise2(H, W, 10, rng, 5)
    pores = _noise2(H, W, 60, rng, 2)
    thick = np.clip((shape - 0.35) * 2.5, 0, 1) * np.clip(press * 1.6 - 0.25 + 0.35 * (pores - 0.5), 0, 1)
    thick[thick < 0.12] = 0
    return _finish(thick, 720)


def _spot_up(n):
    return np.array((0.0, 0.0, 1.0))


def dried_blood(m, rng, sources=(1, 2)):
    """Dried blood: an impact's splatter with its drips, sometimes a smear dragged through it, on the chest, back,
    shoulders or arms -- crisp 2D stamps (splatter, smear) projected with image-down = world-down."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.55), 1.0, 0.0) + np.where(P.reg('arm'), 0.4, 0.0)
    for c, n in P.pick_points(rng, weight > 0, int(rng.integers(sources[0], sources[1] + 1)), weight):
        r, a = flash.project_rgba_at(m, splatter(rng), c, n, width=float(rng.uniform(9, 15)),
                                     rotate=float(rng.uniform(-0.25, 0.25)), alpha=1.0)
        over(rgb, alpha, r, a)
        if rng.random() < 0.45:
            off = c + rng.normal(0, 1.5, 3) * np.array((1.0, 0.3, 1.0))
            r, a = flash.project_rgba_at(m, smear(rng), off, n, width=float(rng.uniform(5, 8)),
                                         rotate=float(rng.uniform(-0.8, 0.8)) + (np.pi if rng.random() < 0.5 else 0), alpha=0.9)
            over(rgb, alpha, r, a)
    return rgb, alpha


def bloody_hands(m, rng, spots=(('chest', 1), ('belly', 0))):
    """Dried blood handprints, some dragged, as the Disciples wear them."""
    rgb, alpha = blank(m)
    for spot_, side in spots:
        c, n, up = decals.anchor(m, spot_, side)
        r, a = flash.project_rgba_at(m, handprint(rng, rng.random() < 0.6), c, n, up, width=float(rng.uniform(4.4, 5.2)),
                                     rotate=float(rng.uniform(-0.5, 0.5)), alpha=1.0)
        over(rgb, alpha, r, a)
    return rgb, alpha


# ---------------------------------------------------------------- dirt

DIRT = np.array((0.47, 0.40, 0.33))       # a film of dust on skin: greyed brown
GRIT = np.array((0.27, 0.23, 0.19))       # the particles themselves


def creases(m):
    """Per texel 0..1: how much the skin folds in there (armpits, elbows' insides, behind the knees, under the
    breasts and buttocks, the groin), from the mesh: a vertex lying below the mean of its neighbours."""
    if hasattr(m, '_creases'):
        return m._creases
    V, T = m.vertices, m.triangles
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, T[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    acc = np.zeros_like(V)
    cnt = np.zeros(len(V))
    for i, j in ((0, 1), (1, 2), (2, 0), (1, 0), (2, 1), (0, 2)):
        np.add.at(acc, T[:, i], V[T[:, j]])
        np.add.at(cnt, T[:, i], 1)
    lap = acc / np.maximum(cnt, 1)[:, None] - V
    concave = (lap * vn).sum(1)                      # > 0: the neighbours stand out above it, a fold
    # smooth it over the surface: the mean over the 24 nearest vertices
    tree = cKDTree(V)
    _, nb = tree.query(V, k=24)
    concave = concave[nb].mean(1)
    scale = np.percentile(np.abs(concave), 97) or 1.0
    vval = np.clip(concave / scale, 0, 1)
    idx = np.flatnonzero(m.covered)
    _, near = tree.query(m.position.reshape(-1, 3)[idx], k=3)
    out = np.zeros(m.covered.shape)
    out.reshape(-1)[idx] = vval[near].mean(1)
    m._creases = out
    return out


def grime(m, rng, amount=0.5, legs_only=False):
    """Ground-in dirt as it is: a film of dust that is grainy, not smooth -- particles at pore scale, patchy at hand
    scale -- worst where the body meets the ground and its work (feet, shins, knees, hands' forearms, elbows),
    packed into the folds, run into streaks where sweat ran down, wiped into smudges by hands; faded out well before
    the neck and wrists, since the head and hands beside it are clean."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    h = P.h
    L = landmarks(m)
    low = np.clip((0.40 - h) / 0.36, 0, 1) ** 0.8                      # 1 at the feet, gone above the thighs
    knee = np.exp(-((h - 0.28) / 0.05) ** 2) * (P.n[..., 1] > 0.2) * P.reg('leg')
    arm_out = np.abs(P.p[..., 0]) / max(np.abs(P.p[..., 0][P.reg('arm')]).max(), 1e-6)
    fore = np.clip((arm_out - 0.45) / 0.3, 0, 1) * P.reg('arm')
    expose = low + 0.6 * knee + 0.75 * fore
    if not legs_only:
        expose = expose + 0.35 + 0.25 * fbm(P.p, 0.15, seed + 9, 2)       # some everywhere on someone this dirty
    expose = expose + 0.9 * creases(m)
    patch = fbm(P.p, 0.45, seed, 4)                                   # hand-sized patches
    grain = fbm(P.p, 5.0, seed + 1, 3)                                # skin-texture scale: where dust settles
    speck = fbm(P.p, 9.0, seed + 2, 3)                                # grit: clustered, uneven sizes
    runs = fbm(P.p * np.array((1.0, 1.0, 0.18)), 0.9, seed + 3, 3)    # streaks run down
    level = 0.75 - 0.35 * amount
    film = np.clip((patch * 0.7 + runs * 0.3 - level + 0.35 * expose - 0.3) * 2.6, 0, 1) * np.clip(expose, 0, 1.4)
    film = film * np.clip(0.35 + 1.1 * (grain - 0.25), 0.2, 1.2)     # a film is never even: it lies in the grain
    parts = np.clip((speck + 0.35 * film - (0.80 - 0.10 * amount)) * 6, 0, 1) * np.clip(expose * film * 3, 0, 1)
    fade = seams.seam_fade(m, 1.0, 9.0)
    a_film = np.clip(film * (0.35 + 0.45 * amount), 0, 0.75) * fade * P.cov
    a_part = np.clip(parts * 0.7, 0, 0.7) * fade * P.cov
    over(rgb, alpha, DIRT * (0.9 + 0.2 * grain[..., None]), a_film)
    over(rgb, alpha, GRIT, a_part)
    # smudges: dirty hands wiped on the thighs and forearms (on the belly they read as stains, 10-09)
    if not legs_only:
        where = P.reg('leg') * (P.n[..., 1] > 0.3) * (h > 0.3) * (h < L['crotch'] - 0.04) + fore * 0.6   # wiped on thighs, forearms
        for c, n in P.pick_points(rng, where > 0, int(1 + 3 * amount), where):
            r, a = flash.project_rgba_at(m, smear(rng, 900, GRIT, DIRT), c, n, width=float(rng.uniform(8, 12)),
                                         rotate=float(rng.uniform(-1.2, 1.2)) + np.pi / 2, alpha=0.3 + 0.2 * amount)
            over(rgb, alpha, r, a * fade)
    return rgb, alpha


MUD = np.array((0.36, 0.28, 0.20))
MUD_DRY = np.array((0.50, 0.44, 0.37))


def mud(m, rng, amount=0.6):
    """Mud on the legs as it dries: caked on the feet and shins with a crisp, lumpy edge, lighter where it dried and
    cracked, splashed above in sharp drops thrown up from the ground."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seed = int(rng.integers(1 << 30))
    legs = P.reg('leg', 'foot')
    low = np.clip((0.30 - P.h) / 0.26, 0, 1) * legs
    lump = fbm(P.p, 0.8, seed, 5)
    caked = ((lump + 0.9 * low - (1.05 - 0.25 * amount)) > 0) * legs
    caked = caked * np.clip((lump + 0.9 * low - (1.05 - 0.25 * amount)) * 30, 0, 1)   # crisp edge, a texel of soft
    crack = np.abs(fbm(P.p, 2.2, seed + 1, 3) - 0.5) < 0.025
    dry = np.clip((fbm(P.p, 1.4, seed + 2, 3) - 0.45) * 3, 0, 1)
    col = MUD * (1 - 0.6 * dry[..., None]) + MUD_DRY * 0.6 * dry[..., None]
    col = np.where(crack[..., None], MUD * 0.7, col)
    over(rgb, alpha, col, np.clip(caked * 0.88, 0, 0.88) * P.cov)
    # splashes: crisp drops, more and bigger near the ground
    drops = np.zeros(m.covered.shape)
    up = P.reg('leg') & (P.h < 0.48)
    for c, n in P.pick_points(rng, up, int(120 + 260 * amount), np.clip(0.5 - P.h, 0, None) ** 2 * up):
        rad = min(0.05 + 0.06 * rng.pareto(2.0), 0.35)
        idx = P.near(c, rad * 3)
        if not len(idx):
            continue
        q = P.p.reshape(-1, 3)[idx] - c
        stretch = q[:, 2] * 0.45                                       # thrown up: longer upward
        d = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2 + (q[:, 2] - stretch) ** 2)
        v = np.clip((rad - d) / 0.03, 0, 1) * (P.n.reshape(-1, 3)[idx] @ n > 0.3)
        flat = drops.reshape(-1)
        flat[idx] = np.maximum(flat[idx], v)
    over(rgb, alpha, MUD * 0.95, np.clip(drops * 0.85, 0, 0.85) * P.cov)
    return rgb, alpha


# ---------------------------------------------------------------- bruises and redness
# The first shading stepped through three colours on thresholds of the bruise's depth: rings, like a target
# (alasdairn: "add more detail to all"). A bruise is blood under the skin: its colour shifts continuously with depth
# and age, its edge is broken up by the tissue, it is mottled, and burst capillaries speckle it.

# alasdairn (10-09): "too purple, add more red, make them all lighter"
FRESH_RAMP = ((0.0, (0.86, 0.54, 0.52)), (0.30, (0.76, 0.38, 0.38)), (0.60, (0.62, 0.26, 0.31)), (1.0, (0.48, 0.18, 0.26)))
OLD_RAMP = ((0.0, (0.84, 0.76, 0.50)), (0.30, (0.74, 0.68, 0.44)), (0.60, (0.62, 0.46, 0.38)), (1.0, (0.52, 0.32, 0.34)))


def _ramp(t, stops):
    xs = [x for x, _ in stops]
    return np.stack([np.interp(t, xs, [c[k] for _, c in stops]) for k in range(3)], -1)


def contusion(P, rgb, alpha, a, rng, age='fresh', strength=0.85):
    """Shades an intensity field a (0..1: where and how deep the bruise is) as a bruise."""
    seed = int(rng.integers(1 << 30))
    warp = fbm(P.p, 0.8, seed, 3)
    mott = fbm(P.p, 2.4, seed + 1, 3)
    fine = fbm(P.p, 8.0, seed + 2, 2)
    t = np.clip(a * (0.65 + 0.7 * warp) + 0.25 * (mott - 0.5), 0, 1)        # the edge broken up, no rings
    stops = FRESH_RAMP if age == 'fresh' else OLD_RAMP
    colour = _ramp(t, stops) * (0.92 + 0.16 * mott[..., None])
    # no airbrushed falloff (alasdairn): the outline is cut crisply at a threshold the noise moves, and the inside
    # breaks into blotches at a second one
    edge = np.clip((t - (0.18 + 0.22 * (warp - 0.5))) * 9, 0, 1)
    blot = np.clip((t + 0.35 * (mott - 0.5) - 0.45) * 6, 0, 1)
    alp = np.clip(edge * (0.42 + 0.48 * blot) * strength * (0.62 + 0.5 * fine), 0, 0.9) * (a > 0.02)
    over(rgb, alpha, colour, alp * P.cov)
    if age == 'fresh':   # petechiae: tiny burst capillaries where it is mid-deep
        pet = (fbm(P.p, 16.0, seed + 3, 1) > 0.80) * np.clip((t - 0.2) * 3, 0, 1) * np.clip((0.85 - t) * 4, 0, 1)
        over(rgb, alpha, (0.60, 0.16, 0.16), np.clip(pet * 0.5, 0, 0.5) * P.cov)


def _lumpy(P, out, c, n, r, rng):
    """An irregular bruise shape: a few overlapping blobs around c, not one disc."""
    t = np.cross(n, (0.0, 0.0, 1.0))
    t = t / (np.linalg.norm(t) or 1)
    b = np.cross(n, t)
    for _ in range(int(rng.integers(3, 6))):
        q = c + (t * rng.normal(0, 0.35) + b * rng.normal(0, 0.35)) * r
        P.blob_into(out, q, n, r * rng.uniform(0.45, 0.8), gain=rng.uniform(0.8, 1.2), cap=1.0)


def bruises(m, rng, count=(2, 4), age='fresh'):
    """Bruises on ribs, flanks, upper arms, thighs and shins: irregular, mottled, deeper at the core."""
    P = Painter(m)
    rgb, alpha = blank(m)
    torso = P.reg('torso') & (P.h > 0.5) & (P.h < 0.85)
    weight = np.where(torso, 1.0, 0.0) + np.where(P.reg('arm') & (P.h > 0.7), 0.7, 0.0) \
        + np.where(P.reg('leg') & (P.h > 0.15), 0.9, 0.0)
    a = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, weight > 0, int(rng.integers(count[0], count[1] + 1)), weight):
        _lumpy(P, a, c, n, rng.uniform(2.0, 4.0), rng)
    contusion(P, rgb, alpha, a, rng, age, 0.62 if age == 'fresh' else 0.55)
    return rgb, alpha


def grip_bruises(m, rng, where='arms'):
    """Finger-shaped bruises where someone held on hard (life.grip_bruises' fingers and thumb), shaded as bruises."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    a = np.zeros(m.covered.shape)
    tw = life.torso_width(P)
    for side in (1, -1):
        if where == 'arms':
            c, n, _ = decals.anchor(m, 'upper_arm', side)
            idx = P.near(c, 6)
            Q = P.p.reshape(-1, 3)[idx]
            Nn = P.n.reshape(-1, 3)[idx]
            k = idx[np.argmin(((Q - (c - n * 3.0)) ** 2).sum(-1) + 10 * np.clip(Nn @ n + 0.5, 0, None))]
            thumb = (P.p.reshape(-1, 3)[k], P.n.reshape(-1, 3)[k])
            life._finger_bruises(P, a, c, n, np.array((0.0, 0.0, 1.0)) if abs(n[2]) < 0.8 else np.array((0.0, 1.0, 0.0)),
                                 rng, thumb=thumb)
        else:
            ch = life.crotch_h(P)
            c, n = life.spot(P, P.reg('torso', 'leg'), side * 0.8 * tw, ch + 0.06, 0.25)
            t_c, t_n = life.spot(P, P.reg('torso'), side * 0.25 * tw, ch + 0.1, -0.5)
            life._finger_bruises(P, a, c, n, np.array((0.0, 0.0, 1.0)), rng, thumb=(t_c, t_n))
    # fingertips press unevenly: break the round prints up at their own scale, or they read as polka dots
    a = a * np.clip(0.45 + 0.9 * fbm(P.p, 3.2, int(rng.integers(1 << 30)), 3), 0, 1.2)
    contusion(P, rgb, alpha, np.clip(a * 1.2, 0, 1), rng, 'fresh', 0.62)
    return rgb, alpha


def bites(m, rng, places=('shoulder',)):
    """Human bite marks (life._bite's two arcs of tooth dents): each dent a crisp dark-red crescent of broken
    skin, a suction bruise around and inside them."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    dent = np.zeros(m.covered.shape)
    bruise = np.zeros(m.covered.shape)
    ch = life.crotch_h(P)
    tw = life.torso_width(P)
    L = landmarks(m)
    for place in places:
        side = 1 if rng.random() < 0.5 else -1
        if place == 'breast':
            tip = L['nipples'][side]
            c, n = life.spot(P, P.reg('torso'), tip[0] - side * 2.5, L['nipple'] + 0.03, 0.4)
        elif place == 'inner_thigh':
            c, n, _ = decals.anchor(m, 'inner_thigh', side)
        elif place == 'butt':
            c, n = life.spot(P, P.reg('torso', 'leg'), side * 0.45 * tw, ch + 0.06, -0.4)
        elif place == 'neck':
            c, n = life.spot(P, P.reg('torso', 'head'), side * 0.3 * tw, L['top'] - 0.035, 0.0)
        else:
            c, n, _ = decals.anchor(m, 'shoulder', side)
        life._bite(P, dent, bruise, c, n, rng, rng.uniform(0.9, 1.1))
    contusion(P, rgb, alpha, np.clip(bruise * 1.3, 0, 1), rng, 'fresh', 0.5)
    seed = int(rng.integers(1 << 30))
    crisp = np.clip((dent - 0.35) * 4, 0, 1) * (0.75 + 0.35 * fbm(P.p, 10.0, seed, 2))
    over(rgb, alpha, (0.52, 0.13, 0.14), np.clip(crisp * 0.75, 0, 0.75) * P.cov)
    over(rgb, alpha, (0.62, 0.20, 0.26), np.clip((dent - crisp) * 0.6, 0, 0.5) * P.cov)   # the swollen rim
    return rgb, alpha


def redness(P, rgb, alpha, a, rng, light=(0.86, 0.48, 0.46), deep=(0.66, 0.20, 0.24), strength=0.6, specks=True, grain=0.55,
            soft=False):
    """Shades a field a as reddened skin: blotchy, deeper where stronger, fine-grained, speckled where hot."""
    seed = int(rng.integers(1 << 30))
    mott = fbm(P.p, 1.6, seed, 3)
    fine = fbm(P.p, 9.0, seed + 1, 2)
    t = np.clip(a * (0.6 + 0.8 * mott), 0, 1)
    colour = np.asarray(light) * (1 - t[..., None]) + np.asarray(deep) * t[..., None]
    edge = np.clip((t - (0.2 + 0.25 * (mott - 0.5))) * 7, 0, 1)             # crisp, ragged blotches, no glow
    if soft:   # a margin that blends into the skin round a crisp core (alasdairn on the restraint marks, 10-10)
        edge = np.clip(t * 2.0, 0, 1)
    over(rgb, alpha, colour, np.clip(edge * (0.45 + 0.55 * t) * strength * (1.0 - grain * 0.73 + grain * fine), 0, 0.8) * P.cov)
    if specks:
        sp = (fbm(P.p, 14.0, seed + 2, 1) > 0.78) * np.clip((t - 0.35) * 2.5, 0, 1)
        over(rgb, alpha, np.asarray(deep) * 0.85, np.clip(sp * 0.55, 0, 0.55) * P.cov)


def spank(m, rng, sides=('l', 'r')):
    """A reddened buttock with a handprint in it: the hand (_hand_shape -- the old one's fingers were boxes)
    projected on the cheek, deeper red, the skin around it blotchy and hot."""
    P = Painter(m)
    rgb, alpha = blank(m)
    seat = P.reg('torso', 'leg') & (P.n[..., 1] < -0.2) & (P.h > 0.47) & (P.h < 0.63)
    if not seat.any():
        return rgb, alpha
    field = np.zeros(m.covered.shape)
    for side in sides:
        half = seat & ((P.p[..., 0] > 1.5) if side == 'l' else (P.p[..., 0] < -1.5))
        if not half.any():
            continue
        target = P.p[half].mean(axis=0) + np.array((0.0, 0.0, rng.uniform(0.5, 2.0)))
        flat = np.flatnonzero(half)
        k = flat[np.argmin(((P.p.reshape(-1, 3)[flat] - target) ** 2).sum(-1))]
        c, n = P.p.reshape(-1, 3)[k], P.n.reshape(-1, 3)[k]
        flush_ = np.exp(-(((P.p[..., 0] - c[0]) / 5.0) ** 2 + ((P.p[..., 2] - c[2]) / 4.0) ** 2)) * half
        field = np.maximum(field, flush_ * rng.uniform(0.3, 0.4))
        hand = _hand_shape(rng, False)
        if side == 'r':
            hand = hand.transpose(Image.FLIP_LEFT_RIGHT)
        stamp = Image.new('RGBA', hand.size, (255, 255, 255, 0))
        stamp.putalpha(hand)
        stamp.info['prefilter'] = True
        _, a = flash.project_rgba_at(m, stamp, c, n, width=float(rng.uniform(8.0, 9.0)),
                                     rotate=float(rng.uniform(-0.6, 0.6)), alpha=1.0)
        field = np.maximum(field, a)
    # alasdairn (10-09): "smoothed out and lightened"
    redness(P, rgb, alpha, np.clip(ndimage.gaussian_filter(field, 1.5), 0, 1), rng, light=(0.88, 0.56, 0.52),
            deep=(0.76, 0.32, 0.32), strength=0.5, specks=False, grain=0.15)
    return rgb, alpha


def flush(m, rng, zone='chest'):
    """Blotchy redness (skin.flush's zones): uneven patches with fine heat speckle."""
    import skin
    P = Painter(m)
    rgb, alpha = blank(m)
    _, a = skin.flush(m, rng, zone)
    redness(P, rgb, alpha, np.clip(a / max(a.max(), 1e-6), 0, 1), rng, strength=0.5)
    return rgb, alpha


def sunburn(m, rng, severity=1.0, peeling=True):
    """Sunburn on what faced the sky (life.sunburn's zones): hot red, blotchy and grainy, freckled with heat
    rash; peeling in flakes with crisp curled edges where it is worst."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    _, a = life.sunburn(m, rng, severity, False)
    a = np.clip(a / max(a.max(), 1e-6), 0, 1) * seams.seam_fade(m, 1.0, 9.0)   # the face above is not burnt
    redness(P, rgb, alpha, a, rng, light=(0.88, 0.52, 0.46), deep=(0.74, 0.26, 0.24), strength=0.45 * severity + 0.1,
            specks=False)
    if peeling:   # sheets of dead skin lifting where it burnt worst, each with a darker curled rim
        seed = int(rng.integers(1 << 30))
        flakes = fbm(P.p, 1.3, seed, 4) + 0.12 * (fbm(P.p, 6.0, seed + 1, 2) - 0.5)
        level = 0.64 - 0.06 * severity
        sheet = np.clip((flakes - level) * 25, 0, 1) * (a > 0.5)
        rim = np.clip((flakes - (level - 0.025)) * 25, 0, 1) * (a > 0.5) - sheet
        over(rgb, alpha, (0.95, 0.86, 0.80), np.clip(sheet * 0.6, 0, 0.6) * P.cov)
        over(rgb, alpha, (0.60, 0.30, 0.26), np.clip(rim * 0.65, 0, 0.65) * P.cov)
    return rgb, alpha


def port_wine(m, rng, size=4.0):
    """A port-wine stain: a flat patch with a map-like coastline (bays, peninsulas, islands off it), pink-red at
    the margins to deep wine-purple inside, and the fine grain of the vessels in it."""
    P = Painter(m)
    rgb, alpha = blank(m)
    import skin
    w = skin._zone(P, m, 'everywhere')
    (c, n), = P.pick_points(rng, w > 0, 1, w)
    seed = int(rng.integers(1 << 30))
    reach = np.zeros(m.covered.shape)
    P.blob_into(reach, c, n, size, gain=1.6, cap=1.0)
    coast = fbm(P.p, 0.55, seed, 5) * 0.7 + fbm(P.p, 1.8, seed + 1, 3) * 0.3
    land = reach * (0.45 + 1.1 * coast)
    shape = np.clip((land - 0.55) * 14, 0, 1)                             # a crisp, ragged coastline
    deep = np.clip((land - 0.75) * 2.5, 0, 1)
    grain = fbm(P.p, 11.0, seed + 2, 2)
    colour = np.array((0.80, 0.42, 0.46)) * (1 - deep[..., None]) + np.array((0.62, 0.24, 0.32)) * deep[..., None]   # lighter (10-09)
    colour = colour * (0.9 + 0.2 * grain[..., None])
    over(rgb, alpha, colour, np.clip(shape * (0.42 + 0.18 * deep) * (0.85 + 0.25 * grain), 0, 0.65) * P.cov)
    return rgb, alpha


# ---------------------------------------------------------------- scars and cuts
# The first scars were smooth gaussian tubes, pale pink on a soft pink rim: airbrushed. alasdairn (10-09): "add more
# detail ... darken red colours on scars". A scar's edge is crisp and uneven, its surface textured (collagen laid
# down in fibres), it stands up or sinks (light on one side, shadow on the other), and its rim is a darker, duller
# red than first painted. Every scar painter builds the same two fields (a pale core, a wider rim) and calls this.

# alasdairn (10-10) rejected those too -- "still airbrushed pink lines" -- and named the radiation sores (passed) as the
# model for every scar: built the same way, a lesion cut out of noise with a crisp irregular edge, a darker crisp rim
# band, patchy tones inside, fine texture, inflamed skin round it.

SCAR_AGES = {
    # age: (core tones pale -> dark, rim, surround)
    'old': (((0.0, (0.42, 0.20, 0.18)), (0.25, (0.56, 0.27, 0.26)), (0.45, (0.78, 0.48, 0.46)), (0.72, (0.86, 0.66, 0.62)), (1.0, (0.88, 0.70, 0.66))),
            (0.45, 0.17, 0.17), (0.84, 0.54, 0.50)),
    'newer': (((0.0, (0.40, 0.13, 0.15)), (0.25, (0.50, 0.17, 0.19)), (0.55, (0.70, 0.30, 0.32)), (1.0, (0.80, 0.44, 0.44))),
              (0.46, 0.12, 0.14), (0.80, 0.40, 0.40)),
    'fresh': (((0.0, (0.26, 0.04, 0.05)), (0.55, (0.36, 0.07, 0.08)), (1.0, (0.50, 0.12, 0.12))),
              (0.58, 0.14, 0.16), (0.78, 0.36, 0.36)),
    # healed scars with purple and red through them (alasdairn's experiment, 10-10)
    'old_pr': (((0.0, (0.38, 0.13, 0.20)), (0.30, (0.55, 0.17, 0.23)), (0.55, (0.68, 0.28, 0.30)), (0.80, (0.76, 0.48, 0.46)), (1.0, (0.78, 0.55, 0.52))),
               (0.42, 0.11, 0.16), (0.74, 0.38, 0.38)),   # a smidge darker, then more red and less pink (10-10)
    # alasdairn on the whip marks (10-10): fresh welts soft pink and white, glossy, no yellow; healed ones less red,
    # soft white and see-through, "as if the scar tissue has returned to normal colours"
    'welt': (((0.0, (0.60, 0.26, 0.28)), (0.45, (0.74, 0.44, 0.44)), (1.0, (0.84, 0.70, 0.68))),       # dimmer (10-10)
             (0.60, 0.24, 0.26), (0.76, 0.46, 0.44)),
    'healed_soft': (((0.0, (0.66, 0.30, 0.34)), (0.35, (0.80, 0.58, 0.56)), (0.7, (0.86, 0.68, 0.64)), (1.0, (0.90, 0.76, 0.72))),
                    (0.62, 0.22, 0.26), (0.86, 0.66, 0.62)),   # less white, a dash of crimson (10-10)
}


def _tex_noise(shape, seed, scale, octaves=3):
    """Noise in texture space (for shading detail; a UV seam inside a scar is too rare to matter)."""
    return _noise2(shape[0], shape[1], scale, np.random.default_rng(seed), octaves)


def scar_shade(rgb, alpha, a_pale, a_rim=None, age='old', opacity=1.0):
    """Shades a scar from its fields: a_pale (the scar itself) and a_rim (a wider halo; blurred from a_pale when
    None) -- as a lesion, the way rad_sores is built."""
    if not a_pale.any():
        return
    seed = int(a_pale.sum() * 1000) % (1 << 30)
    if a_rim is None:
        a_rim = ndimage.gaussian_filter(a_pale, 3)
    size = a_pale.shape[0]
    # widen the thin line a little, then cut it out of noise: a ragged lesion along the scar's path, not a tube
    spread = ndimage.gaussian_filter(a_pale, 1.6)
    field = np.maximum(a_pale, spread / max(spread.max(), 1e-6) * 1.25)
    edge_n = _tex_noise(a_pale.shape, seed, size / 10, 3)
    tone_n = _tex_noise(a_pale.shape, seed + 1, size / 22, 3)
    fine = _tex_noise(a_pale.shape, seed + 2, size / 4, 2)
    irr = field * (0.5 + 1.0 * edge_n)
    core = np.clip((irr - 0.42) * 7, 0, 1)                                 # blended into the skin (alasdairn, 10-10)
    rim = np.clip((irr - 0.24) * 5, 0, 1) - core
    sur = np.clip((ndimage.gaussian_filter(a_rim, 2) * (0.4 + 1.2 * tone_n) - 0.25) * 6, 0, 1) * (1 - core)
    tones, rim_c, sur_c = SCAR_AGES[age]
    colour = _ramp(np.clip(tone_n * 1.3 - 0.15, 0, 1), tones) * (0.9 + 0.2 * fine[..., None])
    sm = ndimage.gaussian_filter(core, 1.0)
    gy, gx = np.gradient(sm)
    relief = -(gx + gy) * 5.0
    sur = ndimage.gaussian_filter(sur, 2.0)
    k = opacity
    over(rgb, alpha, sur_c, np.clip(sur * 0.4 * (0.7 + 0.5 * fine), 0, 0.45) * k)
    over(rgb, alpha, rim_c, np.clip(rim * 0.65 * (0.8 + 0.3 * fine), 0, 0.7) * k)
    over(rgb, alpha, colour, np.clip(core * 0.85, 0, 0.88) * k)
    over(rgb, alpha, np.asarray(rim_c) * 0.9, np.clip(-relief * 0.6, 0, 0.5) * k)
    if age == 'old_pr':   # a dark overlay on the scar only (alasdairn's pick, 10-10)
        over(rgb, alpha, (0.34, 0.14, 0.16), np.clip(core * 0.32, 0, 0.32) * k)
    if age == 'welt':   # glossy: a wet sheen along the top of the welt
        over(rgb, alpha, (0.90, 0.82, 0.80), np.clip(relief * 0.8, 0, 0.45) * core * k)
    elif age != 'fresh':
        over(rgb, alpha, (0.92, 0.80, 0.76), np.clip(relief * 0.35, 0, 0.3) * core * k)
    else:   # a crusted cut: dried blood and yellow crust along it
        crust = (_tex_noise(a_pale.shape, seed + 3, size / 6, 2) > 0.6) * core
        over(rgb, alpha, (0.70, 0.56, 0.30), np.clip(crust * 0.6, 0, 0.6))


def lashes(m, rng, count=(4, 8), healed=False):
    """Whip marks across the back (marks.lashes' strokes): fresh, a crusted split along a swollen red welt;
    healed, pale raised lines with a darker rim."""
    P = Painter(m)
    rgb, alpha = blank(m)
    back = P.reg('torso') & (P.n[..., 1] < -0.15) & (P.h > 0.55) & (P.h < 0.9)
    if not back.any():
        return rgb, alpha
    pts = P.p[back]
    cx, cz = pts[:, 0].mean(), pts[:, 2].mean()
    zr = (pts[:, 2].max() - pts[:, 2].min()) / 2
    line_a = np.zeros(m.covered.shape)
    halo_a = np.zeros(m.covered.shape)
    strokes = int(rng.integers(count[0], count[1] + 1))
    extra = int(rng.integers(3, 6)) if healed and m.sex == 'female' else 0   # more across a woman's upper back (10-10)
    for k in range(strokes + extra):
        ang = rng.uniform(-0.6, 0.6) + (np.pi if rng.random() < 0.5 else 0)
        dx, dz = np.cos(ang), np.sin(ang)
        z0 = cz + (rng.uniform(0.15, 0.85) if k >= strokes else rng.uniform(-0.85, 0.85)) * zr
        x0 = cx + rng.uniform(-6, 6)
        dist = np.abs((P.p[..., 0] - x0) * dz - (P.p[..., 2] - z0) * dx)
        along = (P.p[..., 0] - x0) * dx + (P.p[..., 2] - z0) * dz
        half = rng.uniform(7, 14)
        width = rng.uniform(0.11, 0.19) if not healed else rng.uniform(0.07, 0.13)   # both slimmer (alasdairn, 10-10)
        taper = np.clip(1 - (np.abs(along) / half) ** 4, 0, 1)
        wiggle = 0.35 * (fbm(P.p, 0.6, int(rng.integers(1 << 30)), 3) - 0.5)
        broken = np.clip(0.5 + 0.8 * fbm(P.p, 0.9, int(rng.integers(1 << 30)), 3), 0, 1)
        line_a = np.maximum(line_a, np.exp(-((dist + wiggle) / width) ** 2) * taper * back * broken)
        halo_a = np.maximum(halo_a, np.exp(-((dist + wiggle) / (width * 2.8)) ** 2) * taper * back)
    if healed:
        scar_shade(rgb, alpha, line_a, halo_a, 'healed_soft', opacity=0.6)
    else:
        scar_shade(rgb, alpha, line_a, halo_a, 'welt')
        over(rgb, alpha, (0.42, 0.22, 0.22), np.clip(np.maximum(line_a, halo_a * 0.6) * 0.28, 0, 0.28) * P.cov)   # a dark tone over it all (10-10)
    return rgb, alpha


def burn_scar(m, rng):
    """An old burn scar: a large patch of tight, shiny, grafted-looking skin -- pale and pink islands with crisp
    edges, brown hyperpigmented patches between them, ropey ridges where it contracted, a darker red margin."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm', 'leg') & (P.h > 0.2), 0.8, 0.0)
    (c, n), = P.pick_points(rng, weight > 0, 1, weight)
    patch = np.zeros(m.covered.shape)
    P.blob_into(patch, c, n, rng.uniform(2.5, 4.0), gain=1.6, cap=1.0)
    seed = int(rng.integers(1 << 30))
    land = patch * (0.55 + 0.9 * fbm(P.p, 0.8, seed, 5))
    shape = np.clip((land - 0.38) * 12, 0, 1)                                   # crisp outline
    margin = np.clip((land - 0.30) * 6, 0, 1) - shape
    mix = fbm(P.p, 1.1, seed + 1, 4)
    ridge = np.clip(1 - np.abs(fbm(P.p * np.array((1.0, 1.0, 0.5)), 1.1, seed + 2, 3) - 0.5) / 0.05, 0, 1)
    fine = fbm(P.p, 9.0, seed + 3, 2)
    over(rgb, alpha, (0.50, 0.16, 0.16), np.clip(margin * 0.6, 0, 0.6) * P.cov)
    # pale and pink grafted skin flowing into brown patches -- a continuous ramp (a hard switch read as camouflage)
    # darker browns in the mix (alasdairn, 10-10)
    ramp = ((0.0, (0.38, 0.24, 0.18)), (0.22, (0.48, 0.31, 0.24)), (0.38, (0.64, 0.42, 0.37)), (0.52, (0.78, 0.52, 0.50)), (0.68, (0.86, 0.66, 0.62)), (1.0, (0.88, 0.70, 0.66)))
    colour = _ramp(mix, ramp) * (0.94 + 0.1 * fine[..., None])
    over(rgb, alpha, colour, np.clip(shape * 0.72, 0, 0.72) * P.cov)
    over(rgb, alpha, (0.70, 0.36, 0.34), np.clip(ridge * shape * 0.45, 0, 0.45) * P.cov)
    over(rgb, alpha, (0.94, 0.82, 0.78), np.clip(ridge * shape * (fine > 0.6) * 0.25, 0, 0.25) * P.cov)   # the shine
    return rgb, alpha


def cigarette_burns(m, rng, healed=False):
    """Cigarette burns in a cluster (life.cigarette_burns' places): fresh, a crisp crusted crater with a raw red
    ring and a blistered pale halo; healed, a round sunken pale scar with a darker rim."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    zone = rng.choice(['forearm', 'thigh', 'chest', 'belly'])
    side = 1 if rng.random() < 0.5 else -1
    c0, n0, _ = decals.anchor(m, zone, side if zone != 'belly' else 0)
    t = life._unit(np.cross(n0, (0.0, 0.0, 1.0)) if abs(n0[2]) < 0.9 else np.cross(n0, (1.0, 0.0, 0.0)))
    b = np.cross(n0, t)
    crater = np.zeros(m.covered.shape)
    ring = np.zeros(m.covered.shape)
    halo = np.zeros(m.covered.shape)
    for _ in range(int(rng.integers(3, 8))):
        q = c0 + t * rng.normal(0, 1.6) + b * rng.normal(0, 1.6)
        r = rng.uniform(0.26, 0.40)
        idx = P.near(q, r * 3)
        if not len(idx):
            continue
        d = np.sqrt(((P.p.reshape(-1, 3)[idx] - q) ** 2).sum(-1))
        d = d * (1 + 0.18 * (fbm(P.p.reshape(-1, 3)[idx], 6.0, int(rng.integers(1 << 30)), 2) - 0.5) * 2)
        face = P.n.reshape(-1, 3)[idx] @ n0 > 0.3
        for arr, v in ((crater, np.clip((r * 0.55 - d) / 0.03, 0, 1)), (ring, np.clip((r - d) / 0.03, 0, 1)),
                       (halo, np.clip((r * 1.6 - d) / (r * 0.6), 0, 1))):
            flat = arr.reshape(-1)
            flat[idx] = np.maximum(flat[idx], v * face)
    seed = int(rng.integers(1 << 30))
    fine = fbm(P.p, 10.0, seed, 2)
    if healed:
        scar_shade(rgb, alpha, crater, ring, 'old')
        over(rgb, alpha, (0.46, 0.30, 0.22), np.clip((ring - crater) * 0.45 * (0.6 + 0.6 * fine), 0, 0.5) * P.cov)   # brown ring
    else:
        over(rgb, alpha, (0.80, 0.56, 0.50), np.clip((halo - ring) * 0.45, 0, 0.45) * P.cov)     # blistered halo
        over(rgb, alpha, (0.66, 0.16, 0.16), np.clip((ring - crater) * 0.8, 0, 0.8) * P.cov)     # raw ring
        scorch = np.clip((ring - crater) * 2.5 - 0.6, 0, 1)                                     # a charred brown inner edge
        over(rgb, alpha, (0.36, 0.20, 0.13), np.clip(scorch * 0.7, 0, 0.7) * P.cov)
        over(rgb, alpha, np.array((0.22, 0.08, 0.05)) * (0.85 + 0.3 * fine[..., None]), np.clip(crater * 0.9, 0, 0.9) * P.cov)
    return rgb, alpha


def rad_sores(m, rng):
    """Radiation sores: raw weeping lesions in two or three patches -- a crisp, irregular edge, wet red-pink
    centres with yellow crust, a dark crusted rim, flakes of peeling skin and inflamed red skin around."""
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm', 'leg'), 0.7, 0.0)
    patch = np.zeros(m.covered.shape)
    for c, n in P.pick_points(rng, weight > 0, int(rng.integers(2, 4)), weight):
        _lumpy(P, patch, c, n, rng.uniform(1.6, 2.8), rng)
    seed = int(rng.integers(1 << 30))
    lesion = fbm(P.p, 1.6, seed, 5) * patch
    raw = np.clip((lesion - 0.32) * 14, 0, 1)
    rim = np.clip((lesion - 0.26) * 10, 0, 1) - raw
    crust = (fbm(P.p, 4.0, seed + 1, 3) > 0.58) * raw
    peel = (fbm(P.p, 3.5, seed + 2, 2) > 0.66) * np.clip(patch * 1.5 - 0.2, 0, 1) * (raw < 0.5)
    fine = fbm(P.p, 10.0, seed + 3, 2)
    redness(P, rgb, alpha, np.clip(patch * 1.4, 0, 1), rng, strength=0.55)
    over(rgb, alpha, np.array((0.70, 0.22, 0.26)) * (0.9 + 0.2 * fine[..., None]), np.clip(raw * 0.85, 0, 0.85) * P.cov)
    over(rgb, alpha, (0.76, 0.62, 0.30), np.clip(crust * 0.7, 0, 0.7) * P.cov)
    over(rgb, alpha, (0.30, 0.10, 0.08), np.clip(rim * 0.8, 0, 0.8) * P.cov)
    over(rgb, alpha, (0.96, 0.88, 0.82), np.clip(peel * 0.55, 0, 0.55) * P.cov)
    return rgb, alpha


# ---------------------------------------------------------------- moles
# The first moles were identical round dark dots. Moles differ: flat tan ones, brown ones, a few very dark, some
# raised and catching the light; slightly oval, the outline uneven but sharp, the pigment uneven inside.

MOLE_TYPES = (  # (weight, colour, raised)
    (0.30, (0.56, 0.40, 0.29), False),
    (0.38, (0.38, 0.24, 0.17), False),
    (0.17, (0.22, 0.13, 0.10), False),
    (0.15, (0.32, 0.20, 0.15), True),
)


def _mole(P, rgb, alpha, c, n, r, colour, raised, rng):
    idx = P.near(c, r * 2.5)
    if not len(idx):
        return
    q = P.p.reshape(-1, 3)[idx] - c
    t = np.cross(n, (0.0, 0.0, 1.0))
    t = t / (np.linalg.norm(t) or 1)
    b = np.cross(n, t)
    u, v = q @ t, q @ b
    ang = np.arctan2(v, u)
    k = rng.uniform(0, 2 * np.pi, 3)
    wob = 1 + 0.12 * np.sin(ang * 2 + k[0]) + 0.07 * np.sin(ang * 3 + k[1]) + 0.05 * np.sin(ang * 5 + k[2])
    oval = rng.uniform(0.8, 1.0)
    d = np.sqrt((u * oval) ** 2 + v ** 2) / (r * wob)
    face = np.clip((P.n.reshape(-1, 3)[idx] @ n - 0.3) * 4, 0, 1)
    inside = np.clip((1 - d) / 0.12, 0, 1) * face                    # crisp: a tenth of its radius of edge
    pig = 0.85 + 0.3 * rng.random() + 0.25 * (1 - d)                   # darker toward the middle
    col = np.clip(np.asarray(colour)[None, :] / np.clip(pig, 0.7, 1.3)[:, None] * 1.0, 0, 1)
    flat_rgb = rgb.reshape(-1, 3)
    flat_a = alpha.reshape(-1)
    aa = np.clip(inside * rng.uniform(0.75, 0.95), 0, 0.95)
    flat_rgb[idx] = flat_rgb[idx] * (1 - aa[:, None]) + col * aa[:, None]
    flat_a[idx] = 1 - (1 - flat_a[idx]) * (1 - aa)
    if raised:   # a dome: lit on one side, a thin shadow at the foot on the other
        lit = np.clip(1 - np.sqrt(((u / r) + 0.35) ** 2 + ((v / r) - 0.35) ** 2) / 0.35, 0, 1) * inside
        shadow = np.clip(1 - np.abs(d - 1.05) / 0.12, 0, 1) * np.clip(-(u - v) / r, 0, 1) * face
        la = np.clip(lit * 0.45, 0, 0.45)
        flat_rgb[idx] = flat_rgb[idx] * (1 - la[:, None]) + np.array((0.70, 0.55, 0.47)) * la[:, None]
        sa = np.clip(shadow * 0.35, 0, 0.35)
        flat_rgb[idx] = flat_rgb[idx] * (1 - sa[:, None]) + np.array((0.45, 0.32, 0.26)) * sa[:, None]
        flat_a[idx] = np.maximum(flat_a[idx], sa)


def _mole_kind(rng):
    w = np.array([k[0] for k in MOLE_TYPES])
    return MOLE_TYPES[rng.choice(len(MOLE_TYPES), p=w / w.sum())]


def moles(m, rng, count=(15, 40)):
    """Moles over the torso, back and arms, every one its own."""
    P = Painter(m)
    rgb, alpha = blank(m)
    where = P.reg('torso', 'arm') & (P.h > 0.45)
    for c, n in P.pick_points(rng, where, int(rng.integers(count[0], count[1] + 1))):
        _, colour, raised = _mole_kind(rng)
        _mole(P, rgb, alpha, c, n, min(0.06 + 0.05 * rng.pareto(2.2), 0.28), colour, raised, rng)
    return rgb, alpha


TONE_SHIFT = {'brown': 1.0, 'dark': 0.62, 'light': 1.3, 'red': None}


def moles_zoned(m, rng, count=(20, 40), size=(0.07, 0.2), tone='brown', zone='everywhere', clusters=0, raised=False):
    """skin.moles' sets (count, size, tone, zone, clusters, raised) with real moles."""
    import skin
    P = Painter(m)
    rgb, alpha = blank(m)
    w = skin._zone(P, m, zone)
    if clusters:
        bias = np.zeros(m.covered.shape)
        for c, n in P.pick_points(rng, w > 0, clusters, w):
            bias += np.exp(-((P.p - c) ** 2).sum(-1) / (2 * 3.5 ** 2))
        w = w * (0.08 + bias)
    shift = TONE_SHIFT.get(tone, 1.0) or 1.0
    for c, n in P.pick_points(rng, w > 0, int(rng.integers(count[0], count[1] + 1)), w):
        _, colour, rz = _mole_kind(rng)
        colour = np.clip(np.asarray(colour) * shift, 0, 0.8)
        _mole(P, rgb, alpha, c, n, rng.uniform(*size) * rng.uniform(0.8, 1.25), colour, raised or rz, rng)
    return rgb, alpha


def cherry_angiomas(m, rng, count=(15, 40)):
    """Cherry angiomas: tiny bright-red domes, crisp, each catching a point of light, mostly on the trunk."""
    import skin
    P = Painter(m)
    rgb, alpha = blank(m)
    w = skin._zone(P, m, 'front' if rng.random() < 0.6 else 'back')
    for c, n in P.pick_points(rng, w > 0, int(rng.integers(count[0], count[1] + 1)), w):
        red = (rng.uniform(0.62, 0.78), rng.uniform(0.10, 0.16), rng.uniform(0.14, 0.2))
        _mole(P, rgb, alpha, c, n, rng.uniform(0.035, 0.085), red, True, rng)
    return rgb, alpha


# ---------------------------------------------------------------- restraints
# Rope, shackle and collar marks were smooth red bands. Rope leaves the twist of its strands printed in the skin
# with sharp edges, rubbed raw where the strands crossed; a shackle scrapes a raw band with abraded streaks along
# it and bruises its edges; a collar does the same round the neck.

def _abrasion(P, rgb, alpha, field, rng, strength=0.85):
    """Raw, scraped skin over field: wet red with crisp torn edges, streaks, crusted specks."""
    seed = int(rng.integers(1 << 30))
    torn = np.clip((field - (0.45 + 0.25 * (fbm(P.p, 3.0, seed, 3) - 0.5))) * 8, 0, 1)
    streak = fbm(P.p * np.array((1.0, 1.0, 4.0)), 3.0, seed + 1, 2)
    crust = (fbm(P.p, 12.0, seed + 2, 1) > 0.76) * torn
    over(rgb, alpha, np.array((0.66, 0.18, 0.18)) * (0.85 + 0.3 * streak[..., None]), np.clip(torn * strength * (0.7 + 0.35 * streak), 0, 0.85) * P.cov)
    over(rgb, alpha, (0.30, 0.06, 0.06), np.clip(crust * 0.8, 0, 0.8) * P.cov)


def bindings(m, rng, where='wrists', fresh=True):
    """Rope marks (life.bindings' twisted strands): the twist printed sharp, raw where the strands bit, a scuffed red
    margin; healing, the print brown."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    which = 'arm' if where == 'wrists' else 'leg'
    core = np.zeros(m.covered.shape)
    halo = np.zeros(m.covered.shape)
    for side in (1, -1):
        mask, c, ax = life.limb(P, which, side)
        if not mask.any():
            continue
        t0 = life.limb_end(P, mask, c, ax) - (2.7 if which == 'arm' else 2.4)
        t, theta, r = life.ring_coords(P, mask, c, ax, t0)
        twist = rng.uniform(5, 8)
        strands = int(rng.integers(2, 4))
        for k in range(strands):
            off = (k - (strands - 1) / 2) * 0.62 + 0.25 * np.sin(theta * 2 + k)
            band = np.clip((0.26 - np.abs(t - off)) / 0.05, 0, 1)             # crisp strand width
            stri = np.clip(np.cos(theta * twist * 2 + (t - off) * 14) * 2.2 + 0.4, 0, 1)
            core = np.maximum(core, band * stri * mask)
        halo = np.maximum(halo, np.clip((0.62 * strands * 1.3 - np.abs(t)) / 1.0, 0, 1) ** 1.6 * mask)   # fades out wide
    if fresh:
        redness(P, rgb, alpha, halo, rng, strength=0.8, soft=True)
        _abrasion(P, rgb, alpha, core, rng)
    else:
        seed = int(rng.integers(1 << 30))
        fine = fbm(P.p, 9.0, seed, 2)
        over(rgb, alpha, (0.56, 0.40, 0.33), np.clip(halo * 0.25 * (0.7 + 0.5 * fine), 0, 0.3) * P.cov)
        over(rgb, alpha, np.array((0.44, 0.28, 0.22)) * (0.9 + 0.2 * fine[..., None]), np.clip(core * 0.55, 0, 0.55) * P.cov)
    return rgb, alpha


def shackles(m, rng, where='ankles'):
    """Shackle chafe (life.shackles' band): a raw scraped band with crisp torn edges and streaks along it, bruised
    to either side."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    which = 'arm' if where == 'wrists' else 'leg'
    raw = np.zeros(m.covered.shape)
    bruise = np.zeros(m.covered.shape)
    for side in (1, -1):
        mask, c, ax = life.limb(P, which, side)
        if not mask.any():
            continue
        t0 = life.limb_end(P, mask, c, ax) - (2.6 if which == 'arm' else 2.4)
        t, theta, r = life.ring_coords(P, mask, c, ax, t0)
        wob = 0.25 * np.sin(theta + rng.uniform(0, 6))
        raw = np.maximum(raw, np.clip((0.55 - np.abs(t - wob)) / 0.3, 0, 1) * mask)
        bruise = np.maximum(bruise, np.clip((1.7 - np.abs(t - wob)) / 1.2, 0, 1) ** 1.5 * mask)          # fades out wide
    patchy = np.clip(0.2 + 1.1 * fbm(P.p, 1.3, int(rng.integers(1 << 30)), 3), 0, 1)   # bruised in places, not a stripe
    redness(P, rgb, alpha, bruise * (0.5 + 0.5 * patchy), rng, strength=0.85, soft=True)   # chafed red round it, blending into the skin
    _abrasion(P, rgb, alpha, raw, rng)
    return rgb, alpha


def collar(m, rng):
    """A collar's chafe at the base of the neck (life.collar's band below the seam): rubbed raw with crisp edges,
    bruised along both edges."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    top_z = P.p[..., 2][P.cov].max()
    near = P.cov & (np.abs(P.p[..., 0]) < 7) & (P.p[..., 2] > top_z - 6)
    cx, cy = P.p[..., 0][near].mean(), P.p[..., 1][near].mean()
    theta = np.arctan2(P.p[..., 0] - cx, P.p[..., 1] - cy)
    bins = np.clip(((theta + np.pi) / (2 * np.pi) * 72).astype(int), 0, 71)
    seam = np.full(72, -np.inf)
    np.maximum.at(seam, bins[near], P.p[..., 2][near])
    for _ in range(3):
        seam = (np.roll(seam, 1) + seam * 2 + np.roll(seam, -1)) / 4
    centres = (np.arange(72) + 0.5) / 72 * 2 * np.pi - np.pi
    below = np.interp(theta, centres, seam, period=2 * np.pi) - P.p[..., 2]   # interpolated: per-bin steps were a staircase
    wob = 0.2 * np.sin(theta * 2 + rng.uniform(0, 6))
    dz = below - rng.uniform(2.0, 2.4) - wob                          # clear of the neck seam: skin shows above it
    neck = near & (np.abs(P.p[..., 0] - cx) < 6.5)
    width = 0.32 + 0.3 * fbm(P.p, 0.6, int(rng.integers(1 << 30)), 3)       # rubbed wider in places, narrower in others
    raw = np.clip((width - np.abs(dz)) / 0.15, 0, 1) * neck
    raw = raw * np.clip((fbm(P.p, 1.4, int(rng.integers(1 << 30)), 3) - 0.3) * 4, 0, 1)   # raw in patches, not a full ring
    edge = np.clip((1.3 - np.abs(dz)) / 1.0, 0, 1) ** 1.5 * neck                                  # fades out wide
    patchy = np.clip(0.2 + 1.1 * fbm(P.p, 1.3, int(rng.integers(1 << 30)), 3), 0, 1)
    redness(P, rgb, alpha, np.clip(edge, 0, 1) * (0.5 + 0.5 * patchy), rng, strength=0.85, soft=True)
    _abrasion(P, rgb, alpha, raw, rng, 0.75)
    return rgb, alpha


def laser_burn(m, rng):
    """A laser or plasma burn (life.laser_burn's streak): a lesion along it like the other scars, its edges
    mottled with darker scorched browns."""
    import life
    P = Painter(m)
    rgb, alpha = blank(m)
    weight = np.where(P.reg('torso') & (P.h > 0.5), 1.0, 0.0) + np.where(P.reg('arm', 'leg'), 0.5, 0.0)
    (c, n), = P.pick_points(rng, weight > 0, 1, weight)
    t = rng.normal(size=3)
    half = rng.uniform(4, 8)
    width = rng.uniform(0.45, 0.75)
    seed = int(rng.integers(1 << 30))
    core, _ = life.segment(P, c, n, t, half, width, facing=0.1)
    edge, _ = life.segment(P, c, n, t, half * 1.05, width * 2.2, facing=0.1)
    scar_shade(rgb, alpha, core, edge, 'newer')
    # the char as streaks along the burn's path, not blotches (alasdairn, 10-10: "more lines rather than circles"):
    # noise squeezed along the streak's direction, so it varies across it and runs on along it
    tu = t - n * (t @ n)
    tu = tu / (np.linalg.norm(tu) or 1)
    q = P.p - ((P.p - c) @ tu)[..., None] * tu * 0.9
    band = np.clip(edge * 1.8, 0, 1)
    runs = fbm(q, 2.6, seed + 2, 3)
    breaks = np.clip((fbm(P.p, 0.9, seed + 5, 2) - 0.3) * 4, 0, 1)
    lines = np.clip(1 - np.abs(runs - 0.5) / 0.045, 0, 1) * breaks
    browns = np.clip(1 - np.abs(runs - 0.5) / 0.07, 0, 1) * np.clip((fbm(P.p, 0.9, seed + 5, 2) - 0.22) * 4, 0, 1)   # a slight brown round them (10-10)
    char = np.clip(lines * band * 1.4, 0, 1)
    scorch = np.clip((fbm(q, 1.4, seed + 6, 3) - 0.56) * 5, 0, 1) * np.clip(edge * 1.6 - core, 0, 1)
    flake = 0.75 + 0.4 * fbm(P.p, 11.0, seed + 4, 2)
    over(rgb, alpha, (0.36, 0.22, 0.15), np.clip(scorch * 0.4, 0, 0.4) * P.cov)
    over(rgb, alpha, (0.38, 0.24, 0.16), np.clip(np.clip(browns * band * 1.4, 0, 1) * 0.55, 0, 0.55) * P.cov)
    over(rgb, alpha, np.array((0.12, 0.09, 0.08)) * flake[..., None], np.clip(char * 0.75, 0, 0.78) * P.cov)
    return rgb, alpha


# ---------------------------------------------------------------- healed stitches
# alasdairn (10-10) sent a reference of how stitches heal (an iStock image: looked at, never copied). Once they are
# out, what stays is a thin incision line, pink-red, a little irregular, with a soft pink band round it, and a row
# of small round puncture marks in pairs either side where each stitch went in -- no cross-bars.

def stitch_dots(P, dots, c, n, t, half, width):
    """Adds the puncture marks of one stitched incision to dots: pairs either side of the line along its length."""
    tu = t - n * (t @ n)
    tu = tu / (np.linalg.norm(tu) or 1)
    side = np.cross(n, tu)
    side = side / (np.linalg.norm(side) or 1)
    spacing = 0.55 + 0.25 * min(width / 0.35, 1.5)
    off = max(width * 2.2, 0.5)
    seed = int(abs(c[0] * 997 + c[2] * 131)) % 100000
    jit = np.random.default_rng(seed)
    for s in np.arange(-half * 0.85, half * 0.85 + 1e-6, spacing):
        for sgn in (1, -1):
            q = c + tu * (s + jit.normal(0, 0.04)) + side * sgn * off * jit.uniform(0.9, 1.1)
            r = jit.uniform(0.13, 0.18)
            idx = P.near(q, 3.0)
            if not len(idx):
                continue
            pts = P.p.reshape(-1, 3)[idx]
            near_k = np.argmin(((pts - q) ** 2).sum(-1))
            if ((pts[near_k] - q) ** 2).sum() > 4.0:
                continue
            q = pts[near_k]                                   # onto the skin: a straight line leaves a curved body
            nq = P.n.reshape(-1, 3)[idx][near_k]
            d = np.sqrt(((pts - q) ** 2).sum(-1))
            v = np.clip((r - d) / (r * 0.4), 0, 1) * (P.n.reshape(-1, 3)[idx] @ nq > 0.4)
            flat = dots.reshape(-1)
            flat[idx] = np.maximum(flat[idx], v)


def stitch_shade(P, rgb, alpha, line, halo, dots, rng):
    """A healed stitched incision: soft pink band, thin irregular pink-red line darkened a touch (the dark overlay
    alasdairn chose for scars), dark-pink puncture marks with a softer ring."""
    seed = int(rng.integers(1 << 30))
    fine = fbm(P.p, 9.0, seed, 2)
    wob = fbm(P.p, 3.0, seed + 1, 3)
    soft = ndimage.gaussian_filter(line, 5.0)
    soft = soft / max(soft.max(), 1e-6)
    band = np.clip(np.maximum(soft * 1.3, ndimage.gaussian_filter(dots, 3.0) * 1.5), 0, 1)   # the soft pink round it all
    # older and faded (alasdairn, 10-10): darker, duller colours, the band and punctures faded back toward skin
    over(rgb, alpha, (0.70, 0.50, 0.46), np.clip(band * 0.18 * (0.8 + 0.3 * fine), 0, 0.18) * P.cov)   # a bit more faded (10-10)
    core = np.clip((line * (0.6 + 0.8 * wob) - 0.35) * 5, 0, 1)
    over(rgb, alpha, np.array((0.52, 0.30, 0.29)) * (0.92 + 0.12 * fine[..., None]), np.clip(core * 0.55, 0, 0.58) * P.cov)
    over(rgb, alpha, (0.32, 0.17, 0.17), np.clip(core * 0.22, 0, 0.22) * P.cov)
    ring = np.clip(ndimage.gaussian_filter(dots, 1.2) * 1.6, 0, 1)
    over(rgb, alpha, (0.64, 0.44, 0.40), np.clip(ring * 0.14, 0, 0.14) * P.cov)
    over(rgb, alpha, (0.48, 0.28, 0.27), np.clip(dots * 0.36, 0, 0.36) * P.cov)


if __name__ == '__main__':
    import sys
    rng = np.random.default_rng(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    im = {'splatter': splatter, 'smear': smear}[sys.argv[1]](rng)
    bg = Image.new('RGBA', im.size, (214, 176, 150, 255))
    bg.alpha_composite(im)
    bg.convert('RGB').resize((900, int(900 * im.height / im.width))).save(sys.argv[2])
