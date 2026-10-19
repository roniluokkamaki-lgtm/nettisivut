#!/usr/bin/env python3
"""
Local admin tool for the artwork database.

    admin.bat          (or: py -3 admin.py)

Runs on 127.0.0.1 only, so it is not reachable from the network and needs no
login. It is a tool on this machine, not a website.

It also serves the built site at /site/ for previewing, so there is one process
to start and stop rather than two.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, send_from_directory, url_for)
from io import BytesIO

import build
import db
import visitors

ROOT = Path(__file__).resolve().parent
ORIGINALS = ROOT / "originals"
POSTERS = ORIGINALS / "exhibitions"
DOCS = ROOT / "docs"
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

app = Flask(__name__, template_folder="templates")
app.secret_key = "local-admin-only"  # only used for flash messages on localhost
app.jinja_env.globals.update(STATUSES=db.STATUSES, WEB_STATUSES=db.WEB_STATUSES,
                              HOME_POSITIONS=db.HOME_POSITIONS,
                             SUPPORTS=db.SUPPORTS, CATEGORIES=db.CATEGORIES,
                             EXHIBITION_KINDS=db.EXHIBITION_KINDS)


# ----------------------------------------------------------------- helpers

def slugify(text: str) -> str:
    text = (text or "").lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("å", "a"), ("é", "e")):
        text = text.replace(a, b)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "untitled"


def unique_slug(con, base: str, exclude_id: int | None = None) -> str:
    slug, n = base, 2
    while True:
        row = con.execute(
            "SELECT id FROM artworks WHERE slug = ? AND id IS NOT ?", (slug, exclude_id)
        ).fetchone()
        if not row:
            return slug
        slug, n = f"{base}-{n}", n + 1


def form_value(name: str, default: str = "") -> str:
    return (request.form.get(name) or default).strip()


def form_int(name):
    v = form_value(name)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        raise ValueError(f"{name.replace('_', ' ')} must be a whole number")


def form_float(name):
    v = form_value(name).replace(",", ".")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        raise ValueError(f"{name.replace('_', ' ')} must be a number")


def save_upload(file_storage, slug: str) -> str | None:
    """Store an uploaded photo in originals/ under a name based on the slug."""
    if not file_storage or not file_storage.filename:
        return None
    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE:
        raise ValueError(f"{ext or 'that file'} is not an image I can use")
    ORIGINALS.mkdir(exist_ok=True)
    name = f"{slug}{ext}"
    file_storage.save(ORIGINALS / name)
    return name


def send_bytes(path: Path):
    """Serve an image from memory.

    send_file() on a path leaves the file open until the response is released,
    and Windows then refuses to delete or overwrite it. These are small admin
    previews, so reading them into memory costs nothing and avoids the lock.
    """
    mime = {".png": "image/png", ".webp": "image/webp",
            ".tif": "image/tiff", ".tiff": "image/tiff"}.get(path.suffix.lower(), "image/jpeg")
    return send_file(BytesIO(path.read_bytes()), mimetype=mime)


def run_build() -> tuple[bool, str]:
    """Rebuild the site in a subprocess so a failure cannot kill the admin tool."""
    r = subprocess.run([sys.executable, str(ROOT / "build.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def git(*args) -> tuple[bool, str]:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def live_slugs() -> set[str] | None:
    """Works that are on the live website right now.

    The live site is whatever was last pushed to GitHub, so this reads the
    published thumbnails from origin/main rather than from the local docs/
    folder, which may hold a newer build that has not been published yet.
    Returns None if git can't tell (for example, before the first push).
    """
    ok, out = git("ls-tree", "--name-only", "origin/main", "docs/img/paintings/")
    if not ok:
        return None
    return {Path(p).name[:-len("-thumb.jpg")] for p in out.splitlines()
            if p.endswith("-thumb.jpg")}


# -------------------------------------------------------------------- list

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    show_archived = request.args.get("archived") == "1"
    sort = request.args.get("sort", "year")

    sql = "SELECT * FROM artworks WHERE archived = ?"
    params: list = [1 if show_archived else 0]
    if q:
        sql += " AND (title LIKE ? OR title_fi LIKE ? OR tags LIKE ? OR slug LIKE ?)"
        params += [f"%{q}%"] * 4
    if status in db.STATUSES:
        sql += " AND status = ?"
        params.append(status)
    sql += {
        "title": " ORDER BY title COLLATE NOCASE",
        "added": " ORDER BY created_at DESC",
    }.get(sort, " ORDER BY (year IS NULL), year DESC, (month IS NULL), month DESC, title")

    con = db.connect()
    works = con.execute(sql, params).fetchall()
    counts = {
        "total": con.execute("SELECT COUNT(*) FROM artworks WHERE archived=0").fetchone()[0],
        "sold": con.execute("SELECT COUNT(*) FROM artworks WHERE archived=0 AND status='sold'").fetchone()[0],
        "shown": con.execute("SELECT COUNT(*) FROM artworks WHERE archived=0 AND web_visible=1").fetchone()[0],
        "archived": con.execute("SELECT COUNT(*) FROM artworks WHERE archived=1").fetchone()[0],
    }
    con.close()
    return render_template("admin/list.html", works=works, counts=counts, q=q,
                           status=status, show_archived=show_archived, sort=sort,
                           live=live_slugs())


@app.route("/photo/<slug>")
def photo(slug):
    """Thumbnail for the admin list: the built one if it exists, else the original."""
    built = DOCS / "img" / "paintings" / f"{slug}-thumb.jpg"
    if built.exists():
        return send_bytes(built)
    con = db.connect()
    row = con.execute("SELECT image FROM artworks WHERE slug = ?", (slug,)).fetchone()
    con.close()
    if row and row["image"] and (ORIGINALS / row["image"]).exists():
        return send_bytes(ORIGINALS / row["image"])
    abort(404)


# -------------------------------------------------------------------- edit

@app.route("/work/new")
def new_work():
    return render_template("admin/form.html", w=None, photos=[])


@app.route("/work/<int:wid>")
def edit_work(wid):
    con = db.connect()
    w = con.execute("SELECT * FROM artworks WHERE id = ?", (wid,)).fetchone()
    photos = con.execute(
        "SELECT * FROM photos WHERE artwork_id = ? ORDER BY sort_order, id", (wid,)
    ).fetchall()
    con.close()
    if not w:
        abort(404)
    return render_template("admin/form.html", w=w, photos=photos)


@app.route("/work/<wid>/save", methods=["POST"])
def save_work(wid):
    con = db.connect()
    is_new = wid == "new"
    existing = None
    if not is_new:
        existing = con.execute("SELECT * FROM artworks WHERE id = ?", (int(wid),)).fetchone()
        if not existing:
            abort(404)

    try:
        title = form_value("title")
        if not title:
            raise ValueError("a title is required (use 'Untitled' if it has none)")

        slug = form_value("slug") or slugify(title)
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
            raise ValueError("the web name may use lowercase letters, numbers and hyphens only")
        slug = unique_slug(con, slug, None if is_new else int(wid))

        year, month = form_int("year"), form_int("month")
        if year and not (1900 <= year <= 2100):
            raise ValueError("that year looks wrong")
        if month and not (1 <= month <= 12):
            raise ValueError("month must be between 1 and 12")

        width, height = form_int("width_cm"), form_int("height_cm")
        if bool(width) != bool(height):
            raise ValueError("give both width and height, or neither")

        status = form_value("status", "in_possession")
        if status not in db.STATUSES:
            raise ValueError("unknown status")
        category = form_value("category")
        if category not in db.CATEGORIES:
            raise ValueError("unknown category")
        home_position = form_int("home_position")
        if home_position and home_position not in db.HOME_POSITIONS:
            raise ValueError("unknown front page position")
        override = form_value("web_status_override")
        if override and override not in db.WEB_STATUSES:
            raise ValueError("unknown website status")

        if existing and existing["slug"] != slug and existing["web_visible"]:
            flash(f"Web name changed from '{existing['slug']}' to '{slug}'. Any link or "
                  "bookmark using the old address will stop working.", "warn")

        image = save_upload(request.files.get("photo"), slug) or (
            existing["image"] if existing else "")

        web_visible = 1 if request.form.get("web_visible") else 0
        if web_visible and not image:
            web_visible = 0
            flash("Saved, but it cannot be shown on the site until you add a photograph.", "warn")

        fields = {
            "slug": slug, "title": title, "title_fi": form_value("title_fi"),
            "year": year, "month": month,
            "medium": form_value("medium"), "medium_fi": form_value("medium_fi"),
            "theme": form_value("theme"), "tags": form_value("tags"),
            "category": category,
            "public_tags": form_value("public_tags"),
            "public_tags_fi": form_value("public_tags_fi"),
            "exhibitions": form_value("exhibitions"),
            "width_cm": width, "height_cm": height, "depth_cm": form_float("depth_cm"),
            "support": form_value("support"),
            "framed": 1 if request.form.get("framed") else 0,
            "signed": 1 if request.form.get("signed") else 0,
            "description": form_value("description"),
            "description_fi": form_value("description_fi"),
            "notes": form_value("notes"),
            "status": status,
            "web_visible": web_visible,
            "web_status_override": override or None,
            "home_position": home_position or None,
            "asking_price_eur": form_float("asking_price_eur"),
            "sold_date": form_value("sold_date") or None,
            "sold_price_eur": form_float("sold_price_eur"),
            "buyer_name": form_value("buyer_name"),
            "buyer_email": form_value("buyer_email"),
            "buyer_phone": form_value("buyer_phone"),
            "buyer_address": form_value("buyer_address"),
            "sale_notes": form_value("sale_notes"),
            "image": image,
            "updated_at": db.now(),
        }

        if home_position:
            # one work per place: taking a position frees it from whoever had it
            con.execute("UPDATE artworks SET home_position = NULL "
                        "WHERE home_position = ? AND id IS NOT ?",
                        (home_position, None if is_new else int(wid)))
        if is_new:
            fields["created_at"] = db.now()
            cols = ", ".join(fields)
            con.execute(f"INSERT INTO artworks ({cols}) VALUES ({', '.join('?' * len(fields))})",
                        list(fields.values()))
            wid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            sets = ", ".join(f"{k} = ?" for k in fields)
            con.execute(f"UPDATE artworks SET {sets} WHERE id = ?",
                        [*fields.values(), int(wid)])
        con.commit()
    except ValueError as e:
        con.close()
        flash(str(e), "error")
        return redirect(url_for("new_work") if is_new else url_for("edit_work", wid=int(wid)))
    finally:
        if con:
            con.close()

    ok, where = db.backup()
    flash(f"Saved. {'Backed up to ' + where if ok else 'BACKUP FAILED: ' + where}",
          "ok" if ok else "error")
    return redirect(url_for("edit_work", wid=int(wid)))


@app.route("/work/<int:wid>/photos/add", methods=["POST"])
def add_detail_photo(wid):
    """Extra reference shots: kept with the record, not published."""
    con = db.connect()
    w = con.execute("SELECT slug FROM artworks WHERE id = ?", (wid,)).fetchone()
    if not w:
        abort(404)
    try:
        n = con.execute("SELECT COUNT(*) FROM photos WHERE artwork_id = ?", (wid,)).fetchone()[0]
        name = save_upload(request.files.get("photo"), f"{w['slug']}-detail-{n + 1}")
        if not name:
            raise ValueError("choose a file first")
        con.execute(
            "INSERT INTO photos (artwork_id, filename, caption, sort_order) VALUES (?,?,?,?)",
            (wid, name, form_value("caption"), n + 1))
        con.commit()
        flash("Detail photograph added. These are kept with the record, not published.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    finally:
        con.close()
    db.backup()
    return redirect(url_for("edit_work", wid=wid))


@app.route("/work/<int:wid>/photos/<int:pid>/delete", methods=["POST"])
def delete_detail_photo(wid, pid):
    con = db.connect()
    row = con.execute("SELECT filename FROM photos WHERE id = ? AND artwork_id = ?",
                      (pid, wid)).fetchone()
    if not row:
        abort(404)
    con.execute("DELETE FROM photos WHERE id = ?", (pid,))
    con.commit()
    con.close()
    try:
        (ORIGINALS / row["filename"]).unlink(missing_ok=True)
    except OSError as e:
        # Windows can still hold the file open from having served it. The record
        # is gone either way; the stray file is in originals/, which is private.
        flash(f"Removed from the record, but the file is still in use: {e}", "warn")
    db.backup()
    flash("Detail photograph removed.", "ok")
    return redirect(url_for("edit_work", wid=wid))


@app.route("/detail-photo/<int:pid>")
def detail_photo(pid):
    con = db.connect()
    row = con.execute("SELECT filename FROM photos WHERE id = ?", (pid,)).fetchone()
    con.close()
    if not row or not (ORIGINALS / row["filename"]).exists():
        abort(404)
    return send_bytes(ORIGINALS / row["filename"])


@app.route("/work/<int:wid>/visible", methods=["POST"])
def toggle_visible(wid):
    con = db.connect()
    row = con.execute("SELECT web_visible, image FROM artworks WHERE id = ?", (wid,)).fetchone()
    if not row:
        abort(404)
    if not row["web_visible"] and not row["image"]:
        flash("Add a photograph before showing this work on the site.", "warn")
    else:
        con.execute("UPDATE artworks SET web_visible = ?, updated_at = ? WHERE id = ?",
                    (0 if row["web_visible"] else 1, db.now(), wid))
        con.commit()
    con.close()
    db.backup()
    return redirect(request.referrer or url_for("index"))


@app.route("/work/<int:wid>/archive", methods=["POST"])
def toggle_archive(wid):
    con = db.connect()
    row = con.execute("SELECT archived FROM artworks WHERE id = ?", (wid,)).fetchone()
    if not row:
        abort(404)
    now_archived = 0 if row["archived"] else 1
    con.execute(
        "UPDATE artworks SET archived = ?, web_visible = CASE WHEN ? THEN 0 ELSE web_visible END,"
        " updated_at = ? WHERE id = ?",
        (now_archived, now_archived, db.now(), wid))
    con.commit()
    con.close()
    db.backup()
    flash("Archived. It is hidden from the site but the record is kept."
          if now_archived else "Restored from the archive.", "ok")
    return redirect(url_for("index"))


@app.route("/work/<int:wid>/delete", methods=["POST"])
def delete_work(wid):
    con = db.connect()
    row = con.execute("SELECT * FROM artworks WHERE id = ?", (wid,)).fetchone()
    if not row:
        abort(404)
    if form_value("confirm") != "DELETE":
        con.close()
        flash("Type DELETE in the box to confirm permanent deletion.", "error")
        return redirect(url_for("edit_work", wid=wid))
    con.execute("DELETE FROM artworks WHERE id = ?", (wid,))
    con.commit()
    con.close()
    db.backup()
    flash(f"Deleted {row['title']!r} permanently. The OneDrive backup still holds "
          "the previous copy if you need it back.", "ok")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- visitors

@app.route("/visitors")
def visitors_page():
    days = request.args.get("days", 30, type=int)
    data, error = None, None
    if visitors.is_configured():
        try:
            data = visitors.fetch(days)
        except visitors.VisitorsError as e:
            error = str(e)
    return render_template("admin/visitors.html", data=data, error=error,
                           days=days if days in visitors.PERIODS else 30,
                           periods=visitors.PERIODS,
                           configured=visitors.is_configured(),
                           settings=visitors.load_settings())


@app.route("/visitors/settings", methods=["POST"])
def visitors_settings():
    account_id = form_value("account_id").lower()
    token = form_value("api_token") or visitors.load_settings().get("api_token", "")
    if not re.fullmatch(r"[0-9a-f]{32}", account_id):
        flash("The Account ID should be 32 characters of 0-9 and a-f.", "error")
    elif not token or re.search(r"\s", token):
        flash("Paste the API token (it has no spaces).", "error")
    else:
        visitors.save_settings(account_id, token)
        flash("Saved. The token stays on this computer and is never published.", "ok")
    return redirect(url_for("visitors_page"))


# ------------------------------------------------------------- exhibitions

@app.route("/exhibitions")
def exhibitions():
    con = db.connect()
    rows = con.execute(
        "SELECT * FROM exhibitions "
        "ORDER BY kind DESC, year DESC, (start_date IS NULL), start_date DESC, title"
    ).fetchall()
    con.close()
    return render_template("admin/exhibitions.html", exhibitions=rows)


@app.route("/exhibition/new")
def new_exhibition():
    return render_template("admin/exhibition_form.html", e=None)


@app.route("/exhibition/<int:eid>")
def edit_exhibition(eid):
    con = db.connect()
    e = con.execute("SELECT * FROM exhibitions WHERE id = ?", (eid,)).fetchone()
    con.close()
    if not e:
        abort(404)
    return render_template("admin/exhibition_form.html", e=e)


def form_date(name):
    v = form_value(name)
    if not v:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError(f"{name.replace('_', ' ')} must be a date")
    return v


@app.route("/exhibition/<eid>/save", methods=["POST"])
def save_exhibition(eid):
    con = db.connect()
    is_new = eid == "new"
    existing = None
    if not is_new:
        existing = con.execute("SELECT * FROM exhibitions WHERE id = ?", (int(eid),)).fetchone()
        if not existing:
            con.close()
            abort(404)
    try:
        title = form_value("title")
        if not title:
            raise ValueError("an exhibition needs a title")
        kind = form_value("kind", "solo")
        if kind not in db.EXHIBITION_KINDS:
            raise ValueError("choose solo or group")
        start, end = form_date("start_date"), form_date("end_date")
        if end and not start:
            raise ValueError("give a start date as well as an end date")
        if start and end and end < start:
            raise ValueError("the end date is before the start date")
        year = form_int("year") or (int(start[:4]) if start else None)
        if not year:
            raise ValueError("give a year, or a start date")
        if not (1900 <= year <= 2100):
            raise ValueError("that year looks wrong")

        fields = {
            "kind": kind, "title": title, "title_fi": form_value("title_fi"),
            "venue": form_value("venue"),
            "place": form_value("place"), "place_fi": form_value("place_fi"),
            "year": year, "start_date": start, "end_date": end,
            "details": form_value("details"), "details_fi": form_value("details_fi"),
            "web_visible": 1 if request.form.get("web_visible") else 0,
            "updated_at": db.now(),
        }
        if is_new:
            fields["created_at"] = db.now()
            cols = ", ".join(fields)
            con.execute(f"INSERT INTO exhibitions ({cols}) VALUES ({', '.join('?' * len(fields))})",
                        list(fields.values()))
            eid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            sets = ", ".join(f"{k} = ?" for k in fields)
            con.execute(f"UPDATE exhibitions SET {sets} WHERE id = ?", [*fields.values(), int(eid)])

        # the poster is named after the record's number, so it can only be
        # stored once the record exists
        upload = request.files.get("poster")
        if upload and upload.filename:
            ext = Path(upload.filename).suffix.lower()
            if ext not in ALLOWED_IMAGE:
                raise ValueError(f"{ext or 'that file'} is not an image I can use")
            POSTERS.mkdir(parents=True, exist_ok=True)
            name = f"exhibition-{eid}{ext}"
            for old in POSTERS.glob(f"exhibition-{eid}.*"):
                if old.name != name:
                    old.unlink(missing_ok=True)
            upload.save(POSTERS / name)
            con.execute("UPDATE exhibitions SET poster = ? WHERE id = ?", (name, int(eid)))
        con.commit()
    except ValueError as e:
        con.rollback()
        con.close()
        flash(str(e), "error")
        return redirect(url_for("new_exhibition") if is_new else url_for("edit_exhibition", eid=int(eid)))
    con.close()

    ok, where = db.backup()
    flash(f"Saved. {'Backed up to ' + where if ok else 'BACKUP FAILED: ' + where}",
          "ok" if ok else "error")
    return redirect(url_for("edit_exhibition", eid=int(eid)))


@app.route("/exhibition/<int:eid>/delete", methods=["POST"])
def delete_exhibition(eid):
    con = db.connect()
    row = con.execute("SELECT * FROM exhibitions WHERE id = ?", (eid,)).fetchone()
    if not row:
        con.close()
        abort(404)
    if form_value("confirm") != "DELETE":
        con.close()
        flash("Type DELETE in the box to confirm.", "error")
        return redirect(url_for("edit_exhibition", eid=eid))
    con.execute("DELETE FROM exhibitions WHERE id = ?", (eid,))
    con.commit()
    con.close()
    if row["poster"]:
        try:
            (POSTERS / row["poster"]).unlink(missing_ok=True)
        except OSError:
            pass  # a stray file in originals/ is harmless: that folder is never published
    db.backup()
    flash(f"Deleted the exhibition {row['title']!r}.", "ok")
    return redirect(url_for("exhibitions"))


@app.route("/exhibition-poster/<int:eid>")
def exhibition_poster(eid):
    con = db.connect()
    row = con.execute("SELECT poster FROM exhibitions WHERE id = ?", (eid,)).fetchone()
    con.close()
    if not row or not row["poster"] or not (POSTERS / row["poster"]).exists():
        abort(404)
    return send_bytes(POSTERS / row["poster"])


# ------------------------------------------------------- preview / publish

@app.route("/preview", methods=["POST"])
def preview():
    ok, output = run_build()
    flash(output or "built", "ok" if ok else "error")
    if ok:
        return redirect("/site/index.html")
    return redirect(url_for("index"))


@app.route("/site/", defaults={"path": "index.html"})
@app.route("/site/<path:path>")
def site(path):
    """Serve the built site for previewing, so no second server is needed."""
    return send_from_directory(DOCS, path)


@app.route("/publish", methods=["POST"])
def publish():
    ok, output = run_build()
    if not ok:
        flash("Build failed, nothing was published:\n" + output, "error")
        return redirect(url_for("index"))

    message = form_value("message") or "Update artworks"
    steps = [git("add", "-A")]
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
    if not changed:
        flash("Nothing to publish — the site is already up to date.", "ok")
        return redirect(url_for("index"))
    steps.append(git("commit", "-m", message))
    steps.append(git("push"))

    failures = [out for good, out in steps if not good]
    if failures:
        flash("Publish failed:\n" + "\n".join(failures), "error")
    else:
        flash("Published. The live site updates within a minute or two.", "ok")
    return redirect(url_for("index"))


# -------------------------------------------------------------------- main

def main() -> int:
    db.init()
    url = "http://127.0.0.1:5000/"
    print(f"\n  Artwork admin running at {url}")
    print("  Close this window to stop it.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    # 127.0.0.1 only: not reachable from the network
    app.run(host="127.0.0.1", port=5000, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
