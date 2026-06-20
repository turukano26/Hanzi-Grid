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

## Tests

```bash
source venv/bin/activate
python -m unittest discover -s tests -t .     # run everything
python -m unittest tests.test_zhuyin -v       # one module
```

`tests/` covers the `transcriptions/` converters (one `test_<module>.py` per
system), using stdlib `unittest` only — no extra dependency, and the files are
also collectable by `pytest tests/` if it's installed. Each holds a table of
`input → expected` cases; the romanization/Bopomofo expectations are
ground-truth (checked against the standards), the IPA ones follow each module's
documented scheme.

`test_resolve_end_to_end.py` is the one DB-backed test: it drives
`build_sections()` for a character click through the real resolve chain
(`_iter_groups`/`_handler_readings`/`_fetch_reading_rows`/`_resolve_ts_value`/
`TRANSFORMS`), checking a Pīnyīn-only Mandarin reading fans out to its derived
systems. It needs the locally-built `omnihanzi.db` (gitignored) and **skips
cleanly when the DB is absent**, so a fresh checkout / CI stays green. The Flask
routes themselves (request parsing, JSON envelopes) are still untested.

## Architecture

```
app.py                          # Flask backend — all routes, SQLite + parquet data loading, kana→romaji
templates/index.html            # Single-page HTML shell (Jinja2)
static/script.js                # All frontend logic (vanilla JS, no build step)
static/styles.css               # Styles
charactersets/*.yaml            # Character set definitions (hand-authored v2 YAML; not in the DB)
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
- Character sets are **not** in the DB: they are file-based v2 YAML documents in `charactersets/`,
  loaded directly by `app.py` (see "Character set YAML format" below). Most are hand-authored; the
  HSK 3.0 set is generated from a CSV by `scripts/generate_hsk30_charset.py`.

### Building the database

`scripts/rebuild_db.py` deletes and rebuilds `omnihanzi.db` end to end:

```bash
python scripts/rebuild_db.py                 # download all sources fresh (default)
python scripts/rebuild_db.py --skip-downloads  # reuse cached data/ dumps instead
```

It runs, in order: `create_db.py` (apply `schema.sql`) → `import_unihan.py` →
`import_kanjidic2.py` → `import_cedict.py` → `import_cccanto.py` → `import_libhangul.py` →
`dedup_readings.py`. Each importer can be run standalone with `--db`
and `--skip-download`. Raw
sources live under `data/` (Unihan, CC-CEDICT, CC-Canto, KANJIDIC2, libhangul), which is gitignored along with
the `.db`. (Character sets are not part of this pipeline — they are hand-authored YAML files in
`charactersets/`, with HSK 3.0 generated separately by `scripts/generate_hsk30_charset.py`.)

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
transform (`_kana_to_romaji` / `_ROMAJI` live in `transcriptions/romaji.py`, imported by `app.py`), preserving
okurigana `.` and affix `-` markers — see `transcription_systems.derived_from_ts_id` / `transform`.

Korean **Revised Romanization** (`revised_rom`, ts 40) is likewise not stored: it derives from Hangul
(ts 41) via the `hangul_revised` transform (`hangul_roman.hangul_to_revised`, also imported by
`app.py`). This means every Hangul reading shows a romanization even where Unihan supplied no Yale
(e.g. 두음법칙 forms like 女's 여→"yeo"), and — being sort_order 1 — Revised Romanization is Korean's
default-on primary transcription. Korean **IPA** (`ipa`, ts 43) derives from the same Hangul (ts 41)
via the `hangul_ipa` transform (`hangul_roman.hangul_to_ipa`) — a broad Standard/Seoul transcription
sharing the module's jamo-decomposition machinery (tense consonants with U+0348, representative
unreleased codas). Korean isn't tonal, so it's a single IPA system (no tones/no-tones pair), default
off.

Mandarin **IPA** is similarly not stored: it derives from Pīnyīn (ts 1) via
`transcriptions/pinyin_ipa.py` (imported by `app.py`), a broad *Help:IPA/Mandarin*-style
transcription (tie-bar affricates, syllabic z̩/ʐ̩). There are two variants, both deriving from ts 1:
**IPA** (`ipa`, ts 5, transform `pinyin_ipa`) is phonemes only, and **IPA (with tones)**
(`ipa_tones`, ts 6, transform `pinyin_ipa_tones`) additionally appends a Chao tone letter per
syllable. Neither is the primary (sort_order 5/6), so both appear in the menu but start off.

Cantonese has the same pair, derived from Jyutping (ts 10) via `transcriptions/jyutping_ipa.py`:
**IPA** (`ipa`, ts 12, transform `jyutping_ipa`, phonemes only) and **IPA (with tones)**
(`ipa_tones`, ts 13, transform `jyutping_ipa_tones`). The Cantonese converter looks up the whole
final against a closed rime table (so vowel-length and i/u→ɪ/ʊ-before-velar allophony is tabulated,
not computed) and uses Jyutping's trailing tone digit.

Vietnamese IPA is also derived (from Quốc Ngữ, ts 50) via `transcriptions/quocngu_ipa.py`, but
additionally **split by dialect region** — the dialect being the interesting axis (Northern *tr* [tɕ]
vs C/S [ʈ], the Northern diphthongs /iə ɨə uə/ that surface as long monophthongs in the South, the
differing tone systems). Each dialect gets the same phonemes-only / with-tones pair the other tonal
languages have, for **six** systems: **IPA (Northern)** (`ipa_northern`, ts 51, transform
`quocngu_ipa_northern`) + **IPA (Northern, with tones)** (`ipa_northern_tones`, ts 54,
`quocngu_ipa_northern_tones`), and likewise Central (ts 52/55) and Southern (ts 53/56). Tones are Chao
tone letters (ˀ marks glottalisation). The module is a direct port of James Kirby's *vPhon* (GPL): it
segments a syllable into onset/glide/nucleus/coda/tone, looks each up against vPhon's rule tables,
then applies the dialect's surface transforms; the `_tones` variants only differ by appending the
syllable's tone. Verified syllable-for-syllable against vPhon over its full sample wordlist
(`tests/test_quocngu_ipa.py`).

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

### Character set YAML format

Each file in `charactersets/` is a v2 typed-block document, stored as **YAML** (parsed with
`yaml.safe_load`; the body is opaque to the server, returned to the client as JSON and rendered
entirely by `static/script.js`):

```yaml
version: 2
label: Jōyō Kanji
defaultScript: T     # optional: T/S/J form to show first (see "Script toggle" below)
blocks:
- type: text          # free-text block; `size` is a heading level (smaller = bigger)
  text: |-
    Intro paragraph. Multi-line text uses a literal block scalar.
  size: 4
