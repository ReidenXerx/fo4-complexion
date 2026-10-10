"""Fading every mark out at the body mesh's seams with the head and the hands (owner, 2026-10-03).

The body mesh stops at the neck and the wrists, where the head and hands meshes take over -- and an overlay only
covers the body. So a mark that reaches a seam (sunburn, a tan, grime, body paint) ends there in a hard line against
the bare head or hand. Every body template's mark fades to nothing over the last few units before those seams.

The seams are found on the mesh, not guessed: the open edges of the body shape with its UV splits welded (an edge
used by one triangle only). Measured on both bodies: a loop at each wrist (x about +-36) and the neck opening; the
female body also has an opening at the crotch, which is not a seam with another mesh and is left alone.

    python tools/paint/seams.py --refade        re-fades the finished multiplier PNGs in build/marks and re-encodes
                                                their DDS (the same result as repainting: fading the mark's alpha
                                                scales the multiplier's distance from neutral by the same factor)
"""
import collections

import numpy as np

FADE_START = 0.3   # game units from the seam: fully faded closer than this
FADE_WIDTH = 2.7   # ... and fully there from FADE_START + FADE_WIDTH on (about 4 cm)


def seam_vertices(m):
    """Body-mesh vertices on the neck and wrist openings."""
    if hasattr(m, '_seams'):
        return m._seams
    V, T = m.vertices, m.triangles
    uniq, inv = np.unique(np.round(V, 3), axis=0, return_inverse=True)
    inv = inv.ravel()
    edges = collections.Counter()
    for t in T:
        a, b, c = inv[t]
        for e in ((a, b), (b, c), (c, a)):
            edges[(min(e), max(e))] += 1
    ends = sorted({v for e, n in edges.items() if n == 1 for v in e})
    P = uniq[ends]
    top = V[:, 2].max()
    reach = np.abs(V[:, 0]).max()
    keep = (P[:, 2] > top - 8.0) | (np.abs(P[:, 0]) > reach * 0.8)   # the neck, the wrists
    m._seams = P[keep]
    return m._seams


def seam_fade(m, start=FADE_START, width=FADE_WIDTH):
    """Per texel 0..1: 0 at a seam, 1 from start + width away (smoothstep). Marks covering large areas (grime)
    take a wider fade: the head and hands next to them are clean, so a dirty neck reads as a seam however soft its
    last 4 cm are (alasdairn, 2026-10-09)."""
    key = (start, width)
    cache = m.__dict__.setdefault('_seam_fades', {})
    if key in cache:
        return cache[key]
    if not hasattr(m, '_seam_dist'):
        S = seam_vertices(m)
        idx = np.flatnonzero(m.covered)
        P = m.position.reshape(-1, 3)[idx]
        best = np.empty(len(idx))
        for k in range(0, len(P), 65536):  # in chunks of texels: all at once is gigabytes at 2048
            q = P[k:k + 65536]
            best[k:k + 65536] = np.sqrt(((q[:, None, :] - S[None, :, :]) ** 2).sum(-1)).min(axis=1)
        m._seam_dist = (idx, best)
    idx, best = m._seam_dist
    out = np.ones(m.covered.shape)
    t = np.clip((best - start) / width, 0, 1)
    out.reshape(-1)[idx] = t * t * (3 - 2 * t)
    cache[key] = out
    return out


def main():
    import pathlib
    import subprocess
    import sys
    from PIL import Image
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import make_marks as mm
    from body import UVMap
    if '--refade' not in sys.argv:
        print(__doc__)
        return
    tool = mm.texconv()
    tex_dir = mm.ROOT / 'data' / 'Textures' / 'Overlays' / 'Complexion'
    work = mm.ROOT / 'build' / 'marks'
    only = [a for a in sys.argv[1:] if not a.startswith('--')]
    maps = {}
    done = 0
    for tid, sex, painter, args, size, tag in mm.MARKS:
        if painter in mm.HAND_PAINTERS or painter in mm.SEAM_EXEMPT:
            continue
        if only and not any(tid.startswith(o) for o in only):
            continue
        png = work / f'{tid}_d.png'
        if not png.exists():
            print(f'  {tid}: no PNG, repaint it')
            continue
        img = np.asarray(Image.open(png).convert('RGB'), dtype=np.float64) / 255.0
        key = (sex, img.shape[0])
        if key not in maps:
            maps[key] = UVMap(mm.DATA, sex, img.shape[0])
        f = seam_fade(maps[key])[..., None]
        out = mm.NEUTRAL + (img - mm.NEUTRAL) * f
        if np.abs(out - img).max() < 1.5 / 255:
            continue  # nothing near a seam
        Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB').save(png)
        r = subprocess.run([str(tool), '-nologo', '-y', '-ft', 'dds', '-f', 'BC1_UNORM', '-m', '0', '-o', str(tex_dir), str(png)],
                           capture_output=True, text=True)
        made = next((x for x in tex_dir.iterdir() if x.name.lower() == f'{tid}_d.dds'.lower()), None)
        if r.returncode or not made:
            sys.exit(f'texconv failed on {png}')
        if made.name != f'{tid}_d.dds':
            made.rename(tex_dir / f'{tid}_d.dds')
        done += 1
        print(f'  {tid}: faded at the seams')
    print(f'{done} template(s) re-faded')


if __name__ == '__main__':
    main()
