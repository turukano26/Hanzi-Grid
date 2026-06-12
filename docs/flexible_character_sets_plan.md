# Flexible Character Sets — Redesign Plan

## Goal

Replace the rigid, one-level character-set format with a flexible, recursive
**typed-block document** so a character set can contain: recursive subsections,
collapsible subsections, multi-character words, free-form Markdown text (not just
the grid), custom grid layouts, and future block types.

## Where things stand today

- The **live source** is the JSON files in `charactersets/`. `app.py` loads them
  at startup (`app.py:17-29`) and `/get_character_set` serves them verbatim.
- The DB tables `character_set_nodes` / `character_set_members`
  (`schema.sql:440-454`) exist and the importer populates them, but **the app
  never reads them**. They are not part of this redesign.
- Current format is locked to exactly one level:
  `{label, value: [{label, value: "<chars>"}]}`, rendered by `generateMacroGrid`
  (`script.js:527`) as an `<h1>` + a flat `.grid` of single-char `<span>`s. Each
  `<span>` is keyed by hex codepoint (`data-unicode`) for coloring / search /
  click-to-info.

## Decisions (locked)

- **Storage:** keep JSON files, richer schema. No DB work. User uploads deferred.
- **Multi-character words:** render as *grouped single-char cells*. A word is a
  tight visual run of normal per-character `<span>`s. Each char keeps its
  `data-unicode` key, so coloring, click→info, and search highlighting keep
  working unchanged. No info-sheet changes.

## Document schema (version 2)

A character set is `{version, label, blocks: [...]}`. Each block is a typed node;
`section` blocks nest recursively via their own `blocks` array.

```jsonc
{
  "version": 2,
  "label": "HSK (Simplified)",
  "blocks": [
    {
      "type": "section",
      "title": "Level 1",
      "description": "The 150 most common words.",   // optional, Markdown
      "collapsible": true,
      "collapsed": false,
      "blocks": [
        { "type": "text", "markdown": "Start here, then move on." },
        { "type": "grid", "columns": 12, "cells": ["的", "我", "你", "是"] }
      ]
    },
    {
      "type": "grid",
      "cells": [ { "word": "你好" }, "的", { "word": "谢谢" } ]
    }
  ]
}
```

### Block types

| `type`    | Props                                              | Renders as |
|-----------|----------------------------------------------------|------------|
| `section` | `title`, `description?` (MD), `collapsible?`, `collapsed?`, `blocks[]` | Heading (or `<details>`/`<summary>` when collapsible) + recursive children |
| `grid`    | `cells[]`, `columns?`, `gap?`                      | A `.grid` of cells with optional custom layout |
| `text`    | `markdown`                                          | Rendered Markdown prose |

### Cells

A `grid.cells` entry is **either**:
- a bare string `"的"` — one character cell (today's behavior), or
- an object `{ "word": "你好" }` — a multi-char word, rendered as a `.word`
  wrapper holding one normal char `<span>` per character (each independently
  colorable / clickable).

### Markdown

Yes — a character set can contain Markdown. It enters in two places:
1. `text` blocks (`{ "type": "text", "markdown": "..." }`) — free prose anywhere
   in the tree, between or around grids.
2. A `section`'s optional `description` field.

Both reuse the existing Markdown rendering path (already used for the info sheet /
`character_set_nodes.description`); no new dependency.

## Implementation steps

### 1. One-time conversion — `scripts/convert_charactersets.py`
Rewrite each existing file from v1 to v2:
`{label, value:[{label, value}]}` →
`{version:2, label, blocks:[{type:"section", title, blocks:[{type:"grid", cells:[...chars]}]}]}`.
Run once; commit the six converted files.

### 2. Backend — `app.py` (minimal)
- `/get_character_set` keeps returning the whole document; structure is now opaque
  to the server (pass-through). Names route unchanged.
- Add `_normalize_set()` on load: upgrade any still-v1 file in memory so a stray
  old file never breaks rendering.
- Optionally validate block `type`s on load and log unknown types.

### 3. Frontend — `script.js` (the real work)
- Replace `generateMacroGrid` with a recursive `renderBlock(block, container)`
  plus a `BLOCK_RENDERERS` map (mirroring the info sheet's `RENDERERS`):
  - `section` → `<details>`/`<summary>` when `collapsible` (native collapse,
    respects `collapsed`), else a plain heading; render `description` Markdown if
    present; then recurse over `block.blocks`.
  - `grid` → a `.grid` div; apply `columns`/`gap` via inline style
    (`grid-template-columns: repeat(N, …)`); iterate `cells`.
  - `text` → render `block.markdown`.
- Refactor `generateCharacterElements` into a per-cell renderer:
  - bare-string cell → one char `<span>` (unchanged behavior),
  - `{word}` cell → a `.word` wrapper containing one normal char `<span>` per
    character.
  - Each char span keeps its `data-unicode` key ⇒ coloring, click→info, and
    search highlight all keep working untouched.

### 4. CSS — `styles.css`
- `.word { display: inline-flex; gap: 0; }` — tight run, visually one word, still
  individually colorable.
- `<details>` / `<summary>` styling for collapsible sections.
- Honor per-grid `columns` (inline style overrides the default `.grid` template).

## Net effect

Recursion, collapsibles, multi-char words, Markdown prose blocks, and custom grid
layouts all land. The per-codepoint coloring / info / search machinery is never
touched. No DB changes. Six files converted once.

## Suggested rollout

Start with the converter + one converted file to eyeball the shape, then do the
remaining five files and the renderer.
```
