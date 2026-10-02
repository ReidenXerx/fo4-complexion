"""Front and back views of the body wearing painted overlays, for judging them by eye before they reach a game.

Each covered texel of the UV map already knows its 3D point (body.UVMap), so the body is drawn by splatting
texels -- nearest wins -- rather than rasterizing triangles: millions of points into a few hundred pixels leave no
holes. Orthographic, lit from the front-left.
"""
import numpy as np
from PIL import Image, ImageDraw

SKIN = np.array((0.80, 0.64, 0.54))


def view(m, rgb, alpha, side='front', height=520):
    cov = m.covered
    P = m.position[cov]
    N = m.normal[cov]
    col = rgb[cov]
    a = alpha[cov][:, None]
    lo, hi = m.bounds
    scale = (height - 20) / (hi[2] - lo[2])
    width = int((hi[0] - lo[0]) * scale) + 40
    sign = 1.0 if side == 'front' else -1.0
    visible = N[:, 1] * sign > 0.0
    P, N, col, a = P[visible], N[visible], col[visible], a[visible]
    sx = ((P[:, 0] * (-sign) - lo[0] * (-sign if sign < 0 else 1)) * scale).astype(int)
    if side == 'front':
        sx = ((hi[0] - P[:, 0]) * scale).astype(int) + 20
    else:
        sx = ((P[:, 0] - lo[0]) * scale).astype(int) + 20
    sy = ((hi[2] - P[:, 2]) * scale).astype(int) + 10
    depth = P[:, 1] * sign
    order = np.argsort(depth)
    light = np.array((0.35 * -sign, 0.85 * sign, 0.4))
    light /= np.linalg.norm(light)
    shade = np.clip(N @ light, 0.15, 1.0)[:, None] * 0.85 + 0.15
    colour = (SKIN * (1 - a) + col * a) * shade
    img = np.full((height, width, 3), 0.16)
    img[sy[order], sx[order]] = colour[order]
    # Where the UV map is stretched (the backs of the thighs) too few texels land per pixel and the background
    # shows through in rows of dots: a pixel missed but mostly surrounded by body takes its neighbours' mean.
    filled = np.zeros((height, width), bool)
    filled[sy, sx] = True
    for _ in range(2):
        acc = np.zeros_like(img)
        cnt = np.zeros((height, width))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    sh = np.roll(filled, (dy, dx), (0, 1))
                    acc += np.roll(img, (dy, dx), (0, 1)) * sh[..., None]
                    cnt += sh
        hole = ~filled & (cnt >= 5)
        img[hole] = acc[hole] / cnt[hole][:, None]
        filled |= hole
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def sheet(m, items, path, height=420):
    """items: [(label, rgb, alpha)] -> one image, front and back of each side by side."""
    tiles = []
    for label, rgb, alpha in items:
        f = view(m, rgb, alpha, 'front', height)
        b = view(m, rgb, alpha, 'back', height)
        t = Image.new('RGB', (f.width + b.width, height + 22), (30, 30, 34))
        t.paste(f, (0, 22))
        t.paste(b, (f.width, 22))
        ImageDraw.Draw(t).text((6, 4), label, fill=(255, 255, 170))
        tiles.append(t)
    cols = min(4, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    W, H = tiles[0].width, tiles[0].height
    out = Image.new('RGB', (W * cols, H * rows), (20, 20, 20))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * W, (i // cols) * H))
    out.save(path)
    return path
