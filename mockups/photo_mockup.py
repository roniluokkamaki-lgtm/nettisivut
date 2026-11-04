"""Hang a painting in a real photograph of a Scandinavian-style room.

    py -3 mockups/photo_mockup.py

The room is a stock photo, "Modern wooden sideboard with decorative items and
lamp" by Imani Bahati, free to use under the Unsplash License:
https://unsplash.com/photos/UrQeWGobTnI
Download it into originals/stock/unsplash-UrQeWGobTnI.jpg (originals/ is not
committed).

The painting is the real photograph, untouched apart from the room's light: it
is hung at its true size over the sideboard, and the window light that falls
across the wall falls across the painting and frame too, with a shadow cast to
the lower right like the lamp's.

Scale comes from the speaker on the sideboard (a Sonos Era 100, 12 cm wide),
which also puts the sideboard at about 160 x 77 cm, an ordinary size.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from room_mockup import (FONT, FRAMES, PAINTING_SLUG, ROOT, draw_frame,  # noqa: E402
                         load_painting, to_srgb)

OUT = Path(__file__).resolve().parent
ROOM = ROOT / "originals" / "stock" / "unsplash-UrQeWGobTnI.jpg"
CREDIT = "Kuva · Photo: Imani Bahati / Unsplash"

# measured on the full-size photo (3780 x 4724 px)
PX_PER_CM = 18.7  # on the wall: the speaker is 242 px for 12 cm, a little nearer the camera
CENTRE_X = 1864  # middle of the sideboard, where its two doors meet
SIDEBOARD_TOP = 2497  # where the sideboard top meets the wall
GAP_CM = 22  # from the sideboard to the bottom of the canvas
SUN = np.array([222, 222, 220], np.float32)  # sunlit wall
SHADE = np.array([176, 175, 170], np.float32)  # wall in the shade
# the low sun from the left throws a shadow this far per cm an object stands
# off the wall, judged from the lamp's shadow
SUN_DX, SUN_DY = 1.8, 0.85  # cm right, cm down

FINAL = (1600, 2000)


def lit(img: Image.Image, box, light: np.ndarray) -> None:
    """Multiply the part of img inside box by the light map."""
    x0, y0, x1, y1 = box
    a = np.asarray(img.crop(box), np.float32) * light
    img.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB"), (x0, y0))


def render(room: Image.Image, painting: Image.Image, frame: dict) -> Image.Image:
    wall = np.asarray(room, np.float32)
    img = room.copy()

    pw, ph = painting.size
    bottom = SIDEBOARD_TOP - GAP_CM * PX_PER_CM
    inner = (CENTRE_X - pw / 2, bottom - ph, CENTRE_X + pw / 2, bottom)
    border = sum(b[1] for b in frame["bands"]) * PX_PER_CM
    outer = [round(inner[0] - border), round(inner[1] - border),
             round(inner[2] + border), round(inner[3] + border)]
    depth = frame["depth"]
    dx, dy = round(SUN_DX * depth * PX_PER_CM), round(SUN_DY * depth * PX_PER_CM)

    # cast shadow: where the sun reaches the wall, the frame blocks it, leaving
    # the wall as dark as the shade; where the wall is already in shade, nothing
    mask = Image.new("L", room.size, 0)
    ImageDraw.Draw(mask).rectangle((outer[0] + dx, outer[1] + dy, outer[2] + dx, outer[3] + dy), fill=255)
    m = np.asarray(mask.filter(ImageFilter.GaussianBlur(3 + depth * 2)), np.float32)[:, :, None] / 255
    direct = np.clip(wall - SHADE, 0, None)
    shaded = wall - m * direct
    # and a soft contact shadow all round, from the light bouncing round the room
    mask = Image.new("L", room.size, 0)
    ImageDraw.Draw(mask).rectangle((outer[0], outer[1] + 6, outer[2] + 6, outer[3] + 10), fill=255)
    m = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.5 * PX_PER_CM)), np.float32)[:, :, None] / 255
    shaded *= 1 - 0.22 * m
    img = Image.fromarray(np.clip(shaded, 0, 255).astype(np.uint8), "RGB")

    # the painting and frame, drawn flat, then lit by the light that would fall
    # on the wall a little up and to the left (they stand off the wall)
    art = img.copy()
    art.paste(painting, (round(inner[0]), round(inner[1])))
    draw_frame(art, inner, frame, PX_PER_CM)
    x0, y0, x1, y1 = outer
    sx, sy = -dx, -dy
    light = wall[y0 + sy:y1 + sy, x0 + sx:x1 + sx] / SUN
    light = np.asarray(Image.fromarray(np.clip(light * 100, 0, 255).astype(np.uint8), "RGB")
                       .filter(ImageFilter.GaussianBlur(4)), np.float32) / 100
    lit(art, (x0, y0, x1, y1), np.clip(light, 0.6, 1.06))
    img.paste(art.crop((x0, y0, x1, y1)), (x0, y0))
    return img


def overview(images: dict[str, Image.Image]) -> Image.Image:
    """Close-ups of every frame side by side, plus the whole photo."""
    k = FINAL[1] / 4724
    crop = tuple(round(v * k) for v in (1000, 1150, 2900, 2670))
    tw = 900
    th = round(tw * (crop[3] - crop[1]) / (crop[2] - crop[0]))
    gap, label_h = 40, 80
    sheet = Image.new("RGB", (3 * tw + 4 * gap, 2 * (th + label_h) + 3 * gap + 40), (27, 20, 26))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(str(FONT), 30)
    f.set_variation_by_axes([400])
    small = ImageFont.truetype(str(FONT), 22)
    cells = [(FRAMES[key]["label"], images[key].crop(crop)) for key in FRAMES]
    cells.append(("Koko kuva · Whole photo", ImageOps.pad(images["oak"], (tw, th), color=(27, 20, 26))))
    for i, (label, im) in enumerate(cells):
        col, row = i % 3, i // 3
        x = gap + col * (tw + gap)
        y = gap + row * (th + label_h + gap)
        sheet.paste(ImageOps.fit(im, (tw, th), Image.LANCZOS), (x, y))
        d.text((x, y + th + 22), label, font=f, fill=(201, 194, 198))
    d.text((gap, sheet.height - 50), CREDIT, font=small, fill=(139, 131, 137))
    return sheet


def main() -> None:
    if not ROOM.exists():
        raise SystemExit(f"missing {ROOM.relative_to(ROOT)}: download it from "
                         "https://unsplash.com/photos/UrQeWGobTnI")
    with Image.open(ROOM) as im:
        room = to_srgb(im)
    painting = load_painting(PX_PER_CM)
    images = {}
    for key, frame in FRAMES.items():
        images[key] = render(room, painting, frame).resize(FINAL, Image.LANCZOS)
        name = f"{PAINTING_SLUG}-photo-{key}.jpg"
        images[key].save(OUT / name, quality=90)
        print(f"wrote mockups/{name}")
    overview(images).save(OUT / f"{PAINTING_SLUG}-photo-overview.jpg", quality=90)
    print(f"wrote mockups/{PAINTING_SLUG}-photo-overview.jpg")


if __name__ == "__main__":
    main()
