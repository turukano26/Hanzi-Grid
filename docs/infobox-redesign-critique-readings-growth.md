# Critique: `infobox-redesign-plan.md` — re-weighted for *readings* growth

**Reviewer role:** adversarial critic.
**Reframing (this pass):** the stated growth path is **readings** — new and old languages
and dialects (Hokkien, Jeju, Kansai, Zhuang, …) and **additional dictionaries per existing
language** (more Mandarin/Cantonese sources). The sources are added separately; the plan is
the plumbing. This critique evaluates the plan against *that* growth, not against attributes
or images.

All claims were checked against `app.py`, `schema.sql`, and the live `omnihanzi.db`.

---

## Withdrawn given the readings-growth clarification

An earlier pass argued the derivation optimized the "finished" readings tree and hand-waved
the growth surface. With readings as the growth path, that is **wrong** and is withdrawn:

- **Derivation aimed at the wrong half** — withdrawn. New languages/dialects *are* the
  derived `languages × transcription_systems × category` tree; adding one is a DB row + an
  importer and it appears in the menu automatically. The backbone is aimed correctly.
- **`attributes` handler underspecified** — downgraded to a footnote; attributes are not the
  growth path.
- **Glyph BLOB transport** — downgraded to peripheral; not readings.

What "more dialects + more dictionaries per language" *does* expose is a different set of
gaps, all on the **source/dictionary dimension** and the **per-reading display semantics**.

---

## 1. The source/dictionary is your main growth axis — and the menu derivation ignores it

**Severity: high.**

Adding "another Mandarin dictionary" (ABC, Guoyu Cidian, …) is not a new language or
transcription system. It is a new `sources` row plus an importer that adds senses
(`senses.source_id = X`) and reading attestations. But the menu is derived from
**language → category → transcription_system**; **source is not a menu axis at all.**

Consequence with five Mandarin dictionaries: a character's Mandarin section renders *every*
dictionary's glosses concatenated under one pinyin headword, and the single "Definitions"
toggle is all-or-nothing — the user cannot show ABC but hide CEDICT.

The asymmetry is the tell. The plan already derives one reading-partition axis from the DB —
`DISTINCT readings.category` → on/kun sub-nodes (§4) — but does **not** derive the analogous
`DISTINCT senses.source_id` / `reading_attestations.source_id` → per-dictionary sub-nodes,
even though *that* is the dimension the sources multiply along. The plan defers it to a
someday "filter by source later" (§5). For a multi-dictionary goal, source-as-a-toggle is
core, not later — the derivation models every reading axis **except the growing one**.

## 2. `source_priority` was deleted, but multi-dictionary is exactly when it is needed

**Severity: medium-high.**

