# Plan: Audio for readings (machine-generated + native-speaker)

## Goal

Add **two audio options per language**, exposed in the info-box menu exactly like
two more transcription systems:

- **Machine-generated audio** — TTS, pre-generated in batch (option B).
- **Native speaker audio** — sourced human recordings (option C).

Both are per-language toggles (default **off**), sit alongside Pīnyīn / IPA / Kana /
etc. under each language, and attach to a **reading** (a pronunciation), not to each
text transcription — Pīnyīn, Zhùyīn, Wade-Giles and IPA of one Mandarin reading all
denote the same syllable, so they share one clip.

## Why "two transcription systems" is the right model

The menu, the request payload, and the resolve chain are already driven entirely off
`transcription_systems`:

- `_build_info_tree()` (`app.py:151`) turns every populated/derivable system into a
  menu leaf automatically (`make_leaves`, `app.py:203`).
- The client sends back the set of enabled leaf ids; `build_sections()` filters to
  `transcriptions = [leaf for leaf in active if 'ts_id' in leaf]` (`app.py:508`).
- `_fetch_reading_rows()` resolves each enabled system per reading via
  `_resolve_ts_value()` (`app.py:519`, `app.py:282`), including derived systems
  (IPA from Pīnyīn, Hepburn from Kana, etc.).

So if audio is modelled as transcription systems, we get menu leaves, persistence
(localStorage by leaf id), default-on/off, per-language scoping, and the
enabled-leaf request plumbing **for free**. The only thing audio breaks is the
assumption that a system resolves to an inline **text** `value`; an audio system
resolves to a **clip reference** instead and renders as a play button.

## Scope: which languages

Audio applies to the five living languages. **Middle Chinese is excluded** — it is a
reconstruction with no native speakers and no commercial TTS voice (consistent with
`memory/middle-chinese-ipa-deferred.md`).

| Language | TTS (B) | Native (C) | Canonical key for a clip |
|---|---|---|---|
| Mandarin | yes | yes (free toned-pinyin syllable sets, Wiktionary) | Pīnyīn (ts 1) |
| Cantonese | yes | yes (words.hk, jyutping syllable sets) | Jyutping (ts 10) |
| Tokyo Standard (JP) | yes | partial (Wiktionary, limited per-reading) | Kana (ts 32) |
| Standard Korean | yes | partial (Wiktionary/Forvo) | Hangul (ts 41) |
| Vietnamese | yes | partial (Wiktionary/Forvo) | Quốc Ngữ (ts 50) |
| Middle Chinese | — | — | (excluded) |

→ **10 new transcription-system rows** (5 languages × 2 provenances).

## Scale (from current `omnihanzi.db`)

180k readings, but audio dedupes hard to the distinct spoken syllable per language:

| Language | Readings | Distinct canonical values (~clips) |
|---|---|---|
| Mandarin | 56,142 | ~2,900 |
| Tokyo Standard | 46,354 | ~9,200 |
| Cantonese | 34,886 | ~2,200 |
| Standard Korean | 29,347 | ~8,600 |
| Vietnamese | 8,655 | ~4,700 |

Full TTS coverage ≈ **15–20k clips total**, ~a few hundred MB as Opus/MP3. Native
coverage is whatever the sources supply (sparse, especially for alternate readings).

---

## Data model

### 1. Mark audio systems on `transcription_systems`

Add a media-type column so the rest of the code can branch text-vs-audio:

```sql
ALTER TABLE transcription_systems ADD COLUMN media_type TEXT NOT NULL DEFAULT 'text'
    CHECK (media_type IN ('text', 'audio'));
```

Seed two audio systems per living language (IDs in a new reserved band, e.g. 70–79
to leave the existing per-language bands alone). `code` is the stable key
(`audio_tts`, `audio_native`); `sort_order` placed last so they appear after the
text systems:

```sql
INSERT INTO transcription_systems
  (id, language_id, name, code, sort_order, media_type, derived_from_ts_id, transform) VALUES
  -- Mandarin (canonical = Pīnyīn ts 1)
  (70, 1,  'Machine-generated audio', 'audio_tts',    90, 'audio', 1,  'audio_key'),
  (71, 1,  'Native speaker audio',    'audio_native', 91, 'audio', NULL, NULL),
  -- Cantonese (canonical = Jyutping ts 10)
  (72, 2,  'Machine-generated audio', 'audio_tts',    90, 'audio', 10, 'audio_key'),
  (73, 2,  'Native speaker audio',    'audio_native', 91, 'audio', NULL, NULL),
  -- Tokyo Standard (canonical = Kana ts 32)
  (74, 10, 'Machine-generated audio', 'audio_tts',    90, 'audio', 32, 'audio_key'),
  (75, 10, 'Native speaker audio',    'audio_native', 91, 'audio', NULL, NULL),
  -- Standard Korean (canonical = Hangul ts 41)
  (76, 20, 'Machine-generated audio', 'audio_tts',    90, 'audio', 41, 'audio_key'),
  (77, 20, 'Native speaker audio',    'audio_native', 91, 'audio', NULL, NULL),
  -- Vietnamese (canonical = Quốc Ngữ ts 50)
  (78, 30, 'Machine-generated audio', 'audio_tts',    90, 'audio', 50, 'audio_key'),
  (79, 30, 'Native speaker audio',    'audio_native', 91, 'audio', NULL, NULL);
```

**TTS systems derive** (`derived_from_ts_id` = the canonical text system, `transform =
'audio_key'`): they need **no stored `reading_transcriptions` rows**. The clip key for a
reading is just its canonical value (Pīnyīn, Kana, …), normalized. Because we
pre-generate a clip for every distinct canonical value, every reading that has a
canonical transcription automatically has TTS audio — same trick IPA uses.

**Native systems do not derive**: coverage is sparse and source-specific, so native
clips are recorded explicitly per reading (see junction below). `derived_from`/`transform`
stay NULL.

### 2. `audio_clips` — the deduped media registry

```sql
CREATE TABLE audio_clips (
    id           INTEGER PRIMARY KEY,
    language_id  INTEGER NOT NULL REFERENCES languages(id),
    provenance   TEXT    NOT NULL CHECK (provenance IN ('tts', 'native')),
    clip_key     TEXT    NOT NULL,            -- canonical pronunciation string (dedup key)
    file_path    TEXT    NOT NULL,            -- path under the audio asset dir (see Storage)
    media_type   TEXT    NOT NULL DEFAULT 'audio/ogg',
    source_id    INTEGER REFERENCES sources(id),   -- engine or recording source
    attribution  TEXT,                         -- credit line shown in the UI
    license      TEXT,                         -- e.g. 'CC-BY-SA-3.0', 'Polly-ToS'
    voice        TEXT,                         -- TTS voice / engine, or speaker note
    UNIQUE(language_id, provenance, clip_key)
);
CREATE INDEX idx_audio_clips_lookup ON audio_clips(language_id, provenance, clip_key);
```

One row per distinct syllable per provenance — this is where dedup lives. A TTS clip
for Mandarin `shēng` is one row reused by every 生/聲/牲… reading that resolves to it.

### 3. `reading_audio` — native clips per reading (sparse junction)

TTS needs no per-reading table (key derived). Native audio does, because only some
readings have a recording, and a reading can have several:

```sql
CREATE TABLE reading_audio (
    reading_id     INTEGER NOT NULL REFERENCES readings(id) ON DELETE CASCADE,
    audio_clip_id  INTEGER NOT NULL REFERENCES audio_clips(id),
    sort_order     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (reading_id, audio_clip_id)
);
CREATE INDEX idx_reading_audio_reading ON reading_audio(reading_id);
```

> Note: this gives native audio a different storage path from the
> `reading_transcriptions(reading_id, ts_id, value)` shape the resolve chain
> normally walks. `_resolve_ts_value` keeps working for the TTS (derived) system;
> native is resolved by a small dedicated lookup in the handler (see below). The
> alternative — stuffing a clip key into `reading_transcriptions.value` for ts
> `audio_native` — keeps one code path but loses multi-clip support and mixes media
> refs into a text column. Recommended: the junction.

### 4. Source rows

Add `sources` entries for each engine / recording corpus actually used, e.g. Amazon
Polly / Azure Speech / Google Cloud TTS / piper (for TTS provenance), and Wiktionary
(already source 7), words.hk, Forvo (for native). `audio_clips.source_id` +
`attribution` + `license` carry provenance to the UI.

---

## Storage & surviving DB rebuilds

