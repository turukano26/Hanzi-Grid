# Infobox Redesign — Declarative, Manifest-Driven Sections

**Status:** Planned
**Date:** 2026-06-09
**Goal:** Make adding an infobox field a single declarative edit instead of five
coordinated code changes, scaling cleanly to 10–20 new sources.

---

## 1. Motivation

Adding one infobox field today requires touching five places:

1. A `_get_x()` query function in `app.py`.
2. A checkbox gate in `create_character_info_sheet()`.
3. A hardcoded `<input type="checkbox">` in `templates/index.html`.
4. A render branch in `renderInfoBoxFromData()` in `static/script.js`.
5. The display-order array at the top of that same renderer.

Five edits × 20 planned sources is the cost we are eliminating. Two further
requirements drive the design:

- **On-demand fetching.** The client must not request every field on every
  click. Heavy payloads (e.g. historical glyph images / `character_glyphs`
  BLOBs) must only be queried when their option is actually enabled.
- **One generalized query path.** The seven current `_get_*` functions are the
  *same* SQL (`characters → etymologies → readings → reading_transcriptions
  [→ senses]`) parameterized by `language_id` + `transcription_system_id` +
  an optional `category`. That duplication collapses into one shared core.

---

## 2. Core idea: a single manifest as source of truth

One hand-authored file, **`info_options.json`** (repo root), is the single
source of truth for three derived things:

| Derived artifact | Consumer | Built from |
|---|---|---|
| The options menu (checkbox tree) | client | `id`, `label`, `default`, nesting |
| Server query dispatch | server | `query` + child `param` blocks |
| Client rendering | client | `render` |

Adding a source becomes **one manifest entry**, reusing an existing handler and
an existing renderer. In the common case there is **zero** new server or client
code.

**Format decision:** hand-authored JSON (not derived-from-DB, not a Python
module). It must be consumed by both Python and a sanitized client endpoint, so
a neutral format is cleanest. Schema IDs (`language_id`, `transcription_system_id`,
`source_id`) sit inline, exactly like the existing `LANG_*` / `TS_*` constants in
`app.py` — same "must match `schema.sql`" constraint already documented in
`CLAUDE.md`.

**Migration decision:** clean replacement. Once parity with the current infobox
is verified, the seven `_get_*` functions, `create_character_info_sheet()`, the
hardcoded menu checkboxes, and the branch-per-field `renderInfoBoxFromData()`
are deleted outright. No long-lived dual path.

---

## 3. The key modeling decision: the query unit is the *reading group*, not the transcription

Definitions (`senses`) are a property of a **reading**, not of a transcription
system or a language. Pinyin, Zhùyīn, and Wade-Giles are three *renderings of
the same reading row*, which has *one* set of senses.

Therefore the unit of querying is the **reading group (the language)**, and the
transcription/definition toggles below it only contribute *parameters* to that
single per-group query. This:

- Prevents enabling Pinyin + Zhùyīn + Wade-Giles from firing three queries or
  rendering three identical definition blocks (the group is queried **once**;
  definitions are fetched and shown **once**; the enabled transcriptions are
  rendered inline, e.g. `shēng / ㄕㄥ / shêng¹`).
- Makes **definitions for any language** (e.g. Japanese) work with no new code:
  add a `definitions` toggle child under that language's group; the same handler
  fetches `senses` by `reading_id`, which is language-agnostic.

This matches the hierarchy requested: *Chinese → Mandarin / Cantonese →
(Mandarin Definitions, Mandarin Readings) → the different transcription systems.*

---

## 4. Manifest schema (`info_options.json`)

A nested tree of nodes. Three optional concerns per node:

- **Menu:** `id` (stable contract key), `label`, `default` (initial checked
  state). Present on every node.
- **`query`:** present **only on group nodes** that fetch data. Carries the
  `handler` name + fixed parameters (language, dedup policy, source priority…).
- **`param`:** present on **leaf toggles**. Contributes parameters to the nearest
  ancestor group's query (which transcription system, or `definitions: true`).
