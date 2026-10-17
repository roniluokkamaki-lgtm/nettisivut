#!/usr/bin/env python3
"""
Build the static site from the artwork database + content/*.html into docs/.

Usage:
    python build.py            build the site into docs/
    python build.py --check    build, then verify every internal link/anchor resolves
    python build.py --check-only   skip the build, just check the existing docs/

Add a painting with the admin tool (admin.bat), which can also preview and
publish. See README.md for the full walkthrough.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import shutil
import sys
import urllib.parse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageOps

import db

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
TEMPLATES_DIR = ROOT / "templates"
ORIGINALS_DIR = ROOT / "originals"
DOCS_DIR = ROOT / "docs"

SITE_NAME = "Roni Luokkamäki"
ARTIST_NAME = "Roni Luokkamäki"
CONTACT_EMAIL = "roni.luokkamaki@gmail.com"
AUDIO_FILENAME = "track.mp3"  # only referenced on the page if this file exists in docs/audio/

# Instagram handle without the "@". While this is empty the icon is left off the
# footer entirely, rather than linking somewhere wrong.
INSTAGRAM_HANDLE = ""

# Used only to build absolute hreflang URLs. Change this if the site moves to a
# custom domain (see README, "Custom domain").
SITE_URL = "https://www.roniluokkamaki.com"

VALID_STATUSES = {"for_sale", "inquire", "sold", "not_for_sale"}

# In the gallery filter, a painting counts as large when its longest side is at
# least this many centimetres. Paintings with no size entered are listed under
# "Paintings" only, not as small or large.
LARGE_PAINTING_CM = 50

# Gallery filter categories, in the order they are listed. The second value is
# the indent level: small and large sit under paintings.
FILTER_CATEGORIES = (
    ("painting", 0), ("painting-small", 1), ("painting-large", 1),
    ("drawing", 0), ("other", 0),
)

# English is the default language and lives at the root of docs/. Finnish lives
# in docs/fi/. Every user-visible string is listed here so a page is never half
# translated; the Finnish copy is written as Finnish, not translated word by word.
LANGUAGES = {
    "en": {
        "code": "en",
        "subdir": "",          # written to docs/
        "root": "",            # how a page in this language reaches docs/
        "other": "fi",
        "switch_label": "FI",
        "switch_title": "Suomeksi",
        "nav": {"home": "HOME", "gallery": "GALLERY", "about": "ABOUT", "order": "ORDER"},
        "page_titles": {
            "gallery": "Gallery", "about": "About", "order": "Order",
            "terms": "Terms of purchase", "404": "Not found",
        },
        "descriptions": {
            "home": f"Paintings and current work by {ARTIST_NAME}.",
            "gallery": f"All paintings by {ARTIST_NAME}.",
            "about": f"About {ARTIST_NAME}.",
            "order": "Payments, delivery and returns.",
            "terms": "Terms of purchase.",
            "404": "Page not found.",
        },
        "latest_work": "latest work",
        "view_gallery": "view the full gallery &rarr;",
        "status": {
            "for_sale": "for sale", "inquire": "price on request",
            "sold": "sold", "not_for_sale": "not for sale",
        },
        "btn_order": "[ Order ]",
        "btn_ask": "[ Ask about this work ]",
        "btn_view": "[ View closer ]",
        "tag_sold": "SOLD",
        "tag_nfs": "NOT FOR SALE",
        "price_on_request": "price on request",
        "contact": "contact",
        "last_updated": "last updated",
        "music_label": "background music (own track)",
        "rights": "All works and images © {year} {artist}. All rights reserved.",
        "not_found_body": "That page does not exist.",
        "back_home": "back to the front page",
        "lb": {
            "close": "Close", "prev": "Previous painting", "next": "Next painting",
            "zoom_on": "zoom: on", "zoom_off": "zoom: off", "dialog": "Painting viewer",
        },
        "filter": {
            "label": "Filter the gallery",
            "category": "Category", "years": "Years", "tags": "Tags",
            "all_category": "All works", "all_years": "All years", "all_tags": "All tags",
            "categories": {
                "painting": "Paintings", "painting-small": "Small paintings",
                "painting-large": "Large paintings", "drawing": "Drawings", "other": "Other",
            },
            "showing": "Showing {n} of {total} works",
            "none": "No works match these choices.",
            "clear": "clear filters",
        },
        "mail_subject": "Painting inquiry: {title} ({id})",
        "mail_body": "Hi,\n\nI'm interested in \"{title}\"{detail}.\n\n",
    },
    "fi": {
        "code": "fi",
        "subdir": "fi",        # written to docs/fi/
        "root": "../",
        "other": "en",
        "switch_label": "EN",
        "switch_title": "In English",
        "nav": {"home": "ETUSIVU", "gallery": "TEOKSET", "about": "TIETOA", "order": "TILAAMINEN"},
        "page_titles": {
            "gallery": "Teokset", "about": "Tietoa", "order": "Tilaaminen",
            "terms": "Kauppaehdot", "404": "Sivua ei löytynyt",
        },
        "descriptions": {
            "home": f"{ARTIST_NAME}, maalauksia ja ajankohtaisia teoksia.",
            "gallery": f"{ARTIST_NAME}, kaikki teokset.",
            "about": f"Tietoa taiteilijasta {ARTIST_NAME}.",
            "order": "Maksaminen, toimitus ja palautukset.",
            "terms": "Kauppaehdot.",
            "404": "Sivua ei löytynyt.",
        },
        "latest_work": "uusimmat teokset",
        "view_gallery": "katso kaikki teokset &rarr;",
        "status": {
            "for_sale": "myynnissä", "inquire": "hinta pyynnöstä",
            "sold": "myyty", "not_for_sale": "ei myynnissä",
        },
        "btn_order": "[ Tilaa ]",
        "btn_ask": "[ Kysy teoksesta ]",
        "btn_view": "[ Katso tarkemmin ]",
        "tag_sold": "MYYTY",
        "tag_nfs": "EI MYYNNISSÄ",
        "price_on_request": "hinta pyynnöstä",
        "contact": "yhteys",
        "last_updated": "päivitetty",
        "music_label": "taustamusiikki (oma kappale)",
        "rights": "Teokset ja kuvat © {year} {artist}. Kaikki oikeudet pidätetään.",
        "not_found_body": "Sivua ei ole olemassa.",
        "back_home": "takaisin etusivulle",
        "lb": {
            "close": "Sulje", "prev": "Edellinen teos", "next": "Seuraava teos",
            "zoom_on": "lähennys: päällä", "zoom_off": "lähennys: pois",
            "dialog": "Teoskatselin",
        },
        "filter": {
            "label": "Rajaa teoksia",
            "category": "Kategoria", "years": "Vuodet", "tags": "Tunnisteet",
            "all_category": "Kaikki teokset", "all_years": "Kaikki vuodet",
            "all_tags": "Kaikki tunnisteet",
            "categories": {
                "painting": "Maalaukset", "painting-small": "Pienet maalaukset",
                "painting-large": "Suuret maalaukset", "drawing": "Piirustukset", "other": "Muut",
            },
            "showing": "Näytetään {n}/{total} teosta",
            "none": "Yksikään teos ei vastaa valintoja.",
            "clear": "tyhjennä valinnat",
        },
        "mail_subject": "Teostiedustelu: {title} ({id})",
        "mail_body": "Hei,\n\nOlen kiinnostunut teoksesta \"{title}\"{detail}.\n\n",
    },
}

IMAGE_VARIANTS = {
    # name: (longest_side_px, jpeg_quality)
    # The grid shows three thumbnails across, about 280 CSS px each, so a
    # high-resolution screen asks for up to ~560px of real image. 800 keeps them
    # sharp without making the page heavy.
    "thumb": (800, 80),
    "full": (1400, 85),
    "zoom": (2800, 85),
}


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- catalogue

def load_paintings() -> list[dict]:
    """Works to publish, read from the artwork database.

    The selection and the privacy boundary live in db.public_works(): it returns
    only visible, non-archived works, and only columns that are safe to publish.
    Buyer and sale details are not among them and never reach this module.
    """
    if not db.DB_PATH.exists():
        raise BuildError(
            f"no artwork database at {db.DB_PATH}\n"
            "    Run the admin tool (admin.bat) to create one, or\n"
            "    py -3 migrate_csv_to_db.py to import the old spreadsheet."
        )

    db.init()  # adds any columns introduced since this database was created
    works = db.public_works()
    if not works:
        raise BuildError("no works are marked visible — nothing to publish")

    errors: list[str] = []
    paintings = []

    for w in works:
        where = f"{w['slug']!r}"
        status = w["web_status"]
        price = w["asking_price_eur"]

        if status not in VALID_STATUSES:
            errors.append(f"{where}: unknown website status {status!r}")
        if status == "for_sale" and not price:
            errors.append(f"{where}: shown as for sale but has no price")

        image_name = (w["image"] or "").strip()
        image_path = ORIGINALS_DIR / image_name if image_name else None
        if not image_name:
            errors.append(f"{where}: no photograph attached")
        elif not image_path.exists():
            errors.append(f"{where}: photograph {image_name!r} not found in originals/")

        w_cm, h_cm = w["width_cm"], w["height_cm"]
        if bool(w_cm) != bool(h_cm):
            errors.append(f"{where}: give both width and height, or neither")

        paintings.append({
            # the website's identifier is the slug: it is used in page anchors
            # and in every generated image filename
            "id": w["slug"],
            "title": w["title"],
            "title_fi": w["title_fi"],
            "year": w["year"],
            "technique": w["medium"],
            "technique_fi": w["medium_fi"],
            "theme": w["theme"],
            "category": w["category"],
            "public_tags": w["public_tags"],
            "public_tags_fi": w["public_tags_fi"],
            "width_cm": w_cm,
            "height_cm": h_cm,
            "price_eur": price if status == "for_sale" else None,
            "status": status,
            "description": w["description"],
            "description_fi": w["description_fi"],
            "image": image_name,
            "image_path": image_path,
        })

    if errors:
        raise BuildError(
            "the artwork database has problems:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    return paintings


# ------------------------------------------------------------------ images

def resize_variant(src: Path, dest: Path, longest_side: int, quality: int) -> tuple[int, int]:
    """Create dest from src if missing or stale. Returns the variant's (w, h)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        with Image.open(dest) as im:
            return im.size

    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)  # respect camera rotation, then strip EXIF
            im = im.convert("RGB")
            w, h = im.size
            scale = longest_side / max(w, h)
            if scale < 1:
                im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
            im.save(dest, "JPEG", quality=quality, optimize=True)
            return im.size
    except OSError as e:
        # a damaged or mislabelled file should name itself, not produce a traceback
        raise BuildError(
            f"could not read the photograph {src.name!r}: {e}\n"
            "    Open it to check it is a real image, then replace it in the admin tool."
        ) from None


