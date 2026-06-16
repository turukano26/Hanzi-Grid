# Production Readiness Assessment

_Assessed 2026-06-16. Overall: **close, but not quite** — the app logic is production-ready; the gaps are in the deploy story and some uncommitted work._

## Blockers

_None._

## Should-fix before shipping

- **`--skip-downloads` flag is inverted (footgun).** In `rebuild_db.py`,
  `download=args.skip_downloads`, and `run_step` *strips* each importer's
  `--skip-download` when `download` is true. Net effect: `rebuild_db.py
  --skip-downloads` makes the importers **download fresh**, while `rebuild_db.py`
  with no flag uses cached `data/`. The `Dockerfile` only works because of this
  inversion (its `--skip-downloads` triggers the downloads that build the DB).
  It works today, but the flag does the opposite of its name — fix the logic or
  rename it before someone "corrects" it and breaks the image build.
- **No `.dockerignore`.** `Dockerfile` does `COPY . .` with no `.dockerignore`,
  so the image pulls in `venv/`, `.git/`, the 96 MB local `.db`, and `data/`.
  The build still works (the DB is rebuilt via fresh downloads), but the image is
  needlessly bloated. Add a `.dockerignore`.
- **Dead dependencies:** `requirements.txt` lists `pandas` + `pyarrow` (the
  heaviest installs) but the parquet stage is gone — zero imports in `app.py` /
  `scripts/` / `transcriptions/`. Drop them; the image shrinks a lot.
- **No input validation on routes.** `process_click_on_character` does
  `payload['character']` on raw `request.get_json()` → a malformed/empty body is
  an unhandled 500. Same for `request.form['searchString']`. A public endpoint
  should 400 gracefully. There's also a literal `return "wtf"` for an unknown
  `searchType`.
- **`runtime.txt` is missing** — no pinned Python version for Heroku, and
  `requirements.txt` is fully unpinned (`flask`, `gunicorn`, …). A surprise
  major-version bump can break a deploy silently. Pin them.

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
  `Dockerfile` runs `rebuild_db.py --skip-downloads`, and the importers
  (`import_unihan.py` etc.) download their own sources (Unihan.zip, CC-CEDICT,
  KANJIDIC2, CC-Canto, libhangul) into `data/` at build time and fill the DB from
  them. So neither the gitignored `omnihanzi.db` nor a committed `data/` is
  required for the Docker image. (See the inverted-flag note under Should-fix for
  why `--skip-downloads` is what triggers the downloads.)
