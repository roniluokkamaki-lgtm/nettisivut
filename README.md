# nettisivut

Roni Luokkamäki's painting portfolio and store, live at
**https://www.roniluokkamaki.com**. Hand-built HTML and CSS,
generated from a local artwork database by a small Python script. The only
JavaScript on the site is the gallery's image viewer; everything else works
without it.

Works are managed with `Manage artworks`, which also previews and publishes the site.

See `MUISTIINPANOT.md` for the original design notes, `PLAN.md` for the
full build plan this project followed, and `BACKLOG.md` for what is still to
do.

## Managing artworks

Everything about your works lives in a database, and you manage it with a small
tool that runs on this computer. **Double-click `Manage artworks`.** It opens in your
browser at `http://127.0.0.1:5000`.

From there you can:

- **Add a work** — title, year, medium, size, tags, photograph, and so on.
- **Edit anything** about a work you already have.
- **Record a sale** — date, price paid, and the buyer's name and contact details.
- **Choose what appears on the website** with the Shown tick on each work.
- **Sort works for the gallery filter** with a category (painting, drawing or
  other) and website tags. See *The gallery filter* below.
- **Archive** a work to take it off the site while keeping its record, or delete
  it permanently behind a typed confirmation.
- **Preview** the website as it would look, then **Publish** it live.

Close the window to stop the tool. It listens only on this machine, so nothing
is reachable from the internet and there is no password to manage.

> **Can't find it in File Explorer?** Windows hides file extensions by
> default, so the three scripts show up as **Manage artworks**, **Preview
> site** and **Rebuild site**, without the `.bat` on the end. To see full
> filenames, open the **View** menu in File Explorer, go to **Show**, and
> tick **File name extensions**.

### What is private and what is published

| private, never leaves this computer | published on the website |
|---|---|
| buyer name, email, phone, address | title, year, medium, size |
| price actually paid, date sold | asking price, if you set one |
| sale notes, private notes | description, photograph |
| private tags, exhibitions | whether it is sold |
| | category and website tags (for the gallery filter) |

The website is built from a fixed list of safe columns in `db.py`
(`PUBLIC_COLUMNS`). No buyer field is in that list, so personal data cannot reach
the published pages even by accident. The database file itself is excluded from
git and is never pushed.

### Backups

After every change the database is copied to
`OneDrive/nettisivut-backup/`, together with a full spreadsheet export that
*does* include the buyer details. That export is the escape hatch: your records
stay readable in Excel without this tool. To recover, copy `artworks.db` back
into `data/` and rebuild.

### Status and what the site shows

Each work has a real status, and the website follows it:

| real status | asking price | the site shows |
|---|---|---|
| In my possession | set | the price and an Order button |
| In my possession | blank | "price on request" and an ask button |
| Sold | — | a SOLD marker, no order button |

Use *Override what the site says* on a work to force something else, for example
to mark a piece "not for sale".

### The gallery filter

The gallery page has three menus above the pictures: **Category**, **Years**
and **Tags**. Each lists only what your works actually have, with a count,
and a menu with nothing in it is left out. Today only Years appears, because
no work has a category or website tags yet (see `BACKLOG.md`).

- **Category** is chosen per work in Manage artworks. Paintings are split into
  *small* and *large* automatically: large means the longest side is at least
  50 cm. The cut-off is `LARGE_PAINTING_CM` near the top of `build.py`. A
  painting with no size is listed under Paintings only.
- **Years** come from each work's year.
- **Tags** come from the *Website tags* box, separated by commas, with a
  Finnish version in the box next to it. These are separate from your
  *private tags*, which are never published.

The filter needs JavaScript. Without it the gallery simply shows every work.
Clicking a thumbnail at the top of the gallery scrolls down to that work in
the list; clicking the large picture there opens the viewer.

### Editing the text pages

The site is published in two languages. English lives at the root, Finnish
under `/fi/`. Each language has its own folder of hand-written pages, and
they are separate texts rather than translations of each other:

| file | page |
|---|---|
| `content/en/home.html`, `content/fi/home.html` | front-page introduction |
| `content/en/about.html`, `content/fi/about.html` | bio and portrait |
| `content/en/order.html`, `content/fi/order.html` | payments, delivery, returns |
| `content/en/terms.html`, `content/fi/terms.html` | terms of purchase |

**Edit both languages when you change something**, or the two versions will
drift apart. Everything else — navigation, buttons, status labels, the
footer — is translated once in the `LANGUAGES` table near the top of
`build.py`.

Painting titles come from the database. Fill in the Finnish title, medium or
description in the admin tool to give a work Finnish wording; leave them blank
and the English text is shown on the Finnish pages too.

After editing any of these, double-click `Rebuild site` to apply the change.

## Previewing

