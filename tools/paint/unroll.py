"""A mark on a limb, unrolled flat: every texel near the mark placed by where it is ON THE BODY (along the limb, and
around it), so a design split across a UV seam shows whether its halves meet. The front/back renders see the
underside of an arm edge-on, which is where the arm islands are cut.

    python tools/paint/unroll.py <multiplier png> <sex> <out jpg> [radius]

The PNG is a finished multiplier (build/marks/<id>_d.png, or an artist preview's marks/ folder).
"""
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_marks as mm  # noqa: E402
from body import UVMap  # noqa: E402

PX = 40  # output pixels per game unit


def main():
    png, sex, out = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
    radius = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0
    tex = np.asarray(Image.open(png).convert('RGB'), dtype=np.float64) / 255.0
    m = UVMap(mm.DATA, sex, tex.shape[0])
    ink = m.covered & (np.abs(tex - mm.NEUTRAL).max(-1) > 0.02)
    if not ink.any():
        sys.exit('no ink on the body')
    c = m.position[ink].mean(axis=0)
    near = m.covered & (np.linalg.norm(m.position - c, axis=-1) < radius)
    P = m.position[near]
    # the limb's axis: the main direction of the skin around the mark
    w, v = np.linalg.eigh(np.cov((P - P.mean(0)).T))
    axis = v[:, -1]
    # point the axis up the limb, towards the body (an arm: towards x = 0; a leg: up), as artist_flat wraps a design
    toward = np.array((-np.sign(c[0]), 0.0, 0.0)) if abs(axis[0]) > abs(axis[2]) else np.array((0.0, 0.0, 1.0))
    if axis @ toward < 0:
        axis = -axis
    q = P - P.mean(0)
    along = q @ axis
    rad = q - np.outer(along, axis)
    centre = rad.mean(0)   # the limb's centre line passes near the mean of a ring of skin
    rad = rad - centre
    e1 = v[:, 0] - axis * (v[:, 0] @ axis)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    ang = np.arctan2(rad @ e2, rad @ e1)
    r = np.median(np.linalg.norm(rad, axis=-1))
    # roll the cut to where there is no ink, so the design is not split by the unrolling itself
    ink_ang = ang[np.abs(tex[near] - mm.NEUTRAL).max(-1) > 0.02]
    hist, edges = np.histogram(ink_ang, 72, (-np.pi, np.pi))
    cut = edges[np.argmin(np.convolve(np.r_[hist, hist[:3]], np.ones(4), 'valid')[:72]) + 2]
    ang = (ang - cut) % (2 * np.pi)
    x = (ang * r * PX).astype(int)
    y = ((along.max() - along) * PX).astype(int)   # image-up = up the limb; x runs round it as seen from outside
    W, H = x.max() + 1, y.max() + 1
    acc = np.zeros((H, W, 3))
    cnt = np.zeros((H, W))
    col = np.clip(mm.SKIN * tex[near] / mm.NEUTRAL, 0, 1)
    np.add.at(acc, (y, x), col)
    np.add.at(cnt, (y, x), 1)
    img = np.where(cnt[..., None] > 0, acc / np.maximum(cnt, 1)[..., None], 0.15)
    # fill the holes between texel samples (texels are sparser than output pixels where the UV is stretched)
    from scipy import ndimage
    holes = cnt == 0
    idx = ndimage.distance_transform_edt(holes, return_distances=False, return_indices=True)
    d = ndimage.distance_transform_edt(holes)
    img = np.where((d <= 3)[..., None], img[idx[0], idx[1]], img)
    Image.fromarray((img * 255).astype(np.uint8)).save(out, quality=92)
    print(out, f'{W}x{H}px, limb radius {r:.1f} units')


if __name__ == '__main__':
    main()
