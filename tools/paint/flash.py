"""C-17 (owner, 2026-10-03): Complexion's own art tattoos -- American-traditional "flash", the bold-outline style a
wasteland tattooist would actually ink, so every faction's tattoo styles are covered by our own art and the packs
become optional extra variety.

Each motif is drawn with PIL as an RGBA image: a heavy black outline, flat fills in a few tattoo pigments (red,
green, yellow, blue, and the skin left bare as "white"), black whip-shading. project_rgba() lays it flat on the skin
around a named spot like decals.project, carrying the colours; make_marks multiplies it onto the skin (C-12), so the
pigments read as ink in the skin, lit and shadowed with it.

Motifs are drawn at 2x and scaled down for clean edges. Coordinates are in a 0..1 box, scaled to the canvas.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import decals
from marks import Painter, blank, fbm

INK = (22, 22, 26)
RED = (170, 28, 32)
GREEN = (38, 112, 54)
YELLOW = (226, 178, 44)
BLUE = (36, 72, 150)
ORANGE = (214, 104, 30)
BONE = (236, 226, 200)
GREY = (150, 156, 164)
BROWN = (112, 66, 34)
PURPLE = (96, 46, 130)
S = 1200  # the canvas, drawn at 2x


class Art:
    """A 2x RGBA canvas with tattoo-style helpers; coordinates 0..1."""

    def __init__(self, w=1.0, h=1.0):
        self.W, self.H = int(S * w), int(S * h)
        self.im = Image.new('RGBA', (self.W, self.H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def p(self, x, y):
        return (x * S, y * S)

    def pts(self, seq):
        return [self.p(x, y) for x, y in seq]

    def shape(self, seq, fill, line=INK, width=0.022):
        q = self.pts(seq)
        if fill:
            self.d.polygon(q, fill=fill + (255,))
        if line:
            self.d.line(q + [q[0]], fill=line + (255,), width=int(width * S), joint='curve')
            r = width * S / 2
            for x, y in q:
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=line + (255,))

    def line(self, seq, colour=INK, width=0.018):
        q = self.pts(seq)
        self.d.line(q, fill=colour + (255,), width=int(width * S), joint='curve')
        r = width * S / 2
        for x, y in (q[0], q[-1]):
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=colour + (255,))

    def circle(self, x, y, r, fill, line=INK, width=0.022):
        b = (x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S
        self.d.ellipse(b, fill=(fill + (255,)) if fill else None, outline=(line + (255,)) if line else None,
                       width=int(width * S) if line else 0)

    def ellipse(self, x, y, rx, ry, fill, line=INK, width=0.022):
        b = (x - rx) * S, (y - ry) * S, (x + rx) * S, (y + ry) * S
        self.d.ellipse(b, fill=(fill + (255,)) if fill else None, outline=(line + (255,)) if line else None,
                       width=int(width * S) if line else 0)

    def text(self, s, x, y, size, font='western', colour=INK):
        f = ImageFont.truetype(str(decals.FONTS / decals.FONT[font]), int(size * S))
        l, t, r, b = f.getbbox(s)
        self.d.text((x * S - (r - l) / 2 - l, y * S - (b - t) / 2 - t), s, fill=colour + (255,), font=f)

    def done(self, px=600):
        w = px if self.W >= self.H else int(px * self.W / self.H)
        h = int(w * self.H / self.W)
        return self.im.resize((w, h), Image.LANCZOS)


def bez(p0, p1, p2, p3=None, n=24):
    """Points along a quadratic (3 points) or cubic (4 points) Bezier."""
    t = np.linspace(0, 1, n)[:, None]
    a, b, c = np.array(p0), np.array(p1), np.array(p2)
    if p3 is None:
        q = (1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c
    else:
        d = np.array(p3)
        q = (1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * c + t ** 3 * d
    return [tuple(v) for v in q]


def ring(cx, cy, rx, ry, a0=0.0, a1=2 * np.pi, n=48):
    return [(cx + np.cos(a) * rx, cy + np.sin(a) * ry) for a in np.linspace(a0, a1, n)]


def heart_pts(cx, cy, s, n=80):
    t = np.linspace(0, 2 * np.pi, n)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    return [(cx + xi / 17 * s, cy - yi / 17 * s) for xi, yi in zip(x, y)]


def leaf(a, cx, cy, ang, length, width, fill=GREEN):
    dx, dy = np.cos(ang), np.sin(ang)
    nx, ny = -dy, dx
    tip = (cx + dx * length, cy + dy * length)
    side1 = bez((cx, cy), (cx + dx * length * 0.5 + nx * width, cy + dy * length * 0.5 + ny * width), tip, n=14)
    side2 = bez(tip, (cx + dx * length * 0.5 - nx * width, cy + dy * length * 0.5 - ny * width), (cx, cy), n=14)
    a.shape(side1 + side2[1:], fill, width=0.014)
    a.line([(cx, cy), (cx + dx * length * 0.85, cy + dy * length * 0.85)], width=0.008)


# ---------------------------------------------------------------- motifs


def rose(colour=RED):
    """The traditional rose: a scalloped cup of petals, a front petal folded over, the swirl at the heart, two
    leaves, whip-shading on the lower petals."""
    a = Art()
    dark = tuple(int(c * 0.62) for c in colour)
    leaf(a, 0.40, 0.64, np.pi * 0.80, 0.30, 0.10)
    leaf(a, 0.62, 0.66, np.pi * 0.14, 0.30, 0.10)
    cup = ring(0.5, 0.46, 0.26, 0.24, 0.0, np.pi, 30)                     # the bowl, right to left
    for cx in (0.30, 0.43, 0.57, 0.70):                                    # the scalloped rim, left to right
        cup += ring(cx, 0.40, 0.075, 0.08, np.pi, 2 * np.pi, 10)
    a.shape(cup, colour, width=0.026)
    a.shape(ring(0.5, 0.36, 0.17, 0.10), dark, width=0.018)               # the opening, in shadow
    spiral = [(0.5 + np.cos(t) * (0.008 + 0.0068 * t) * 1.3, 0.36 + np.sin(t) * (0.008 + 0.0068 * t) * 0.75)
              for t in np.linspace(0, 3.4 * np.pi, 60)]
    a.line(spiral, width=0.014)
    front = ring(0.5, 0.50, 0.21, 0.16, 0.0, np.pi, 26) + bez((0.29, 0.50), (0.5, 0.40), (0.71, 0.50), n=16)
    a.shape(front, colour, width=0.022)
    for side in (1, -1):                                                   # the side petals curling in
        a.line(bez((0.5 + side * 0.24, 0.44), (0.5 + side * 0.18, 0.56), (0.5 + side * 0.08, 0.62)), width=0.014)
    for k in range(7):                                                     # whip-shading low on the bowl
        x = 0.36 + k * 0.045
        a.line([(x, 0.60 + 0.02 * abs(k - 3) / 3), (x + 0.01, 0.66 - 0.03 * abs(k - 3) / 3)], colour=dark, width=0.010)
    return a.done()


def skull(eyes=INK, bone=BONE):
    a = Art()
    cran = ring(0.5, 0.40, 0.26, 0.25, np.pi * 0.85, np.pi * 2.15, 40)
    jaw = [(0.66, 0.60), (0.63, 0.74), (0.37, 0.74), (0.34, 0.60)]
    a.shape(cran + jaw, bone, width=0.026)
    for x in (0.40, 0.60):
        a.shape(ring(x, 0.47, 0.075, 0.07, 0, 2 * np.pi, 28), eyes, width=0.018)
    a.shape([(0.5, 0.54), (0.465, 0.61), (0.535, 0.61)], INK, width=0.012)
    a.line([(0.39, 0.69), (0.61, 0.69)], width=0.012)
    for x in np.linspace(0.42, 0.58, 5):
        a.line([(x, 0.64), (x, 0.74)], width=0.010)
    a.line(bez((0.55, 0.17), (0.6, 0.24), (0.57, 0.3)), width=0.010)        # a crack
    a.line([(0.3, 0.42), (0.33, 0.5)], width=0.009)
    return a.done()


def skull_bones():
    a = Art()
    for (x0, y0, x1, y1) in ((0.18, 0.88, 0.82, 0.30), (0.18, 0.30, 0.82, 0.88)):
        a.line([(x0, y0), (x1, y1)], colour=INK, width=0.075)
        a.line([(x0, y0), (x1, y1)], colour=BONE, width=0.045)
        for x, y in ((x0, y0), (x1, y1)):
            a.circle(x, y, 0.045, BONE, width=0.016)
    sk = skull()
    a.im.alpha_composite(sk.resize((a.W, a.H)).crop((0, 0, a.W, a.H)), (0, -int(0.05 * S)))
    return a.done()


def dagger(handle=RED):
    a = Art(0.6, 1.0)
    a.shape([(0.30, 0.12), (0.34, 0.55), (0.26, 0.55)], GREY, width=0.02)       # the blade
    a.line([(0.30, 0.16), (0.30, 0.53)], width=0.008)
    a.shape([(0.12, 0.55), (0.48, 0.55), (0.48, 0.60), (0.12, 0.60)], YELLOW, width=0.018)  # the guard
    a.shape([(0.26, 0.60), (0.34, 0.60), (0.34, 0.80), (0.26, 0.80)], handle, width=0.018)
    for y in np.linspace(0.63, 0.77, 5):
        a.line([(0.26, y), (0.34, y + 0.02)], width=0.008)
    a.circle(0.30, 0.84, 0.045, YELLOW, width=0.018)
    return a.done()


def heart_banner(text='MOM', colour=RED):
    a = Art(1.0, 0.85)
    a.shape(heart_pts(0.5, 0.40, 0.33), colour, width=0.026)
    a.line(ring(0.42, 0.30, 0.08, 0.06, np.pi * 1.1, np.pi * 1.6, 12), colour=BONE, width=0.022)  # highlight
    band = [(0.06, 0.40), (0.94, 0.40), (0.94, 0.55), (0.06, 0.55)]
    a.shape([(0.0, 0.44), (0.10, 0.44), (0.10, 0.60), (0.0, 0.60), (0.04, 0.52)], YELLOW, width=0.016)
    a.shape([(1.0, 0.44), (0.90, 0.44), (0.90, 0.60), (1.0, 0.60), (0.96, 0.52)], YELLOW, width=0.016)
    a.shape(band, BONE, width=0.018)
    a.text(text, 0.5, 0.475, 0.10 if len(text) < 6 else 0.07)
    return a.done()


def anchor(rope=YELLOW):
    a = Art(0.8, 1.0)
    a.circle(0.40, 0.14, 0.06, None, width=0.028)
    a.shape([(0.37, 0.20), (0.43, 0.20), (0.43, 0.82), (0.37, 0.82)], GREY, width=0.02)
    a.shape([(0.18, 0.28), (0.62, 0.28), (0.62, 0.33), (0.18, 0.33)], GREY, width=0.02)
    a.line(ring(0.40, 0.66, 0.26, 0.20, 0.05, np.pi - 0.05, 30), colour=INK, width=0.06)
    a.line(ring(0.40, 0.66, 0.26, 0.20, 0.05, np.pi - 0.05, 30), colour=GREY, width=0.035)
    for x, s in ((0.66, 1), (0.14, -1)):
        a.shape([(x, 0.62), (x + s * 0.09, 0.66), (x + s * 0.01, 0.74)], GREY, width=0.018)
    rope_pts = [(0.40 + 0.20 * np.sin(t * 2.4), 0.20 + t * 0.52) for t in np.linspace(0, 1, 40)]
    a.line(rope_pts, colour=INK, width=0.034)
    a.line(rope_pts, colour=rope, width=0.02)
    return a.done()


def snake(body=GREEN):
    a = Art()
    t = np.linspace(0, 1, 120)
    xs = 0.5 + 0.30 * np.sin(t * np.pi * 2.2)
    ys = 0.90 - t * 0.72
    w = 0.012 + 0.05 * np.sin(np.pi * np.clip(t * 1.05, 0, 1)) ** 0.6
    for k in range(len(t)):
        a.circle(xs[k], ys[k], w[k] + 0.012, INK, line=None)
    for k in range(len(t)):
        a.circle(xs[k], ys[k], w[k], body, line=None)
    for k in range(4, len(t) - 6, 6):
        a.line([(xs[k] - w[k] * 0.7, ys[k]), (xs[k] + w[k] * 0.7, ys[k] - 0.01)], colour=YELLOW, width=0.012)
    hx, hy = xs[-1], ys[-1]
    a.shape(ring(hx, hy - 0.02, 0.07, 0.05), body, width=0.02)
    a.circle(hx + 0.02, hy - 0.035, 0.012, YELLOW, width=0.006)
    a.line([(hx, hy - 0.07), (hx - 0.01, hy - 0.13), (hx - 0.04, hy - 0.16)], colour=RED, width=0.009)
    a.line([(hx - 0.01, hy - 0.13), (hx + 0.02, hy - 0.16)], colour=RED, width=0.009)
    return a.done()


def web():
    a = Art()
    cx, cy = 0.5, 0.5
    spokes = [np.pi * 2 * k / 9 + 0.15 for k in range(9)]
    for ang in spokes:
        a.line([(cx, cy), (cx + np.cos(ang) * 0.47, cy + np.sin(ang) * 0.47)], width=0.010)
    for r in (0.1, 0.19, 0.28, 0.37, 0.45):
        for k in range(9):
            a0, a1 = spokes[k], spokes[(k + 1) % 9] + (2 * np.pi if k == 8 else 0)
            p0 = (cx + np.cos(a0) * r, cy + np.sin(a0) * r)
            p1 = (cx + np.cos(a1) * r, cy + np.sin(a1) * r)
            mid = ((p0[0] + p1[0]) / 2 - (np.cos((a0 + a1) / 2)) * r * 0.12, (p0[1] + p1[1]) / 2 - np.sin((a0 + a1) / 2) * r * 0.12)
            a.line(bez(p0, mid, p1, n=10), width=0.009)
    return a.done()


def spider():
    a = Art()
    for s in (1, -1):
        for k, (ang, bend) in enumerate(((-0.9, 0.3), (-0.35, 0.2), (0.25, -0.2), (0.8, -0.3))):
            kx, ky = 0.5 + s * 0.20, 0.45 + ang * 0.18
            a.line([(0.5 + s * 0.05, 0.47 + ang * 0.05), (kx, ky - 0.08), (0.5 + s * 0.36, ky + 0.12 + bend * 0.1)], width=0.016)
    a.ellipse(0.5, 0.40, 0.07, 0.06, INK, line=None)
    a.ellipse(0.5, 0.56, 0.10, 0.12, INK, line=None)
    a.shape([(0.5, 0.50), (0.47, 0.56), (0.5, 0.62), (0.53, 0.56)], RED, line=None)   # the hourglass
    return a.done()


def nautical_star(c2=RED):
    a = Art()
    cx, cy = 0.5, 0.5
    outer = [(cx + np.cos(-np.pi / 2 + k * 2 * np.pi / 5) * 0.44, cy + np.sin(-np.pi / 2 + k * 2 * np.pi / 5) * 0.44) for k in range(5)]
    inner = [(cx + np.cos(-np.pi / 2 + np.pi / 5 + k * 2 * np.pi / 5) * 0.18, cy + np.sin(-np.pi / 2 + np.pi / 5 + k * 2 * np.pi / 5) * 0.18) for k in range(5)]
    for k in range(5):
        a.shape([(cx, cy), outer[k], inner[k]], INK, width=0.016)
        a.shape([(cx, cy), inner[k - 1], outer[k]], c2, width=0.016)
    return a.done()


def lightning():
    a = Art(0.7, 1.0)
    a.shape([(0.42, 0.04), (0.16, 0.50), (0.34, 0.50), (0.20, 0.96), (0.56, 0.40), (0.38, 0.40), (0.56, 0.04)], YELLOW, width=0.024)
    return a.done()


def mushroom_cloud():
    """The bomb: a wide boiling cap, a ring of cloud round a column, a skirt of dust at the foot."""
    a = Art()
    a.shape([(0.44, 0.40), (0.56, 0.40), (0.60, 0.80), (0.40, 0.80)], ORANGE, width=0.02)     # the column
    for x in np.linspace(0.24, 0.76, 6):                                                       # the dust skirt
        a.circle(x, 0.86, 0.075, GREY, width=0.018)
    a.shape(ring(0.5, 0.58, 0.20, 0.035), GREY, width=0.016)                                   # the ring cloud
    for x, y, r, c in ((0.22, 0.32, 0.09, RED), (0.78, 0.32, 0.09, RED), (0.32, 0.26, 0.11, ORANGE),
                       (0.68, 0.26, 0.11, ORANGE), (0.5, 0.22, 0.14, ORANGE), (0.40, 0.36, 0.10, RED),
                       (0.60, 0.36, 0.10, RED), (0.5, 0.36, 0.10, ORANGE), (0.42, 0.17, 0.07, YELLOW),
                       (0.58, 0.17, 0.07, YELLOW)):
        a.circle(x, y, r, c, width=0.02)
    for x in (0.47, 0.5, 0.53):
        a.line([(x, 0.46), (x + 0.004, 0.76)], colour=YELLOW, width=0.010)
    return a.done()


def radiation():
    a = Art()
    a.circle(0.5, 0.5, 0.44, YELLOW, width=0.03)
    for k in range(3):
        a0 = -np.pi / 2 + k * 2 * np.pi / 3 - np.pi / 6
        pts = [(0.5 + np.cos(t) * r, 0.5 + np.sin(t) * r) for r, ts in ((0.10, np.linspace(a0, a0 + np.pi / 3, 8)),
                                                                     (0.36, np.linspace(a0 + np.pi / 3, a0, 12)))
               for t in ts]
        a.shape(pts, INK, line=None)
    a.circle(0.5, 0.5, 0.06, INK, line=None)
    return a.done()


def nuka_cap():
    a = Art()
    teeth = [(0.5 + np.cos(t) * (0.44 if k % 2 else 0.40), 0.5 + np.sin(t) * (0.44 if k % 2 else 0.40))
             for k, t in enumerate(np.linspace(0, 2 * np.pi, 49)[:-1])]
    a.shape(teeth, RED, width=0.02)
    a.circle(0.5, 0.5, 0.34, None, width=0.012)
    a.line(bez((0.22, 0.58), (0.5, 0.30), (0.78, 0.46)), colour=BONE, width=0.05)
    a.text('Nuka', 0.5, 0.52, 0.17, font='script', colour=INK)
    return a.done()


def cherries():
    a = Art()
    a.line(bez((0.36, 0.62), (0.40, 0.30), (0.56, 0.16)), width=0.022)
    a.line(bez((0.64, 0.66), (0.62, 0.36), (0.56, 0.16)), width=0.022)
    leaf(a, 0.56, 0.17, -0.3, 0.26, 0.08)
    for x, y in ((0.34, 0.72), (0.64, 0.76)):
        a.circle(x, y, 0.15, RED, width=0.024)
        a.line(ring(x - 0.04, y - 0.04, 0.07, 0.06, np.pi * 1.1, np.pi * 1.5, 10), colour=BONE, width=0.02)
    return a.done()


def eye():
    a = Art(1.0, 0.8)
    lid = bez((0.10, 0.40), (0.5, 0.05), (0.90, 0.40)) + bez((0.90, 0.40), (0.5, 0.75), (0.10, 0.40))[1:]
    a.shape(lid, BONE, width=0.024)
    a.circle(0.5, 0.40, 0.14, BLUE, width=0.02)
    a.circle(0.5, 0.40, 0.06, INK, line=None)
    a.circle(0.46, 0.36, 0.022, BONE, line=None)
    for ang in np.linspace(np.pi * 1.1, np.pi * 1.9, 7):
        a.line([(0.5 + np.cos(ang) * 0.42, 0.40 + np.sin(ang) * 0.35), (0.5 + np.cos(ang) * 0.50, 0.40 + np.sin(ang) * 0.45)], width=0.012)
    return a.done()


def wolf():
    """A geometric wolf's head, facing out: ears, the brow, the long snout, built from facets."""
    a = Art()
    G1, G2, G3 = (70, 74, 80), (120, 126, 134), (190, 192, 196)
    L = [(0.5, 0.30), (0.30, 0.10), (0.26, 0.36), (0.18, 0.52), (0.30, 0.60), (0.40, 0.80), (0.5, 0.92)]
    R = [(1 - x, y) for x, y in L]
    a.shape(L + R[::-1], G2, width=0.024)
    for side in (L, R):
        a.shape([side[1], side[2], side[0]], G1, width=0.014)                    # ears
        a.shape([side[2], side[3], side[4], (0.5, 0.56), side[0]], G3, width=0.012)  # cheeks
        a.shape([side[4], side[5], side[6], (0.5, 0.56)], G2, width=0.012)
    for x in (0.40, 0.60):
        a.shape([(x - 0.05, 0.44), (x + 0.05, 0.46 if x < 0.5 else 0.42), (x, 0.48)], YELLOW, width=0.012)
    a.shape([(0.45, 0.84), (0.55, 0.84), (0.5, 0.90)], INK, line=None)
    return a.done()


