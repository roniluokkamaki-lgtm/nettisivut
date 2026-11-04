"""Show a painting hanging in a drawn Scandinavian-style room, in several frames.

    py -3 mockups/room_mockup.py

The room is drawn, not photographed: a warm white wall, a light oak floor, an
oak sideboard with a vase and books, a linen floor lamp and an olive tree. The
painting is the real photograph, untouched, hung at its true size over the
sideboard, so the picture gives an honest idea of scale. Everything in the
room is drawn to the same scale (13 px per cm in the finished image).

Writes one picture per frame and an overview of all of them into mockups/.
"""

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import to_srgb  # noqa: E402

OUT = Path(__file__).resolve().parent
FONT = ROOT / "docs" / "fonts" / "inter-latin.woff2"

PAINTING = ROOT / "originals" / "abstract.jpg"
PAINTING_SLUG = "abstract"
PAINTING_H_CM = 33  # the photo's own proportions set the width (about 32 cm)
PAINTING_CENTRE = (115, 97)  # cm: over the middle of the sideboard

# frames, as bands from the canvas outwards: (kind, width in cm, colour).
# depth is how far the frame stands off the wall, which sets its shadow.
FRAMES = {
    "none": {"label": "Ilman kehystä · No frame", "depth": 2.0, "bands": [], "grain": 0},
    "oak": {"label": "Tammi, kelluva kehys · Oak floater frame", "depth": 4.0, "grain": 0.04,
            "bands": [("gap", 0.7, (78, 64, 52)), ("flat", 1.0, (206, 174, 130)),
                      ("bevel_out", 0.15, (206, 174, 130))]},
    "black": {"label": "Musta kehys · Black frame", "depth": 3.0, "grain": 0.03,
              "bands": [("bevel_in", 0.4, (58, 55, 52)), ("flat", 1.6, (31, 30, 29)),
                        ("bevel_out", 0.15, (40, 39, 38))]},
    "white": {"label": "Valkoinen kehys · White frame", "depth": 3.0, "grain": 0.012,
              "bands": [("bevel_in", 0.7, (236, 233, 226)), ("flat", 2.6, (245, 243, 238)),
                        ("bevel_out", 0.3, (245, 243, 238))]},
    "walnut": {"label": "Pähkinä · Walnut frame", "depth": 4.5, "grain": 0.06,
               "bands": [("bevel_in", 1.0, (80, 56, 40)), ("flat", 3.2, (106, 74, 52)),
                         ("bevel_out", 0.6, (106, 74, 52))]},
}

# how bright each side of a band is, lit from the upper left (top, left, bottom, right)
SIDE_LIGHT = {
    "flat": (1.03, 1.0, 0.96, 0.98),
    "bevel_out": (1.14, 1.07, 0.80, 0.87),
    "bevel_in": (0.80, 0.86, 1.10, 1.04),
    "gap": (0.55, 0.68, 1.0, 0.9),
}

W, H = 3000, 2000  # finished image
K = 2  # drawn at twice the size, then scaled down, for smooth edges
S = 13 * K  # px per cm while drawing
FLOOR_BAND = 170 * K  # the strip of floor below the wall
WALL_BASE = H * K - FLOOR_BAND
SHADOW = (66, 54, 46)

rng = np.random.default_rng(7)


def cm(v: float) -> float:
    return v * S


def at(x_cm: float, h_cm: float, forward: float = 0) -> tuple[float, float]:
    """A point x cm from the left and h cm up, on something standing `forward`
    finished-image px in front of the wall (its feet sit that far down the floor)."""
    return x_cm * S, WALL_BASE + forward * K - h_cm * S


def shade(color, f):
    return tuple(max(0, min(255, round(c * f))) for c in color)


