# Dialect-Specific Transcriptions & Japanese Etymology-Level Definitions

**Status:** Planned
**Date:** 2026-06-16
**Goal:** Support (1) transcription systems that branch by dialect while the
reading/orthography/meaning stay dialect-neutral (Vietnamese IPA), and (2)
definitions that attach to a Japanese *etymology* rather than to a single
reading — without a schema rewrite. Both fit the existing
`character → etymology → reading → transcription/sense` tree with small,
additive changes.

---

## 1. Motivation

Two language-specific requirements don't sit cleanly in the current model:

1. **Vietnamese IPA is dialect-specific; Quốc Ngữ is not.** The national
   script (Quốc Ngữ) spells a syllable the same regardless of dialect, and the
   meaning is shared too — but the *phonetic realization* (IPA) forks Northern
   vs Southern. Today dialect is modeled **as a language** (`Northern
   Vietnamese` 30, `Southern Vietnamese` 31), which forces the dialect-neutral
   layers (orthography, definitions) to be duplicated per dialect. The thing
   that actually varies is the **transcription system**, one level below the
   language — so the menu needs transcription systems at *different depths*:
   Quốc Ngữ flat under "Vietnamese", IPA nested under a dialect.

2. **Japanese meaning is tied to the character/etymology, not the reading.**
   Unlike Mandarin/Cantonese (行 xíng "walk" vs háng "row" — meaning is
   reading-specific), a Japanese character's meaning is shared across its on
   and kun readings. But it is *not* always character-global either: some
   sources give a character several distinct etymologies, each with its own
   readings **and** meanings (see
   [生 on Wiktionary](https://en.wiktionary.org/wiki/%E7%94%9F#Japanese), with
   multiple Etymology sections). So the correct home for Japanese definitions
   is the **etymology**, which the schema already models — but `senses`
   currently FK to `readings`, one level too low.

---

## 2. Core idea: dialect lives at three possible levels, chosen by *what varies*

The recurring design question is "where does the dialect axis live?" The answer
is not one level — it depends on what actually differs between the dialects:

| What varies between dialects | Correct level | Examples |
|---|---|---|
| Only phonetic **realization** (same reading, same meaning) | **transcription group** (the new level) | VN Northern/Central/Southern IPA (via vPhon); Kansai pitch accent; Hokkien Amoy/Zhangzhou IPA |
| The **reading** itself (different syllable, not just accent) | reading-level — a dialect tag on `readings`, or a separate etymology | a kanji read differently in Kansai |
| **Vocabulary / meaning** wholesale (mutual unintelligibility) | separate **language** (already modeled) | Mandarin / Cantonese / Hokkien / Hakka / Wu; Ryukyuan; Jeju |
| Literary vs colloquial reading (文白異讀) | `readings.category` (already modeled) | Min Nan 文/白 |

These coexist; none replaces another. The only piece missing today is the
**top row** — a realization sub-grouping *below* the language and *above* the
transcription leaves. That is the one new structural level this plan adds.

### Symmetry payoff

Modeling realizational dialects this way makes the *language* the
dialect-neutral abstraction and the *groups* its realizations. That argues for
naming the language plainly ("Vietnamese", "Japanese") rather than picking one
dialect as the language name ("Northern Vietnamese", "Tokyo Standard") with the
others dangling oddly beside it.

### Worked example: 行 vs 生

行 is the Chinese counterpart to the 生 Japanese case and conveniently touches
**three** rows of the table at once, which makes the contrast with 生 concrete:

- **Reading-specific senses (separate etymologies).** In Mandarin, 行 is two
  genuinely distinct origins:
  - xíng → "to walk, to go; behavior (行為); OK" (etymology 1)
  - háng → "a row; profession/trade (行業); firm, e.g. 銀行 'bank'" (etymology 2)

  The meanings are tied to the *reading*, so senses stay on `reading_id` and the
  two readings live under two `etymologies` rows (`etymology_order` 1/2 — the
  schema's existing canonical multi-etymology example). **No change** from
  today's model.

- **Contrast with 生 (Japanese).** 生's on/kun readings (sei, shō; i-, u-, ha-,
  ki, nama…) *share* their etymology's meaning set, so senses attach to
  `etymology_id` (Phase 2). And like 行, 生 has several Japanese etymologies,
  each bundling its own readings **and** meanings. Same etymology layer, but
  senses sit at the etymology node for Japanese and at the reading node for
  Mandarin — exactly the `reading_id`/`etymology_id` split in §4.2.

- **Language row + 文白 row, in one character.** 行 is read differently across
  topolects (Mandarin xíng, Cantonese hang4/hong4, Hokkien…), which is the
  **language** level. And within Hokkien it shows the literary/colloquial split:
  文 hêng/hâng vs 白 kiâⁿ ("to walk") — the **`readings.category`** row. Neither
  needs the new transcription-group level; they're already modeled.

So 行 demonstrates that the framework keeps Mandarin's reading-specific senses
untouched while Japanese moves up to the etymology — and that the language and
文白 axes for the same character are independent of the dialect-realization level
this plan adds.

---

## 3. Does it generalize? (Kansai, Hakka, Min)

Yes — and the table above is the rule of thumb.

- **Kansai (Japanese).** The usual Tokyo↔Kansai kanji difference is
  suprasegmental (pitch accent), not a different kana, so it fits the
  **transcription-group** row: model the language as "Japanese" with
  Tokyo/Kansai realization groups, exactly like Vietnamese. If a Kansai
  reading is ever genuinely a *different syllable*, that part drops to the
  reading level instead — the two are complementary.

- **Mandarin / Cantonese / Hokkien / Hakka / Wu.** These are mutually
  unintelligible topolects that differ in the *reading itself* (and vocabulary),
  so they correctly stay at the **language** level — where they already are. The
  transcription-group level is **not** for them and must not collapse them.
  Their own romanizations (Hokkien POJ / Tâi-lô, Hakka Pha̍k-fa-sṳ) are just
  ordinary `transcription_systems` under each language, exactly like Jyutping
  under Cantonese, with IPA derived from them.

- **Within Hokkien / Hakka.** Sub-dialects that differ only realizationally
  (Hokkien: Amoy / Quanzhou / Zhangzhou; Hakka: Sixian / Hailu) are the
  realizational case → **transcription groups** (per-dialect IPA off the same
  POJ/PFS reading). Min's literary/colloquial split is orthogonal and already
  handled by `readings.category`.

So the framework covers every Sinitic case without further structural change:
**language** = topolect, **transcription group** = realizational sub-dialect,
**category** = 文/白, **reading/etymology** = genuinely distinct readings.

---

## 4. Schema changes (additive)

All changes are additive and ship via an **in-place migration** against the live
`omnihanzi.db` *and* equivalent edits to `schema.sql` + the importers, kept in
lockstep — the same discipline used for the infobox redesign (see
`memory/infobox-redesign-db-migration.md`).

### 4.1 Transcription grouping level

```sql
CREATE TABLE transcription_groups (
    id          INTEGER PRIMARY KEY,
    language_id INTEGER NOT NULL REFERENCES languages(id),
    name        TEXT    NOT NULL,   -- 'Northern', 'Southern'
    code        TEXT    NOT NULL,   -- 'north', 'south'
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(language_id, code)
);

-- transcription_systems gains:
--   group_id INTEGER NULL REFERENCES transcription_groups(id)
-- and its UNIQUE(language_id, code) becomes effectively
--   UNIQUE(language_id, group_id, code)
```

`group_id NULL` → the system renders as a flat leaf under its language (today's
behavior, unchanged for every existing system). A non-NULL `group_id` nests the
leaf under a group node. Allowing the same `code` (e.g. `ipa`) under different
groups is why the uniqueness key gains `group_id`.

> **SQLite note:** a `UNIQUE` constraint can't be altered in place, so the
> migration rebuilds `transcription_systems` (create new → copy → swap) — the
> one non-trivial step. Everything else is `ADD COLUMN` / `CREATE TABLE`.

### 4.2 Senses attachable at the etymology level

```sql
-- senses.reading_id becomes nullable; add etymology_id; exactly one is set.
--   etymology_id INTEGER NULL REFERENCES etymologies(id)
--   CHECK ( (reading_id IS NULL) <> (etymology_id IS NULL) )
-- plus: CREATE INDEX idx_senses_etymology ON senses(etymology_id);
```

Mandarin/Cantonese senses keep `reading_id` (reading-specific, unchanged).
Japanese senses use `etymology_id` (shared across that etymology's on/kun
readings). The etymology layer already exists and is intended for exactly this —
its own schema comment calls it the thing that "groups related readings +
meanings."

---

## 5. Phase 1 — Vietnamese (realizational dialects)

Vietnamese IPA is generated by **[vPhon](https://github.com/kirbyj/vPhon)**, a
mature, stdlib-only (Python 3.4+) rule-based Vietnamese orthography→IPA
phonetizer. This replaces the earlier idea of writing our own `quocngu_ipa`
rules from scratch — and changes the derive-vs-store decision.

### 5.1 vPhon, and why it flips derive→store

- **Three dialects, not two.** vPhon supports Northern/Hà Nội (`-d n`,
  default), Central/Huế (`-d c`), and Southern/Sài Gòn (`-d s`) — so the model
  gets **three** dialect groups. (Its experimental orthographic "spelling
  pronunciation" mode, `-d o`, we ignore.)
- **License: GPL-3.0.** vPhon's *code* is copyleft, but its *output* (IPA
  strings) is plain data, not a derivative work. So we must **not** vendor/ship
  vPhon's source, and the runtime Flask app must **not** import it.
- **Therefore: store IPA at build time; don't derive at runtime.** This is the
  deliberate opposite of the Mandarin/Cantonese/Korean IPA decision: those use
  *our own* tiny transforms, so runtime derivation is free and dependency-free;
  vPhon is a substantial third-party GPL tool, so the clean fit is a
  **build-time importer** (like Unihan/CEDICT) that populates stored
  `reading_transcriptions`, leaving only IPA *data* in the (gitignored) DB.

### 5.2 Data

- Collapse languages 30/31 into a single `Vietnamese` language; one
  etymology/reading per character.
- `transcription_groups` under Vietnamese: `Northern (north)`,
  `Central (central)`, `Southern (south)`.
- Quốc Ngữ (ts 50): `group_id NULL` (dialect-neutral, flat leaf).
- Three IPA systems, `code='ipa'`, one per group. These are **stored**
  (populated by the importer below), so `derived_from_ts_id` / `transform` are
  **NULL** — `_resolve_ts_value` returns the stored value directly, and
  `_build_info_tree`'s `populated_ts` check picks them up automatically.

### 5.3 Build-time importer (`scripts/import_vphon.py`)

- vPhon lives under `data/vphon/` (gitignored, cloned — not committed, mirroring
  how the other raw sources live under `data/`). `rebuild_db.py` gains a
  download/clone step plus this import step, run after the Vietnamese readings
  are in place.
- For each Vietnamese reading, feed its Quốc Ngữ value to vPhon once per dialect
  (`-d n|c|s`) and `INSERT` the result as a `reading_transcriptions` row under
  the matching per-dialect IPA system. Idempotent (re-run replaces).
- **Tone notation:** recommend `--chao` (Chao tone numbers, e.g. `33`, `21`).
  Vietnamese tones (incl. creaky/glottalized) don't map cleanly onto the Chao
  tone *letters* the Sinitic "IPA (with tones)" systems append, so numbers are
  the standard, pragmatic choice for VN. (vPhon's default Gedney superscripts
  and `-8` eight-tone encoding are the alternatives.)
- **Bad input:** vPhon brackets non-Vietnamese input (`[x]`); the importer treats
  a bracketed result as "no IPA" and skips that row.

### 5.4 App (`app.py`)

- `_build_info_tree` / `make_leaves`: group a language's transcription systems by
  `group_id`, emitting an intermediate menu node per group and flat leaves for
  `group_id NULL`. Leaf ids extend to `lang:group:ts` (e.g. `vi:north:ipa`).
- **Untouched:** `_resolve_ts_value`, `_fetch_reading_rows`, `_handler_readings`.
  The dialect IPAs are ordinary stored transcriptions on the same reading and
  render inline; the grouping is purely menu presentation.

Resulting menu:

```
Vietnamese
  Quốc Ngữ          (group NULL → flat)
  Northern → IPA
  Central  → IPA
  Southern → IPA
```

---

## 6. Phase 2 — Japanese definitions at the etymology level (phased)

Chosen scope: **move definitions up now; defer visible multi-etymology grouping.**

**Now**
- Japanese senses attach to `etymology_id`. Kanjidic2 meanings are already
  character/etymology-level English glosses, so this is a *more* faithful fit
  than today's "pick a reading to hang them on."
- `_build_info_tree`: the Definitions-leaf detection (`sense_cats`) must also
  count etymology-attached senses and emit the Japanese **Definitions leaf at
  the language level**, not under On'yomi/Kun'yomi.
- Japanese menu becomes:

  ```
  Japanese
    On'yomi  → Hepburn / Kana / IPA
    Kun'yomi → Hepburn / Kana / IPA
    Definitions          (language / etymology level)
  ```

- Render a single "Japanese — Definitions" section from etymology-level senses.
  Correct for the common single-etymology character.

**Deferred (follow-up)**
- Visible **multi-etymology grouping** (the 生 case): render etymology as a
  visible level so each etymology shows its readings + its definitions as a
  separate bundle, including `etymology_text`. The schema already supports the
  data after Phase 0 — this is a render-only change to `build_sections` and the
  client `RENDERERS`, deferred to keep this pass small.

---

## 7. Open items before coding

- **Confirm `import_kanjidic2.py`'s current sense attachment** so Phase 2 *moves*
  senses to `etymology_id` cleanly rather than double-attaching.
- **vPhon integration** replaces hand-written IPA rules: clone vPhon into
  `data/vphon/` (gitignored, not committed — GPL-3.0, so only its IPA *output*
  enters the DB), wire `scripts/import_vphon.py` into `rebuild_db.py`, and decide
  the tone notation (recommended `--chao`). The conversion itself is vPhon's job;
  the effort is the importer + plumbing, not phonology.
- **Migration vs rebuild:** ship the in-place migration and the
  `schema.sql`/importer edits together and verify they produce identical DBs
  (per the established convention).

---

## 8. Why this is "small"

- No table is removed or repurposed; the linguistic tree is unchanged in shape.
- One new thin table + two nullable columns cover both features.
- Vietnamese touches exactly one function's nesting logic; the fetch/resolve
  path is untouched.
- Japanese Phase 2 is a sense-attachment move + one menu-placement change; the
  larger render change is explicitly deferred.
- The dialect framework generalizes to Kansai, Hokkien, and Hakka sub-dialects
  with **no further structural change** — only data rows, a build-time importer
  (vPhon for Vietnamese), and transform modules where IPA is ours to derive.
</content>
</invoke>
