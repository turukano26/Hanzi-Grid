# Flexible Character Sets — Redesign Plan (v2)

> Supersedes the original draft. Every decision below was settled in review; the
> reasoning is recorded in `flexible_character_sets_critique_review.md`.

## Goal

Replace the rigid one-level character-set format with a flexible, recursive
**typed-block document** so a character set can contain: recursively nested sections,
collapsible sections, free-form plain-text prose, and interactive reading passages
(classical texts) — not just a flat grid.

## Where things stand today

- The **live source** is the JSON files in `charactersets/` (committed to git). `app.py`
  loads *all* of them into memory at startup (`app.py:17-29`) and `/get_character_set`
  serves them verbatim.
- Current format is locked to exactly one level:
  `{label, value: [{label, value: "<chars>"}]}`, rendered by `generateMacroGrid`
  (`script.js:527`) as an `<h1>` + a flat `.grid` of single-char `<span>`s. Each `<span>`
  is keyed by hex codepoint (`data-unicode`) for coloring / search / click-to-info.
- The DB tables `character_set_nodes` / `character_set_members` (`schema.sql:440-454`) are
  populated by `scripts/import_character_sets.py` but **never read by the app**. They are
  removed by this redesign (see step 5).

## Decisions (locked)

- **Storage = JSON only.** JSON files stay the single canonical format. The unused DB
  character-set tables and the stale root `character_sets.json` are deleted. Word identity
  is concatenated codepoints, so sets never need to reference DB rows.
- **No Markdown, no new dependency.** Prose is plain text rendered via
  `textContent`/escaped (never `innerHTML`) — no parser, no sanitizer.
- **No grid `columns` / `gap`.** The grid keeps its existing responsive layout.
- **No special word unit.** No `{word}` cell type, no `.word` element. Grid/text content is
  bare characters. Words-as-units remain a *future* goal that builds nothing now.
- **Lazy loading.** Startup builds a `label → filepath` index; each set is parsed on demand.
- **Persistent collapse.** Collapsed/expanded state is saved to `localStorage`, keyed by a
  required per-section `id`.
- **Search is out of scope.** The existing single-match highlight is untouched.
- **User uploads (future):** will live in browser `localStorage` as the same v2 document —
  no server storage. Not built now.

## Document schema (version 2)

A character set is `{version, label, blocks: [...]}`. Each block is a typed node; `section`
blocks nest recursively via their own `blocks` array.

```jsonc
{
  "version": 2,
  "label": "HSK (Simplified)",
  "blocks": [
    {
      "type": "section",
      "id": "level-1",            // required, unique within the document
      "title": "Level 1",
      "size": 2,                  // optional 1–5 heading scale (1 = largest)
      "collapsed": false,         // optional; presence ⇒ collapsible, value ⇒ default state
      "blocks": [
        { "type": "text", "text": "The 150 most common words." },
        { "type": "grid", "cells": "的我你是了不在他们好" }
      ]
    },
    {
      "type": "text",
      "text": "床前明月光，\n疑是地上霜。\n举头望明月，\n低头思故乡。",
      "interactive": true         // Han chars become live cells; punctuation/breaks inert
    }
  ]
}
```

### Block types

| `type`    | Props                                          | Renders as |
|-----------|------------------------------------------------|------------|
| `section` | `id` (req), `title`, `size?`, `collapsed?`, `blocks[]` | Heading (sized) + recursive children; `<details>`/`<summary>` when `collapsed` is present |
| `grid`    | `cells` (raw string)                           | A `.grid` of fixed study cells, one per character |
| `text`    | `text` (raw string), `size?`, `interactive?`   | Plain prose, or — when `interactive` — a reading-flow passage with live Han chars |

There is **no** `passage` type and **no** `description` field on sections: an interactive
`text` block covers classical passages, and a `text` child block covers section prose.

### `section`

- **`id`** — required, unique within the document, stable across edits/renames. Generated
  by the converter (slugified title + disambiguating counter). Keys persisted collapse
  state. Required on *all* sections (not just collapsible ones) so the converter always
  emits it and it is available for any future per-section state.
- **`size`** — optional 1–5 (see below); styles the title.
- **`collapsed`** — optional, single field replacing the old `collapsible` + `collapsed`
  pair. **Present** ⇒ the section is collapsible (`<details>`/`<summary>`), and the value
  is the *default* initial state. **Absent** ⇒ a plain non-collapsible heading. The live
  open/closed state comes from `localStorage` (the JSON value is only the default).

### `grid`

