# Critique — Dialect & Japanese Etymology Plan

**Reviews:** `docs/dialect_and_japanese_etymology_plan.md`
**Date:** 2026-06-16
**Stance:** Adversarial review — find flaws, over-engineering, and redundancy.
Grounded against the live schema (`schema.sql`), `app.py` (`_build_info_tree`,
`make_leaves`, `_resolve_ts_value`, `_fetch_reading_rows`, `_handler_readings`),
and the client renderers (`static/script.js`).

---

## 1. Headline problem: the central abstraction never reaches the output

The plan's whole §2 thesis is "dialect lives at the **transcription-group**
level," and §4.1 spends a new table (`transcription_groups`) plus the *one risky
migration step* — rebuilding `transcription_systems` to change a UNIQUE
constraint — to model it. Then §5.4 says the payoff is **"purely menu
presentation"** and that `_handler_readings` / `_fetch_reading_rows` are
**"Untouched."**

That is contradicted by the actual renderer. `static/script.js:221`:

```js
var headword = tr.map(function (t) { return escapeHtml(t.value); }).join(' / ');
```

The readings renderer emits **only `t.value`** and discards `t.label`. So when a
user enables Northern + Central + Southern IPA — three stored transcriptions on
the *same* reading row, all `code='ipa'`, all `label='IPA'` — the info sheet
renders three slash-joined IPA strings with **no indication of which dialect is
which**. The `transcription_groups` table built to organize them by dialect dies
at the menu and never labels the rendered data. As specified, the feature
produces unusable output for its own motivating use case.

Consequences:

- Either `RENDERERS.readings` must change to show the group/label → **"client
  untouched" is false**, or
- the section must be split by group server-side → **`_fetch_reading_rows` /
  `_handler_readings` are not untouched**.

Either way, three of the four "untouched" claims in §5.4 / §8 are wrong. The
plan undersells its own blast radius.

---

## 2. Over-engineering: `transcription_groups` is probably unnecessary

The stated Phase-1 requirement: Quốc Ngữ flat, three dialect IPAs available,
menu-nested by dialect. Everything that actually **renders** can be had without
a new table, without a new column, and without the UNIQUE-rebuild migration (the
single step the plan itself flags as "non-trivial"):

Create three flat transcription systems under the single Vietnamese language —
`ipa_north` / `ipa_central` / `ipa_south`, named "IPA (Northern)" etc. Distinct
codes → no UNIQUE collision, no `group_id`, no leaf-id scheme change
(`make_leaves` already does `prefix + ':' + code`). They render inline, and
their names carry the dialect (once the §1 `t.value`-only bug is fixed).

What does `transcription_groups` buy over that? **Exactly one thing: a
collapsible "Northern" submenu node in the options popup.** That is cosmetic
menu sugar, paid for with a new table + a column + the only schema-rebuild
migration in the plan. The recursive `buildMenuNode` (`script.js:360`) already
handles arbitrary depth and mixed leaf/parent siblings, so flat systems work in
the menu today.

The generality argument (§3: Kansai pitch, Hokkien Amoy/Zhangzhou) is the only
real defense, and forward-design for future sources is explicitly wanted. But an
abstraction earns forward-design weight only if it is **threaded through**. Right
now `group_id` is write-only: into the DB and into menu nesting, then it stops.
Until the render path consumes it, the table is speculative structure adding
migration risk and a second leaf-id depth for no rendered benefit.

**Recommendation:** either *commit fully* (thread `group` → `make_leaves` label
→ `_fetch_reading_rows` row → `RENDERERS.readings`, so output reads
"Northern: …"), or *defer the table* and ship distinct-coded flat systems now.
Half-threading is the worst of both.

---

## 3. Phase 2 scrambles the marquee example in the interim

The "Now" scope attaches Japanese senses to `etymology_id` but renders "a single
'Japanese — Definitions' section," deferring multi-etymology grouping. For 生 —
*the character used to motivate the entire etymology move* — "Now" merges the
definitions of multiple distinct etymologies into one flat list. That is
arguably **worse** than today, where senses are at least separated per reading.
The plan admits "Correct for the common single-etymology character" but never
acknowledges that its own headline example regresses in the interim: every
genuine multi-etymology kanji shows a meaning soup until the deferred grouping
lands.

---

## 4. Phase 2's code impact is undersold and underspecified

