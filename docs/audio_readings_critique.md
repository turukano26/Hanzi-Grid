# Critique — Audio Readings Plan

**Reviews:** `docs/audio_readings_plan.md`
**Date:** 2026-08-04
**Stance:** Adversarial review — hunt for unneeded complexity and fragile
design. Grounded against the live `omnihanzi.db` (counts re-run, not taken from
the plan), `app.py` (`TRANSFORMS`, `_build_info_tree`, `make_leaves`,
`_resolve_ts_value`, `_fetch_reading_rows`), `overlay.json`, `static/script.js`
(`RENDERERS.readings`), and `Dockerfile`.

---

## 0. What the plan gets right

The central judgment is sound and should survive any rewrite:

- **Audio as transcription-system leaves.** The menu, localStorage persistence,
  per-language scoping, default state, and the enabled-leaf request payload all
  come free, exactly as the plan argues. No new menu concept is needed.
- **A clip attaches to a *reading*, not to a text transcription.** Pīnyīn,
  Zhùyīn, Wade-Giles and IPA of one Mandarin reading denote one syllable and
  share one clip. This is the right granularity.
- **Files on disk, not BLOBs**, and **generation decoupled from `rebuild_db.py`**
  (audio must not be re-synthesized on every rebuild).
- **Middle Chinese excluded** — consistent with
  `memory/middle-chinese-ipa-deferred.md`.

Everything below is about the layers built on top of that.

---

## 1. `reading_audio` is unneeded, and it defeats its own justification

This is the plan's largest self-inflicted complexity.

§3 introduces the `reading_audio` junction so that "a reading can have several
[native clips]" — but §2's constraint forbids exactly that:

```sql
UNIQUE(language_id, provenance, clip_key)
```

Two native recordings of the same syllable cannot both exist. So the multi-clip
feature the junction was added for **is impossible as specified**. The junction
delivers nothing the derived path doesn't.

Worse, §"Sourcing pipeline (C)" step 2 says native clips are matched *by
syllable/romanization key against the language's canonical transcription value* —
which is precisely how TTS resolves. Native and TTS differ in **provenance and
coverage, not in addressing**.

**Recommendation:** make native derive too (`derived_from_ts_id` = the canonical
text system, `provenance = 'native'`), identical to TTS. That deletes, in one
move:

- the `reading_audio` table and its index,
- the second resolution branch in the handler (§"Server changes" 3),
- the special-case extension of the populated-set check in `_build_info_tree`
  (§"Server changes" 2, the sub-bullet),
- the apologetic note in §3 about native taking a different storage path from
  the resolve chain.

The junction earns its place only if a native clip attaches to one *specific*
reading by something other than its canonical value (e.g. a recording valid for
one etymology but not its homophone twin). Nothing in the plan does that. If
that requirement appears later, add the junction then — and relax the UNIQUE at
the same time.

---

## 2. The `audio_key` transform is a drift contract you can delete

Two problems, one small and one structural.

**Small:** `TRANSFORMS` (`app.py:115`) is a registry whose contract is
*text → displayable text*; every entry produces something the headword renders.
`audio_key` returns a lookup key instead. It stays invisible only because the
new `media_type` branch keeps that system out of `trs`. Any future path that
resolves systems without consulting `media_type` renders a raw clip key as a
pronunciation.

**Structural:** the plan then commits to a shared normalizer imported by both
`app.py` and the generator, "same discipline as `kanaToRomaji` ↔ `romaji.py`",
plus unit tests whose stated purpose is to stop the two sides drifting. That is
a permanent maintenance obligation created entirely by the decision to
normalize.

**Recommendation:** make `clip_key` the **exact resolved canonical value**, and
dedup identical *audio* at the file layer (content-addressed filename) rather
than at the key layer. `audio_clips` rows are cheap text; several keys pointing
at one file costs nothing. Then:

- request time is a plain equality lookup — no transform, no registry entry,
- generation is `DISTINCT` over resolved values — same strings by construction,
- there is no shared helper, no sync test, and nothing to drift.

