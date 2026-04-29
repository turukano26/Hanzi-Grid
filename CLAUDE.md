# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**omni-hanzi** — a Flask web app for browsing and studying CJK (Chinese/Japanese/Korean/Vietnamese) characters. Users select a character set (HSK, Jōyō, etc.), click characters on a grid to see multilingual readings/definitions in a side panel, and can color-code characters with persistent localStorage state.

## Running the app

```bash
# Development
source venv/bin/activate
python app.py          # runs on http://localhost:5000 with debug=True

# Production (as on Heroku)
gunicorn app:app
```

There are no tests currently (the `tests/` and `info_sections/` directories contain only type definition stubs).

## Architecture

```
app.py                        # Flask backend — all routes + data loading
templates/index.html          # Single-page HTML shell (Jinja2)
static/script.js              # All frontend logic (vanilla JS, no build step)
static/styles.css             # Styles
charactersets/*.json          # Character set definitions (HSK, Jōyō, JLPT, etc.)
df.parquet                    # Kanjidic/Unihan data (readings, frequency, grade)
mandarin_eng_dictionary.parquet  # CC-CEDICT-derived Mandarin definitions
info_sections/definitions.py  # TypedDict shapes for the infobox JSON protocol
```

### Data flow

1. On page load, `fetchCharacterSetNames()` → `/get_character_set_names` → populates the dropdown.
2. Selecting a character set calls `fetchCharacterSet()` → `/get_character_set` → `generateMacroGrid()` renders `<span data-unicode="…">` cells.
3. Clicking a cell calls `fetchCharacterInfo(character)` → `/process_click_on_character` (POST JSON) → `create_character_info_sheet()` queries both parquet DataFrames → returns a dict whose keys (`mandarin`, `cantonese`, `tang`, `japanese_kun`, `japanese_on`, `korean`, `vietnamese`) are rendered client-side by `renderInfoBoxFromData()`.
4. The search bar calls `/get_search_results` with `searchString` + `searchType` (Pinyin, Romaji, or Character); results are highlighted in the grid and shown in the search column.

### Key design points

- Both parquet files are loaded once at startup into module-level DataFrames (`char_info_df`, `mand_def_df`) — only the columns actually used by routes are loaded to keep memory low.
- `df.parquet` is indexed by Unicode character; lookups use `char_info_df.loc[character]`.
- Character coloring is stored entirely in `localStorage` keyed by hex Unicode codepoint (e.g. `"4e00"` → `"#ff6060"`). Export/import serializes this as JSON.
- Language toggles (checkboxes in the popup menu) are also persisted to `localStorage` by checkbox `id`.
- `info_sections/definitions.py` defines the TypedDict contract between `create_character_info_sheet()` and `renderInfoBoxFromData()` — keep these in sync when adding new section types.

### Character set JSON format

```json
{
  "label": "HSK Simplified",
  "value": [
    { "label": "HSK 1", "value": "一二三四五六七八九十" },
    ...
  ]
}
```

Each file in `charactersets/` follows this shape. `character_sets.json` at the root appears to be an older/alternate version of the same data.
