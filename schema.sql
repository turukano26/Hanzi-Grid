-- ============================================================
-- omni-hanzi SQLite schema
-- ============================================================
--
-- Hierarchy:
--   Character (codepoint)
--     → Etymology (per language — usually one, sometimes multiple)
--       → Reading (one per distinct pronunciation)
--         → Transcription (same sound in different systems: pinyin, IPA, …)
--         → Sense (definition, with optional POS / register tags)
--           → Example
--
-- Parallel to that linguistic tree, characters also have:
--   • Glyphs        — historical script images (oracle bone, seal, etc.)
--   • Variants      — simplified/traditional, shinjitai/kyūjitai, chữ nôm
--   • Components    — radical decomposition (bidirectional)
--   • Set membership — HSK level, Jōyō grade, etc.
--
-- The codepoint (INTEGER) is the primary key for characters.
-- SQLite INTEGER PRIMARY KEYs are stored in sorted order, so
-- "ORDER BY codepoint" is essentially free.
--
-- Future: multi-character words can be added via a `words` table
-- that shares the etymology→reading→sense→example chain.
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;


-- ============================================================
-- 1. LOOKUP / REFERENCE TABLES
-- ============================================================

CREATE TABLE language_families (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

INSERT INTO language_families (id, name, sort_order) VALUES
    (1, 'Sinitic',   1),
    (2, 'Japonic',   2),
    (3, 'Koreanic',  3),
    (4, 'Vietic',    4),
    (5, 'Other',     5);


CREATE TABLE languages (
    id          INTEGER PRIMARY KEY,
    family_id   INTEGER NOT NULL REFERENCES language_families(id),
    name        TEXT    NOT NULL UNIQUE,
    code        TEXT,                       -- ISO 639-3 / BCP-47 when available
    sort_order  INTEGER NOT NULL DEFAULT 0
);

INSERT INTO languages (id, family_id, name, code, sort_order) VALUES
    -- Sinitic
    (1,  1, 'Mandarin',              'cmn',  1),
    (2,  1, 'Cantonese',             'yue',  2),
    (3,  1, 'Hokkien',               'nan',  3),
    (4,  1, 'Hakka',                 'hak',  4),
    (5,  1, 'Shanghainese',          'wuu',  5),
    (6,  1, 'Nanjing Dialect',        NULL,  6),
    (7,  1, 'Middle Chinese',        'ltc',  7),
    (8,  1, 'Old Chinese',           'och',  8),
    -- Japonic
    (10, 2, 'Tokyo Standard',         'ja',  1),
    (11, 2, 'Kansai Dialect',          NULL,  2),
    (12, 2, 'Ryukyuan',              'ryu',  3),
    -- Koreanic
    (20, 3, 'Standard Korean',        'ko',  1),
    (21, 3, 'Jeju Dialect',            NULL,  2),
    -- Vietic
    (30, 4, 'Northern Vietnamese',    'vi',  1),
    (31, 4, 'Southern Vietnamese',     NULL,  2),
    -- Other
    (40, 5, 'Sino-Xenic (General)',    NULL,  1);


-- Transcription systems are per-language: Mandarin has pinyin, wade-giles, etc.
-- The `code` column is a stable machine-readable key.
CREATE TABLE transcription_systems (
    id          INTEGER PRIMARY KEY,
    language_id INTEGER NOT NULL REFERENCES languages(id),
    name        TEXT    NOT NULL,
    code        TEXT    NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    -- When this system stores no value of its own for a reading, fall back to the
    -- value stored under `derived_from_ts_id`, then apply `transform` (a key into
    -- the app's TRANSFORMS registry, e.g. 'kana_romaji', 'lower'). This is how a
    -- romanization derived from another system (Hepburn from Kana) is expressed
    -- as system metadata rather than as menu/handler special-casing.
    derived_from_ts_id INTEGER REFERENCES transcription_systems(id),
    transform   TEXT,
    UNIQUE(language_id, code)
);

INSERT INTO transcription_systems (id, language_id, name, code, sort_order) VALUES
    -- Mandarin
    (1,  1,  'Pīnyīn',              'pinyin',          1),
    (2,  1,  'Pīnyīn (numbered)',   'pinyin_num',      2),
    (3,  1,  'Wade-Giles',          'wade_giles',      3),
    (4,  1,  'Zhùyīn (Bopomofo)',   'zhuyin',          4),
    (5,  1,  'IPA',                 'ipa',             5),
    (6,  1,  'IPA (with tones)',    'ipa_tones',       6),
    -- Cantonese
    (10, 2,  'Jyutping',            'jyutping',        1),
    (11, 2,  'Yale',                'yale',            2),
    (12, 2,  'IPA',                 'ipa',             3),
    (13, 2,  'IPA (with tones)',    'ipa_tones',       4),
    -- Middle Chinese
    (20, 7,  'Baxter-Sagart',       'baxter_sagart',   1),
    (21, 7,  'Zhengzhang',          'zhengzhang',      2),
    (22, 7,  'IPA',                 'ipa',             3),
    -- Tokyo Standard Japanese
    (30, 10, 'Hepburn',             'hepburn',         1),
    (31, 10, 'Kunrei-shiki',        'kunrei',          2),
    (32, 10, 'Kana',                'kana',            3),
    (33, 10, 'IPA',                 'ipa',             4),
    -- Standard Korean
    (40, 20, 'Revised Romanization','revised_rom',     1),
    (42, 20, 'Yale Romanization',   'yale',            2),
    (41, 20, 'Hangul',              'hangul',          3),
    (43, 20, 'IPA',                 'ipa',             4),
    (44, 20, 'Eumhun',              'eumhun',          5),
    -- Northern Vietnamese
    (50, 30, 'Quốc Ngữ',           'quoc_ngu',        1),
    (51, 30, 'IPA',                 'ipa',             2);

-- Per-system value derivations (see `derived_from_ts_id` / `transform` above).
-- Hepburn (30) falls back to Kana (32) then romanizes it; this reproduces the
-- old COALESCE(kana, hepburn) + _kana_to_romaji path exactly, because kana_romaji
-- only lowercases an already-romaji (orphan Unihan) value.
UPDATE transcription_systems SET derived_from_ts_id = 32, transform = 'kana_romaji' WHERE id = 30;
-- Kana (32) is the mirror image: most readings store kana (Kanjidic), but orphan
-- Unihan readings store only romaji under Hepburn (30). For those, derive the
-- Kana back from Hepburn via romaji_kana, so every Japanese reading offers both
-- kana and Hepburn (and, in turn, IPA). romaji_kana is dual-mode — a value that
-- already has kana is passed through — so this is a no-op on stored kana. This is
-- the reverse of derivation 30→32 above; the two never form an actual cycle
-- because exactly one of Hepburn/Kana is stored per reading (see _resolve_ts_value).
UPDATE transcription_systems SET derived_from_ts_id = 30, transform = 'romaji_kana' WHERE id = 32;
-- Korean Revised Romanization (40) is not stored; derive it from Hangul (41) via
-- hangul_revised at render time, so every Hangul reading shows a romanization
-- even where Unihan supplied no Yale (e.g. 두음법칙 forms like 女's 여).
UPDATE transcription_systems SET derived_from_ts_id = 41, transform = 'hangul_revised' WHERE id = 40;
-- Korean IPA (43) is also derived from Hangul (41), via hangul_ipa — a broad
-- Standard/Seoul transcription. Not tonal, so (unlike Mandarin/Cantonese) there
-- is a single IPA system, not a tones/no-tones pair.
UPDATE transcription_systems SET derived_from_ts_id = 41, transform = 'hangul_ipa' WHERE id = 43;
-- Japanese IPA (33) is derived from Kana (32) via kana_ipa — a broad
-- Help:IPA/Japanese transcription (same Kana the Hepburn fallback uses). Not
-- tonal, so (like Korean) a single IPA system, not a tones/no-tones pair.
UPDATE transcription_systems SET derived_from_ts_id = 32, transform = 'kana_ipa' WHERE id = 33;
-- Mandarin IPA is not stored; derive it from Pīnyīn (1) at render time, so every
-- Mandarin reading with a Pinyin shows a broad IPA. Two variants: 'IPA' (5) is
-- phonemes only; 'IPA (with tones)' (6) appends a Chao tone letter per syllable.
UPDATE transcription_systems SET derived_from_ts_id = 1, transform = 'pinyin_ipa' WHERE id = 5;
UPDATE transcription_systems SET derived_from_ts_id = 1, transform = 'pinyin_ipa_tones' WHERE id = 6;
-- Wade-Giles (3) is likewise not stored; derive it from Pīnyīn (1) via the
-- pinyin_wade_giles transform, so every Mandarin reading with a Pinyin shows a
-- Wade-Giles spelling (with a superscript Chao tone number per syllable).
UPDATE transcription_systems SET derived_from_ts_id = 1, transform = 'pinyin_wade_giles' WHERE id = 3;
-- Zhùyīn / Bopomofo (4) is likewise not stored; derive it from Pīnyīn (1) via the
-- pinyin_zhuyin transform, so every Mandarin reading with a Pinyin shows a
-- Bopomofo spelling (with the standard tone marks, neutral tone dot prepended).
UPDATE transcription_systems SET derived_from_ts_id = 1, transform = 'pinyin_zhuyin' WHERE id = 4;
-- Cantonese IPA, likewise derived from Jyutping (10): 'IPA' (12) phonemes only,
-- 'IPA (with tones)' (13) with a Chao tone letter per syllable.
UPDATE transcription_systems SET derived_from_ts_id = 10, transform = 'jyutping_ipa' WHERE id = 12;
UPDATE transcription_systems SET derived_from_ts_id = 10, transform = 'jyutping_ipa_tones' WHERE id = 13;
-- Middle Chinese Stimson / kTang (ts 60) is created by import_unihan.py, which
-- seeds its transform = 'lower' there (this schema seed does not define ts 60).


-- ============================================================
-- 1b. SOURCES
-- ============================================================
-- Central registry of reference works, dictionaries, and databases.
-- Anything that can provide or attest data gets an entry here.
CREATE TABLE sources (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,    -- full name
    short_name  TEXT,                       -- abbreviated (for UI badges, etc.)
    source_type TEXT    NOT NULL DEFAULT 'dictionary'
                CHECK (source_type IN (
                    'dictionary',           -- CC-CEDICT, ABC Chinese Dict, Daijirin…
                    'database',             -- Unihan, Kanjidic2, KanjiVG…
                    'corpus',               -- frequency lists, BLCU, BCCWJ…
                    'scholarly_work',        -- Baxter & Sagart 2014, Schuessler…
                    'standard',             -- GB 2312, Jōyō Kanji list, Unicode…
                    'other'
                )),
    url         TEXT,                       -- canonical URL
    version     TEXT,                       -- edition, date, or version tag
    notes       TEXT
);

INSERT INTO sources (id, name, short_name, source_type, url) VALUES
    (1,  'CC-CEDICT',                  'CEDICT',   'dictionary',     'https://cc-cedict.org'),
    (2,  'Unihan Database',            'Unihan',   'database',       'https://unicode.org/charts/unihan.html'),
    (3,  'Kanjidic2',                  'KD2',      'database',       'https://www.edrdg.org/wiki/index.php/KANJIDIC_Project'),
    (4,  'KanjiVG',                    'KVG',      'database',       'https://kanjivg.tagaini.net'),
    (5,  'Baxter & Sagart (2014)',     'B&S',      'scholarly_work', NULL),
    (6,  'Zhengzhang Shangfang',       'ZZ',       'scholarly_work', NULL),
    (7,  'Wiktionary',                 'Wikt',     'dictionary',     'https://en.wiktionary.org'),
    (8,  'CHISE IDS',                  'IDS',      'database',       'https://www.chise.org'),
    (9,  'GB 2312',                    'GB2312',   'standard',       NULL),
    (10, 'Jōyō Kanji (2010)',         'Jōyō',    'standard',       NULL),
    (11, 'CantoDict',                  'CDict',    'dictionary',     'https://cantodict.org'),
    (12, 'Shuowen Jiezi',             'SWJZ',     'scholarly_work', NULL),
    (13, 'CC-Canto',                   'CC-Canto', 'dictionary',     'https://cantonese.org'),
    (14, 'libhangul (hanja.txt)',      'libhangul','dictionary',     'https://github.com/libhangul/libhangul');


-- Types of historical script images.
CREATE TABLE glyph_types (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

INSERT INTO glyph_types (id, name, sort_order) VALUES
    (1, 'Oracle Bone Script',    1),
    (2, 'Bronze Inscription',    2),
    (3, 'Small Seal Script',     3),
    (4, 'Clerical Script',       4),
    (5, 'Regular Script',        5),
    (6, 'Running Script',        6),
    (7, 'Cursive Script',        7);


-- Types of variant relationships.
-- language_id is set when the variant type is specific to one language
-- (e.g., shinjitai is Japanese-only); NULL means cross-linguistic.
CREATE TABLE variant_types (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    language_id INTEGER REFERENCES languages(id),
    sort_order  INTEGER NOT NULL DEFAULT 0
);

INSERT INTO variant_types (id, name, language_id, sort_order) VALUES
    (1, 'Simplified Chinese',    1,    1),   -- Mandarin context
    (2, 'Traditional Chinese',   NULL, 2),   -- cross-linguistic
    (3, 'Shinjitai',             10,   3),   -- Japanese new form
    (4, 'Kyūjitai',              10,   4),   -- Japanese old form
    (5, 'Chữ Nôm',              30,   5),   -- Vietnamese
    (6, 'Variant Glyph',        NULL, 6);   -- catch-all for other variants


-- ============================================================
-- 2. CORE CHARACTER TABLE
-- ============================================================

CREATE TABLE characters (
    codepoint       INTEGER PRIMARY KEY,   -- Unicode codepoint value (e.g., 0x751F = 29983)
    character       TEXT    NOT NULL UNIQUE,-- the actual character: '生'
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- Modular key-value attributes for a character.
-- Keeps the characters table minimal while allowing arbitrary properties
-- (stroke count, frequency, WaniKani mnemonics, etc.) to be added from
-- any source without schema changes.
--
-- value_type hints how to interpret the stored text:
--   'integer' — parse as int
--   'real'    — parse as float
--   'text'    — plain string
--   'json'    — parse as JSON (arrays, objects)
--
-- One canonical value per (codepoint, key) — last import wins.
-- source_id records which reference work provided the value.
CREATE TABLE character_attributes (
    id          INTEGER PRIMARY KEY,
    codepoint   INTEGER NOT NULL REFERENCES characters(codepoint),
    key         TEXT    NOT NULL,
    value       TEXT    NOT NULL,
    value_type  TEXT    NOT NULL DEFAULT 'text'
                CHECK (value_type IN ('integer', 'real', 'text', 'json')),
    source_id   INTEGER REFERENCES sources(id),
    UNIQUE(codepoint, key, source_id)
);


-- ============================================================
-- 3. LINGUISTIC HIERARCHY
--    Character → Etymology → Reading → Sense → Example
-- ============================================================

-- Etymology: groups related readings + meanings for one character in one language.
--
-- Most characters have exactly 1 etymology per language. But some have
-- genuinely distinct origins that produce different readings/meanings:
--   行 in Mandarin: etym 1 → xíng (to walk)
--                   etym 2 → háng (row, profession)
--
-- When there's only one etymology, just leave etymology_text NULL and
-- set etymology_order = 1 — the layer becomes an invisible passthrough.
CREATE TABLE etymologies (
    id               INTEGER PRIMARY KEY,
    codepoint        INTEGER NOT NULL REFERENCES characters(codepoint),
    language_id      INTEGER NOT NULL REFERENCES languages(id),
    etymology_order  INTEGER NOT NULL DEFAULT 1,
    etymology_text   TEXT,                 -- origin explanation (optional)
    UNIQUE(codepoint, language_id, etymology_order)
);

-- Reading: a single distinct pronunciation.
--
-- `kind`        — 'reading' (modern, attested) or 'reconstruction' (Middle/Old Chinese).
--                  Reconstructions typically have transcriptions but no senses.
-- `category`    — language-specific grouping: 'on'/'kun' for Japanese,
--                  'literary'/'colloquial' for some Chinese dialects, etc.
-- `subcategory` — further refinement: 'kan'/'go'/'tou'/'souon' for Japanese on-readings,
--                  or NULL when not applicable.
-- `tone`        — stored here for convenience even though it's also encoded in some
--                  transcription systems. Allows tone-based queries without parsing strings.
-- `features`    — JSON blob for language-specific flags (e.g., {"okurigana": true}).
-- A reading is a distinct pronunciation, independent of which source attests it.
-- Source attribution lives in the reading_attestations junction (see section 3b),
-- so a pronunciation confirmed by several references is ONE reading row with
-- several attestations — not one duplicate row per source.
CREATE TABLE readings (
    id              INTEGER PRIMARY KEY,
    etymology_id    INTEGER NOT NULL REFERENCES etymologies(id),
    kind            TEXT    NOT NULL DEFAULT 'reading'
                    CHECK (kind IN ('reading', 'reconstruction')),
    category        TEXT,
    subcategory     TEXT,
    tone            TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,  -- display ordering within the etymology
    features        TEXT                   -- JSON
);

-- Transcription: the same pronunciation rendered in different systems.
-- One reading → many transcriptions.
--
-- Example for Mandarin reading of 生:
--   reading_id=1, system=pinyin      → "shēng"
--   reading_id=1, system=wade_giles  → "shêng¹"
--   reading_id=1, system=ipa         → "/ʂəŋ˥˥/"
CREATE TABLE reading_transcriptions (
    id                      INTEGER PRIMARY KEY,
    reading_id              INTEGER NOT NULL REFERENCES readings(id),
    transcription_system_id INTEGER NOT NULL REFERENCES transcription_systems(id),
    value                   TEXT    NOT NULL,
    UNIQUE(reading_id, transcription_system_id)
);

-- Sense: one definition/meaning attached to a reading.
CREATE TABLE senses (
    id              INTEGER PRIMARY KEY,
    reading_id      INTEGER NOT NULL REFERENCES readings(id),
    source_id       INTEGER NOT NULL REFERENCES sources(id),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    definition      TEXT    NOT NULL,
    part_of_speech  TEXT,                  -- 'noun', 'verb', 'adjective', etc.
    register        TEXT,                  -- 'formal', 'colloquial', 'literary', etc.
    notes           TEXT
);

-- Example: a usage example for a sense.
-- `source` here is free-text attribution for where the example sentence
-- itself comes from (a novel, a textbook, etc.) — distinct from the
-- data-source tracking in the junction tables below.
CREATE TABLE examples (
    id              INTEGER PRIMARY KEY,
    sense_id        INTEGER NOT NULL REFERENCES senses(id),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    example_text    TEXT    NOT NULL,       -- in source script
    transliteration TEXT,                   -- romanized form
    translation     TEXT,                   -- English translation
    source          TEXT                    -- free-text attribution (book, URL, etc.)
);


-- ============================================================
-- 3b. SOURCE ATTRIBUTION
-- ============================================================
-- Shareable facts that several references can independently attest --
-- etymologies and readings -- use junction tables (many-to-many) so
-- agreement is represented by extra attestation rows pointing at ONE
-- fact, rather than duplicate fact rows. senses.source_id stays inline
-- because a definition's wording is source-specific (CC-CEDICT and Unihan
-- phrase the same meaning differently), so it is genuinely a distinct row
-- per source rather than a shared fact.

CREATE TABLE etymology_sources (
    etymology_id INTEGER NOT NULL REFERENCES etymologies(id) ON DELETE CASCADE,
    source_id    INTEGER NOT NULL REFERENCES sources(id),
    notes        TEXT,                     -- e.g., "listed under alternate reading"
    PRIMARY KEY (etymology_id, source_id)
);

-- Which reference work(s) attest a given reading. A pronunciation confirmed
-- by N sources is one readings row with N attestation rows here.
CREATE TABLE reading_attestations (
    reading_id INTEGER NOT NULL REFERENCES readings(id) ON DELETE CASCADE,
    source_id  INTEGER NOT NULL REFERENCES sources(id),
    notes      TEXT,                       -- e.g., "listed under alternate reading"
    PRIMARY KEY (reading_id, source_id)
);


-- ============================================================
-- 4. CHARACTER VISUAL FORMS
-- ============================================================

-- Historical glyph images (oracle bone, bronze, seal script, etc.)
-- A character can have multiple images of the same type (different sources).
CREATE TABLE character_glyphs (
    id              INTEGER PRIMARY KEY,
    codepoint       INTEGER NOT NULL REFERENCES characters(codepoint),
    glyph_type_id   INTEGER NOT NULL REFERENCES glyph_types(id),
    image           BLOB,                  -- PNG data (for inline storage)
    image_path      TEXT,                  -- or filesystem path (for large collections)
    source_id       INTEGER REFERENCES sources(id),  -- which database/collection this image is from
    attribution     TEXT,                  -- free-text credit line for display
    sort_order      INTEGER NOT NULL DEFAULT 0,
    CHECK (image IS NOT NULL OR image_path IS NOT NULL)
);

-- Variant forms: links a character to its variants.
-- Prefers a reference to another character in the DB (variant_codepoint);
-- falls back to an image when no Unicode representation exists.
CREATE TABLE character_variants (
    id                  INTEGER PRIMARY KEY,
    codepoint           INTEGER NOT NULL REFERENCES characters(codepoint),
    variant_type_id     INTEGER NOT NULL REFERENCES variant_types(id),
    variant_codepoint   INTEGER REFERENCES characters(codepoint),
    variant_image       BLOB,
    variant_image_path  TEXT,
    source_id           INTEGER REFERENCES sources(id),  -- which standard/dictionary defines this relationship
    notes               TEXT,
    CHECK (variant_codepoint IS NOT NULL
        OR variant_image IS NOT NULL
        OR variant_image_path IS NOT NULL)
);


-- ============================================================
-- 5. RADICAL / COMPONENT DECOMPOSITION
-- ============================================================

-- Bidirectional decomposition.
-- Row: "codepoint contains component_codepoint in role X at position Y"
--
-- To find components OF 休: WHERE codepoint = 0x4F11
-- To find characters CONTAINING 人: WHERE component_codepoint = 0x4EBA
CREATE TABLE character_components (
    id                  INTEGER PRIMARY KEY,
    codepoint           INTEGER NOT NULL REFERENCES characters(codepoint),
    component_codepoint INTEGER NOT NULL REFERENCES characters(codepoint),
    role                TEXT    NOT NULL DEFAULT 'component'
                        CHECK (role IN ('radical', 'phonetic', 'semantic', 'component')),
    position            TEXT,              -- 'left', 'right', 'top', 'bottom', 'inner', 'enclosure', etc.
    source_id           INTEGER REFERENCES sources(id),  -- decomposition authority (CHISE IDS, KanjiVG, etc.)
    sort_order          INTEGER NOT NULL DEFAULT 0,
    UNIQUE(codepoint, component_codepoint, role)
);


-- ============================================================
-- 6. INDEXES
-- ============================================================
-- (Character sets are stored as v2 JSON documents in charactersets/, not in
--  the DB — see docs/flexible_character_sets_plan.md.)

-- Character attributes
CREATE INDEX idx_char_attrs_codepoint ON character_attributes(codepoint);
CREATE INDEX idx_char_attrs_key       ON character_attributes(key);

-- Linguistic hierarchy traversal
CREATE INDEX idx_etymologies_char         ON etymologies(codepoint);
CREATE INDEX idx_etymologies_lang         ON etymologies(language_id);
CREATE INDEX idx_etymologies_char_lang    ON etymologies(codepoint, language_id);
CREATE INDEX idx_readings_etymology       ON readings(etymology_id);
CREATE INDEX idx_readings_category        ON readings(category);
CREATE INDEX idx_senses_reading           ON senses(reading_id);
CREATE INDEX idx_examples_sense           ON examples(sense_id);

-- Transcription lookups (search by reading value across all characters)
CREATE INDEX idx_rt_reading               ON reading_transcriptions(reading_id);
CREATE INDEX idx_rt_system                ON reading_transcriptions(transcription_system_id);
CREATE INDEX idx_rt_value                 ON reading_transcriptions(value COLLATE NOCASE);

-- Visual forms
CREATE INDEX idx_glyphs_char              ON character_glyphs(codepoint);
CREATE INDEX idx_variants_char            ON character_variants(codepoint);
CREATE INDEX idx_variants_target          ON character_variants(variant_codepoint);

-- Component / radical lookups (both directions)
CREATE INDEX idx_components_char          ON character_components(codepoint);
CREATE INDEX idx_components_component     ON character_components(component_codepoint);

-- Source attribution (reverse lookups: "everything from source X")
CREATE INDEX idx_etym_sources_source      ON etymology_sources(source_id);
CREATE INDEX idx_read_attest_source       ON reading_attestations(source_id);
CREATE INDEX idx_senses_source            ON senses(source_id);
CREATE INDEX idx_glyphs_source            ON character_glyphs(source_id);
CREATE INDEX idx_variants_source          ON character_variants(source_id);
CREATE INDEX idx_components_source        ON character_components(source_id);


-- ============================================================
-- 7. CONVENIENCE VIEWS
-- ============================================================

-- Flat view: character → family → language → reading → transcription → definitions
-- Useful for debugging and bulk exports.
CREATE VIEW v_character_readings AS
SELECT
    c.codepoint,
    c.character,
    lf.name   AS family,
    l.name    AS language,
    e.etymology_order,
    e.etymology_text,
    r.id      AS reading_id,
    r.kind,
    r.category,
    r.subcategory,
    r.tone,
    ts.name   AS transcription_system,
    rt.value  AS transcription_value
FROM characters        c
JOIN etymologies       e  ON e.codepoint  = c.codepoint
JOIN languages         l  ON l.id         = e.language_id
JOIN language_families lf ON lf.id        = l.family_id
JOIN readings          r  ON r.etymology_id = e.id
LEFT JOIN reading_transcriptions rt ON rt.reading_id = r.id
LEFT JOIN transcription_systems  ts ON ts.id = rt.transcription_system_id
ORDER BY c.codepoint, lf.sort_order, l.sort_order, e.etymology_order, r.sort_order, ts.sort_order;

-- Definitions view: everything down to the sense level
CREATE VIEW v_character_senses AS
SELECT
    c.codepoint,
    c.character,
    lf.name   AS family,
    l.name    AS language,
    e.etymology_order,
    r.id      AS reading_id,
    r.category,
    s.sort_order AS sense_order,
    s.definition,
    s.part_of_speech
FROM characters        c
JOIN etymologies       e  ON e.codepoint    = c.codepoint
JOIN languages         l  ON l.id           = e.language_id
JOIN language_families lf ON lf.id          = l.family_id
JOIN readings          r  ON r.etymology_id = e.id
JOIN senses            s  ON s.reading_id   = r.id
ORDER BY c.codepoint, lf.sort_order, l.sort_order, e.etymology_order, r.sort_order, s.sort_order;

-- Source-annotated senses: shows which sources back each definition.
-- Useful for auditing data provenance and resolving conflicts.
CREATE VIEW v_sourced_senses AS
SELECT
    c.codepoint,
    c.character,
    l.name        AS language,
    r.id          AS reading_id,
    r.category,
    s.id          AS sense_id,
    s.definition,
    src.short_name AS source
FROM characters        c
JOIN etymologies       e   ON e.codepoint    = c.codepoint
JOIN languages         l   ON l.id           = e.language_id
JOIN readings          r   ON r.etymology_id = e.id
JOIN senses            s   ON s.reading_id   = r.id
JOIN sources           src ON src.id         = s.source_id
ORDER BY c.codepoint, l.sort_order, e.etymology_order, r.sort_order, s.sort_order;

-- Component breakdown view
CREATE VIEW v_components AS
SELECT
    parent.character  AS character,
    parent.codepoint  AS codepoint,
    comp.character    AS component,
    comp.codepoint    AS component_codepoint,
    cc.role,
    cc.position
FROM character_components cc
JOIN characters parent ON parent.codepoint = cc.codepoint
JOIN characters comp   ON comp.codepoint   = cc.component_codepoint
ORDER BY parent.codepoint, cc.sort_order;