Double-click `Preview site`. It starts a small local server and opens the
site in your browser at `http://localhost:8000`. Close the server window
when you're done.

## Publishing

The site is published from the `docs/` folder via GitHub Pages (Settings →
Pages → Deploy from branch `main`, folder `/docs`). The **Publish** button
in `Manage artworks` does this for you; from a terminal it is:

```
git add -A
git commit -m "Add <painting title>"
git push
```

The live site updates within a minute or two.

## First-time setup

Requires [Python 3.10+](https://www.python.org/downloads/) — check
"Add python.exe to PATH" during install, since `Rebuild site` and
`Preview site` both use the `py` launcher that the installer registers.

```
py -3 -m pip install -r requirements.txt
```

`Rebuild site` runs this automatically every time, so you only need this step
if you want to run `python build.py` yourself from a terminal instead of
double-clicking.

## Project layout

```
data/artworks.db        the artwork database — source of truth, NOT in git
admin.py                the admin tool, started by "Manage artworks"
db.py                   database schema, and the list of columns safe to publish
content/en, content/fi  hand-written text pages, one folder per language
originals/               full-resolution photos (not committed to git)
templates/               Jinja2 page templates
build.py                 the generator — reads the above, writes docs/
docs/                    the published site (English at root, Finnish in docs/fi/)
palette.jpg              the site's color palette, sampled from a photo
```

`docs/` is regenerated by `build.py` every time — don't hand-edit files in
it (except one-off hand-placed assets noted below), your changes will be
overwritten on the next build.

### Hand-placed assets (not generated by build.py)

- **Background music**: put an MP3 at `docs/audio/track.mp3` and rebuild —
  the audio player appears in the footer automatically once that file
  exists, and is omitted (not broken) while it doesn't.
- **Site icon**: `docs/img/icon-32.png` and `icon-180.png`, the RL monogram
  shown in the browser tab.
- **Font files**: `docs/fonts/`, Inter in two parts (basic Latin, and
  extended Latin for accented letters), plus its licence.
- **Custom domain**: `docs/CNAME`, containing `www.roniluokkamaki.com`.
  GitHub Pages reads it to know which domain the site answers on.

### Settings at the top of `build.py`

- `INSTAGRAM_HANDLE` — your handle without the `@`. While it is empty the
  Instagram link is left out of the footer entirely, rather than pointing
  somewhere wrong. Set it to switch the icon on.
- `SITE_URL` — the site's public address, `https://www.roniluokkamaki.com`.
  It is used for the `hreflang` tags that tell search engines which page is
  the English one and which is the Finnish one.

## Custom domain

The site lives at `www.roniluokkamaki.com`. The domain is registered at
Domainhotelli, its DNS is on Cloudflare's free plan, and the site is hosted
on GitHub Pages with HTTPS. See **`INFRASTRUCTURE.md`** for the full setup,
costs, renewal date, DNS records, and what to check if the site stops
loading.

## Design decisions on record

- **Color theme**: sampled from a Carhartt Canvas Script Cap (see
  `palette.jpg` and the `:root` variables at the top of
  `docs/css/style.css`). `--surface` is the cap fabric, `--accent` is the
  embroidery thread, `--rose` is that same mint hue rotated to a
  blue-leaning red.
- **Typography**: Inter throughout (changed from monospace on 17.10.2026),
  including headings, which are regular weight, uppercase and letter-spaced.
  The font files are in `docs/fonts/` and served from the site itself, not
  from Google Fonts, so visitors' browsers don't contact Google. Inter is
  free to use under the SIL Open Font License (`docs/fonts/Inter-OFL.txt`).
- **No divider lines** between sections (removed 17.10.2026); sections are
  separated by space alone.
- **Contact**: roni.luokkamaki@gmail.com, shown both as a mailto link and
  as plain text (per painting on the Order button, and in the footer).
- **Order terms**: collection in Helsinki, or shipping within Finland by Matkahuolto/UPS from 15 EUR; payment agreed per order, usually MobilePay or bank transfer; made-to-order work exempt from exchange/return. See `content/en/order.html` and `content/fi/order.html`.
- **No browse-by-category section** on the gallery page — the thumbnail
  grid and full list are the whole gallery. `theme` stays in the
  catalogue for possible future use but isn't shown anywhere yet.

## Troubleshooting

**"Python was not found" / opens the Microsoft Store** — this happens when
something runs the bare `python` command and Windows intercepts it with a
broken shortcut. `Rebuild site` and `Preview site` use `py -3` instead, which
avoids this; if you see the Store-redirect message anyway, Python isn't
installed yet — see **First-time setup**.

**A painting is missing from the website** — open `Manage artworks` and check the
Shown tick on that work. A work with no photograph cannot be shown, and the
tool says so when you try.

**The admin tool will not start** — something else may already be using port
5000. Close the other program, or close and reopen `Manage artworks`.
