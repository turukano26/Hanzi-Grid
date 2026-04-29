-- ============================================================
-- Worked example: 生 (U+751F, codepoint 29983)
-- Shows how data flows through every level of the schema,
-- including source attribution.
-- ============================================================

-- The character itself
INSERT INTO characters (codepoint, character, stroke_count, radical_number)
VALUES (29983, '生', 5, 100);  -- radical 100 = 生 (it is its own radical)


-- ============================================================
-- SINITIC
-- ============================================================

-- Mandarin: single etymology, one reading, multiple transcription systems
INSERT INTO etymologies (id, codepoint, language_id, etymology_order)
VALUES (1, 29983, 1, 1);  -- language 1 = Mandarin

INSERT INTO readings (id, etymology_id, kind, tone, sort_order)
VALUES (1, 1, 'reading', '1', 1);

-- Source attribution: this reading is attested in both CC-CEDICT and Unihan
INSERT INTO reading_sources (reading_id, source_id) VALUES
    (1, 1),   -- CC-CEDICT
    (1, 2);   -- Unihan

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (1, 1, 'shēng'),        -- pinyin
    (1, 2, 'sheng1'),       -- pinyin numbered
    (1, 3, 'shêng¹'),       -- wade-giles
    (1, 4, 'ㄕㄥ'),          -- zhuyin
    (1, 5, '/ʂəŋ˥˥/');      -- IPA

-- Senses with source tracking
INSERT INTO senses (id, reading_id, sort_order, definition, part_of_speech) VALUES
    (1, 1, 1, 'to be born; to give birth',    'verb'),
    (2, 1, 2, 'life; living',                 'noun'),
    (3, 1, 3, 'raw; uncooked',               'adjective'),
    (4, 1, 4, 'student; pupil',              'noun'),
    (5, 1, 5, 'unfamiliar; strange',         'adjective');

-- Senses 1-4 come from CC-CEDICT; sense 5 also backed by Wiktionary
INSERT INTO sense_sources (sense_id, source_id) VALUES
    (1, 1),   -- CEDICT
    (2, 1),
    (3, 1),
    (4, 1),
    (5, 1),   -- CEDICT
    (5, 7);   -- Wiktionary (additional confirmation)

INSERT INTO examples (sense_id, sort_order, example_text, transliteration, translation) VALUES
    (1, 1, '他生于北京。', 'Tā shēng yú Běijīng.', 'He was born in Beijing.'),
    (3, 1, '生鱼片',       'shēng yúpiàn',          'sashimi (raw fish slices)');


-- Cantonese: same character, separate language entry
INSERT INTO etymologies (id, codepoint, language_id, etymology_order)
VALUES (2, 29983, 2, 1);  -- language 2 = Cantonese

INSERT INTO readings (id, etymology_id, kind, tone, sort_order)
VALUES (2, 2, 'reading', '1', 1);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (2, 2),   -- Unihan (kCantonese field)
    (2, 11);  -- CantoDict

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (2, 10, 'saang1'),      -- jyutping
    (2, 11, 'sāang'),       -- yale
    (2, 12, '/saːŋ˥˥/');    -- IPA

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (6, 2, 1, 'life; birth'),
    (7, 2, 2, 'raw; uncooked');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (6, 11),  -- CantoDict
    (7, 11);


-- Middle Chinese: reconstruction, no senses — sources are especially
-- important here since reconstructions are inherently scholarly claims.
INSERT INTO etymologies (id, codepoint, language_id, etymology_order)
VALUES (3, 29983, 7, 1);  -- language 7 = Middle Chinese

INSERT INTO etymology_sources (etymology_id, source_id, notes) VALUES
    (3, 5, 'Baxter & Sagart (2014), Old Chinese: A New Reconstruction'),
    (3, 6, 'Zhengzhang Shangfang reconstruction system');

