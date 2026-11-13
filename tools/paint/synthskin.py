"""Synthetic skin: a synth's seam lines over a person's own skin (alasdairn, 2026-11-13).

    The lines are his: the seams he drew on his own synth skin atlas (tools/paint/art/contrib/alasdairn_synth_atlas.png,
    CREDITS.md) -- pieces of a whole synthetic body -- projected onto our meshes piece by piece, each anchored on
    landmarks the two share (nipples, nape, crotch to knee, along the arm; nose and chin for the head). The hands get a
    synth's joint lines from their own finger bones (his hand pieces are drawn palm up and carry no clean seams).

    Lines only, crisp and dark (his verdict on test v2, in game: "Lost definition in the lines, hands have nothing
    notable, applies a layer of shading over everything else. Remove the shading, darken and sharpen the lines"). His
    atlas is about 11 pixels to a game unit; sampled straight, its strokes blurred over a 4096 body, and a pixel
    centreline drawn as it was made stair-steps and crack spurs (test v3: "I don't want to see each and every pixel",
    "these lines look nothing like what I gave you"). So his seams are traced as vector polylines -- found as thin
    dark valleys, followed as a graph, straightened to the runs and corners he drew, then checked by hand piece by
    piece against his atlas (art/contrib/alasdairn_synth_seams.json: cracks and creases dropped, faint seams added
    along his own groove) -- and every texel draws an anti-aliased line by its exact distance to them, in game units.
    Everything else multiplies by exactly 1: the person's own skin, its colour and its light, are untouched.

    Selectable only (lore "breaks"): body and hands in LooksMenu's overlay list (make_marks rows SynthShell,
    SynthShellHands), the face as a face tint (make_faces.py). Ace Male Race wears the vanilla male body, and has its
    own head (face.py).

What he struck out stays out: no line in the band under the women's breasts (his atlas's breasts sit lower than ours,
and drew a ghost outline there), no specks, scratches or stubs (the "random scar" on a thigh), and nothing read from
above the leg pieces at the hips (a straight dash).
"""
import pathlib

import numpy as np

from body import REGIONS
from marks import landmarks

HERE = pathlib.Path(__file__).resolve().parent
ATLAS = HERE / 'art' / 'contrib' / 'alasdairn_synth_atlas.png'

# ---- his atlas (1536 x 1024): where each piece sits, by the anchors it shares with our meshes (atlas pixels)
MALE_FRONT = dict(cx=400, nip=(300, 305))      # the torso fronts: the midline and a nipple
FEMALE_FRONT = dict(cx=1180, nip=(1110, 288))
MALE_BACK = dict(cx=935, top=165)              # the backs: the spine and the nape
FEMALE_BACK = dict(cx=1375, top=175)
LEG_FRONT = dict(cx=180, top=575, knee=897)    # his (male) leg pieces, for both sexes: crotch to the knee's V
LEG_BACK = dict(cx=327, top=575, knee=897)
ARM = dict(cx=57.0, shoulder=95.0, length=520.0)   # his long arm piece, shoulder to wrist
HEAD_SIDE = dict(nose=(382, 95), chin=(370, 140))  # the head, seen from its right side

# ---- which of his atlas's dark marks are seams
DETAIL_SIGMA = 8.0     # atlas px: the local average a mark is measured against
RIDGE_SCALES = (0.8, 1.2)   # atlas px: his seams are a pixel or two wide
RIDGE_STRONG = 0.06    # valley strength of a clear seam ...
RIDGE_WEAK = 0.03    # ... and of a faint stretch running on from one
LINE_MIN_PX = 30       # atlas px: a stroke shorter than this is a speck, a scratch or a stub, not a seam
EDGE_PX = 4.0          # atlas px: no line this close to a piece's outline (the outline itself reads as a valley)

# ---- how a seam is drawn (game units)
LINE_W = 0.075         # half-width: 0.15 across, his strokes' width (1.5-2 atlas px at ~11 px a unit)
LINE_SOFT = 0.025      # its edge: about a texel at 2048, so crisp but not jagged
LINE_DEPTH = 0.8       # the skin multiplied by 1 - this on the line
FACE_LINE_W = 0.075    # on the face tint (1024 over a head)
HAND_LINE_W = 0.045
SPUR_PX = 12           # atlas px: twigs this short off a seam (thinning's leftovers, his texture's cracks) are pruned
SIMPLIFY_PX = 1.0      # atlas px: a traced run may stray this far from the straight line it is drawn as
CORRIDOR_PX = 4.0      # atlas px: a hand-added seam keeps this close to the line through its waypoints
ROUTE_STRAIGHT = 12.0  # cost per atlas px off that line (a clear groove costs ~14 a step, bare skin ~30-100)
SEAMS = HERE / 'art' / 'contrib' / 'alasdairn_synth_seams.json'   # the hand check of the traced seams

