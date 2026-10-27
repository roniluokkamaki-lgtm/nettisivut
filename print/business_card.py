"""Draw the front of the business card as a print-ready PNG.

    py -3 print/business_card.py

The contact lines come from print/card_contacts.txt, which is never committed;
neither are the card images it writes.

The file is 88 x 58 mm at 600 dpi: a standard 85 x 55 mm card plus 1.5 mm of
bleed on every side, which the printer trims off. Text and the QR code stay at
least 3 mm inside the trim line. A second copy with the trim and safe lines
drawn on is written beside it, for checking only; never send that one to print.

Colours and font are the website's (docs/css/style.css). The QR code points at
the /card address, which forwards to the home page and is counted separately
on the Visitors page.
"""

from pathlib import Path

import segno
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
FONT = ROOT / "docs" / "fonts" / "inter-latin-ext.woff2"
FONT_LATIN = ROOT / "docs" / "fonts" / "inter-latin.woff2"

NAME = "Roni Luokkamäki"
TITLE = "Kuvataiteilija · Visual artist"
# One line each, top to bottom. Kept in a file git ignores, because the card
# carries a phone number and this repository is public.
CONTACTS_FILE = Path(__file__).resolve().parent / "card_contacts.txt"
CONTACTS: list[str] = []
QR_URL = "https://www.roniluokkamaki.com/card"

# the site's palette
BG = "#1b141a"
FG = "#c9c2c6"
ACCENT = "#a1afa7"
ACCENT_HI = "#cfe6d6"

DPI = 600
MM = DPI / 25.4
W, H = round(88 * MM), round(58 * MM)
BLEED = 1.5 * MM
MARGIN = BLEED + 5 * MM  # from the file edge to the text; 5 mm inside the trim


def font(size_pt: float) -> ImageFont.FreeTypeFont:
    # inter-latin carries ASCII and ä; the latin-ext file would be needed only
    # for letters beyond that
    f = ImageFont.truetype(str(FONT_LATIN), round(size_pt / 72 * DPI))
    f.set_variation_by_axes([400])
    return f


def tracked(draw, xy, text, f, fill, tracking_em=0.0, anchor_bottom=False):
    """Draw text with letter-spacing, as the site does with CSS letter-spacing.

    Returns the width drawn. xy is the left end of the baseline.
    """
    x, y = xy
    gap = tracking_em * f.size
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill, anchor="ls")
        x += f.getlength(ch) + gap
    return x - gap - xy[0]


def draw_card(guides: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # QR code: dark modules on a light tile, since many phone cameras fail to
    # read a light-on-dark code
    qr = segno.make(QR_URL, error="m", micro=False)
    matrix = list(qr.matrix)
    quiet = 3
    n = len(matrix) + 2 * quiet
    tile = round(22 * MM)
    module = tile / n
    tx, ty = W - MARGIN - tile, H - MARGIN - tile
    d.rounded_rectangle((tx, ty, tx + tile, ty + tile), radius=round(1.2 * MM), fill=ACCENT_HI)
    for r, row in enumerate(matrix):
        for c, on in enumerate(row):
            if on:
                x0 = tx + (c + quiet) * module
                y0 = ty + (r + quiet) * module
                d.rectangle((round(x0), round(y0), round(x0 + module) - 1, round(y0 + module) - 1), fill=BG)

    # name and title, top left
    name_f = font(11.5)
    y = MARGIN + name_f.getbbox("H")[3] - name_f.getbbox("H")[1]
    tracked(d, (MARGIN, y), NAME.upper(), name_f, FG, tracking_em=0.06)
    title_f = font(7.5)
    y += round(4.2 * MM)
    tracked(d, (MARGIN, y), TITLE, title_f, ACCENT, tracking_em=0.04)

    # contact lines, bottom left, last baseline level with the QR tile's bottom
    contact_f = font(7)
    line = round(3.5 * MM)
    base = H - MARGIN
    for i, text in enumerate(reversed(CONTACTS)):
        tracked(d, (MARGIN, base - i * line), text, contact_f, FG, tracking_em=0.02)

    if guides:
        trim = (BLEED, BLEED, W - BLEED, H - BLEED)
        safe = (BLEED + 3 * MM, BLEED + 3 * MM, W - BLEED - 3 * MM, H - BLEED - 3 * MM)
        d.rectangle(trim, outline="#ff3b3b", width=3)
        d.rectangle(safe, outline="#3bb0ff", width=2)

    return img


def main() -> None:
    if not CONTACTS_FILE.exists():
        raise SystemExit(f"missing {CONTACTS_FILE.name}: write the card's contact lines in it, one per line")
    CONTACTS[:] = [x.strip() for x in CONTACTS_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
    for guides, name in ((False, "business-card-front.png"),
                         (True, "business-card-front-guides.png")):
        draw_card(guides).save(OUT / name, dpi=(DPI, DPI))
        print(f"wrote print/{name}  ({W} x {H} px, {DPI} dpi)")


if __name__ == "__main__":
    main()