INSERT INTO readings (id, etymology_id, kind, sort_order)
VALUES (3, 3, 'reconstruction', 1);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (3, 5),   -- Baxter & Sagart
    (3, 6);   -- Zhengzhang

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (3, 20, '*sreng'),       -- baxter-sagart
    (3, 21, '/*ʃˤeŋ/');     -- zhengzhang


-- ============================================================
-- JAPONIC
-- ============================================================

-- Tokyo Standard: single etymology, multiple readings (on + kun)
INSERT INTO etymologies (id, codepoint, language_id, etymology_order)
VALUES (4, 29983, 10, 1);  -- language 10 = Tokyo Standard

-- On-reading: sei (kan-on)
INSERT INTO readings (id, etymology_id, kind, category, subcategory, sort_order)
VALUES (4, 4, 'reading', 'on', 'kan', 1);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (4, 3);   -- Kanjidic2

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (4, 30, 'sei'),          -- hepburn
    (4, 32, 'せい');          -- kana

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (8, 4, 1, 'life; living'),
    (9, 4, 2, 'birth; being born');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (8, 3),   -- Kanjidic2
    (9, 3);

-- On-reading: shō (go-on)
INSERT INTO readings (id, etymology_id, kind, category, subcategory, sort_order)
VALUES (5, 4, 'reading', 'on', 'go', 2);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (5, 3);   -- Kanjidic2

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (5, 30, 'shō'),         -- hepburn
    (5, 32, 'しょう');        -- kana

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (10, 5, 1, 'nature; disposition');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (10, 3);

-- Kun-reading: ikiru (with okurigana)
INSERT INTO readings (id, etymology_id, kind, category, sort_order, features)
VALUES (6, 4, 'reading', 'kun', 3, '{"okurigana": true}');

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (6, 3);

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (6, 30, 'ikiru'),       -- hepburn
    (6, 32, 'いきる');        -- kana

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (11, 6, 1, 'to live; to be alive');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (11, 3);

-- Kun-reading: umareru
INSERT INTO readings (id, etymology_id, kind, category, sort_order, features)
VALUES (7, 4, 'reading', 'kun', 4, '{"okurigana": true}');

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (7, 3);

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (7, 30, 'umareru'),     -- hepburn
    (7, 32, 'うまれる');      -- kana

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (12, 7, 1, 'to be born');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (12, 3);

-- Kun-reading: nama
INSERT INTO readings (id, etymology_id, kind, category, sort_order)
VALUES (8, 4, 'reading', 'kun', 5);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (8, 3);

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (8, 30, 'nama'),        -- hepburn
    (8, 32, 'なま');          -- kana

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (13, 8, 1, 'raw; uncooked; draft (beer)');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (13, 3),  -- Kanjidic2
    (13, 7);  -- Wiktionary


-- ============================================================
-- KOREANIC
-- ============================================================

INSERT INTO etymologies (id, codepoint, language_id, etymology_order)
VALUES (5, 29983, 20, 1);  -- language 20 = Standard Korean

INSERT INTO readings (id, etymology_id, kind, sort_order)
VALUES (9, 5, 'reading', 1);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (9, 2);   -- Unihan

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (9, 40, 'saeng'),       -- revised romanization
    (9, 41, '생');            -- hangul

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (14, 9, 1, 'life; living'),
    (15, 9, 2, 'raw; fresh');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (14, 7),  -- Wiktionary
    (15, 7);


-- ============================================================
-- VIETIC
-- ============================================================

INSERT INTO etymologies (id, codepoint, language_id, etymology_order)
VALUES (6, 29983, 30, 1);  -- language 30 = Northern Vietnamese

INSERT INTO readings (id, etymology_id, kind, sort_order)
VALUES (10, 6, 'reading', 1);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (10, 2),  -- Unihan
    (10, 7);  -- Wiktionary

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (10, 50, 'sinh'),       -- quốc ngữ
    (10, 51, '/siŋ˧˧/');    -- IPA

