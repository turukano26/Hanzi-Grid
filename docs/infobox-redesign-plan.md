# Infobox Redesign — Declarative, DB-Derived Sections

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

## 2. Core idea: the menu is *derived from the DB*; a thin overlay supplies only what the DB can't

The reading menu is **not hand-authored**. The DB already models the entire
linguistic tree the menu needs — re-encoding any of it in a manifest would create
a second source of truth that drifts the moment an importer renumbers or renames
something. Instead, `/get_info_options` **builds the reading tree by querying the
DB**:

| Menu concern | Already in the DB |
|---|---|
| Top-level grouping (Chinese, Japanese…) | `language_families` (+ `sort_order`) |
| Language nodes (Mandarin, Cantonese…) | `languages` (`name`, `code`, `family_id`, `sort_order`) |
| On/Kun-style sub-splits | `DISTINCT readings.category` within a language |
| Transcription leaves (Pinyin, Jyutping, Kana…) | `transcription_systems` (`name`, `code`, `language_id`, `sort_order`) |
| Which leaves actually have data | `DISTINCT reading_transcriptions.transcription_system_id` (+ derivable systems) |
| Stable contract id for each node | `languages.code` / `transcription_systems.code` (e.g. `cmn:pinyin`) |

Add a transcription system, a language, or a whole family **to the DB** and it
appears in the menu automatically — no second edit, nothing to keep in sync,
nothing to drift.

Only two kinds of thing the DB genuinely does *not* model stay hand-authored —
and that is **all** that stays hand-authored:

1. **`overlay.json` (tiny).** Initial checked state (a UI preference, not a
   linguistic fact) and the handful of display labels the schema lacks (the
   category-code → "On'yomi"/"Kun'yomi" map). Written as *exceptions to a derived
   default*, so it is a few lines, not a mirror of the DB.
2. **Non-reading sources** (`character_glyphs`, `character_attributes`, future
   free-text prose). These have no language→reading→transcription analogue, so
   they are declared explicitly — `id`, `label`, `default`, `handler`, `render`.
   This is the only place a manifest entry still looks like the old proposal.

Behavioral quirks the first draft put in the manifest move to where the data
lives (see §5): per-system value derivations onto two new `transcription_systems`
columns, editorial-note filtering into the importer, tone into the existing
`readings.tone` column. The net effect: the menu and its query parameters are
**computed**, and hand-authoring shrinks to "what's on by default" plus "sources
that aren't readings."

**Migration decision:** clean replacement. Once parity is verified, the seven
`_get_*` functions, `create_character_info_sheet()`, the hardcoded menu
checkboxes, and the branch-per-field `renderInfoBoxFromData()` are deleted
outright. No long-lived dual path.

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

## 4. What the server derives, and the two columns that make it possible

### The derived reading tree

`/get_info_options` emits a node tree by joining the DB — no hand-authored file
backs any of it:

```
language_families              → grouping node   (label = name)
  └ languages                  → group node      (id = lang code; label = name; handler = readings; render = readings)
      ├ DISTINCT category      → sub-group node   (Japanese on/kun; label from overlay map)
      └ transcription_systems  → leaf node        (id = "lang:ts" code; label = name)
           + an implicit "Definitions" leaf when senses exist for the language
```

A node's **id is its stable `code`** (`cmn`, `cmn:pinyin`, `ja:on:kana`,
`cmn:definitions`) — the `:`-joined chain of `code` columns the schema already
guarantees unique, now doing double duty as the request/persistence contract.
**Ordering** at every level is the corresponding `sort_order` column.

A transcription leaf is included **only if it can render data**: either its
`transcription_system_id` is populated (`reading_transcriptions` has rows) or it
is *derivable* from a populated system (next subsection). Empty systems (IPA
everywhere, Kunrei, Cantonese Yale…) are skipped automatically — the old "don't
add empty leaves by hand" rule becomes a data-driven filter on
`DISTINCT reading_transcriptions.transcription_system_id`.

### Two new `transcription_systems` columns absorb the per-leaf transforms

The first draft carried `value_transform` and `fallback_ts_id` on every Japanese
leaf. Those are properties of the *transcription system*, not of a menu entry, so
they move into the table that defines the system:

```sql
ALTER TABLE transcription_systems ADD COLUMN derived_from_ts_id INTEGER
    REFERENCES transcription_systems(id);   -- fall back to this system's value …
ALTER TABLE transcription_systems ADD COLUMN transform TEXT;  -- … then apply this transform
```

Resolving one reading in one target system becomes a single rule the shared core
applies uniformly:

```
value = COALESCE( stored[target_ts], stored[derived_from_ts] )   -- fallback chain
if transform: value = TRANSFORMS[transform](value)               -- e.g. kana_romaji, lower
```

Seeded once in `schema.sql`:

| ts | system | `derived_from_ts_id` | `transform` | effect |
|---|---|---|---|---|
| 30 | Hepburn | 32 (Kana) | `kana_romaji` | stored Hepburn for orphans, else romanize kana — reproduces the old `COALESCE(kana, hepburn)` exactly (`kana_romaji` converts a kana value, only lowercases an already-romaji one) |
| 60 | Stimson (kTang) | — | `lower` | lowercase Middle Chinese |
| 32 | Kana | — | — | stored kana only; correctly empty for orphans (no kana to reconstruct) |

This is the **same merge §8 already shipped**, just expressed as system metadata
instead of a per-leaf manifest knob. Future rule-based systems slot in identically
— `ipa` derived from `pinyin` via a `pinyin_ipa` transform, `revised_rom` from
`hangul` — with **zero** manifest involvement: add the row's two columns, write
the transform once.

### The overlay (`overlay.json`) — the only hand-authored reading config

Everything the DB can't know, and nothing it can:

```jsonc
{
  // Initial checked state is DERIVED: a language's primary transcription (the
  // lowest-sort_order one that renders) + its Definitions are on; everything
  // else is off. List only the exceptions to that rule:
  "default_off": ["ja:on:definitions", "ja:kun:definitions"],
  // Display labels the schema lacks (category codes -> human label):
  "category_labels": { "on": "On'yomi", "kun": "Kun'yomi" }
}
```

(If category labels ever proliferate, promote them to a `reading_categories`
lookup table and the overlay loses even that — fully DB-derived.)

### Non-reading sources stay explicit

Glyphs and attributes have no linguistic tree, so they are listed directly. This
is the small residue of the original manifest:

```jsonc
{ "id": "glyphs", "label": "Historical Glyphs", "default": false,
  "handler": "glyph_images", "render": { "type": "image_gallery", "title": "Glyphs" } }
```

Korean **Hangul** comes for free with no special-casing: ts 41 (Hangul) and ts 42
(Yale) are both populated `transcription_systems` rows under language 20, so both
surface as leaves automatically — fixing the current gap where `_get_korean`
queries Yale only.

---

## 5. Handler set (server)

The seven `_get_*` functions collapse into **one shared SQL core plus a small
registry of handlers** dispatched by `query.handler`.

### Shared core (eliminates the duplication)

```python
def _fetch_reading_rows(codepoint, language_id, *, transcriptions, category=None):
    """The single SELECT all seven current functions duplicate.
    `transcriptions` is the list of enabled transcription systems; each carries its
    `ts_id` plus the `derived_from_ts_id`/`transform` read from the
    `transcription_systems` table (not from the menu). Returns distinct reading
    rows; each column resolves per reading as
    `COALESCE(stored[ts], stored[derived_from])` then applies `transform` — e.g.
    Japanese romaji (ts 30) COALESCEs its stored value with kana (ts 32) and then
    applies `kana_romaji`."""
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

Middle Chinese (`tang`) is **not** a separate handler: it is `readings` for
language 7. No `kind` filter is needed (every reading there is a reconstruction);
the lowercase is `transcription_systems.transform = 'lower'` on ts 60 (§4),
rendered inline.

### Language quirks: relocated out of the manifest

The first draft turned every quirk into a hand-authored manifest knob. Each one
instead moves to where its data already lives:

| Quirk | First-draft knob | Now lives in |
|---|---|---|
| CEDICT-over-Unihan definitions | `source_priority: [1, 2]` | **nothing** — the default `ORDER BY source_id` already yields CEDICT (1) before Unihan (2); a `sources.priority` column is the DB home if a future source ever needs a non-id order |
| Jyutping trailing tone digit | `tone_from: "trailing_digit"` | **nothing** — `readings.tone` is populated (34 876 / 34 886, 100% agreement with the digit) and read uniformly for every tonal language |
| CC-Canto `#` editorial notes | `drop_hash_defs: true` | **the importer** — `import_cccanto.py` skips `#` lines instead of storing them as senses (equivalently a global `WHERE definition NOT LIKE '#%'`) |
| Kana → Hepburn romaji | `value_transform` + `fallback_ts_id` on leaf | **`transcription_systems`** columns (ts 30: `derived_from_ts_id = 32`, `transform = kana_romaji`) |
| Middle Chinese lowercase | `value_transform: "lower"` on leaf | **`transcription_systems`** column (ts 60: `transform = lower`) |
| Reconstruction vs reading | `kind: "reconstruction"` | **nothing** — fetch all readings for the language; `kind` is descriptive data, not a filter the menu needs |
| Primary / anchor transcription | `primary: true` on leaf | **derived** — the enabled transcription with the lowest `sort_order` |

