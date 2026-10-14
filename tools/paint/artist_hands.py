"""An artist's tattoo on the HANDS: the hands are their own mesh (LooksMenu overlay slot 4, like the nails, hands.py),
so a body template never reaches them; a hand piece is a hands template. Previewed on the hands themselves, back and
palm of each, before anything goes into the build (alasdairn's rule, 2026-10-14). For Vex, 2026-10-14.

    python tools/paint/artist_hands.py <out dir> <png> --id Complexion_VexHand_F01 --place back --side right
        --height-cm 7 [--width-cm W] [--rotate DEG] [--shift-cm S] [--across-cm A] [--flip]
    python tools/paint/artist_hands.py <out dir> <png> --id Complexion_VexHand_F01 --place finger --finger 2
        --segment 1 --face back --side left --height-cm 1.5
    python tools/paint/artist_hands.py <out dir> <png laid out on the hands UV> --id Complexion_VexHand_F01 --uv
    python tools/paint/artist_hands.py --uv-template <dir>     the hands' UV layouts for painting by hand

back / palm: the design is laid flat on the back (or palm) of the hand like a stamp, its top towards the fingertips,
centred on the middle of the hand; --shift-cm moves it towards the fingertips (negative: towards the wrist),
--across-cm towards the thumb. Fingers seen from that side are covered too, so knuckle letters can be one design.
finger: wrapped round one finger segment (1 nearest the hand .. 3 the tip; finger 1 thumb .. 5 little), its top
towards the fingertip; --face back / palm / thumb / little turns it round the finger; --width-cm up to the finger's
girth wraps it all the way round (a ring).

The wrist end of the hands mesh is a seam with the body: ink there fades over its last ~1 cm, as an artist's piece
does at the body's wrist. Sizes are centimetres on the skin (1 game unit = 1.4287 cm). New hand templates are 2048.
"""
import argparse
import collections
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import artist_art  # noqa: E402
import hands  # noqa: E402
import make_marks as mm  # noqa: E402
import seams  # noqa: E402
from artist_flat import CM, premultiplied_resize  # noqa: E402
from preview import SKIN  # noqa: E402


def wrist_seam(m):
    """The hands mesh's open edges, with its UV splits welded: the wrist loops (measured: the only open edges)."""
    uniq, inv = np.unique(np.round(m.vertices, 3), axis=0, return_inverse=True)
    inv = inv.ravel()
    edges = collections.Counter()
    for t in m.triangles:
        a, b, c = inv[t]
        for e in ((a, b), (b, c), (c, a)):
            edges[(min(e), max(e))] += 1
    return uniq[sorted({v for e, n in edges.items() if n == 1 for v in e})]


def wrist_fade(m, start=seams.TATTOO_FADE[0], width=seams.TATTOO_FADE[1]):
    """Per texel 0..1: 0 at the wrist seam, 1 from start + width away (smoothstep), as seams.seam_fade on the body."""
    d = np.full(m.covered.shape, np.inf)
    d[m.covered] = cKDTree(wrist_seam(m)).query(m.position[m.covered])[0]
    t = np.clip((d - start) / width, 0, 1)
    return t * t * (3 - 2 * t)


def centre(m, side, bone):
    return hands._bone_vertices(m, f'{"L" if side < 0 else "R"}Arm_{bone}').mean(0)


def hand_frame(m, side):
    """The hand's own frame from its bones: o the middle of the hand, f towards the fingertips, p the way the palm
    faces (fingers x thumb on the left hand, thumb x fingers on the right, as artist_flat.palm_normal)."""
    o = centre(m, side, 'Hand')
    f = np.mean([centre(m, side, f'Finger{k}1') for k in (2, 3, 4, 5)], 0) - o
    f /= np.linalg.norm(f)
    t = centre(m, side, 'Finger13') - o
    t -= f * (t @ f)
    p = np.cross(f, t) if side < 0 else np.cross(t, f)
    return o, f, p / np.linalg.norm(p)


def texels_per_unit(m):
    """Texture texels per game unit of skin on the hands (the median over triangles)."""
    V, T, s = m.vertices, m.triangles, m.size
    uv = getattr(m, 'uv', None)
    if uv is None:
        import body
        name, shape = hands.HANDS[m.sex]
        uv = body.read_shape(pathlib.Path(mm.DATA) / body.ASSETS / f'{name}.nif', shape)[1]
        m.uv = uv
    a3 = np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)
    u = uv[T] * s
    e1, e2 = u[:, 1] - u[:, 0], u[:, 2] - u[:, 0]
    a2 = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    ok = a3 > 1e-6
    return float(np.sqrt(np.median(a2[ok] / a3[ok])))