def noise_texture(w: int, h: int, along_x: bool, stretch: int = 70) -> np.ndarray:
    """Zero-centred streaky noise, for wood grain and linen."""
    if along_x:
        small = rng.normal(0, 1, (max(2, h // 2), max(2, w // stretch)))
    else:
        small = rng.normal(0, 1, (max(2, h // stretch), max(2, w // 2)))
    img = Image.fromarray(small.astype(np.float32), "F").resize((w, h), Image.BILINEAR)
    a = np.asarray(img)
    return a / (a.std() or 1)


def textured(w: int, h: int, color, strength: float, along_x: bool,
             gradient: tuple[float, float] = (1.0, 1.0)) -> Image.Image:
    """A block of colour with grain and a left-to-right brightness gradient."""
    w, h = max(1, int(w)), max(1, int(h))
    a = np.empty((h, w, 3), np.float32)
    a[:] = color
    g = np.linspace(gradient[0], gradient[1], w, dtype=np.float32)[None, :, None]
    a *= g
    if strength:
        a *= 1 + strength * noise_texture(w, h, along_x)[:, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def paste_shape(img: Image.Image, polygon, tex_fn, ellipse=False) -> None:
    """Fill a polygon (or ellipse box) with the texture tex_fn(w, h) makes."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(math.ceil(max(xs))), int(math.ceil(max(ys)))
    w, h = x1 - x0 + 1, y1 - y0 + 1
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    local = [(x - x0, y - y0) for x, y in polygon]
    if ellipse:
        md.ellipse((local[0][0], local[0][1], local[1][0], local[1][1]), fill=255)
    else:
        md.polygon(local, fill=255)
    img.paste(tex_fn(w, h), (x0, y0), mask)


def soft_shadow(img: Image.Image, draw_fn, blur_cm: float, alpha: int, color=SHADOW) -> None:
    """Draw shapes with draw_fn onto a mask, blur it, and darken the image through it."""
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    # shapes drawn without a colour are filled in full strength (ImageDraw's
    # default ink on a greyscale image is black, which would draw nothing)
    d.ink, d.fill = 255, True
    draw_fn(d)
    bbox = mask.getbbox()
    if not bbox:
        return
    pad = int(cm(blur_cm) * 3) + 2
    box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
           min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad))
    region = mask.crop(box).filter(ImageFilter.GaussianBlur(cm(blur_cm)))
    region = region.point(lambda v: v * alpha // 255)
    img.paste(Image.new("RGB", region.size, color), box[:2], region)


def leaf(cx, cy, length, width, angle):
    """A pointed leaf outline centred on (cx, cy)."""
    pts = []
    ca, sa = math.cos(angle), math.sin(angle)
    for i in range(18):
        t = 2 * math.pi * i / 18
        x = length / 2 * math.cos(t)
        y = width / 2 * math.sin(t) * (abs(math.cos(t)) ** 0.25 if abs(math.cos(t)) > 0.9 else 1)
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


def bezier(p0, p1, p2, n=30):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (i / n for i in range(n + 1))]


# ------------------------------------------------------------------ the room

def draw_wall_and_floor(img: Image.Image) -> None:
    w, h = img.size
    # warm white wall, lit from a window on the left
    wall = np.empty((WALL_BASE, w, 3), np.float32)
    wall[:] = (236, 231, 223)
    wall *= np.linspace(1.035, 0.94, w, dtype=np.float32)[None, :, None]
    wall *= np.linspace(0.975, 1.0, WALL_BASE, dtype=np.float32)[:, None, None]
    wall += rng.normal(0, 1.1, (WALL_BASE, w, 1)).astype(np.float32)
    img.paste(Image.fromarray(np.clip(wall, 0, 255).astype(np.uint8), "RGB"), (0, 0))

    # light oak boards running along the wall, wider as they come nearer
    rows = 6
    edges = [WALL_BASE + FLOOR_BAND * (i / rows) ** 1.45 for i in range(rows + 1)]
    for i in range(rows):
        y0, y1 = int(edges[i]), int(edges[i + 1]) + 1
        tone = 1 + rng.normal(0, 0.025)
        tex = textured(w, y1 - y0, shade((210, 182, 145), tone), 0.035, True, (1.04, 0.93))
        img.paste(tex, (0, y0))
        d = ImageDraw.Draw(img)
        d.line((0, y0, w, y0), fill=(150, 120, 86), width=max(1, int(1.2 * K * (0.6 + i * 0.15))))
        x = rng.uniform(0, 300) * K
        while x < w:
            d.line((x, y0, x, y1), fill=(160, 130, 95), width=K)
            x += rng.uniform(900, 1500) * K

    # where wall meets floor, a soft shadow on the boards
    soft_shadow(img, lambda d: d.rectangle((0, WALL_BASE, w, WALL_BASE + 6 * K)), 0.8, 90)

    # painted skirting board
    top = WALL_BASE - cm(8)
    img.paste(textured(w, cm(8), (242, 239, 233), 0.004, True, (1.02, 0.95)), (0, int(top)))
    d = ImageDraw.Draw(img)
    d.rectangle((0, top, w, top + cm(0.5)), fill=(248, 246, 241))
    soft_shadow(img, lambda d: d.rectangle((0, top - 2, w, top)), 0.15, 70)


def draw_sideboard(img: Image.Image) -> float:
    """A low oak sideboard on tapered legs. Returns y of its top surface."""
    fwd = 45
    x0, x1 = 55, 175
    oak = (214, 184, 143)

    # its shadow on the wall behind, and underneath it
    soft_shadow(img, lambda d: d.rectangle((*at(x0 + 4, 60, fwd - 25), *at(x1 + 5, 14, fwd))), 3.5, 70)
    soft_shadow(img, lambda d: d.rectangle((*at(x0 + 2, 17, fwd), *at(x1 - 1, -0.5, fwd))), 2.0, 120)

    # legs, splayed slightly
    for lx, out in ((x0 + 7, -1.3), (x1 - 7, 1.3)):
        leg = [at(lx - 1.6, 16, fwd), at(lx + 1.6, 16, fwd),
               at(lx + 1.1 + out, 0, fwd), at(lx - 1.1 + out, 0, fwd)]
        paste_shape(img, leg, lambda w, h: textured(w, h, shade(oak, 0.92), 0.05, False, (1.08, 0.82)))
        soft_shadow(img, lambda d, lx=lx, out=out: d.ellipse((*at(lx - 2 + out, 0.4, fwd), *at(lx + 3.5 + out, -0.6, fwd))), 0.4, 140)

    # body: three doors with fine gaps, a top board and a sliver of the top surface
    paste_shape(img, [at(x0, 62, fwd), at(x1, 62, fwd), at(x1, 16, fwd), at(x0, 16, fwd)],
                lambda w, h: textured(w, h, oak, 0.025, False, (1.06, 0.93)))
    d = ImageDraw.Draw(img)
    for gx in (x0 + 40, x0 + 80):
        d.rectangle((*at(gx - 0.18, 59.8, fwd), *at(gx + 0.18, 17.2, fwd)), fill=(126, 98, 70))
    d.rectangle((*at(x0, 17.2, fwd), *at(x1, 16, fwd)), fill=shade(oak, 0.74))
    paste_shape(img, [at(x0, 62, fwd), at(x1, 62, fwd), at(x1, 59.8, fwd), at(x0, 59.8, fwd)],
                lambda w, h: textured(w, h, shade(oak, 1.06), 0.05, True, (1.06, 0.94)))
    d.rectangle((*at(x0, 59.95, fwd), *at(x1, 59.8, fwd)), fill=shade(oak, 0.78))
    paste_shape(img, [at(x0 + 0.6, 63.4, fwd), at(x1 - 0.6, 63.4, fwd), at(x1, 62, fwd), at(x0, 62, fwd)],
                lambda w, h: textured(w, h, shade(oak, 1.13), 0.04, True, (1.05, 0.95)))
    # small round knobs
    for kx in (x0 + 20, x0 + 60, x0 + 100):
        cx, cy = at(kx, 50, fwd)
        r = cm(1.2)
        soft_shadow(img, lambda d, cx=cx, cy=cy: d.ellipse((cx - r + cm(0.3), cy - r + cm(0.4), cx + r + cm(0.3), cy + r + cm(0.4))), 0.25, 120)
        d = ImageDraw.Draw(img)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=shade(oak, 0.86))
        d.ellipse((cx - r * 0.7, cy - r * 0.75, cx + r * 0.3, cy + r * 0.2), fill=shade(oak, 1.02))
    return at(0, 62.7, fwd)[1]


def draw_vase_and_branches(img: Image.Image, top_y: float) -> None:
    cx = cm(80)

    def pt(x_off_cm, h_cm):
        return cx + cm(x_off_cm), top_y - cm(h_cm)

    # eucalyptus branches, drawn first so the vase sits in front of their ends
    stems = [((-13, 30), (-24, 38)), ((-3, 36), (1, 47)), ((7, 20), (8, 31))]
    stem_col = (98, 84, 70)
    leaf_cols = [(143, 157, 146), (126, 141, 131), (162, 172, 160), (112, 126, 117)]
    for (mx, mh), (ex, eh) in stems:
        pts = bezier(pt(0, 24), pt(mx, 24 + mh), pt(ex, 24 + eh))
        soft_shadow(img, lambda d, pts=pts: d.line([(x + cm(2.2), y + cm(1.5)) for x, y in pts], fill=255, width=int(cm(0.4))), 0.5, 45)
        d = ImageDraw.Draw(img)
        d.line(pts, fill=stem_col, width=int(cm(0.3)), joint="curve")
        for i in range(6, len(pts), 3):
            (px, py), (qx, qy) = pts[i - 1], pts[i]
            ang = math.atan2(qy - py, qx - px)
            for side in (-1, 1):
                if rng.random() < 0.15:
                    continue
                a = ang + side * rng.uniform(0.7, 1.2)
                L = cm(rng.uniform(2.2, 2.9))
                lx = qx + math.cos(a) * L * 0.55
                ly = qy + math.sin(a) * L * 0.55
                col = leaf_cols[rng.integers(len(leaf_cols))]
                soft_shadow(img, lambda d, lx=lx, ly=ly, a=a, L=L: d.polygon(leaf(lx + cm(2), ly + cm(1.4), L, L * 0.72, a)), 0.4, 35)
                ImageDraw.Draw(img).polygon(leaf(lx, ly, L, L * 0.72, a), fill=col)

    # a round-bellied stoneware vase
    prof_h = [0, 1.5, 5, 9, 13, 16.5, 19, 23.5, 25.4, 26]
    prof_r = [5.4, 7.0, 8.2, 8.0, 6.3, 3.6, 2.2, 1.9, 2.3, 2.3]
    hs = np.linspace(0, 26, 400)
    rs = np.interp(hs, prof_h, prof_r)
    k = 41  # smooth the corners out of the straight-line profile
    padded = np.concatenate([np.full(k, rs[0]), rs, np.full(k, rs[-1])])
    rs = np.convolve(padded, np.ones(k) / k, "same")[k:-k]
    outline = [pt(r, h) for h, r in zip(hs, rs)] + [pt(-r, h) for h, r in zip(hs[::-1], rs[::-1])]
    soft_shadow(img, lambda d: d.polygon([(x + cm(3), y + cm(1)) for x, y in outline]), 1.5, 55)
    soft_shadow(img, lambda d: d.ellipse((*pt(-6, 0.8), *pt(9, -0.8))), 0.5, 120)
    paste_shape(img, outline, lambda w, h: textured(w, h, (162, 151, 138), 0.02, False, (1.16, 0.72)))
    d = ImageDraw.Draw(img)
    d.ellipse((*pt(-2.3, 26.5), *pt(2.3, 25.5)), fill=(92, 84, 76))


def draw_books(img: Image.Image, top_y: float) -> None:
    def box(x0, x1, h0, h1):
        return [(cm(x0), top_y - cm(h1)), (cm(x1), top_y - cm(h1)),
                (cm(x1), top_y - cm(h0)), (cm(x0), top_y - cm(h0))]

    soft_shadow(img, lambda d: d.rectangle((cm(146), top_y - cm(12), cm(172), top_y)), 1.6, 60)
    for x0, x1, h0, h1, col in ((143, 170, 0, 3.2, (148, 158, 140)), (145.5, 167, 3.2, 5.8, (199, 174, 143))):
        paste_shape(img, box(x0, x1, h0, h1), lambda w, h, col=col: textured(w, h, col, 0.015, True, (1.08, 0.9)))
        d = ImageDraw.Draw(img)
        for f in (0.28, 0.72):
            yy = top_y - cm(h0 + (h1 - h0) * f)
            d.line((cm(x0 + 0.4), yy, cm(x1 - 0.4), yy), fill=shade(col, 0.88), width=K)
    # a small black stoneware sphere
    cx, cy, r = cm(157), top_y - cm(5.8 + 3.5), cm(3.5)
    soft_shadow(img, lambda d: d.ellipse((cx - r * 0.7, cy + r * 0.8, cx + r * 1.2, cy + r * 1.1)), 0.4, 140)
    paste_shape(img, [(cx - r, cy - r), (cx + r, cy + r)],
                lambda w, h: textured(w, h, (56, 53, 50), 0.02, False, (1.25, 0.7)), ellipse=True)
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r * 0.55, cy - r * 0.7, cx - r * 0.1, cy - r * 0.35), fill=(84, 80, 76))


def draw_lamp(img: Image.Image) -> None:
    fwd = 95
    cx = 24
    black = (40, 39, 38)
    soft_shadow(img, lambda d: d.rectangle((*at(cx + 7, 112, fwd - 60), *at(cx + 8.5, 6, fwd - 60))), 1.6, 45)
    soft_shadow(img, lambda d: d.polygon([at(cx - 13 + 9, 140, fwd - 60), at(cx + 13 + 9, 140, fwd - 60),
                                          at(cx + 16 + 9, 113, fwd - 60), at(cx - 16 + 9, 113, fwd - 60)]), 3.0, 40)
    soft_shadow(img, lambda d: d.ellipse((*at(cx - 12, 1.5, fwd), *at(cx + 16, -2.2, fwd))), 0.8, 130)
    paste_shape(img, [at(cx - 0.55, 114, fwd), at(cx + 0.55, 114, fwd), at(cx + 0.55, 2, fwd), at(cx - 0.55, 2, fwd)],
                lambda w, h: textured(w, h, black, 0, False, (1.5, 0.8)))
    paste_shape(img, [at(cx - 12, 2.6, fwd), at(cx + 12, -1.6, fwd)],
                lambda w, h: textured(w, h, black, 0, False, (1.4, 0.8)), ellipse=True)
    # linen drum shade
    shade_pts = [at(cx - 15, 139, fwd), at(cx + 15, 139, fwd), at(cx + 18, 113, fwd), at(cx - 18, 113, fwd)]
    paste_shape(img, shade_pts, lambda w, h: textured(w, h, (229, 221, 206), 0.012, False, (1.06, 0.84)))
    d = ImageDraw.Draw(img)
    d.rectangle((*at(cx - 18, 114, fwd), *at(cx + 18, 113, fwd)), fill=(206, 197, 181))
    d.rectangle((*at(cx - 15, 139, fwd), *at(cx + 15, 138.4, fwd)), fill=(214, 206, 191))


def draw_olive_tree(img: Image.Image) -> None:
    fwd = 125
    cx = 211
    # matte ceramic planter, slightly tapered
    soft_shadow(img, lambda d: d.polygon([at(cx - 15, 34, fwd - 90), at(cx + 26, 34, fwd - 90),
                                          at(cx + 24, 0, fwd - 90), at(cx - 13, 0, fwd - 90)]), 3.0, 50)
    soft_shadow(img, lambda d: d.ellipse((*at(cx - 18, 1.5, fwd), *at(cx + 26, -3, fwd))), 1.0, 140)
    pot = [at(cx - 18, 36, fwd), at(cx + 18, 36, fwd), at(cx + 15, 0, fwd), at(cx - 15, 0, fwd)]
    paste_shape(img, pot, lambda w, h: textured(w, h, (214, 208, 199), 0.008, True, (1.1, 0.74)))
    paste_shape(img, [at(cx - 18, 37, fwd), at(cx + 18, 37, fwd), at(cx + 18, 35.8, fwd), at(cx - 18, 35.8, fwd)],
                lambda w, h: textured(w, h, (226, 221, 213), 0, True, (1.08, 0.78)))
    paste_shape(img, [at(cx - 16.5, 37.6, fwd), at(cx + 16.5, 37.6, fwd), at(cx + 16.5, 37, fwd), at(cx - 16.5, 37, fwd)],
                lambda w, h: textured(w, h, (88, 72, 60), 0, True))

    # trunk and branches
    trunk = bezier(at(cx, 37.3, fwd), at(cx - 6, 70, fwd), at(cx + 1, 100, fwd))
    branches = [
        bezier(at(cx + 1, 100, fwd), at(cx - 8, 112, fwd), at(cx - 22, 120, fwd)),
        bezier(at(cx + 1, 100, fwd), at(cx - 4, 122, fwd), at(cx - 10, 140, fwd)),
        bezier(at(cx + 1, 100, fwd), at(cx + 6, 120, fwd), at(cx + 12, 146, fwd)),
        bezier(at(cx + 1, 100, fwd), at(cx + 12, 108, fwd), at(cx + 26, 116, fwd)),
        bezier(at(cx - 3, 82, fwd), at(cx - 10, 88, fwd), at(cx - 18, 96, fwd)),
    ]
    bark = (112, 100, 88)
    leaves = []
    cols_dark = [(92, 104, 78), (106, 117, 90), (121, 131, 102)]
    cols_light = [(150, 158, 136), (168, 173, 156), (138, 147, 122)]
    for br in branches:
        for t in np.linspace(0.25, 1, 70):
            i = int(t * (len(br) - 1))
            bx, by = br[i]
            for _ in range(3):
                lx = bx + rng.normal(0, cm(5.5))
                ly = by + rng.normal(0, cm(4.5))
                a = rng.uniform(0, math.pi)
                L = cm(rng.uniform(4.8, 6.6))
                light = rng.random() < 0.32
                col = (cols_light if light else cols_dark)[rng.integers(3)]
                leaves.append((light, lx, ly, a, L, col))
    # shadow of the whole tree on the wall
    def tree_shadow(d):
        dx, dy = cm(13), cm(-2)
        d.line([(x + dx, y + dy) for x, y in trunk], fill=255, width=int(cm(2.4)))
        for br in branches:
            d.line([(x + dx, y + dy) for x, y in br], fill=255, width=int(cm(1.2)))
        for _, lx, ly, a, L, _ in leaves:
            d.polygon(leaf(lx + dx, ly + dy, L, L * 0.24, a))
    soft_shadow(img, tree_shadow, 1.8, 50)

    d = ImageDraw.Draw(img)
    d.line(trunk, fill=bark, width=int(cm(2.4)), joint="curve")
    d.line([(x - cm(0.5), y) for x, y in trunk], fill=(140, 128, 114), width=int(cm(0.7)))
    for br in branches:
        d.line(br, fill=bark, width=int(cm(1.0)), joint="curve")
    leaves.sort(key=lambda lf: lf[0])  # dark leaves behind, silvery ones in front
    for _, lx, ly, a, L, col in leaves:
        d.polygon(leaf(lx, ly, L, L * 0.24, a), fill=col)


# ------------------------------------------------------------- the painting

def load_painting() -> Image.Image:
    with Image.open(PAINTING) as im:
        im = to_srgb(ImageOps.exif_transpose(im))
    h = round(cm(PAINTING_H_CM))
    w = round(h * im.width / im.height)
    return im.resize((w, h), Image.LANCZOS)


def hang(img: Image.Image, painting: Image.Image, frame: dict) -> None:
    cx, cy = at(*PAINTING_CENTRE)
    pw, ph = painting.size
    inner = [cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2]
    outer_w = sum(b[1] for b in frame["bands"])
    ox0, oy0, ox1, oy1 = (inner[0] - cm(outer_w), inner[1] - cm(outer_w),
                          inner[2] + cm(outer_w), inner[3] + cm(outer_w))

    depth = frame["depth"]
    soft_shadow(img, lambda d: d.rectangle((ox0 + cm(depth * 0.3), oy0 + cm(depth * 0.45),
                                            ox1 + cm(depth * 0.3), oy1 + cm(depth * 0.45))),
                0.6 + depth * 0.35, 110)
    soft_shadow(img, lambda d: d.rectangle((ox0 + cm(0.15), oy0 + cm(0.3), ox1 + cm(0.25), oy1 + cm(0.4))), 0.3, 80)

    img.paste(painting, (round(inner[0]), round(inner[1])))

    x0, y0, x1, y1 = inner
    for kind, width, color in frame["bands"]:
        w = cm(width)
        X0, Y0, X1, Y1 = x0 - w, y0 - w, x1 + w, y1 + w
        sides = [
            ([(X0, Y0), (X1, Y0), (x1, y0), (x0, y0)], True),   # top
            ([(X0, Y0), (x0, y0), (x0, y1), (X0, Y1)], False),  # left
            ([(x0, y1), (x1, y1), (X1, Y1), (X0, Y1)], True),   # bottom
            ([(x1, y0), (X1, Y0), (X1, Y1), (x1, y1)], False),  # right
        ]
        for (poly, along_x), f in zip(sides, SIDE_LIGHT[kind]):
            paste_shape(img, poly, lambda w_, h_, c=shade(color, f), ax=along_x:
                        textured(w_, h_, c, frame["grain"], ax))
        x0, y0, x1, y1 = X0, Y0, X1, Y1


# ------------------------------------------------------------------ output

def render(frame_key: str, room: Image.Image, painting: Image.Image) -> Image.Image:
    img = room.copy()
    hang(img, painting, FRAMES[frame_key])
    return img


def build_room() -> Image.Image:
    img = Image.new("RGB", (W * K, H * K))
    draw_wall_and_floor(img)
    draw_lamp(img)
    top = draw_sideboard(img)
    draw_vase_and_branches(img, top)
    draw_books(img, top)
    draw_olive_tree(img)
    return img


def finish(img: Image.Image) -> Image.Image:
    img = img.resize((W, H), Image.LANCZOS)
    # a gentle vignette and a little grain, like a photograph
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a = np.asarray(img, np.float32) * (1 - 0.06 * np.clip(r - 0.5, 0, 1) ** 1.5)[:, :, None]
    a += rng.normal(0, 1.4, (H, W, 1))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def overview(images: dict[str, Image.Image]) -> Image.Image:
    """Close-ups of every frame side by side, plus the whole room."""
    crop = (round(45 * 13), round(H - 170 - 136 * 13), round(185 * 13), round(H - 170 - 36 * 13))
    tw = 900
    th = round(tw * (crop[3] - crop[1]) / (crop[2] - crop[0]))
    gap, label_h = 40, 80
    cells = [(k, images[k].crop(crop)) for k in FRAMES] + [("room", images["oak"])]
    sheet = Image.new("RGB", (3 * tw + 4 * gap, 2 * (th + label_h) + 3 * gap), (27, 20, 26))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(str(FONT), 30)
    f.set_variation_by_axes([400])
    for i, (key, im) in enumerate(cells):
        col, row = i % 3, i // 3
        x = gap + col * (tw + gap)
        y = gap + row * (th + label_h + gap)
        sheet.paste(ImageOps.fit(im, (tw, th), Image.LANCZOS), (x, y))
        label = FRAMES[key]["label"] if key in FRAMES else "Koko huone · Whole room"
        d.text((x, y + th + 22), label, font=f, fill=(201, 194, 198))
    return sheet


def main() -> None:
    painting = load_painting()
    room = build_room()
    images = {}
    for key in FRAMES:
        images[key] = finish(render(key, room, painting))
        name = f"{PAINTING_SLUG}-room-{key}.jpg"
        images[key].save(OUT / name, quality=92)
        print(f"wrote mockups/{name}")
    overview(images).save(OUT / f"{PAINTING_SLUG}-room-overview.jpg", quality=90)
    print(f"wrote mockups/{PAINTING_SLUG}-room-overview.jpg")


if __name__ == "__main__":
    main()