- type: section       # collapsible group; nests via its own `blocks`
  id: first-grade
  title: First Grade
  size: 3
  blocks:
  - type: grid        # the character grid; `cells` is the raw cell string
    cells: 一二三四五六七八九十…
  - type: poem        # Japanese poem; one verse line per source line
    text: |-
      {草|くさ}の{戸|と}も
      {住替|すみかわ}る{代|よ}ぞ
```

Block `type`s are `text`, `section` (recursive), `grid`, and `poem`. `cells` may use the
Traditional/Simplified/Japanese variant syntax (e.g. `{萬T万SJ}`) parsed by `parseCells` in
`static/script.js`. These files are authored directly (not exported from the DB).

**Script toggle** (the top-bar 繁/简/日 buttons, `#scriptToggle`): like the poem reading-aid
toggle, it is shown only when relevant to the current set. While rendering, `collectScripts` gathers
which script tags (T/S/J) appear in the set's variant groups; `updateScriptToggle` then hides the
whole toggle for sets with no variant groups and, within it, hides any button for a form the set
doesn't use (so a trad/simp-only set like HSK shows just 繁/简, not 日). `resolveActiveScript` picks
which form is active on open: the user's persisted choice (`csScript`) when this set offers it,
otherwise the set's optional **`defaultScript`** (a top-level `T`/`S`/`J` key) when present, else the
first available form (fallback order T→J→S). It is applied without persisting, so the active button
is always a *visible* one yet the user's global choice is restored on a set that does offer it.

A `text` block with `interactive: true` makes its Han characters clickable study cells (the rest of
the text is inert). A `poem` block is the Japanese-poem variant of that: kanji render larger than
kana and stay clickable, and it supports two optional reading aids toggled from the top bar
(`#poemToggle`, shown only while a set contains a poem) — **furigana** (the kana reading shown as
ruby above its kanji) and **romaji** (a Hepburn line beneath each verse line). Furigana is authored
inline as `{base|reading}` groups, e.g. `{夏|なつ}{山|やま}に`; that same kana reading also feeds the
romaji line (`parsePoemLine` / `poemLineRomaji` in `static/script.js`). Romaji is produced by
`kanaToRomaji`, a JS port of `transcriptions/romaji.py` that must be kept in sync with it (verified
against the Python output). The toggles are global and persisted to `localStorage`
(`poemFurigana`/`poemRomaji`, furigana default-on); unannotated kanji simply contribute no romaji.

Romaji word spacing is **author-controlled**: a literal space in the poem source is a romaji word
boundary but is *not* rendered in the verse, so `{草|くさ}の {戸|と}も` shows as 草の戸も yet romanizes
as `kusano tomo` (and `{草|くさ} の {戸|と} も` → `kusa no to mo`). With no spaces the romaji runs
together (`kusanotomo`) — spacing is never auto-inserted, since that would mis-split okurigana.

When generating these files programmatically (see `scripts/generate_hsk30_charset.py`), dump with
`allow_unicode=True, sort_keys=False, width=10**9` and a custom `str` representer that uses a literal
block scalar (`|`) for multi-line strings — this keeps CJK readable and long `cells` strings on one
line.