`_kana_to_romaji` / `_ROMAJI` move into one importable module (`romaji.py`) so the
`app.py` TRANSFORMS registry and `dedup_readings.py` share a single copy instead
of the current duplicated mirror.

### Parameter reference (now internal, not hand-authored)

There is **no hand-authored parameter table for readings** anymore. The server
derives each handler call from the node it built:

| Handler-call input | Derived from |
|---|---|
| `handler` | `readings` for any language node; written explicitly only on non-reading entries |
| `language_id` | the `languages` row the node was built from |
| `category` | the node's `DISTINCT readings.category` value (Japanese on/kun), else none |
| `transcriptions` | the enabled transcription leaves — each already carries its ts id, plus `derived_from_ts_id`/`transform` read from the DB |
| `definitions` | whether the node's implicit Definitions leaf is enabled |
| `primary` | computed: lowest `sort_order` among the enabled transcriptions |

The only knobs a human still writes are on **non-reading** entries (`handler`,
`render.type` / `title`) and in the **overlay** (`default_off`, `category_labels`).

---

## 6. Dispatch and request/response contract

### Endpoints

- **`GET /get_info_options`** → the menu tree, assembled server-side from the DB
  (reading nodes) + `overlay.json` (defaults, category labels) + the non-reading
  manifest entries, with every server-only field **stripped** (`handler`,
  `language_id`, ts ids, `derived_from_ts_id`/`transform`). The client receives
  ids, labels, nesting, `render.type`, and default state only — enough to draw the
  menu and pick a renderer; query internals stay server-side.
- **`POST /process_click_on_character`** → new body
  `{ "character": "生", "options": ["cmn:pinyin", "cmn:definitions", ...] }`
  (a flat list of enabled **leaf** ids — the derived `code` keys). Response:
  `{ "sections": [ { "id", "type", "title", "data" }, ... ] }` in **tree order**
  (display order is independent of request order).

### Dispatch (coalesce per group — do not iterate per leaf)

`TREE` below is the assembled node tree (DB-derived reading nodes + non-reading
manifest entries), built once at startup. Each group node already carries the
fields the server derived for it (`handler`, `language_id`, `category`, `render`);
each transcription leaf carries its ts id + `derived_from_ts_id`/`transform` from
the DB.

