# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**omni-hanzi** — a Flask web app for browsing and studying CJK (Chinese/Japanese/Korean/Vietnamese) characters. Users select a character set (HSK, Jōyō, JLPT, etc.), click characters on a grid to see multilingual readings/definitions in a side panel, search by Pinyin/Romaji/character, and color-code characters with persistent localStorage state.

## Running the app

```bash
# Development
source venv/bin/activate
python app.py          # runs on http://localhost:5000 with debug=True

# Production (as on Heroku)
gunicorn app:app
```

There are no live tests. `tests/` and `info_sections/` hold a not-yet-wired-up
infobox-section framework (see "Caveats" below).

## Architecture

```
app.py                          # Flask backend — all routes, SQLite + parquet data loading, kana→romaji
templates/index.html            # Single-page HTML shell (Jinja2)
static/script.js                # All frontend logic (vanilla JS, no build step)
static/styles.css               # Styles
charactersets/*.json            # Character set definitions, generated from the DB
omnihanzi.db                    # SQLite database — the primary data store (gitignored)
schema.sql                      # Full DB schema + seed data (languages, transcription systems, sources)
df.parquet                      # Legacy Kanjidic/Unihan data — still used by search routes
mandarin_eng_dictionary.parquet # Legacy CC-CEDICT Mandarin data — still used by Pinyin search
data/                           # Raw source dumps: unihan/, cedict/, kanjidic2/ (gitignored)
scripts/                        # DB build pipeline (see below)
info_sections/                  # WIP section-protocol framework — NOT imported by app.py yet
```

### Data layer: hybrid SQLite + parquet

The app is mid-migration from parquet to SQLite. Currently **both** are loaded at startup:

- **`omnihanzi.db`** (SQLite) is the source of truth for the character info sheet
  (`/process_click_on_character`). Opened once with `check_same_thread=False` and
  `PRAGMA journal_mode = WAL`. Schema in `schema.sql`.
- **`df.parquet`** and **`mandarin_eng_dictionary.parquet`** are still loaded into
  module-level DataFrames (`char_info_df`, `mand_def_df`) and used only by
  `/get_search_results` (Pinyin and Romaji search). Only the columns the routes use are read.

When extending search, the eventual goal is to query SQLite instead of parquet; for now the
two stores coexist.

### SQLite schema (key tables)

Normalized around characters → etymologies → readings → transcriptions/senses:

- `characters` (keyed by `codepoint`) → `etymologies` (per character + language) →
  `readings` (one distinct pronunciation; has `category` like `kun`/`on`, `tone`) →
  `reading_transcriptions` (a reading rendered in a `transcription_system`, e.g. Pinyin, Jyutping,
  Kana, Hepburn) and `senses` (definitions, each with their own `source_id`).
- Source attribution for readings is **not** on the reading row: it lives in the
  `reading_attestations(reading_id, source_id, notes)` junction (a reading can be attested by
  several sources), mirroring `etymology_sources`. `senses.source_id` stays inline.
- Lookups in `app.py` are by `codepoint` + `language_id` + `transcription_system_id`. The relevant
  IDs are hard-coded constants near the top of `app.py` (`LANG_MANDARIN`, `TS_PINYIN`, etc.) that
  must match the seed data in `schema.sql`.
- Character sets live in `character_set_nodes` (self-referential tree via `parent_id`) +
  `character_set_members`. The JSON files in `charactersets/` are *generated* from these tables.

### Building the database

`scripts/rebuild_db.py` deletes and rebuilds `omnihanzi.db` end to end:

```bash
python scripts/rebuild_db.py                 # use cached data/ dumps
python scripts/rebuild_db.py                 # (add real downloads by NOT passing --skip-downloads internally)
```

It runs, in order: `create_db.py` (apply `schema.sql`) → `import_unihan.py` →
`import_kanjidic2.py` → `import_cedict.py` → `import_cccanto.py` → `import_character_sets.py` →
`dedup_readings.py`. Each importer can be run standalone with `--db` and `--skip-download`. Raw
sources live under `data/` (Unihan, CC-CEDICT, CC-Canto, KANJIDIC2), which is gitignored along with
the `.db`.

`dedup_readings.py` is a post-import pass: each importer inserts readings independently, so the same
pronunciation under one etymology starts as several reading rows (one per source). The pass merges
readings that share an identical `(transcription_system_id, value)` within the same
`(etymology_id, kind, category, subcategory)`, unioning their `reading_attestations`,
`reading_transcriptions` and `senses` onto the lowest-id survivor. It is idempotent.

### Data flow (request lifecycle)

1. On page load, `fetchCharacterSetNames()` → `/get_character_set_names` → populates the dropdown.
2. Selecting a set calls `fetchCharacterSet()` → `/get_character_set` → `generateMacroGrid()` renders
   one `<h1>` + grid of `<span data-unicode="…">` cells per sub-node.
3. Clicking a cell calls `fetchCharacterInfo()` → `/process_click_on_character` (POST JSON) →
   `create_character_info_sheet()` queries SQLite and returns a flat dict whose keys
   (`mandarin`, `cantonese`, `tang`, `japanese_kun`, `japanese_on`, `korean`, `vietnamese`) are
   rendered client-side by `renderInfoBoxFromData()` in `script.js`. Each language is gated by a
   checkbox flag in the POST body (e.g. `chineseMandarinCheckbox`).
4. The search bar calls `/get_search_results` with `searchString` + `searchType` (Pinyin, Romaji,
   or Character); results are highlighted in the grid and shown in the search column.

### Per-language info-sheet shapes

`create_character_info_sheet()` returns different sub-shapes per language, each matched by a branch
in `renderInfoBoxFromData()`:

- `mandarin` → `{readings: [{pinyin_accent, tone, definitions: [...]}]}` — deduped by NFC-normalized
  pinyin, preferring CC-CEDICT (`source_id` 1) over Unihan (2).
- `cantonese` → `{segments: [{text, tone}]}`.
- `tang` (Middle Chinese) → `{text: "..."}`.
- `japanese_kun` / `japanese_on` / `korean` / `vietnamese` → `{items: [...]}`.
- Any language with no data returns `{error: "..."}`.

Japanese readings are stored as kana and converted to Hepburn romaji at request time by
`_kana_to_romaji()` / `_ROMAJI` in `app.py`, preserving okurigana `.` and affix `-` markers.

### Key design points

- Character coloring is stored in `localStorage` keyed by hex Unicode codepoint
  (e.g. `"4e00"` → `"#ff6060"`). Export/import serializes this as JSON.
- Language toggles (checkboxes in the popup menu) are also persisted to `localStorage` by checkbox `id`.

### Character set JSON format

```json
{
  "label": "Jōyō Kanji",
  "value": [
    { "label": "First Grade", "value": "一二三四五六七八九十…" },
    ...
  ]
}
```

Each file in `charactersets/` follows this shape (one level of `{label, value:string}` nodes;
`generateMacroGrid` renders exactly one level). The DB models a deeper tree, but the exported JSON is
flattened to this shape. `character_sets.json` at the root is an older/alternate copy of the same data.

## Caveats

- **`info_sections/` and `tests/` are aspirational and not wired in.** `app.py` does **not** import
  `info_sections`. The TypedDicts in `info_sections/definitions.py` describe a richer
  section/group protocol (`SectionJson`, `CharacterInfoResponse`) that the live code does *not* use —
  the actual contract is the flat dict described under "Per-language info-sheet shapes" above. Treat
  `info_sections/` as a planned refactor, not the current source of truth.