UNDERBUST_TOP, UNDERBUST_DEPTH = 1.0, 16.0  # game units above / below the nipples: the band he struck out
UNDERBUST_FADE = 2.5

_cache = {}


# ---------------------------------------------------------------- limbs and heads


class _Limb:
    """A limb as an axis, a centreline along it and an angle round it, from points on its surface (texels: the male
    body has few vertices, and a centreline from them leans towards wherever the mesh is dense)."""

    def __init__(self, P, axis_hint, ref):
        P = P[::max(1, len(P) // 40000)]
        c = P.mean(0)
        a = np.linalg.svd(P - c, full_matrices=False)[2][0]
        if a @ axis_hint < 0:
            a = -a
        self.c, self.a = c, a
        t = (P - c) @ a
        self.tmin, self.tmax = float(t.min()), float(t.max())
        edges = np.arange(self.tmin, self.tmax + 1.0, 1.0)
        which = np.digitize(t, edges) - 1
        cen_t, cen = [], []
        for k in range(len(edges) - 1):
            sel = which == k
            if sel.sum() >= 3:
                cen_t.append((edges[k] + edges[k + 1]) / 2)
                cen.append(P[sel].mean(axis=0))
        self.cen_t, self.cen = np.array(cen_t), np.array(cen)
        e1 = ref - (ref @ a) * a
        self.e1 = e1 / np.linalg.norm(e1)
        self.e2 = np.cross(a, self.e1)

    def coords(self, X):
        """t along the axis, r and theta round the centreline (theta 0 towards ref)."""
        t = (X - self.c) @ self.a
        C = np.stack([np.interp(t, self.cen_t, self.cen[:, k]) for k in range(3)], axis=1)
        d = X - C
        d -= np.outer(d @ self.a, self.a)
        return t, np.linalg.norm(d, axis=1), np.arctan2(d @ self.e2, d @ self.e1)


def face_landmarks(m):
    """Measured on a head mesh (face.HeadMap; local units, face towards +y, z up): the nose tip and the chin."""
    V = m.vertices
    nose = V[np.argmax(V[:, 1])]
    front = V[(np.abs(V[:, 0]) < 0.4) & (V[:, 1] > nose[1] - 3.5)]
    return {'nose': nose, 'chin': front[np.argmin(front[:, 2])]}


# ---------------------------------------------------------------- his seams, as centrelines


def _thin(mask):
    """Zhang-Suen thinning: a stroke mask to its one-pixel centreline."""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            P = [img[1:-1, 1:-1], img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:], img[2:, 2:], img[2:, 1:-1],
                 img[2:, :-2], img[1:-1, :-2], img[:-2, :-2]]
            p1, p2, p3, p4, p5, p6, p7, p8, p9 = P
            nb = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            trans = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(np.uint8) for k in range(8))
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            rm = (p1 == 1) & (nb >= 2) & (nb <= 6) & (trans == 1) & c
            if rm.any():
                img[1:-1, 1:-1][rm] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)


def _strokes():
    """(his seam strokes as a one-pixel skeleton, distance inside a piece's outline) -- atlas pixels."""
    if 'skel' not in _cache:
        from PIL import Image
        from scipy import ndimage
        img = np.asarray(Image.open(ATLAS).convert('RGB'), dtype=np.float32) / 255.0
        lum = img @ np.array((0.3, 0.59, 0.11), np.float32)
        inside = ndimage.distance_transform_edt(ndimage.binary_erosion(lum > 0.10, iterations=2)).astype(np.float32)
        valid = inside > 0
        w = valid.astype(np.float32)
        avg = ndimage.gaussian_filter(lum * w, DETAIL_SIGMA) / np.maximum(ndimage.gaussian_filter(w, DETAIL_SIGMA), 1e-3)
        det = np.where(valid, lum / np.maximum(avg, 1e-3), 1.0)
        # a seam is a thin dark valley: the Hessian's larger eigenvalue large, the smaller near 0 (a crack's pit or
        # a speck curves both ways); broad shading (his muscles, the creases under the pecs) is too wide to count
        ridge = np.zeros_like(det)
        for s in RIDGE_SCALES:
            hxx = ndimage.gaussian_filter(det, s, order=(0, 2))
            hyy = ndimage.gaussian_filter(det, s, order=(2, 0))
            hxy = ndimage.gaussian_filter(det, s, order=(1, 1))
            tr, dt = hxx + hyy, hxx * hyy - hxy * hxy
            disc = np.sqrt(np.maximum(tr * tr / 4 - dt, 0))
            l1, l2 = tr / 2 + disc, tr / 2 - disc
            ridge = np.maximum(ridge, np.where(l1 > 0, l1 - 2 * np.maximum(l2, 0), 0) * s * s)
        ridge[inside <= EDGE_PX] = 0
        # hysteresis: the faint stretch of a seam counts when it runs on from a clear one
        lab, n = ndimage.label(ridge > RIDGE_WEAK, structure=np.ones((3, 3)))
        keep = np.zeros(n + 1, bool)
        strong = ndimage.maximum(ridge, lab, np.arange(n + 1)) > RIDGE_STRONG
        for i, sl in enumerate(ndimage.find_objects(lab), 1):
            if sl is not None and strong[i] and max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) >= LINE_MIN_PX:
                keep[i] = True
        _cache['skel'] = _thin(keep[lab])
        _cache['ridge'] = ridge
        _cache['inside'] = inside
    return _cache['skel'], _cache['inside']


