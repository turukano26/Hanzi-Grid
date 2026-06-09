# Hanzi Character Attributes (per `omnihanzi.db`)

In this database a hanzi character isn't a single flat row — it's a `codepoint`
in the `characters` table that everything else hangs off of. Below is every
attribute, grouped by where it lives.

## 1. Core identity — `characters`

| Attribute | Notes |
|---|---|
| `codepoint` | integer Unicode value, primary key (e.g. `29983`) |
| `character` | the glyph itself, e.g. `生` |
| `created_at` / `updated_at` | row timestamps |

## 2. Scalar attributes — `character_attributes` (key/value store)

These are the only "flat" per-character properties. There are exactly **4
distinct keys** currently populated:

| `key` | type | count | meaning |
|---|---|---|---|
| `stroke_count` | integer | 116,106 | number of strokes |
| `radical_number` | integer | 102,998 | Kangxi radical (1–214) |
| `grade_level` | integer | 2,632 | school grade (Jōyō / Kyōiku) |
| `frequency_rank` | integer | 2,501 | usage-frequency rank |

The table is extensible — any `key` / `value` / `value_type` with a `source_id`
can be added — but those four are all that's currently populated.

## 3. Readings & meanings (normalized tree)

A character has, per language, one or more etymologies, each with readings, each
with transcriptions and senses:

- **`etymologies`** — `language_id` (Mandarin, Cantonese, Middle/Old Chinese,
  Japanese, Korean, Vietnamese, etc. — 17 languages), `etymology_order`,
  `etymology_text` (origin explanation).
- **`readings`** — one pronunciation: `kind` (`reading` / `reconstruction`),
  `category` (`kun` / `on` for Japanese), `subcategory`, `tone`, `features`
  (JSON). Source attribution lives in the `reading_attestations` junction, not on
  the reading itself.
- **`reading_attestations`** — junction (`reading_id`, `source_id`, `notes`)
  recording which reference work(s) attest a reading; one reading row can have
  many attestations.
- **`reading_transcriptions`** — that reading written in a
  `transcription_system` (Pīnyīn, Wade-Giles, Zhùyīn, Jyutping, Yale, Hepburn,
  Kunrei-shiki, Kana, Hangul, Quốc Ngữ, Baxter-Sagart, Zhengzhang, IPA, … 24
  systems).
- **`senses`** — `definition`, `part_of_speech`, `register` (formal /
  colloquial / literary), `notes`.

## 4. Graphical / structural attributes

- **`character_glyphs`** — historical script images by `glyph_type`: Oracle
  Bone, Bronze Inscription, Small Seal, Clerical, Regular, Running, Cursive.
  (`image` BLOB or `image_path`, plus `attribution`.)
- **`character_components`** — decomposition: each `component_codepoint` with a
  `role` (`radical`, `phonetic`, `semantic`, `component`) and `position`
  (left / right / top / bottom / inner / enclosure…).
- **`character_variants`** — related forms by `variant_type`: Simplified,
  Traditional, Shinjitai, Kyūjitai, Chữ Nôm, Variant Glyph (links to another
  codepoint or an image).

## 5. Group membership

- **`character_set_members`** — which study sets (HSK, Jōyō, JLPT…) a character
  belongs to, via the `character_set_nodes` tree.

---

**Summary:** intrinsically a character carries only its codepoint/glyph plus the
4 scalar attributes (stroke count, radical number, grade level, frequency rank).
Everything else — readings, transcriptions, definitions, etymology, ancient
glyph images, component decomposition, variants, and set membership — is stored
as one-to-many relations keyed by `codepoint`, each tagged with a `source_id` so
the same fact can come from multiple authorities (CC-CEDICT, Unihan, Kanjidic2,
KanjiVG, CHISE IDS, etc.).

---

## Full attribute tree

Every field reachable from a single character (`codepoint`), with column types,
constraints, and enumerated values. `→` denotes a foreign-key relationship;
`[1:N]` marks one-to-many edges.