The plan removed `source_priority`, arguing the default `ORDER BY source_id` "already yields
CEDICT before Unihan," with a `sources.priority` column only "*if a future source ever needs
a non-id order*" (§5, §9). With many dictionaries per language as a stated goal, that "if" is
"immediately": `ORDER BY source_id` is just **insertion order** — whichever dictionary was
imported first wins the top slot, arbitrarily. Wanting "prefer ABC's gloss first for Mandarin"
without re-importing to renumber source ids is a baseline requirement of the goal. The
`sources.priority` column (a DB column, matching the plan's own pattern) belongs in the plan
**now**, not dismissed as hypothetical. The thing that was cut is the thing the goal demands.

## 3. "primary" and "default-on" are derived from `sort_order` — already wrong for Korean, and every incoming dialect has multiple romanizations

**Severity: medium-high, and recurring per dialect.**

Verified Korean break: transcription systems under language 20 are Revised-Rom (sort 1,
empty → skipped), Hangul (sort 2), Yale (sort 3). The derived primary/default ("lowest
`sort_order` that renders") is therefore **Hangul**, while the current app (`_get_korean`)
uses **Yale**. §8 claims parity for `korean`; the derivation rule silently breaks it.

The clarification makes this systemic. **Hokkien (POJ vs Tâi-lô), Cantonese
(Jyutping/Yale/IPA), Mandarin (Pinyin/Zhùyīn/Wade)** — every dialect being added ships
*multiple* romanizations, so for each one "which is the headword" and "which is on by
default" are silently encoded in `sort_order`, a column authored for menu ordering. That
overloads `sort_order` with three meanings at once (display order, primary headword,
default-checked), and forces per-dialect hand-tuning of one column to get the right headword.
A scholar adding Hokkien who wants Tâi-lô primary but POJ listed first cannot express it.

**Move "primary" and "default" out of `sort_order`** — into the overlay or an explicit
column. This is exactly the value-coupling the plan avoids elsewhere.

## 4. `category_labels` in the overlay is under-modeled, and dialects flood it on arrival

**Severity: medium.**

`readings.category` is on/kun today (Japanese only), but the schema comment notes it also
means literary/colloquial — and **Hokkien's 文白 (literary vs colloquial) split is a defining
feature**, as for other Min/Yue varieties. As dialects arrive, `category` gets populated
widely, and the menu derives a sub-node per `DISTINCT category` with its label coming from the
overlay's flat `category_labels` map.

Two problems that bite immediately:

- The map is a **global `code → label`** dict, but category semantics are
  **language-specific**: a "literary" node under Hokkien may want different labeling/treatment
  than elsewhere, and codes can collide. It should be keyed by language — i.e. a
  `reading_categories(language_id, code, label, sort_order)` table.
- The plan calls that table a "someday, if labels proliferate" nicety (§4). With the listed
  dialects they proliferate on arrival, so the table is part of the **initial** design, not a
  deferral.

The overlay grows in lockstep with the growth area — which is the coupling the DB-derivation
was supposed to eliminate.

## 5. The string couplings (overlay ids, `transform` names) grow with every dialect and are unvalidated

**Severity: medium.**

Every new dialect potentially adds overlay `default_off`/primary entries that hand-encode
derived `:`-joined ids, and possibly a `transcription_systems.transform` string that must
match a `TRANSFORMS` key in `app.py`. None of these are FK'd or checked. Across ~15 dialects
this is a steady accumulation of stringly-typed DB ↔ code ↔ overlay references that fail
**silently** (a default flips, a transform no-ops) on a typo or rename. At minimum the plan
should commit to **startup validation**: every seeded `transform` resolves to a registered
function; every overlay id resolves to a real node. Otherwise the silent drift the redesign
was built to kill has been reintroduced, just spread across three files.

---

## Still-minor (unchanged by the clarification)

- **`transform` has muddy dual semantics.** `kana_romaji` *converts from* `derived_from`,
  while `lower` *post-processes the system's own* stored value — and `lower` being
  system-level means search/export get it too. One column, two jobs. Low-medium.
- **`handler` and `render.type` are 1:1** yet both are hand-written on non-reading nodes.
  Since the growth is readings (which hand-write neither), this is now genuinely minor.
- **"The single SELECT all seven functions duplicate" is aspirational** — per-reading `senses`
  and `attestations` are N+1 fan-out, and that fan-out *grows with the number of attesting
  dictionaries*. Fine for local SQLite, but it is not one SELECT. Low-medium.
- **Korean/Vietnamese Definitions default-on** yields near-empty toggles (Vietnamese has 13
  senses total). Low.
- **`info_sections/definitions.py` "retire or realign"** is unresolved indecision. Low.

---

## Bottom line

With readings as the growth axis, the menu-from-DB backbone is right: adding a language or
transcription system is close to free. The real gaps are all on the **source/dictionary
dimension and per-reading display semantics** — precisely what "more dictionaries per language
+ more dialects" stresses:

1. **Model source as a first-class reading axis** — derive per-dictionary toggles
   (`DISTINCT senses.source_id`) the way category sub-nodes are derived, and add
   `sources.priority`. Highest-value change; currently absent.
2. **Move "primary" and "default-on" out of `sort_order`** — every multi-romanization dialect
   needs them set deliberately; Korean already proves the derived rule wrong.
3. **Promote `reading_categories` from "someday" to now** — literary/colloquial categories
   arrive with the first Min/Yue dialect; the flat overlay map won't carry them.
4. **Validate the DB ↔ code ↔ overlay string couplings at startup**, since they now scale with
   dialect count.

Items 1 and 2 are worth blocking the build on: both are cheap before the first new dialect
lands and awkward after.
