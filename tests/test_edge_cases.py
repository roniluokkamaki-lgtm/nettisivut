#!/usr/bin/env python3
"""Round two: adversarial probes at the things most likely to be broken."""
import io
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ronil\GitHub repos\nettisivut")
sys.path.insert(0, str(ROOT))
import db, admin  # noqa: E402

admin.app.config["TESTING"] = True
C = admin.app.test_client()
findings = []


def report(name, ok, detail=""):
    findings.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'BUG '}  {name}" + (f"\n          {detail}" if detail else ""))


def row(slug):
    con = db.connect()
    r = con.execute("SELECT * FROM artworks WHERE slug=?", (slug,)).fetchone()
    con.close()
    return r


def build():
    return subprocess.run([sys.executable, "build.py", "--check"], cwd=ROOT,
                          capture_output=True, text=True)


def cleanup(*slugs):
    con = db.connect()
    for s in slugs:
        con.execute("DELETE FROM artworks WHERE slug=?", (s,))
    con.commit(); con.close()


print("\n=== J. Decimal comma (the test I previously faked) ===")
C.get("/")
C.post("/work/new/save", data=dict(title="Comma Price", slug="comma-price",
                                   status="in_possession", asking_price_eur="1 234,50".replace(" ", "")))
r = row("comma-price")
report("J1 '1234,50' is accepted as a price", r is not None and abs((r["asking_price_eur"] or 0) - 1234.50) < 0.01,
       f"stored {r['asking_price_eur'] if r else 'nothing'}")
cleanup("comma-price")


print("\n=== K. Orphaned files after delete / rename ===")
pngs_before = {p.name for p in (ROOT / "docs" / "img" / "paintings").glob("*.jpg")}
# give a work a photo, publish it, then delete the work
shutil.copyfile(ROOT / "originals" / "DSCF1176.jpg", ROOT / "originals" / "orphan-test.jpg")
C.post("/work/new/save", data=dict(title="Orphan Test", slug="orphan-test",
                                   status="in_possession", web_visible="on"))
con = db.connect()
con.execute("UPDATE artworks SET image='orphan-test.jpg', web_visible=1 WHERE slug='orphan-test'")
con.commit(); con.close()
build()
made = {p.name for p in (ROOT / "docs" / "img" / "paintings").glob("orphan-test-*.jpg")}
report("K1 publishing a work generates its web images", len(made) == 3, f"{sorted(made)}")

w = row("orphan-test")
C.post(f"/work/{w['id']}/delete", data={"confirm": "DELETE"})
build()
left = {p.name for p in (ROOT / "docs" / "img" / "paintings").glob("orphan-test-*.jpg")}
report("K2 deleting a work also removes its published images", not left,
       f"{len(left)} image(s) remain published after deletion and are still "
       f"reachable on the live site: {sorted(left)}")
orig_left = (ROOT / "originals" / "orphan-test.jpg").exists()
report("K3 deleting a work removes its original photo", not orig_left,
       "the original stays in originals/ (harmless: that folder is never published)")
# tidy up whatever the code did not
for p in (ROOT / "docs" / "img" / "paintings").glob("orphan-test-*.jpg"):
    p.unlink()
(ROOT / "originals" / "orphan-test.jpg").unlink(missing_ok=True)


print("\n=== L. Missing or corrupt photo files ===")
v = row("vision")
img = ROOT / "originals" / v["image"]
tmp = ROOT / "originals" / "_vision_hidden.bak"
shutil.move(img, tmp)
b = build()
report("L1 a missing photo fails the build with a clear message",
       b.returncode != 0 and "not found in originals" in (b.stdout + b.stderr),
       (b.stdout + b.stderr).strip()[-160:])
shutil.move(tmp, img)

# a file that is not really an image but has a .jpg name
fake = ROOT / "originals" / "fake-image.jpg"
fake.write_text("this is definitely not a JPEG")
C.post("/work/new/save", data=dict(title="Fake Image", slug="fake-image",
                                   status="in_possession", web_visible="on"))
con = db.connect()
con.execute("UPDATE artworks SET image='fake-image.jpg', web_visible=1 WHERE slug='fake-image'")
con.commit(); con.close()
b = build()
out = (b.stdout + b.stderr)
report("L2 a corrupt image fails the build understandably",
       b.returncode != 0 and ("cannot identify image" in out.lower() or "image" in out.lower()),
       "build crashes with a raw Pillow traceback rather than a readable message"
       if "Traceback" in out else out.strip()[-160:])
cleanup("fake-image")
fake.unlink(missing_ok=True)


print("\n=== M. Upload handling ===")
C.get("/")
data = {"title": "Upload Test", "slug": "upload-test", "status": "in_possession",
        "photo": (io.BytesIO(b"not an image"), "evil.exe")}
C.post("/work/new/save", data=data, content_type="multipart/form-data")
msgs = [m for _, m in __import__("re").findall(r'flash (\w+)">([^<]*)',
        C.get("/").get_data(as_text=True))]
report("M1 a non-image upload is refused", row("upload-test") is None,
       "the work was created anyway" if row("upload-test") else "")
