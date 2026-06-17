# Production Readiness Assessment

_Assessed 2026-06-16 (last updated 2026-06-16). Overall: **shippable** — no blockers, and all should-fix items have been addressed. See Resolved._

## Blockers

_None._

## Should-fix before shipping

_None — all addressed; see Resolved._

## Non-issues (these are fine)

- `app.run(debug=True)` only runs under `python app.py`; gunicorn imports
  `app:app` and never hits it. Worth flipping to `debug=False` for hygiene, but
  not a security exposure in prod.
- No `SECRET_KEY` — correct, the app uses no sessions/cookies.
- WAL + per-thread read-only connections is a sound concurrency model for this
  workload.
- **`Procfile` has no DB-build step — not a concern.** The `Procfile`
  (`web: gunicorn app:app`) runs no `rebuild_db.py`, so a buildpack/git deploy
  would boot against an empty DB. But the production deploy is the `Dockerfile`,
  which rebuilds the DB at image-build time, so this never applies.

## Resolved

- **The threading fix is committed.** ✅
  The `_ThreadLocalDB` change in `app.py` — a production correctness fix (the old
  shared connection would corrupt under gunicorn's concurrent requests) — is now
  committed rather than a dirty working-tree change.
- **The Docker deploy rebuilds the DB from scratch — no DB or `data/` in git
  needed.** ✅ Originally flagged as a blocker ("DB won't exist"); that was wrong.
  `Dockerfile` runs `rebuild_db.py` at build, and the importers
  (`import_unihan.py` etc.) download their own sources (Unihan.zip, CC-CEDICT,
  KANJIDIC2, CC-Canto, libhangul) into `data/` at build time and fill the DB from
  them. So neither the gitignored `omnihanzi.db` nor a committed `data/` is
  required for the Docker image.
- **`--skip-downloads` flag de-inverted.** ✅ Previously the flag did the
  opposite of its name: `rebuild_db.py --skip-downloads` downloaded fresh and the
  bare command used cache. Fixed the inverted argument at the call site
  (`download=not args.skip_downloads`), so now no flag = download fresh and
  `--skip-downloads` = reuse cached `data/`, matching the docstring. The
  `Dockerfile` was updated to drop the flag so it still downloads fresh at build,
  and `CLAUDE.md`'s usage block was corrected.
- **Dead dependencies removed.** ✅ `pandas` and `pyarrow` (the heaviest
  installs, left over from the retired parquet stage — zero imports anywhere in
  the repo) were dropped from `requirements.txt`. Remaining: `flask`, `wheel`,
  `gunicorn`, `regex`.
- **`.dockerignore` added.** ✅ `COPY . .` no longer pulls `venv/`, `.git/`, the
  96 MB local `.db`, or `data/` into the image — the DB is rebuilt and the
  sources re-downloaded during the build, so those local copies were pure bloat.
  Kept what the build/runtime actually need (`charactersets/`, `overlay.json`,
  `templates/`, `static/`, `scripts/`, `schema.sql`, `transcriptions/`).
- **Route input validation added.** ✅ A shared `_bad_request()` helper now
  returns clean JSON 400s. `process_click_on_character` validates the body is a
  JSON object, `character` is a single-codepoint string, and `options` is a list;
  `get_character_set` and `get_search_results` check their required form fields.
  Also fixed two latent 500s/quirks: the `return "wtf"` for an unknown
  `searchType` is now a 400, and the unimplemented `Radical` branch (which fell
  through to a `None` return → 500) now returns empty results. Verified via the
  Flask test client across malformed and valid inputs.
- **Dependencies pinned.** ✅ `requirements.txt` now pins exact versions
  (`flask==3.1.3`, `wheel==0.46.3`, `gunicorn==25.1.0`, `regex==2026.2.28`) so a
  surprise upstream release can't silently change a build. The Python version is
  pinned separately by the `Dockerfile` base image (`python:3.11-slim`), so a
  Heroku-style `runtime.txt` isn't needed for the Docker deploy. (Note: the local
  venv is Python 3.12; the image is 3.11. All pins support both. Optionally
  tighten the base tag to an exact patch, e.g. `python:3.11.x-slim`, for fully
  reproducible builds.)