def koi(body=ORANGE):
    """A koi turning: a heavy body in an S, a round head with its whiskers, a fanned tail, red patches, scales."""
    a = Art()
    t = np.linspace(0, 1, 70)
    spine = [(0.42 + 0.20 * np.sin(v * np.pi * 1.05 + 0.3), 0.12 + v * 0.62) for v in t]
    wid = 0.15 * np.sin(np.pi * np.clip(0.18 + t * 0.85, 0, 1)) ** 0.9 + 0.018
    left, right = [], []
    for k in range(len(t)):
        x0, y0 = spine[max(k - 1, 0)]
        x1, y1 = spine[min(k + 1, len(t) - 1)]
        dx, dy = x1 - x0, y1 - y0
        nrm = np.hypot(dx, dy) or 1
        nx, ny = -dy / nrm, dx / nrm
        left.append((spine[k][0] + nx * wid[k], spine[k][1] + ny * wid[k]))
        right.append((spine[k][0] - nx * wid[k], spine[k][1] - ny * wid[k]))
    tx, ty = spine[-1]
    a.shape([(tx, ty - 0.02), (tx - 0.20, ty + 0.10), (tx - 0.10, ty + 0.20), (tx, ty + 0.10),
             (tx + 0.10, ty + 0.22), (tx + 0.16, ty + 0.10)], body, width=0.018)          # the tail
    for k in (18, 36):                                                                     # pectoral fins
        a.shape([left[k], (left[k][0] - 0.16, left[k][1] + 0.02), (left[k][0] - 0.06, left[k][1] + 0.10)], body, width=0.014)
    a.shape(left + right[::-1], body, width=0.024)
    for k0, k1 in ((12, 24), (34, 44)):                                                    # red patches
        a.shape(left[k0:k1] + [spine[k1]] + [spine[k0]], RED, line=None)
    for k in range(14, 60, 5):
        for f in (-0.5, 0.0, 0.5):
            x, y = spine[k]
            a.line(ring(x + f * wid[k] * 0.9, y, wid[k] * 0.22, 0.022, 0.2, np.pi - 0.2, 8), width=0.007)   # scales
    hx, hy = spine[2]
    a.circle(hx + 0.05, hy + 0.01, 0.018, INK, line=None)                                   # the eye
    a.line(bez((hx - 0.05, hy - 0.06), (hx - 0.12, hy - 0.10), (hx - 0.16, hy - 0.04)), width=0.008)   # whiskers
    a.line(bez((hx + 0.03, hy - 0.08), (hx + 0.06, hy - 0.16), (hx + 0.12, hy - 0.16)), width=0.008)
    return a.done()


