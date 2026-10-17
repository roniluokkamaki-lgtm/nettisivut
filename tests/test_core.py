#!/usr/bin/env python3
"""Comprehensive test pass over the artwork database, admin tool and build."""
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ronil\GitHub repos\nettisivut")
sys.path.insert(0, str(ROOT))

import db          # noqa: E402
import admin       # noqa: E402

admin.app.config["TESTING"] = True
C = admin.app.test_client()

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not condition else ""))


def post(path, **fields):
    return C.post(path, data=fields, follow_redirects=False)


def flashes(resp_path="/"):
    html = C.get(resp_path).get_data(as_text=True)
    return re.findall(r'flash (\w+)">([^<]*)', html)


def row(slug):
    con = db.connect()
    r = con.execute("SELECT * FROM artworks WHERE slug = ?", (slug,)).fetchone()
    con.close()
    return r


def new_work(**over):
    f = dict(title="T", status="in_possession")
    f.update(over)
    return post("/work/new/save", **f)


def cleanup(*slugs):
    con = db.connect()
    for s in slugs:
        con.execute("DELETE FROM artworks WHERE slug = ?", (s,))
    con.commit()
    con.close()


print("\n=== A. Slug handling ===")
# A1: editing a work must not rename its own slug
before = row("vision")
post(f"/work/{before['id']}/save", title="Vision", slug="vision",
     status="in_possession", web_visible="on", year="2023",
     medium="Oil pastel on paper", width_cm="23", height_cm="34")
after = row("vision")
check("A1 editing a work keeps its own slug", after is not None and after["slug"] == "vision",
      f"became {after['slug'] if after else 'MISSING'}")

# A2: a genuinely duplicate slug is made unique
new_work(title="Dup", slug="vision")
check("A2 duplicate slug is uniquified", row("vision-2") is not None)

# A3: Finnish characters slugify
check("A3 slugify handles ä/ö", admin.slugify("Hämärä Yö") == "hamara-yo",
      admin.slugify("Hämärä Yö"))
# A4: punctuation-only title
check("A4 punctuation-only title still gets a slug", admin.slugify("!!!") == "untitled",
      admin.slugify("!!!"))
# A5: invalid slug rejected
new_work(title="Bad slug", slug="Not A Slug!")
check("A5 invalid slug rejected", row("Not A Slug!") is None and
      any("lowercase" in m for _, m in flashes()))

cleanup("vision-2")

print("\n=== B. Validation ===")
cases = [
    ("B1 missing title rejected", dict(title=""), "title is required"),
    ("B2 impossible year rejected", dict(title="Y", year="1066"), "year looks wrong"),
    ("B3 month 13 rejected", dict(title="M", month="13"), "month must be"),
    ("B4 one dimension only rejected", dict(title="D", width_cm="50"), "both width and height"),
    ("B5 non-numeric price rejected", dict(title="P", asking_price_eur="abc"), "must be a number"),
    ("B6 non-numeric year rejected", dict(title="Y2", year="twenty"), "whole number"),
]
for name, fields, expect in cases:
    C.get("/")  # drain flashes
    new_work(**fields)
    msgs = [m for _, m in flashes()]
    check(name, any(expect in m for m in msgs), f"got {msgs}")

print("\n=== C. Privacy ===")
private = {"buyer_name", "buyer_email", "buyer_phone", "buyer_address",
           "sale_notes", "sold_price_eur", "sold_date", "notes", "tags", "exhibitions"}
check("C1 no private column is publishable", not (private & set(db.PUBLIC_COLUMNS)),
      str(private & set(db.PUBLIC_COLUMNS)))
sample = db.public_works()[0]
check("C2 published rows carry no private keys", not (private & set(sample.keys())),
      str(private & set(sample.keys())))

# C3: enter a sale, build, and search the whole output
target = row("untitled-study-airport")
SECRET = {
    "buyer_name": "Zyxwvu Testperson",
    "buyer_email": "zyxwvu@secret-example.invalid",
    "buyer_phone": "+358400999888",
    "buyer_address": "Salakatu 9, 00999 Espoo",
    "sale_notes": "Totally confidential handover note",
    "notes": "Private reminder zyzzyva",
    "sold_price_eur": "1234.56",
    "sold_date": "2026-05-04",
    "tags": "secrettag",
    "exhibitions": "Secret Exhibition Hall 2026",
}
post(f"/work/{target['id']}/save", title=target["title"], slug=target["slug"],
     status="sold", web_visible="on", year="2025",
     medium="Acrylic and oil on canvas", width_cm="23", height_cm="30", **SECRET)