def build_images(paintings: list[dict]) -> None:
    out_dir = DOCS_DIR / "img" / "paintings"
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = set()
    for p in paintings:
        for variant, (longest_side, quality) in IMAGE_VARIANTS.items():
            dest = out_dir / f"{p['id']}-{variant}.jpg"
            expected.add(dest.name)
            w, h = resize_variant(p["image_path"], dest, longest_side, quality)
            p[f"{variant}_w"], p[f"{variant}_h"] = w, h

    # Remove published images belonging to works that are no longer published:
    # deleted, archived, hidden, or renamed. Without this they would stay on the
    # live site at a guessable address long after the work came down.
    removed = 0
    for stale in out_dir.glob("*.jpg"):
        if stale.name not in expected:
            stale.unlink()
            removed += 1
    if removed:
        print(f"removed {removed} image(s) belonging to works no longer published")

    # profile picture: hand-prepared, just copied through if present
    profile_src = ORIGINALS_DIR / "profile.jpg"
    profile_dest = DOCS_DIR / "img" / "profile.jpg"
    if profile_src.exists():
        if (not profile_dest.exists()) or profile_src.stat().st_mtime > profile_dest.stat().st_mtime:
            shutil.copyfile(profile_src, profile_dest)
    elif not profile_dest.exists():
        print("warning: originals/profile.jpg not found — front page image will 404", file=sys.stderr)