`omnihanzi.db` is gitignored and **rebuilt from scratch** by `rebuild_db.py`
(`memory/rebuild-db-not-migrate.md`). Audio generation/sourcing is **expensive and
must not rerun on every rebuild**. So:

- **Clip files live outside the DB**, on disk under a persistent asset dir, e.g.
  `data/audio/<lang_code>/<provenance>/<hash>.ogg` (gitignored like other `data/`
  dumps; backed up / regenerated only deliberately). Do **not** store audio as BLOBs
  — keeps the DB small and lets a CDN/static route serve files directly.
- Each generation/sourcing run writes a **manifest** (`data/audio/manifest.jsonl`:
  one record per clip — language, provenance, clip_key, file_path, source,
  attribution, license, voice; plus, for native, the list of reading match keys).
- A new importer **`scripts/import_audio.py`** reads the manifest during a rebuild
  and populates `audio_clips` + `reading_audio`. It is idempotent and **skips
  cleanly when the manifest/audio dir is absent** (like `test_resolve_end_to_end`
  skips without a DB), so a fresh checkout / CI stays green and audio is purely
  additive. Wire it into `rebuild_db.py` after `dedup_readings.py`.

This decouples the slow, occasional generation step from the routine DB rebuild.

---

## Generation pipeline (B — machine-generated)

`scripts/generate_tts_audio.py`:

1. For each living language, `SELECT DISTINCT value` from `reading_transcriptions`
   for that language's canonical text system (Pīnyīn 1 / Jyutping 10 / Kana 32 /
   Hangul 41 / Quốc Ngữ 50). Normalize to a `clip_key` (the same normalization the
   `audio_key` transform applies at request time — see below).
2. Skip keys already present in the manifest (idempotent / resumable).
3. Synthesize one clip per key, write `data/audio/<lang>/tts/<hash>.ogg`, append a
   manifest record.

**Engine & input — recommended:** drive synthesis from the **IPA we already derive**
via SSML `<phoneme alphabet="ipa">`, with a language-appropriate neural voice
(Azure Speech / Google Cloud TTS support IPA phoneme input for cmn/yue/ja/ko/vi).
This ties directly into "each reading has IPA transcriptions" and gives the *exact*
reading rather than a character's default reading. Fallbacks where IPA-SSML is weak:
feed the native orthography (Kana / Hangul) or toned romanization. Offline option:
`piper` / `espeak-ng` for a zero-cost first pass.

> Important: synthesizing the **character** yields only its *default* reading and
> can't voice a specific alternate reading of a polyphone — that's why TTS is driven
> from the canonical transcription/IPA, not the glyph.

The `audio_key` transform (registered in `TRANSFORMS`, `app.py:115`) is just the
normalization function: given a reading's canonical value it returns the `clip_key`
used to look up `audio_clips`. It must match the normalization used at generation
time (one shared helper, e.g. `transcriptions/audio_key.py`, imported by both
`app.py` and the generator — same discipline as `kanaToRomaji` ↔ `romaji.py`).

## Sourcing pipeline (C — native)

`scripts/import_native_audio.py` (or per-source importers, mirroring
`import_cedict` / `import_cccanto`):

1. Ingest a source corpus (free toned-pinyin syllable MP3 set; jyutping syllable set
   / words.hk; Wiktionary–Commons CC-licensed single-char audio via category dumps;
   Forvo if licensed).
2. Each clip carries a syllable/romanization key + attribution + license. Match the
   key against the language's canonical transcription value to find the reading(s)
   it belongs to.
3. Copy the file to `data/audio/<lang>/native/…`, append a manifest record listing
   the matched reading keys; `import_audio.py` then creates the `audio_clips` row and
   the `reading_audio` links.

**Licensing is first-class:** store `license` + `attribution` + `source_id` per clip
and surface attribution in the UI (next to the play button, like glyph image
attributions at `script.js:503`). Don't ingest a source whose license forbids
redistribution without clearing it.

---

## Server changes (`app.py`)

1. **`TRANSFORMS`** (`app.py:115`): add `'audio_key': normalize_audio_key`.
2. **`_build_info_tree`** (`app.py:151`): no change needed — the new audio systems are
   populated/derivable so they become leaves automatically. (TTS leaves derive from a
   populated canonical system → included; native leaves need a populated check — see
   below.)
   - The populated-or-derivable gate (`app.py:189`) keys off
     `reading_transcriptions`. Native audio lives in `reading_audio`, not
     `reading_transcriptions`, so extend the "populated" set to also include audio
     systems that have any `reading_audio`/`audio_clips` rows, so an empty native
     system doesn't render a dead leaf.
