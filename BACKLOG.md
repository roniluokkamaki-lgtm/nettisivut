# Backlog

Things to do later, roughly in order of importance. Tick them off or delete
them as they are done.

## Fill in the missing artwork details

Everything below is done in **Manage artworks**, one work at a time. Only the
artist knows these facts, so none of them should be guessed.

Status on 17.10.2026, for the 19 works shown on the site:

| Missing | Works | Why it matters |
|---|---|---|
| Category (painting / drawing / other) | 19 | the gallery's Category filter stays hidden until works have one |
| Website tags | 19 | the Tags filter stays hidden until works have some |
| Real title (still "Untitled…") | 18 | fine if a work really is untitled |
| Year | 14 | works without a year don't appear under any year in the filter |
| Medium | 14 | shown under each work in the gallery |
| Size | 14 | shown in the gallery; also decides small vs large painting in the filter |
| Asking price | 19 | without one the site says "price on request" |
| Finnish title | 19 | optional; the English title is shown on the Finnish pages otherwise |
| Description | 19 | optional |

Website tags work best as a short, shared list (for example *still life,
landscape, portrait, travel*) reused across works, rather than new words for
every piece. Give each tag a Finnish version too, or the English word is shown
on the Finnish pages.

## Make the tests use a copy of the database

`tests/test_core.py` and `tests/test_edge_cases.py` run against the real
`data/artworks.db`. One privacy test writes made-up buyer details into the
*Untitled (Study: airport)* record and sets its private tags to `secrettag`,
and earlier runs left those made-up details behind (cleared on 17.10.2026).
The tests should copy the database to a temporary file and work on that, so
running them can never change real records. The groundwork exists: setting
the `NETTISIVUT_DB` environment variable points `db.py` at another database
file, and a copy used that way backs up beside itself instead of over the
OneDrive backup. Until then, check that record's
sale details after running the tests.

## Add your exhibitions

The Exhibitions page appears on the site once the first exhibition is entered
in Manage artworks (Exhibitions button). Posters are optional.

## Small things

- The private tags on *Untitled (Study: airport)* still read `secrettag`, a
  test value. Clear it in Manage artworks.
- Background music: add `docs/audio/track.mp3` when the track is ready.
- Instagram: set `INSTAGRAM_HANDLE` in `build.py` to show the footer icon.
