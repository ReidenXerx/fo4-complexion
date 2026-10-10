"""Black-and-grey and realistic tattoo pieces, painted in ink density (alasdairn's review, 2026-10-09: the flash
versions read as "a 4th grader in MS Paint"; his references are fine-line black-and-grey realism and an
airbrushed fire sleeve). Each returns an RGBA image (ink colour, alpha = how much ink) for flash.project_rgba.

The kit: an ink-density canvas drawn at 3x and reduced, where a filled shape REPLACES what is under it (paint order
is occlusion, as a tattooist layers feathers), lines add, and a shape can carry a gradient.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

K = 3  # supersampling


class Ink:
    """Ink density 0..1 on a w x h canvas (units: the canvas width is 1.0)."""

    def __init__(self, w_px, aspect):
        self.W, self.H = w_px * K, int(w_px * K * aspect)
        self.d = np.zeros((self.H, self.W), np.float32)
        self.col = np.zeros((self.H, self.W, 3), np.float32)  # ink colour per pixel (black and grey: all black)

    def px(self, pts):
        return [(x * self.W, y * self.W) for x, y in pts]

    def mask(self, pts, blur=0.0):
        m = Image.new('L', (self.W, self.H), 0)
        ImageDraw.Draw(m).polygon(self.px(pts), fill=255)
        if blur:
            m = m.filter(ImageFilter.GaussianBlur(blur * self.W))
        return np.asarray(m, np.float32) / 255.0

    def fill(self, pts, density, colour=(0, 0, 0)):
        """A shape that covers what is under it. density: a number, or a function of (x, y) arrays in canvas units
        (a gradient). Worked inside the shape's bounding box only."""
        q = self.px(pts)
        xs, ys = [a for a, _ in q], [b for _, b in q]
        x0, x1 = max(int(min(xs)) - 2, 0), min(int(max(xs)) + 3, self.W)
        y0, y1 = max(int(min(ys)) - 2, 0), min(int(max(ys)) + 3, self.H)
        if x1 <= x0 or y1 <= y0:
            return
        im = Image.new('L', (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(im).polygon([(a - x0, b - y0) for a, b in q], fill=255)
        m = np.asarray(im, np.float32) / 255.0
        if callable(density) or callable(colour):
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        if callable(density):
            density = density(xx / self.W, yy / self.W)
        colour = colour(xx / self.W, yy / self.W) if callable(colour) else np.array(colour, np.float32)
        box = self.d[y0:y1, x0:x1]
        self.d[y0:y1, x0:x1] = box * (1 - m) + m * density
        cb = self.col[y0:y1, x0:x1]
        self.col[y0:y1, x0:x1] = cb * (1 - m[..., None]) + m[..., None] * colour

    def lines(self, segs, width, density=0.95, colour=(0, 0, 0)):
        """Lines added on top (outlines, hatching): segs = [[(x, y), ...], ...]."""
        im = Image.new('L', (self.W, self.H), 0)
        dr = ImageDraw.Draw(im)
        w = max(1, int(width * self.W))
        for seq in segs:
            dr.line(self.px(seq), fill=255, width=w, joint='curve')
        m = np.asarray(im, np.float32) / 255.0
        self.d = np.maximum(self.d, m * density)
        self.col = self.col * (1 - m[..., None]) + m[..., None] * np.array(colour, np.float32)

    def done(self, w_px):
        a = Image.fromarray((np.clip(self.d, 0, 1) * 255).astype(np.uint8))
        rgb = Image.fromarray(np.clip(self.col, 0, 255).astype(np.uint8))
        h = int(w_px * self.H / self.W)
        a = a.resize((w_px, h), Image.LANCZOS)
        rgb = rgb.resize((w_px, h), Image.LANCZOS)
        out = rgb.convert('RGBA')
        out.putalpha(a)
        out.info['prefilter'] = True  # flash.project_rgba shrinks it to the texels it lands on
        return out

    def grid(self):
        y, x = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        return x / self.W, y / self.W


def _curve(p0, p1, p2, n=20):
    t = np.linspace(0, 1, n)[:, None]
    a, b, c = np.array(p0), np.array(p1), np.array(p2)
    return [tuple(v) for v in (1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c]


def _feather_pts(base, ang, length, width, bend=0.0, tip=0.35):
    """A feather: a long rounded blade from base along ang; bend curves it; tip = how pointed."""
    dx, dy = np.cos(ang), np.sin(ang)
    nx, ny = -dy, dx
    pts_l, pts_r = [], []
    for t in np.linspace(0, 1, 18):
        cx = base[0] + dx * length * t + nx * bend * length * t * t
        cy = base[1] + dy * length * t + ny * bend * length * t * t
        w = width * (0.45 + 0.55 * np.sin(np.pi * min(t, 0.5))) * np.sqrt(max(1 - t, 0.0)) ** (0.6 + tip)
        pts_l.append((cx + nx * w, cy + ny * w))
        pts_r.append((cx - nx * w, cy - ny * w))
    return pts_l + pts_r[::-1], (base, (base[0] + dx * length * 0.92 + nx * bend * length * 0.85,
                                       base[1] + dy * length * 0.92 + ny * bend * length * 0.85))


def feather(ink, base, ang, length, width, shade, bend=0.0, barbs=7, line=0.0016, tip=0.35):
    """One feather in black and grey: a shaded vane (darker at its base), its outline, the shaft, fine barbs."""
    pts, (s0, s1) = _feather_pts(base, ang, length, width, bend, tip)
    ca, sa = np.cos(ang), np.sin(ang)
    ink.fill(pts, lambda x, y: shade * (1.05 - 0.55 * np.clip(((x - base[0]) * ca + (y - base[1]) * sa) / length, 0, 1)))
    ink.lines([pts + [pts[0]]], line, 0.95)
    ink.lines([[s0, s1]], line * 0.7, 0.8)
    dx, dy = np.cos(ang), np.sin(ang)
    nx, ny = -dy, dx
    segs = []
    for k in range(1, barbs):
        tt = k / barbs
        sx, sy = base[0] + dx * length * tt * 0.9, base[1] + dy * length * tt * 0.9
        for sgn in (1, -1):
            w = width * 0.8
            segs.append([(sx, sy), (sx + nx * sgn * w + dx * w * 0.6, sy + ny * sgn * w + dy * w * 0.6)])
    ink.lines(segs, line * 0.5, 0.55)


def eagle_bg():
    """A black-and-grey eagle seen from behind, wings spread wide: the head, the feathered back, a fanned tail;
    each wing in rows -- long fingered primaries, the secondaries along the trailing edge, two rows of coverts and
    the small scalloped feathers along the leading edge -- every feather shaded at its base, outlined, with its
    shaft and barbs (after alasdairn's reference: fine-line realism, not flash)."""
    ink = Ink(900, 0.62)
    cx = 0.5
    for s in (1, -1):
        lead = _curve((cx + s * 0.05, 0.22), (cx + s * 0.21, 0.13), (cx + s * 0.40, 0.17), n=60)
        for k in range(9):                                      # primaries: long, fingered, fanning out and down
            t = 0.62 + k * 0.042
            bx, by = lead[min(int(t * 59), 59)]
            tilt = 0.30 + k * 0.10
            ang = np.pi / 2 - s * tilt
            feather(ink, (bx, by + 0.02), ang, 0.16 - k * 0.004, 0.016, 0.62, bend=-s * 0.10, barbs=8)
        for k in range(14):                                     # secondaries: the trailing edge, hanging down
            t = 0.08 + k * 0.042
            bx, by = lead[int(t * 59)]
            feather(ink, (bx, by + 0.035), np.pi / 2 - s * (0.06 + k * 0.012), 0.15 - k * 0.002, 0.017, 0.52,
                    bend=-s * 0.04, barbs=7)
        for k in range(16):                                     # greater coverts
            t = 0.06 + k * 0.045
            bx, by = lead[min(int(t * 59), 59)]
            feather(ink, (bx, by + 0.018), np.pi / 2 - s * (0.10 + k * 0.03), 0.085, 0.015, 0.38, bend=-s * 0.05, barbs=5)
        for row, (off, length, w, shade, n) in enumerate(((0.008, 0.055, 0.013, 0.30, 18), (0.0, 0.032, 0.011, 0.24, 22))):
            for k in range(n):                                  # median and lesser coverts, scalloped
                t = 0.04 + k * (0.86 / n)
                bx, by = lead[min(int(t * 59), 59)]
                feather(ink, (bx, by + off), np.pi / 2 - s * (0.25 + k * 0.025), length, w, shade, barbs=3 if row else 4)
        ink.lines([lead], 0.0022, 0.95)
    for k, ang in enumerate(np.linspace(np.pi / 2 - 0.42, np.pi / 2 + 0.42, 9)):   # the tail, fanned
        feather(ink, (cx, 0.42), ang, 0.17 - abs(k - 4) * 0.012, 0.019, 0.45, barbs=8)
    # the body: a tapered back under the feathers (no skin between their rows), then the feathers row by row
    body = ([(cx + 0.06 * np.sin(a) * (1 - 0.55 * max(np.cos(a), 0)), 0.30 - 0.14 * np.cos(a)) for a in np.linspace(0, 2 * np.pi, 60)])
    ink.fill(body, lambda x, y: 0.40 + 0.18 * np.clip((y - 0.18) / 0.26, 0, 1))
    # covered in small rounded feathers row by row, narrowing to the tail
    for r, y in enumerate(np.linspace(0.18, 0.44, 11)):
        half = 0.050 * (1 - (r / 10) ** 1.6) + 0.012
        n = max(2, int(half / 0.012) + 1)
        for x in np.linspace(cx - half, cx + half, n):
            feather(ink, (x, y), np.pi / 2 + (x - cx) * 3.0, 0.042, 0.013, 0.26 + r * 0.025, barbs=3, tip=0.1)
    # the head, from behind, set on the shoulders: a rounded crown with fine strokes, the beak's tip showing
    head = [(cx + 0.034 * np.cos(a), 0.165 + 0.044 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 48)]
    ink.fill(head, lambda x, y: 0.08 + 0.30 * np.clip((y - 0.13) / 0.08, 0, 1))
    ink.lines([head + [head[0]]], 0.0022, 0.95)
    strokes = [[(cx + dx, 0.135 + k * 0.012), (cx + dx * 1.15, 0.148 + k * 0.012)] for k in range(5) for dx in (-0.022, -0.008, 0.008, 0.022)]
    ink.lines(strokes, 0.0008, 0.5)
    ink.fill([(cx - 0.009, 0.124), (cx + 0.009, 0.124), (cx, 0.104)], 0.85)
    return ink.done(900)


def _metal(v0, v1, axis='y', hi=0.30):
    """Polished steel across a part, from v0 to v1 along axis: dark edges, a bright highlight band, mid greys."""
    def f(x, y):
        v = np.clip(((y if axis == 'y' else x) - v0) / (v1 - v0), 0, 1)
        return np.clip(0.46 - 0.44 * np.exp(-((v - hi) / 0.09) ** 2) + 0.30 * v ** 2 + 0.30 * np.exp(-(v / 0.05) ** 2), 0.02, 0.92)
    return f


def revolver_bg():
    """A Colt Python in black and grey, after alasdairn's reference, in the gun's own proportions (about two long
    to one high): the six-inch barrel and its full-length underlug as ONE block of polished steel under the
    ventilated rib, the ramp front sight, the frame with its top strap running back to the hammer, the fluted
    cylinder in its window, the trigger in a solid guard, and the wooden grip sloping down and back with its
    checkering and medallion. Bold outlines and broad shading: it lands on a few hundred texels, so detail finer
    than that turns to noise."""
    ink = Ink(900, 0.54)
    L = 0.0042
    steel = _metal(0.11, 0.275, hi=0.28)
    # the barrel and the underlug: one profile, rounded at the lug's front, the muzzle face at the left
    barrel = ([(0.035, 0.11), (0.565, 0.11), (0.565, 0.275), (0.075, 0.275)]
              + _curve((0.075, 0.275), (0.04, 0.27), (0.04, 0.235), n=8)[1:] + [(0.035, 0.19)])
    ink.fill(barrel, steel)
    ink.lines([[(0.05, 0.19), (0.555, 0.19)]], L * 0.45, 0.75)                 # where the lug meets the barrel
    ink.fill([(0.035, 0.115), (0.05, 0.115), (0.05, 0.185), (0.035, 0.185)], 0.85)   # the muzzle face
    ink.fill(_ellipse(0.0425, 0.15, 0.006, 0.018), 1.0)
    # the ventilated rib on top, its vents as dark slots, the front sight ramp
    rib = [(0.035, 0.08), (0.57, 0.08), (0.57, 0.11), (0.035, 0.11)]
    ink.fill(rib, _metal(0.08, 0.11, hi=0.45))
    for k in range(7):
        x = 0.10 + k * 0.064
        ink.fill([(x, 0.087), (x + 0.036, 0.087), (x + 0.036, 0.103), (x, 0.103)], 0.95)
    ramp = [(0.045, 0.08), (0.10, 0.08)] + _curve((0.10, 0.08), (0.075, 0.07), (0.065, 0.045), n=6)[1:] + [(0.05, 0.045)]
    ink.fill(ramp, 0.8)
    ink.lines([barrel + [barrel[0]], rib + [rib[0]], ramp + [ramp[0]]], L, 1.0)
    # the frame: the top strap back to the hammer, the cylinder window, the recoil shield sloping to the grip
    frame = [(0.555, 0.08), (0.79, 0.08), (0.815, 0.11), (0.835, 0.20), (0.82, 0.29), (0.70, 0.30),
             (0.60, 0.295), (0.555, 0.275)]
    ink.fill(frame, _metal(0.08, 0.30, hi=0.22))
    ink.lines([frame + [frame[0]]], L, 1.0)
    # the cylinder: rounded ends, three flutes, each a dark groove lit along one edge
    cyl = ([(0.60, 0.105), (0.735, 0.105)] + _curve((0.735, 0.105), (0.755, 0.19), (0.735, 0.28), n=10)[1:]
           + [(0.60, 0.28)] + _curve((0.60, 0.28), (0.58, 0.19), (0.60, 0.105), n=10)[1:])
    ink.fill(cyl, _metal(0.105, 0.28, hi=0.30))
    for y in (0.125, 0.175, 0.225):
        flute = [(0.615, y), (0.72, y), (0.728, y + 0.016), (0.72, y + 0.032), (0.615, y + 0.032), (0.607, y + 0.016)]
        ink.fill(flute, lambda x, yy, y=y: 0.85 - 0.6 * np.clip((yy - y) / 0.032, 0, 1))
        ink.lines([flute + [flute[0]]], L * 0.5, 0.9)
    ink.lines([cyl + [cyl[0]]], L, 1.0)
    ink.fill([(0.765, 0.135), (0.80, 0.135), (0.80, 0.16), (0.765, 0.16)], 0.55)         # the cylinder latch
    ink.lines([[(0.765, 0.135), (0.80, 0.135), (0.80, 0.16), (0.765, 0.16), (0.765, 0.135)]], L * 0.5, 0.9)
    # the hammer: a spur rising from the back of the frame and curling back
    spur = ([(0.785, 0.085)] + _curve((0.80, 0.05), (0.83, 0.02), (0.885, 0.015), n=10) + [(0.89, 0.04)]
            + _curve((0.865, 0.045), (0.835, 0.07), (0.825, 0.12), n=8))
    ink.fill(spur, _metal(0.015, 0.12, hi=0.35))
    ink.lines([spur + [spur[0]]], L, 1.0)
    ink.lines([[(0.845 + k * 0.012, 0.022), (0.85 + k * 0.012, 0.042)] for k in range(3)], L * 0.45, 0.8)
    # the trigger guard (a solid steel loop) and the trigger
    outer = _curve((0.625, 0.29), (0.62, 0.42), (0.72, 0.415), n=16) + _curve((0.72, 0.415), (0.775, 0.40), (0.775, 0.29), n=10)[1:]
    inner = _curve((0.765, 0.295), (0.765, 0.385), (0.72, 0.39), n=10) + _curve((0.72, 0.39), (0.645, 0.395), (0.645, 0.295), n=16)[1:]
    guard = outer + inner
    ink.fill(guard, _metal(0.29, 0.42, hi=0.4))
    ink.lines([guard + [guard[0]]], L * 0.8, 1.0)
    trig = ([(0.705, 0.295)] + _curve((0.70, 0.33), (0.69, 0.36), (0.675, 0.375), n=8)
            + _curve((0.69, 0.38), (0.715, 0.35), (0.725, 0.295), n=8))
    ink.fill(trig, 0.7)
    ink.lines([trig + [trig[0]]], L * 0.6, 1.0)
    # the grip: dark wood sloping down and back from the frame, checkered, the medallion near its top
    grip = ([(0.775, 0.29), (0.835, 0.20)] + _curve((0.835, 0.20), (0.88, 0.17), (0.905, 0.22), n=8)[1:]
            + _curve((0.905, 0.22), (0.96, 0.36), (0.975, 0.47), n=12)[1:]
            + _curve((0.975, 0.47), (0.97, 0.52), (0.92, 0.52), n=8)[1:]
            + _curve((0.92, 0.52), (0.85, 0.52), (0.815, 0.44), n=8)[1:] + [(0.79, 0.36)])
    ink.fill(grip, lambda x, y: 0.62 + 0.25 * np.clip((x - 0.80) / 0.17, 0, 1))
    hatch = []
    for k in range(-10, 14):
        x = 0.77 + k * 0.02
        hatch.append([(x, 0.18), (x + 0.20, 0.55)])
        hatch.append([(x + 0.20, 0.18), (x, 0.55)])
    hm = Image.new('L', (ink.W, ink.H), 0)                                 # the checkering: lighter cut lines
    dr = ImageDraw.Draw(hm)
    for seq in hatch:
        dr.line(ink.px(seq), fill=255, width=max(1, int(L * 0.45 * ink.W)))
    hm = np.asarray(hm, np.float32) / 255.0
    panel = ([(0.82, 0.31), (0.86, 0.235), (0.895, 0.25)] + _curve((0.895, 0.25), (0.94, 0.37), (0.95, 0.46), n=8)[1:]
             + [(0.925, 0.49), (0.86, 0.49), (0.83, 0.42)])
    gm = ink.mask(panel)
    ink.d = ink.d - 0.35 * hm * gm
    ink.lines([panel + [panel[0]]], L * 0.5, 1.0)
    ink.fill(_ellipse(0.875, 0.265, 0.016, 0.016), 0.12)
    ink.lines([_ellipse(0.875, 0.265, 0.016, 0.016)], L * 0.5, 1.0)
    ink.lines([grip + [grip[0]]], L, 1.0)
    return ink.done(900)


def _ellipse(cx, cy, rx, ry, n=36):
    return [(cx + rx * np.cos(a), cy + ry * np.sin(a)) for a in np.linspace(0, 2 * np.pi, n)]


def fire_real(flip=False, w_px=600, aspect=1.5, seed=7):
    """Realistic fire, after alasdairn's reference sleeve: tall flowing tongues licking upward, swaying more and
    curling toward their tips, a yellow-white core through orange to deep red, dark red-black between them where
    the back flames show -- painted as a heat field, not drawn shapes."""
    rng = np.random.default_rng(seed)
    W, H = w_px, int(w_px * aspect)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    u = x / W                      # 0..1 across
    v = 1.0 - y / H                # 0 at the base, 1 at the top

    def layer(n, height, width, amp, bright):
        heat = np.zeros((H, W), np.float32)
        for k in range(n):
            x0 = 0.08 + 0.84 * (k + rng.uniform(0.2, 0.8)) / n
            top = height * rng.uniform(0.65, 1.0)
            phase, freq = rng.uniform(0, 6.3), rng.uniform(5.0, 8.0)
            t = np.clip(v / top, 0, 1.2)
            sway = amp * t ** 1.5 * np.sin(freq * t + phase) + amp * 0.6 * t ** 3 * np.sin(freq * 2.3 * t + phase * 1.7)
            wdt = width * (1 - np.clip(t, 0, 1)) ** 0.85 * (0.85 + 0.25 * np.sin(t * 9 + phase))
            d = np.abs(u - x0 - sway) / np.maximum(wdt, 1e-4)
            h = np.clip(1 - d, 0, 1) ** 0.8 * (t <= 1.0) * (1 - 0.55 * np.clip(t, 0, 1))
            heat = np.maximum(heat, h * bright)
        return heat

    back = layer(9, 0.92, 0.09, 0.07, 0.42)
    front = layer(7, 0.80, 0.075, 0.06, 1.0)
    # a glow at the root the tongues rise out of, fading up with no edge
    base = np.clip(1 - v / 0.16, 0, 1) ** 2.2 * 0.40 * np.clip(np.sin(np.pi * u) * 1.4, 0, 1)   # orange, not a pale band
    heat = np.clip(np.maximum(front, back) + base * (1 - 0.5 * np.maximum(front, back)), 0, 1)
    # the heat to colour: deep red-black at the edges, red, orange, yellow, a pale core
    stops = np.array([0.0, 0.10, 0.25, 0.45, 0.68, 0.88, 1.0])
    cols = np.array([(40, 4, 4), (70, 6, 6), (150, 18, 10), (215, 70, 16), (245, 150, 30), (255, 214, 90), (255, 240, 190)], np.float32)
    rgb = np.stack([np.interp(heat, stops, cols[:, c]) for c in range(3)], -1)
    alpha = np.clip((heat - 0.04) / 0.10, 0, 1) * 0.96 * np.clip(v / 0.14, 0, 1) ** 1.5   # the root fades, no cut edge
    im = Image.fromarray(rgb.astype(np.uint8)).convert('RGBA')
    im.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
    im = im.transpose(Image.FLIP_TOP_BOTTOM) if flip else im
    im.info['prefilter'] = True
    return im


def _grad(c0, c1, p0, p1):
    """A colour ramp from c0 at point p0 to c1 at p1 (canvas units), as a fill colour."""
    c0, c1 = np.array(c0, np.float32), np.array(c1, np.float32)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n2 = dx * dx + dy * dy

    def f(x, y):
        t = np.clip(((x - p0[0]) * dx + (y - p0[1]) * dy) / n2, 0, 1)[..., None]
        return c0 * (1 - t) + c1 * t
    return f


def swallow_trad(back=(28, 64, 168)):
    """An American traditional swallow in flight, done properly: a bold black outline; one wing raised and one
    swept down, their long primaries split and each lit by a pale stroke, deep blue at the body going bright to
    the tips; the dark blue crown and back, the red face and throat, a cream belly shaded warm, the long forked
    tail with its white spots, a bright eye; black whip shading where the wings meet the body."""
    ink = Ink(900, 0.8)
    deep = tuple(int(c * 0.35) for c in back)
    bright = tuple(min(255, int(c * 1.5 + 30)) for c in back)
    O = 0.0075
    # the tail streamers (behind)
    for tip, ctrl in (((0.97, 0.50), (0.80, 0.46)), ((0.93, 0.66), (0.78, 0.58))):
        st = _curve((0.60, 0.47), ctrl, tip, n=16) + _curve(tip, (ctrl[0] - 0.02, ctrl[1] + 0.05), (0.60, 0.53), n=16)[1:]
        ink.fill(st, 1.0, _grad(deep, back, (0.6, 0.5), tip))
        ink.lines([st + [st[0]]], O, 1.0)
    for x, y in ((0.70, 0.485), (0.69, 0.555)):
        ink.fill(_ellipse(x, y, 0.012, 0.006), 1.0, (245, 240, 225))
    # the lower wing, swept down and back
    low = (_curve((0.36, 0.46), (0.48, 0.66), (0.78, 0.78), n=18)
           + [(0.70, 0.71), (0.73, 0.70), (0.62, 0.63)]
           + _curve((0.62, 0.63), (0.56, 0.55), (0.52, 0.50), n=12)[1:])
    ink.fill(low, 1.0, _grad(deep, back, (0.40, 0.50), (0.76, 0.76)))
    ink.lines([low + [low[0]]], O, 1.0)
    ink.lines([[(0.46, 0.58), (0.72, 0.74)]], O * 0.4, 1.0, (150, 180, 235))
    # the body: crown and back blue, then the cream belly and the red face over it
    body = (_curve((0.14, 0.36), (0.22, 0.26), (0.36, 0.32), n=16) + _curve((0.36, 0.32), (0.52, 0.40), (0.64, 0.48), n=16)[1:]
            + _curve((0.64, 0.48), (0.62, 0.55), (0.48, 0.54), n=10)[1:] + _curve((0.48, 0.54), (0.24, 0.50), (0.14, 0.40), n=16)[1:])
    ink.fill(body, 1.0, _grad(deep, back, (0.2, 0.28), (0.6, 0.5)))
    belly = _curve((0.22, 0.44), (0.40, 0.56), (0.62, 0.52), n=16) + _curve((0.62, 0.52), (0.42, 0.46), (0.26, 0.41), n=16)[1:]
    ink.fill(belly, 1.0, _grad((250, 244, 228), (222, 196, 150), (0.3, 0.44), (0.55, 0.54)))
    face = _curve((0.14, 0.37), (0.17, 0.33), (0.23, 0.35), n=10) + _curve((0.23, 0.35), (0.28, 0.42), (0.24, 0.46), n=10)[1:] + _curve((0.24, 0.46), (0.17, 0.45), (0.14, 0.40), n=8)[1:]
    ink.fill(face, 1.0, _grad((200, 30, 28), (150, 18, 20), (0.16, 0.36), (0.26, 0.45)))
    ink.lines([body + [body[0]]], O, 1.0)
    ink.lines([belly[:16], face + [face[0]]], O * 0.6, 1.0)
    # the beak and the eye
    beak = [(0.145, 0.365), (0.09, 0.385), (0.145, 0.40)]
    ink.fill(beak, 1.0, (30, 30, 34))
    ink.fill(_ellipse(0.188, 0.348, 0.016, 0.014), 1.0, (250, 248, 240))
    ink.fill(_ellipse(0.190, 0.348, 0.008, 0.008), 1.0, (12, 12, 14))
    ink.lines([_ellipse(0.188, 0.348, 0.016, 0.014)], O * 0.5, 1.0)
    # the raised wing, on top: split primaries, each with a pale stroke
    up = (_curve((0.36, 0.40), (0.48, 0.20), (0.90, 0.05), n=20)
          + [(0.80, 0.12), (0.86, 0.12), (0.74, 0.20), (0.80, 0.21), (0.66, 0.28), (0.71, 0.30)]
          + _curve((0.71, 0.30), (0.56, 0.40), (0.46, 0.46), n=12)[1:])
    ink.fill(up, 1.0, _grad(deep, bright, (0.40, 0.44), (0.88, 0.07)))
    ink.lines([up + [up[0]]], O, 1.0)
    for a, b in (((0.50, 0.30), (0.84, 0.09)), ((0.52, 0.34), (0.76, 0.17)), ((0.54, 0.37), (0.68, 0.26))):
        ink.lines([[a, b]], O * 0.4, 1.0, (170, 200, 245))       # pale strokes along the feathers
    whips = [[(0.40 + k * 0.012, 0.40 - k * 0.006), (0.43 + k * 0.012, 0.36 - k * 0.006)] for k in range(8)]
    ink.lines(whips, O * 0.35, 1.0)                              # whip shading where the wing leaves the body
    return ink.done(900)


if __name__ == '__main__':
    import sys
    fn = {'eagle': eagle_bg, 'revolver': revolver_bg, 'fire': fire_real, 'swallow': swallow_trad}[sys.argv[1]]
    im = fn()
    bg = Image.new('RGBA', im.size, (214, 176, 150, 255))
    bg.alpha_composite(im)
    bg.save(sys.argv[2])
    print(im.size)
