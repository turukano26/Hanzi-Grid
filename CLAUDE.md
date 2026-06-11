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

There are no live tests.

## Architecture

```
app.py                          # Flask backend — all routes, SQLite + parquet data loading, kana→romaji
templates/index.html            # Single-page HTML shell (Jinja2)
static/script.js                # All frontend logic (vanilla JS, no build step)
static/styles.css               # Styles
charactersets/*.json            # Character set definitions, generated from the DB
omnihanzi.db                    # SQLite database — the primary data store (gitignored)
schema.sql                      # Full DB schema + seed data (languages, transcription systems, sources)
data/                           # Raw source dumps: unihan/, cedict/, kanjidic2/ (gitignored)
scripts/                        # DB build pipeline (see below)
```

### Data layer: SQLite

**`omnihanzi.db`** (SQLite) is the single data store for everything the app serves — the
character info sheet (`/process_click_on_character`) and search (`/get_search_results`, both
Pinyin and Romaji). Opened once with `check_same_thread=False` and `PRAGMA journal_mode = WAL`.
Schema in `schema.sql`.

The old parquet stage (`df.parquet`, `mandarin_eng_dictionary.parquet`, pandas) is gone — search
now queries SQLite directly (see "Search" below). Their underlying data still enters the DB
through the `scripts/` importers (Unihan, Kanjidic2, CC-CEDICT, CC-Canto, libhangul).

### SQLite schema (key tables)

Normalized around characters → etymologies → readings → transcriptions/senses:

- `characters` (keyed by `codepoint`) → `etymologies` (per character + language) →
  `readings` (one distinct pronunciation; has `category` like `kun`/`on`, `tone`) →
  `reading_transcriptions` (a reading rendered in a `transcription_system`, e.g. Pinyin, Jyutping,
  Kana, Hepburn) and `senses` (definitions, each with their own `source_id`).
- Source attribution for readings is **not** on the reading row: it lives in the
  `reading_attestations(reading_id, source_id, notes)` junction (a reading can be attested by
  several sources), mirroring `etymology_sources`. `senses.source_id` stays inline.
- Lookups in `app.py` are by `codepoint` + `language_id` + `transcription_system_id`. Most of these
  IDs are resolved dynamically from the DB while building the info-box menu tree (`_build_info_tree`);
  the search helpers use a few hard-coded constants (`LANG_MANDARIN`, `LANG_JAPANESE`,
  `TS_PINYIN_NUM`, `TS_HEPBURN`, `TS_KANA`) that must match the seed data in `schema.sql`.
- Character sets live in `character_set_nodes` (self-referential tree via `parent_id`) +
  `character_set_members`. The JSON files in `charactersets/` are *generated* from these tables.

### Building the database

`scripts/rebuild_db.py` deletes and rebuilds `omnihanzi.db` end to end:

```bash
python scripts/rebuild_db.py                 # use cached data/ dumps
python scripts/rebuild_db.py                 # (add real downloads by NOT passing --skip-downloads internally)
```

It runs, in order: `create_db.py` (apply `schema.sql`) → `import_unihan.py` →
`import_kanjidic2.py` → `import_cedict.py` → `import_cccanto.py` → `import_libhangul.py` →
`import_character_sets.py` → `dedup_readings.py`. Each importer can be run standalone with `--db`
and `--skip-download`. Raw
sources live under `data/` (Unihan, CC-CEDICT, CC-Canto, KANJIDIC2, libhangul), which is gitignored along with
the `.db`.

`dedup_readings.py` is a post-import pass: each importer inserts readings independently, so the same
pronunciation under one etymology starts as several reading rows (one per source). The pass merges
readings that share an identical `(transcription_system_id, value)` within the same
`(etymology_id, kind, category, subcategory)`, unioning their `reading_attestations`,
`reading_transcriptions` and `senses` onto the lowest-id survivor. It is idempotent. Two
cross-system **bridge** passes handle readings that the generic rule misses because the same
pronunciation is spelled in two different systems: `merge_japanese_romaji` folds Unihan's Hepburn
rows onto their Kanjidic kana twins, and `merge_korean_yale` folds Unihan's Yale-only Korean rows
onto their Hangul twins (romanizing each Hangul to Yale via `hangul_roman.hangul_to_yale`, then
matching). In both, the native-script row (kana / Hangul) is the survivor; the Korean bridge keeps
Unihan's Yale value by moving it onto the survivor (it is not lossy, unlike the JA romaji).