# -------------------------------------------------------------- localisation

def localise(p: dict, L: dict) -> dict:
    """One painting as it appears in a given language.

    Finnish columns fall back to the English ones when blank, so a row that has
    only been half translated still renders correctly rather than showing gaps.
    """
    fi = L["code"] == "fi"
    title = (p["title_fi"] or p["title"]) if fi else p["title"]
    technique = (p["technique_fi"] or p["technique"]) if fi else p["technique"]
    description = (p["description_fi"] or p["description"]) if fi else p["description"]

    # real Unicode, not HTML entities, so autoescaping leaves it alone
    size = f"{p['width_cm']}×{p['height_cm']} cm" if p["width_cm"] and p["height_cm"] else ""
    meta = " · ".join(b for b in (str(p["year"]) if p["year"] else "", technique, size) if b)

    tags = split_tags((p["public_tags_fi"] or p["public_tags"]) if fi else p["public_tags"])

    out = dict(p)
    out.update({
        "categories": filter_categories(p),
        "tags": tags,
        # written into data-* attributes for the gallery filter script
        "filter_cats": " ".join(filter_categories(p)),
        "filter_tags": "|".join(tag_key(t) for t in tags),
        "title": title,
        "technique": technique,
        "description": description,
        "size_label": size,
        "meta": meta,
        "status_label": L["status"].get(p["status"], p["status"]),
    })
    out["buy_href"] = mailto_for(out, L) if p["status"] in ("for_sale", "inquire") else None
    return out