def butterfly(wing=BLUE):
    a = Art()
    t = np.linspace(0, 2 * np.pi, 400)
    r = np.exp(np.sin(t)) - 2 * np.cos(4 * t) + np.sin((2 * t - np.pi) / 24) ** 5
    x, y = r * np.cos(t), -r * np.sin(t)
    pts = [(0.5 + xi * 0.105, 0.55 + yi * 0.105) for xi, yi in zip(x, y)]
    a.shape(pts, wing, width=0.02)
    for s in (1, -1):
        a.circle(0.5 + s * 0.20, 0.38, 0.05, YELLOW, width=0.012)
        a.circle(0.5 + s * 0.13, 0.62, 0.03, BONE, width=0.01)
    a.ellipse(0.5, 0.55, 0.025, 0.17, INK, line=None)
    a.line(bez((0.5, 0.39), (0.47, 0.30), (0.42, 0.26)), width=0.01)
    a.line(bez((0.5, 0.39), (0.53, 0.30), (0.58, 0.26)), width=0.01)
    return a.done()


def grenade():
    a = Art(0.8, 1.0)
    a.shape(ring(0.40, 0.58, 0.24, 0.30), GREEN, width=0.026)
    for x in (0.28, 0.40, 0.52):
        a.line(ring(x, 0.58, 0.04, 0.28, -np.pi / 2, np.pi / 2, 16), width=0.01)
    for y in (0.42, 0.54, 0.66, 0.78):
        a.line([(0.18, y), (0.62, y)], width=0.01)
    a.shape([(0.32, 0.22), (0.48, 0.22), (0.48, 0.30), (0.32, 0.30)], GREY, width=0.016)
    a.shape([(0.46, 0.22), (0.66, 0.30), (0.62, 0.36), (0.46, 0.28)], GREY, width=0.014)        # the lever
    a.circle(0.28, 0.20, 0.06, None, width=0.016)                                               # the pin ring
    return a.done()