```
character (codepoint)
│
├─ characters .......................... core identity (1:1)
│   ├─ codepoint        INTEGER  PK      — Unicode scalar value, e.g. 29983
│   ├─ character        TEXT     UNIQUE  — the glyph, e.g. 生
│   ├─ created_at       TEXT             — datetime('now') default
│   └─ updated_at       TEXT             — datetime('now') default
│
├─ character_attributes [1:N] .......... extensible key/value scalars
│   ├─ id               INTEGER  PK
│   ├─ codepoint        INTEGER  → characters.codepoint
│   ├─ key              TEXT             — populated keys:
│   │                                       • stroke_count    (integer)
│   │                                       • radical_number  (integer, 1–214)
│   │                                       • grade_level     (integer)
│   │                                       • frequency_rank  (integer)
│   ├─ value            TEXT
│   ├─ value_type       TEXT             — CHECK ∈ {integer, real, text, json}
│   ├─ source_id        INTEGER  → sources.id
│   └─ UNIQUE(codepoint, key, source_id)
│
├─ etymologies [1:N] ................... one per (character, language, order)
│   ├─ id               INTEGER  PK
│   ├─ codepoint        INTEGER  → characters.codepoint
│   ├─ language_id      INTEGER  → languages.id
│   ├─ etymology_order  INTEGER          — default 1
│   ├─ etymology_text   TEXT             — origin explanation (optional)
│   ├─ UNIQUE(codepoint, language_id, etymology_order)
│   │
│   ├─ etymology_sources [1:N] ......... source attribution for the etymology
│   │   ├─ etymology_id  INTEGER  → etymologies.id  (ON DELETE CASCADE)
│   │   ├─ source_id     INTEGER  → sources.id
│   │   ├─ notes         TEXT
│   │   └─ PK(etymology_id, source_id)
│   │
│   └─ readings [1:N] ................. one distinct pronunciation (no source_id)
│       ├─ id            INTEGER  PK
│       ├─ etymology_id  INTEGER  → etymologies.id
│       ├─ kind          TEXT     — CHECK ∈ {reading, reconstruction}
│       ├─ category      TEXT     — e.g. kun, on  (Japanese)
│       ├─ subcategory   TEXT
│       ├─ tone          TEXT
│       ├─ sort_order    INTEGER
│       ├─ features      TEXT     — JSON blob
│       │
│       ├─ reading_attestations [1:N] .. which source(s) attest this reading
│       │   ├─ reading_id  INTEGER  → readings.id  (ON DELETE CASCADE)
│       │   ├─ source_id   INTEGER  → sources.id
│       │   ├─ notes       TEXT
│       │   └─ PK(reading_id, source_id)
│       │
│       ├─ reading_transcriptions [1:N] . reading rendered in a script/romanization
│       │   ├─ id                       INTEGER  PK
│       │   ├─ reading_id               INTEGER  → readings.id
│       │   ├─ transcription_system_id  INTEGER  → transcription_systems.id
│       │   ├─ value                    TEXT
│       │   └─ UNIQUE(reading_id, transcription_system_id)
│       │
│       └─ senses [1:N] ................ definitions for the reading
│           ├─ id              INTEGER  PK
│           ├─ reading_id      INTEGER  → readings.id
│           ├─ source_id       INTEGER  → sources.id
│           ├─ sort_order      INTEGER
│           ├─ definition      TEXT     NOT NULL
│           ├─ part_of_speech  TEXT     — noun, verb, adjective, …
│           ├─ register        TEXT     — formal, colloquial, literary, …
│           ├─ notes           TEXT
│           │
│           └─ examples [1:N] ......... usage examples for the sense
│               ├─ id               INTEGER  PK
│               ├─ sense_id         INTEGER  → senses.id
│               ├─ sort_order       INTEGER
│               ├─ example_text     TEXT  NOT NULL  — in source script
│               ├─ transliteration  TEXT            — romanized form
│               ├─ translation      TEXT            — English
│               └─ source           TEXT            — free-text attribution
│
├─ character_glyphs [1:N] .............. historical script images
│   ├─ id             INTEGER  PK
│   ├─ codepoint      INTEGER  → characters.codepoint
│   ├─ glyph_type_id  INTEGER  → glyph_types.id
│   ├─ image          BLOB             — PNG data (inline)        ┐ at least
│   ├─ image_path     TEXT             — or filesystem path       ┘ one required
│   ├─ source_id      INTEGER  → sources.id
│   ├─ attribution    TEXT             — credit line
│   └─ sort_order     INTEGER
│
├─ character_components [1:N] .......... decomposition into sub-glyphs
│   ├─ id                   INTEGER  PK
│   ├─ codepoint            INTEGER  → characters.codepoint
│   ├─ component_codepoint  INTEGER  → characters.codepoint
│   ├─ role                 TEXT  — CHECK ∈ {radical, phonetic, semantic, component}
│   ├─ position             TEXT  — left, right, top, bottom, inner, enclosure, …
│   ├─ source_id            INTEGER  → sources.id
│   ├─ sort_order           INTEGER
│   └─ UNIQUE(codepoint, component_codepoint, role)
│
├─ character_variants [1:N] ............ related glyph forms
│   ├─ id                  INTEGER  PK
│   ├─ codepoint           INTEGER  → characters.codepoint
│   ├─ variant_type_id     INTEGER  → variant_types.id
│   ├─ variant_codepoint   INTEGER  → characters.codepoint   ┐ at least
│   ├─ variant_image       BLOB                              │ one of the
│   ├─ variant_image_path  TEXT                              ┘ three required
│   ├─ source_id           INTEGER  → sources.id
│   └─ notes               TEXT
│
└─ character_set_members [1:N] ......... study-set membership
    ├─ node_id     INTEGER  → character_set_nodes.id
    ├─ codepoint   INTEGER  → characters.codepoint
    ├─ sort_order  INTEGER
    └─ PK(node_id, codepoint)
```

### Lookup / reference tables (the enumerations above resolve to these)

