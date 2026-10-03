"""Drawn tattoos (C-13): a 2D design projected flat onto the skin around a named spot on the body.

Anchors are found in 3D on the body itself (body.UVMap): "the middle of the upper back", "the outer left forearm".
At the anchor the skin's normal n and an up vector give a frame; every texel near it gets (u, v) in that frame and
samples the design -- so the design lies flat on the skin there, crosses UV seams whole, and keeps its size in
game units on any body. Designs are greyscale masks drawn with PIL: words in open-licence tattoo fonts
(tools/paint/fonts, OFL), geometric and tribal patterns, and faction emblems as vector shapes.
"""
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from marks import Painter, blank, fbm, over

FONTS = pathlib.Path(__file__).resolve().parent / 'fonts'
FONT = {'blackletter': 'UnifrakturMaguntia-Book.ttf', 'pirate': 'PirataOne-Regular.ttf', 'western': 'Rye-Regular.ttf',
        'script': 'GreatVibes-Regular.ttf', 'stencil': 'StardosStencil-Bold.ttf'}
INK = {'fresh': (0.10, 0.12, 0.13), 'faded': (0.24, 0.30, 0.38), 'red': (0.45, 0.10, 0.10)}


# ---------------------------------------------------------------- anchors

def anchor(m, spot, side=0):
    """(point, normal, up) of a named spot. side: +1 the character's RIGHT (+x), -1 their left, 0 the middle.
    Measured 2026-10-03: the packs' "ArmL" tattoos sit at x < 0, so +x is the character's right."""
    P = Painter(m)
    p, n, h = P.p, P.n, P.h
    torso = P.reg('torso')
    arm = P.reg('arm')
    leg = P.reg('leg')
    reach = max(np.abs(p[..., 0][arm]).max(), 1e-6) if arm.any() else 1.0
    tw = np.abs(p[..., 0][torso & (np.abs(h - 0.75) < 0.02)]).max() if torso.any() else 10.0
    front_torso = torso & (n[..., 1] > 0.3)
    crotch = h[front_torso].min() if front_torso.any() else 0.47
    specs = {
        # spot: (mask, target x, target h, facing (+1 front / -1 back / 0 side), up)
        'chest': (torso, side * 0.42 * tw if side else 0.0, 0.80, 1, (0, 0, 1)),
        'belly': (torso, 0.0, 0.63, 1, (0, 0, 1)),
        'upper_back': (torso, 0.0, 0.80, -1, (0, 0, 1)),
        'lower_back': (torso, 0.0, 0.58, -1, (0, 0, 1)),
        'neck_back': (torso, 0.0, 0.875, -1, (0, 0, 1)),
        'shoulder': (torso | arm, side * 0.75 * tw, 0.83, 0, (0, 0, 1)),
        'upper_arm': (arm, side * 0.45 * reach, None, 0, (0, 0, 1)),
        'forearm': (arm, side * 0.72 * reach, None, 1, (side or 1, 0, 0)),
        'thigh': (leg, side * 0.45 * tw, 0.38, 1, (0, 0, 1)),
        'thigh_back': (leg, side * 0.45 * tw, 0.40, -1, (0, 0, 1)),
        'calf': (leg, side * 0.40 * tw, 0.16, -1, (0, 0, 1)),
        'hip': (torso | leg, side * 0.85 * tw, 0.53, 0, (0, 0, 1)),
        'butt': (torso | leg, side * 0.45 * tw, None, -1, (0, 0, 1)),  # height: from the crotch, below
        # Lewd marks (C-14): just above the pubic hair, the crack of the buttocks, the inner thighs.
        'pubic': (torso, 0.0, crotch + 0.05, 1, (0, 0, 1)),
        'tailbone': (torso, 0.0, crotch + 0.05, -1, (0, 0, 1)),
        'inner_thigh': (leg, side * 0.16 * tw, crotch - 0.07, 2, (0, 0, 1)),
    }
    mask, tx, th, facing, up = specs[spot]
    if spot == 'butt':
        th = crotch + 0.075  # the middle of a buttock (a fixed 0.51 put the words on the backs of the thighs)
    mask = mask & P.cov
    idx = np.flatnonzero(mask)
    pts = p.reshape(-1, 3)[idx]
    nrm = n.reshape(-1, 3)[idx]
    hh = h.reshape(-1)[idx]
    score = np.abs(pts[:, 0] - tx)
    if th is not None:
        score = score + 40 * np.abs(hh - th)
    if facing == 1:
        score = score + 20 * np.clip(0.5 - nrm[:, 1], 0, None)
    elif facing == -1:
        score = score + 20 * np.clip(0.5 + nrm[:, 1], 0, None)
    elif facing == 2:
        # the inner face of a thigh: its normal points toward the middle
        score = score + 20 * np.clip(0.4 + nrm[:, 0] * side, 0, None)
    elif side:
        score = score + 10 * np.clip(0.6 - nrm[:, 0] * side, 0, None)
    k = np.argmin(score)
    return pts[k], nrm[k], np.array(up, dtype=float)