def side_mask(m, side):
    return m.covered & np.isin(m.bone, [i for i, b in enumerate(m.bone_names) if b.startswith('L' if side < 0 else 'R')])


def sample(m, design, zone, u, v, width, height):
    """The design sampled at (u, v) in units from its centre (u right, v up) over the texels of zone."""
    tpu = texels_per_unit(m)
    dw, dh = max(int(width * tpu * 1.5), 8), max(int(height * tpu * 1.5), 8)
    d = premultiplied_resize(design, dw, dh)
    x = (u / width + 0.5) * dw - 0.5
    y = (0.5 - v / height) * dh - 0.5
    rgb = np.ones(m.covered.shape + (3,)) * mm.SKIN
    alpha = np.zeros(m.covered.shape)
    a = ndimage.map_coordinates(d[..., 3], [y, x], order=1, mode='constant', cval=0.0)
    pm = [ndimage.map_coordinates(d[..., k] * d[..., 3], [y, x], order=1, mode='constant', cval=0.0) for k in range(3)]
    alpha[zone] = a
    rgb[zone] = np.clip(np.stack(pm, -1) / np.maximum(a, 1e-4)[:, None], 0, 1)
    return rgb, alpha


def stamp(m, design, side, palm, height, width, rotate, shift, across):
    """Flat on the back (or palm) of the hand, seen straight on: its top towards the fingertips."""
    o, f, p = hand_frame(m, side)
    out = p if palm else -p            # towards the viewer
    right = np.cross(-out, f)          # forward x up, forward = -out
    thumb = centre(m, side, 'Finger13') - o
    # across: midway over the four knuckles (the Hand bone's skin sits towards the little finger on the male hand)
    knuckles = np.mean([centre(m, side, f'Finger{k}1') for k in (2, 3, 4, 5)], 0) - o
    c = o + right * (knuckles @ right) + f * shift + (np.sign(thumb @ right) * right) * across
    q = m.position - c
    u, v = q @ right, q @ f
    if rotate:
        cr, sr = np.cos(rotate), np.sin(rotate)
        u, v = u * cr - v * sr, u * sr + v * cr
    facing = m.normal @ out
    zone = side_mask(m, side) & (facing > 0.05) & (np.abs(u) < width * 0.75) & (np.abs(v) < height * 0.75)
    rgb, alpha = sample(m, design, zone, u[zone], v[zone], width, height)
    alpha *= np.clip((facing - 0.05) / 0.2, 0, 1)   # soft where the skin turns away round the hand's edge
    return rgb, alpha


def ring(m, design, side, finger, segment, face, height, width, rotate, shift):
    """Wrapped round one finger segment, like artist_flat.wrap round a limb: height along it, width round it."""
    bone = f'Finger{finger}{segment}'
    nxt = f'Finger{finger}{segment + 1}' if segment < 3 else None
    a0 = centre(m, side, bone)
    if nxt:
        axis = centre(m, side, nxt) - a0
    else:
        axis = a0 - centre(m, side, f'Finger{finger}2')
    axis /= np.linalg.norm(axis)
    names = [f'{"L" if side < 0 else "R"}Arm_Finger{finger}{k}' for k in (1, 2, 3)]
    on = m.covered & np.isin(m.bone, [m.bone_names.index(n) for n in names if n in m.bone_names])
    seg = m.bone_mask(f'{"L" if side < 0 else "R"}Arm_{bone}')
    P = m.position
    pts = P[seg]
    c = pts.mean(0) + axis * shift
    q = P - c
    along = q @ axis
    rad = q - np.multiply.outer(along, axis)
    r0 = float(np.median(np.linalg.norm(rad[seg], axis=-1)))
    _, f, p = hand_frame(m, side)
    thumb = centre(m, side, 'Finger13') - centre(m, side, 'Hand')
    want = {'back': -p, 'palm': p, 'thumb': thumb, 'little': -thumb}[face]
    want = want - axis * (want @ axis)
    e1 = want / np.linalg.norm(want)
    e2 = np.cross(axis, e1)
    theta = np.arctan2(rad @ e2, rad @ e1)
    arc = theta * np.linalg.norm(rad, axis=-1)
    if rotate:
        cr, sr = np.cos(rotate), np.sin(rotate)
        arc, along = arc * cr - along * sr, arc * sr + along * cr
    zone = on & (np.abs(along) < height * 0.75) & (np.abs(arc) < width * 0.75) & (np.linalg.norm(rad, axis=-1) < r0 * 2)
    print(f'  finger {finger} segment {segment}: girth {2 * np.pi * r0 * CM:.1f} cm')
    return sample(m, design, zone, arc[zone], along[zone], width, height)


