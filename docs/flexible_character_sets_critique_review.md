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
- Multi-character word rendering is a preparatory step toward adding words as unique
  elements in the DB and throughout the app.

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
| 7 | `{word}` dual-shape cell costs forever for cosmetic gain | **Softened, not gone** — accepted as prep for words-as-DB-elements. But see new issue #6: per-char spans likely aren't the end-state representation. |
| 8 | Collapse state isn't persisted / re-render wipes it | **Now in scope** — persisting it resolves the re-render concern *provided* state is read on render. But it surfaces a new requirement: stable section identity (issue #2). |
| 10 | Search single-match highlight | **Dropped** — out of scope. |

The big one (#3, DB redundancy) is untouched by any decision and actually gets **more**
pressing — see below.

---

## Unaddressed issues that still stand

1. **DB redundancy — now sharper, not softer.** `character_set_nodes` (recursive
   `parent_id` tree) + `character_set_members` already exist and are populated by the
   importer, and were built for exactly the recursive nesting now being committed to.
   Classical texts are large, structured, and DB-bound. Doubling down on recursive JSON
   files while a recursive set-tree schema sits unread — plus the stale root
   `character_sets.json` "alternate copy" — means 2–3 drifting representations. The
   nesting + classical-text goals make "JSON files vs. the DB tree" a decision the plan
   must now actually make, not defer.

2. **Persisted collapse needs a stable section identity.** Sections currently have only
   `title`, which is neither unique nor stable (two "Level 1"s; rename breaks the key).
   Persisting collapse state to localStorage requires a stable key scheme. A
   positional/path index (`blocks.2.blocks.0`) breaks the moment a document is edited or
   a classical text is inserted; explicit `id` fields are more robust. The plan
   specifies none.

3. **"Size variable" is undefined.** Allowed values (enum `sm/md/lg`? raw px? rem?),
   where it applies (text blocks only, or also section headings / grid cells?), and how
   it maps to CSS are all unspecified. Without bounds it becomes another free-form style
   knob like the `columns` just removed.

4. **Classical-text rendering is a genuine gap.** A classical text wants characters in
   reading order, flowing, *still individually clickable/colorable*. That is neither
   today's fixed-cell `.grid` (`minmax(50px,1fr)` — unusable for thousands of
   reading-order chars) nor a non-interactive plain-`text` block. The plan's two block
   types don't cover the headline use case. Need either a grid "flow" mode or a third
   interactive-text block — decide which, or explicitly defer with the chosen approach
   named.

5. **Per-character scaling.** `generateCharacterElements` creates one `<span>` **and
   attaches one click listener per character** (`script.js:570`). Fine for ~2,000-char
   HSK; a classical text of thousands–tens of thousands of chars makes that a lot of DOM
   nodes and listeners. The classical-text goal probably wants event delegation (one
   listener on the grid). Worth flagging now since it's the stated direction.

6. **The `{word}` "prep step" may be throwaway.** Words-as-unique-DB-elements will most
   likely render as a *single* clickable/colorable unit with its own info sheet and its
   own key — not as a `.word` wrapper of independent per-char spans. If so, the per-char-
   span word rendering isn't a stepping stone toward that model; it's a different model
   that gets ripped out. Confirm the end-state so the interim shape actually converges on
   it.

7. **Minor:** `collapsible`+`collapsed` as two fields is redundant (collapse one, tie to
   persisted state); and "optionally validate/log unknown block types" should be made
   concrete (skip-and-log, like `renderSections` already does) rather than optional.

---

## Modifications the plan needs

1. **Strip all Markdown.** `text` block becomes
   `{ "type": "text", "text": "...", "size"?: ... }`. State that text and descriptions
   render via **`textContent`/escaped** (no `innerHTML`) — record this as the reason no
   sanitizer/dependency is needed.
2. **Define `size`:** enum of named sizes mapped to CSS classes (recommended) rather than
   free-form values; state where it's allowed.
3. **Remove `columns` and `gap`** from the grid schema, the renderer step, and the CSS
   step.
4. **Drop runtime `_normalize_set`.** Keep only the one-time converter script. Note v1
   files + converter are deleted after the trial period; document that v1 detection is by
   shape (`value` key present), since v1 files carry no `version`.
5. **Specify collapse persistence:** add stable section `id`s to the schema, define the
   localStorage key (namespaced so the colour-export regex `^[0-9a-f]+$` won't pick it up
   — like `infoOptions` is excluded), and read state on every render so re-renders
   restore it. Collapse `collapsible`/`collapsed` into the persisted model.
6. **Resolve the DB question explicitly:** either (a) generate v2 JSON from
   `character_set_nodes` and treat the DB as source of truth, or (b) state why JSON files
   stay authoritative and the DB tree is removed. Either way, address the stale root
   `character_sets.json`.
7. **Add a classical-text rendering decision:** specify whether classical texts are a
   grid "flow" variant or a new interactive-text block, or defer with the chosen approach
   named. This is the actual driver of the refactor and currently has no block type.
8. **Make unknown-type handling concrete:** skip + log, mirroring `renderSections`
   (`script.js:167-169`) — drop the word "optionally."
9. **Note the scaling plan** (event delegation) for large interactive sets, even if
   deferred, so the classical-text import doesn't dead-end on per-char listeners.
10. **Pin down the word end-state** (single unit vs. per-char spans) so the interim
    `{word}` rendering converges on the eventual DB word element instead of being
    discarded.