INSERT INTO senses (id, reading_id, sort_order, definition) VALUES
    (16, 10, 1, 'to be born; to give birth'),
    (17, 10, 2, 'student');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (16, 7),  -- Wiktionary
    (17, 7);


-- ============================================================
-- GLYPHS (historical script forms) — with source FK
-- ============================================================

INSERT INTO character_glyphs (codepoint, glyph_type_id, image_path, source_id, attribution, sort_order) VALUES
    (29983, 1, 'glyphs/751F_oracle.png',   NULL, 'Academia Sinica Oracle Bone DB',   1),
    (29983, 2, 'glyphs/751F_bronze.png',   NULL, 'CHANT Bronze Inscriptions',        2),
    (29983, 3, 'glyphs/751F_seal.png',     12,   'Shuowen Jiezi, radical 生 section', 3),  -- source 12 = SWJZ
    (29983, 4, 'glyphs/751F_clerical.png', NULL, 'Han Dynasty bamboo slips',          4);


-- ============================================================
-- COMPONENTS (radical decomposition) — with source FK
-- ============================================================

-- 生 is itself radical 100 and is not typically decomposed further,
-- but it appears as a component in many other characters.

-- 性 (xìng) = 忄 + 生 (生 is the phonetic component)
INSERT INTO characters (codepoint, character, stroke_count, radical_number) VALUES (24615, '性', 8, 61);
INSERT INTO character_components (codepoint, component_codepoint, role, position, source_id)
VALUES (24615, 29983, 'phonetic', 'right', 8);  -- source 8 = CHISE IDS

-- 星 (xīng) = 日 + 生 (生 is the phonetic component)
INSERT INTO characters (codepoint, character, stroke_count, radical_number) VALUES (26143, '星', 9, 72);
INSERT INTO character_components (codepoint, component_codepoint, role, position, source_id)
VALUES (26143, 29983, 'phonetic', 'bottom', 8);  -- source 8 = CHISE IDS

-- Query both directions:
--   Components OF 性:  SELECT * FROM character_components WHERE codepoint = 24615;
--   Characters CONTAINING 生: SELECT * FROM character_components WHERE component_codepoint = 29983;


-- ============================================================
-- MULTI-ETYMOLOGY EXAMPLE: 行 (U+884C, codepoint 34892)
-- Shows how multiple etymologies split readings within one language,
-- and how different sources may back different etymological analyses.
-- ============================================================

INSERT INTO characters (codepoint, character, stroke_count, radical_number)
VALUES (34892, '行', 6, 144);

-- Etymology 1: "to walk, to travel"
INSERT INTO etymologies (id, codepoint, language_id, etymology_order, etymology_text)
VALUES (10, 34892, 1, 1, 'From Proto-Sino-Tibetan; original meaning "to walk, to go"');

INSERT INTO etymology_sources (etymology_id, source_id, notes) VALUES
    (10, 5, 'Baxter & Sagart reconstruct *gˤraŋ'),
    (10, 7, 'Wiktionary Chinese etymology section');

INSERT INTO readings (id, etymology_id, kind, tone, sort_order)
VALUES (20, 10, 'reading', '2', 1);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (20, 1),   -- CC-CEDICT
    (20, 2);   -- Unihan

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (20, 1, 'xíng'),
    (20, 5, '/ɕiŋ˧˥/');

INSERT INTO senses (id, reading_id, sort_order, definition, part_of_speech) VALUES
    (20, 20, 1, 'to walk; to go; to travel',   'verb'),
    (21, 20, 2, 'to carry out; to execute',     'verb'),
    (22, 20, 3, 'behavior; conduct',            'noun'),
    (23, 20, 4, 'OK; all right; capable',       'adjective');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (20, 1), (21, 1), (22, 1), (23, 1);  -- all from CC-CEDICT

-- Etymology 2: "row, profession" (same character, different origin)
INSERT INTO etymologies (id, codepoint, language_id, etymology_order, etymology_text)
VALUES (11, 34892, 1, 2, 'Extended or separate derivation; "row, line" → "trade, profession"');

