"""Draw the horse sticker as a print-ready PNG.

    py -3 print/sticker.py

The whole of Horse Painting No.01 with a QR code tucked into the empty red
ground in its lower right corner, and nothing else: no name, no address.

The sticker is 60 x 40 mm, the stock size closest to the painting's own
proportions (70 x 48 cm), plus 2 mm of bleed on every side for the printer to
trim off; about 1 mm of the painting's top and bottom edges is lost. A copy with
the trim and safe lines drawn on is written beside it, for checking only.

The QR code points at the /sticker address, which forwards to the home page
and is counted separately on the Visitors page.
"""

import sys
from pathlib import Path

import segno
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import to_srgb  # noqa: E402

OUT = Path(__file__).resolve().parent
PAINTING = ROOT / "originals" / "DSCF6013.jpg"
QR_URL = "https://www.roniluokkamaki.com/sticker"

DPI = 600
MM = DPI / 25.4
TRIM_W, TRIM_H = 60, 40
BLEED = 2 * MM
W, H = round((TRIM_W + 4) * MM), round((TRIM_H + 4) * MM)
SAFE = BLEED + 3 * MM

# the QR tile takes its colours from the painting: the pale ground behind the
# horse, and the deep shadow of the red
TILE = "#ead3bf"
MODULES = "#3d1510"


def draw_sticker(guides: bool) -> Image.Image:
    with Image.open(PAINTING) as im:
        im = to_srgb(ImageOps.exif_transpose(im))
        # cover the whole sticker including bleed; the bleed trims a sliver off
        # the painting's edges, which is what bleed is for
        img = ImageOps.fit(im, (W, H), Image.LANCZOS)
    d = ImageDraw.Draw(img)

    qr = segno.make(QR_URL, error="m", micro=False)
    matrix = list(qr.matrix)
    quiet = 2
    n = len(matrix) + 2 * quiet
    # 12 mm still scans from a normal distance and leaves the painting in charge
    tile = round(12 * MM)
    module = tile / n
    tx, ty = W - SAFE - tile, H - SAFE - tile
    d.rounded_rectangle((tx, ty, tx + tile, ty + tile), radius=round(0.8 * MM), fill=TILE)
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if on:
                x0 = tx + (c + quiet) * module
                y0 = ty + (r + quiet) * module
                d.rectangle((round(x0), round(y0), round(x0 + module) - 1, round(y0 + module) - 1), fill=MODULES)

    if guides:
        d.rectangle((BLEED, BLEED, W - BLEED, H - BLEED), outline="#ff3b3b", width=3)
        d.rectangle((SAFE, SAFE, W - SAFE, H - SAFE), outline="#3bb0ff", width=2)

    return img


def main() -> None:
    for guides, name in ((False, "sticker-horse.png"), (True, "sticker-horse-guides.png")):
        draw_sticker(guides).save(OUT / name, dpi=(DPI, DPI))
        print(f"wrote print/{name}  ({W} x {H} px, {DPI} dpi)")


if __name__ == "__main__":
    main()
