"""Body measurements from horizontal slices of skin regions (arm / leg / torso by heaviest bone).
The body faces +y, z is up (feet ~-120, neck ~-7). Girths are convex-hull perimeters."""
import math


def hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def perimeter(h):
    return sum(math.dist(h[i], h[(i + 1) % len(h)]) for i in range(len(h)))


class Slicer:
    def __init__(self, verts, region):
        self.v = verts
        self.r = region

    def pts(self, z0, z1, regions, side=None):
        out = []
        for p, r in zip(self.v, self.r):
            if z0 <= p[2] < z1 and r in regions and (side is None or p[0] * side > 0):
                out.append((p[0], p[1]))
        return out

    def section(self, z, regions=('torso',), side=None, h=2.0):
        pts = self.pts(z - h / 2, z + h / 2, regions, side)
        if len(pts) < 8:
            return None
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return {'girth': perimeter(hull(pts)), 'width': max(xs) - min(xs), 'front': max(ys), 'back': min(ys)}

    def over(self, z0, z1, key, pick, regions=('torso',), side=None):
        vals = [self.section(z + 0.5, regions, side) for z in range(z0, z1)]
        vals = [v[key] for v in vals if v]
        return pick(vals) if vals else 0.0


# landmark heights, read off the zeroed references' profiles
LANDMARKS = {
    'female': {'shoulder': -13, 'bust': (-30, -16), 'underbust': -31, 'waist': (-46, -34), 'belly': (-52, -40),
               'hip': (-62, -48), 'thigh': -70, 'calf': -100, 'upperarm': -22},
    'male': {'shoulder': -13, 'bust': (-30, -16), 'underbust': -32, 'waist': (-48, -34), 'belly': (-54, -40),
             'hip': (-62, -48), 'thigh': -70, 'calf': -100, 'upperarm': -22},
}


def measure(verts, region, sex):
    L = LANDMARKS[sex]
    s = Slicer(verts, region)
    m = {}
    m['bust'] = s.over(*L['bust'], 'girth', max)
    ub = s.section(L['underbust'])
    m['underbust'] = ub['girth']
    m['waist'] = s.over(*L['waist'], 'girth', min)
    m['hip'] = s.over(*L['hip'], 'girth', max, regions=('torso', 'leg'))
    m['thigh'] = (s.section(L['thigh'], ('leg',), +1) or {}).get('girth', 0.0)
    m['calf'] = (s.section(L['calf'], ('leg',), +1) or {}).get('girth', 0.0)
    m['arm'] = (s.section(L['upperarm'], ('arm',), +1) or {}).get('girth', 0.0)
    m['shoulders'] = (s.section(L['shoulder']) or {}).get('width', 0.0)
    m['bustProjection'] = s.over(*L['bust'], 'front', max) - ub['front']
    m['belly'] = s.over(*L['belly'], 'front', max) - s.over(*L['waist'], 'front', min)
    m['butt'] = s.over(*L['waist'], 'back', max) - s.over(*L['hip'], 'back', min, regions=('torso', 'leg'))
    best, bz = -1e9, 0
    for z in range(L['bust'][0] - 6, L['bust'][1]):
        sec = s.section(z + 0.5)
        if sec and sec['front'] > best:
            best, bz = sec['front'], z
    m['bustHeight'] = bz                     # where the breast is fullest: lower = hangs more
    m['whr'] = m['waist'] / m['hip'] if m['hip'] else 0.0
    m['bwr'] = m['bust'] / m['waist'] if m['waist'] else 0.0
    m['volume'] = m['bust'] + m['waist'] + m['hip'] + 2 * m['thigh'] + 2 * m['arm']   # overall size
    return m
