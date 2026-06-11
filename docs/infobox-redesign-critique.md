# Critique: `infobox-redesign-plan.md` (re-weighted for the extensibility goal)

**Reviewer role:** adversarial critic.
**Reframing:** the stated goal is to design the infobox plumbing so it can absorb a
*plethora of future sources*, with the sources themselves added separately. Designing
ahead of the data is therefore intentional, not premature. This list keeps only the
issues that survive that framing — genuine **redundancies**, **internal inconsistencies**,
and **places where the design works against its own extensibility goal** — and explicitly
withdraws the objections that were really just "this data doesn't exist yet."

All claims below were checked against `app.py`, `schema.sql`, `static/script.js`, and the
live `omnihanzi.db`.

---

## A. Issues that stand (and matter *more* at scale)

### A1. The manifest becomes a second source of truth competing with the DB

`info_options.json` hand-encodes ids and labels that are already normalized, seeded data:

- `languages` (id, name, sort_order, code)
- `transcription_systems` (id, **language_id**, name, code, sort_order, `UNIQUE(language_id, code)`)
- `sources` (id, short_name, …)

For a system whose whole purpose is to add many sources, having **two** authorities that
define "what languages / transcription systems / sources exist" is the central liability,
not a convenience. Adding a real new source already requires an importer (writes the DB);
the manifest forces a *second, manually-synchronized* edit that restates ids the importer
just created. Renumber a `ts` id or rename a system in `schema.sql` and the manifest drifts
silently — in two ways at once (wrong query id **and** stale label).

This does not mean "don't have a manifest." It means **split the concerns**:

- **Derive from the DB** everything the DB already owns: language/transcription/source
  ids, display names, and even menu nesting + ordering (`languages.sort_order`,
  `transcription_systems.sort_order` already exist). `/get_info_options` can serialize this
  out of a join just as easily as out of a file.
- **Keep in a small hand-authored overlay** only what the DB genuinely does *not* model:
  `default`-checked state, which `render.type` a node uses, and grouping that has no DB
  analogue.

The plan rejected DB-derivation in a single sentence ("must be consumed by both Python and a
sanitized client endpoint, so a neutral format is cleanest"). That is not an argument — Python
already consumes the DB, and the sanitized client endpoint can serialize from it. At 20 sources
the hand-maintained-ids approach is the thing most likely to rot.

**Severity: high. Gets worse linearly with the number of sources — i.e. directly opposes the goal.**

### A2. `tone_from: "trailing_digit"` is a redundant knob — the canonical value is already columnar

Verified in the DB:

```
cantonese readings with non-null tone : 34876 / 34886
readings.tone vs jyutping trailing digit : 34876 match, 0 mismatch
```

`readings.tone` is fully populated for Cantonese and agrees with the parsed jyutping digit in
**100%** of cases. The schema comment on `readings.tone` states its exact purpose: *"stored
here for convenience… allows tone-based queries without parsing strings."* The redesign should
**delete** this quirk and have the `readings` handler read `readings.tone` uniformly for every
tonal language. Instead the plan promotes the current string-parsing into a named per-source
parameter (`tone_from`). An extensible design should be *removing* per-source special cases
that the schema already normalizes away, not enshrining them as manifest config that every
future tonal source must reason about.

**Severity: medium (documentation correctness), trivial to fix.**

### A4. `_kana_to_romaji` is triplicated and re-run on every click

The romaji converter already exists twice — `app.py` and `scripts/dedup_readings.py` (whose
header literally says *"Mirror of … Duplicated"*). The plan keeps render-time conversion as the
`kana_romaji` value-transform, adding a **third** dependence on the same logic and re-deriving
Hepburn on every Japanese click, even though the dedup pass already established kana as
canonical and Hepburn for the kept readings is deterministic. For a hot path that will only get
hotter as sources grow, pick one: materialize Hepburn into `ts 30` at import for the kana-backed
readings (orphans already are), **or** centralize the converter in one importable module that
both `app.py` and the dedup script call. The plan does neither.

**Severity: medium. Redundancy + per-click recompute on the request path.**

### A5. The "one manifest entry = zero new code" claim is miscalibrated and should be stated honestly

The plan repeatedly sells "adding a source = one manifest entry, zero new server/client code."
The plan's *own* §8 data audit contradicts this: the interesting additions (IPA, Korean Revised
Romanization, Japanese on-subtypes, attested anything) need either a new `value_transform`
(server code) or a new importer + `data/` dump (a lot of code). The genuine "zero-code" case is
the *least* valuable one — a new transcription system in an *already-populated* `ts` that needs
none of the eight knobs. Since extensibility is the headline goal, the doc should set an honest
expectation: **a new source is typically importer + (sometimes) transform + (rarely) renderer;
the manifest entry is the cheap part, not the whole part.** Over-promising "one edit" will read
as a broken promise the first time a real source lands.

**Severity: low-medium (calibration / expectation-setting), but it's the plan's core pitch.**

---