def place_on_hand(m, png, place, side, height_cm=6.0, width_cm=0.0, rotate_deg=0.0, shift_cm=0.0, across_cm=0.0,
                  flip=False, finger=2, segment=1, face='back'):
    """rgb, alpha on the hands' UV map, wrist fade included (a hands painter can rebuild a piece from this)."""
    design = Image.open(png).convert('RGBA')
    box = design.getbbox()
    if box:
        design = design.crop(box)
    if flip:
        design = design.transpose(Image.FLIP_LEFT_RIGHT)
    height = height_cm / CM
    width = width_cm / CM if width_cm else height * design.width / design.height
    if place in ('back', 'palm'):
        rgb, alpha = stamp(m, design, side, place == 'palm', height, width, np.radians(rotate_deg), shift_cm / CM,
                           across_cm / CM)
    elif place == 'finger':
        rgb, alpha = ring(m, design, side, finger, segment, face, height, width, np.radians(rotate_deg), shift_cm / CM)
    else:
        raise ValueError(f'unknown hand place {place!r}: back, palm, finger')
    return rgb, alpha * wrist_fade(m)


# --- the preview: the hands themselves, rasterized like collage.Views but from the hand's own frame -----------------

def view(m, tex, side, palm, scale=70.0):
    """One hand seen straight on from its back (or palm), fingertips up, the multiplier applied to plain skin."""
    import body
    name, shape = hands.HANDS[m.sex]
    V, uv, T, bones = body.read_shape(pathlib.Path(mm.DATA) / body.ASSETS / f'{name}.nif', shape)
    pref = 'L' if side < 0 else 'R'
    keep = np.array([b.startswith(pref) for b in bones])
    T = T[keep[T].all(1)]
    o, f, p = hand_frame(m, side)
    out = p if palm else -p
    right = np.cross(-out, f)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, T[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    light = out + 0.4 * f + 0.3 * right
    light /= np.linalg.norm(light)
    vshade = np.clip(vn @ light, 0.15, 1.0) * 0.85 + 0.15
    used = np.unique(T)
    sx_all, sy_all = (V - o) @ right, -((V - o) @ f)
    lo_x, hi_x = sx_all[used].min(), sx_all[used].max()
    lo_y, hi_y = sy_all[used].min(), sy_all[used].max()
    sx, sy = (sx_all - lo_x) * scale + 20, (sy_all - lo_y) * scale + 20
    W, H = int((hi_x - lo_x) * scale) + 40, int((hi_y - lo_y) * scale) + 40
    depth = (V - o) @ out
    zbuf = np.full((H, W), -np.inf)
    U, Vv, shade = np.full((H, W), -1.0), np.full((H, W), -1.0), np.zeros((H, W))
    for t in T:
        xs, ys = sx[t], sy[t]
        x0, x1 = int(max(0, np.floor(xs.min()))), int(min(W - 1, np.ceil(xs.max())))
        y0, y1 = int(max(0, np.floor(ys.min()))), int(min(H - 1, np.ceil(ys.max())))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(d) < 1e-9:
            continue
        l1 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
        l2 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        if not inside.any():
            continue
        z = l1 * depth[t[0]] + l2 * depth[t[1]] + l3 * depth[t[2]]
        yy, xx = np.nonzero(inside)
        yy, xx = yy + y0, xx + x0
        zi = z[inside]
        win = zi > zbuf[yy, xx]
        yy, xx = yy[win], xx[win]
        a, b, c = l1[inside][win], l2[inside][win], l3[inside][win]
        zbuf[yy, xx] = zi[win]
        U[yy, xx] = a * uv[t[0], 0] + b * uv[t[1], 0] + c * uv[t[2], 0]
        Vv[yy, xx] = a * uv[t[0], 1] + b * uv[t[1], 1] + c * uv[t[2], 1]
        shade[yy, xx] = a * vshade[t[0]] + b * vshade[t[1]] + c * vshade[t[2]]
    mask = U >= 0
    s = tex.shape[0]
    col = np.clip((U * s).astype(int), 0, s - 1)
    row = np.clip((Vv * s).astype(int), 0, s - 1)
    img = np.full((H, W, 3), 0.1)
    img[mask] = np.clip(SKIN * tex[row[mask], col[mask]] * 2.0, 0, 1) * shade[mask][:, None]
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def preview(m, multiplier_png, out_jpg, title):
    """Both hands, back and palm, side by side (left hand: back, palm; right hand: palm, back -- as held out)."""
    tex = np.asarray(Image.open(multiplier_png).convert('RGB'), dtype=np.float64) / 255.0
    tiles = [(view(m, tex, -1, False), 'left, back'), (view(m, tex, -1, True), 'left, palm'),
             (view(m, tex, 1, True), 'right, palm'), (view(m, tex, 1, False), 'right, back')]
    h = max(t.height for t, _ in tiles) + 40
    w = sum(t.width for t, _ in tiles) + 12 * (len(tiles) + 1)
    sheet = Image.new('RGB', (w, h + 36), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    d.text((12, 8), title, fill=(236, 226, 200))
    x = 12
    for t, label in tiles:
        sheet.paste(t, (x, 36))
        d.text((x + 6, 36 + t.height + 6), label, fill=(236, 226, 200))
        x += t.width + 12
    sheet.save(out_jpg, quality=92)
    print(out_jpg)


def uv_templates(out, size=2048):
    """The hands' UV layouts to paint on: skin areas shaded by where they face (back of the hand blue, palm yellow,
    the rest grey), the wrist fade band orange, the triangles drawn over."""
    import body
    out.mkdir(parents=True, exist_ok=True)
    for sex in ('female', 'male'):
        m = hands.HandMap(mm.DATA, sex, size)
        img = np.zeros((size, size, 4), np.uint8)
        img[m.covered] = (225, 225, 225, 255)
        for side in (-1, 1):
            _, _, p = hand_frame(m, side)
            sm = side_mask(m, side)
            img[sm & (m.normal @ -p > 0.35)] = (170, 200, 240, 255)   # back of the hand and fingers
            img[sm & (m.normal @ p > 0.35)] = (245, 225, 150, 255)    # palm side
        img[m.covered & (wrist_fade(m) < 0.999)] = (255, 170, 120, 255)
        im = Image.fromarray(img, 'RGBA')
        d = ImageDraw.Draw(im)
        name, shape = hands.HANDS[sex]
        uv, tris = body.read_shape(pathlib.Path(mm.DATA) / body.ASSETS / f'{name}.nif', shape)[1:3]
        px = uv * size
        for t in tris:
            a, b, c = (tuple(px[i]) for i in t)
            d.line((a, b, c, a), fill=(90, 90, 90, 255), width=1)
        f = out / f'Complexion_UV_hands_{sex}_{size}.png'
        im.save(f)
        print(f)


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--uv-template':
        uv_templates(pathlib.Path(sys.argv[2]))
        return
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=pathlib.Path)
    ap.add_argument('png', type=pathlib.Path)
    ap.add_argument('--id', required=True)
    ap.add_argument('--uv', action='store_true', help='the PNG is already laid out on the hands UV')
    ap.add_argument('--place', choices=('back', 'palm', 'finger'), default='back')
    ap.add_argument('--side', choices=('left', 'right'), default='right')
    ap.add_argument('--height-cm', type=float, default=6.0)
    ap.add_argument('--width-cm', type=float, default=0.0)
    ap.add_argument('--rotate', type=float, default=0.0, help='degrees, clockwise as seen on the skin')
    ap.add_argument('--shift-cm', type=float, default=0.0)
    ap.add_argument('--across-cm', type=float, default=0.0)
    ap.add_argument('--finger', type=int, default=2, choices=range(1, 6))
    ap.add_argument('--segment', type=int, default=1, choices=range(1, 4))
    ap.add_argument('--face', choices=('back', 'palm', 'thumb', 'little'), default='back')
    ap.add_argument('--size', type=int, default=2048)
    ap.add_argument('--flip', action='store_true')
    a = ap.parse_args()
    row = next((r for r in mm.MARKS if r[0] == a.id), None)
    sex = row[1] if row else ('female' if a.id.split('_')[-1].startswith('F') else 'male')
    size = row[4] if row else a.size
    m = hands.HandMap(mm.DATA, sex, size)
    if a.uv:
        im = Image.open(a.png)
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        rgb, alpha = artist_art.ink_of(im)
        alpha = alpha * wrist_fade(m)
    else:
        rgb, alpha = place_on_hand(m, a.png, a.place, -1 if a.side == 'left' else 1, a.height_cm, a.width_cm,
                                   a.rotate, a.shift_cm, a.across_cm, a.flip, a.finger, a.segment, a.face)
    artist_art.save(a.out, a.id, m, rgb, alpha, fade=None)
    preview(m, a.out / 'marks' / f'{a.id}_d.png', a.out / f'{a.id}.jpg', a.id)


if __name__ == '__main__':
    main()