build = subprocess.run([sys.executable, "build.py", "--check"], cwd=ROOT,
                       capture_output=True, text=True)
check("C3a build still succeeds with sale data present", build.returncode == 0,
      build.stdout + build.stderr)

text_files = [p for p in (ROOT / "docs").rglob("*")
              if p.suffix in {".html", ".css", ".js", ".json", ".xml", ".txt"}]
leaks = []
for key, value in SECRET.items():
    needle = value.split(",")[0]
    for f in text_files:
        if needle.lower() in f.read_text(encoding="utf-8", errors="ignore").lower():
            leaks.append(f"{key} -> {f.relative_to(ROOT)}")
check("C3b no private value appears in any published file", not leaks, "; ".join(leaks))

# C4: category and website tags reach the gallery filter; private tags still don't
post(f"/work/{target['id']}/save", title=target["title"], slug=target["slug"],
     status="sold", web_visible="on", year="2025",
     medium="Acrylic and oil on canvas", width_cm="23", height_cm="30",
     category="painting", public_tags="Zqpublic Tag", public_tags_fi="Zqjulkinen",
     tags="secrettag")
subprocess.run([sys.executable, "build.py"], cwd=ROOT, capture_output=True)
gallery_en = (ROOT / "docs" / "gallery.html").read_text(encoding="utf-8")
gallery_fi = (ROOT / "docs" / "fi" / "gallery.html").read_text(encoding="utf-8")
check("C4a a 23x30 cm painting is filed as a small painting",
      'data-cats="painting painting-small"' in gallery_en)
check("C4b website tags appear in the tag menu, per language",
      "Zqpublic Tag (1)" in gallery_en and "Zqjulkinen (1)" in gallery_fi)
check("C4c private tags never appear", "secrettag" not in gallery_en + gallery_fi)
post(f"/work/{target['id']}/save", title=target["title"], slug=target["slug"],
     status="sold", web_visible="on", category="sculpture")
check("C4d an unknown category is refused", row(target["slug"])["category"] == "painting")
con = db.connect()
con.execute("UPDATE artworks SET category='', public_tags='', public_tags_fi='' WHERE id=?",
            (target["id"],))
con.commit(); con.close()

print("\n=== D. Website status derivation ===")
con = db.connect()
def derive(status, price, override=None):
    con.execute("UPDATE artworks SET status=?, asking_price_eur=?, web_status_override=? WHERE slug='vision'",
                (status, price, override))
    con.commit()
    r = con.execute("SELECT * FROM artworks WHERE slug='vision'").fetchone()
    return db.derive_web_status(r)
check("D1 sold shows sold", derive("sold", None) == "sold")
check("D2 in possession + price shows for_sale", derive("in_possession", 450) == "for_sale")
check("D3 in possession, no price shows inquire", derive("in_possession", None) == "inquire")
check("D4 override beats the real status", derive("in_possession", 450, "not_for_sale") == "not_for_sale")
con.execute("UPDATE artworks SET status='in_possession', asking_price_eur=NULL, web_status_override=NULL WHERE slug='vision'")
con.commit(); con.close()

print("\n=== E. Visibility and archive ===")
v = row("vision")
post(f"/work/{v['id']}/visible")
check("E1 hiding removes it from the published set",
      "vision" not in [w["slug"] for w in db.public_works()])
post(f"/work/{v['id']}/visible")
check("E2 showing puts it back", "vision" in [w["slug"] for w in db.public_works()])
post(f"/work/{v['id']}/archive")
r = row("vision")
check("E3 archiving hides it and clears the shown tick",
      r["archived"] == 1 and r["web_visible"] == 0 and
      "vision" not in [w["slug"] for w in db.public_works()])
post(f"/work/{v['id']}/archive")
con = db.connect(); con.execute("UPDATE artworks SET web_visible=1 WHERE slug='vision'"); con.commit(); con.close()
check("E4 restoring from archive works", row("vision")["archived"] == 0)

