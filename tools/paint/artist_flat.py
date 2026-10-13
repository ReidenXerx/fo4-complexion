"""An artist's FLAT tattoo design (a PNG of the design on transparency, not laid out on the UV) wrapped onto the
body at a named place, then previewed like artist_art.py. For pieces that cross a UV seam (inner arms, inner legs),
which are hard to split by hand (Vex, 2026-10-14).

    python tools/paint/artist_flat.py <out dir> <png> --id Complexion_VexAnchor_F01 --place forearm --side left
        --face inner --height-cm 8 [--width-cm W] [--rotate DEG] [--shift-cm S] [--flip]

On a limb (upper_arm, forearm, thigh, thigh_back, calf) the design is WRAPPED round it: its height runs along the limb,
its width round it, measured on the skin, so it does not stretch towards the sides as a flat projection would. The
top of the design points up the limb, towards the body. Elsewhere it is projected flat, image-up = world-up.

--face turns a limb piece round the limb: palm (the inside of the forearm: the way the palm faces, from the hand's
own bones -- in the rest pose that is mostly towards the body and a little back), back_of_hand, front, back, inner
(towards the body's middle), outer, up, down. --shift-cm moves it along the limb (+ towards the body);
--from-wrist-cm / --from-ankle-cm put its lower edge that far from the end of the limb instead. Sizes are in centimetres on the body (1 game unit =
1.4287 cm). Placement words come from decals.anchor.
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import artist_art  # noqa: E402
import decals  # noqa: E402
import flash  # noqa: E402
import make_marks as mm  # noqa: E402
from body import UVMap  # noqa: E402

CM = 1.4287  # centimetres per game unit
LIMBS = ('upper_arm', 'forearm', 'thigh', 'thigh_back', 'calf')
FACES = {'front': (0, 1, 0), 'back': (0, -1, 0), 'up': (0, 0, 1), 'down': (0, 0, -1)}


def premultiplied_resize(img, w, h):
    a = np.asarray(img.convert('RGBA'), dtype=np.float64) / 255.0
    pm = np.dstack([a[..., :3] * a[..., 3:], a[..., 3]])
    out = np.stack([np.asarray(Image.fromarray(pm[..., k].astype(np.float32), 'F').resize((w, h), Image.LANCZOS))
                    for k in range(4)], -1)
    out[..., 3] = np.clip(out[..., 3], 0, 1)
    out[..., :3] = np.clip(out[..., :3] / np.maximum(out[..., 3:], 1e-4), 0, 1)
    return out


def palm_normal(sex, side):
    """The way the palm faces, from the hand bones: fingers x thumb (left hand), thumb x fingers (right)."""
    import hands
    h = hands.HandMap(mm.DATA, sex, 256)
    arm = 'LArm' if side < 0 else 'RArm'

    def centre(name):
        return np.asarray(hands._bone_vertices(h, f'{arm}_{name}')).reshape(-1, 3).mean(0)
    base = centre('Hand')
    f = centre('Finger33') - base
    f /= np.linalg.norm(f)
    t = centre('Finger13') - base
    t -= f * (t @ f)
    p = np.cross(f, t) if side < 0 else np.cross(t, f)
    return p / np.linalg.norm(p)


def wrap(m, design, place, side, face, height, width, rotate, shift, flip, from_end=None):
    """rgb, alpha on the UV map: the design wrapped round a limb."""
    c, n, _ = decals.anchor(m, place, side)
    pos = m.position
    reg = 'arm' if 'arm' in place else 'leg'
    P = decals.Painter(m)
    limb = m.covered & P.reg(reg) & ((pos[..., 0] * side > 0) if side else True)
    near = limb & (np.linalg.norm(pos - c, axis=-1) < 6.0)
    Q = pos[near]
    w, v = np.linalg.eigh(np.cov((Q - Q.mean(0)).T))
    axis = v[:, -1]
    toward_body = np.array((-side, 0.0, 0.0)) if reg == 'arm' else np.array((0.0, 0.0, 1.0))
    if axis @ toward_body < 0:
        axis = -axis
    if from_end is not None:   # the lower edge from_end above the wrist / ankle: the limb's far end along the axis
        far = ((pos[limb & (np.linalg.norm(pos - c, axis=-1) < 25.0)] - c) @ axis).min()
        shift = far + from_end + height / 2
    c = c + axis * shift
    # the limb's centre at that point: the mean of a thin ring of skin round it
    along_all = (pos - c) @ axis
    ring = limb & (np.abs(along_all) < 0.4) & (np.linalg.norm(pos - c, axis=-1) < 8.0)
    centre = pos[ring].mean(0)
    centre = centre - axis * ((centre - c) @ axis)
    if face:
        want = np.array(FACES.get(face, (0, 0, 0)), np.float64)
        if face in ('palm', 'back_of_hand'):
            want = palm_normal(m.sex, side) * (1 if face == 'palm' else -1)
        elif face == 'inner':
            want = np.array((-side, 0.0, 0.0))
        elif face == 'outer':
            want = np.array((side, 0.0, 0.0))
        want = want - axis * (want @ axis)
        rp = pos[ring] - centre
        k = np.argmax((rp / np.linalg.norm(rp, axis=-1, keepdims=True)) @ (want / np.linalg.norm(want)))
        c = pos[ring][k]
    e1 = c - centre
    e1 = e1 - axis * (e1 @ axis)
    r0 = np.linalg.norm(e1)
    e1 /= r0
    e2 = np.cross(axis, e1)   # round the limb; with axis = image-up and e1 = outward this is image-right
    q = pos - centre
    along = q @ axis - (c - centre) @ axis
    rad = q - np.outer(q.reshape(-1, 3) @ axis, axis).reshape(q.shape)
    theta = np.arctan2(rad @ e2, rad @ e1)
    arc = theta * np.linalg.norm(rad, axis=-1)
    if rotate:
        cr, sr = np.cos(rotate), np.sin(rotate)
        arc, along = arc * cr - along * sr, arc * sr + along * cr
    zone = limb & (np.abs(along) < height * 0.75) & (np.abs(arc) < width * 0.75)
    # sample the design at about the texel density it lands on (more is moire, as the flash prefilter found)
    tpu = np.sqrt(zone.sum() / (width * 1.5 * height * 1.5))
    dw, dh = max(int(width * tpu * 1.5), 8), max(int(height * tpu * 1.5), 8)
    d = premultiplied_resize(design.transpose(Image.FLIP_LEFT_RIGHT) if flip else design, dw, dh)
    u = (arc[zone] / width + 0.5) * dw - 0.5
    vv = (0.5 - along[zone] / height) * dh - 0.5
    rgb = np.ones(m.covered.shape + (3,)) * mm.SKIN
    alpha = np.zeros(m.covered.shape)
    a = ndimage.map_coordinates(d[..., 3], [vv, u], order=1, mode='constant', cval=0.0)
    pm = [ndimage.map_coordinates(d[..., k] * d[..., 3], [vv, u], order=1, mode='constant', cval=0.0) for k in range(3)]
    alpha[zone] = a
    rgb[zone] = np.clip(np.stack(pm, -1) / np.maximum(a, 1e-4)[:, None], 0, 1)
    print(f'  wrapped on the {"left" if side < 0 else "right"} {place}, {face or "as anchored"}: limb radius '
          f'{r0 * CM:.1f} cm, {tpu / CM:.1f} texels per cm')
    return rgb, alpha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=pathlib.Path)
    ap.add_argument('png', type=pathlib.Path)
    ap.add_argument('--id', required=True)
    ap.add_argument('--place', required=True)
    ap.add_argument('--side', choices=('left', 'right', 'middle'), default='middle')
    ap.add_argument('--face', default='')
    ap.add_argument('--height-cm', type=float, required=True)
    ap.add_argument('--width-cm', type=float, default=0.0)
    ap.add_argument('--rotate', type=float, default=0.0, help='degrees, clockwise as seen on the skin')
    ap.add_argument('--shift-cm', type=float, default=0.0)
    ap.add_argument('--from-wrist-cm', '--from-ankle-cm', dest='from_end', type=float, default=None)
    ap.add_argument('--size', type=int, default=4096, help='texture size of a NEW template (detailed pieces: 4096)')
    ap.add_argument('--flip', action='store_true', help='mirror the design (for the other side of a pair)')
    a = ap.parse_args()
    row = next((r for r in mm.MARKS if r[0] == a.id), None)
    sex = row[1] if row else ('female' if a.id.split('_')[-1].startswith('F') else 'male')
    size = row[4] if row else a.size
    m = UVMap(mm.DATA, sex, size)
    design = Image.open(a.png).convert('RGBA')
    box = design.getbbox()
    if box:
        design = design.crop(box)   # the size given is the design's, not its canvas's
    height = a.height_cm / CM
    width = a.width_cm / CM if a.width_cm else height * design.width / design.height
    side = {'left': -1, 'right': 1, 'middle': 0}[a.side]
    if a.place in LIMBS:
        if not side:
            sys.exit('a limb piece needs --side left or right')
        rgb, alpha = wrap(m, design, a.place, side, a.face, height, width, np.radians(a.rotate), a.shift_cm / CM, a.flip,
                          None if a.from_end is None else a.from_end / CM)
    else:
        c, n, up = decals.anchor(m, a.place, side)
        design.info['prefilter'] = True
        rgb, alpha = flash.project_rgba_at(m, design.transpose(Image.FLIP_LEFT_RIGHT) if a.flip else design, c, n,
                                           width=width, rotate=np.radians(a.rotate), alpha=1.0)
    artist_art.save(a.out, a.id, m, rgb, alpha, row[2] if row else '')
    artist_art.render(a.out, [a.id.rsplit('_', 1)[0]])


if __name__ == '__main__':
    main()
