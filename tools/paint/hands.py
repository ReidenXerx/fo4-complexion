"""The hands (C-15): Complexion's own nails, painted on the hands mesh (LooksMenu overlay slot 4, as the packs'
nails are: LMNSOverlays.esp f_nails_1, read 2026-10-03).

FemaleHands.nif / MaleHands.nif (shapes BaseFemaleHands3rd:0, BaseMaleHands3rd:0) have their own UV layout -- the
two sexes' layouts differ -- so the nails are found on the mesh, not in the texture: the back of each finger's last
bone (LArm_Finger13 ... RArm_Finger53), toward its tip. Checked against the female hands texture, where the nails
are drawn pale (check_nails below).
"""
import pathlib

import numpy as np

from body import ASSETS, read_shape

HANDS = {'female': ('FemaleHands', 'BaseFemaleHands3rd:0'), 'male': ('MaleHands', 'BaseMaleHands3rd:0')}
NORMAL = {'female': 'actors/character/basehumanfemale/basefemalehands_n.dds',
          'male': 'actors/character/basehumanmale/basemalehands_n.dds'}


class HandMap:
    """Per texel of the hands' UV map: covered, position, normal and the bone it belongs to (UVMap's layout)."""

    def __init__(self, data, sex, size=1024):
        name, shape = HANDS[sex]
        pos, uv, tris, bones = read_shape(pathlib.Path(data) / ASSETS / f'{name}.nif', shape)
        self.size, self.sex = size, sex
        self.vertices, self.triangles = pos, tris
        self.bone_names = sorted(set(bones))
        vb = np.array([self.bone_names.index(b) for b in bones], dtype=np.int16)
        self.vertex_bone = vb
        fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
        vn = np.zeros_like(pos)
        for k in range(3):
            np.add.at(vn, tris[:, k], fn)
        vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
        self.vertex_normal = vn
        self.covered = np.zeros((size, size), bool)
        self.position = np.zeros((size, size, 3))
        self.normal = np.zeros((size, size, 3))
        self.bone = np.full((size, size), -1, np.int16)
        px = uv * size - 0.5
        for t in tris:
            a, b_, c_ = px[t[0]], px[t[1]], px[t[2]]
            x0, x1 = int(max(0, np.floor(min(a[0], b_[0], c_[0])))), int(min(size - 1, np.ceil(max(a[0], b_[0], c_[0]))))
            y0, y1 = int(max(0, np.floor(min(a[1], b_[1], c_[1])))), int(min(size - 1, np.ceil(max(a[1], b_[1], c_[1]))))
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            d = (b_[1] - c_[1]) * (a[0] - c_[0]) + (c_[0] - b_[0]) * (a[1] - c_[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((b_[1] - c_[1]) * (xs - c_[0]) + (c_[0] - b_[0]) * (ys - c_[1])) / d
            l2 = ((c_[1] - a[1]) * (xs - c_[0]) + (a[0] - c_[0]) * (ys - c_[1])) / d
            l3 = 1 - l1 - l2
            inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
            if not inside.any():
                continue
            yy, xx = ys[inside], xs[inside]
            w = np.stack([l1[inside], l2[inside], l3[inside]], axis=1)
            self.covered[yy, xx] = True
            self.position[yy, xx] = w @ pos[t]
            n = w @ vn[t]
            self.normal[yy, xx] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
            self.bone[yy, xx] = vb[t[np.argmax(w, axis=1)]]

    def bone_mask(self, name):
        if name not in self.bone_names:
            return np.zeros(self.covered.shape, bool)
        return self.covered & (self.bone == self.bone_names.index(name))


def _bone_vertices(m, name):
    return m.vertices[m.vertex_bone == m.bone_names.index(name)]


def finger_frame(m, side, f):
    """A frame on finger f (1 thumb .. 5 little) of hand side 'L'/'R': axis along the last bone toward the tip;
    b, the palm plane's normal (least spread of the Hand bone's vertices) flattened against the axis and turned
    toward the thumb's tip; c = axis x b. Built from the skeleton's own bones, so it means the same on both sexes'
    meshes. Returns axis, b, c, and the last bone's extent along the axis (tip, base)."""
    H = _bone_vertices(m, f'{side}Arm_Hand')
    hc = H.mean(axis=0)
    _, _, vt = np.linalg.svd(H - hc, full_matrices=False)
    palm = vt[2]
    if palm @ (_bone_vertices(m, f'{side}Arm_Finger13').mean(axis=0) - hc) < 0:
        palm = -palm
    D = _bone_vertices(m, f'{side}Arm_Finger{f}3')
    M = _bone_vertices(m, f'{side}Arm_Finger{f}2')
    axis = D.mean(axis=0) - M.mean(axis=0)
    axis /= np.linalg.norm(axis)
    b = palm - axis * (palm @ axis)
    b /= np.linalg.norm(b)
    t = D @ axis
    return axis, b, np.cross(axis, b), t.max(), t.min()


# Measured 2026-10-03 on the female hands, from the texels its texture draws as nails (pale, unsaturated, on the
# last finger bones only, from 0.6 of the bone's length to its tip): each nail's mean normal in finger_frame's
# (axis, b, c). nailprobe2 in the session scratchpad; check_nails() re-measures the agreement.
NAIL_NORMAL = {
    'L1': (0.36, 0.11, -0.93), 'L2': (0.48, 0.03, 0.88), 'L3': (0.46, 0.82, 0.34), 'L4': (0.44, 0.85, 0.27),
    'L5': (0.48, 0.87, 0.10),
    'R1': (0.38, 0.10, 0.92), 'R2': (0.54, 0.03, -0.84), 'R3': (0.47, 0.82, -0.33), 'R4': (0.48, 0.83, -0.27),
    'R5': (0.50, 0.86, -0.08),
}


def nail_mask(m, start=0.6, facing=0.7):
    """0..1 per texel: the nail plates. For each finger, the last bone's texels from `start` of its length to the
    tip, whose normal is within the nail's measured direction (NAIL_NORMAL); soft edges."""
    out = np.zeros(m.covered.shape)
    P, N = m.position, m.normal
    for side in ('L', 'R'):
        for f in range(1, 6):
            if f'{side}Arm_Finger{f}3' not in m.bone_names:
                continue
            axis, b, c, tip, base = finger_frame(m, side, f)
            la, lb, lc = NAIL_NORMAL[f'{side}{f}']
            want = la * axis + lb * b + lc * c
            want /= np.linalg.norm(want)
            mask = m.bone_mask(f'{side}Arm_Finger{f}3')
            frac = (P[mask] @ axis - base) / (tip - base)
            along = np.clip((frac - start) / 0.06, 0, 1)
            face = np.clip((N[mask] @ want - facing) / 0.12, 0, 1)
            out[mask] = np.maximum(out[mask], along * face)
    return out


POLISH = {'red': (0.62, 0.04, 0.08), 'black': (0.07, 0.06, 0.08), 'purple': (0.36, 0.08, 0.42),
          'pink': (0.90, 0.42, 0.58)}


def nails(m, rng, style='red', chipped=False):
    """Nails: polish in a colour (chipped at the tips when worn), or dirty -- black under the tips, grime ground into
    the fingertips."""
    from marks import blank, fbm, over
    rgb, alpha = blank(m)
    mask = nail_mask(m)
    seed = int(rng.integers(1 << 30))
    P = m.position
    if style == 'dirty':
        tips = np.zeros(m.covered.shape)
        under = np.zeros(m.covered.shape)
        for side in ('L', 'R'):
            for f in range(1, 6):
                axis, b, c, tip, base = finger_frame(m, side, f)
                bm = m.bone_mask(f'{side}Arm_Finger{f}3')
                frac = (P[bm] @ axis - base) / (tip - base)
                tips[bm] = np.clip((frac - 0.3) / 0.4, 0, 1)
                under[bm] = np.clip((frac - 0.9) / 0.06, 0, 1)
        grime = np.clip((fbm(P, 2.5, seed, 3) - 0.35) * 2.5, 0, 1)
        over(rgb, alpha, (0.30, 0.22, 0.15), np.clip(tips * grime * 0.55 * m.covered, 0, 0.55))
        # the plate itself stained: the female hands draw their nails near white, which read as clean (review)
        over(rgb, alpha, (0.50, 0.42, 0.33), np.clip(mask * (0.45 + 0.3 * grime), 0, 0.7))
        over(rgb, alpha, (0.10, 0.07, 0.05), np.clip(under * np.maximum(mask, 0.6) * 0.85, 0, 0.85))
        return rgb, alpha
    a = mask * 0.92
    if chipped:
        chip = np.clip((fbm(P, 4.0, seed, 3) - 0.45) * 6, 0, 1)
        a = a * chip
    over(rgb, alpha, POLISH[style], np.clip(a, 0, 0.92))
    return rgb, alpha