```python
def build_sections(character, enabled_ids):
    cp = ord(character)
    sections = []
    for group in query_groups(TREE):                # nodes that fetch data
        enabled = [leaf for leaf in descendants(group) if leaf["id"] in enabled_ids]
        if not enabled:
            continue
        transcriptions = [l for l in enabled if l.get("ts_id")]   # ts_id + derived_from + transform
        want_defs      = any(l.get("definitions") for l in enabled)
        data = HANDLERS[group["handler"]](
            cp, group, transcriptions=transcriptions, definitions=want_defs)
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

Nothing in this table is hand-authored — every row is *derived* from the DB rows
shown. The "was a param" column records what the first draft would have written by
hand and where it now comes from instead.

| Current field | Derived from | Was a param → now | Render |
|---|---|---|---|
| `mandarin` | lang 1 | `source_priority` → default `ORDER BY source_id`; `primary` → Pinyin (lowest `sort_order`) | `readings` |
| `cantonese` | lang 2 | `tone_from` → `readings.tone`; `drop_hash_defs` → importer | `readings` |
| `tang` | lang 7 | `kind`/`value_transform:lower` → ts 60 `transform=lower` (DB) | `readings` (inline) |
| `japanese_kun` | lang 10, `category=kun` | romaji/kana leaves → ts 30 (`derived_from 32`, `kana_romaji`) + ts 32, both from DB | `readings` |
| `japanese_on` | lang 10, `category=on` | same | `readings` |
| `korean` | lang 20 | Yale (ts 42) + Hangul (ts 41) → both surface as populated `transcription_systems` leaves | `readings` |
| `vietnamese` | lang 30 | Quốc Ngữ (ts 50) → populated `transcription_systems` leaf | `readings` |

Japanese/Korean/Vietnamese gain a Definitions toggle for free — the implicit
Definitions leaf appears wherever senses exist (Japanese already has 24 117).
Adding **kana**, Zhùyīn, Wade-Giles, etc. needs **no manifest edit at all**: seed
the `transcription_systems` row (and a `derived_from`/`transform` if it's
rule-based) and it appears as a leaf. Korean **Hangul** — unreachable today
because `_get_korean` queries Yale only — surfaces automatically for the same
reason: it is a populated `transcription_systems` row under language 20.

### Data availability (which transcription leaves actually have data)

A leaf is auto-included only if it can render — (a) an importer populates that
`transcription_system_id`, or (b) the `transcription_systems` row sets
`derived_from_ts_id` + `transform` pointing at a populated one. Current state
across Unihan / CC-CEDICT / CC-Canto / KANJIDIC2:

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

1. **Derived system (cheap, no new data):** IPA and Revised Romanization are
   largely rule-based from populated data — `pinyin→IPA`, `jyutping→IPA`,
   `hangul→revised_rom`, `hangul→IPA`, `kana→IPA`. Set the existing empty
   `transcription_systems` row's `derived_from_ts_id` + `transform` (e.g. ts 5
   IPA → `derived_from 1`, `transform pinyin_ipa`) and write the transform once —
   same mechanism as Hepburn. The leaf then auto-appears; `pinyin` (ts 1) and
   `pinyin→IPA` (ts 5) coexist as two separate `transcription_systems` rows.
2. **New importer (higher quality):** add a source that ships attested IPA
   (e.g. Wiktionary / WikiPron) — a new `data/` dump + importer.

Until one of those exists, an empty system (IPA, Revised Rom, Zhùyīn, Wade-Giles,
Cantonese Yale, …) is simply skipped by the data-driven leaf filter — it never
needs to be excluded by hand.

### Reading categorization gap: Japanese on-reading subtypes

On vs kun **is** captured (`readings.category`, populated for all Japanese
readings). The finer **on-reading subtypes** (漢音 kan'on, 呉音 go'on, 唐音
tō'on, 慣用音 kan'yō-on) are **not**: `readings.subcategory` exists for exactly
this purpose (its schema comment lists `'kan'/'go'/'tou'/'souon'`) but is 100%
NULL. The data is absent at the source — KANJIDIC2's DTD defines an `on_type`
attribute, but the EDRDG dump never populates it (every `<reading
r_type="ja_on">` is bare), and Unihan's `kJapaneseOn` carries no subtype either.
So this cannot be a derived `transform`; it **needs a Wiktionary-class source**
that tags on-reading type (e.g. Wiktionary's Japanese kanji reading tables) —
a new `data/` dump + importer writing `subcategory`. Until then a manifest leaf
that filters or labels by on-subtype would be empty for every character.

### Japanese kana/Hepburn duplication and its dedup merge (already shipped — context, not redesign work)

> **Status: done.** Everything in this subsection describes a merge that is
> **already implemented and already run** — `merge_japanese_romaji` /
> `_absorb_hepburn` in `scripts/dedup_readings.py` (commit `964533a`). The live
> DB is already in the post-merge state described below. The infobox redesign
> consumes this state; it does **not** build it. This subsection is retained only
> to explain *why* the Japanese manifest leaves look the way they do in §4.

The "Hepburn (30, partial)" entry above reflects this merge: Unihan (`source_id` 2)
and KANJIDIC2 (`source_id` 3) each emit the *same* Japanese pronunciations, but
Unihan writes uppercase romaji into **ts 30** and KANJIDIC2 writes kana into
**ts 32** — disjoint at the row level (0 readings carry both ts on one row). The
generic `(transcription_system_id, value)` dedup pass cannot merge them, because
it treats `SEI`@ts30 and `セイ`@ts32 as unrelated. A dedicated Japanese bridge
pass (`merge_japanese_romaji`) was therefore added to close the gap; before it,
Japanese had **zero** multi-source reading rows (unlike Mandarin/Cantonese, where
both sources agree on the ts and were merged by the generic pass), and the old
infobox papered over the duplication by de-duplicating on the *romaji string* at
request time inside `_get_japanese`.

Canonical-form decision (**implemented**): **keep kana (ts 32) as canonical and
derive Hepburn** via `_kana_to_romaji` (lossless — kana carries the okurigana
`.`, affix `-`, and script distinctions that Unihan's stripped uppercase romaji
loses). The bridge pass folds each Unihan ts-30 row into its kana twin and unions
its attestation onto the surviving kana row — so those merged readings are now
**multi-source** (Kanjidic2 + Unihan: 31,317 Japanese readings carry >1
attestation today). The result is **hybrid, not pure**: ~77% of ts-30 rows had a
kana twin and were merged away; ~23% (9,409 rows, the current ts-30 total) are
Unihan-only orphans with no kana to convert from, so they **remain stored as
ts-30** Hepburn. The DB therefore still stores some Hepburn after the merge —
there is no single transcription system that is both lossless and universal here.

**Merge key includes `category`/`subcategory`.** The match is scoped to the same
`(etymology_id, kind, category, subcategory)` group the generic dedup uses, with a
normalized-romaji bridge value (`_kana_to_romaji(kana)` marker-stripped vs
`hepburn.lower()`) replacing the literal `(ts, value)`. On vs kun **cannot** be
dropped from the key: there are **119** `(character, romaji-key)` pairs where the
same romanization is *both* an on- and a kun-reading (e.g. 耼 `tan`/`ban`/`man`,
腱 `ken`) — a category-blind key would wrongly collapse each pair into one,
erasing the on/kun distinction. Keeping `subcategory` in the key (all-NULL today)
future-proofs the merge for when an on-subtype source lands.

---

## 9. Persistence cleanup

Today language checkbox booleans are written into the **same** `localStorage`
namespace as per-character colorings (hex codepoint → color), so
`exportUserData()` leaks checkbox state into color exports. Move enabled option
ids into a **single dedicated key** (`infoOptions`, a JSON array of derived leaf
`code`s, e.g. `["cmn:pinyin", "cmn:definitions"]`). The old
`chineseMandarinCheckbox`-style keys become harmless orphans — no migration
needed; the derived defaults (overlay `default_off` aside) apply on first load.

### Edge cases to handle

- **Only "Definitions" enabled, no romanization:** there is no transcription to
  label each reading, so no headword is shown — all of the group's definitions
  are merged into a single flat list. (Per-reading grouping resumes as soon as
  any transcription leaf is enabled.) This keeps the §6 dispatch honest: it
  forwards only enabled leaves, so when no transcription leaf is on there is
  simply nothing to anchor by.
- **Definition ordering:** `dedup_readings.py` already merges duplicate reading
  rows at import, so there is no "which reading survives" decision left to make at
  request time. Definitions are simply ordered by `source_id` (CEDICT before
  Unihan); no `source_priority` knob is needed unless a future source wants a
  non-id order, which would be a `sources.priority` column, not a manifest field.

---

## 10. Build phases

1. **Schema + data:** add the two `transcription_systems` columns
   (`derived_from_ts_id`, `transform`) and seed them (ts 30→32 `kana_romaji`, ts
   60 `lower`); move `_kana_to_romaji` into `romaji.py`; drop CC-Canto `#` notes
   in `import_cccanto.py`. Author the tiny `overlay.json` (`default_off`,
   `category_labels`) and the non-reading manifest entries. No reading menu is
   hand-authored — it is derived in the next step.