- **`render`:** present on group nodes. Names the client renderer + section title.

Pure grouping nodes (e.g. `chinese`) have none of `query`/`param`/`render` — they
are just subtree toggles.

### Example

```jsonc
{
  "id": "chinese", "label": "Chinese", "default": true,
  "children": [
    {
      "id": "mandarin", "label": "Mandarin", "default": true,
      "query":  { "handler": "readings", "language_id": 1, "source_priority": [1, 2] },
      "render": { "type": "readings", "title": "Mandarin" },
      "children": [
        { "id": "mandarin_definitions", "label": "Definitions", "default": true,
          "param": { "definitions": true } },
        {
          "id": "mandarin_readings", "label": "Romanizations", "default": true,
          "children": [
            { "id": "mandarin_pinyin", "label": "Pinyin",     "default": true,
              "param": { "transcription_system_id": 1, "primary": true } },
            { "id": "mandarin_zhuyin", "label": "Zhùyīn",     "default": false,
              "param": { "transcription_system_id": 4 } },
            { "id": "mandarin_wade",   "label": "Wade-Giles", "default": false,
              "param": { "transcription_system_id": 3 } }
          ]
        }
      ]
    },
    {
      "id": "cantonese", "label": "Cantonese", "default": true,
      "query":  { "handler": "readings", "language_id": 2,
                  "tone_from": "trailing_digit", "drop_hash_defs": true },
      "render": { "type": "readings", "title": "Cantonese" },
      "children": [
        { "id": "cantonese_definitions", "label": "Definitions", "default": true,
          "param": { "definitions": true } },
        { "id": "cantonese_jyutping",   "label": "Jyutping",    "default": true,
          "param": { "transcription_system_id": 10, "primary": true } }
      ]
    }
  ]
}
```

Japanese demonstrates **kana vs romaji** — two transcription leaves over the
*same* stored kana (ts 32), distinguished only by a leaf-level `value_transform`:

```jsonc
{
  "id": "japanese_on", "label": "On'yomi", "default": true,
  "query":  { "handler": "readings", "language_id": 10, "category": "on" },
  "render": { "type": "readings", "title": "On-Reading" },
  "children": [
    { "id": "ja_on_defs",   "label": "Definitions", "default": false,
      "param": { "definitions": true } },
    { "id": "ja_on_romaji", "label": "Romaji", "default": true,
      "param": { "transcription_system_id": 32, "value_transform": "kana_romaji",
                 "primary": true } },
    { "id": "ja_on_kana",   "label": "Kana",   "default": false,
      "param": { "transcription_system_id": 32 } }
  ]
}
// japanese_kun is identical with "category": "kun"
```

Korean, Vietnamese, and Middle Chinese follow the same shape (see §8).

---

## 5. Handler set (server)

The seven `_get_*` functions collapse into **one shared SQL core plus a small
registry of handlers** dispatched by `query.handler`.

### Shared core (eliminates the duplication)

```python
def _fetch_reading_rows(codepoint, language_id, *, ts_ids, category=None,
                        kind=None, fallback_ts_id=None):
    """The single SELECT all seven current functions duplicate.
    Returns distinct reading rows, each with the requested transcriptions."""
```

### Handlers

| handler | replaces | output shape |
|---|---|---|
| `readings` | `_get_mandarin`, `_get_cantonese`, `_get_japanese`, `_get_korean`, `_get_vietnamese`, `_get_tang` | `{ "readings": [ { "transcriptions": [...], "tone": str?, "definitions": [...]? } ] }` |
| `glyph_images` | *(new)* | `{ "images": [ { "url"\|"data": ..., "attribution": str } ] }` |
| `attributes` | *(new)* | `{ "rows": [ { "key": str, "value": str } ] }` |

> **Naming note (the rename):** the unified handler is `readings`, **not**
> `tonal_readings`. Tone is an *optional* per-reading attribute — present for
> Mandarin/Cantonese, absent for Japanese/Korean/Vietnamese. The handler's job
> is "fetch reading rows + optional senses + the enabled transcriptions,"
> independent of whether tones exist. This is precisely why Japanese can reuse
> it to carry definitions while having no tones.