If normalization is kept anyway, it must be specified against the real data, not
hand-waved. What is actually in the DB today:

| Hazard | Distinct values affected |
|---|---|
| Kana readings carrying okurigana `.` / affix `-` | 2,705 |
| Jyutping changed-tone `*` notation (e.g. `paau4*2`) | 1 |
| Malformed Pīnyīn (`qiǎn1wa`, `qiàn1ke`, …) | 13 |

The malformed Pīnyīn matters beyond normalization: a naive generator will spend
synthesis budget producing clips for garbage keys. Validate keys before
synthesis.

---

## 3. `manifest.jsonl` is a third source of truth carrying mostly constants

For the TTS run, a per-clip JSONL of ~15k records stores `language`,
`provenance`, `source`, `attribution`, `license`, `voice` — all **constant per
run** — alongside the only two varying fields, `clip_key` and `file_path`. And
`file_path` is derivable from `clip_key` under any sane naming scheme.

**Recommendation:** per-batch `meta.json` (the constants) + a directory scan (the
keys, from filenames). Keep a per-clip JSONL only for **native**, where
attribution, speaker and license genuinely vary clip-by-clip — that is the case
the format was designed for.

Related gap: §"Storage" specifies `data/audio/<lang>/<prov>/<hash>.ogg` but never
says what `<hash>` hashes. If it is content, regeneration renames files and
invalidates every cached URL. If it is the key, say so.

---

## 4. The ten `default_off` entries are dead config

§"Menu defaults" adds all ten audio leaf ids to `overlay.json`'s `default_off`.
`make_leaves` sets:

```python
'default': (i == 0),   # primary = lowest sort_order, on by default
```

over systems already ordered by `sort_order` (`app.py:206-213`). Audio sits at
`sort_order` 90/91, so it is never index 0 and is already off. `overlay.json`
says as much itself:

> List here only the ids that the derived rule would turn ON but should start
> OFF.

**Recommendation:** delete the section. It also removes the plan's own caveat
about having to work out the Japanese per-category id spellings
(`ja:on:audio_tts` / `ja:kun:audio_tts`) — those ids stop mattering.

---

## 5. `provenance` is encoded twice and must stay in agreement

Provenance appears in the ts `code` (`audio_tts` / `audio_native`) *and* as a
CHECK-constrained column on `audio_clips`. A lookup then joins on
`(language_id, provenance)` — a pair that reconstructs, by hand, what a single ts
row already identifies.

**Recommendation:** key `audio_clips` on `ts_id` (FK to `transcription_systems`)
with `UNIQUE(ts_id, clip_key)`. Language and provenance come along for free,
there is one enum instead of two, and the lookup is single-column.

---

## 6. `media_type` means two different things in two tables

- `transcription_systems.media_type` — a *kind*: `'text' | 'audio'`.
- `audio_clips.media_type` — a *MIME type*: `'audio/ogg'`.

Same name, same schema, unrelated semantics. Rename one: `kind` on the system,
`mime_type` on the clip.

---

## 7. Generation enumerates stored values; the request path resolves derived ones

§"Generation pipeline" step 1:

> `SELECT DISTINCT value` from `reading_transcriptions` for that language's
> canonical text system

But `_resolve_ts_value` (`app.py:282`) resolves through `derived_from` chains.
Measured against the live DB:

| Japanese readings | Count |
|---|---|
| Total | 46,354 |
| With a stored Kana (ts 32) value | 37,045 |
| **With Hepburn but no Kana** | **9,309** |

Those 9,309 readings resolve their Kana at request time via the `romaji_kana`
transform, producing keys that a stored-value enumeration never generated. Some
20% of Japanese readings would silently have no audio.