- **`cells`** — a raw string of characters; the renderer iterates it and emits one
  `<span data-unicode>` study cell per character (today's behavior). No `columns`/`gap`, no
  word objects.

### `text`

- **`text`** — a raw string (newlines significant).
- **`interactive`** — optional boolean, default `false`.
  - `false` ⇒ inert prose: rendered via `textContent`/escaped.
  - `true` ⇒ the renderer walks the string char-by-char: Han chars (`\p{Han}`) become
    `<span data-unicode>` cells (coloring/click/search work unchanged); everything else
    (punctuation, spaces) passes through as inert text; `\n` → line break.
- **`size`** — optional 1–5.
- The discriminator between prose and passage is the **flag, not the content** — a Han-rich
  caption stays inert with `interactive` omitted.

### `size` scale

Integer **1–5**, heading-style like Markdown `#`…`#####`: **1 = largest**, 5 ≈ body.
Mapped to CSS classes `.cs-size-1`…`.cs-size-5` on a **neutral element** (not real
`<h1>`–`<h5>`, to keep the heading outline / a11y tree intact). Allowed on `text` blocks
and `section` titles only — never grid cells. Out-of-range values clamp; missing falls back
to a body-weight default. Section titles start with **explicit `size` only** (a
nesting-depth default can be layered on later if hand-setting becomes tedious).

### Persistence (localStorage)

- **Colors** — unchanged: keyed by hex codepoint (e.g. `4e00`).
- **Collapse** — keyed `csCollapse:<section id>`. Namespaced so the colour-export regex
  `^[0-9a-f]+$` (`script.js:785`) never picks it up — exactly how `infoOptions` is already
  excluded. Read on every render so re-renders restore state; written on `<details>` toggle.

## Implementation steps

### 1. One-time conversion — `scripts/convert_charactersets.py`

Rewrite each existing file from v1 to v2:

`{label, value:[{label, value}]}` →
`{version:2, label, blocks:[{type:"section", id, title, blocks:[{type:"grid", cells}]}]}`

- One `section` per old inner node; its `title` is the old `label`, its single child is a
  `grid` whose `cells` is the old `value` string verbatim.
- Generate each section `id` (slugify `title`, append a counter on collision).
- Run once; commit the six converted files. **No runtime upgrade path** — the converter is
  the only v1→v2 step. (v1 files + this converter are deleted after the new app is tried
  out; v1 detection, while it exists, is by shape: a `value` key present / no `version`.)

### 2. Backend — `app.py` (lazy loading, pass-through)

- Replace the load-all loop (`app.py:17-29`) with a startup scan that parses each file only
  for its `label` and builds a `label → filepath` index (discarding the parsed body).
- `/get_character_set` reads + `json.load`s the one selected file on demand and returns the
  whole document verbatim (structure is opaque to the server). Wrap the per-file load in a
  small `functools.lru_cache` so repeated hits don't re-parse. *(If the corpus ever grows
  enough that the startup label-parse is costly, add a generated `charactersets/index.json`
  manifest — not needed at current size.)*
- `/get_character_set_names` reads labels from the index.
- No `_normalize_set`, no server-side block validation (validation is client-side, step 3).

### 3. Frontend — `script.js` (the real work)

- Replace `generateMacroGrid` with a recursive **`renderBlock(block, container)`** plus a
  **`BLOCK_RENDERERS`** map (mirroring the info sheet's `RENDERERS`). Unknown `type` →
  **skip + `console.warn`** (concrete, like `renderSections` at `script.js:167-169`).
  - `section` → a sized heading; if `collapsed` is present, wrap children in
    `<details>`/`<summary>`, set `open` from `localStorage` (`csCollapse:<id>`) falling back
    to the JSON `collapsed` default, and persist on `toggle`; then recurse over
    `block.blocks`.
  - `grid` → a `.grid` div; iterate `cells` (raw string), one study cell per character.
  - `text` → inert prose via `textContent` (+ size class); when `interactive`, char-walk
    (Han → `<span data-unicode>`, else inert text, `\n` → `<br>`).
- **Event delegation** for cell clicks: attach **one** listener per grid/passage container
  that derives the cell via `event.target.closest('span[data-unicode]')`, replacing the
  per-character `addEventListener` (`script.js:570`). Required so large classical texts
  (thousands of chars) don't attach thousands of listeners. Per-char span creation still
  applies the saved color from `localStorage` at build time.

### 4. CSS — `styles.css`

- `.cs-size-1`…`.cs-size-5` heading-style classes (decreasing weight/size).
- `<details>` / `<summary>` styling for collapsible sections.
- Reading-flow styling for `interactive` `text` (line-height, inline colorable chars),
  distinct from the grid's fixed `minmax(50px,1fr)` cells.

### 5. Cleanup — remove the dead character-set DB + redundant files

- Delete `character_set_nodes` + `character_set_members` from `schema.sql`.
- Drop the `import_character_sets.py` step from `scripts/rebuild_db.py` and delete
  `scripts/import_character_sets.py`.
- Delete the stale root `character_sets.json`.

## Out of scope

- Fixing the single-match search highlight.
- Words as unique units / DB elements / dedicated render elements (future goal).
- User-uploaded sets (future; will reuse the v2 document via `localStorage`).
- Nesting-depth-derived default sizes (explicit `size` only for now).

## Net effect

Recursive nesting, persistent collapsibles, plain-text prose, and interactive classical-text
passages all land on one small, extensible block model. The per-codepoint coloring / info /
search machinery is untouched; cell-click handling moves to event delegation. The redundant
DB set-tree and stale root JSON are deleted, leaving JSON files as the single source of
truth. Six files converted once.

## Rollout

1. Write the converter; convert **one** file and eyeball the v2 shape.
2. Convert the remaining five; commit all six.
3. Build the renderer (`renderBlock` + delegation + collapse persistence) and CSS.
4. Do the cleanup removals (step 5).
5. After the new app is tried out, delete the v1 files and the converter.