def tombstone(text='RIP'):
    a = Art(0.8, 1.0)
    a.shape(ring(0.40, 0.36, 0.26, 0.22, np.pi, 2 * np.pi, 30) + [(0.66, 0.84), (0.14, 0.84)], GREY, width=0.026)
    a.text(text, 0.40, 0.50, 0.15, font='blackletter')
    for x in np.linspace(0.06, 0.74, 14):
        a.line([(x, 0.86), (x + 0.02, 0.76)], colour=GREEN, width=0.014)
    return a.done()


def eight_ball():
    a = Art()
    a.circle(0.5, 0.5, 0.40, INK, line=None)
    a.circle(0.5, 0.44, 0.16, BONE, width=0.012)
    a.text('8', 0.5, 0.44, 0.22, font='stencil')
    a.line(ring(0.40, 0.36, 0.25, 0.22, np.pi * 1.1, np.pi * 1.35, 8), colour=GREY, width=0.02)
    return a.done()


def compass():
    a = Art()
    a.circle(0.5, 0.5, 0.42, None, width=0.024)
    a.circle(0.5, 0.5, 0.36, None, width=0.010)
    for k in range(8):
        ang = -np.pi / 2 + k * np.pi / 4
        r = 0.40 if k % 2 == 0 else 0.26
        c = (RED if k == 0 else INK) if k % 2 == 0 else GREY
        p = (0.5 + np.cos(ang) * r, 0.5 + np.sin(ang) * r)
        l_ = (0.5 + np.cos(ang - 0.35) * 0.08, 0.5 + np.sin(ang - 0.35) * 0.08)
        r_ = (0.5 + np.cos(ang + 0.35) * 0.08, 0.5 + np.sin(ang + 0.35) * 0.08)
        a.shape([l_, p, r_, (0.5, 0.5)], c, width=0.012)
    a.text('N', 0.5, 0.04, 0.08, font='stencil')
    return a.done()