INSERT INTO etymology_sources (etymology_id, source_id) VALUES
    (11, 7);  -- Wiktionary

INSERT INTO readings (id, etymology_id, kind, tone, sort_order)
VALUES (21, 11, 'reading', '2', 1);

INSERT INTO reading_sources (reading_id, source_id) VALUES
    (21, 1),   -- CC-CEDICT
    (21, 2);   -- Unihan

INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) VALUES
    (21, 1, 'háng'),
    (21, 5, '/xɑŋ˧˥/');

INSERT INTO senses (id, reading_id, sort_order, definition, part_of_speech) VALUES
    (24, 21, 1, 'row; line',                    'noun'),
    (25, 21, 2, 'trade; profession; business',  'noun'),
    (26, 21, 3, 'firm; commercial house',       'noun');

INSERT INTO sense_sources (sense_id, source_id) VALUES
    (24, 1), (25, 1), (26, 1);  -- all from CC-CEDICT


-- ============================================================
-- QUERY EXAMPLES
-- ============================================================

-- Q: Get all readings for 生 across all languages, grouped by family:
--    SELECT * FROM v_character_readings WHERE codepoint = 29983;

-- Q: Search by pinyin 'shēng' — find all characters with that reading:
--    SELECT DISTINCT c.character, c.codepoint
--    FROM reading_transcriptions rt
--    JOIN transcription_systems ts ON ts.id = rt.transcription_system_id
--    JOIN readings r              ON r.id  = rt.reading_id
--    JOIN etymologies e           ON e.id  = r.etymology_id
--    JOIN characters c            ON c.codepoint = e.codepoint
--    WHERE ts.code = 'pinyin' AND rt.value = 'shēng'
--    ORDER BY c.codepoint;

-- Q: Find all characters that contain 生 as a component:
--    SELECT parent.character, cc.role, cc.position
--    FROM character_components cc
--    JOIN characters parent ON parent.codepoint = cc.codepoint
--    WHERE cc.component_codepoint = 29983;

-- Q: Get the full info sheet for 生 in Mandarin (replaces create_character_info_sheet):
--    SELECT r.id, rt.value AS pinyin, s.definition
--    FROM etymologies e
--    JOIN readings r  ON r.etymology_id = e.id
--    JOIN reading_transcriptions rt ON rt.reading_id = r.id
--    JOIN transcription_systems ts  ON ts.id = rt.transcription_system_id
--    LEFT JOIN senses s ON s.reading_id = r.id
--    WHERE e.codepoint = 29983
--      AND e.language_id = 1
--      AND ts.code = 'pinyin'
--    ORDER BY e.etymology_order, r.sort_order, s.sort_order;

-- Q: Show all sources for a specific reading:
--    SELECT src.name, src.short_name, src.source_type, rs.notes
--    FROM reading_sources rs
--    JOIN sources src ON src.id = rs.source_id
--    WHERE rs.reading_id = 1;

-- Q: Find all definitions that come from CC-CEDICT:
--    SELECT c.character, l.name AS language, s.definition
--    FROM sense_sources ss
--    JOIN senses s            ON s.id          = ss.sense_id
--    JOIN readings r          ON r.id          = s.reading_id
--    JOIN etymologies e       ON e.id          = r.etymology_id
--    JOIN characters c        ON c.codepoint   = e.codepoint
--    JOIN languages l         ON l.id          = e.language_id
--    WHERE ss.source_id = 1   -- CC-CEDICT
--    ORDER BY c.codepoint;

-- Q: Show sourced definitions (using the convenience view):
--    SELECT * FROM v_sourced_senses WHERE codepoint = 29983;

-- Q: Find readings that are ONLY attested in a single source (potential data quality flag):
--    SELECT r.id, COUNT(rs.source_id) AS source_count
--    FROM readings r
--    LEFT JOIN reading_sources rs ON rs.reading_id = r.id
--    GROUP BY r.id
--    HAVING source_count <= 1;
