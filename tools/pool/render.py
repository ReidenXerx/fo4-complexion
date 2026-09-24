"""Review sheets for the pool: each body drawn front and side (flat-shaded, orthographic), labelled with
its name, archetype and measurements. Needs Pillow; nothing else in Silhouette does."""
import math

from measure import measure


def render(verts, tris, size=(150, 300)):
    from PIL import Image, ImageDraw
    zs = [p[2] for p in verts]
    zmin, zmax = min(zs), max(zs)
    scale = (size[1] - 20) / (zmax - zmin)
    img = Image.new('RGB', (size[0] * 2, size[1]), (40, 40, 46))
    d = ImageDraw.Draw(img)
    for k, view in enumerate(('front', 'side')):
        ox = size[0] * k + size[0] / 2
        # the body faces +y: front looks from +y, side from +x (her left); painter's order, far first
        V = (0.0, 1.0, 0.0) if view == 'front' else (1.0, 0.0, 0.0)
        L = (0.4 * V[0] + 0.3, 0.8 * V[1] + 0.4 * V[0], 0.55)
        ll = math.sqrt(sum(c * c for c in L))
        L = tuple(c / ll for c in L)
        polys = []
        for a, b, c in tris:
            A, B, C = verts[a], verts[b], verts[c]
            ux, uy, uz = B[0] - A[0], B[1] - A[1], B[2] - A[2]
            vx, vy, vz = C[0] - A[0], C[1] - A[1], C[2] - A[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            depth = sum(P[0] * V[0] + P[1] * V[1] for P in (A, B, C))
            if view == 'front':
                pts = [(ox - P[0] * scale, size[1] - 10 - (P[2] - zmin) * scale) for P in (A, B, C)]
            else:
                pts = [(ox + P[1] * scale, size[1] - 10 - (P[2] - zmin) * scale) for P in (A, B, C)]
            lit = abs(nx * L[0] + ny * L[1] + nz * L[2]) / nl
            polys.append((depth, pts, 0.3 + 0.7 * lit))
        polys.sort(key=lambda t: t[0])
        for _d, pts, sh in polys:
            d.polygon(pts, fill=tuple(int(c * sh) for c in (210, 170, 150)))
    return img


def render_sheet(body, rows, path, cols=6):
    from PIL import Image, ImageDraw
    thumbs = []
    for c in rows:
        verts = body.build({s: v / 100.0 for s, v in c['values'].items()})
        img = render(verts, body.tris)
        m = c.get('measure') or measure(verts, body.region, body.sex)
        d = ImageDraw.Draw(img)
        d.text((4, 2), f"{c['name']}  {c['archetype']}", fill=(255, 255, 255))
        d.text((4, 14), f"whr {m['whr']:.2f}  b/w {m['bwr']:.2f}  vol {m['volume']:.0f}", fill=(200, 200, 200))
        thumbs.append(img)
    if not thumbs:
        return
    w, h = thumbs[0].size
    out = Image.new('RGB', (w * cols, h * math.ceil(len(thumbs) / cols)), (30, 30, 34))
    for i, t in enumerate(thumbs):
        out.paste(t, ((i % cols) * w, (i // cols) * h))
    out.save(path)
