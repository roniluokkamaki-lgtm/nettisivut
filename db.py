#!/usr/bin/env python3
"""
The artwork database: schema, connection, and the one query the website may use.

Shared by admin.py (full read/write, including buyer details) and build.py
(public fields of visible works only).

PRIVACY: buyer_name, buyer_email, buyer_phone, buyer_address, sale_notes,
sold_price_eur and notes are private. They live only in this database and in the
OneDrive backup. They are never selected by `public_works()`, never passed to a
template, and the database file itself is excluded from git. If you add a column
here, decide which of those two worlds it belongs to.
"""
from __future__ import annotations

import csv
import datetime
import os
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# NETTISIVUT_DB points the tools at another database file, for trying changes
# out on a copy without touching the real records.
DB_PATH = Path(os.environ.get("NETTISIVUT_DB") or ROOT / "data" / "artworks.db")
# A copy pointed to by NETTISIVUT_DB backs up beside itself, never over the real
# OneDrive backup.
BACKUP_DIR = (DB_PATH.parent / "backup" if os.environ.get("NETTISIVUT_DB")
              else Path.home() / "OneDrive" / "nettisivut-backup")

STATUSES = ("in_possession", "sold")
WEB_STATUSES = ("for_sale", "inquire", "sold", "not_for_sale")
SUPPORTS = ("", "canvas", "paper", "panel", "board", "other")
# What kind of work it is, for the gallery filter. Blank means not yet decided;
# such a work is still shown, it just isn't listed under any category.
CATEGORIES = ("", "painting", "drawing", "other")
EXHIBITION_KINDS = ("solo", "group")
# Places on the front page. A work with no position is not featured there.
HOME_POSITIONS = (1, 2, 3)

SCHEMA = """
CREATE TABLE IF NOT EXISTS artworks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                TEXT    NOT NULL UNIQUE,
    title               TEXT    NOT NULL,
    title_fi            TEXT    NOT NULL DEFAULT '',
    year                INTEGER,
    month               INTEGER,
    medium              TEXT    NOT NULL DEFAULT '',
    medium_fi           TEXT    NOT NULL DEFAULT '',
    theme               TEXT    NOT NULL DEFAULT '',
    width_cm            INTEGER,
    height_cm           INTEGER,
    depth_cm            REAL,
    support             TEXT    NOT NULL DEFAULT '',
    framed              INTEGER NOT NULL DEFAULT 0,
    signed              INTEGER NOT NULL DEFAULT 0,
    description         TEXT    NOT NULL DEFAULT '',
    description_fi      TEXT    NOT NULL DEFAULT '',
    tags                TEXT    NOT NULL DEFAULT '',
    category            TEXT    NOT NULL DEFAULT '',
    public_tags         TEXT    NOT NULL DEFAULT '',
    public_tags_fi      TEXT    NOT NULL DEFAULT '',
    exhibitions         TEXT    NOT NULL DEFAULT '',
    notes               TEXT    NOT NULL DEFAULT '',
    status              TEXT    NOT NULL DEFAULT 'in_possession',
    archived            INTEGER NOT NULL DEFAULT 0,
    web_visible         INTEGER NOT NULL DEFAULT 1,
    web_status_override TEXT,
    home_position       INTEGER,
    asking_price_eur    REAL,
    sold_date           TEXT,
    sold_price_eur      REAL,
    buyer_name          TEXT    NOT NULL DEFAULT '',
    buyer_email         TEXT    NOT NULL DEFAULT '',
    buyer_phone         TEXT    NOT NULL DEFAULT '',
    buyer_address       TEXT    NOT NULL DEFAULT '',
    sale_notes          TEXT    NOT NULL DEFAULT '',
    image               TEXT    NOT NULL DEFAULT '',
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL,
    CHECK (status IN ('in_possession', 'sold')),
    CHECK (month IS NULL OR (month BETWEEN 1 AND 12))
);

CREATE TABLE IF NOT EXISTS photos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artwork_id  INTEGER NOT NULL REFERENCES artworks(id) ON DELETE CASCADE,
    filename    TEXT    NOT NULL,
    caption     TEXT    NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_photos_artwork ON photos(artwork_id);

-- Exhibitions for the website's Exhibitions page. Everything here is public:
-- an exhibition record holds nothing private, and hiding one is done with
-- web_visible rather than by keeping secrets in it.
CREATE TABLE IF NOT EXISTS exhibitions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL DEFAULT 'solo',
    title       TEXT    NOT NULL,
    title_fi    TEXT    NOT NULL DEFAULT '',
    venue       TEXT    NOT NULL DEFAULT '',
    place       TEXT    NOT NULL DEFAULT '',
    place_fi    TEXT    NOT NULL DEFAULT '',
    year        INTEGER NOT NULL,
    start_date  TEXT,
    end_date    TEXT,
    details     TEXT    NOT NULL DEFAULT '',
    details_fi  TEXT    NOT NULL DEFAULT '',
    poster      TEXT    NOT NULL DEFAULT '',
    web_visible INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    CHECK (kind IN ('solo', 'group'))
);
"""

