#!/usr/bin/env python3
"""
One-off: move data/paintings.csv into the artwork database.

Run once. Kept afterwards as a record of how the old catalogue was mapped.

    py -3 migrate_csv_to_db.py

Slugs are preserved exactly as the CSV `id` values, because they appear in page
anchors and in every generated image filename. Changing them would break links
and force all images to be rebuilt.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import db

CSV_PATH = db.ROOT / "data" / "paintings.csv"

# Old publishing status -> (real status, web override)
# The old file described how a work should appear on the site. The database
# separates that from what is actually true of the piece.
STATUS_MAP = {
    "inquire":      ("in_possession", None),
    "for_sale":     ("in_possession", None),
    "sold":         ("sold", None),
    "not_for_sale": ("in_possession", "not_for_sale"),
}


def to_int(v):
    v = (v or "").strip()
    return int(v) if v else None


def to_float(v):
    v = (v or "").strip()
    return float(v) if v else None


def main() -> int:
    if not CSV_PATH.exists():
        print(f"nothing to migrate: {CSV_PATH} not found")
        return 1

    db.init()
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    con = db.connect()
    existing = {r["slug"] for r in con.execute("SELECT slug FROM artworks")}
    if existing:
        print(f"database already holds {len(existing)} works; refusing to migrate twice")
        return 1

    stamp = db.now()
    added = 0
    for r in rows:
        old_status = (r.get("status") or "").strip()
        if old_status not in STATUS_MAP:
            print(f"  ! unknown status {old_status!r} for {r.get('id')!r}, skipping")
            continue
        status, override = STATUS_MAP[old_status]

        con.execute(
            """INSERT INTO artworks (
                   slug, title, title_fi, year, medium, medium_fi, theme,
                   width_cm, height_cm, description, description_fi,
                   status, web_status_override, asking_price_eur, image,
                   web_visible, archived, created_at, updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0,?,?)""",
            (
                r["id"].strip(), r["title"].strip(), (r.get("title_fi") or "").strip(),
                to_int(r.get("year")), (r.get("technique") or "").strip(),
                (r.get("technique_fi") or "").strip(), (r.get("theme") or "").strip(),
                to_int(r.get("width_cm")), to_int(r.get("height_cm")),
                (r.get("description") or "").strip(),
                (r.get("description_fi") or "").strip(),
                status, override, to_float(r.get("price_eur")),
                (r.get("image") or "").strip(), stamp, stamp,
            ),
        )
        added += 1

    con.commit()
    sold = con.execute("SELECT COUNT(*) FROM artworks WHERE status='sold'").fetchone()[0]
    con.close()

    print(f"migrated {added} works into {db.DB_PATH}")
    print(f"  {sold} marked sold — open the admin tool to fill in the buyer details")
    ok, where = db.backup()
    print(f"  backup: {'written to ' + where if ok else 'FAILED: ' + where}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