## B. New concerns that exist *because* you're scaling to many sources

### B1. The design surfaces no source provenance — in an explicitly multi-source app

This is the biggest *omission* given the goal. Provenance is real, populated data:

```
reading_attestations rows            : 215907
readings attested by >1 source       : 54810
distinct sources (attestations/senses): 4
```

54,810 readings are already attested by multiple sources, and `senses.source_id` /
`reading_attestations` exist precisely to answer "which dictionary said this." A system built to
ingest a *plethora of sources* will inevitably need to show "reading per Unihan vs CC-CEDICT,"
badge a definition with its source, or let users filter by source. The redesign's response unit
is the **reading group**, and it explicitly reduces `source_priority` to "which *definitions*
win" — i.e. it **discards** attribution after using it to pick a winner. You are designing the
forward-looking contract right now; not reserving a place for `source` in the response shape
(`readings[].transcriptions[].source`, `senses[].source`) is the kind of thing that's cheap to
include in the schema today and expensive to retrofit into 20 sources' worth of renderers later.

**Severity: high for the stated goal. The plan optimizes for hiding source multiplicity; the goal implies surfacing it.**

### B2. Reading-group-as-query-unit can flatten cross-source disagreement

Related to B1. The plan's §3 modeling decision (definitions belong to a reading, not a
transcription) is **correct** and worth keeping. But pushing the *query/response* unit up to the
reading group, combined with "`dedup_readings.py` already merged duplicate readings," means the
contract has no way to express *source-level* disagreement about the readings themselves — only
about definitions. For two sources that attest *different* reading sets (not just different
glosses), the merged-group response can't say "Source X lists ⟨a,b⟩, Source Y lists ⟨b,c⟩." If
provenance display ever matters (B1), the unit-of-response choice forecloses it. Worth at least
an explicit "we are deliberately collapsing source-level reading provenance; revisit if a source
needs disjoint attribution."

**Severity: medium. A design fork worth naming now rather than discovering at source #6.**

### B3. Persisted leaf-id contract is brittle as the manifest reorganizes

Enabled leaf ids (`mandarin_pinyin`, …) become the persisted user state (§9, single
`infoOptions` key — the move out of the color namespace is good and should ship). But the plan
also says renamed ids "become harmless orphans — no migration needed; manifest defaults apply."
Across 10–20 sources the manifest *will* be reorganized, and every reorganization silently
resets affected user selections back to defaults with no migration path. For a few fields that's
fine; as the stable contract surface grows it deserves either id stability as a hard rule or a
tiny alias/migration map. Flag it now while the id scheme is still being designed.

**Severity: low, but cheap to address only while the id scheme is young.**

### B4. The eight-knob parameter surface is the real extensibility risk to watch

`handler`, `language_id`, `transcription_system_id`, `category`, `kind`, `tone_from`,
`drop_hash_defs`, `source_priority`, `value_transform`, `fallback_ts_id`, `primary`,
`definitions` — the parameter table is already larger than the seven fields it models, and the
goal guarantees it will grow as each new source contributes its own quirk-as-parameter. That is
the failure mode to guard against: a "declarative manifest" that accretes a per-source flag for
every dataset's idiosyncrasy is just imperative special-casing relocated into JSON, minus the
type-checking. Two of today's knobs are already removable — `tone_from` (A2, use the column) and
arguably `value_transform: "lower"` (trivial). Establish a **bar for adding a knob** (e.g. "must
generalize to ≥2 sources; one-off quirks get normalized at import instead") or this table is
where the complexity the redesign claims to eliminate will quietly re-accumulate.

**Severity: medium. The single most important discipline for hitting the extensibility goal.**

---

## C. The cheap wins worth pulling out of the big rewrite

Independent of whether the full manifest engine ships, these are low-risk and valuable now:

1. **Collapse the seven `_get_*` SQL bodies into one parameterized fetch.** This is the real,
   uncontroversial deduplication and should happen regardless.
2. **Surface the senses that already exist** for Japanese (24,117), Korean (514), Vietnamese
   (13) — a one-handler win the current code discards.
3. **Move language toggles out of the color `localStorage` namespace** (§9) — the single
   unambiguous, no-downside cleanup.
4. **Populate-and-use `readings.tone` uniformly**, deleting the jyutping string-parse path (A2).

---

## Bottom line

With extensibility as the goal, the speculative-generality objections mostly dissolve — but the
**redundancy and provenance** issues get *sharper*, because they're the ones that scale badly
with source count. Priorities:

1. **A1 / B1** — don't let the manifest become a second source of truth competing with the DB,
   and reserve a place for source provenance in the response shape *now*. These are the two
   decisions that are cheap today and expensive after 20 sources exist.
2. **B4** — set an explicit bar for adding per-source knobs, or the "declarative" manifest
   becomes imperative special-casing in JSON.
3. **A2 / A3 / A4** — delete the redundancies (`tone_from`, triplicated romaji) and fix the doc
   so already-shipped work isn't billed as future design.