def project(m, design, spot, side=0, width=8.0, rotate=0.0, alpha=0.9, ink='fresh', crude=0.0, seed=0):
    """design (a PIL 'L' image, white = ink) flat on the skin around the spot, width game units across."""
    P = Painter(m)
    rgb, a_out = blank(m)
    c, n, up = anchor(m, spot, side)
    up = up - n * (up @ n)
    if np.linalg.norm(up) < 1e-3:
        up = np.array((0.0, 0.0, 1.0)) - n * n[2]
    up = up / np.linalg.norm(up)
    right = np.cross(up, n)
    if rotate:
        cr, sr = np.cos(rotate), np.sin(rotate)
        up, right = up * cr + right * sr, right * cr - up * sr
    img = np.asarray(design, dtype=np.float64) / 255.0
    hgt = width * img.shape[0] / img.shape[1]
    idx = P.near(c, max(width, hgt))
    if not len(idx):
        return rgb, a_out
    pts = P.p.reshape(-1, 3)[idx] - c
    nrm = P.n.reshape(-1, 3)[idx]
    u = pts @ right / width + 0.5
    v = 0.5 - pts @ up / hgt
    depth = np.abs(pts @ n)
    ok = (u >= 0) & (u < 1) & (v >= 0) & (v < 1) & (nrm @ n > 0.25) & (depth < max(width, hgt) * 0.5)
    vals = np.zeros(len(idx))
    xi = np.clip((u[ok] * img.shape[1]).astype(int), 0, img.shape[1] - 1)
    yi = np.clip((v[ok] * img.shape[0]).astype(int), 0, img.shape[0] - 1)
    vals[ok] = img[yi, xi]
    a = np.zeros(m.covered.shape)
    a.reshape(-1)[idx] = vals
    if crude:
        # Stick-and-poke: uneven saturation, a little blown-out ink.
        a = a * (1 - crude * 0.5 * fbm(P.p, 3.0, seed, 2))
    a = np.clip(a * alpha, 0, 0.95) * P.cov
    over(rgb, a_out, INK[ink], a)
    return rgb, a_out


# ---------------------------------------------------------------- designs

def _canvas(w, h):
    im = Image.new('L', (w, h), 0)
    return im, ImageDraw.Draw(im)


def word(text, font='blackletter', arc=0.0, px=160):
    """A word in a tattoo font, cropped tight; arc > 0 bends it along a circle (a chest or back banner)."""
    f = ImageFont.truetype(str(FONTS / FONT[font]), px)
    l, t, r, b = f.getbbox(text)
    im, d = _canvas(r - l + 20, b - t + 20)
    d.text((10 - l, 10 - t), text, fill=255, font=f)
    if arc:
        w, h = im.size
        arr = np.asarray(im)
        out = np.zeros((h + int(w * arc), w), np.uint8)
        for x in range(w):
            dy = int((((x - w / 2) / (w / 2)) ** 2) * w * arc)
            out[dy:dy + h, x] = arr[:, x]
        im = Image.fromarray(out)
    return im


