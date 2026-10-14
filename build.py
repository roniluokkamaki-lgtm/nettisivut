#!/usr/bin/env python3
"""
Build the static site from data/paintings.csv + content/*.html into docs/.

Usage:
    python build.py            build the site into docs/
    python build.py --check    build, then verify every internal link/anchor resolves
    python build.py --check-only   skip the build, just check the existing docs/

Add a painting: put its photo in originals/, add one row to data/paintings.csv,
run this script, commit, push. See README.md for the full walkthrough.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import html
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
DATA_CSV = ROOT / "data" / "paintings.csv"
CONTENT_DIR = ROOT / "content"
TEMPLATES_DIR = ROOT / "templates"
ORIGINALS_DIR = ROOT / "originals"
DOCS_DIR = ROOT / "docs"

SITE_NAME = "Roni Luokkamäki"
ARTIST_NAME = "Roni Luokkamäki"
CONTACT_EMAIL = "roni.luokkamaki@gmail.com"
AUDIO_FILENAME = "track.mp3"  # only referenced on the page if this file exists in docs/audio/

VALID_STATUSES = {"for_sale", "inquire", "sold", "not_for_sale"}
STATUS_LABEL = {
    "for_sale": "for sale",
    "inquire": "price on request",   # shown, buyable by email, but no price set yet
    "sold": "sold",
    "not_for_sale": "not for sale",
}

# Only these must be filled in for every row. Everything else (year, technique,
# theme, dimensions, description, price) may be left blank and is simply left
# off the page — so a work can go up before its details are known.
REQUIRED_FIELDS = ("id", "title", "status", "image")

IMAGE_VARIANTS = {
    # name: (longest_side_px, jpeg_quality)
    "thumb": (400, 80),
    "full": (1400, 85),
    "zoom": (2800, 85),
}


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- catalogue

def load_paintings() -> list[dict]:
    if not DATA_CSV.exists():
        raise BuildError(f"missing catalogue: {DATA_CSV}")

    with DATA_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_cols = {
            "id", "title", "year", "technique", "theme",
            "width_cm", "height_cm", "price_eur", "status",
            "description", "image",
        }
        missing_cols = required_cols - set(reader.fieldnames or [])
        if missing_cols:
            raise BuildError(f"paintings.csv is missing columns: {sorted(missing_cols)}")
        rows = list(reader)

    if not rows:
        raise BuildError("paintings.csv has no rows")

    seen_ids: set[str] = set()
    errors: list[str] = []
    paintings = []

    for i, row in enumerate(rows, start=2):  # row 1 is the header
        where = f"row {i} (id={row.get('id','?')!r})"

        for field in REQUIRED_FIELDS:
            if not (row.get(field) or "").strip():
                errors.append(f"{where}: '{field}' is empty")

        pid = (row.get("id") or "").strip()
        if pid:
            if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", pid):
                errors.append(f"{where}: id {pid!r} should be a lowercase-hyphen slug, e.g. 'red-field-2023'")
            if pid in seen_ids:
                errors.append(f"{where}: duplicate id {pid!r}")
            seen_ids.add(pid)

        status = (row.get("status") or "").strip()
        if status and status not in VALID_STATUSES:
            errors.append(f"{where}: status {status!r} must be one of {sorted(VALID_STATUSES)}")

        price_raw = (row.get("price_eur") or "").strip()
        price = None
        if status == "for_sale":
            if not price_raw:
                errors.append(f"{where}: status is 'for_sale' but price_eur is empty")
            else:
                try:
                    price = float(price_raw)
                    if price <= 0:
                        errors.append(f"{where}: price_eur must be positive")
                except ValueError:
                    errors.append(f"{where}: price_eur {price_raw!r} is not a number")
        elif price_raw:
            errors.append(f"{where}: status is {status!r} but price_eur is set ({price_raw!r}) — leave it blank")

        # year is optional; if given it must be a sane integer
        year = None
        year_raw = (row.get("year") or "").strip()
        if year_raw:
            try:
                year = int(year_raw)
                if not (1900 <= year <= 2100):
                    errors.append(f"{where}: year {year} looks wrong")
            except ValueError:
                errors.append(f"{where}: year {year_raw!r} is not an integer")

        # dimensions are optional, but must come as a pair if given at all
        width_cm = height_cm = None
        w_raw = (row.get("width_cm") or "").strip()
        h_raw = (row.get("height_cm") or "").strip()
        if bool(w_raw) != bool(h_raw):
            errors.append(f"{where}: give both width_cm and height_cm, or neither")
        elif w_raw and h_raw:
            try:
                width_cm, height_cm = int(w_raw), int(h_raw)
                if width_cm <= 0 or height_cm <= 0:
                    errors.append(f"{where}: width_cm/height_cm must be positive")
            except ValueError:
                errors.append(f"{where}: width_cm/height_cm must be whole numbers")

        image_name = (row.get("image") or "").strip()
        image_path = ORIGINALS_DIR / image_name if image_name else None
        if image_name and not (image_path and image_path.exists()):
            errors.append(f"{where}: image {image_name!r} not found in originals/")

        if errors and errors[-1].startswith(where):
            # still build the record where possible so later checks (e.g. image
            # resize) don't crash on None, but the run will fail at the end.
            pass

        technique = (row.get("technique") or "").strip()
        # real Unicode, not HTML entities, so autoescaping leaves it alone
        size = f"{width_cm}×{height_cm} cm" if width_cm and height_cm else ""
        # the detail line under a title, built from whatever is actually known
        meta = " · ".join(bit for bit in (str(year) if year else "", technique, size) if bit)

        paintings.append({
            "id": pid,
            "title": (row.get("title") or "").strip(),
            "year": year,
            "technique": technique,
            "theme": (row.get("theme") or "").strip(),
            "width_cm": width_cm,
            "height_cm": height_cm,
            "size_label": size,
            "meta": meta,
            "price_eur": price,
            "status": status,
            "status_label": STATUS_LABEL.get(status, status),
            "description": (row.get("description") or "").strip(),
            "image": image_name,
            "image_path": image_path,
        })

    if errors:
        msg = "paintings.csv has problems:\n" + "\n".join(f"  - {e}" for e in errors)
        raise BuildError(msg)

    # newest first; works with no year yet sort to the end, then by title
    paintings.sort(key=lambda p: (0 if p["year"] else 1, -(p["year"] or 0), p["title"]))
    return paintings


# ------------------------------------------------------------------ images

def resize_variant(src: Path, dest: Path, longest_side: int, quality: int) -> tuple[int, int]:
    """Create dest from src if missing or stale. Returns the variant's (w, h)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        with Image.open(dest) as im:
            return im.size

    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # respect camera rotation, then strip EXIF
        im = im.convert("RGB")
        w, h = im.size
        scale = longest_side / max(w, h)
        if scale < 1:
            im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        im.save(dest, "JPEG", quality=quality, optimize=True)
        return im.size


