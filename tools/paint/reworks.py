"""Vex's rework list (2026-10-15, for_vex/from_vex/tattoo_names_draft.csv): our own tattoos redrawn, moved and copied
as his notes ask -- new fonts, clean edges, new places, mirrored copies. Each piece is a function of the UV map, so the
preview and (once Vex and alasdairn approve) make_marks build the very same texture.

    python tools/paint/reworks.py <out dir> [--only Complexion_TattooRust,...]     marks + preview sheets
    python tools/paint/reworks.py <out dir> --test-mod <zip dir>                     test mods from <out dir>/marks

Places are measured on the bodies (marks.landmarks; the navel and the top of the cleft below), not guessed:
1 game unit = 1.4287 cm. Text is drawn large and sampled bilinearly at 4096, so its edges stay clean on the skin.
"""
import argparse
import io
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import artist_art  # noqa: E402
import artist_flat  # noqa: E402
import artist_hands  # noqa: E402
import decals  # noqa: E402
import seams  # noqa: E402
import flash  # noqa: E402
import hands  # noqa: E402
import make_marks as mm  # noqa: E402
from body import UVMap  # noqa: E402
from marks import Painter, landmarks  # noqa: E402

CM = artist_flat.CM
INDEX = {r[0]: n for n, r in enumerate(mm.MARKS)}
FOREARM_CM = {'female': 20.0, 'male': 22.0}   # wrist to elbow, measured 10-14 (canvas_sizes_cm.txt)


# ---------------------------------------------------------------- designs (RGBA, ink on transparency)

def _rgba(mask, ink='fresh', alpha=0.92):
    a = np.asarray(mask, dtype=np.float64) / 255.0 * alpha
    out = np.zeros(a.shape + (4,))
    out[..., :3] = decals.INK[ink]
    out[..., 3] = a
    return Image.fromarray(np.uint8(out * 255 + 0.5), 'RGBA')


def text(s, font='block', arc=0.0, bold=0, px=320, ink='fresh'):
    """A word drawn large (px), bold = an outline that thickens thin strokes, arc > 0 bows the middle up."""
    f = ImageFont.truetype(str(decals.FONTS / decals.FONT[font]), px)
    l, t, r, b = f.getbbox(s, stroke_width=bold)
    im = Image.new('L', (r - l + 40, b - t + 40), 0)
    ImageDraw.Draw(im).text((20 - l, 20 - t), s, fill=255, font=f, stroke_width=bold, stroke_fill=255)
    if arc:
        w, h = im.size
        arr = np.asarray(im)
        out = np.zeros((h + int(w * arc), w), np.uint8)
        for x in range(w):
            dy = int((((x - w / 2) / (w / 2)) ** 2) * w * arc)
            out[dy:dy + h, x] = arr[:, x]
        im = Image.fromarray(out)
    return _rgba(im, ink)


