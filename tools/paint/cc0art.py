"""Tattoo pieces from real, freely licensed tattoo art instead of drawn from primitives (alasdairn, 2026-10-09: a
tattoo is lines and shading, and two rounds of procedural pieces "using shapes" were rejected; the owner chose
CC0 / public-domain art, 4096 textures for the detailed ones). Sources and licences: tools/paint/art/SOURCES.md.

A scan is ink on paper. Divided by the paper colour under it, it is exactly the factor the ink multiplies the
paper by -- and a multiply overlay (C-12) multiplies the skin by the same factor, so the piece lands on the skin
as it was drawn: black linework, the washes thinned like tattoo colour, no paper. Returns RGBA for
flash.project_rgba (prefiltered to the texels it lands on).
"""
import pathlib

import numpy as np
from PIL import Image, ImageFilter

ART = pathlib.Path(__file__).resolve().parent / 'art'
SKIN = np.array((0.80, 0.64, 0.54))  # make_marks.SKIN: the colour project_rgba's rgb is relative to


def _paper(a, reach):
    """The paper colour under every pixel: the brightest nearby (ink only darkens), smoothed. reach: wider than
    the widest solid ink area, in pixels."""
    h, w, _ = a.shape
    k = max(reach // 8, 1)
    small = Image.fromarray(np.uint8(a * 255)).resize((max(w // k, 1), max(h // k, 1)), Image.BOX)
    small = small.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
    return np.asarray(small.resize((w, h), Image.BILINEAR), np.float64) / 255.0


def scan(name, box=None, width=1600, mirror=False, clean=0.10, reach=240, holes=(), margin=0.015, bold=0):
    """art/<name> cropped to box (source pixels), as RGBA ink. clean: paper grain and stains lighter than this
    much darkening count as skin. holes: (x0, y0, x1, y1) source boxes to blank (grommets, stray marks).
    margin: only what lies within this share of the width of a real line is kept -- old paper's stains and
    foxing never reach the skin. bold: thicken the lines by this many source pixels."""
    src = Image.open(ART / name)
    if src.mode in ('RGBA', 'LA', 'P'):
        src = src.convert('RGBA')
        flat = Image.new('RGBA', src.size, (255, 255, 255, 255))
        flat.alpha_composite(src)
        src = flat
    src = src.convert('RGB')
    a = np.asarray(src, np.float64) / 255.0
    paper = _paper(a, reach)
    a = np.clip(a / np.maximum(paper, 0.05), 0, 1)
    for x0, y0, x1, y1 in holes:
        a[y0:y1, x0:x1] = 1.0
    if box:
        a = a[box[1]:box[3], box[0]:box[2]]
    img = Image.fromarray(np.uint8(a * 255 + 0.5))
    if bold:  # thin pen lines thickened by `bold` source pixels: they must survive a few texels
        img = img.filter(ImageFilter.MinFilter(2 * bold + 1))
    if mirror:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    img = img.resize((width, int(width * img.height / img.width)), Image.LANCZOS)
    f = np.asarray(img, np.float64) / 255.0
    f = np.clip(1 - (1 - f - clean) / (1 - clean), 0, 1)                 # the factor, paper grain removed
    dark = np.clip((1 - f.mean(-1, keepdims=True) - 0.3) / 0.25, 0, 1)
    w = dark * np.clip((f[..., :1] - f[..., 2:]) * 10, 0, 1)            # brown (red over blue) and dark: a pen line
    f = f * (1 - w) + f.min(-1, keepdims=True) * w                       # aged brown pen lines read black, washes keep colour
    alpha = 1 - f.min(-1)
    if margin:
        r = max(int(margin * width), 1)
        lines = Image.fromarray(np.uint8((f.max(-1) < 0.68) * 255))   # a line is dark in every channel, a stain is not.filter(ImageFilter.MaxFilter(2 * (r // 2) + 1))
        lines = lines.filter(ImageFilter.MaxFilter(2 * (r // 2) + 1)).filter(ImageFilter.GaussianBlur(r / 3))
        alpha = alpha * np.asarray(lines, np.float64) / 255.0
    rgb = np.where(alpha[..., None] > 1e-3, SKIN * (f - (1 - alpha[..., None])) / np.maximum(alpha[..., None], 1e-3), SKIN)
    out = Image.fromarray(np.uint8(np.clip(rgb, 0, 1) * 255 + 0.5)).convert('RGBA')
    out.putalpha(Image.fromarray(np.uint8(alpha * 255 + 0.5)))
    out.info['prefilter'] = True
    return out


# The pieces. Boxes are in the source's pixels.
def eagle():
    """The wings-spread eagle with its UNION FOREVER MORE banner, arrows and laurel: a hand-drawn early-1900s
    flash sheet (Smithsonian American Art Museum 1998.84.50D, CC0). The grommets in the corners and the bits of
    the nurse and the Kewpie above are blanked."""
    return scan('saam_1998_84_50D.jpg', box=(165, 885, 2835, 2265), width=2000, clean=0.16,
                holes=((0, 2040, 420, 2414), (2640, 2040, 3000, 2414), (1300, 700, 1760, 1000), (2150, 780, 2420, 970)))


def swallow(mirror=False):
    """The diving swallow, black linework with blue stipple shading (SAAM 1998.84.50C, CC0)."""
    return scan('saam_1998_84_50C.jpg', box=(2005, 1395, 2725, 2240), mirror=mirror, width=1000, bold=2,
                holes=((2600, 2040, 3000, 2364),))


def swallow_pair():
    """Two of them facing each other, for the collarbones."""
    one = swallow()
    w, h = one.size
    pair = Image.new('RGBA', (int(w * 2.35), h), (0, 0, 0, 0))
    pair.alpha_composite(one, (0, 0))                                        # it flies right: the left one
    pair.alpha_composite(one.transpose(Image.FLIP_LEFT_RIGHT), (pair.width - w, 0))
    pair.info['prefilter'] = True
    return pair


def revolver():
    """An engraved revolver: horizontal line shading on the steel, a stippled checkered grip (openclipart 306002,
    CC0)."""
    return scan('openclipart_306002_revolver.png', width=1800, reach=400)


if __name__ == '__main__':
    import sys
    fn = {'eagle': eagle, 'swallow': swallow, 'pair': swallow_pair, 'revolver': revolver}[sys.argv[1]]
    im = fn()
    bg = Image.new('RGBA', im.size, (214, 176, 150, 255))
    bg.alpha_composite(im)
    bg.convert('RGB').save(sys.argv[2])
    print(im.size)