def pinup(colour=RED):
    """A sitting pin-up silhouette, the mud-flap pose: leaning back on her hands, one knee up, hair long."""
    a = Art(0.8, 1.0)
    body = (bez((0.30, 0.18), (0.24, 0.30), (0.30, 0.42)) + bez((0.30, 0.42), (0.20, 0.50), (0.26, 0.60))[1:] +
            bez((0.26, 0.60), (0.40, 0.66), (0.55, 0.62))[1:] + bez((0.55, 0.62), (0.68, 0.48), (0.62, 0.40))[1:] +
            [(0.58, 0.42)] + bez((0.58, 0.42), (0.60, 0.52), (0.50, 0.56))[1:] + [(0.66, 0.84), (0.60, 0.86)] +
            bez((0.60, 0.86), (0.44, 0.64), (0.36, 0.62))[1:] + bez((0.36, 0.62), (0.30, 0.74), (0.20, 0.86))[1:] +
            [(0.14, 0.84)] + bez((0.14, 0.84), (0.22, 0.70), (0.20, 0.58))[1:] + bez((0.20, 0.58), (0.16, 0.44), (0.24, 0.30))[1:] +
            bez((0.24, 0.30), (0.20, 0.20), (0.28, 0.14))[1:])
    a.shape(body, INK, line=None)
    a.circle(0.30, 0.12, 0.06, INK, line=None)                     # the head
    a.shape(bez((0.26, 0.10), (0.14, 0.18), (0.18, 0.34)) + [(0.24, 0.24), (0.30, 0.08)], INK, line=None)   # the hair
    a.shape([(0.26, 0.60), (0.40, 0.66), (0.36, 0.62), (0.30, 0.58)], colour, line=None)   # a red shoe/accent
    return a.done()


# ---- redrawn for alasdairn's review, 2026-10-09: an eagle that is an eagle, fire that is fire, a Colt Python,
#      a real swallow (the first versions were "a 4th grader in MS Paint", "triangles, not fire")

DARK_BROWN, LIGHT_BROWN = (78, 44, 22), (156, 104, 56)
DEEP_RED, DEEP_BLUE, STEEL, STEEL_DARK, WOOD, WOOD_DARK = (120, 16, 20), (22, 44, 98), (120, 128, 138), (70, 76, 86), (118, 66, 30), (78, 40, 18)


def whip(a, seq, side_pts, colour=INK, n=14, length=0.03, width=0.004):
    """Whip shading: short tapering strokes from a line (seq) towards side_pts' direction."""
    for k in range(n):
        t = k / max(n - 1, 1)
        i = min(int(t * (len(seq) - 1)), len(seq) - 1)
        x, y = seq[i]
        dx, dy = side_pts
        L = length * (0.6 + 0.4 * np.sin(t * np.pi))
        a.line([(x, y), (x + dx * L, y + dy * L)], colour, width=width)


def feather(a, base, ang, length, width, fill, shade=None, quill=True):
    dx, dy = np.cos(ang), np.sin(ang)
    nx, ny = -dy, dx
    tip = (base[0] + dx * length, base[1] + dy * length)
    s1 = bez(base, (base[0] + dx * length * 0.45 + nx * width, base[1] + dy * length * 0.45 + ny * width), tip, n=16)
    s2 = bez(tip, (base[0] + dx * length * 0.45 - nx * width, base[1] + dy * length * 0.45 - ny * width), base, n=16)
    a.shape(s1 + s2[1:], fill, width=0.009)
    if shade:  # the inner half darker
        a.shape(bez(base, (base[0] + dx * length * 0.45 + nx * width * 0.9, base[1] + dy * length * 0.45 + ny * width * 0.9), tip, n=12)
                + [(base[0] + dx * length * 0.6, base[1] + dy * length * 0.6)], shade, line=None)
    if quill:
        a.line([base, (base[0] + dx * length * 0.85, base[1] + dy * length * 0.85)], INK, width=0.005)


