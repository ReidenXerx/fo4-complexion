"""One smooth 3D warp of the female body + hands onto the male body + hands (alasdairn, v21 11-14: "still misaligned").

The men's synthetic skin lines used to be carried through two separate approximate matches -- one for the body
(landmark heights, torso width, nearest texel), one for the hands (each side's bounding box) -- so lines that meet on a
woman did not meet on a man: the forearm lines missed the wrist bands, the shin lines stopped short of the ankle bands.
Here both meshes of each sex are put in one frame (the hands' raw vertices sit elsewhere: their skin transforms bring
them onto the body's bones), and the woman's surface is pulled onto the man's by a non-rigid ICP whose displacements are
smoothed over her mesh, coarse to fine. Lines carried through it as 3D points keep meeting where they met.

Both sexes share the game's one skeleton, so no bone retargeting: the bodies already stand in the same place.
"""
import pathlib
import numpy as np

import make_marks as mm
from body import ASSETS, BODIES, REGIONS, read_shape, region_of
from hands import HANDS

HAND = REGIONS.index('hand')
SEAM_JOIN = 0.3      # world units: body and hands vertices this close are one seam
_cache = {}


def _load(table, sex):
    name, shape = table[sex]
    return read_shape(pathlib.Path(mm.DATA) / ASSETS / f'{name}.nif', shape, want_skin=True)


def _apply(tf, v, inverse=False):
    R, t, s = tf
    if not inverse:
        return (v @ R.T) * s + t
    return ((v - t) / s) @ R


def hands_to_body(sex):
    """f(points Nx3 in the hands mesh's own frame) -> the body mesh's frame: hands skin space -> each side's hand bone ->
    the body's skin space (measured 11-14: male hands sit ~40 units off the body raw, land on its wrists after this)."""
    key = ('h2b', sex)
    if key not in _cache:
        *_, bt = _load(BODIES, sex)
        *_, ht = _load(HANDS, sex)
        tf = {}
        for side, bone in ((1, 'RArm_Hand'), (-1, 'LArm_Hand')):
            if bone not in bt:   # the body has no hand bone: its last forearm bone
                bone = bone.replace('Hand', 'ForeArm3_skin')
            tf[side] = (ht[bone], bt[bone])

        def f(v):
            v = np.asarray(v, np.float64)
            out = np.empty_like(v)
            for side, (h, b) in tf.items():
                sel = (v[..., 0] * side) > 0
                out[sel] = _apply(b, _apply(h, v[sel]), inverse=True)
            return out
        _cache[key] = f
    return _cache[key]


def _mesh(sex):
    """(vertices Nx3, normals Nx3, region per vertex, adjacency (sparse, row-normalised), mesh id per vertex: 0 body 1 hands)
    for the body + hands of one sex, all in the body's frame."""
    key = ('mesh', sex)
    if key not in _cache:
        import scipy.sparse as sp
        parts = []
        for k, (table, conv) in enumerate(((BODIES, None), (HANDS, hands_to_body(sex)))):
            pos, _uv, tris, bones, _tf = _load(table, sex)
            if conv is not None:
                pos = conv(pos)
            reg = np.array([HAND if k else REGIONS.index(region_of(b)) for b in bones], np.int8)
            fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
            vn = np.zeros_like(pos)
            for j in range(3):
                np.add.at(vn, tris[:, j], fn)
            vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
            parts.append((pos, vn, reg, tris, k))
        off, V, N, R, T, I = 0, [], [], [], [], []
        for pos, vn, reg, tris, k in parts:
            V.append(pos); N.append(vn); R.append(reg); T.append(tris + off); I.append(np.full(len(pos), k, np.int8))
            off += len(pos)
        V, N, R, T, I = (np.concatenate(x) for x in (V, N, R, T, I))
        e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
        # the wrist seam: body and hands vertices that coincide are neighbours too, so the two meshes move as one
        from scipy.spatial import cKDTree
        b, h = np.flatnonzero(I == 0), np.flatnonzero(I == 1)
        dist, j = cKDTree(V[h]).query(V[b], distance_upper_bound=SEAM_JOIN)
        ok = np.isfinite(dist)
        seam = np.stack((b[ok], h[j[ok]]), -1)
        e = np.concatenate([e, seam])
        e = np.concatenate([e, e[:, ::-1]])
        A = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(V), len(V))).tocsr()
        A.data[:] = 1.0
        A = A + sp.identity(len(V), format='csr')
        A = sp.diags(1.0 / np.asarray(A.sum(1)).ravel()) @ A
        _cache[key] = (V, N, R, A, I)
        _cache[('seam', sex)] = seam
    return _cache[key]