Middle Chinese (`tang`) is **not** a separate handler: it is `readings` with
`kind: "reconstruction"` and a `value_transform: "lower"`, rendered inline.

### Language quirks become named parameters, not functions

| Quirk | Today (hardcoded) | Manifest parameter | Where |
|---|---|---|---|
| CEDICT-over-Unihan definition preference | `_get_mandarin` | `source_priority: [1, 2]` | group |
| Jyutping trailing tone digit | `_get_cantonese` | `tone_from: "trailing_digit"` | group |
| CC-Canto `#` editorial notes | `_get_cantonese` | `drop_hash_defs: true` | group |
| Kana → Hepburn romaji | `_get_japanese` | `value_transform: "kana_romaji"`, `fallback_ts_id: <hepburn>` | **leaf** |
| Middle Chinese lowercase | `_get_tang` | `value_transform: "lower"` | **leaf** |

`_kana_to_romaji` / `_ROMAJI` stay in `app.py` and are invoked as the
`kana_romaji` value-transform. These knobs cover all seven current cases; new
sources typically set none of them.

### Parameter reference

Only three parameters are required; the rest are optional and each defaults to a
no-op. A clean new source sets just the three. The dropped `dedup` parameter is
gone because `dedup_readings.py` already merges duplicate reading rows at import.

| Parameter | Where | Required? | Default | Purpose |
|---|---|---|---|---|
| `handler` | group | **yes** | — | which fetch handler (`readings`, `glyph_images`, `attributes`) |
| `language_id` | group | **yes** (readings) | — | which language's readings to fetch |
| `transcription_system_id` | leaf | **yes** (a transcription leaf) | — | which transcription column to render |
| `category` | group | no | all | filter readings (e.g. Japanese `kun`/`on`) |
| `kind` | group | no | `reading` | `reading` vs `reconstruction` (Middle Chinese) |
| `tone_from` | group | no | `readings.tone` column | where the tone comes from (`trailing_digit` for jyutping) |
| `drop_hash_defs` | group | no | `false` | strip CC-Canto `#` editorial notes |
| `source_priority` | group | no | order by `source_id` | which source's definitions win |
| `definitions` | leaf | no | `false` | fetch `senses` for this group (one toggle, not per transcription) |
| `value_transform` | leaf | no | none | post-process a transcription value (`kana_romaji`, `lower`) |
| `fallback_ts_id` | leaf | no | none | secondary transcription system if the primary value is missing |
| `primary` | leaf | no | first transcription leaf | anchor transcription used to group/label readings |
| `id`, `label`, `default` | any | menu | — | stable key, display label, initial checked state |
| `type`, `title` | group | render | — | client renderer name + section heading |

---

## 6. Dispatch and request/response contract

### Endpoints

- **`GET /get_info_options`** → the manifest with every `query` block **stripped**
  (menu + `param` + `render` only). The client builds the menu and knows which
  renderer to call; query internals stay server-side.
- **`POST /process_click_on_character`** → new body
  `{ "character": "生", "options": ["mandarin_pinyin", "mandarin_definitions", ...] }`
  (a flat list of enabled **leaf** ids). Response:
  `{ "sections": [ { "id", "type", "title", "data" }, ... ] }` in **manifest
  order** (display order is independent of request order).

### Dispatch (coalesce per group — do not iterate per leaf)

```python
def build_sections(character, enabled_ids):
    cp = ord(character)
    sections = []
    for group in query_groups(MANIFEST):            # nodes carrying a `query`
        enabled = [leaf for leaf in descendants(group) if leaf["id"] in enabled_ids]
        if not enabled:
            continue
        transcriptions = [l["param"] for l in enabled          # ts_id + transform + fallback + primary
                          if "transcription_system_id" in l["param"]]
        want_defs      = any(l["param"].get("definitions") for l in enabled)
        data = HANDLERS[group["query"]["handler"]](
            cp, group["query"], transcriptions=transcriptions, definitions=want_defs)
        if "error" not in data:
            sections.append({"id": group["id"], **group["render"], "data": data})
    return sections
```