_NB8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
# a walk takes a side neighbour before a corner one: at a stair step both are on the line, and the corner jump
# would leave the side pixel behind as a stray
_NB8_STRAIGHT_FIRST = ((-1, 0), (0, -1), (0, 1), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1))


def _graph(skel):
    """A skeleton as a graph: (edges, node of each pixel). Nodes are clusters of pixels that are not plain
    line pixels (ends; junctions, with the pixels round them); each edge is (node a, node b, [(x, y), ...]) from
    a's centre to b's. A closed loop with no node becomes one edge from a pixel back to itself."""
    from scipy import ndimage
    # a pixel's crossing number (runs of neighbours round it), not its neighbour count: thinning leaves a stair
    # step's corner with three neighbours, and counting those made a node of every step -- a line cut into
    # pieces short enough for the twig pruning to eat it whole
    p = np.pad(skel.astype(np.uint8), 1)
    ring = [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:], p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]
    cn = sum(((ring[k] == 0) & (ring[(k + 1) % 8] == 1)).astype(np.uint8) for k in range(8))
    # a junction is a little knot of such pixels; grown by one and taken as ONE node, the runs between its pixels
    # (which drew as ticks) vanish, and every line into it is carried on to its centre, so corners meet cleanly
    junction = skel & (cn >= 3)
    node_px = (ndimage.binary_dilation(junction, structure=np.ones((3, 3))) & skel) | (skel & (cn <= 1))
    nlab, nn = ndimage.label(node_px, structure=np.ones((3, 3)))
    centre = np.zeros((nn + 1, 2))
    if nn:
        cy, cx = np.asarray(ndimage.center_of_mass(node_px, nlab, np.arange(1, nn + 1))).T
        centre[1:, 0], centre[1:, 1] = cx, cy
    h, w = skel.shape
    seen = np.zeros_like(skel)
    edges = []

    def walk(y, x, start, prev):
        """From line pixel (y, x), away from prev, to the next node (its label) or a dead end (0)."""
        path = [(x, y)]
        while True:
            seen[y, x] = True
            to_node = to_line = None
            for dy, dx in _NB8_STRAIGHT_FIRST:
                yy, xx = y + dy, x + dx
                if (yy, xx) == prev or not (0 <= yy < h and 0 <= xx < w) or not skel[yy, xx]:
                    continue
                if nlab[yy, xx]:
                    if not (nlab[yy, xx] == start and len(path) < 3):   # not straight back into where it began
                        to_node = (yy, xx)
                elif not seen[yy, xx] and to_line is None:
                    to_line = (yy, xx)
            if to_node is not None:
                path.append((to_node[1], to_node[0]))
                return path, int(nlab[to_node])
            if to_line is None:
                return path, 0
            prev, (y, x) = (y, x), to_line
            path.append((x, y))
    for y, x in zip(*np.nonzero(node_px)):
        for dy, dx in _NB8:
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and skel[yy, xx] and not nlab[yy, xx] and not seen[yy, xx]:
                a = int(nlab[y, x])
                path, b = walk(yy, xx, a, (y, x))
                if b:
                    path[-1] = tuple(centre[b])
                edges.append((a, b, [tuple(centre[a])] + path))
    for y, x in zip(*np.nonzero(skel & ~node_px)):    # loops with no node on them
        if not seen[y, x]:
            path, _b = walk(y, x, 0, (-9, -9))
            edges.append((0, 0, path + [path[0]]))
    return edges


def _length(p):
    a = np.asarray(p, np.float64)
    return float(np.hypot(*np.diff(a, axis=0).T).sum()) if len(a) > 1 else 0.0