# coarse to fine: (smoothing passes over her mesh, ICP rounds)
ICP_SCHEDULE = ((200, 4), (80, 4), (30, 6), (10, 8), (3, 8), (1, 6))
ICP_AGREE = (0.3, -0.3)   # a target's normal must face within ~70 degrees of hers; failing any, within ~107 (her breasts'
                          # underside faces down where his chest faces forward: they never moved, 11-14)


def female_to_male():
    """Per female vertex (body + hands, _mesh order): her displacement onto the man (Nx3), fitted once."""
    if 'disp' not in _cache:
        from scipy.spatial import cKDTree
        FV, FN, FR, A, FI = _mesh('female')
        MV, MN, MR, _, MI = _mesh('male')
        trees = {}
        for r in np.unique(FR):
            idx = np.flatnonzero(MR == r)
            if len(idx):
                trees[r] = (idx, cKDTree(MV[idx]))
        seam = _cache[('seam', 'female')]
        X = FV.copy()
        for passes, rounds in ICP_SCHEDULE:
            for _ in range(rounds):
                d = np.zeros_like(X)
                w = np.zeros(len(X))
                for r, (idx, tree) in trees.items():
                    sel = np.flatnonzero(FR == r)
                    dist, nb = tree.query(X[sel], k=8)
                    agree = np.einsum('nkc,nc->nk', MN[idx[nb]], FN[sel])
                    score = np.where(agree > ICP_AGREE[0], dist, np.inf)
                    loose = ~np.isfinite(score).any(1)
                    score[loose] = np.where(agree[loose] > ICP_AGREE[1], dist[loose], np.inf)
                    pick = np.argmin(score, axis=1)
                    ok = np.isfinite(score[np.arange(len(sel)), pick])
                    tgt = MV[idx[nb[np.arange(len(sel)), pick]]]
                    # to the target's tangent plane, not its vertex: a sparse male mesh would pull her into facets
                    n = MN[idx[nb[np.arange(len(sel)), pick]]]
                    step = np.einsum('nc,nc->n', tgt - X[sel], n)[:, None] * n
                    d[sel[ok]] = step[ok]
                    w[sel[ok]] = 1.0
                for _ in range(passes):   # smoothed over her mesh; vertices with no target take their neighbours'
                    d = A @ d
                    w = A @ w
                d = d / np.maximum(w, 1e-6)[:, None]
                d[seam[:, 0]] = d[seam[:, 1]] = (d[seam[:, 0]] + d[seam[:, 1]]) / 2   # the wrist moves as one
                X = X + d
        _cache['disp'] = X - FV
    return _cache['disp']


def carry(points, mesh, sex):
    """3D points on a woman's body (mesh 0) or hands (mesh 1), in her body frame, carried onto the man (sex 'male') or
    kept (sex 'female'), then laid on that sex's surface (nearest vertex's tangent plane)."""
    points = np.asarray(points, np.float64)
    if sex == 'female' or not len(points):
        return points
    from scipy.spatial import cKDTree
    FV, _FN, _FR, _A, FI = _mesh('female')
    D = female_to_male()
    sel = np.flatnonzero(FI == mesh)
    key = ('ftree', mesh)
    if key not in _cache:
        _cache[key] = cKDTree(FV[sel])
    dist, nb = _cache[key].query(points, k=6)
    w = 1.0 / np.maximum(dist, 1e-4)
    P = points + (w[..., None] * D[sel[nb]]).sum(1) / w.sum(1)[:, None]
    MV, MN, _MR, _, MI = _mesh('male')
    msel = np.flatnonzero(MI == mesh)
    key = ('mtree', mesh)
    if key not in _cache:
        _cache[key] = cKDTree(MV[msel])
    _d, j = _cache[key].query(P)
    v, n = MV[msel[j]], MN[msel[j]]
    return P - np.einsum('nc,nc->n', P - v, n)[:, None] * n