def split_tags(text: str) -> list[str]:
    """Comma-separated tags as entered in the admin tool, tidied and de-duplicated."""
    seen, out = set(), []
    for t in (text or "").split(","):
        t = " ".join(t.split())
        if t and tag_key(t) not in seen:
            seen.add(tag_key(t))
            out.append(t)
    return out


def tag_key(tag: str) -> str:
    """How tags are compared, so "Still life" and "still life" are one tag."""
    return " ".join(tag.split()).casefold()


def filter_categories(p: dict) -> list[str]:
    """The gallery filter categories a work belongs to, e.g. painting + painting-large."""
    cat = p["category"]
    if not cat:
        return []
    cats = [cat]
    if cat == "painting" and p["width_cm"] and p["height_cm"]:
        large = max(p["width_cm"], p["height_cm"]) >= LARGE_PAINTING_CM
        cats.append("painting-large" if large else "painting-small")
    return cats


def gallery_filters(local: list[dict], L: dict) -> dict:
    """Options for the gallery's three filter menus, each with how many works it holds.

    Only options that at least one work has are listed, and a menu with no
    options is left out, so the filter never offers a choice that shows nothing.
    """
    F = L["filter"]
    indent = " " * 4
    cat_counts: dict[str, int] = {}
    year_counts: dict[int, int] = {}
    tag_counts: dict[str, list] = {}  # key -> [label, count]
    for p in local:
        for c in p["categories"]:
            cat_counts[c] = cat_counts.get(c, 0) + 1
        if p["year"]:
            year_counts[p["year"]] = year_counts.get(p["year"], 0) + 1
        for t in p["tags"]:
            tag_counts.setdefault(tag_key(t), [t, 0])[1] += 1

    menus = [
        ("category", F["category"], F["all_category"], [
            (c, indent * depth + f"{F['categories'][c]} ({cat_counts[c]})")
            for c, depth in FILTER_CATEGORIES if c in cat_counts
        ]),
        ("year", F["years"], F["all_years"], [
            (str(y), f"{y} ({n})") for y, n in sorted(year_counts.items(), reverse=True)
        ]),
        ("tag", F["tags"], F["all_tags"], [
            (k, f"{label} ({n})")
            for k, (label, n) in sorted(tag_counts.items(), key=lambda kv: kv[1][0].casefold())
        ]),
    ]
    return {
        "menus": [
            {"name": name, "label": label, "all": all_label, "options": opts}
            for name, label, all_label, opts in menus if opts
        ],
        "total": len(local),
    }


def mailto_for(p: dict, L: dict) -> str:
    """Prefilled inquiry email. Only mentions details that are actually known."""
    subject = L["mail_subject"].format(title=p["title"], id=p["id"])
    bits = [b for b in (
        str(p["year"]) if p["year"] else "",
        p["technique"],
        f"{p['width_cm']}x{p['height_cm']} cm" if p["width_cm"] and p["height_cm"] else "",
    ) if b]
    detail = f" ({', '.join(bits)})" if bits else ""
    body = L["mail_body"].format(title=p["title"], detail=detail)
    q = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    return f"mailto:{CONTACT_EMAIL}?{q}"


# --------------------------------------------------------------------- html

def asset_version(rel_path: str) -> str:
    """Short content hash, appended to the CSS/JS URLs as ?v=...

    Browsers cache stylesheets and scripts aggressively, so an edit could sit
    invisible behind a stale copy for a long time. Changing the URL whenever the
    file's contents change forces the browser to fetch the new one immediately.
    """
    p = DOCS_DIR / rel_path
    if not p.exists():
        return "0"
    return hashlib.sha1(p.read_bytes()).hexdigest()[:8]


def read_content(lang: str, name: str) -> str:
    path = CONTENT_DIR / lang / name
    if not path.exists():
        raise BuildError(f"missing content fragment: {path}")
    return path.read_text(encoding="utf-8")