def _simplify(p, tol):
    """Douglas-Peucker: a pixel staircase to the straight runs and corners it stands for."""
    a = np.asarray(p, np.float64)
    if len(a) < 3:
        return a
    keep = np.zeros(len(a), bool)
    keep[[0, -1]] = True
    stack = [(0, len(a) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        d = a[j] - a[i]
        n = np.hypot(*d)
        seg = a[i + 1:j] - a[i]
        dist = np.abs(seg[:, 0] * d[1] - seg[:, 1] * d[0]) / n if n > 0 else np.hypot(*seg.T)
        k = int(np.argmax(dist))
        if dist[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return a[keep]


def _route(a, b, ridge):
    """The pixel path from a to b (atlas px) that keeps to his groove: least cost through the valley strength,
    within CORRIDOR_PX of the straight line between them."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = CORRIDOR_PX + 2
    x0, y0 = int(np.floor(min(a[0], b[0]) - m)), int(np.floor(min(a[1], b[1]) - m))
    x1, y1 = int(np.ceil(max(a[0], b[0]) + m)) + 1, int(np.ceil(max(a[1], b[1]) + m)) + 1
    x0, y0 = max(x0, 0), max(y0, 0)
    R = ridge[y0:y1, x0:x1]
    h, w = R.shape
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = b - a
    L = max(np.hypot(*d), 1e-6)
    t = np.clip(((xx - a[0]) * d[0] + (yy - a[1]) * d[1]) / L ** 2, 0, 1)
    off = np.hypot(xx - (a[0] + t * d[0]), yy - (a[1] + t * d[1]))
    # straight unless his groove pulls it: where his line is faint the texture's cracks would otherwise lead it astray
    cost = 1.0 / (np.maximum(R, 0) + 0.01) + ROUTE_STRAIGHT * off + np.where(off > CORRIDOR_PX, 1e4, 0)
    idx = np.arange(h * w).reshape(h, w)
    rows, cols, wts = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        ys, ye = 0, h - dy
        xs, xe = max(0, -dx), w - max(0, dx)
        u = idx[ys:ye, xs:xe]
        v = idx[ys + dy:ye + dy, xs + dx:xe + dx]
        c = (cost[ys:ye, xs:xe] + cost[ys + dy:ye + dy, xs + dx:xe + dx]) / 2 * np.hypot(dy, dx)
        rows.append(u.ravel()); cols.append(v.ravel()); wts.append(c.ravel())
    G = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(h * w, h * w)).tocsr()
    s = idx[int(round(a[1])) - y0, int(round(a[0])) - x0]
    e = idx[int(round(b[1])) - y0, int(round(b[0])) - x0]
    _dist, pred = dijkstra(G, directed=False, indices=s, return_predecessors=True)
    path = [e]
    while path[-1] != s and pred[path[-1]] >= 0:
        path.append(pred[path[-1]])
    return [(int(k % w) + x0, int(k // w) + y0) for k in reversed(path)]


def _layout():
    import json
    return json.loads(SEAMS.read_text(encoding='utf-8'))


def seam_paths():
    """His seams as polylines (atlas pixels): the strokes' centrelines traced into a graph, the twigs thinning
    leaves and the cracks of his texture that touch a seam pruned off, each run straightened to the straight
    lines and corners he drew; then the hand check (alasdairn_synth_seams.json): marks that are not seams
    dropped, faint seams the detector missed added, each routed along his own groove."""
    if 'paths' not in _cache:
        skel, _inside = _strokes()
        edges = _graph(skel)
        def degrees():
            deg = {0: 1}           # a dead-end walk (node 0) counts as an end
            for a, b, _p in edges:
                deg[a] = deg.get(a, 0) + 1
                deg[b] = deg.get(b, 0) + 1
            deg[0] = 1
            return deg
        best = {}                 # two runs between the same two nodes: a little eye in his stroke; keep the shorter
        for e in edges:
            k = (min(e[0], e[1]), max(e[0], e[1]))
            if k[0] == 0 or k[0] == k[1] or k not in best or _length(e[2]) < _length(best[k][2]):
                best[k if k[0] and k[0] != k[1] else (id(e),)] = e
        edges = list(best.values())
        for _ in range(3):        # twigs: a short edge from a junction to nothing, or a little loop back to it
            deg = degrees()
            edges = [(a, b, p) for a, b, p in edges
                     if not (a != b and min(deg[a], deg[b]) == 1 and max(deg[a], deg[b]) >= 3 and _length(p) < SPUR_PX)
                     and not (a == b and a != 0 and _length(p) < 2 * SPUR_PX)]
        deg = degrees()           # and a short stroke on its own: a speck or a scratch
        edges = [(a, b, p) for a, b, p in edges
                 if not (a != b and deg[a] == 1 and deg[b] == 1 and _length(p) < LINE_MIN_PX)]
        lay = _layout()

        def dropped(p):
            a = np.asarray(p, float)
            mid = a[len(a) // 2]
            return any(x0 <= mid[0] <= x1 and y0 <= mid[1] <= y1 for x0, y0, x1, y1 in lay['drop'])
        paths = [p for _a, _b, p in edges if _length(p) >= 2 and not dropped(p)]
        for way in lay['add']:
            run = []
            for a, b in zip(way[:-1], way[1:]):
                run += _route(a, b, _cache['ridge'])[1 if run else 0:]
            paths.append(run)
        paths += [np.asarray(way, float) for way in lay.get('straight', [])]   # his straight, faint ones, as drawn
        _cache['paths'] = [_simplify(p, SIMPLIFY_PX) for p in paths]
    return _cache['paths']


def _seam_tree():
    if 'tree' not in _cache:
        from scipy.spatial import cKDTree
        pts = []
        for p in seam_paths():
            for a, b in zip(p[:-1], p[1:]):
                n = max(2, int(np.ceil(np.hypot(*(b - a)) / 0.1)) + 1)
                pts.append(a + np.linspace(0, 1, n)[:, None] * (b - a))
        _cache['tree'] = cKDTree(np.concatenate(pts))
    return _cache['tree']


def _seam_distance(U, V):
    """Per point: distance (atlas px, exact to a tenth of a pixel) to his nearest seam; inf off the atlas (NaN U),
    outside his pieces, or farther than a line could reach."""
    _skel, inside = _strokes()
    d = np.full(len(U), np.inf)
    ok = np.isfinite(U)
    if ok.any():
        h, w = inside.shape
        u = np.clip(U[ok], 0, w - 1.001)
        v = np.clip(V[ok], 0, h - 1.001)
        a, _i = _seam_tree().query(np.stack([u, v], axis=1), distance_upper_bound=8.0)
        a[inside[np.rint(v).astype(int), np.rint(u).astype(int)] <= 0] = np.inf   # outside his pieces
        d[ok] = a
    return d


def _line(d_units, half_width):
    """1 - depth on a line of that half-width (game units), 1 off it; crisp edge."""
    t = np.clip((half_width - d_units) / LINE_SOFT + 0.5, 0, 1)
    return 1 - LINE_DEPTH * t * t * (3 - 2 * t)


# ---------------------------------------------------------------- his atlas, mapped onto our meshes


def _own_piece(U, V, k, anchors):
    """Texels k keep their atlas spot only inside the piece(s) their anchors stand in: the outer side of a leg
    unrolled past its piece's outline landed in the NEXT piece and drew its knee seams there (v4 in game: a thick
    'U' on the outer thigh)."""
    if 'pieces' not in _cache:
        from scipy import ndimage
        _skel, inside = _strokes()
        _cache['pieces'] = ndimage.label(inside > 0)[0]
    lab = _cache['pieces']
    h, w = lab.shape
    own = {int(lab[int(y), int(x)]) for x, y in anchors} - {0}
    u, v = U[k], V[k]
    ok = np.isfinite(u)
    got = np.zeros(len(k), int)
    got[ok] = lab[np.clip(np.rint(v[ok]).astype(int), 0, h - 1), np.clip(np.rint(u[ok]).astype(int), 0, w - 1)]
    U[k[~np.isin(got, list(own))]] = np.nan


def atlas_uv(m):
    """Per covered texel of a body (body.UVMap): (idx, positions, U, V, S) -- the atlas pixel it takes and the atlas
    pixels per game unit there; NaN U where no piece is meant to reach (hands, feet, the gaps between pieces, another
    piece than its own)."""
    L = landmarks(m)
    lo, hi = m.bounds

    def Z(h):
        return lo[2] + h * (hi[2] - lo[2])
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx]
    R = m.region.reshape(-1)[idx]
    x, y, z = X[:, 0], X[:, 1], X[:, 2]
    U = np.full(len(idx), np.nan)
    V = np.full(len(idx), np.nan)
    S = np.ones(len(idx))
    # the torso, unrolled round its middle: front and back parted by the plane through its depth's middle per height
    torso = R == REGIONS.index('torso')
    mid = torso & (np.abs(x) < 1.5)
    zc, ym = [], []
    for z0 in np.arange(z[torso].min(), z[torso].max(), 1.0):
        sel = mid & (z >= z0) & (z < z0 + 1.0)
        if (sel & (y > 0)).any() and (sel & (y < 0)).any():
            zc.append(z0 + 0.5)
            ym.append((y[sel].max() + y[sel].min()) / 2)
    ymid = np.interp(z, zc, np.convolve(np.pad(ym, 2, mode='edge'), np.ones(5) / 5, mode='valid'))
    r = np.hypot(x, y - ymid)
    female = m.sex == 'female'
    F = FEMALE_FRONT if female else MALE_FRONT
    B = FEMALE_BACK if female else MALE_BACK
    s = (F['cx'] - F['nip'][0]) / abs(L['nipples'][1][0])        # atlas px per game unit: his nipples on ours
    front = torso & (y > ymid)
    U[front] = (F['cx'] - np.arctan2(x, y - ymid) * r * s)[front]   # drawn facing us: his left is the body's right
    V[front] = (F['nip'][1] + (Z(L['nipple']) - z) * s)[front]
    back = torso & (y <= ymid)
    U[back] = (B['cx'] + np.arctan2(x, ymid - y) * r * s)[back]     # from behind: his left is the body's left
    V[back] = (B['top'] + (Z(L['top']) - z) * s)[back]
    S[torso] = s
    _own_piece(U, V, np.flatnonzero(front), [(F['cx'], F['nip'][1])])
    _own_piece(U, V, np.flatnonzero(back), [(B['cx'], B['top'] + 40)])
    # the legs: front and back halves round each leg's own centre, crotch to knee as his pieces
    zcr, zk = Z(L['crotch']), Z(0.285)
    leg = R == REGIONS.index('leg')
    for side in (1, -1):
        lm = leg & (x * side > 0)
        limb = _Limb(X[lm & (z < zcr - 1.0)], np.array((0.0, 0.0, -1.0)), np.array((side, 0.0, 0.0)))
        _t, rl, th = limb.coords(X[lm])          # theta 0 = out to the side; the front is -side * pi/2
        out = rl * np.cos(th)
        frontish = np.cos(th - side * np.pi / 2) < 0
        sub = np.flatnonzero(lm)
        for piece, half, sign in ((LEG_FRONT, frontish, -1), (LEG_BACK, ~frontish, 1)):
            sv = (piece['knee'] - piece['top']) / (zcr - zk)
            # the outer hip is the leg's (by bone) but above the crotch: it would read the atlas above the leg
            # piece's top -- the torso piece's bottom seam, a straight dash at each hip -- so it takes none
            sel = half & (z[sub] < zcr)
            k = sub[sel]
            U[k] = piece['cx'] + sign * out[sel] * sv
            V[k] = piece['top'] + (zcr - z[k]) * sv
            S[k] = sv
            _own_piece(U, V, k, [(piece['cx'], (piece['top'] + piece['knee']) / 2)])
    # the arms: his long arm piece, shoulder to wrist, unrolled round the arm from its underside
    arm = R == REGIONS.index('arm')
    for side in (1, -1):
        am = arm & (x * side > 0)
        limb = _Limb(X[am], np.array((side, 0.0, -0.5)), np.array((0.0, 0.0, -1.0)))
        t, ra, tha = limb.coords(X[am])
        sa = ARM['length'] / (limb.tmax - limb.tmin)
        k = np.flatnonzero(am)
        U[k] = ARM['cx'] + side * ra * (np.abs(tha) - np.pi / 2) * sa
        V[k] = ARM['shoulder'] + (t - limb.tmin) * sa
        S[k] = sa
        _own_piece(U, V, k, [(ARM['cx'], ARM['shoulder'] + 0.2 * ARM['length']),    # upper arm and forearm (if his
                             (ARM['cx'], ARM['shoulder'] + 0.8 * ARM['length'])])  # elbow parts them)
    return idx, X, U, V, S


def head_uv(m):
    """Per covered texel of a head (face.HeadMap): (idx, U, V, s) on his head piece seen from the side, the face's
    front left out (no piece sees it squarely)."""
    L = face_landmarks(m)
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx]
    N = m.normal.reshape(-1, 3)[idx]
    yn, zn, zc = L['nose'][1], L['nose'][2], L['chin'][2]
    H = HEAD_SIDE
    s = (H['chin'][1] - H['nose'][1]) / (zn - zc)
    U = H['nose'][0] - (yn - X[:, 1]) * s
    V = H['nose'][1] + (zn - X[:, 2]) * s
    U[np.abs(N[:, 0]) < 0.45] = np.nan
    _own_piece(U, V, np.arange(len(U)), [(H['nose'][0] - 80, H['nose'][1])])
    return idx, U, V, s


def _underbust_keep(m, X):
    """1 everywhere but the band under a woman's breasts he struck out (0 there, soft-edged)."""
    zn = float(np.mean([p[2] for p in landmarks(m)['nipples'].values()]))
    z = X[:, 2]
    inside = np.minimum((zn + UNDERBUST_TOP) - z, z - (zn - UNDERBUST_DEPTH))   # right across: a midline left in it
                                                                               # kept a mark at the sternum
    return np.where(X[:, 1] > 0, np.clip(1 - inside / UNDERBUST_FADE, 0, 1), 1.0)


def _multiply(m, f):
    """(rgb, alpha) for make_marks' multiply path: the colour that, over its SKIN, multiplies by f."""
    from preview import SKIN
    return np.clip(SKIN[None, None, :] * f[..., None], 0, 1), m.covered.astype(np.float64)


# ---------------------------------------------------------------- the hands' joint lines

HAND_RING_REACH = 1.1      # game units off a finger's axis a ring reaches (the finger, not its neighbours)
WRIST_RING = 0.9           # game units up the hand from the wrist's open edge


def hand_distance(m):
    """Per covered texel of a hands map (hands.HandMap): distance (game units) to its nearest joint line -- a ring
    where each finger bone begins (the knuckles included) and one round the wrist."""
    import collections
    import hands
    from scipy.spatial import cKDTree
    idx = np.flatnonzero(m.covered)
    X = m.position.reshape(-1, 3)[idx]
    d = np.full(len(idx), np.inf)
    for side in ('L', 'R'):
        for f in range(1, 6):
            if f'{side}Arm_Finger{f}3' not in m.bone_names:
                continue
            axis = hands.finger_frame(m, side, f)[0]
            bones = [hands._bone_vertices(m, f'{side}Arm_Finger{f}{k}') for k in (1, 2, 3)]
            c = np.concatenate(bones).mean(axis=0)
            rel = X - c
            near = np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1) < HAND_RING_REACH
            for B in bones:
                t0 = (B @ axis).min() + 0.08
                d[near] = np.minimum(d[near], np.abs(X[near] @ axis - t0))
    V, T = m.vertices, m.triangles
    uniq, inv = np.unique(np.round(V, 3), axis=0, return_inverse=True)
    inv = inv.ravel()
    count = collections.Counter()
    for t in T:
        a, b, cc = inv[t]
        for e in ((a, b), (b, cc), (cc, a)):
            count[(min(e), max(e))] += 1
    ends = np.array([e for e, k in count.items() if k == 1]).reshape(-1, 2)
    if len(ends):
        A, Bv = uniq[ends[:, 0]], uniq[ends[:, 1]]
        P = (A[:, None, :] + np.linspace(0, 1, 8)[None, :, None] * (Bv - A)[:, None, :]).reshape(-1, 3)
        d = np.minimum(d, np.abs(cKDTree(P).query(X)[0] - WRIST_RING))
    return idx, d


# ---------------------------------------------------------------- the painters


def pack_body(m, rng=None):
    idx, X, U, V, S = atlas_uv(m)
    f = _line(_seam_distance(U, V) / S, LINE_W)
    if m.sex == 'female':
        f = 1 - (1 - f) * _underbust_keep(m, X)
    out = np.ones(m.covered.shape)
    out.reshape(-1)[idx] = f
    return _multiply(m, out)


def pack_hands(m, rng=None):
    idx, d = hand_distance(m)
    out = np.ones(m.covered.shape)
    out.reshape(-1)[idx] = _line(d, HAND_LINE_W)
    return _multiply(m, out)


# ---------------------------------------------------------------- variant B: plated (his material, opaque-ish)
#
# alasdairn after test v2: "I can also add the material back, have it darken the lines and boom we're back in
# business ... do this as a secondary option actually". So a second, separately selectable look: his atlas's own pale
# synthetic surface, projected as above (a clean patch of his skin wherever no piece reaches), mostly opaque -- a lit
# overlay (.bgsm, make_marks' LIT_PAINTERS), the same on every skin tone -- with his seams over it as wider, darker
# panel gaps (the testers' Gen 1 synth / SyntheticZombies mood). The face: a face tint laid on with blend "Default".

PATCH = (845, 220, 915, 300)    # a clean patch of his skin (the male back's left shoulder blade, clear of seams)
PATCH_TILE = 9.0                # game units the patch covers before it mirrors
PLATED_ALPHA = 0.92             # mostly his surface; a little of the person's own skin under it
PLATED_LINE_W = 0.11            # half-width: a panel gap, not a hairline
PLATED_LINE_DEPTH = 0.86
PLATED_FACE_LINE_W = 0.09
PLATED_HAND_LINE_W = 0.07
PLATED_SPEC = (0.45, 0.6)       # specular, smoothness: a soft synthetic sheen


def _colour():
    if 'rgb' not in _cache:
        from PIL import Image
        _cache['rgb'] = np.asarray(Image.open(ATLAS).convert('RGB'), dtype=np.float32) / 255.0
        x0, y0, x1, y1 = PATCH
        _cache['patch'] = _cache['rgb'][y0:y1, x0:x1]
    return _cache['rgb'], _cache['patch']


def _triplanar(tile, X, N, size):
    """tile laid over points X with normals N, mirrored every `size` game units along each plane, blended by how
    squarely the surface faces it (normal^4); z up, so each plane's image stands upright."""
    h, w = tile.shape[:2]

    def sample(u, v):
        fu, fv = np.mod(u / size, 2.0), np.mod(v / size, 2.0)
        fu = np.where(fu > 1, 2 - fu, fu)
        fv = np.where(fv > 1, 2 - fv, fv)
        return tile[np.clip((fv * (h - 1)).astype(int), 0, h - 1), np.clip((fu * (w - 1)).astype(int), 0, w - 1)]
    wts = np.abs(N) ** 4
    wts = (wts / np.maximum(wts.sum(axis=1, keepdims=True), 1e-9))[:, :, None]
    return (wts[:, 0] * sample(X[:, 1], -X[:, 2]) + wts[:, 1] * sample(X[:, 0], -X[:, 2]) +
            wts[:, 2] * sample(X[:, 0], X[:, 1]))


def _surface(X, N, U, V):
    """His surface per point: the atlas's colour where a piece maps (bilinear), his clean patch elsewhere, the two
    cross-faded over a piece's outline."""
    rgb, patch = _colour()
    _, inside = _strokes()
    col = _triplanar(patch, X, N, PATCH_TILE)
    ok = np.isfinite(U)
    if ok.any():
        h, w = inside.shape
        u = np.clip(U[ok], 0, w - 1.001)
        v = np.clip(V[ok], 0, h - 1.001)
        x0, y0 = np.floor(u).astype(int), np.floor(v).astype(int)
        fx, fy = (u - x0)[:, None], (v - y0)[:, None]
        c = (rgb[y0, x0] * (1 - fx) * (1 - fy) + rgb[y0, x0 + 1] * fx * (1 - fy) +
             rgb[y0 + 1, x0] * (1 - fx) * fy + rgb[y0 + 1, x0 + 1] * fx * fy)
        wt = np.clip(inside[np.rint(v).astype(int), np.rint(u).astype(int)] / EDGE_PX, 0, 1)[:, None]
        col[ok] = c * wt + col[ok] * (1 - wt)
    return col


def _plated_line(d_units, half_width):
    t = np.clip((half_width - d_units) / LINE_SOFT + 0.5, 0, 1)
    return 1 - PLATED_LINE_DEPTH * t * t * (3 - 2 * t)


def _lit(m, idx, col):
    diffuse = np.zeros(m.covered.shape + (4,))
    spec = np.zeros(m.covered.shape + (2,))
    diffuse.reshape(-1, 4)[idx, :3] = np.clip(col, 0, 1)
    diffuse.reshape(-1, 4)[idx, 3] = PLATED_ALPHA
    spec.reshape(-1, 2)[idx] = PLATED_SPEC
    return diffuse, spec


def plated_body(m, rng=None):
    """(diffuse RGBA, spec RG) for make_marks' lit path."""
    idx, X, U, V, S = atlas_uv(m)
    N = m.normal.reshape(-1, 3)[idx]
    line = _plated_line(_seam_distance(U, V) / S, PLATED_LINE_W)
    if m.sex == 'female':
        line = 1 - (1 - line) * _underbust_keep(m, X)
    return _lit(m, idx, _surface(X, N, U, V) * line[:, None])


def plated_hands(m, rng=None):
    idx, d = hand_distance(m)
    X = m.position.reshape(-1, 3)[idx]
    N = m.normal.reshape(-1, 3)[idx]
    n = len(idx)
    col = _surface(X, N, np.full(n, np.nan), np.full(n, np.nan)) * _plated_line(d, PLATED_HAND_LINE_W)[:, None]
    return _lit(m, idx, col)


def plated_face(m):
    """The face tint, blend "Default" (laid over the face): RGBA, his surface with his head band's seams."""
    idx, U, V, s = head_uv(m)
    X = m.position.reshape(-1, 3)[idx]
    N = m.normal.reshape(-1, 3)[idx]
    col = _surface(X, N, U, V) * _plated_line(_seam_distance(U, V) / s, PLATED_FACE_LINE_W)[:, None]
    out = np.zeros(m.covered.shape + (4,))
    out.reshape(-1, 4)[idx, :3] = np.clip(col, 0, 1)
    out.reshape(-1, 4)[idx, 3] = PLATED_ALPHA
    return out


def pack_face(m):
    """The face tint, blend "Multiply" (white leaves the face as it is; lines only now, so a plain darkening -- the
    "Overlay" blend turned a dark line orange on light skin): RGBA."""
    idx, U, V, s = head_uv(m)
    f = np.ones(m.covered.shape)
    f.reshape(-1)[idx] = _line(_seam_distance(U, V) / s, FACE_LINE_W)
    out = np.zeros(m.covered.shape + (4,))
    out[..., :3] = np.clip(f, 0, 1)[..., None]
    out[..., 3] = m.covered
    return out