- **The senses fetch path is `reading_id`-only.** `_fetch_reading_rows`
  (`app.py:564`) pulls definitions via `WHERE s.reading_id = ?`. Move Japanese
  senses to `etymology_id` (`reading_id NULL`) and Japanese definitions silently
  vanish from that path. The plan calls `_fetch_reading_rows` "untouched" — but
  there is **no** etymology-level sense fetch anywhere, and the plan never
  defines the handler, section `type`, or query for the new "Japanese —
  Definitions" section. That is a new fetch + a new section emission, not "one
  menu-placement change."

- **The Japanese language node has no handler.** When a language has categories
  (on/kun), `_build_info_tree` builds the language node as pure nesting
  (`app.py:228`, no `handler`). A language-level Definitions section requires
  giving that node a handler or adding a sibling definitions group — a real
  restructure of the tree builder.

- **`sense_cats` detection** (`app.py:159-164`) joins `senses → readings →
  etymologies` via `s.reading_id`. Etymology-attached senses (`reading_id NULL`)
  drop out of that join, so the Definitions leaf *disappears* unless the query is
  rewritten. The plan mentions this in one clause; it is load-bearing.

---

## 5. Migration mechanics the plan waves at but doesn't specify

- **Re-parenting on the VN collapse.** "Collapse 30/31 into single Vietnamese" —
  which id survives, and what re-points `etymologies` / `readings` under the
  dropped language? `variant_types` row 5 (Chữ Nôm) FKs `language_id = 30`
  (`schema.sql:241`); if 30 isn't the survivor that breaks. Not addressed.

- **Sense dedup on the JP move.** If Kanjidic currently attaches the same glosses
  to each of N readings under one etymology, re-parenting to `etymology_id`
  creates N duplicate sense rows that must be merged — a `dedup`-style pass
  analogous to `dedup_readings.py`. Open-item #1 ("confirm attachment") gestures
  at this but does not plan the de-duplication.

- **localStorage.** Language toggles persist by leaf id (`script.js:380`).
  Collapsing 30/31, changing VN IPA leaf ids, and moving the JP Definitions leaf
  out from under On/Kun all change ids. Existing users' custom toggles for those
  silently reset to defaults. Probably acceptable, but it is an unstated
  user-visible regression; the plan claims localStorage compatibility nowhere.

---

## 6. Smaller things

- **The GPL reasoning in §5.1 is shaky** (the conclusion is fine). "Output is
  data, not derivative; runtime must not import it" conflates two things. GPL
  obligations trigger on *distribution of the combined work*, not on import; for
  a hosted Flask app nothing is distributed, so importing vPhon at runtime would
  not itself force GPL on the app (AGPL would be the relevant license, and vPhon
  is GPL-3.0, not AGPL). The genuine reasons to store-at-build-time are
  **engineering** ones — no runtime dep, no Python-version coupling, regenerable
  like Unihan/CEDICT. Lead with those; the license argument as written is
  half-right and will mislead a future reader.

- **Asymmetry worth stating plainly.** Every other IPA
  (Mandarin/Cantonese/Korean/Japanese) derives at runtime via
  `derived_from_ts_id` / `transform`; VN alone is stored. Defensible, but VN's
  IPA can't be regenerated without re-running the importer, and the derive-meta
  columns sit unused for VN. Document the asymmetry at the schema, since it
  breaks the otherwise-uniform `_resolve_ts_value` mental model.

- **Bundling.** Two unrelated features (VN dialect IPA, JP etymology senses)
  share only "the etymology tree is adequate." They touch different code and
  carry independent migrations. Shipping them as one migration multiplies risk
  for no shared benefit. Split them.

---

## 7. What to keep

- **§4.2 `senses.etymology_id` + XOR CHECK** is genuinely clean and correct —
  senses *should* hang at the etymology level, the table already exists for it,
  and the constraint is right.
- **§2 "what varies → which level" table** is good design thinking and the right
  framing.
- **Build-time-importer pattern for vPhon** matches the existing `scripts/`
  convention well.

---

## 8. Bottom line

The direction is sound. The problems are:

1. The marquee abstraction (`transcription_groups`) does not reach render and may
   be unnecessary for the stated requirement.
2. The "small / untouched" framing is contradicted by the actual fetch/render
   code in at least four places (§1, §4).
3. The interim Phase-2 state regresses the very example used to justify it (§3).

**Minimal alternative to weigh against the table-based version:** distinct-coded
flat VN IPA systems + the one `RENDERERS.readings` label fix + the etymology-sense
fetch/handler — compare blast radius before committing to the new table.
