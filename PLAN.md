# Plan: painting portfolio site ("nettisivut")

## Context

The design notes in `MUISTIINPANOT.md` describe a hand-coded, 90s-spirited, English-language
portfolio and light web store for paintings. The project folder is otherwise empty. This plan
turns the notes into an architecture and a phased build order, from the general level down to
the individual files. Decisions confirmed in the interview:

- **Hosting:** GitHub Pages, published from the `docs/` folder of this repo.
- **Language:** English only.
- **Scale:** 15 to 40 paintings at launch, a few added per year.
- **Content pipeline:** one CSV catalogue + a local Python generator writes static HTML.
  The published site is pure HTML/CSS. The only JavaScript is the gallery lightbox.
- **Gallery:** one scrollable page with every painting and its details, plus a thumbnail grid
  that opens a lightbox (prev/next, zoom). Category browsing by theme, year and technique.
- **Music:** native `<audio controls>` in the footer of every page, off by default, restarts
  on navigation. No JS.
- **Mood:** cyberpunk underground carried by color (placeholder theme), monospace typography
  everywhere, texture (scanlines, ASCII dividers, pixel icons) and terse copy.
- **Defaults:** newest painting first; originals stay out of git; block-capital display font
  for headings (existing OFL font, self-hosted).

Tooling verified on this machine: Python 3.14 + Pillow 12, git 2.53, gh 2.89.
Jinja2 is not yet installed (one `pip install`).

---

## 1. Architecture

```
data/paintings.csv  ─┐
originals/*.jpg     ─┤──►  build.py  ──►  docs/   (committed, served by GitHub Pages)
templates/*.html    ─┤        │
content/*.html      ─┘        └── validates CSV, resizes images, checks internal links
```

- **Source of truth** is `data/paintings.csv`. Adding a painting = one CSV row + one photo,
  then `python build.py`, then commit and push.
- **Generator** `build.py` (Python, Jinja2 for templates, Pillow for images). Runs locally.
  No CI, no build service: what is in `docs/` is exactly what is served.
- **Output** `docs/` contains readable, indented HTML (no minification) so the result still
  reads like hand-coded 90s markup.
- **Runtime dependencies of the site: none.** No CDN, no fonts from Google servers, no
  analytics. Font, audio and images are all self-hosted.

### Repo layout

```
nettisivut/
├── MUISTIINPANOT.md
├── README.md              how to add a painting, build, preview, publish
├── build.py               generator + image pipeline + link check
├── requirements.txt       jinja2, pillow
├── .gitignore             originals/, __pycache__/
├── data/
│   └── paintings.csv      catalogue (source of truth)
├── content/               hand-written page texts (HTML fragments)
│   ├── home.html
│   ├── about.html
│   └── buying.html
├── templates/             Jinja2
│   ├── base.html          <head>, nav, footer (email, audio player, last-updated)
│   ├── page.html          wraps a content fragment
│   ├── gallery.html       grid + category index + full list
│   └── 404.html
├── originals/             full-res painting photos, NOT in git
│   └── <id>.jpg
└── docs/                  published site (GitHub Pages root)
    ├── .nojekyll
    ├── index.html
    ├── gallery.html
    ├── about.html
    ├── buying.html
    ├── 404.html
    ├── css/style.css
    ├── js/lightbox.js
    ├── fonts/<display-font>.woff2
    ├── img/profile.jpg
    ├── img/ui/            pixel icons, dividers
    ├── img/paintings/<id>-thumb.jpg | -full.jpg | -zoom.jpg
    └── audio/track.mp3    (added when the track is finished)
```

---

## 2. Catalogue: `data/paintings.csv`

| column | notes |
|---|---|
| `id` | slug, unique; used for filenames and `#anchors` (e.g. `red-harbour-2024`) |
| `title` | |
| `year` | integer |
| `technique` | free text, but consistent spelling (used as a category) |
| `theme` | theme or series name (used as a category) |
| `width_cm`, `height_cm` | integers |
| `price_eur` | blank unless `status` is `for_sale` |
| `status` | `for_sale` / `sold` / `not_for_sale` |
| `description` | optional, one or two sentences |
| `image` | filename in `originals/` |

`build.py` validates: unique ids, allowed status values, price present iff for sale, image
file exists, no empty required fields. Build fails loudly on any error.

---

## 3. Pages

Shared by all pages (`base.html`): text nav `HOME | GALLERY | ABOUT | BUYING` at the top,
ASCII divider, footer with email as text, the audio player, "last updated <date>" and a
copyright line. `<meta viewport>`, `<meta description>`, favicon.

1. **index.html** — profile picture (passport-photo shot), short intro, link into the
   gallery, three newest works as thumbnails.
2. **gallery.html** — three blocks, generated from the CSV, newest first:
   1. *Thumbnail grid* of all works. Each thumb is `<a href="#<id>">` with data-attributes
      for the lightbox (`data-full`, `data-zoom`, `data-title`, `data-caption`).
   2. *Browse by* index: three plain link lists (by theme, by year, by technique), each
      entry jumps to `#<id>`. Works without JS.
   3. *Full list*: one `<section id="<id>">` per painting: full-size image, title, year,
      technique, size, price or status, **Buy** mailto link, **View closer** link that
      opens the lightbox in zoom mode (fallback href = the zoom image).
3. **about.html** — bio text, profile picture, email as text.
4. **buying.html** — how to buy: email inquiry, shipping, payment, what happens after
   "sold". Text written by the user; placeholder headings until then.
5. **404.html** — plain page with the nav.

**Buy link:** `mailto:<email>?subject=Painting inquiry: <title> (<id>)` with a short body,
URL-encoded by the generator. The address is also printed as plain text next to it.

