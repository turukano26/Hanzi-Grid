# Critique: `infobox-redesign-plan.md` (re-weighted for the extensibility goal)

**Reviewer role:** adversarial critic.
**Reframing:** the stated goal is to design the infobox plumbing so it can absorb a
*plethora of future sources*, with the sources themselves added separately. Designing
ahead of the data is therefore intentional, not premature.

**Status of this review:** the plan has been revised twice since the original critique. The
first pass **derived the reading menu from the DB** (resolving the redundancy and "second source
of truth" issues — the heaviest ones); the second **added source provenance to the response
contract** (resolving B1/B2). Those are listed under "Resolved" below and removed from the active
list.

All claims below were checked against `app.py`, `schema.sql`, `static/script.js`, and the
live `omnihanzi.db`.

---

## Resolved (removed from the active list)

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
- **B1 — no source provenance in the response.** Addressed. §5 now returns attribution at the two
  levels the schema models: `"sources": [str]` per reading (`reading_attestations → sources.short_name`)
  and `{ "text", "source" }` per definition (`senses.source_id`); `attributes` rows gained a
  `source` too. A new §5 "Source provenance" subsection plus §7 (source badges) and §9 ("ordering
  no longer discards attribution") carry it through to render. The `source` slot is reserved before
  building, which was the ask.
- **B2 — reading-group flattens cross-source disagreement.** Addressed and named. §3 now states the
  reading group is the *display* unit, not a provenance-collapsing one: because `dedup_readings.py`
  unions every attesting source onto the surviving reading, each reading carries its full source set,
  and the "which source lists which reading" view is recoverable by inverting the per-reading source
  sets. Nothing is lost by merging. (The one residue: attestation is per-reading, not
  per-transcription — `reading_transcriptions` has no source column — so "which source supplied this
  exact romanization" is still not expressible. The plan calls this granularity out explicitly, which
  is the right move; it only matters if a future source disputes a transcription value rather than a
  reading.)

- **B3 — no migration path when a persisted leaf id changes.** Addressed. §9 now declares leaf ids a
  **stable, append-only contract**: the `:`-joined `code` chain is frozen once shipped (add new
  codes, never rename existing ones; label changes are fine because labels live in the overlay / DB
  `name` columns, not the id). That keeps a saved `infoOptions` list valid for the life of the app
  with no alias map, and the rule is adopted now while there is no user state in the wild. The one
  escape hatch — a deliberate `{ old_id: new_id }` migration if a `code` ever truly must change — is
  named explicitly.

---

## Bottom line

All findings are resolved. The DB-derived rewrite closed the redundancy and source-of-truth issues
(A1, A2, A4, A5, B4); the provenance pass closed B1/B2 by reserving `source` attribution at the
reading and definition levels and stating the merge-preserves-provenance invariant; the id-stability
decision closed B3. Nothing in this critique remains open against the current plan — it is ready to
build.