3. **`_fetch_reading_rows`** (`app.py:519`): split enabled systems into text vs audio
   by `media_type`.
   - Text systems: unchanged (`trs` list of `{code, label, value}`).
   - Audio systems: resolve to clip(s) and append to a new per-row `audio` list:
     `{code, label, provenance, url, attribution}`.
     - TTS: `_resolve_ts_value` → `clip_key`; look up `audio_clips(language, 'tts',
       clip_key)`; if present emit a URL (`/audio/<id>` route or static path).
     - Native: query `reading_audio`→`audio_clips` for this `reading_id`.
   - A reading with only audio enabled (no text) must still render — relax the
     "inline_ts and not trs" empty-row guard (`app.py:567`) to also keep rows that
     have audio.
4. **Reading row shape** gains optional `audio: [{code, label, provenance, url,
   attribution}]` alongside `transcriptions`. Update the docstring/section-shape
   notes in `CLAUDE.md`.
5. **Serving**: add a route to stream clips (`/audio/<clip_id>` → send_file with
   correct mimetype + long cache header), or serve straight from `static/`/a CDN if
   the asset dir is web-exposed. Files, not BLOBs.

## Frontend changes (`static/script.js`)

1. **`readings` renderer** (`script.js:476`): after the headword span, render a play
   button per entry in `r.audio` — a 🔊 control whose handler does
   `new Audio(entry.url).play()`. Distinguish provenance visually (e.g. a small "TTS"
   vs speaker badge) and show `attribution` on hover/inline (reuse the
   `info-source` / `titleAttr` pattern at `script.js:482`).
2. Menu: nothing special — the two leaves arrive via `/get_info_options` like any
   transcription system and persist by id in localStorage automatically.

## Menu defaults (`overlay.json`)

Add all ten audio leaf ids to `default_off` so audio starts disabled, e.g.
`cmn:audio_tts`, `cmn:audio_native`, `yue:…`, `ja:…`, `ko:…`, `vi:…`. (Leaf ids
follow `make_leaves`: `lang_code[:category]:code`. Japanese is categorized on/kun, so
its ids are `ja:on:audio_tts`, `ja:kun:audio_tts`, etc. — confirm against the
generated tree.)

## Tests

- Unit-test `normalize_audio_key` (shared helper) so generation and request-time keys
  can't drift — same rationale as the romaji JS/Python sync tests.
- Extend `test_resolve_end_to_end.py` (DB-backed, skips without DB) with an
  audio-enabled click asserting the reading row carries an `audio` entry with a URL
  when a clip exists, and none when it doesn't.
- `import_audio.py` idempotency test against a tiny fixture manifest.

---

## Phasing

1. **Schema + plumbing, no clips yet.** Add `media_type`, `audio_clips`,
   `reading_audio`, the 10 ts rows, the `audio_key` transform, the handler audio
   branch, the route, and the renderer button. With no clips, leaves render but
   resolve to nothing (no dead UI). Rebuild DB. Ships the architecture.
2. **TTS batch (B).** `generate_tts_audio.py` + `import_audio.py`; generate Mandarin
   first (smallest, highest value), validate quality, then the other four. Full
   coverage of readings with a canonical transcription.
3. **Native (C).** Start with the best-covered free, redistributable corpora
   (toned-pinyin syllables, jyutping/words.hk, Wiktionary–Commons); add Forvo only if
   licensed. Sparse but high-quality, correct tones.

## Open decisions

- **TTS engine**: cloud neural + IPA-SSML (best quality, one-time cost) vs offline
  piper/espeak (free, lower quality). Recommend cloud for the shipped set, piper as a
  dev fallback.
- **Clip format/bitrate**: Opus/OGG (smallest) vs MP3 (broadest compatibility).
  Recommend Opus with an MP3 fallback only if a target browser needs it.
- **Native multi-clip UI**: show all recordings (multiple speakers) or just the
  first? Schema supports many (`reading_audio.sort_order`); UI can start with one.
- **Asset hosting**: serve from the app (`/audio/<id>`) vs a static CDN bucket.
  Junction/manifest design is agnostic; pick at deploy time.