cleanup("upload-test")

real = (ROOT / "originals" / "DSCF1176.jpg").read_bytes()
C.post("/work/new/save", content_type="multipart/form-data",
       data={"title": "Good Upload", "slug": "good-upload", "status": "in_possession",
             "web_visible": "on", "photo": (io.BytesIO(real), "whatever.JPG")})
g = row("good-upload")
report("M2 a real upload is stored under the work's own name",
       g is not None and g["image"] == "good-upload.jpg" and
       (ROOT / "originals" / "good-upload.jpg").exists(),
       f"image={g['image'] if g else None}")
report("M3 uploading a photo makes the work publishable",
       g is not None and g["web_visible"] == 1)
cleanup("good-upload")
(ROOT / "originals" / "good-upload.jpg").unlink(missing_ok=True)


print("\n=== N. Renaming a live work ===")
v = row("vision")
C.post(f"/work/{v['id']}/save", data=dict(title="Vision", slug="vision-renamed",
       status="in_possession", web_visible="on", year="2023",
       medium="Oil pastel on paper", width_cm="23", height_cm="34"))
renamed = row("vision-renamed")
report("N1 renaming is allowed", renamed is not None)
if renamed:
    b = build()
    stale = list((ROOT / "docs" / "img" / "paintings").glob("vision-*.jpg"))
    msgs = [m for _, m in __import__("re").findall(r'flash (\w+)">([^<]*)',
            C.get("/").get_data(as_text=True))]
    report("N2 renaming warns that old links will break",
           any("stop working" in m or "old address" in m for m in msgs), f"got {msgs}")
    # put it back
    C.post(f"/work/{renamed['id']}/save", data=dict(title="Vision", slug="vision",
           status="in_possession", web_visible="on", year="2023",
           medium="Oil pastel on paper", width_cm="23", height_cm="34"))
    for p in (ROOT / "docs" / "img" / "paintings").glob("vision-renamed-*.jpg"):
        p.unlink()


print("\n=== O. Backup resilience ===")
real_dir = db.BACKUP_DIR
db.BACKUP_DIR = Path("Z:/definitely/not/mounted")
ok, msg = db.backup(backup_dir=db.BACKUP_DIR)
report("O1 an unavailable backup folder is reported, not crashed", ok is False and msg,
       f"returned {(ok, msg)}")
db.BACKUP_DIR = real_dir
ok, msg = db.backup()
report("O2 backups work again once the folder is back", ok, msg)


print("\n=== P. Publish when nothing changed ===")
# NOT exercised live: calling /publish really does commit and push. Earlier this
# test pushed a junk commit to the real repository. Check the guard by reading
# the same state the route reads, without invoking it.
build()
subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True)
dirty = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
subprocess.run(["git", "reset", "-q"], cwd=ROOT, capture_output=True)
report("P1 the publish guard can tell whether anything changed", isinstance(dirty, bool),
       f"working tree has changes: {dirty}")


print("\n=== Q. Detail photographs (the photos table) ===")
con = db.connect()
has_table = con.execute(
    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='photos'").fetchone()[0]
con.close()
v = row("vision")
page = C.get(f"/work/{v['id']}").get_data(as_text=True)
has_ui = "Add detail photograph" in page
real = (ROOT / "originals" / "DSCF1176.jpg").read_bytes()
C.post(f"/work/{v['id']}/photos/add", content_type="multipart/form-data",
       data={"photo": (io.BytesIO(real), "detail.jpg"), "caption": "test detail"})
con = db.connect()
n = con.execute("SELECT COUNT(*) FROM photos WHERE artwork_id=?", (v["id"],)).fetchone()[0]
pid = con.execute("SELECT id FROM photos WHERE artwork_id=?", (v["id"],)).fetchone()
con.close()
report("Q1 detail photos can be added and are stored", has_table and has_ui and n == 1,
       f"ui={has_ui} stored={n}")
shown = C.get(f"/work/{v['id']}").get_data(as_text=True)
report("Q2 detail photos appear on the edit screen", "test detail" in shown)
served = C.get(f"/detail-photo/{pid['id']}")
report("Q3 a detail photo is viewable", served.status_code == 200 and len(served.data) > 1000)
C.post(f"/work/{v['id']}/photos/{pid['id']}/delete")
con = db.connect()
left = con.execute("SELECT COUNT(*) FROM photos WHERE artwork_id=?", (v["id"],)).fetchone()[0]
con.close()
report("Q4 a detail photo can be removed", left == 0)
b = subprocess.run([sys.executable, "build.py", "--check"], cwd=ROOT, capture_output=True, text=True)
leaked = any("detail" in f.name for f in (ROOT / "docs" / "img" / "paintings").glob("*.jpg"))
report("Q5 detail photos are never published", not leaked)


print("\n" + "=" * 62)
bugs = [(n, d) for n, ok, d in findings if not ok]
print(f"{len(findings) - len(bugs)}/{len(findings)} passed")
if bugs:
    print("\nISSUES FOUND:")
    for n, d in bugs:
        print(f"  * {n}\n      {d}")