def arrow(s, font='block', bold=0, px=300, ink='fresh'):
    """The words over a fat arrow pointing straight down; the tip is the image's bottom edge."""
    w = np.ascontiguousarray(np.asarray(text(s, font, 0.0, bold, px, ink))[..., 3])
    th, tw = w.shape
    k = px / 150.0
    W, Hh = max(tw, int(160 * k)), th + int(180 * k)
    im = Image.new('L', (W, Hh), 0)
    im.paste(Image.fromarray(w), ((W - tw) // 2, 0))
    d = ImageDraw.Draw(im)
    cx = W // 2
    d.rectangle((cx - 16 * k, th + 10 * k, cx + 16 * k, th + 110 * k), fill=255)
    d.polygon([(cx - 60 * k, th + 100 * k), (cx + 60 * k, th + 100 * k), (cx, Hh - 1)], fill=255)
    return _rgba(im, ink, 1.0)


def snake_eyes(size=520):
    """decals.dice with both dice on one (Vex: snake eyes)."""
    out = Image.new('L', (size, size), 0)
    for cx, cy, rot in ((170, 230, 14), (360, 300, -22)):
        im = Image.new('L', (220, 220), 0)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((10, 10, 210, 210), radius=34, outline=255, width=12)
        d.ellipse((110 - 22, 110 - 22, 110 + 22, 110 + 22), fill=255)
        im = im.rotate(rot, expand=True)
        out.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)
    return _rgba(out)


def emblem(name):
    return _rgba(decals.emblem(name))


# ---------------------------------------------------------------- places on the body

def snap(m, target, n, facing=0.5):
    """The skin nearest target that faces about the way n does: (point, normal)."""
    ok = m.covered & (m.normal @ n > facing)
    k = np.argmin(np.where(ok, np.linalg.norm(m.position - target, axis=-1), np.inf))
    return m.position.reshape(-1, 3)[k], m.normal.reshape(-1, 3)[k]


def smooth_n(m, c, n, r=3.0):
    """The skin's mean normal within r units of c: inside the cleft (or any crease) one texel's normal points
    sideways, and a design laid on that plane came out sheared (10-15)."""
    near = m.covered & (np.linalg.norm(m.position - c, axis=-1) < r) & (m.normal @ n > -0.2)
    v = m.normal[near].mean(0)
    return v / np.linalg.norm(v)


def z_of(m, h):
    return m.bounds[0][2] + h * (m.bounds[1][2] - m.bounds[0][2])


def front_at(m, h, x=0.0, sgn=1):
    """The skin at height h (Painter.h), across position x, on the front (sgn 1) or the back (-1) of the torso."""
    P = Painter(m)
    band = m.covered & (np.abs(P.h - h) < 0.004) & (np.abs(m.position[..., 0] - x) < 0.5) & (m.normal[..., 1] * sgn > 0.2)
    pts = m.position[band]
    k = np.argmax(pts[:, 1] * sgn)
    return pts[k], smooth_n(m, pts[k], np.array((0.0, float(sgn), 0.0)))


def half_width(m, h):
    P = Painter(m)
    band = m.covered & P.reg('torso') & (np.abs(P.h - h) < 0.004)
    return float(np.abs(m.position[..., 0][band]).max())


def side_at(m, h, side):
    """The side of the hip at height h: the skin there facing most squarely out to that side."""
    P = Painter(m)
    band = m.covered & (np.abs(P.h - h) < 0.004) & (m.position[..., 0] * side > 0) & (P.reg('torso') | P.reg('leg'))
    out = np.array((side, 0.0, 0.0))
    score = m.normal[band] @ out
    # the mean of the best few percent, not one texel: at 4096 the single best was a stray one at an island's edge
    # (a swallow there came out 22 texels, 10-15)
    best = score >= np.quantile(score, 0.97)
    c = m.position[band][best].mean(0)
    return snap(m, c, out, 0.7)


def nipple(m, side):
    p = landmarks(m)['nipples'][side]
    return snap(m, p, np.array((0.25 * side, 1.0, 0.0)) / np.hypot(0.25, 1.0), 0.3)


def navel_h(m):
    """The navel: the deepest dimple on the front midline (measured 10-15: 23 cm above the crotch on the women's body,
    26 cm on the men's -- landmarks()['navel'] guesses 13 cm)."""
    if hasattr(m, '_navel_h'):
        return m._navel_h
    V, T = m.vertices, m.triangles
    lo, hi = m.bounds[0][2], m.bounds[1][2]
    H = (V[:, 2] - lo) / (hi - lo)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, T[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    cr = landmarks(m)['crotch']
    cand = np.flatnonzero((np.abs(V[:, 0]) < 1.5) & (H > cr + 0.03) & (H < cr + 0.22) & (vn[:, 1] > 0.3))
    near = V[(vn[:, 1] > 0.0) & (H > cr - 0.02) & (H < cr + 0.27)]
    best, bh = 0.0, landmarks(m)['navel']
    for i in cand:
        d = np.linalg.norm(near - V[i], axis=1)
        nb = near[(d < 2.0) & (d > 0.01)]
        if len(nb) >= 4:
            bump = (V[i] - nb.mean(0)) @ vn[i]
            if bump < best:
                best, bh = bump, H[i]
    m._navel_h = float(bh)
    return m._navel_h


def cleft_h(m):
    """The top of the cleft of the buttocks: where the midline stops lying deep between the cheeks (measured 10-15,
    about 8 cm above the crotch on both bodies)."""
    return landmarks(m)['crotch'] + 0.055


def tramp(m, up_cm=5.0):
    return front_at(m, cleft_h(m) + up_cm / CM / (m.bounds[1][2] - m.bounds[0][2]), 0.0, -1)


def h_up(m, h, cm):
    return h + cm / CM / (m.bounds[1][2] - m.bounds[0][2])


def arm_axis(m, side, place='upper_arm'):
    """Unit vector down the limb (towards the elbow / the wrist), from its bones."""
    a, b = (artist_flat.bone_centre(m.sex, f'{"L" if side < 0 else "R"}{x}') for x in artist_flat.LIMB_BONES[place])
    v = b - a
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------- laying a design on the skin

def flat(m, design, c, n, width_cm, rotate_deg=0.0, up=(0.0, 0.0, 1.0), anchor='centre'):
    """The design flat on the skin at c (normal n), width_cm across, sampled bilinearly. up: the design's up before
    rotate_deg (clockwise as seen on the skin). anchor='bottom': c is the middle of its bottom edge (an arrow's tip)."""
    design = design.crop(design.getbbox() or (0, 0, design.width, design.height))
    width = width_cm / CM
    hgt = width * design.height / design.width
    up = np.asarray(up, np.float64)
    up = up - n * (up @ n)
    up /= np.linalg.norm(up)
    right = np.cross(up, n)
    if rotate_deg:
        cr, sr = np.cos(np.radians(rotate_deg)), np.sin(np.radians(rotate_deg))
        up, right = up * cr + right * sr, right * cr - up * sr
    if anchor == 'bottom':
        c, _ = snap(m, c + up * hgt / 2, n, 0.2)
    q = m.position - c
    u, v, depth = q @ right, q @ up, q @ n
    near = m.covered & (m.normal @ n > 0.25) & (np.abs(depth) < max(width, hgt) * 0.5)
    zone = near & (np.abs(u) < width * 0.6) & (np.abs(v) < hgt * 0.6)
    inner = near & (np.abs(u) < width * 0.5) & (np.abs(v) < hgt * 0.5)
    tpu = np.sqrt(max(inner.sum(), 1) / (width * hgt))
    dw, dh = max(int(width * tpu * 1.5), 8), max(int(hgt * tpu * 1.5), 8)
    d = artist_flat.premultiplied_resize(design, dw, dh)
    x = (u[zone] / width + 0.5) * dw - 0.5
    y = (0.5 - v[zone] / hgt) * dh - 0.5
    rgb = np.ones(m.covered.shape + (3,)) * mm.SKIN
    alpha = np.zeros(m.covered.shape)
    a = ndimage.map_coordinates(d[..., 3], [y, x], order=1, mode='constant', cval=0.0)
    pm = [ndimage.map_coordinates(d[..., k] * d[..., 3], [y, x], order=1, mode='constant', cval=0.0) for k in range(3)]
    alpha[zone] = a
    rgb[zone] = np.clip(np.stack(pm, -1) / np.maximum(a, 1e-4)[:, None], 0, 1)
    return rgb, alpha


def limb(m, design, place, side, face, height_cm, rotate_deg=0.0, shift_cm=0.0, centred=False):
    """artist_flat's wrap round a limb; centred: in the middle of the forearm, whatever way the design turns."""
    buf = io.BytesIO()
    design.save(buf, 'PNG')
    from_end = None
    if centred:
        from_end = FOREARM_CM[m.sex] / 2 - height_cm / 2
    return artist_flat.place_design(m, buf, place, side, face, height_cm, 0.0, rotate_deg, shift_cm, False, from_end)


def over_all(parts):
    import marks
    rgb = np.ones(parts[0][0].shape) * mm.SKIN
    alpha = np.zeros(parts[0][1].shape)
    for r, a in parts:
        marks.over(rgb, alpha, r, a)
    return rgb, alpha


def original_flash(tid):
    """(design, spot, side, width, faded, crude, rotate, seed) as make_marks paints the row now."""
    n = INDEX[tid]
    motif, margs, spot, side, width, faded, crude = mm.MARKS[n][3]
    rng = np.random.default_rng(1000 + n)
    rot = float(rng.uniform(-0.15, 0.15))
    seed = int(rng.integers(1 << 30))
    return flash.MOTIFS[motif](*margs), spot, side, width, faded, crude, rot, seed


def flash_at(m, tid, design=None, width=None, move=None, rotate=None, at=None, up=(0.0, 0.0, 1.0)):
    """A flash row as it is now, changed only where asked: design, width (units), move (cm, a function of the map
    giving an offset), rotate (radians) or a new place at = (point, normal)."""
    d0, spot, side, w0, faded, crude, rot, seed = original_flash(tid)
    c, n, _ = decals.anchor(m, spot, side) if at is None else (*at, None)
    if move is not None:
        c, n = snap(m, c + move(m, c, n) / CM, n)
    return flash.project_rgba_at(m, design or d0, c, n, up, w0 if width is None else width,
                                 rot if rotate is None else rotate, 0.92, crude, seed, faded)


def decal_row(m, tid, args, painter='decal'):
    """make_marks' own decal painter with this row's seed (an unchanged look; a copy with new words)."""
    return mm.paint(painter, m, np.random.default_rng(1000 + INDEX[tid]), args)


# ---------------------------------------------------------------- the pieces

PIECES = {}   # tid -> dict(sex, size, hands, fn, what)


def piece(tid, what, size=4096, on_hands=False):
    sex = 'female' if tid.rsplit('_', 1)[1].startswith('F') else 'male'

    def reg(fn):
        PIECES[tid] = dict(sex=sex, size=2048 if on_hands else size, hands=on_hands, fn=fn, what=what)
        return fn
    return reg


def both(base, what, size=4096, sexes='FM'):
    def reg(fn):
        for s in sexes:
            piece(f'{base}_{s}01', what, size)(fn)
        return fn
    return reg


# --- knuckles: one letter on the back of each finger's first segment, upright for someone facing the raised fists:
# the letter's top towards the knuckle, read index -> little on the left hand, little -> index on the right.
KNUCKLES = [('Complexion_TattooRust', 'RUST', 'block', 1, ''), ('Complexion_TattooRustLeftHand', 'RUST', 'block', -1, 'copy'),
            ('Complexion_TattooKill', 'KILL', 'pirate', -1, ''), ('Complexion_TattooKillRightHand', 'KILL', 'pirate', 1, 'copy'),
            ('Complexion_TattooLove', 'LOVE', 'block', -1, ''), ('Complexion_TattooLoveRightHand', 'LOVE', 'block', 1, 'copy'),
            ('Complexion_TattooHate', 'HATE', 'block', 1, ''), ('Complexion_TattooHateLeftHand', 'HATE', 'block', -1, 'copy')]


def knuckles(word, font, side):
    def fn(m):
        hgt = 1.4 if m.sex == 'female' else 1.7
        fingers = (2, 3, 4, 5) if side < 0 else (5, 4, 3, 2)
        parts = []
        for letter, finger in zip(word, fingers):
            d = text(letter, font, px=260)
            buf = io.BytesIO()
            d.save(buf, 'PNG')
            parts.append(artist_hands.place_on_hand(m, buf, 'finger', side, hgt, 0.0, 180.0, finger=finger, segment=1,
                                                    face='back'))
        return over_all(parts)
    return fn


for base, word, font, side, kind in KNUCKLES:
    for s in 'FM':
        piece(f'{base}_{s}01', f'{"copy: " if kind else "moved: "}"{word}" on the {"left" if side < 0 else "right"} '
              f'knuckles, one letter a finger', on_hands=True)(knuckles(word, font, side))


# --- words on the body
def abdomen(m):
    L = landmarks(m)
    return front_at(m, (L['underbust'] + navel_h(m)) / 2)


@both('Complexion_TattooNoMercy', 'moved to the abdomen (between breasts and navel), a readable font')
def _(m):
    return flat(m, text('No Mercy', 'pirate'), *abdomen(m), 15.0)


@both('Complexion_TattooWasteland', 'moved to the abdomen, a readable font (the W), bowed 15%')
def _(m):
    return flat(m, text('Wasteland', 'pirate', arc=0.15), *abdomen(m), 18.0)


@both('Complexion_TattooAtomPraised', 'moved to the abdomen, a readable font (the A), bowed 15%')
def _(m):
    return flat(m, text('Atom Be Praised', 'pirate', arc=0.15), *abdomen(m), 20.0)


@piece('Complexion_TattooMom_F01', 'straight across the outer upper arm when the arm hangs down')
def _(m):
    c, n, _ = decals.anchor(m, 'upper_arm', 1)
    return flat(m, text('Mom', 'western'), c, n, 7.0, up=-arm_axis(m, 1))


@piece('Complexion_TattooMom_M01', 'moved to the middle of the outer shoulder, straight when the arm hangs down')
def _(m):
    d = text('Mom', 'western')
    return limb(m, d, 'upper_arm', 1, 'outer', 7.0 * d.height / d.width, shift_cm=6.0)


@both('Complexion_TattooOneEleven', 'copy of "13" with 111', size=2048)
def _(m):
    return decal_row(m, 'Complexion_TattooThirteen_' + ('F01' if m.sex == 'female' else 'M01'),
                     (('word', '111', 'pirate', 0.0), 'neck_back', 0, 3, 'faded', 0.7))


@both('Complexion_TattooLucky', 'the upper-back version: lighter ink, bigger (8 cm, men 9 cm)')
def _(m):
    return decal_row(m, 'Complexion_TattooLucky_' + ('F01' if m.sex == 'female' else 'M01'),
                     (('lucky',), 'chest', -1, 8 if m.sex == 'female' else 9, 'faded', 0.0))


# --- Vex's per-overlay requests (10-15 on: one texture + its changes -> a render; the zip after his OK)
def decal_row_at(m, tid, args, c, n, painter='decal'):
    """decal_row with its spot moved to (c, n): the painters only take named spots, so the anchor answers c, n."""
    real = decals.anchor
    decals.anchor = lambda m_, spot, side=0: (c, n, np.array((0.0, 0.0, 1.0)))
    try:
        return decal_row(m, tid, args, painter)
    finally:
        decals.anchor = real


# cm above the upper_back landmark: the highest the whole scar stays clear of the neck fade (every inked texel >= 3.0
# units from the seam, measured by scratchpad atomscar_search.py); the width in game units (the men's unchanged)
ATOMSCAR = {'female': (10.5, 6), 'male': (9.5, 8)}


def atomscar_back(m, up_cm=None):
    up, width = ATOMSCAR[m.sex]
    h = h_up(m, landmarks(m)['upper_back'], up if up_cm is None else up_cm)
    tid = 'Complexion_AtomScar_' + ('F01' if m.sex == 'female' else 'M01')
    return decal_row_at(m, tid, (('emblem', 'atom'), 'upper_back', 0, width), *front_at(m, h, 0.0, -1), 'scar_decal')


@piece('Complexion_AtomScar_F01', 'moved up the back as close to the neck as it goes unfaded, 25% smaller', size=2048)
def _(m):
    return atomscar_back(m)


@piece('Complexion_AtomScar_M01', 'moved up the back as close to the neck as it goes unfaded, same size', size=2048)
def _(m):
    return atomscar_back(m)


def tile_fill(m, tid, tile_png, tile_cm, blur=24.0, full=85, reach=0.55, opacity=0.85, tint=None):
    """A seamless hair tile (art/contrib) as the fill of an existing mark: inside that mark's coverage (its painting at
    its own size, blurred over a few strands, full from the `full` percentile of its density), laid flat from behind
    with its strands down the back, tile_cm a repeat, shrunk once to about one tile pixel per texel. Strands, not a
    mat: a strand shows where its darkness clears a threshold the density lowers, so even the densest part keeps skin
    between strands (reach = how far down the darkness scale full density goes) and the edges thin out gradually
    (alasdairn 10-15: the solid fill with a ragged edge read as "a partially waxed Bigfoot")."""
    n = INDEX[tid]
    row = mm.MARKS[n]
    m0 = UVMap(mm.DATA, m.sex, row[4])
    _, a0 = mm.paint(row[2], m0, np.random.default_rng(1000 + n), row[3])
    a0 = a0 * seams.seam_fade(m0)                    # the old texture's own neck/wrist fade
    old = np.asarray(Image.fromarray((np.clip(a0, 0, 1) * 255).astype(np.uint8)).resize(m.covered.shape[::-1],
                     Image.BILINEAR), dtype=np.float64) / 255.0 * m.covered
    env = ndimage.gaussian_filter(old, m.covered.shape[0] / 2048 * blur)
    env = np.clip(env / np.percentile(env[env > 0.02], full), 0, 1) * m.covered
    P = m.position
    span = tile_cm / CM
    back = env > 0.5
    dx = np.linalg.norm(np.diff(P, axis=1), axis=-1)[back[:, 1:] & back[:, :-1]]
    T = int(round(span / np.median(dx[dx > 0])))
    tile = np.asarray(Image.open(HERE / 'art' / 'contrib' / tile_png).convert('RGB').resize((T, T), Image.LANCZOS),
                      dtype=np.float64) / 255.0
    rgb = tile[(((-P[..., 2] / span) % 1.0) * (T - 1)).astype(int), (((P[..., 0] / span) % 1.0) * (T - 1)).astype(int)]
    if tint is not None:   # the tile recoloured: its mean on the back becomes tint, each strand keeps its variation
        rgb = np.clip(rgb * (np.asarray(tint) / rgb[back].mean(0)), 0, 1)
    lum = rgb.mean(-1)
    lo, hi = np.percentile(lum[back], [5, 95])
    dark = np.clip((hi - lum) / (hi - lo), 0, 1)
    return rgb, np.clip((dark - 1 + env * reach) * 4, 0, 1) * opacity * m.covered


# Vex 10-15: the same light/heavy hair in the other colours. The tile as he made it is the black; the brown takes the
# step the tile took from the old black ink (x2.7 on its mean), from the old brown ink; the grey keeps the old grey ink's
# tone (x2.7 would be near white, which a multiply overlay cannot show on skin).
HAIR_TINT = {'brown': tuple(np.array((0.20, 0.13, 0.08)) * 2.7), 'grey': (0.45, 0.43, 0.42)}
HAIR_REACH = {'light': 0.55, 'heavy': 0.62}


def hair_piece(tid, colour, weight):
    @piece(tid, f"Vex's hair tile, {weight}, {colour} (4096)")
    def _(m):
        return tile_fill(m, 'Complexion_BackHairBlackHeavy_M01', 'vex_thick_body_hair.jpg', 16.0,
                         reach=HAIR_REACH[weight], tint=HAIR_TINT[colour])


hair_piece('Complexion_BackHairBrownLight_M01', 'brown', 'light')
hair_piece('Complexion_BackHairBrown_M01', 'brown', 'heavy')
hair_piece('Complexion_BackHairGreyLight_M01', 'grey', 'light')
hair_piece('Complexion_BackHairGreyHeavy_M01', 'grey', 'heavy')   # NEW id (no heavy grey existed)


@piece('Complexion_BackHairBlack_M01', "Vex's hair tile, the thinned version (as previewed for the heavy one) (4096)")
def _(m):   # Vex 10-15: the thinned preview replaces the light back hair, inside the heavy one's coverage as he saw it
    return tile_fill(m, 'Complexion_BackHairBlackHeavy_M01', 'vex_thick_body_hair.jpg', 16.0)


@piece('Complexion_BackHairBlackHeavy_M01', "Vex's hair tile, thinned: strands with skin between, fading out gradually (4096)")
def _(m):
    return tile_fill(m, 'Complexion_BackHairBlackHeavy_M01', 'vex_thick_body_hair.jpg', 16.0, reach=0.62)   # Vex: 20% thicker (ink +20%)


def vex_birthmark(m, tid):
    """Vex's birthmark art (art/contrib, 10-17) where the old painted one is: realism.birthmark's own spot (the row's
    seed, drawn on the row's 2048 map), as wide across as the old one's ink, turned by the row's seed so the four
    textures are not one stamp."""
    n_ = INDEX[tid]
    P = Painter(m)
    c, n = P.pick_points(np.random.default_rng(1000 + n_), P.reg('torso', 'arm', 'leg') & (P.h > 0.2), 1)[0]
    _, a0 = mm.paint('birthmark', m, np.random.default_rng(1000 + n_), ())
    up = np.array((0.0, 0.0, 1.0)) - n * n[2]
    right = np.cross(up / np.linalg.norm(up), n)
    across = (m.position[a0 > 0.1] - c) @ right
    width_cm = float(np.ptp(np.percentile(across, [2, 98]))) * CM
    turn = float(np.random.default_rng(1000 + n_).uniform(0, 360))
    png = HERE / 'art' / 'contrib' / 'vex_birthmark.png'
    if tid in BIRTHMARK_WRAP:
        place, side, face, from_wrist = BIRTHMARK_WRAP[tid]
        art = Image.open(png).convert('RGBA')
        art = art.crop(art.getbbox())
        cm_per_px = width_cm / art.width
        art = art.rotate(-turn, Image.BICUBIC, expand=True)   # turned first, so from_wrist holds for its real extent
        art = art.crop(art.getbbox())
        buf = io.BytesIO()
        art.save(buf, 'PNG')
        return artist_flat.place_design(m, buf, place, side, face, art.height * cm_per_px, from_end_cm=from_wrist)
    return flat(m, Image.open(png).convert('RGBA'), c, n, width_cm, turn)


# M02's old spot is on the inner right wrist, its edge on the mesh's end: a flat 7 cm stamp there ran off the arm and
# broke up round the thin forearm, so it wraps round the forearm (inner face), its lower edge 2.5 cm above the wrist (the wrist's
# cut slants: at 1.5 cm the inner side still came within the tattoo fade)
BIRTHMARK_WRAP = {'Complexion_Birthmark_M02': ('forearm', 1, 'inner', 2.5)}


def birthmark_piece(tid):
    @piece(tid, "Vex's birthmark art, at the old birthmark's spot and size", size=2048)
    def _(m):
        return vex_birthmark(m, tid)


for _tid in ('Complexion_Birthmark_F01', 'Complexion_Birthmark_F02', 'Complexion_Birthmark_M01', 'Complexion_Birthmark_M02'):
    birthmark_piece(_tid)


def bites_no_dents(m, tid, strays=False):
    """real.bites as the row paints it (same seed, same spots, same suction bruise), without the tooth dents: the
    crisp dark-red crescents and their swollen rims, the deep-red dots circling each mark (Vex 10-17).
    strays: the inner thigh's dents are projected along its normal, which points across the gap at the other leg, so
    most of them landed on that leg's OUTER thigh as a ring of dots with no bruise (the bruise, a 3D blob, stayed on
    the inner thigh, out of sight between the legs). Each such stray ring gets a bite's bruise where it is (Vex's
    option C), so what was a ring of dots reads as the other bites do."""
    import life
    import real
    n_ = INDEX[tid]
    places = mm.MARKS[n_][3][0]
    rng = np.random.default_rng(1000 + n_)
    P = Painter(m)
    rgb, alpha = real.blank(m)
    dent = np.zeros(m.covered.shape)
    bruise = np.zeros(m.covered.shape)
    ch = life.crotch_h(P)
    tw = life.torso_width(P)
    L = landmarks(m)
    bites = []
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
        size = rng.uniform(0.9, 1.1)
        life._bite(P, dent, bruise, c, n, rng, size)
        bites.append((c, size))
    if strays:
        ink = (dent > 0.35) & m.covered
        far = ink & np.all([np.linalg.norm(m.position - c, axis=-1) > 4.0 for c, _ in bites], axis=0)
        pos, nrm = m.position[far], m.normal[far]
        left = np.ones(len(pos), bool)
        while left.any():
            g = left & (np.linalg.norm(pos - pos[np.flatnonzero(left)[0]], axis=1) < 4.0)
            g = left & (np.linalg.norm(pos - pos[g].mean(0), axis=1) < 4.0)
            left &= ~g
            c = pos[g].mean(0)
            n = nrm[g].mean(0)
            n /= np.linalg.norm(n)
            c, n = snap(m, c, n)
            P.blob_into(bruise, c, n, 0.95 * bites[0][1], gain=0.9, cap=0.55)   # life._bite's own suction bruise
    real.contusion(P, rgb, alpha, np.clip(bruise * 1.3, 0, 1), rng, 'fresh', 0.5)
    return rgb, alpha * seams.seam_fade(m)   # the row's own neck fade (the neck bite sits near it)


def no_dents_piece(tid, strays=False):
    what = 'the deep-red tooth-dent dots round the marks removed, the bruise kept'
    @piece(tid, what + ('; the dots-only ring on the outer thigh given a bruise' if strays else ''), size=2048)
    def _(m):
        return bites_no_dents(m, tid, strays)


for _tid in ('Complexion_BiteBreast_F01', 'Complexion_BiteShoulder_F01', 'Complexion_BiteShoulder_M01'):   # Vex 10-17
    no_dents_piece(_tid)
for _tid in ('Complexion_BiteThigh_F01', 'Complexion_BiteThigh_M01'):   # Vex 10-17: option C
    no_dents_piece(_tid, strays=True)


@both('Complexion_TattooHope', 'on the side of the hip (not the buttock), bolder lines')
def _(m):
    c, n = side_at(m, h_up(m, landmarks(m)['crotch'], 9.0), 1)
    return flat(m, text('Hope', 'script', bold=6), c, n, 8.6)


@both('Complexion_TattooFaith', 'moved to the inner right forearm, reading along it, wrist to elbow')
def _(m):
    long_cm = 15.0 if m.sex == 'female' else 17.0
    d = text('Faith', 'script', bold=5)
    return limb(m, d, 'forearm', 1, 'palm', long_cm * d.height / d.width, -90.0, centred=True)


@both('Complexion_TattooMinutemenWord', 'moved across the upper back, shoulder to shoulder, bowed up in the middle')
def _(m):
    c, n = front_at(m, landmarks(m)['shoulder'] - 0.02, 0.0, -1)
    return flat(m, text('Minutemen', 'western', arc=0.06), c, n, 30.0 if m.sex == 'female' else 34.0)


@both('Complexion_TattooProperty', 'moved to the tramp-stamp spot')
def _(m):
    return flat(m, text('PROPERTY', 'stencil'), *tramp(m), 15.0)


@both('Complexion_TattooOwned', 'moved to the tramp-stamp spot, clean edges')
def _(m):
    return flat(m, text('OWNED', 'pirate'), *tramp(m), 12.0)


# --- emblems
@both('Complexion_TattooAtomShoulder', 'moved to the right breast, the nipple in the crossing of the lower two rings')
def _(m):
    w = 6 * CM
    c, n = nipple(m, 1)
    # the rings (decals.emblem, a 500 px canvas) cross on the middle line 135 px below the nucleus
    d = emblem('atom')
    return flat(m, d.crop((0, 0, 500, 500)), *snap(m, c + np.array((0, 0, 1.0)) * (135 / 500 * w / CM), n, 0.2), w * 456 / 500)


@both('Complexion_TattooAtomChest', 'moved to the belly, the nucleus on the navel')
def _(m):
    return flat(m, emblem('atom'), *front_at(m, navel_h(m)), 9 * CM * 456 / 500)


@both('Complexion_TattooVaultTecArm', 'centred on the left forearm')
def _(m):
    return limb(m, emblem('vault_tec'), 'forearm', -1, 'front', 7.0, centred=True)


@both('Complexion_TattooBoSArm', 'moved onto the outer left shoulder, top to the neck, foot to the elbow, 5% smaller')
def _(m):
    return limb(m, emblem('bos'), 'upper_arm', -1, 'outer', 7.0, shift_cm=6.0)


@both('Complexion_TattooMinutemenShoulder', 'moved to the right breast, centred on the nipple')
def _(m):
    return flat(m, emblem('minutemen'), *nipple(m, 1), 6 * CM)


@both('Complexion_TattooMinutemenChest', 'moved to the left breast, centred on the nipple')
def _(m):
    return flat(m, emblem('minutemen'), *nipple(m, -1), 6 * CM)


@both('Complexion_TattooRailroadWrist', 'centred on the inner forearm, lantern head to the wrist, twice the size')
def _(m):
    return limb(m, emblem('railroad'), 'forearm', 1, 'palm', 6.0, 180.0, centred=True)


@piece('Complexion_TattooGunnersShoulder_F01', 'moved to the top of the left breast')
def _(m):
    c, n = nipple(m, -1)
    return flat(m, emblem('gunners'), *snap(m, c + np.array((0, 0, 6.0 / CM)), n, 0.2), 6 * CM)


@piece('Complexion_TattooGunnersShoulder_M01', 'moved onto the left pectoral, towards the middle')
def _(m):
    c, n = nipple(m, -1)
    return flat(m, emblem('gunners'), *snap(m, c + np.array((3.0, 0, 2.0)) / CM, n, 0.2), 6 * CM)


@both('Complexion_TattooLewdTally', 'moved to the middle of the tramp-stamp spot, smooth lines')
def _(m):
    return flat(m, _rgba(decals.tally(17)), *tramp(m), 8 * CM)


@both('Complexion_TattooGunnersTally', 'along the inner right forearm, wrist to elbow, smooth lines')
def _(m):
    d = _rgba(decals.tally(13))
    return limb(m, d, 'forearm', 1, 'palm', 14.0 * d.height / d.width, -90.0, centred=True)


@both('Complexion_TattooAceSpades', 'moved to the front of the left hip bone, tilted 40 degrees, its foot to the pelvis')
def _(m):
    h = h_up(m, landmarks(m)['crotch'], 11.0)
    c, n = front_at(m, h, -0.7 * half_width(m, h))
    return flat(m, _rgba(decals.card()), c, n, 4.5 * CM, rotate_deg=40.0)


@piece('Complexion_TattooDice_F01', 'snake eyes')
def _(m):
    c, n, _ = decals.anchor(m, 'upper_arm', -1)
    return flat(m, snake_eyes(), c, n, 5.5 * CM)


@piece('Complexion_TattooDice_M01', 'snake eyes, moved off the armpit to the outer arm')
def _(m):
    return limb(m, snake_eyes(), 'upper_arm', -1, 'outer', 6.5)


@both('Complexion_TattooDollar', 'moved to the middle of the pelvis')
def _(m):
    return flat(m, _rgba(decals.dollar()), *pelvis(m), 5 * CM)


def pelvis(m):
    return front_at(m, h_up(m, landmarks(m)['crotch'], 13.0 if m.sex == 'female' else 14.0))


@piece('Complexion_TattooVault81_M01', '2 cm lower')
def _(m):
    c, n, _ = decals.anchor(m, 'upper_arm', 1)
    c, n = snap(m, c + arm_axis(m, 1) * (2.0 / CM), n)
    return flat(m, _rgba(decals.vault_number(81)), c, n, 5.5 * CM)


# --- flash
@both('Complexion_FlashNauticalStar', 'moved to the inner right wrist, a point to the hand (men 10% larger)')
def _(m):
    return _wrist_star(m)


def _wrist_star(m):
    buf = io.BytesIO()
    flash.nautical_star().save(buf, 'PNG')
    hgt = 5.7 * (1.0 if m.sex == 'female' else 1.1)
    return artist_flat.place_design(m, buf, 'forearm', 1, 'palm', hgt, 0.0, 180.0, 0.0, False, 2.0)


@both('Complexion_FlashNauticalStarHip', 'red instead of blue, moved to the front of the left hip')
def _(m):
    h = h_up(m, landmarks(m)['crotch'], 8.0)
    c, n = front_at(m, h, -0.75 * half_width(m, h))
    return flash_at(m, 'Complexion_FlashNauticalStarHip_' + _sfx(m), design=flash.nautical_star(flash.RED), at=(c, n))


def _sfx(m):
    return 'F01' if m.sex == 'female' else 'M01'


@piece('Complexion_FlashLightning_F01', '20% smaller')
def _(m):
    return flash_at(m, 'Complexion_FlashLightning_F01', width=3.0 * 0.8)


@piece('Complexion_FlashRadiation_F01', 'moved towards the chest, away from the armpit', size=2048)
def _(m):
    return flash_at(m, 'Complexion_FlashRadiation_F01', move=lambda m, c, n: np.array((2.5, 2.5, 0.0)))


@piece('Complexion_FlashCherries_M01', '0.5 cm higher', size=2048)
def _(m):
    return flash_at(m, 'Complexion_FlashCherries_M01', move=lambda m, c, n: np.array((0, 0, 0.5)))


@piece('Complexion_FlashSwallowPair_M01', '1 cm lower')
def _(m):
    return flash_at(m, 'Complexion_FlashSwallowPair_M01', move=lambda m, c, n: np.array((0, 0, -1.0)))


@both('Complexion_FlashSwallow', 'moved to the left hip, flying towards the front of the body')
def _(m):
    c, n = side_at(m, h_up(m, landmarks(m)['crotch'], 9.0), -1)
    d = original_flash('Complexion_FlashSwallow_' + _sfx(m))[0]
    return flash_at(m, 'Complexion_FlashSwallow_' + _sfx(m), design=d.transpose(Image.FLIP_LEFT_RIGHT), at=(c, n))


@piece('Complexion_FlashEagle_F01', '25% smaller, 1 cm lower')
def _(m):
    return flash_at(m, 'Complexion_FlashEagle_F01', width=22.0 * 0.75, move=lambda m, c, n: np.array((0, 0, -1.0)))


@piece('Complexion_FlashEagle_M01', '1 cm lower')
def _(m):
    return flash_at(m, 'Complexion_FlashEagle_M01', move=lambda m, c, n: np.array((0, 0, -1.0)))


@piece('Complexion_FlashEagleBack_F01', '10% smaller, centred')
def _(m):
    return flash_at(m, 'Complexion_FlashEagleBack_F01', width=24.0 * 0.9)


@piece('Complexion_FlashEagleBack_M01', "turned to the women's angle (the left wing lower)")
def _(m):
    return flash_at(m, 'Complexion_FlashEagleBack_M01', rotate=original_flash('Complexion_FlashEagleBack_F01')[6])


@both('Complexion_FlashRevolver', 'turned upside down')
def _(m):
    tid = 'Complexion_FlashRevolver_' + _sfx(m)
    return flash_at(m, tid, design=original_flash(tid)[0].transpose(Image.FLIP_TOP_BOTTOM))


@piece('Complexion_FlashHeartMom_M01', 'moved to the middle of the outer shoulder')
def _(m):
    return limb(m, flash.heart_banner('MOM', px=1200), 'upper_arm', 1, 'outer', 6.7, shift_cm=6.0)


@both('Complexion_FlashHeartTrueLove', 'clear lettering, no pixels')
def _(m):
    d0, spot, side, w, faded, crude, rot, seed = original_flash('Complexion_FlashHeartTrueLove_' + _sfx(m))
    c, n, _ = decals.anchor(m, spot, side)
    return flat(m, flash.heart_banner('TRUE LOVE', font='block', px=1200), c, n, w * CM, np.degrees(rot))


@both('Complexion_FlashHeartNuka', 'clear lettering, no pixels')
def _(m):
    d0, spot, side, w, faded, crude, rot, seed = original_flash('Complexion_FlashHeartNuka_' + _sfx(m))
    c, n, _ = decals.anchor(m, spot, side)
    return flat(m, flash.heart_banner('NUKA', font='block', px=1200), c, n, w * CM, np.degrees(rot))


# --- lewd: block letters for the stencil ones (Vex: "none stencil"), arrows to the top of the cleft
def cleft(m):
    return front_at(m, cleft_h(m), 0.0, -1)


def pubic(m):
    c, n, _ = decals.anchor(m, 'pubic', 0)
    return c, n


ARROWS = [('Entry', 'ENTRY', 'block', 9), ('InsertHere', 'INSERT HERE', 'pirate', 11), ('CumHere', 'CUM HERE', 'block', 11),
          ('Open247', 'OPEN 24/7', 'block', 11)]
for name, words, font, w_units in ARROWS:
    def front(m, words=words, font=font, w=w_units):
        return flat(m, arrow(words, font), *pubic(m), w * CM)

    def back(m, words=words, font=font, w=w_units):
        return flat(m, arrow(words, font), *cleft(m), w * CM, anchor='bottom')
    piece(f'Complexion_TattooLewd{name}_F01', {'Entry': 'block letters', 'InsertHere': 'clean edges',
                                              'CumHere': 'a new readable font', 'Open247': 'block letters, black'}[name])(front)
    for s in 'FM':
        piece(f'Complexion_TattooLewd{name}Back_{s}01', 'copy: tramp stamp, the arrow to the top of the cleft')(back)


@both('Complexion_TattooLewdBackDoor', 'tramp stamp, the arrow to the top of the cleft, clean letters (+ men)')
def _(m):
    return flat(m, arrow('Back Door', 'script', bold=4), *cleft(m), 12 * CM, anchor='bottom')


@both('Complexion_TattooLewdSpreadMe', 'SPREAD on the left cheek, ME on the right, low and central (+ men)')
def _(m):
    parts = []
    letter_cm = 2.6 if m.sex == 'female' else 3.0
    for word, side in (('SPREAD', -1), ('ME', 1)):
        c, n, _ = decals.anchor(m, 'butt', side)
        if m.sex == 'female':   # the butt anchor sits ~4 cm above the fullest point and near the middle (10-14)
            c, n = snap(m, c + np.array((side * 2.0, 0, -4.5)) / CM, n)
        else:
            c, n = snap(m, c + np.array((0, 0, -1.5)) / CM, n)
        d = text(word, 'pirate')
        parts.append(flat(m, d, c, n, letter_cm * d.width / d.height))
    return over_all(parts)


@both('Complexion_TattooLewdRideMe', 'moved to the middle of the pelvis, block letters (+ men)')
def _(m):
    return flat(m, text('RIDE ME'), *pelvis(m), 10.0)


@both('Complexion_TattooLewdFuckMe', 'moved to the tramp stamp, above an arrow to the top of the cleft (+ men)')
def _(m):
    return flat(m, arrow('FUCK ME'), *cleft(m), 12.0, anchor='bottom')


def above_cock(m):
    """Above the men's pubic spot, clear of the cock (which covered words centred there)."""
    return front_at(m, h_up(m, landmarks(m)['crotch'], 10.0))


@piece('Complexion_TattooLewdSuck_M01', '"SUCK IT", block letters, no arrow, centred above the cock')
def _(m):
    return flat(m, text('SUCK IT'), *above_cock(m), 10.0)


@both('Complexion_TattooLewdCumDump', 'raised: the arrow to the top of the cleft (+ women)')
def _(m):
    return flat(m, arrow('CUM DUMP', 'pirate'), *cleft(m), 11 * CM, anchor='bottom')


@piece('Complexion_TattooLewdCumDumpFront_F01', 'new: on the pelvis, the arrow to just above the clit')
def _(m):
    return flat(m, arrow('CUM DUMP', 'pirate'), *front_at(m, h_up(m, landmarks(m)['crotch'], 4.5)), 11 * CM,
                anchor='bottom')


@piece('Complexion_TattooLewdFreeUse_F01', 'block letters')
def _(m):
    return flat(m, arrow('FREE USE'), *pubic(m), 11 * CM)


@piece('Complexion_TattooLewdFreeUse_M01', 'block letters, no arrow, above the cock')
def _(m):
    return flat(m, text('FREE USE'), *above_cock(m), 11 * CM * 0.9)


@both('Complexion_TattooLewdSlut', 'block letters, moved to the tramp stamp')
def _(m):
    return flat(m, text('SLUT'), *tramp(m), 10.0)


# ---------------------------------------------------------------- run

def render(out, only=(), sex='', resume=False, sheets=True):
    todo = sorted((p for p in PIECES.items() if (not only or p[0].startswith(only)) and (not sex or p[1]['sex'] == sex)
                   and not (resume and (out / 'marks' / f'{p[0]}_d.png').exists())),
                  key=lambda kv: (kv[1]['hands'], kv[1]['sex'], kv[1]['size'], kv[0]))
    key, m = None, None
    for tid, p in todo:
        k = (p['hands'], p['sex'], p['size'])
        if k != key:
            m = None
            m = hands.HandMap(mm.DATA, p['sex'], p['size']) if p['hands'] else UVMap(mm.DATA, p['sex'], p['size'])
            key = k
        print(tid, '--', p['what'], flush=True)
        rgb, alpha = p['fn'](m)
        if p['hands']:
            artist_art.save(out, tid, m, rgb, alpha, fade=None)
            artist_hands.preview(m, out / 'marks' / f'{tid}_d.png', out / f'{tid}.jpg', f'{tid}: {p["what"]}')
        else:
            artist_art.save(out, tid, m, rgb, alpha)
        del rgb, alpha
    bases = sorted({t.rsplit('_', 1)[0] for t, p in todo if not p['hands']})
    if bases and sheets:
        artist_art.render(out, bases)


LIVE = '5c0a729'   # the 0.1.7 release: the names testers' LooksMenu shows today


def live_names():
    """(id, gender) -> name, as the released overlays.json has them."""
    import json
    raw = subprocess.run(['git', 'show', f'{LIVE}:data/F4SE/Plugins/F4EE/Overlays/Complexion.esp/overlays.json'],
                         cwd=HERE, capture_output=True, check=True).stdout
    return {(e['id'], e['gender']): e['name'] for e in json.loads(raw)}


def shown_name(tid, names):
    female = mm.MARKS[INDEX[tid]][1] == 'female'
    return f'{names[(tid, 1 if female else 0)]} ({"women" if female else "men"})'


def multiply(a, b):
    """Two multiplier textures as one (each factor = texel / NEUTRAL)."""
    fa = np.asarray(Image.open(a).convert('RGB'), dtype=np.float64) / 255.0 / mm.NEUTRAL
    fb = np.asarray(Image.open(b).convert('RGB'), dtype=np.float64) / 255.0 / mm.NEUTRAL
    return Image.fromarray(np.uint8(np.clip(fa * fb * mm.NEUTRAL, 0, 1) * 255 + 0.5), 'RGB')


# The hands have their own slot (4): the knuckle pieces borrow nail templates, two words (both hands) a texture.
HAND_PAIRS = [('Complexion_TattooLove', 'Complexion_TattooHate'), ('Complexion_TattooKill', 'Complexion_TattooRust'),
              ('Complexion_TattooHateLeftHand', 'Complexion_TattooLoveRightHand'),
              ('Complexion_TattooRustLeftHand', 'Complexion_TattooKillRightHand')]


def test_mods(out, dest):
    """Test mods from <out>/marks: Textures/Overlays/Complexion/*_d.dds only. A redrawn template ships under its own
    id; a NEW one borrows a template Vex removed (same sex); the knuckles borrow nail templates. The men have two nail
    templates, so their mirrored copies come in a second mod over the first."""
    marks = out / 'marks'
    names = live_names()
    # borrow only removed templates whose name in LooksMenu is the only one of its kind, so a tester can find it
    count = {}
    for (t, g), nm in names.items():
        count[(nm, g)] = count.get((nm, g), 0) + 1
    removed = {s: [t for t in sorted(mm.REMOVED) if t.endswith(f'_{s}01')
                   and count[(names[(t, 1 if s == 'F' else 0)], 1 if s == 'F' else 0)] == 1] for s in 'FM'}
    nails = {s: [r[0] for r in mm.MARKS if r[2] == 'nails' and r[0].endswith(f'_{s}01') and not r[5].get('retired')] for s in 'FM'}
    mods = {1: {}, 2: {}}          # mod -> {borrowed or own id: png or Image}
    lines = {1: [], 2: []}  # (the knuckles never need a third)
    for tid in sorted(PIECES):
        if PIECES[tid]['hands'] or not (marks / f'{tid}_d.png').exists():
            continue
        if tid in INDEX and not mm.MARKS[INDEX[tid]][5].get('retired'):
            mods[1][tid] = marks / f'{tid}_d.png'
            g = 1 if tid.endswith('_F01') else 0
            twins = count[(names[(tid, g)], g)]
            lines[1].append(f'{shown_name(tid, names)}  ->  {PIECES[tid]["what"]}'
                            + (f'   [{twins} entries have this name: one of them shows the new version]' if twins > 1 else ''))
        else:
            s = tid[-3]
            slot = removed[s].pop(0)
            mods[1][slot] = marks / f'{tid}_d.png'
            lines[1].append(f'{shown_name(slot, names)}  ->  NEW {tid}: {PIECES[tid]["what"]}')
    for s in 'FM':
        free, mod = list(nails[s]), 1
        for k, (left, right) in enumerate(HAND_PAIRS):
            if not free:   # out of nail templates: the rest go in a second mod, over the same ones
                free, mod = list(nails[s]), mod + 1
            slot = free.pop(0)
            img = multiply(marks / f'{left}_{s}01_d.png', marks / f'{right}_{s}01_d.png')
            mods[mod][slot] = img
            lines[mod].append(f'{shown_name(slot, names)}  ->  hands: {left.split("Tattoo")[1]} (left hand) + '
                              f'{right.split("Tattoo")[1]} (right hand), {"women" if s == "F" else "men"}')
    dest.mkdir(parents=True, exist_ok=True)
    made = []
    for mod, files in mods.items():
        if not files:
            continue
        name = 'Complexion_Vex_reworks_test' if mod == 1 else 'Complexion_Vex_reworks_test2_mens_mirrored_knuckles'
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            tex = tmp / 'mod' / 'Textures' / 'Overlays' / 'Complexion'
            tex.mkdir(parents=True)
            for slot, src in files.items():
                png = tmp / f'{slot}_d.png'
                (src if isinstance(src, Image.Image) else Image.open(src)).save(png)
                mm.encode(mm.texconv(), png, tex, slot)
            z = dest / f'{name}.zip'
            z.unlink(missing_ok=True)
            subprocess.run(['7z', 'a', '-tzip', str(z.resolve()), 'Textures'], cwd=tmp / 'mod', check=True, capture_output=True)
        (dest / f'{name}.txt').write_text('In LooksMenu, pick the entry on the left to see the piece on the right.\n\n'
                                          + '\n'.join(lines[mod]) + '\n', encoding='utf-8')
        made.append(z)
        print(z, len(files), 'textures')
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=pathlib.Path)
    ap.add_argument('--only', default='')
    ap.add_argument('--sex', choices=('female', 'male'), default='')
    ap.add_argument('--resume', action='store_true', help='skip pieces already in <out>/marks')
    ap.add_argument('--no-sheets', action='store_true')
    ap.add_argument('--test-mod', type=pathlib.Path, default=None, help='build the test mods from <out>/marks into here')
    a = ap.parse_args()
    if a.test_mod:
        test_mods(a.out, a.test_mod)
        return
    render(a.out, tuple(x for x in a.only.split(',') if x), a.sex, a.resume, not a.no_sheets)


if __name__ == '__main__':
    main()
