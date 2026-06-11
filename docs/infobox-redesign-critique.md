# Critique: `infobox-redesign-plan.md` (re-weighted for the extensibility goal)

**Reviewer role:** adversarial critic.
**Reframing:** the stated goal is to design the infobox plumbing so it can absorb a
*plethora of future sources*, with the sources themselves added separately. Designing
ahead of the data is therefore intentional, not premature.

**Status of this review:** the plan has since been revised to **derive the reading menu
from the DB** rather than from a hand-authored manifest. That revision resolved the entire
first batch of findings — the redundancy and "second source of truth" issues, which were
the heaviest ones. Those are listed under "Resolved" below and removed from the active list.
What remains are forward-looking concerns the revision did **not** address.

All claims below were checked against `app.py`, `schema.sql`, `static/script.js`, and the
live `omnihanzi.db`.

---

## Resolved by the DB-derived revision (removed from the active list)

- **A1 — manifest as a second source of truth.** The plan now builds the reading tree by
  querying `language_families` / `languages` / `transcription_systems` (§2, §4), keeping only
  a tiny `overlay.json` for defaults + labels. That is exactly the "derive from the DB, keep a
  small overlay" split A1 asked for.
- **A2 — `tone_from` redundant.** Deleted. §5 reads the populated `readings.tone` column
  uniformly for every tonal language.
- **A4 — `_kana_to_romaji` triplicated.** §11 adds `romaji.py` as the single shared converter
  imported by both `app.py` and `dedup_readings.py` — the resolution A4 offered.
- **A5 — "one manifest entry = zero code" oversold.** The manifest-knob model that claim rested
  on is gone; adding a transcription system is now a DB row that appears automatically (§8/§10),
  and the doc names the importer path explicitly. The specific miscalibration no longer exists.
- **B4 — the eight-knob parameter surface.** Those knobs (`tone_from`, `source_priority`,
  `kind`, `primary`, `value_transform`, `fallback_ts_id`, `drop_hash_defs`) are deleted,
  derived, or moved to `transcription_systems` columns / the importer (§5). §5 now states
  outright there is "no hand-authored parameter table for readings anymore." Premise dismantled.
- **C — cheap wins.** All four (collapse the `_get_*` bodies, surface existing senses, move
  toggles out of the color `localStorage` namespace, use `readings.tone`) are now part of the
  plan's build phases.

---

## Remaining concerns (still apply to the revised plan)

### B1. The design surfaces no source provenance — in an explicitly multi-source app

This is the biggest *omission* given the goal, and the revision did not touch it. Provenance is
real, populated data:

```
reading_attestations rows            : 215907
readings attested by >1 source       : 54810
distinct sources (attestations/senses): 4
```

54,810 readings are already attested by multiple sources, and `senses.source_id` /
`reading_attestations` exist precisely to answer "which dictionary said this." A system built to
ingest a *plethora of sources* will inevitably need to show "reading per Unihan vs CC-CEDICT,"
badge a definition with its source, or let users filter by source. The revised response shape is
still `{ readings: [ { transcriptions, tone, definitions } ] }` (§5) — **no `source` field
anywhere** — and §9 still orders definitions by `source_id` only to *discard* the attribution
afterward. You are designing the forward-looking contract right now; not reserving a place for
`source` in the response (`readings[].transcriptions[].source`, `senses[].source`) is cheap
today and expensive to retrofit into 20 sources' worth of renderers later.

**Severity: high for the stated goal. The plan optimizes for collapsing source multiplicity; the goal implies surfacing it.**

### B2. Reading-group-as-query-unit can flatten cross-source disagreement

Related to B1. The §3 modeling decision (definitions belong to a reading, not a transcription)
is **correct** and worth keeping. But pushing the *query/response* unit up to the reading group,
combined with "`dedup_readings.py` already merged duplicate readings," means the contract has no
way to express *source-level* disagreement about the readings themselves — only about
definitions. For two sources that attest *different* reading sets (not just different glosses),
the merged-group response can't say "Source X lists ⟨a,b⟩, Source Y lists ⟨b,c⟩." If provenance
display ever matters (B1), the unit-of-response choice forecloses it. Worth at least an explicit
"we are deliberately collapsing source-level reading provenance; revisit if a source needs
disjoint attribution."

**Severity: medium. A design fork worth naming now rather than discovering at source #6.**

### B3. No migration path when a persisted leaf id changes

Enabled leaf ids become the persisted user state (§9, single `infoOptions` key — the move out of
the color namespace is good and should ship). The revision improved this by deriving ids from the
stable `code` columns (`cmn:pinyin`) instead of hand-authored strings, so ids are now *more*
stable than before. But the plan still says renamed/orphaned ids "become harmless orphans — no
migration needed; defaults apply." The day a `transcription_systems.code` is renamed or a node is
renumbered, every affected user's selection silently resets to default with no alias map. Smaller
risk than in the manifest design, but the "no migration" stance is still a deliberate choice worth
stating as such while the id scheme (`:`-joined codes) is still young.

**Severity: low. Cheap to address only while the id scheme is being fixed.**

---

## Bottom line

The DB-derived revision did the heavy lifting: the redundancy and source-of-truth findings (A1,
A2, A4, A5, B4) are genuinely resolved, not papered over. The remaining concerns are all about
**source provenance**, which the revision left exactly where it was:

1. **B1 / B2** — the contract still collapses source multiplicity. Reserve a `source` slot in the
   response shape now; it is cheap today and expensive after 20 sources exist. This is the one
   forward-looking decision the revision should still make before building.
2. **B3** — decide id stability vs. a migration map deliberately, while the `:`-joined-code scheme
   is still being fixed.
