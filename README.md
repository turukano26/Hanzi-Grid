# omni-hanzi

A Flask web app for browsing and studying CJK (Chinese / Japanese / Korean / Vietnamese)
characters. Pick a character set, click any character on the grid to see its multilingual
readings and definitions in a side panel, search by Pinyin / Romaji / character, and
colour-code characters to track your study progress — all persisted locally in your browser.

It is built around a single normalized SQLite database (`omnihanzi.db`) assembled from
authoritative open data sources (Unihan, KANJIDIC2, CC-CEDICT, CC-Canto, libhangul), with a
zero-build-step vanilla-JS frontend.

---

## Features

### Character grid & study workflow
- **Selectable character sets** — choose from a dropdown of bundled sets (HSK 2.0/3.0, Jōyō,
  Jinmeiyō, JLPT, 通用规范汉字表, curated "Foundations", famous poems, and more). Your last
  selection is remembered.
- **Click-to-inspect** — click any character (in a grid, in interactive prose, or even inside
  the info panel itself) to load its full reading/definition sheet and show it enlarged.
- **Colour-coding** — paint characters with a colour picker or quick-pick swatches to mark
  them (e.g. learned / reviewing / unknown). Colourings persist in `localStorage` keyed by
  Unicode codepoint and are reflected everywhere the character appears.
- **Paint mode toggle** — switch between "inspect" clicks and "paint" clicks.
- **Hide/show colours** — temporarily hide all colourings (e.g. to self-test) without losing
  them; the hidden/shown choice is itself remembered.
- **Export / import** — save your colourings to a JSON file and re-import them on another
  device. Menu preferences are deliberately kept out of the colour export.
- **Clear all** — reset all saved data (with confirmation).
- **Resizable columns** — drag the dividers between the info, grid, and search columns.

### Script variants (Traditional / Simplified / Japanese)
- A **繁 / 简 / 日 toggle** switches the displayed glyph for sets that encode variant groups
  (e.g. `(東TJ东S)`). Each cell still records *all* of its variants' codepoints, so search
  matches a form even when it isn't the one currently displayed.
- A character set may declare a preferred default script, honoured until the user picks one.

### Rich, configurable info sheet
Clicking a character opens a per-language reading sheet. **Everything shown is toggleable**
through a nested checkbox menu (Menu → Languages), and your selection persists. The menu tree
is generated automatically from the database, so it only ever offers data that actually exists.

Languages / families modelled in the schema:
- **Sinitic** — Mandarin, Cantonese, Hokkien, Hakka, Shanghainese, Nanjing dialect, Middle
  Chinese, Old Chinese.
- **Japonic** — Tokyo Standard (on'yomi / kun'yomi), Kansai, Ryukyuan.
- **Koreanic** — Standard Korean, Jeju.
- **Vietic** — Northern / Southern Vietnamese.
- **Other** — Sino-Xenic (general).

(Leaves appear only for languages with imported data; the rest are scaffolding the schema
supports as sources are added.)

**Transcription systems** available per language (toggle each on/off independently):
- **Mandarin** — Pīnyīn, numbered Pīnyīn, Wade–Giles, Zhùyīn (Bopomofo), IPA, IPA with tones.
- **Cantonese** — Jyutping, Yale, IPA, IPA with tones.
- **Japanese** — Hepburn, Kunrei-shiki, Kana, IPA.
- **Korean** — Revised Romanization, Yale, Hangul, IPA, Eumhun (음훈).
- **Vietnamese** — Quốc Ngữ, IPA.

Many of these are **derived on the fly** rather than stored, so they're always available:
romaji from kana (Hepburn), Mandarin/Cantonese IPA from Pīnyīn/Jyutping (with optional Chao
tone letters), Korean Revised Romanization and IPA from Hangul, Wade–Giles from Pīnyīn, and
Japanese/Korean IPA from their native scripts.

Other info-sheet sections:
- **Definitions** — per-language glosses sourced from dedicated dictionaries (CC-CEDICT,
  CC-Canto, KANJIDIC2, libhangul eumhun). Toggleable per language.
- **Historical glyphs** — a gallery of historical/seal-script glyph images (when available).
- **Character attributes** — key/value facts (e.g. grade level, frequency rank).
- **Tone colouring** — readings are colour-coded by tone in the headword.
- **Source attribution** — hover any reading or definition to see which source attests it.

### Search
A search bar with a type selector returns matching characters, highlights them in the grid,
and lists them in a results column:
- **Pinyin** — toneless numbered-pinyin match (`sheng` → `shēng`, `shèng`, …), ordered by a
  frequency proxy.
- **Romaji** — matches Japanese on/kun readings romanized to Hepburn (kana-derived and
  directly-stored readings match alike), ordered by Kanjidic frequency rank.