**Recommendation:** generation must enumerate through the *same* resolve chain
the request path uses — iterate readings and call `_resolve_ts_value`, not
`SELECT DISTINCT value`. (This is also the cheapest way to guarantee generation
and lookup agree, and it composes with §2's "key = exact resolved value".)

---

## 8. Deployment is a hole, not an open decision

§"Open decisions" defers asset hosting to "pick at deploy time". It cannot be
deferred — it determines what `file_path` even means.

`Dockerfile`:

```dockerfile
COPY . .
RUN python scripts/rebuild_db.py    # builds the DB at image-build time
```

`.gitignore` excludes `data/`. So at image build there is **no `data/audio/`**,
and `import_audio.py` — correctly written to skip cleanly when the manifest is
absent — will skip. The production image ships **zero clips**, and every audio
leaf is dead. Separately, a few hundred MB of clips is a poor fit for a slug or
image layer even if they were present.

**Recommendation:** decide now, and pick the option that makes local and
production the same code path — store a resolvable **URL or object-store key** on
the clip row rather than a repo-relative path. A local dev run can point that at
a filesystem prefix; production points it at a bucket/CDN. The `/audio/<id>`
route then becomes optional rather than load-bearing.

---

## 9. Phase 1 ships ten toggles that do nothing

§"Phasing" 1 claims "with no clips, leaves render but resolve to nothing (no dead
UI)". Leaves that render and do nothing **are** dead UI. And they will render:
the gate is

```python
if ts_id not in populated_ts and derived_from not in populated_ts:
    continue                                        # app.py:189
```

A TTS system deriving from Pīnyīn (populated) passes immediately — clips or no
clips.

**Recommendation:** make the gate uniform for audio systems — an audio leaf
renders only when that language actually has clips. Note this is the *same* check
the plan already wanted to add for native (§"Server changes" 2); applying it to
both is simpler than applying it to one. Phase 1 then ships genuinely invisible
architecture, and each language lights up as its clips land — which is also the
natural phase-2 increment.

While there, state the intended behavior for coverage gaps within an enabled
language: leaf on, individual reading silently shows no button. That is
acceptable, but it should be a decision rather than an accident.

---

## 10. Smaller fragilities

**Route safety.** `/audio/<clip_id>` → `send_file(file_path)` where `file_path`
was written by an importer needs a `realpath` containment check against the asset
root. Cheap to add, unpleasant to discover later.

**Frontend mechanics don't match the renderer.** `RENDERERS` build HTML strings
for `innerHTML` (`script.js:476-489`), so the plan's `new Audio(entry.url).play()`
implies an inline `onclick` with a URL interpolated into an attribute. Use a
delegated click listener on the info box keyed off `data-audio` attributes, and a
single shared `Audio` element so rapid clicking replaces the current clip instead
of overlapping several.

**Query amplification.** `_fetch_reading_rows` already issues 2–3 queries *per
reading row* (transcriptions, attestations, senses). Adding a clip lookup per
reading per enabled audio system compounds that on characters with many readings.
Fold the clip join into the existing per-reading pass.

**The end-to-end test passes vacuously.** `test_resolve_end_to_end.py` runs
against the developer's real DB, which has no clips — so an "assert the row
carries an audio entry" test will skip or trivially pass. Insert a fixture clip
row inside the test rather than relying on skip semantics.

---

## 11. The TTS input strategy is the most fragile technical choice

§"Generation pipeline" recommends driving synthesis from **the IPA we already
derive**, via SSML `<phoneme alphabet="ipa">`, uniformly across all five
languages. Three problems:

1. **Our IPA is display-oriented.** `pinyin_ipa`, `jyutping_ipa`, `hangul_ipa`,
   `quocngu_ipa` are broad transcriptions tuned for a human reading a chart —
   tabulated rime tables, representative codas, Chao tone letters. They were
   never validated as synthesizer input, and coupling audio quality to them means
   any future display refinement is also an audio regression risk.
2. **Engine IPA support is partial and per-locale.** `<phoneme alphabet="ipa">`
   coverage for cmn / yue / ja / ko / vi is uneven and thinly documented, and
   **tone letters are commonly ignored** — which discards precisely the
   information the exercise exists to preserve.