---

## 4. Image pipeline (in `build.py`)

From `originals/<id>.jpg` produce, only if missing or older than the source:

| variant | longest side | JPEG quality | use |
|---|---|---|---|
| `-thumb` | 400 px | 80 | grid, front page |
| `-full` | 1400 px | 85 | full list, lightbox default |
| `-zoom` | 2800 px | 85 | lightbox zoom only, loaded on demand |

Convert to sRGB, strip EXIF, write `width`/`height` attributes into the HTML to avoid layout
shift, `loading="lazy"` on grid and list images. Profile picture is prepared by hand once.

---

## 5. CSS: `docs/css/style.css`

- Hand-written, single file, no preprocessor.
- **Theme as CSS custom properties** on `:root` (`--bg`, `--fg`, `--accent-1`, `--accent-2`,
  `--border`) with placeholder values (dark warm-grey base, muted lime and pink accents).
  Deciding the real theme later is a five-line edit.
- **Typography:** display font (self-hosted woff2, OFL block-capital face) for headings and
  nav; monospace stack (`ui-monospace, "Courier New", monospace`) for everything else.
  Candidate display fonts to pick from in Phase 1: Permanent Marker, Architects Daughter,
  Patrick Hand SC, Amatic SC, Rock Salt.
- **Layout:** semantic HTML, max-width ~900px, 1px solid borders around boxes to get the
  table-like look, no rounded corners, no shadows, no transitions outside the lightbox.
  Thumbnail grid via `grid-template-columns: repeat(auto-fill, minmax(140px, 1fr))`.
  Single column under 600px, nav wraps.
- **Texture:** subtle scanline overlay via `repeating-linear-gradient` on a fixed
  `pointer-events:none` layer; ASCII-art dividers as text; a few tiny pixel icons.
- No `<table>` for layout: it breaks phones and screen readers. The look comes from CSS.

---

## 6. Lightbox: `docs/js/lightbox.js` (the one dynamic exception)

Vanilla JS, no dependencies, roughly 150 lines, progressive enhancement:

- Without JS: grid thumbs jump to the painting's section; "View closer" opens the zoom image.
- With JS: clicking a thumb opens a fixed dark overlay showing the `-full` image fitted to the
  viewport, caption (title, year, size, price/status), prev/next buttons, arrow keys, Esc,
  click-outside and × to close. Adjacent images are preloaded.
- **Zoom:** a toggle swaps to the `-zoom` image at natural size inside an `overflow:auto`
  container; panning is native scrolling and touch drag. Toggle again to fit.
- Data comes from the grid links' data-attributes, so it also works from `file://`.
- Accessibility: `role="dialog"`, `aria-modal`, focus trapped while open and returned on close,
  body scroll locked.

---

## 7. Music

`<audio controls preload="none" src="audio/track.mp3">` in the footer of every page, labelled
"Background music (own track)". Off by default, browser's own play/pause and mute. Restarts on
navigation, which is accepted. `preload="none"` keeps page loads fast. A build flag omits the
element until the mp3 exists, so no broken player ships.

---

## 8. Publishing

- `git init`, first commit, `gh repo create nettisivut --public --source . --push`.
- GitHub Pages: Deploy from branch `main`, folder `/docs`. `docs/.nojekyll` present.
- Custom domain later by adding `docs/CNAME`.
- Workflow after launch: edit CSV or content, `python build.py`, commit, push. Live in about
  a minute.

---

## 9. Build order

**Phase 0 — content (user, can run in parallel with Phases 1 to 3)**
- Photograph paintings, drop files in `originals/`, fill `data/paintings.csv`.
- Profile photo, intro text, about text, buying text.
- Pick the display font; decide colors (can stay placeholder); finish the track (can wait).

**Phase 1 — skeleton and first publish**
- Repo init, layout above, `requirements.txt`, `.gitignore`, README.
- `build.py` that renders `base.html` + the four static pages + 404 from content fragments.
- `style.css` with theme variables, fonts, nav, footer, mobile rules.
- Publish to GitHub Pages immediately so every later step is checked live.

**Phase 2 — gallery generation**
- CSV loader with validation, image pipeline, `gallery.html` template (grid, category
  index, full list), mailto buy links, newest-first ordering, three newest on the front page.

**Phase 3 — lightbox**
- `lightbox.js` as specified in section 6, including keyboard and touch behaviour.

**Phase 4 — mood and music**
- Scanlines, ASCII dividers, pixel icons, final typography pass, audio player wiring.

**Phase 5 — QA and launch**
- Everything in the verification section below, then README finalisation.

---

## 10. Verification

- **Build:** `python build.py` exits 0; deliberately broken CSV rows (duplicate id, missing
  image, for_sale without price) make it fail with a clear message.
- **Internal links:** `build.py --check` walks every `href`/`src` in `docs/` and confirms the
  target exists, including `#anchors`. Zero failures is the bar for "no broken links".
- **Local preview:** `python -m http.server -d docs 8000`.
- **No-JS test:** disable JavaScript in DevTools; grid thumbs must jump to sections and
  "View closer" must open the zoom image.
- **Mobile:** Chrome device mode at 400px width, screenshots of every page via the
  claude-in-chrome tools; no horizontal scroll, nav readable, grid reflows.
- **Browsers:** Chrome, Firefox and Edge locally; Safari on an iPhone if available.
- **Performance:** Lighthouse in Chrome, targets performance and accessibility >= 90 on the
  gallery page; total gallery page weight with thumbs under ~2 MB for 40 works.
- **HTML validity:** paste each page into validator.w3.org/nu at the end of Phases 1 and 2.
- **Live:** after each push, open the GitHub Pages URL and repeat the link check against it.