def eagle(head=BONE):
    """A traditional flash eagle, wings spread and raised: layered primaries and secondaries with quills and a
    shaded half, scalloped coverts on a lit wing band, a feathered body, a white head with a hooked beak and a hard
    brow, a fanned white tail, talons gripping."""
    a = Art(1.0, 0.8)
    for s in (1, -1):
        arm = bez((0.5 + s * 0.06, 0.36), (0.5 + s * 0.17, 0.17), (0.5 + s * 0.28, 0.11), (0.5 + s * 0.37, 0.07), n=40)
        for k in range(7):
            t = 0.46 + k * 0.08
            bx, by = arm[min(int(t * 39), 39)]
            _f = 0.12 + k * 0.12
            feather(a, (bx, by + 0.02), np.pi / 2 - s * _f, 0.25 - k * 0.006, 0.050, DARK_BROWN, (50, 26, 12))
        for k in range(6):
            t = 0.10 + k * 0.07
            bx, by = arm[int(t * 39)]
            feather(a, (bx, by + 0.02), np.pi / 2 - s * (0.03 + k * 0.03), 0.20 - k * 0.008, 0.044, BROWN, DARK_BROWN)
        band = arm + [(x, y + 0.075 + 0.05 * (1 - i / 39)) for i, (x, y) in enumerate(arm)][::-1]
        a.shape(band, LIGHT_BROWN, width=0.014)
        for row, off in ((0, 0.035), (1, 0.075)):
            for i in range(3 + row * 2, 38, 5):
                x, y = arm[i]
                a.line(bez((x - 0.022, y + off), (x, y + off + 0.028), (x + 0.022, y + off), n=10), INK, width=0.007)
        whip(a, arm[2:38], (0, 1), n=16, length=0.022, width=0.004)
    for k, ang in enumerate(np.linspace(np.pi / 2 - 0.5, np.pi / 2 + 0.5, 5)):
        feather(a, (0.5, 0.58), ang, 0.21 - abs(k - 2) * 0.02, 0.042, BONE, (210, 200, 176))
    body = bez((0.5, 0.30), (0.62, 0.36), (0.60, 0.58), (0.5, 0.66), n=30) + bez((0.5, 0.66), (0.40, 0.58), (0.38, 0.36), (0.5, 0.30), n=30)[1:]
    a.shape(body, BROWN, width=0.020)
    a.shape(bez((0.5, 0.31), (0.57, 0.37), (0.56, 0.57), (0.5, 0.65), n=20) + [(0.5, 0.31)], DARK_BROWN, line=None)
    for y in (0.40, 0.46, 0.52, 0.58):
        for x in (0.455, 0.50, 0.545):
            if abs(x - 0.5) < 0.07 - (y - 0.40) * 0.25:
                a.line(bez((x - 0.02, y), (x, y + 0.024), (x + 0.02, y), n=8), INK, width=0.006)
    for s in (1, -1):
        a.shape([(0.5 + s * 0.025, 0.60), (0.5 + s * 0.055, 0.60), (0.5 + s * 0.06, 0.67), (0.5 + s * 0.025, 0.67)], YELLOW, width=0.010)
        for k in range(3):
            x0 = 0.5 + s * (0.022 + k * 0.016)
            a.line(bez((x0, 0.67), (x0 + s * 0.006, 0.70), (x0 + s * 0.012, 0.705), n=6), INK, width=0.010)
    a.shape(bez((0.44, 0.31), (0.42, 0.20), (0.52, 0.16), (0.58, 0.21), n=24) + bez((0.58, 0.21), (0.60, 0.25), (0.57, 0.30), (0.52, 0.32), n=16)[1:],
            head, width=0.018)
    for k in range(4):  # head feathers at the neck
        x = 0.455 + k * 0.025
        a.line(bez((x, 0.30), (x + 0.008, 0.315), (x + 0.016, 0.30), n=6), (170, 160, 140), width=0.006)
    beak = bez((0.575, 0.205), (0.64, 0.20), (0.668, 0.235), (0.64, 0.262), n=14) + [(0.62, 0.245), (0.585, 0.25)]
    a.shape(beak, YELLOW, width=0.012)
    a.line([(0.585, 0.228), (0.63, 0.232)], INK, width=0.006)
    a.circle(0.545, 0.215, 0.012, (196, 120, 30), width=0.008)
    a.circle(0.548, 0.215, 0.006, INK, line=None)
    a.line([(0.522, 0.196), (0.572, 0.204)], INK, width=0.011)
    return a.done()


def _tongue(x0, base, height, width, phase, amp, curl=0.0, n=40):
    """One flame tongue: a wavy centre line rising from the base, its width tapering to a point, the tip curling."""
    t = np.linspace(0, 1, n)
    cx = x0 + amp * np.sin(phase + t * 3.0) * t + curl * t ** 3
    cy = base - t * height
    w = width * (1 - t) ** 0.75 * (1 + 0.18 * np.sin(t * 8 + phase))
    dx, dy = np.gradient(cx), np.gradient(cy)
    nrm = np.hypot(dx, dy) + 1e-9
    nx, ny = -dy / nrm, dx / nrm
    left = [(cx[i] + nx[i] * w[i], cy[i] + ny[i] * w[i]) for i in range(n)]
    right = [(cx[i] - nx[i] * w[i], cy[i] - ny[i] * w[i]) for i in range(n)]
    return left + right[::-1]


