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
    UNIQUE(language_id, code)
);

INSERT INTO transcription_systems (id, language_id, name, code, sort_order) VALUES
    -- Mandarin
    (1,  1,  'Pīnyīn',              'pinyin',          1),
    (2,  1,  'Pīnyīn (numbered)',   'pinyin_num',      2),
    (3,  1,  'Wade-Giles',          'wade_giles',      3),
    (4,  1,  'Zhùyīn (Bopomofo)',   'zhuyin',          4),
    (5,  1,  'IPA',                 'ipa',             5),
    -- Cantonese
    (10, 2,  'Jyutping',            'jyutping',        1),
    (11, 2,  'Yale',                'yale',            2),
    (12, 2,  'IPA',                 'ipa',             3),
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
    (41, 20, 'Hangul',              'hangul',          2),
    (42, 20, 'Yale Romanization',   'yale',            3),
    (43, 20, 'IPA',                 'ipa',             4),
    -- Northern Vietnamese
    (50, 30, 'Quốc Ngữ',           'quoc_ngu',        1),
    (51, 30, 'IPA',                 'ipa',             2);


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
    (12, 'Shuowen Jiezi',             'SWJZ',     'scholarly_work', NULL);


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
    stroke_count    INTEGER,
    radical_number  INTEGER,               -- Kangxi radical number (1–214)
    frequency_rank  INTEGER,               -- corpus frequency rank (lower = more common)
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
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
CREATE TABLE readings (
    id              INTEGER PRIMARY KEY,
    etymology_id    INTEGER NOT NULL REFERENCES etymologies(id),
    source_id       INTEGER NOT NULL REFERENCES sources(id),
    kind            TEXT    NOT NULL DEFAULT 'reading'
                    CHECK (kind IN ('reading', 'reconstruction')),
    category        TEXT,
    subcategory     TEXT,
    tone            TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,  -- ordering within this source's readings
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
-- readings.source_id and senses.source_id record which reference work
-- each row came from directly. When two sources attest the same
-- pronunciation, they each get their own reading row; display code
-- deduplicates by converted value and picks the preferred source.
--
-- etymology_sources is a junction table (many-to-many) because a single
-- etymology grouping can be confirmed by multiple references without
-- warranting duplicate rows.

CREATE TABLE etymology_sources (
    etymology_id INTEGER NOT NULL REFERENCES etymologies(id) ON DELETE CASCADE,
    source_id    INTEGER NOT NULL REFERENCES sources(id),
    notes        TEXT,                     -- e.g., "listed under alternate reading"
    PRIMARY KEY (etymology_id, source_id)
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
-- 6. CHARACTER SETS (replaces charactersets/*.json)
-- ============================================================

CREATE TABLE character_set_groups (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE character_set_levels (
    id          INTEGER PRIMARY KEY,
    group_id    INTEGER NOT NULL REFERENCES character_set_groups(id),
    name        TEXT    NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE character_set_members (
    level_id    INTEGER NOT NULL REFERENCES character_set_levels(id),
    codepoint   INTEGER NOT NULL REFERENCES characters(codepoint),
    sort_order  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (level_id, codepoint)
);


-- ============================================================
-- 7. INDEXES
-- ============================================================

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
CREATE INDEX idx_readings_source          ON readings(source_id);
CREATE INDEX idx_senses_source            ON senses(source_id);
CREATE INDEX idx_glyphs_source            ON character_glyphs(source_id);
CREATE INDEX idx_variants_source          ON character_variants(source_id);
CREATE INDEX idx_components_source        ON character_components(source_id);

-- Character sets
CREATE INDEX idx_charset_members_char     ON character_set_members(codepoint);
CREATE INDEX idx_charset_levels_group     ON character_set_levels(group_id);


-- ============================================================
-- 8. CONVENIENCE VIEWS
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