3. **Three of the five languages don't need it at all.** Japanese (Kana), Korean
   (Hangul) and Vietnamese (Quốc Ngữ) canonical values *are* native orthography
   that engines accept directly as text, with correct prosody. Feeding them
   through IPA is a downgrade.

**Recommendation:** replace the single recommendation with a per-language input
table. Japanese/Korean/Vietnamese: feed the canonical value as plain text.
Mandarin and Cantonese are the genuinely hard cases (the glyph is polyphone-
ambiguous, and romanization fed as text is read as English letters) — those are
where SSML phoneme input, or a per-syllable representative-character trick, has
to be evaluated, per engine, with listening tests. The plan's own warning about
never synthesizing the glyph remains correct and important.

---

## 12. The scale numbers are wrong, and the phasing follows from them

Re-run against the live `omnihanzi.db` (distinct values of each language's
canonical transcription system):

| Language | Plan's estimate | Actual distinct | Readings |
|---|---|---|---|
| Mandarin (Pīnyīn, ts 1) | ~2,900 | **1,573** | 56,142 |
| Cantonese (Jyutping, ts 10) | ~2,200 | 2,176 ✓ | 34,886 |
| Japanese (Kana, ts 32) | ~9,200 | **6,220** | 46,354 (37,045 with kana) |
| Korean (Hangul, ts 41) | ~8,600 | **555** | 29,347 |
| Vietnamese (Quốc Ngữ, ts 50) | ~4,700 | 4,661 ✓ | 8,655 |
| **Total** | 15–20k | **~15.2k** | |

The total survives by luck; three of five per-language figures do not.

Consequences for §"Phasing" 2, which proposes "generate Mandarin first
(smallest, highest value)":

- **Korean is off by 15×.** At 555 clips — one Hangul syllable per hanja reading,
  a closed set — complete Korean coverage is a rounding error in cost and time.
  Combined with §11 (Hangul is the *easiest* engine input of the five), Korean is
  the obvious first language and the best end-to-end pipeline validation, not a
  phase-3 straggler.
- **Mandarin is 1,573, not 2,900** — still second-cheapest, and it is the harder
  synthesis case, so it is a poor choice for validating the pipeline first.
- **Vietnamese has by far the worst dedup ratio** — 4,661 clips for 8,655
  readings (~1.9 readings per clip, versus ~53:1 for Korean). It is the expensive
  language per unit of coverage; schedule it last.

Suggested order: **Korean → Cantonese or Mandarin → Japanese → Vietnamese**,
with the caveat that Cantonese and Mandarin ordering depends on which engine
handles Sinitic phoneme input acceptably (§11).

---

## Summary of recommended changes

| # | Change | Effect |
|---|---|---|
| 1 | Native derives like TTS; drop `reading_audio` | −1 table, −1 handler branch, −1 tree special case |
| 2 | `clip_key` = exact resolved value; drop `audio_key` transform + shared normalizer | −1 registry violation, −1 permanent sync contract |
| 3 | Per-batch `meta.json` + dir scan for TTS; JSONL only for native | −15k redundant records |
| 4 | Delete the `default_off` section | Dead config, plus its Japanese-id caveat |
| 5 | Key `audio_clips` on `ts_id` | −1 duplicated enum, simpler lookup |
| 6 | Rename `media_type` on one of the two tables | Removes a real ambiguity |
| 7 | Generate via `_resolve_ts_value`, not stored values | Fixes 9,309 silently audio-less JA readings |
| 8 | Store a URL/object key; decide hosting now | Production currently ships zero clips |
| 9 | Uniform clip-existence gate on audio leaves | Phase 1 stops shipping dead toggles |
| 10 | Path containment, delegated click handler, shared `Audio`, folded query, real test fixture | Assorted |
| 11 | Per-language TTS input strategy, not uniform IPA-SSML | Decouples audio quality from display transcribers |
| 12 | Re-base counts; start with Korean | Cheapest + easiest language validates the pipeline |