def build_images(paintings: list[dict]) -> None:
    out_dir = DOCS_DIR / "img" / "paintings"
    for p in paintings:
        for variant, (longest_side, quality) in IMAGE_VARIANTS.items():
            dest = out_dir / f"{p['id']}-{variant}.jpg"
            w, h = resize_variant(p["image_path"], dest, longest_side, quality)
            p[f"{variant}_w"], p[f"{variant}_h"] = w, h

    # profile picture: hand-prepared, just copied through if present
    profile_src = ORIGINALS_DIR / "profile.jpg"
    profile_dest = DOCS_DIR / "img" / "profile.jpg"
    if profile_src.exists():
        if (not profile_dest.exists()) or profile_src.stat().st_mtime > profile_dest.stat().st_mtime:
            shutil.copyfile(profile_src, profile_dest)
    elif not profile_dest.exists():
        print("warning: originals/profile.jpg not found — front page image will 404", file=sys.stderr)


# ------------------------------------------------------------------- mailto

def mailto_for(p: dict) -> str:
    """Prefilled inquiry email. Only mentions details that are actually known."""
    subject = f"Painting inquiry: {p['title']} ({p['id']})"
    bits = [b for b in (
        str(p["year"]) if p["year"] else "",
        p["technique"],
        f"{p['width_cm']}x{p['height_cm']} cm" if p["width_cm"] and p["height_cm"] else "",
    ) if b]
    detail = f" ({', '.join(bits)})" if bits else ""
    body = f'Hi,\n\nI\'m interested in "{p["title"]}"{detail}.\n\n'
    q = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    return f"mailto:{CONTACT_EMAIL}?{q}"