def render_site(paintings: list[dict]) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        # Autoescape everywhere: CSV-sourced fields (title, technique, ...) and the
        # mailto href need HTML/attribute escaping. The hand-written content
        # fragments are raw HTML on purpose and opt out explicitly with `| safe`.
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    today = datetime.date.today()
    audio_present = (DOCS_DIR / "audio" / AUDIO_FILENAME).exists()
    if not audio_present:
        print("note: docs/audio/track.mp3 not found — audio player omitted for now", file=sys.stderr)
    if not INSTAGRAM_HANDLE:
        print("note: INSTAGRAM_HANDLE is empty in build.py — Instagram icon omitted", file=sys.stderr)

    css_v = asset_version("css/style.css")
    js_v = asset_version("js/lightbox.js")
    filter_v = asset_version("js/filter.js")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for lang, L in LANGUAGES.items():
        out_dir = DOCS_DIR / L["subdir"] if L["subdir"] else DOCS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        local = [localise(p, L) for p in paintings]

        base_ctx = {
            "L": L,
            "lang": L["code"],
            "site_name": SITE_NAME,
            "artist_name": ARTIST_NAME,
            "contact_email": CONTACT_EMAIL,
            "instagram": INSTAGRAM_HANDLE,
            "build_date": today.isoformat(),
            "build_year": today.year,
            "audio_file": AUDIO_FILENAME if audio_present else None,
            "root": L["root"],
            "css_v": css_v,
            "js_v": js_v,
            "filter_v": filter_v,
            "site_url": SITE_URL,
        }

        pages = [
            ("index.html", "index.html", {
                "page_id": "home",
                "content": read_content(lang, "home.html"),
                "newest": local[:3],
            }),
            ("about.html", "page.html", {"page_id": "about", "content": read_content(lang, "about.html")}),
            ("order.html", "page.html", {"page_id": "order", "content": read_content(lang, "order.html")}),
            ("terms.html", "page.html", {"page_id": "terms", "content": read_content(lang, "terms.html")}),
            ("gallery.html", "gallery.html", {
                "page_id": "gallery",
                "paintings": local,
                "filters": gallery_filters(local, L),
            }),
            ("404.html", "404.html", {"page_id": "404"}),
        ]

        for out_name, template_name, ctx in pages:
            key = ctx["page_id"]
            ctx.setdefault("page_title", L["page_titles"].get(key))
            ctx.setdefault("page_description", L["descriptions"].get(key, ""))
            # where the language switch in the header points for this page
            other = LANGUAGES[L["other"]]
            ctx["switch_href"] = (
                f"{other['subdir']}/{out_name}" if other["subdir"] else f"{L['root']}{out_name}"
            )
            ctx["alt_en"] = f"{SITE_URL}/{out_name}"
            ctx["alt_fi"] = f"{SITE_URL}/fi/{out_name}"

            tmpl = env.get_template(template_name)
            (out_dir / out_name).write_text(tmpl.render(**base_ctx, **ctx), encoding="utf-8")

        shown = L["subdir"] + "/" if L["subdir"] else ""
        print(f"wrote docs/{shown}  ({len(pages)} pages, {lang})")

    (DOCS_DIR / ".nojekyll").touch()


# ------------------------------------------------------------------- check

LINK_RE = re.compile(r'(?:href|src)="([^"]+)"')
ID_RE = re.compile(r'id="([^"]+)"')


def check_links() -> list[str]:
    problems = []
    html_files = sorted(DOCS_DIR.rglob("*.html"))  # includes the /fi/ pages
    id_cache: dict[Path, set[str]] = {}

    def ids_in(path: Path) -> set[str]:
        if path not in id_cache:
            id_cache[path] = set(ID_RE.findall(path.read_text(encoding="utf-8"))) if path.exists() else set()
        return id_cache[path]

    for page in html_files:
        where = page.relative_to(DOCS_DIR).as_posix()
        text = page.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("mailto:", "http://", "https://", "data:", "tel:")):
                continue
            path_part, _, fragment = target.partition("#")
            path_part = path_part.partition("?")[0]  # drop ?v= cache-busting stamps
            if path_part in ("", "."):
                resolved = page
            else:
                # relative to the page that contains the link, so ../ works
                resolved = (page.parent / path_part).resolve()
            if not str(resolved).startswith(str(DOCS_DIR.resolve())):
                problems.append(f"{where}: link escapes docs/: {target}")
                continue
            if not resolved.exists():
                problems.append(f"{where}: broken link target: {target}")
                continue
            if fragment and resolved.suffix == ".html" and fragment not in ids_in(resolved):
                problems.append(f"{where}: missing anchor #{fragment} in {resolved.name}")

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