2. **Server:** the DB-derived menu builder (`/get_info_options`), shared
   `_fetch_reading_rows` core + `readings` handler + TRANSFORMS registry + the new
   request/response contract. Verify the rendered infobox matches current output
   for a sample of characters spanning all seven languages.
3. **Client:** dynamic checkbox tree, enabled-ids request, `RENDERERS` registry,
   single-key persistence. Delete the legacy menu/render code.
4. **Prove the on-demand path:** add `character_glyphs` images as the first *new*
   field; confirm BLOBs ship only when that option is toggled on.
5. **Scale:** new transcription systems / languages are **DB rows** (they appear
   in the menu automatically); only non-reading sources need a manifest entry.

---

## 11. Files touched

| File | Change |
|---|---|
| `schema.sql` | **add** `transcription_systems.derived_from_ts_id` + `transform` columns; seed them (ts 30→32 `kana_romaji`, ts 60 `lower`) |
| `overlay.json` | **new** — tiny: `default_off` exceptions, `category_labels`, and the explicit non-reading source entries (glyphs, attributes) |
| `romaji.py` | **new** — single home for `_kana_to_romaji` / `_ROMAJI`, imported by both `app.py` and `dedup_readings.py` (removes the duplicated mirror) |
| `import_cccanto.py` | drop `#` editorial lines instead of importing them as senses |
| `app.py` | remove 7 `_get_*` + `create_character_info_sheet`; add the DB-derived menu builder, overlay loader, `_fetch_reading_rows`, handler registry, TRANSFORMS, `/get_info_options`, rewritten POST route |
| `templates/index.html` | remove hardcoded language checkboxes |
| `static/script.js` | dynamic menu builder, enabled-ids request, `RENDERERS` registry, `infoOptions` persistence; remove `renderInfoBoxFromData` branches |
| `info_sections/definitions.py` | retire or realign to the new `{sections:[{id,type,title,data}]}` contract |