def flames():
    """Traditional tattoo fire: wavy tongues licking up from one body of flame and curling over at their tips, red
    outside, orange within, a yellow heart -- not triangles."""
    a = Art(1.0, 0.8)
    base = 0.74
    spec = [(0.16, 0.36, 0.09, 0.4, 0.03, -0.05), (0.30, 0.56, 0.10, 2.2, 0.05, 0.06), (0.47, 0.66, 0.11, 4.0, 0.06, -0.07),
            (0.63, 0.54, 0.10, 1.1, 0.05, 0.07), (0.78, 0.44, 0.09, 3.1, 0.04, -0.05), (0.89, 0.28, 0.07, 5.0, 0.03, 0.04)]
    body = bez((0.06, base), (0.08, base - 0.10), (0.20, base - 0.12), n=8) + [(0.80, base - 0.12)] + bez((0.80, base - 0.12), (0.92, base - 0.10), (0.94, base), n=8)[1:] + bez((0.94, base), (0.50, base + 0.05), (0.06, base), n=16)[1:]
    a.shape(body, RED, width=0.018)
    for x, h, w, ph, amp, curl in spec:
        a.shape(_tongue(x, base - 0.04, h, w, ph, amp, curl), RED, width=0.016)
    a.shape(body, RED, line=None)
    for x, h, w, ph, amp, curl in spec:
        a.shape(_tongue(x, base - 0.02, h * 0.68, w * 0.62, ph + 0.4, amp * 0.8, curl * 0.6), ORANGE, line=None)
    a.shape(bez((0.12, base), (0.30, base - 0.08), (0.50, base - 0.09), (0.88, base), n=20) + bez((0.88, base), (0.50, base + 0.02), (0.12, base), n=10)[1:], ORANGE, line=None)
    for x, h, w, ph, amp, curl in spec[1:-1]:
        a.shape(_tongue(x, base, h * 0.38, w * 0.38, ph + 0.8, amp * 0.6, curl * 0.3), YELLOW, line=None)
    return a.done()


