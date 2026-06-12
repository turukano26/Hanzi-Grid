# Flexible Character Sets — Critique Review (after first round of decisions)

Review of the earlier critique against the following decisions:

- Remove Markdown; accept plain text with a `size` variable instead.
- The refactor's purpose is **deeper nesting** + **text strings** (classical texts
  will later be imported as character sets), so YAGNI does not apply to recursion/text.
- Remove the ability to specify `gap`/`columns`.
- v1 files are normalized to v2 **once**; after the new app is tried out, v1 + any
  converter are deleted.
- `collapsed` state is now saved and persistent.
- Fixing search is out of scope.
- ~~Multi-character word rendering is a preparatory step toward adding words as unique
  elements in the DB and throughout the app.~~ **Reversed (third round):** treating a word
  as a special unit — the `{word}` cell type and any dedicated `.word` render element — is
  **out of scope** for this rewrite. Words-as-units remains a future goal but builds no
  render elements now; grid cells stay **bare single characters** (today's behavior).

### Second round of decisions (storage)

- **JSON is the single canonical format.** The DB tables for character sets
  (`character_set_nodes` + `character_set_members`) are **deleted** — they are unused,
  are the worst fit for a recursive typed-block document, and every benefit they offered
  has collapsed (see below). The stale root `character_sets.json` is removed at the same
  time.
- **Lazy loading** replaces the load-everything-at-startup behavior: startup builds only a
  `label → filepath` index; each set is read + parsed on demand in `/get_character_set`
  (optionally LRU-cached).
- **User-uploaded sets live in browser `localStorage`** (view-your-own, not sharing).
  They are the same v2 JSON document and flow through the same renderer — no server-side
  storage needed.

Why the DB case collapsed (each prior DB benefit, after the decisions):

| DB benefit previously claimed | Status |
|---|---|
| Lazy load / smaller memory footprint | ❌ JSON does it fine — index + on-demand read (+ optional LRU cache). |
| One store so sets can reference word elements | ❌ Word identity is **concatenated codepoints** (like single chars today). A set stores literal text; the DB holds word *data* keyed by concat-codepoint; the join is derived at request time. No cross-store FK, no integrity concern — same relationship sets↔chars already have. |
| Durable / transactional user uploads | ❌ Uploads are client-side `localStorage`; no server storage, no concurrency problem. |

Remaining DB-only upsides are thin and unneeded: cross-set queries ("which sets contain
好?") — not a requirement, indexable in memory — and schema validation, which is done in
code regardless. The v2 JSON document is the unavoidable client-facing format anyway
(localStorage sets are JSON), so a relational server store would only ever be an extra
representation converted away on every request.

Caveat that survives (unrelated to the storage choice): large classical texts mean large
committed files and large localStorage entries (localStorage is ~5 MB/origin) — worth
watching when a whole text becomes a "set," but it doesn't change the answer.

---

## Criticisms — resolved vs. still standing

| # | Criticism | Status after these decisions |
|---|-----------|------------------------------|
| 1 | Markdown rendering path doesn't exist | **Resolved** — Markdown removed. Plain text via `textContent` needs no parser. |
| 2 | Markdown→`innerHTML` XSS | **Resolved, conditional** — only if text renders via `textContent`, not `innerHTML`. Worth stating explicitly as a requirement. |
| 5 | Per-grid `columns`/`gap` fight responsive layout | **Resolved** — removed. |
| 4 | YAGNI on recursion + text blocks | **Withdrawn** — deep nesting and classical-text strings are stated requirements. Generality now has a caller. |
| 6 | Converter **and** runtime `_normalize_set` is redundant | **Partially stands** — "normalize once, then delete v1 + converter" means a one-time on-disk conversion. The runtime `_normalize_set` is still redundant and should be dropped. |
| 7 | `{word}` dual-shape cell costs forever for cosmetic gain | **Resolved by removal** — words-as-units (the `{word}` cell + `.word` element) are out of scope; cells stay bare strings, so the dual-shape cost never lands. |
| 8 | Collapse state isn't persisted / re-render wipes it | **Now in scope** — persisting it resolves the re-render concern *provided* state is read on render. But it surfaces a new requirement: stable section identity (issue #2). |
| 10 | Search single-match highlight | **Dropped** — out of scope. |

---

## Unaddressed issues that still stand

*(none — all resolved; see "Modifications the plan needs" below.)*

~~**Classical-text rendering is a genuine gap.**~~ **RESOLVED** — decision: no separate
`passage`/flow type. A classical text is a **`text` block** containing a **raw string**,
with an optional **`interactive` flag**. One renderer walks the string char-by-char; when
`interactive: true`, Han chars (`\p{Han}`) become `<span data-unicode>` cells
(coloring/click/search work unchanged) and everything else (punctuation, spaces, `\n`)
passes through as inert text. A no-Han block renders identically with or without the flag,
so `text` subsumes the old `passage` idea. See modifications #1 and #7.

---

## Modifications the plan needs

1. **Strip all Markdown; one unified `text` block.** A `text` block is
   `{ "type": "text", "text": "<raw string>", "size"?: …, "interactive"?: false }` — the
   payload is a **raw string only** (no cells array, no nested structure). Default render
   is **inert** prose via **`textContent`/escaped** (no `innerHTML`) — this is the reason
   no Markdown parser / sanitizer / dependency is needed. With **`interactive: true`** the
   same renderer walks the string char-by-char: Han chars (`\p{Han}`) become
   `<span data-unicode>` cells (coloring/click/search unchanged), everything else
   (punctuation, spaces, `\n`) passes through as inert text. This single type also covers
   classical-text passages (see #7), so there is **no separate `passage`/flow type**.
2. **Define `size`:** integer **1–5 heading-style scale** (`1` = largest, like one `#`;
   `5` ≈ body), mapped to CSS classes `.cs-size-1`…`.cs-size-5` rendered on a **neutral
   element** (not real `<h1>`–`<h5>`, to keep the heading outline / a11y tree intact).
   Allowed on `text` blocks and `section` titles only — not grid cells. Clamp out-of-range
   values; missing `size` falls back to a body-weight default. Decide whether `section`
   titles take explicit `size` only, or `size` overrides a nesting-depth-derived default
   (start explicit-only).
3. **Remove `columns` and `gap`** from the grid schema, the renderer step, and the CSS
   step.
4. **Drop runtime `_normalize_set`.** Keep only the one-time converter script. Note v1
   files + converter are deleted after the trial period; document that v1 detection is by
   shape (`value` key present), since v1 files carry no `version`.
5. **Specify collapse persistence:** add a **required `id`** to **every** `section` block
   in the schema (string, unique within the document — `{ "type": "section", "id":
   "level-1", "title": "Level 1", … }`; required on all sections, not just collapsible
   ones, so the converter always emits it and it's available for any future per-section
   state), generated by the v1→v2 converter (e.g. slugified title with a disambiguating
   counter). It keys the persisted collapse state — stable across edits/renames, unlike
   `title` or a positional path. Define the localStorage key as
   `<set>:<id>`-namespaced (e.g. `csCollapse:<id>`) so the colour-export regex
   `^[0-9a-f]+$` won't pick it up (like `infoOptions` is excluded), and read state on every
   render so re-renders restore it. Collapse `collapsible`/`collapsed` into the persisted
   model.
6. **Storage = JSON only (decided).** Delete `character_set_nodes` +
   `character_set_members` from `schema.sql` and drop their importer step
   (`import_character_sets.py`); remove the stale root `character_sets.json`. Add **lazy
   loading**: replace the startup load-all loop (`app.py:17-29`) with a `label → filepath`
   index, reading + parsing each file on demand in `/get_character_set` (optional LRU
   cache for large texts). Reserve **`localStorage`** as the future home for
   user-uploaded sets — same v2 document, same renderer, no server storage.
7. **Classical texts = interactive `text` block (decided).** No new `passage`/flow type
   and no `grid` "flow" mode. A classical text is a `text` block with `interactive: true`
   holding the verbatim text as a raw string (newlines preserved → line breaks). The
   char-walk renderer (modification #1) makes Han chars interactive and passes punctuation
   / whitespace through inertly. Distinguish from inert prose purely by the `interactive`
   flag, not by content — a Han-rich caption stays inert with `interactive` omitted/false.
   Reading-flow CSS (line-height, inline colored chars) differs from the grid's 50px cells.
8. **Make unknown-type handling concrete:** skip + log, mirroring `renderSections`
   (`script.js:167-169`) — drop the word "optionally."
9. **Fix per-character scaling for large interactive sets.** `generateCharacterElements`
   creates one `<span>` **and attaches one click listener per character**
   (`script.js:570`). Fine for ~2,000-char HSK; a classical text of thousands–tens of
   thousands of chars makes that a lot of DOM nodes and listeners. Move to event
   delegation (one listener on the grid, derive the cell from `event.target`) so the
   classical-text import doesn't dead-end on per-char listeners — even if the switch is
   deferred, the plan should commit to it.
10. **Drop the `{word}` cell type from the schema and renderer.** Words-as-units are out
    of scope; the `grid.cells` entry is a **bare string only** (one character), and there
    is no `.word` wrapper. Words-as-DB-units stay a noted future goal with no build now.
11. **Collapse `collapsible` + `collapsed` into one field.** Two fields are redundant —
    `collapsed` is meaningless without `collapsible`. Use a single optional `collapsed`
    (`true`/`false`) on `section`: its presence makes the section collapsible, its value
    sets the initial state; absent ⇒ a plain non-collapsible heading. Tie the live state to
    the persisted model (modification #5), so the JSON value is only the *default*.
    (Unknown block-type validation, the other half of the old "Minor" issue, is already
    covered by modification #8.)