# --------------------------------------------------------------------- html

def read_content(name: str) -> str:
    path = CONTENT_DIR / name
    if not path.exists():
        raise BuildError(f"missing content fragment: {path}")
    return path.read_text(encoding="utf-8")


def render_site(paintings: list[dict]) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        # Autoescape everywhere: CSV-sourced fields (title, technique, ...) and the
        # mailto href need HTML/attribute escaping. The three hand-written content
        # fragments are raw HTML on purpose and opt out explicitly with `| safe`.
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    today = datetime.date.today()
    audio_present = (DOCS_DIR / "audio" / AUDIO_FILENAME).exists()
    base_ctx = {
        "site_name": SITE_NAME,
        "artist_name": ARTIST_NAME,
        "contact_email": CONTACT_EMAIL,
        "build_date": today.isoformat(),
        "build_year": today.year,
        "audio_file": AUDIO_FILENAME if audio_present else None,
        "root": "",
    }
    if not audio_present:
        print("note: docs/audio/track.mp3 not found — audio player omitted for now", file=sys.stderr)

    for p in paintings:
        p["buy_href"] = mailto_for(p) if p["status"] in ("for_sale", "inquire") else None

    pages = [
        ("index.html", "index.html", {
            "page_id": "home",
            "content": read_content("home.html"),
            "newest": paintings[:3],
        }),
        ("about.html", "page.html", {
            "page_id": "about",
            "page_title": "About",
            "page_description": f"About {ARTIST_NAME}.",
            "content": read_content("about.html"),
        }),
        ("buying.html", "page.html", {
            "page_id": "buying",
            "page_title": "Buying",
            "page_description": "How to buy a painting.",
            "content": read_content("buying.html"),
        }),
        ("gallery.html", "gallery.html", {
            "page_id": "gallery",
            "page_title": "Gallery",
            "page_description": f"All paintings by {ARTIST_NAME}.",
            "paintings": paintings,
        }),
        ("404.html", "404.html", {
            "page_id": None,
            "page_title": "Not found",
            "page_description": "Page not found.",
        }),
    ]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for out_name, template_name, ctx in pages:
        tmpl = env.get_template(template_name)
        rendered = tmpl.render(**base_ctx, **ctx)
        (DOCS_DIR / out_name).write_text(rendered, encoding="utf-8")
        print(f"wrote docs/{out_name}")

    (DOCS_DIR / ".nojekyll").touch()


# ------------------------------------------------------------------- check

LINK_RE = re.compile(r'(?:href|src)="([^"]+)"')
ID_RE = re.compile(r'id="([^"]+)"')


def check_links() -> list[str]:
    problems = []
    html_files = sorted(DOCS_DIR.glob("*.html"))
    id_cache: dict[Path, set[str]] = {}

    def ids_in(path: Path) -> set[str]:
        if path not in id_cache:
            id_cache[path] = set(ID_RE.findall(path.read_text(encoding="utf-8"))) if path.exists() else set()
        return id_cache[path]

    for page in html_files:
        text = page.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("mailto:", "http://", "https://", "data:", "tel:")):
                continue
            path_part, _, fragment = target.partition("#")
            if path_part in ("", "."):
                resolved = page
            else:
                resolved = (DOCS_DIR / path_part).resolve()
            if not str(resolved).startswith(str(DOCS_DIR.resolve())):
                problems.append(f"{page.name}: link escapes docs/: {target}")
                continue
            if not resolved.exists():
                problems.append(f"{page.name}: broken link target: {target}")
                continue
            if fragment and resolved.suffix == ".html" and fragment not in ids_in(resolved):
                problems.append(f"{page.name}: missing anchor #{fragment} in {resolved.name}")

    return problems


# -------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="build, then verify internal links")
    ap.add_argument("--check-only", action="store_true", help="skip the build, just check docs/")
    args = ap.parse_args()

    if not args.check_only:
        try:
            paintings = load_paintings()
            build_images(paintings)
            render_site(paintings)
        except BuildError as e:
            print(f"\nBUILD FAILED:\n{e}\n", file=sys.stderr)
            return 1
        print(f"\nBuilt {len(paintings)} paintings into docs/\n")

    if args.check or args.check_only:
        problems = check_links()
        if problems:
            print("LINK CHECK FAILED:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("Link check passed: every internal href/src and #anchor resolves.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