def revolver():
    """A Colt Python in profile: the ventilated rib on the six-inch barrel, the full-length ejector shroud beneath
    it, the front sight ramp, a fluted cylinder, the frame and the hammer spur, the trigger in its guard, a
    checkered walnut grip with its medallion."""
    a = Art(1.0, 0.62)
    # barrel with the vent rib (slots) and the ejector shroud
    a.shape([(0.06, 0.20), (0.56, 0.20), (0.56, 0.37), (0.10, 0.37), (0.06, 0.34)], STEEL, width=0.016)
    a.shape([(0.06, 0.20), (0.56, 0.20), (0.56, 0.255), (0.06, 0.255)], STEEL_DARK, width=0.010)    # the rib
    for k in range(7):
        x = 0.12 + k * 0.06
        a.shape([(x, 0.21), (x + 0.03, 0.21), (x + 0.03, 0.245), (x, 0.245)], INK, line=None)      # rib vents
    a.shape([(0.06, 0.17), (0.11, 0.17), (0.12, 0.20), (0.06, 0.20)], STEEL_DARK, width=0.010)      # front sight ramp
    a.line([(0.10, 0.31), (0.55, 0.31)], STEEL_DARK, width=0.008)                                   # shroud line
    a.circle(0.085, 0.29, 0.012, INK, line=None)                                                     # the muzzle
    # frame
    frame = [(0.55, 0.18), (0.80, 0.18), (0.84, 0.24), (0.82, 0.42), (0.74, 0.44), (0.66, 0.44), (0.55, 0.40)]
    a.shape(frame, STEEL, width=0.018)
    # cylinder with flutes
    a.shape([(0.58, 0.215), (0.71, 0.215), (0.715, 0.385), (0.58, 0.385)], STEEL, width=0.014)
    for y in (0.245, 0.29, 0.335):
        a.shape([(0.595, y), (0.695, y), (0.695, y + 0.022), (0.595, y + 0.022)], STEEL_DARK, line=None)
    # rear sight and hammer spur
    a.shape([(0.76, 0.18), (0.80, 0.18), (0.80, 0.16), (0.77, 0.16)], STEEL_DARK, width=0.008)
    a.shape([(0.795, 0.20), (0.815, 0.135), (0.85, 0.105), (0.895, 0.10), (0.885, 0.125), (0.85, 0.15), (0.83, 0.215)], STEEL_DARK, width=0.010)
    # trigger guard and trigger
    a.line(bez((0.66, 0.44), (0.66, 0.54), (0.76, 0.55), (0.78, 0.45), n=18), INK, width=0.016)
    a.shape(bez((0.725, 0.43), (0.715, 0.49), (0.70, 0.515), n=8) + [(0.715, 0.515), (0.735, 0.44)], STEEL_DARK, width=0.008)
    # the grip: walnut, checkered, a medallion
    grip = [(0.78, 0.40), (0.84, 0.30), (0.90, 0.33), (0.96, 0.56), (0.92, 0.60), (0.82, 0.60), (0.78, 0.50)]
    a.shape(grip, WOOD, width=0.018)
    hatch = Image.new('RGBA', a.im.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for k in range(-6, 14):
        x = 0.78 + k * 0.016
        hd.line([a.p(x, 0.30), a.p(x + 0.12, 0.62)], fill=WOOD_DARK + (255,), width=int(0.004 * S))
        hd.line([a.p(x + 0.12, 0.30), a.p(x, 0.62)], fill=WOOD_DARK + (255,), width=int(0.004 * S))
    mask = Image.new('L', a.im.size, 0)
    ImageDraw.Draw(mask).polygon(a.pts([(0.80, 0.42), (0.845, 0.33), (0.89, 0.355), (0.94, 0.55), (0.91, 0.58), (0.83, 0.58), (0.80, 0.50)]), fill=255)
    hatch.putalpha(Image.fromarray(np.minimum(np.asarray(hatch.getchannel('A')), np.asarray(mask))))
    a.im.alpha_composite(hatch)
    a.circle(0.87, 0.36, 0.015, (196, 160, 70), width=0.006)
    # light on the barrel
    a.line([(0.14, 0.275), (0.50, 0.275)], (190, 196, 204), width=0.008)
    return a.done()


def swallow(back=BLUE):
    """A traditional swallow in flight: the long forked tail, swept pointed wings with banded flight feathers, a
    deep blue back and crown, the red throat, a cream belly, a bright eye."""
    a = Art()
    # far wing (behind), then tail, body, near wing
    far = bez((0.46, 0.44), (0.56, 0.26), (0.74, 0.14), (0.92, 0.10), n=20) + bez((0.92, 0.10), (0.78, 0.24), (0.64, 0.36), (0.54, 0.46), n=20)[1:]
    a.shape(far, DEEP_BLUE, width=0.018)
    for s, (tx, ty) in ((0, (0.92, 0.80)), (1, (0.82, 0.88))):     # the fork
        a.shape(bez((0.62, 0.58), (0.74, 0.66), (tx - 0.04, ty - 0.04), (tx, ty), n=14) + bez((tx, ty), (tx - 0.10, ty - 0.10), (0.66, 0.66), (0.58, 0.62), n=14)[1:],
                back, width=0.016)
    body = bez((0.16, 0.46), (0.26, 0.36), (0.46, 0.38), (0.62, 0.54), n=24) + bez((0.62, 0.54), (0.66, 0.62), (0.50, 0.62), (0.30, 0.58), n=16)[1:] + bez((0.30, 0.58), (0.20, 0.55), (0.16, 0.50), n=8)[1:]
    a.shape(body, back, width=0.020)
    a.shape(bez((0.30, 0.58), (0.44, 0.62), (0.58, 0.60), n=14) + bez((0.58, 0.60), (0.50, 0.52), (0.34, 0.50), n=12)[1:], BONE, width=0.012)   # belly
    a.shape(bez((0.18, 0.48), (0.24, 0.43), (0.31, 0.45), n=10) + bez((0.31, 0.45), (0.33, 0.52), (0.30, 0.58), n=10)[1:] + [(0.20, 0.53)], RED, width=0.012)  # throat
    a.shape([(0.16, 0.465), (0.09, 0.48), (0.16, 0.495)], INK, width=0.008)                     # the beak
    a.circle(0.225, 0.455, 0.016, BONE, width=0.006)
    a.circle(0.228, 0.455, 0.008, INK, line=None)
    near = bez((0.40, 0.44), (0.50, 0.22), (0.66, 0.08), (0.86, 0.02), n=22) + bez((0.86, 0.02), (0.70, 0.18), (0.58, 0.34), (0.50, 0.48), n=22)[1:]
    a.shape(near, back, width=0.020)
    for k in range(5):                                         # banded flight feathers
        t = 0.35 + k * 0.13
        p0 = bez((0.40, 0.44), (0.50, 0.22), (0.66, 0.08), (0.86, 0.02), n=40)[int(t * 39)]
        p1 = bez((0.50, 0.48), (0.58, 0.34), (0.70, 0.18), (0.86, 0.02), n=40)[int(t * 39)]
        a.line([p0, p1], INK, width=0.007)
    a.shape(bez((0.42, 0.42), (0.50, 0.26), (0.62, 0.16), n=12) + bez((0.62, 0.16), (0.56, 0.30), (0.48, 0.44), n=12)[1:], DEEP_BLUE, line=None)  # shade
    return a.done()


def swallow_pair():
    """Two swallows facing each other over a banner: the sailor's classic."""
    a = Art(1.0, 0.7)
    sw = swallow().resize((int(a.W * 0.5), int(a.W * 0.5)))
    a.im.alpha_composite(sw, (int(a.W * 0.0), 0))
    a.im.alpha_composite(sw.transpose(Image.FLIP_LEFT_RIGHT), (int(a.W * 0.5), 0))
    return a.done()


MOTIFS = {
    'rose': rose, 'skull': skull, 'skull_bones': skull_bones, 'dagger': dagger, 'heart_banner': heart_banner,
    'swallow': swallow, 'swallow_pair': swallow_pair, 'anchor': anchor, 'snake': snake, 'web': web, 'spider': spider,
    'nautical_star': nautical_star, 'lightning': lightning, 'mushroom_cloud': mushroom_cloud, 'radiation': radiation,
    'nuka_cap': nuka_cap, 'cherries': cherries, 'eye': eye, 'flames': flames, 'wolf': wolf, 'eagle': eagle, 'koi': koi,
    'butterfly': butterfly, 'revolver': revolver, 'grenade': grenade, 'tombstone': tombstone, 'eight_ball': eight_ball,
    'compass': compass,
}


# ---------------------------------------------------------------- onto the skin


def project_rgba(m, design, spot, side=0, width=6.0, rotate=0.0, alpha=0.92, crude=0.0, seed=0, faded=False):
    """A colour design (RGBA) flat on the skin around a spot (decals.anchor), width game units across. Returns
    (rgb, alpha) for make_marks. faded: older ink, colours greyed and blurred a touch."""
    P = Painter(m)
    rgb, a_out = blank(m)
    c, n, up = decals.anchor(m, spot, side)
    up = up - n * (up @ n)
    if np.linalg.norm(up) < 1e-3:
        up = np.array((0.0, 0.0, 1.0)) - n * n[2]
    up = up / np.linalg.norm(up)
    right = np.cross(up, n)
    if rotate:
        cr, sr = np.cos(rotate), np.sin(rotate)
        up, right = up * cr + right * sr, right * cr - up * sr
    if faded:
        design = design.filter(ImageFilter.GaussianBlur(1.5))
    img = np.asarray(design.convert('RGBA'), dtype=np.float64) / 255.0
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
    xi = np.clip((u[ok] * img.shape[1]).astype(int), 0, img.shape[1] - 1)
    yi = np.clip((v[ok] * img.shape[0]).astype(int), 0, img.shape[0] - 1)
    col = np.zeros((len(idx), 3))
    al = np.zeros(len(idx))
    col[ok] = img[yi, xi, :3]
    al[ok] = img[yi, xi, 3]
    if faded:
        grey = col.mean(axis=1, keepdims=True)
        col = col * 0.6 + grey * 0.4 + 0.06
    flat_c = rgb.reshape(-1, 3)
    flat_a = a_out.reshape(-1)
    a_ = al * alpha
    if crude:
        a_ = a_ * (1 - crude * 0.5 * fbm(P.p.reshape(-1, 3)[idx], 3.0, seed, 2))
    flat_c[idx] = col
    flat_a[idx] = np.clip(a_, 0, 0.95) * P.cov.reshape(-1)[idx]
    return rgb, a_out


def sheet(out, px=300):
    """Every motif on one contact sheet, for review."""
    ims = [(k, f()) for k, f in MOTIFS.items()]
    cols = 8
    rows = (len(ims) + cols - 1) // cols
    sh = Image.new('RGB', (cols * px, rows * px), (205, 165, 140))
    d = ImageDraw.Draw(sh)
    for i, (k, im) in enumerate(ims):
        im.thumbnail((px - 20, px - 30))
        x, y = (i % cols) * px + (px - im.width) // 2, (i // cols) * px + 22
        sh.paste(im, (x, y), im)
        d.text(((i % cols) * px + 6, (i // cols) * px + 4), k, fill=(0, 0, 0))
    sh.save(out)
    return out


if __name__ == '__main__':
    import sys
    print(sheet(sys.argv[1] if len(sys.argv) > 1 else 'build/flash_sheet.png'))