- **Character** — extracts Han characters from the query (handy for pasting text).
- *(Radical / Meaning search are stubbed in the UI for future work.)*

---

## Architecture

```
app.py                 # Flask backend — routes, SQLite access, info-tree assembly, search
templates/index.html   # Single-page HTML shell (Jinja2)
static/script.js       # All frontend logic (vanilla JS, no build step)
static/styles.css      # Styles
transcriptions/        # Pure-Python romanization/IPA transforms (romaji, IPA, Wade-Giles…)
charactersets/*.yaml   # Character-set documents (v2 typed-block format), rendered client-side
schema.sql             # Full DB schema + seed data (languages, transcription systems, sources)
omnihanzi.db           # SQLite database — the single data store (gitignored)
scripts/               # DB build pipeline (importers + rebuild orchestrator)
data/                  # Raw source dumps: unihan/, cedict/, kanjidic2/, … (gitignored)
docs/                  # Design plans and critiques
```

### Data layer
`omnihanzi.db` (SQLite, WAL mode, one connection per thread) is the single store for everything
the app serves. It is normalized around
`characters → etymologies → readings → reading_transcriptions / senses`, with source
attribution tracked in junction tables. Lookups are by codepoint + language + transcription
system. The reading menu and most IDs are resolved dynamically from the DB at startup.

Transcription systems carry `derived_from_ts_id` + `transform` metadata, so a romanization or
IPA can be expressed as data ("Hepburn derives from Kana via `kana_romaji`") rather than as
special-cased code. The Python transforms live in `transcriptions/`.

### Request lifecycle
1. Page load → `/get_character_set_names` populates the dropdown; `/get_info_options` builds the
   language menu.
2. Selecting a set → `/get_character_set` returns a typed-block JSON document, rendered into the
   grid entirely client-side.
3. Clicking a character → `/process_click_on_character` (with the enabled menu options) returns
   a list of info-sheet sections.
4. Searching → `/get_search_results` returns matching characters to highlight.

See `CLAUDE.md` for a deeper tour of the schema, the info-sheet section shapes, the derivation
machinery, and the search internals.

---

## Running the app

```bash
# Development
source venv/bin/activate
python app.py                 # http://localhost:5000, debug=True

# Production (as on Heroku / containers)
gunicorn app:app
```

The app needs `omnihanzi.db` present (see below — it is gitignored).

### Docker

```bash
docker build -t omni-hanzi .   # builds the DB at image-build time
docker run -p 8081:8081 omni-hanzi
```

### Requirements
Python 3.11+, Flask, gunicorn, `regex`, and PyYAML (see `requirements.txt`).

---

## Building the database

`omnihanzi.db` is generated from open data sources, not checked in:

```bash
python scripts/rebuild_db.py                  # download all sources fresh (default)
python scripts/rebuild_db.py --skip-downloads # reuse cached data/ dumps
```

The pipeline runs, in order: `create_db.py` (apply `schema.sql`) → `import_unihan.py` →
`import_kanjidic2.py` → `import_cedict.py` → `import_cccanto.py` → `import_libhangul.py` →
`dedup_readings.py`. Each importer can also be run standalone with
`--db` / `--skip-download`. `dedup_readings.py` is an idempotent post-pass that merges duplicate
readings inserted independently by each importer (including cross-system "bridge" merges for
Japanese romaji↔kana and Korean Yale↔Hangul). Character sets are not part of this pipeline —
they are hand-authored YAML files in `charactersets/` (HSK 3.0 is generated from a CSV by
`scripts/generate_hsk30_charset.py`).

### Data sources
- **Unihan** (Unicode) — pan-CJK readings, definitions, attributes.
- **KANJIDIC2** — Japanese kanji readings (kana) and frequency.
- **CC-CEDICT** — Mandarin definitions.
- **CC-Canto** — Cantonese (Jyutping) definitions.
- **libhangul** — Korean Hanja↔Hangul readings and eumhun glosses.

---

## Character set format

Each file in `charactersets/` is a **v2 typed-block document** (`{version, label, blocks}`).
Blocks are rendered recursively client-side and can be:
- `grid` — a string of characters (with optional `(…)` variant groups) rendered as study cells;
- `section` — a titled, optionally collapsible group of nested blocks, with a 1–5 size scale;
- `text` — prose, optionally `interactive` so Han characters in the flow become clickable cells
  (used for reading passages like *Oku no Hosomichi*).

The server treats the document body as opaque — it's returned verbatim and rendered entirely in
the browser. New sets are added by dropping a JSON file into `charactersets/`.

---

## Persistence

All user state lives in the browser's `localStorage`:
- Character colourings, keyed by hex codepoint (e.g. `"4e00"` → `"#ff6060"`).
- Enabled info-sheet options (single `infoOptions` key).
- Selected character set, script variant, collapsed-section state, and colours-hidden flag.

There is no server-side user data and there are no accounts.