def arrow_word(text, font='stencil', arrow='down', px=150):
    """A word with a fat hand-drawn arrow: below it pointing down, or after it pointing sideways."""
    w = word(text, font, 0.0, px)
    tw, th = w.size
    if arrow == 'down':
        im, d = _canvas(max(tw, 160), th + 190)
        im.paste(w, ((im.width - tw) // 2, 0))
        cx = im.width // 2
        d.rectangle((cx - 16, th + 10, cx + 16, th + 110), fill=255)
        d.polygon([(cx - 60, th + 100), (cx + 60, th + 100), (cx, th + 180)], fill=255)
        return im
    im, d = _canvas(tw + 220, max(th, 130))
    im.paste(w, (0, (im.height - th) // 2))
    cy = im.height // 2
    sign = 1 if arrow == 'right' else -1
    x0 = tw + 20 if sign > 0 else tw + 200
    d.rectangle((tw + 20, cy - 14, tw + 160, cy + 14), fill=255)
    tip = tw + 215 if sign > 0 else tw + 5
    base = tw + 150 if sign > 0 else tw + 70
    d.polygon([(base, cy - 50), (base, cy + 50), (tip, cy)], fill=255)
    return im


def tally(count=12, w=520, h=180):
    """Tally marks: groups of four strokes crossed by a fifth."""
    im, d = _canvas(w, h)
    x = 20
    for i in range(count):
        if i % 5 == 4:
            d.line((x - 4 * 26 - 10, h - 30, x - 10, 30), fill=255, width=12)
            x += 30
        else:
            d.line((x, 25, x + 4, h - 25), fill=255, width=12)
            x += 26
    return im


def barcode(rng, w=400, h=160):
    im, d = _canvas(w, h)
    x = 10
    while x < w - 10:
        bw = int(rng.integers(2, 9))
        if rng.random() < 0.55:
            d.rectangle((x, 10, x + bw, h - 34), fill=255)
        x += bw + int(rng.integers(2, 6))
    digits = ''.join(str(int(rng.integers(0, 10))) for _ in range(10))
    f = ImageFont.truetype(str(FONTS / FONT['stencil']), 22)
    d.text((w // 2 - 70, h - 30), digits, fill=255, font=f)
    return im


def prison_dots():
    im, d = _canvas(200, 200)
    for x, y in ((50, 50), (150, 50), (100, 100), (50, 150), (150, 150)):
        d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=255)
    return im


def mandala(rng, size=600):
    im, d = _canvas(size, size)
    c = size / 2
    rings = int(rng.integers(3, 6))
    for k in range(rings):
        r = c * (0.2 + 0.75 * k / max(rings - 1, 1))
        petals = int(rng.choice([8, 12, 16, 24]))
        pr = r * rng.uniform(0.12, 0.22)
        for i in range(petals):
            a = 2 * np.pi * i / petals
            x, y = c + np.cos(a) * r, c + np.sin(a) * r
            if k % 2:
                d.ellipse((x - pr, y - pr, x + pr, y + pr), outline=255, width=6)
            else:
                d.polygon([(c + np.cos(a - 0.12) * (r - pr), c + np.sin(a - 0.12) * (r - pr)),
                           (x + np.cos(a) * pr * 1.6, y + np.sin(a) * pr * 1.6),
                           (c + np.cos(a + 0.12) * (r - pr), c + np.sin(a + 0.12) * (r - pr))], outline=255, width=6)
        d.ellipse((c - r * 0.55, c - r * 0.55, c + r * 0.55, c + r * 0.55), outline=255, width=4)
    d.ellipse((c - 18, c - 18, c + 18, c + 18), fill=255)
    return im


def tribal(rng, w=700, h=420):
    """A mirrored tribal piece: thick tapering hooks swept from the middle line."""
    half = Image.new('L', (w // 2, h), 0)
    d = ImageDraw.Draw(half)
    for _ in range(int(rng.integers(3, 6))):
        y0 = rng.uniform(0.2, 0.8) * h
        pts = []
        length = rng.uniform(0.6, 1.0) * (w / 2)
        curl = rng.uniform(-1.4, 1.4)
        thick = rng.uniform(18, 40)
        for t in np.linspace(0, 1, 28):
            x = t * length
            y = y0 + np.sin(t * np.pi * curl) * h * 0.25 * t
            pts.append((x, y, thick * (1 - t) ** 0.8 + 2))
        for x, y, r in pts:
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    arr = np.asarray(half)
    full = np.concatenate([arr[:, ::-1], arr], axis=1)
    return Image.fromarray(full)


def band(rng, w=900, h=120):
    """An arm or leg band: a strip of repeated triangles or knots between two lines."""
    im, d = _canvas(w, h)
    d.rectangle((0, 8, w, 18), fill=255)
    d.rectangle((0, h - 18, w, h - 8), fill=255)
    step = int(rng.integers(40, 80))
    kind = rng.integers(0, 2)
    for x in range(0, w, step):
        if kind == 0:
            d.polygon([(x, h - 22), (x + step / 2, 22), (x + step, h - 22)], fill=255)
        else:
            d.ellipse((x + 6, 28, x + step - 6, h - 28), outline=255, width=8)
    return im


# Faction emblems: simplified, recognisable silhouettes (Fallout's own marks; drawn here, not copied).

def emblem(name, size=500):
    im, d = _canvas(size, size)
    c = size / 2
    if name == 'atom':
        for ang in (0, 60, 120):
            e = Image.new('L', (size, size), 0)
            ImageDraw.Draw(e).ellipse((c - 220, c - 80, c + 220, c + 80), outline=255, width=16)
            im.paste(e.rotate(ang, center=(c, c)), (0, 0), e.rotate(ang, center=(c, c)))
        d.ellipse((c - 40, c - 40, c + 40, c + 40), fill=255)
    elif name == 'vault_tec':
        teeth = 12
        pts = []
        for i in range(teeth * 2):
            a = np.pi * i / teeth
            r = 230 if i % 2 == 0 else 195
            pts.append((c + np.cos(a) * r, c + np.sin(a) * r))
        d.polygon(pts, fill=255)
        d.ellipse((c - 150, c - 150, c + 150, c + 150), fill=0)
        f = ImageFont.truetype(str(FONTS / FONT['stencil']), 190)
        d.text((c - 70, c - 120), 'V', fill=255, font=f)
    elif name == 'bos':
        d.ellipse((c - 120, c - 120, c + 120, c + 120), outline=255, width=26)
        d.rectangle((c - 14, c - 230, c + 14, c + 230), fill=255)            # the sword
        d.polygon([(c - 60, c - 175), (c + 60, c - 175), (c, c - 215)], fill=255)
        for s in (1, -1):                                                     # the wings
            for k in range(4):
                y = c - 40 + k * 30
                d.polygon([(c + s * 120, y), (c + s * (240 - k * 20), y - 50), (c + s * (230 - k * 20), y + 10)], fill=255)
    elif name == 'minutemen':
        d.ellipse((c - 220, c - 220, c + 220, c + 220), outline=255, width=18)
        star = [(c + np.cos(-np.pi / 2 + i * 4 * np.pi / 5) * 170, c + np.sin(-np.pi / 2 + i * 4 * np.pi / 5) * 170) for i in range(5)]
        d.polygon(star, fill=255)
    elif name == 'railroad':
        d.rectangle((c - 90, c - 120, c + 90, c + 150), outline=255, width=20)   # a lantern
        d.rectangle((c - 50, c - 190, c + 50, c - 120), outline=255, width=16)
        d.arc((c - 60, c - 250, c + 60, c - 150), 180, 360, fill=255, width=14)
        d.ellipse((c - 40, c - 20, c + 40, c + 70), fill=255)
    elif name == 'raiders':
        d.ellipse((c - 150, c - 200, c + 150, c + 80), fill=255)                 # a skull
        d.rectangle((c - 90, c + 40, c + 90, c + 140), fill=255)
        d.ellipse((c - 110, c - 90, c - 30, c - 10), fill=0)
        d.ellipse((c + 30, c - 90, c + 110, c - 10), fill=0)
        d.polygon([(c, c - 5), (c - 22, c + 35), (c + 22, c + 35)], fill=0)
        for x in range(-75, 90, 30):
            d.rectangle((c + x, c + 95, c + x + 6, c + 140), fill=0)
    elif name == 'gunners':
        d.ellipse((c - 200, c - 200, c + 200, c + 200), outline=255, width=16)    # a crosshair
        d.ellipse((c - 90, c - 90, c + 90, c + 90), outline=255, width=12)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            d.line((c + dx * 110, c + dy * 110, c + dx * 245, c + dy * 245), fill=255, width=16)
    return im