**On-demand guarantee:** a group whose subtree has no enabled leaf is skipped
entirely. The `glyph_images` handler — and its BLOB reads — only run when that
group's option is toggled on. This is the whole point of sending enabled-leaf
ids rather than every checkbox boolean.

---

## 7. Client changes

### Menu (replace hardcoded checkboxes in `index.html`)

- Recursively render the tree from `/get_info_options`.
- Parent nodes get a checkbox that toggles their whole subtree, with an
  indeterminate state for partial selection.
- Only leaf ids are sent in requests.

### Request builder (replace the `querySelectorAll('#languagemenu input')` scrape)

- Read enabled leaf ids from state; send `{ character, options }`.

### Renderer registry (replace the 7-branch `renderInfoBoxFromData`)

```js
const RENDERERS = {
  readings:      (s) => /* per-reading rows: enabled transcriptions inline
                           (primary first, tone-colored from s.data tone),
                           definitions listed once below; renders compactly
                           when a reading has no definitions. When no
                           transcription is enabled (definitions-only), there is
                           no headword: render all definitions as one merged
                           list. */,
  image_gallery: (s) => ...,   // new — glyphs
  key_value:     (s) => ...,   // new — attributes (frequency, strokes…)
  // plain_text reserved for future free-form prose (e.g. etymology paragraphs).
  // Middle Chinese is NOT plain_text — it is `readings` rendered inline
  // (no tone, no definitions → the same compact path Korean/Vietnamese use).
};
// iterate response.sections in order; call RENDERERS[s.type](s)
```

**Handler ≠ render type.** `query.handler` (server fetch) and `render.type`
(client renderer key) are independent namespaces — they coincide for `readings`
only by coincidence. The `glyph_images` handler renders with `image_gallery`;
the `attributes` handler renders with `key_value`. A manifest entry's
`render.type` must name a `RENDERERS` key, never a handler.

Adding a source that fits an existing shape = **zero** new client code. A
genuinely new visual = one new `RENDERERS` entry.

---

## 8. Parity mapping (current → manifest)

| Current field | Group `query` | Notable params | Render |
|---|---|---|---|
| `mandarin` | `readings`, lang 1 | `source_priority:[1,2]`, child `definitions` + `pinyin(primary)` | `readings` |
| `cantonese` | `readings`, lang 2 | `tone_from: trailing_digit`, `drop_hash_defs`, child `definitions` + `jyutping(primary)` | `readings` |
| `tang` | `readings`, lang 7 | `kind: reconstruction`; leaf `value_transform: lower` | `readings` (inline) |
| `japanese_kun` | `readings`, lang 10 | `category: kun`; romaji leaf `{ts:32, value_transform: kana_romaji}`, optional kana leaf `{ts:32}` | `readings` |
| `japanese_on` | `readings`, lang 10 | `category: on`; same leaves | `readings` |
| `korean` | `readings`, lang 20 | Yale leaf `{ts:42}` + Hangul leaf `{ts:41}` — both already populated on the same reading by the importer | `readings` |
| `vietnamese` | `readings`, lang 30 | leaf `transcription_system_id: 50` (Quốc Ngữ) | `readings` |

Japanese/Korean/Vietnamese gain a `definitions` toggle child for free once
senses exist for those languages — no code change. Adding a **kana** column (or
Zhùyīn, Wade-Giles, etc.) is one extra transcription leaf — no code change.
Korean **Hangul** is a special case: it is *already populated* in the DB on the
same reading as Yale, but unreachable today because `_get_korean` only queries
Yale. The redesign exposes it as a transcription leaf for free.

### Data availability (which transcription leaves actually have data)

A manifest leaf renders data only if (a) an importer populates that
`transcription_system_id`, or (b) a `value_transform` derives it from a
populated one. Current state across Unihan / CC-CEDICT / CC-Canto / KANJIDIC2:

| Populated | Empty (declared in schema, no source feeds them) |
|---|---|
| Pinyin accented (1), Pinyin numbered (2) | Mandarin Zhùyīn (4), Wade-Giles (3), IPA (5) |
| Jyutping (10) | Cantonese Yale (11), IPA (12) |
| Middle Chinese Stimson / kTang (60) | MC Baxter-Sagart (20), Zhengzhang (21), IPA (22) |
| Kana (32), Hepburn (30, partial) | Japanese Kunrei (31), IPA (33) |
| Hangul (41), Korean Yale (42) | Korean Revised Romanization (40), IPA (43) |
| Quốc Ngữ (50) | Vietnamese IPA (51) |

**IPA is empty for every language; Korean Revised Romanization is empty.** Two
ways to fill a gap:

1. **`value_transform` (cheap, no new data):** IPA and Revised Romanization are
   largely rule-based from populated data — `pinyin→IPA`, `jyutping→IPA`,
   `hangul→revised_rom`, `hangul→IPA`, `kana→IPA`. Write the transform once;
   point a leaf at the populated source ts with that transform (same mechanism
   as `kana_romaji`). Because `value_transform` is leaf-level, `pinyin` and
   `pinyin→IPA` are two leaves over the same ts 1.
2. **New importer (higher quality):** add a source that ships attested IPA
   (e.g. Wiktionary / WikiPron) — a new `data/` dump + importer.

Until one of those exists, do **not** add empty leaves (IPA, Revised Rom,
Zhùyīn, Wade-Giles, Cantonese Yale, etc.) to the manifest — they would render
blank.

---

## 9. Persistence cleanup

Today language checkbox booleans are written into the **same** `localStorage`
namespace as per-character colorings (hex codepoint → color), so
`exportUserData()` leaks checkbox state into color exports. Move enabled option
ids into a **single dedicated key** (`infoOptions`, a JSON array). The old
`chineseMandarinCheckbox`-style keys become harmless orphans — no migration
needed; manifest `default` values apply on first load.

### Edge cases to handle

- **Only "Definitions" enabled, no romanization:** there is no transcription to
  label each reading, so no headword is shown — all of the group's definitions
  are merged into a single flat list. (Per-reading grouping resumes as soon as
  any transcription leaf is enabled.) This keeps the §6 dispatch honest: it
  forwards only enabled leaves, so when no transcription leaf is on there is
  simply nothing to anchor by.
- **Definition-priority semantics:** `dedup_readings.py` already merges duplicate
  reading rows at import time, so `source_priority` now only governs which
  *definitions* win, not which reading survives.

---

## 10. Build phases

1. **Author `info_options.json`** reproducing today's exact seven fields in the
   group-query shape above. Parity target, no behavior change yet.
2. **Server:** shared `_fetch_reading_rows` core + `readings` handler +
   transforms + `/get_info_options` + the new request/response contract. Verify
   the rendered infobox matches current output for a sample of characters
   spanning all seven languages.
3. **Client:** dynamic checkbox tree, enabled-ids request, `RENDERERS` registry,
   single-key persistence. Delete the legacy menu/render code.
4. **Prove the on-demand path:** add `character_glyphs` images as the first *new*
   field; confirm BLOBs ship only when that option is toggled on.
5. **Scale:** the remaining 10–20 sources are manifest entries only.

---

## 11. Files touched

| File | Change |
|---|---|
| `info_options.json` | **new** — the manifest |
| `app.py` | remove 7 `_get_*` + `create_character_info_sheet`; add manifest loader, `_fetch_reading_rows`, handler registry, transforms, `/get_info_options`, rewritten POST route |
| `templates/index.html` | remove hardcoded language checkboxes |
| `static/script.js` | dynamic menu builder, enabled-ids request, `RENDERERS` registry, `infoOptions` persistence; remove `renderInfoBoxFromData` branches |
| `info_sections/definitions.py` | retire or realign to the new `{sections:[{id,type,title,data}]}` contract |