`import_libhangul.py` imports libhangul's `hanja.txt` (a colon-delimited `reading:hanja:eumhun`
Korean→Hanja dictionary). It keeps only single-Hangul→single-Hanja entries and creates Korean
readings mirroring Unihan's shape (`LANG_KOREAN`, `kind='reading'`, Hangul under `TS_HANGUL=41`),
so `dedup_readings.py` merges them onto Unihan's identical Hangul readings. The optional eumhun
(음훈) string is stored **verbatim** as a second transcription under the `eumhun` system
(`TS_EUMHUN=44`). Eumhun is a transcription system but is rendered on its **own line like a
definition** rather than inline in the headword: `_fetch_reading_rows` in `app.py` splits the
eumhun value out of the inline `transcriptions` list and appends it to the row's `definitions`
(see `TS_EUMHUN` / `LIBHANGUL_SHORT` there).

### Data flow (request lifecycle)

1. On page load, `fetchCharacterSetNames()` → `/get_character_set_names` → populates the dropdown.
2. Selecting a set calls `fetchCharacterSet()` → `/get_character_set` → `generateMacroGrid()` renders
   one `<h1>` + grid of `<span data-unicode="…">` cells per sub-node.
3. Clicking a cell calls `fetchCharacterInfo()` → `/process_click_on_character` (POST JSON
   `{character, options: [enabled leaf ids]}`) → `build_sections()` queries SQLite and returns
   `{sections: [...]}`, a list of section objects each rendered client-side by `renderSections()` in
   `script.js`. `options` is the set of toggled-on menu leaves (persisted in `localStorage`); a group
   whose subtree has no enabled leaf is skipped server-side.
4. The search bar calls `/get_search_results` with `searchString` + `searchType` (Pinyin, Romaji,
   or Character); results are highlighted in the grid and shown in the search column.

### Info-sheet section shapes

The info sheet is **language-generic** since the infobox redesign: `build_sections()` emits a uniform
list of sections rather than per-language keys. Each section is
`{id, type, title, data}` (the `type`/`title` come from the group's `render`), where `type` selects a
client renderer in `script.js`'s `RENDERERS` map. There are three `type`s / handlers:

- `readings` (`_handler_readings`) → `{readings: [...]}`. Every Sinitic/Japonic/etc. reading group —
  Mandarin, Cantonese, Middle Chinese, Japanese on/kun, Korean, Vietnamese — uses this one shape. Each
  reading row is `{transcriptions: [{code, label, value}], tone, sources: [short_name…],
  definitions?: [{text, source}]}`. `transcriptions` holds only the enabled systems (resolved as
  `COALESCE(stored[ts], stored[derived_from])` then the system's `transform`); `definitions` is present
  only when a Definitions leaf is enabled.
- `image_gallery` (`_handler_glyph_images`) → `{images: [{url|data, attribution}]}` — historical glyphs.
- `key_value` (`_handler_attributes`) → `{rows: [{key, value, source}]}` — `character_attributes`.

A handler with nothing to return yields `{error: ...}`, and `build_sections()` drops that section
entirely (errors are never serialized).

Japanese readings are stored as kana and romanized to Hepburn at request time via the `kana_romaji`
transform (`_kana_to_romaji` / `_ROMAJI` live in `romaji.py`, imported by `app.py`), preserving
okurigana `.` and affix `-` markers — see `transcription_systems.derived_from_ts_id` / `transform`.

Korean **Revised Romanization** (`revised_rom`, ts 40) is likewise not stored: it derives from Hangul
(ts 41) via the `hangul_revised` transform (`hangul_roman.hangul_to_revised`, also imported by
`app.py`). This means every Hangul reading shows a romanization even where Unihan supplied no Yale
(e.g. 두음법칙 forms like 女's 여→"yeo"), and — being sort_order 1 — Revised Romanization is Korean's
default-on primary transcription.

### Search (`/get_search_results`)

`searchType` selects one of three branches, all returning `{"search": "<chars>"}`:

- **Character** — extracts Han characters from the query with a `\p{Script=Han}` regex.
- **Pinyin** — `_search_pinyin()`: matches Mandarin readings whose numbered-pinyin transcription
  (`TS_PINYIN_NUM`), with its tone digit stripped (`rtrim(value, '0123456789')`), equals the query —
  i.e. toneless pinyin, so `sheng` hits `sheng1`/`sheng4`/…. Ordered by Unihan `grade_level` (a coarse
  frequency proxy) then codepoint.
- **Romaji** — `_search_romaji()`: pulls every Japanese reading's `COALESCE(hepburn, kana)` value and
  romanizes it in Python via `_transform_kana_romaji` (the same path the info sheet uses, so
  directly-stored and kana-derived readings match alike), strips okurigana/affix punctuation, and
  compares to the query. Ordered by Kanjidic `frequency_rank` then Unihan `grade_level`.

The ordering is approximate: the DB has no Unihan `kFrequency` or Kanjidic grade (what the old parquet
search sorted on), so the available `frequency_rank` / `grade_level` attributes stand in.

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