```
languages (→ language_families)
    family_id, name, code (ISO 639-3 / BCP-47), sort_order
    1  Mandarin            2  Cantonese          3  Hokkien
    4  Hakka               5  Shanghainese       6  Nanjing Dialect
    7  Middle Chinese      8  Old Chinese        10 Tokyo Standard
    11 Kansai Dialect      12 Ryukyuan           20 Standard Korean
    21 Jeju Dialect        30 Northern Vietnamese 31 Southern Vietnamese
    40 Sino-Xenic (General)

transcription_systems (→ languages)
    language_id, name, code, sort_order
    1  Pīnyīn              2  Pīnyīn (numbered)  3  Wade-Giles
    4  Zhùyīn (Bopomofo)   5  IPA                10 Jyutping
    11 Yale                12 IPA                20 Baxter-Sagart
    21 Zhengzhang          22 IPA                30 Hepburn
    31 Kunrei-shiki        32 Kana               33 IPA
    40 Revised Romanization 41 Hangul            42 Yale Romanization
    43 IPA                 50 Quốc Ngữ           51 IPA
    60 Stimson (kTang)

glyph_types
    1 Oracle Bone Script   2 Bronze Inscription  3 Small Seal Script
    4 Clerical Script      5 Regular Script      6 Running Script
    7 Cursive Script

variant_types (→ languages, optional)
    1 Simplified Chinese   2 Traditional Chinese 3 Shinjitai
    4 Kyūjitai             5 Chữ Nôm             6 Variant Glyph

sources
    id, name, short_name, source_type ∈ {dictionary, database, corpus,
        scholarly_work, standard, other}, url, version, notes
    1  CC-CEDICT           2  Unihan Database     3  Kanjidic2
    4  KanjiVG             5  Baxter & Sagart (2014) 6 Zhengzhang Shangfang
    7  Wiktionary          8  CHISE IDS           9  GB 2312
    10 Jōyō Kanji (2010)   11 CantoDict           12 Shuowen Jiezi

character_set_nodes (self-referential tree)
    id, parent_id → character_set_nodes.id, name, description (Markdown),
    sort_order, user_id (NULL = built-in)

language_families
    id, name, sort_order
```

---

## Source tracking (provenance)

Source attribution is **not uniform** across the readings/meanings tree — there
are three different mechanisms at three different granularities.

| Table | How source is tracked | Cardinality |
|---|---|---|
| `etymologies` | **No `source_id` column.** Attribution via the junction table `etymology_sources(etymology_id, source_id, notes)` | **many** sources per etymology |
| `readings` | **No `source_id` column.** Attribution via the junction table `reading_attestations(reading_id, source_id, notes)` | **many** sources per reading |
| `reading_transcriptions` | **No source field** — inherits its parent reading's source | (inherited) |
| `senses` | `source_id INTEGER NOT NULL → sources(id)` | exactly **one** source per sense |
| `examples` | free-text `source TEXT` column — **not** a foreign key | loose string (book, URL…) |

All `source_id` foreign keys resolve to the `sources` table (`name`,
`short_name`, `source_type`, `url`, `version`, `notes`). The same `source_id`
pattern also tags `character_attributes`, `character_glyphs`,
`character_components`, and `character_variants`.

### What this means in practice

- **Etymologies and readings are multi-sourced** via junction tables
  (`etymology_sources`, `reading_attestations`). A pronunciation confirmed by
  several references is **one** reading row with several attestation rows, each
  with its own `notes` — agreement is extra rows pointing at one fact, not
  duplicate facts. The importers still insert one reading per source, then a
  final `scripts/dedup_readings.py` pass (last step of `rebuild_db.py`) merges
  readings that spell the same pronunciation in the same transcription system,
  unioning their attestations, transcriptions and senses onto one survivor row.
  In the current build ~15k readings carry more than one source.
- **Senses are single-sourced by design.** Each sense carries its *own*
  `source_id`, because a definition's wording is source-specific — CC-CEDICT and
  Unihan phrase the same meaning differently, so it's genuinely a distinct row
  per source rather than a shared fact. A reading attested by **Unihan** can hang
  a definition from **CC-CEDICT**; the app's dedup logic relies on this,
  preferring CC-CEDICT senses over Unihan.
- **Transcriptions have no independent provenance.** A `reading_transcription`
  is just the reading rendered in a given system, so its source is whoever
  attests the reading; join through `reading_attestations` if you need it.
- **Examples are weakly sourced** — a free-text string rather than an FK into
  `sources`, so they're outside the structured provenance graph.

### Views that surface provenance

- **`v_sourced_senses`** — flattens `characters → etymologies → readings →
  senses → sources`, exposing each definition with its `source`
  (`src.short_name`). The canonical "which dictionary gave this meaning" lookup.
- **`v_character_readings`** — flattens readings + transcriptions but **omits** a
  source column, consistent with transcriptions inheriting their reading's
  source.

**Rule of thumb:** structured, FK-backed provenance is many-to-many (junction
tables) at the etymology and reading levels, single-source inline at the sense
level (because definition wording is source-specific), and absent/inherited at
the transcription level.