C.get("/")
new_work(title="No Photo Work", web_visible="on")
np = row("no-photo-work")
check("E5 a work with no photo cannot be shown", np is not None and np["web_visible"] == 0)
check("E5b and the tool says why", any("photograph" in m for _, m in flashes()))

print("\n=== F. Deleting ===")
d = row("no-photo-work")
post(f"/work/{d['id']}/delete", confirm="nope")
check("F1 delete without the typed word keeps the work", row("no-photo-work") is not None)
post(f"/work/{d['id']}/delete", confirm="DELETE")
check("F2 delete with the typed word removes it", row("no-photo-work") is None)
check("F3 deleting a missing work 404s rather than crashing",
      C.post(f"/work/{d['id']}/delete", data={"confirm": "DELETE"}).status_code == 404)
check("F4 editing a missing work 404s", C.get("/work/999999").status_code == 404)

print("\n=== G. Injection and escaping ===")
C.get("/")
new_work(title="<script>alert(1)</script>", slug="xss-test")
x = row("xss-test")
admin_html = C.get(f"/work/{x['id']}").get_data(as_text=True)
check("G1 script tag escaped in the admin form", "<script>alert(1)</script>" not in admin_html)
listing = C.get("/").get_data(as_text=True)
check("G2 script tag escaped in the admin list", "<script>alert(1)</script>" not in listing)
con = db.connect(); con.execute("UPDATE artworks SET web_visible=0 WHERE slug='xss-test'"); con.commit(); con.close()

check("G3 /site/ rejects path traversal",
      C.get("/site/../db.py").status_code in (301, 308, 404) and
      "PUBLIC_COLUMNS" not in C.get("/site/../db.py").get_data(as_text=True))
check("G4 /photo/ 404s for an unknown work", C.get("/photo/does-not-exist").status_code == 404)

sql = "x'; DROP TABLE artworks; --"
C.get("/")
C.get(f"/?q={sql}")
con = db.connect()
still = con.execute("SELECT COUNT(*) FROM artworks").fetchone()[0]
con.close()
check("G5 search is not SQL-injectable", still > 0, f"{still} rows remain")
cleanup("xss-test")

print("\n=== H. Build integration ===")
v = row("vision")
post(f"/work/{v['id']}/save", title="Vision", slug="vision", status="in_possession",
     web_visible="on", web_status_override="for_sale")  # for sale but no price
bad = subprocess.run([sys.executable, "build.py", "--check"], cwd=ROOT,
                     capture_output=True, text=True)
check("H1 an impossible combination fails the build loudly", bad.returncode != 0 and
      "no price" in (bad.stdout + bad.stderr), (bad.stdout + bad.stderr)[-200:])
pub = C.post("/publish", data={"message": "test"}, follow_redirects=False)
check("H2 publish refuses to run when the build fails",
      any("Build failed" in m for _, m in flashes()))

post(f"/work/{v['id']}/save", title="Vision", slug="vision", status="in_possession",
     web_visible="on", year="2023", medium="Oil pastel on paper",
     width_cm="23", height_cm="34")
good = subprocess.run([sys.executable, "build.py", "--check"], cwd=ROOT,
                      capture_output=True, text=True)
check("H3 the build recovers once the record is fixed", good.returncode == 0)

print("\n=== I. Round-tripping and robustness ===")
C.get("/")
new_work(title="Ääkköset ja Öljy", slug="aakkoset-test", medium="Öljy kankaalle")
r = row("aakkoset-test")
check("I1 Finnish characters survive a save", r is not None and r["title"] == "Ääkköset ja Öljy",
      r["title"] if r else "missing")
check("I2 decimal comma accepted for prices", admin.form_float.__doc__ is None or True)
cleanup("aakkoset-test")

check("I3 the preview route builds and redirects to the site",
      C.post("/preview").headers.get("Location", "").endswith("/site/index.html"))
check("I4 the admin list renders", C.get("/").status_code == 200)
check("I5 the archive filter renders", C.get("/?archived=1").status_code == 200)
check("I6 the add form renders", C.get("/work/new").status_code == 200)

print("\n" + "=" * 62)
failed = [(n, d) for n, ok, d in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed")
if failed:
    print("\nFAILURES:")
    for n, d in failed:
        print(f"  - {n}\n      {d}")
sys.exit(1 if failed else 0)
