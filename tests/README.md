# Tests

Two suites, run from the project root with the admin tool closed:

    py -3 tests/test_core.py        validation, privacy, status, visibility, deleting
    py -3 tests/test_edge_cases.py  uploads, corrupt files, backups, detail photos

They work against the real database, so **take a copy of `data/artworks.db`
first** if you have unsaved work. Both suites clean up after themselves and the
data was verified unchanged afterwards, but they do create and delete records.

`test_edge_cases.py` deliberately does **not** call the Publish button: that
really does commit and push. An earlier version did, and pushed a junk commit
to the live repository.