# The website may read exactly these columns. No buyer or private field appears
# here, which is what keeps personal data out of the generated pages.
PUBLIC_COLUMNS = (
    "slug", "title", "title_fi", "year", "month",
    "medium", "medium_fi", "theme",
    # category and public_tags drive the gallery filter. `tags` (without the
    # public_ prefix) is the artist's private labelling and stays off this list.
    "category", "public_tags", "public_tags_fi",
    "width_cm", "height_cm",
    "description", "description_fi",
    "status", "web_status_override", "asking_price_eur",
    "home_position", "image",
)


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


# Columns added after the first version of the schema. Listed here so an
# existing database gains them on the next run instead of needing a rebuild.
ADDED_COLUMNS = {
    "tags": "TEXT NOT NULL DEFAULT ''",
    "exhibitions": "TEXT NOT NULL DEFAULT ''",
    "category": "TEXT NOT NULL DEFAULT ''",
    "public_tags": "TEXT NOT NULL DEFAULT ''",
    "public_tags_fi": "TEXT NOT NULL DEFAULT ''",
    "home_position": "INTEGER",
}


def init(path: Path = DB_PATH) -> None:
    with connect(path) as con:
        con.executescript(SCHEMA)
        have = {r["name"] for r in con.execute("PRAGMA table_info(artworks)")}
        for name, decl in ADDED_COLUMNS.items():
            if name not in have:
                con.execute(f"ALTER TABLE artworks ADD COLUMN {name} {decl}")


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def derive_web_status(row) -> str:
    """What the public site should say about a work.

    Follows the real status unless the artist set an explicit override.
    """
    override = row["web_status_override"]
    if override:
        return override
    if row["status"] == "sold":
        return "sold"
    return "for_sale" if row["asking_price_eur"] else "inquire"


def public_works(path: Path = DB_PATH) -> list[dict]:
    """Works the website should publish, newest first.

    Archived and hidden works are excluded here rather than in build.py, so
    there is one place that decides what reaches the public site.
    """
    cols = ", ".join(PUBLIC_COLUMNS)
    with connect(path) as con:
        rows = con.execute(
            f"SELECT {cols} FROM artworks "
            "WHERE archived = 0 AND web_visible = 1 "
            "ORDER BY (year IS NULL), year DESC, (month IS NULL), month DESC, title"
        ).fetchall()
    return [dict(r) | {"web_status": derive_web_status(r)} for r in rows]


def public_exhibitions(path: Path = DB_PATH) -> list[dict]:
    """Exhibitions the website should list, newest first."""
    with connect(path) as con:
        rows = con.execute(
            "SELECT id, kind, title, title_fi, venue, place, place_fi, year, "
            "start_date, end_date, details, details_fi, poster FROM exhibitions "
            "WHERE web_visible = 1 "
            "ORDER BY year DESC, (start_date IS NULL), start_date DESC, title"
        ).fetchall()
    return [dict(r) for r in rows]


def backup(path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR) -> tuple[bool, str]:
    """Copy the database and a full CSV export to OneDrive.

    The CSV carries the buyer details too. That is deliberate: it is the escape
    hatch that keeps the records readable without this tool, and it lives in the
    artist's own cloud storage, never in the public repository.
    """
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        with connect(path) as con:
            dest = backup_dir / "artworks.db"
            con.execute("PRAGMA wal_checkpoint(FULL)")
            # sqlite's own backup API copies safely even while connected
            with sqlite3.connect(dest) as target:
                con.backup(target)
            tables = {
                name: con.execute(f"SELECT * FROM {name} ORDER BY id").fetchall()
                for name in ("artworks", "exhibitions")
            }

        stamp = datetime.date.today().isocalendar()
        for name, rows in tables.items():
            if not rows:
                continue
            csv_path = backup_dir / f"{name}-{stamp.year}-w{stamp.week:02d}.csv"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                for r in rows:
                    w.writerow(dict(r))
        return True, str(backup_dir)
    except Exception as e:  # a failed backup must never block saving
        return False, str(e)
