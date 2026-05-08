#!/usr/bin/env python3
"""
Import Unihan database into the omni-hanzi SQLite database.

Downloads the latest Unihan.zip from unicode.org, parses the relevant
fields, and populates characters, etymologies, readings,
reading_transcriptions, senses, and character_variants.

Run scripts/create_db.py first to initialise the database.

Usage:
    python scripts/create_db.py
    python scripts/import_unihan.py
"""

import argparse
import os
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "omnihanzi.db"
CACHE_DIR = ROOT / "data" / "unihan"
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"

# ---------------------------------------------------------------------------
# IDs from schema.sql seed data
# ---------------------------------------------------------------------------

# language IDs
LANG_MANDARIN = 1
LANG_CANTONESE = 2
LANG_MIDDLE_CHINESE = 7
LANG_TOKYO = 10
LANG_KOREAN = 20
LANG_VIETNAMESE = 30

# transcription-system IDs
TS_PINYIN = 1
TS_PINYIN_NUM = 2
TS_JYUTPING = 10
TS_HEPBURN = 30
TS_KANA = 32
TS_REVISED_ROM = 40
TS_HANGUL = 41
TS_YALE_KO = 42
TS_QUOC_NGU = 50

# We insert one extra transcription system for kTang
TS_STIMSON = 60

# source IDs
SOURCE_UNIHAN = 2

# Unihan field names we care about
FIELDS_OF_INTEREST = {
    # readings
    "kMandarin", "kHanyuPinyin", "kCantonese",
    "kJapaneseOn", "kJapaneseKun",
    "kKorean", "kHangul",
    "kVietnamese", "kTang",
    # definitions
    "kDefinition",
    # character metadata
    "kTotalStrokes", "kRSUnicode", "kGradeLevel",
    # variants
    "kSimplifiedVariant", "kTraditionalVariant",
}

# ---------------------------------------------------------------------------
# Tone helpers
# ---------------------------------------------------------------------------

_PINYIN_TONE: dict[str, str] = {}
for _chars, _tone in [
    ("āĀēĒīĪōŌūŪǖǕ", "1"),
    ("áÁéÉíÍóÓúÚǘǗ", "2"),
    ("ǎǍěĚǐǏǒǑǔǓǚǙ", "3"),
    ("àÀèÈìÌòÒùÙǜǛ", "4"),
]:
    for _c in _chars:
        _PINYIN_TONE[_c] = _tone


def tone_from_pinyin(pinyin: str) -> str:
    """Return '1'-'4' from an accented pinyin string, or '5' (neutral)."""
    for ch in pinyin:
        if ch in _PINYIN_TONE:
            return _PINYIN_TONE[ch]
    return "5"


def tone_from_jyutping(jyutping: str) -> str | None:
    """Return trailing digit from jyutping, or None."""
    if jyutping and jyutping[-1].isdigit():
        return jyutping[-1]
    return None


# ---------------------------------------------------------------------------
# Unihan field parsers
# ---------------------------------------------------------------------------

def parse_mandarin_readings(fields: dict) -> list[str]:
    """Pinyin readings from kHanyuPinyin (preferred) or kMandarin (fallback).

    kHanyuPinyin format: "loc:py,py loc:py"
    kMandarin format:    "py py" (space-separated, max 2)
    """
    seen: set[str] = set()
    readings: list[str] = []

    if "kHanyuPinyin" in fields:
        for entry in fields["kHanyuPinyin"].split():
            if ":" in entry:
                _, pinyins = entry.split(":", 1)
                for py in pinyins.split(","):
                    py = py.strip()
                    if py and py not in seen:
                        seen.add(py)
                        readings.append(py)

    if "kMandarin" in fields:
        for py in fields["kMandarin"].split():
            py = py.strip()
            if py and py not in seen:
                seen.add(py)
                readings.append(py)

    return readings


def parse_cantonese_readings(fields: dict) -> list[str]:
    """Jyutping syllables from kCantonese (space-separated)."""
    raw = fields.get("kCantonese", "")
    return [s.strip() for s in raw.split() if s.strip()]


def parse_japanese_on(fields: dict) -> list[str]:
    """Katakana on-readings from kJapaneseOn (space-separated, UPPERCASE romaji in old Unihan, katakana in current)."""
    raw = fields.get("kJapaneseOn", "")
    return [s.strip() for s in raw.split() if s.strip()]


def parse_japanese_kun(fields: dict) -> list[str]:
    """Hiragana/romaji kun-readings from kJapaneseKun (space-separated, dots mark okurigana)."""
    raw = fields.get("kJapaneseKun", "")
    return [s.strip() for s in raw.split() if s.strip()]


def parse_korean_yale(fields: dict) -> list[str]:
    """Yale romanisation from kKorean (space-separated, often UPPERCASE)."""
    raw = fields.get("kKorean", "")
    return [s.strip().lower() for s in raw.split() if s.strip()]


def parse_korean_hangul(fields: dict) -> list[str]:
    """Hangul from kHangul. Format: 'hangul:type hangul:type'."""
    raw = fields.get("kHangul", "")
    results: list[str] = []
    for token in raw.split():
        hangul = token.split(":")[0].strip()
        if hangul:
            results.append(hangul)
    return results


def parse_vietnamese(fields: dict) -> list[str]:
    """Quoc ngu from kVietnamese (space-separated)."""
    raw = fields.get("kVietnamese", "")
    return [s.strip() for s in raw.split() if s.strip()]


def parse_tang(fields: dict) -> list[str]:
    """Tang dynasty reconstructions from kTang (space-separated, * = uncertain)."""
    raw = fields.get("kTang", "")
    return [s.strip() for s in raw.split() if s.strip()]


def parse_definitions(fields: dict) -> list[str]:
    """English glosses from kDefinition (semicolon-separated)."""
    raw = fields.get("kDefinition", "")
    return [d.strip() for d in raw.split(";") if d.strip()]


def parse_radical_stroke(fields: dict) -> tuple[int | None, int | None]:
    """Parse kRSUnicode → (radical_number, additional_strokes). Takes first value."""
    raw = fields.get("kRSUnicode", "")
    if not raw:
        return None, None
    first = raw.split()[0]
    try:
        # format: "radical.additional" — radical may have a trailing ' for simplified radical
        radical_str, strokes_str = first.split(".")
        radical = int(radical_str.rstrip("'"))
        extra = int(strokes_str)
        return radical, extra
    except (ValueError, IndexError):
        return None, None


def parse_total_strokes(fields: dict) -> int | None:
    """Parse kTotalStrokes → int. Takes first value (CN standard)."""
    raw = fields.get("kTotalStrokes", "")
    if not raw:
        return None
    try:
        return int(raw.split()[0])
    except ValueError:
        return None


def parse_grade_level(fields: dict) -> int | None:
    """Parse kGradeLevel → int (PRC school grade: 1-6, or higher)."""
    raw = fields.get("kGradeLevel", "")
    try:
        return int(raw)
    except ValueError:
        return None


def parse_variant_codepoints(value: str) -> list[int]:
    """Parse space-separated U+XXXX references → list of int codepoints."""
    results: list[int] = []
    for token in value.split():
        token = token.strip()
        if token.startswith("U+"):
            try:
                results.append(int(token[2:], 16))
            except ValueError:
                pass
    return results


# ---------------------------------------------------------------------------
# Download / parse
# ---------------------------------------------------------------------------

def download_unihan() -> None:
    """Download and extract Unihan.zip to CACHE_DIR."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE_DIR / "Unihan.zip"

    if not zip_path.exists():
        print(f"Downloading {UNIHAN_URL} ...")
        urllib.request.urlretrieve(UNIHAN_URL, zip_path)
    else:
        print(f"Using cached {zip_path}")

    print("Extracting ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(CACHE_DIR)
    print(f"Extracted to {CACHE_DIR}")


def parse_unihan_files() -> dict[int, dict[str, str]]:
    """Parse all Unihan_*.txt files → {codepoint: {field: value}}."""
    data: dict[int, dict[str, str]] = {}
    count = 0

    for txt_path in sorted(CACHE_DIR.glob("Unihan_*.txt")):
        with open(txt_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t", 2)
                if len(parts) != 3:
                    continue
                cp_str, field, value = parts
                if field not in FIELDS_OF_INTEREST:
                    continue
                cp = int(cp_str[2:], 16)
                data.setdefault(cp, {})[field] = value
                count += 1

    print(f"Parsed {count:,} field values for {len(data):,} codepoints")
    return data


# ---------------------------------------------------------------------------
# Import phases
# ---------------------------------------------------------------------------

def import_characters(cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]]) -> None:
    """Phase 1: populate the characters table."""
    rows = []
    for cp, fields in unihan.items():
        char = chr(cp)
        stroke_count = parse_total_strokes(fields)
        radical, _ = parse_radical_stroke(fields)
        grade = parse_grade_level(fields)
        rows.append((cp, char, stroke_count, radical, grade))

    cur.executemany(
        "INSERT OR IGNORE INTO characters (codepoint, character, stroke_count, radical_number, frequency_rank) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    print(f"  characters: {cur.rowcount:,} inserted")


def _insert_readings_for_language(
    cur: sqlite3.Cursor,
    unihan: dict[int, dict[str, str]],
    *,
    language_id: int,
    parser,
    transcription_system_id: int,
    kind: str = "reading",
    category: str | None = None,
    tone_fn=None,
    primary_readings: dict[int, int],
) -> int:
    """Shared helper: create etymology → reading(s) → transcription for one language.

    Returns the number of readings inserted.
    """
    count = 0
    for cp, fields in unihan.items():
        values = parser(fields)
        if not values:
            continue

        cur.execute(
            "INSERT INTO etymologies (codepoint, language_id, etymology_order) VALUES (?, ?, 1)",
            (cp, language_id),
        )
        etym_id = cur.lastrowid

        for i, val in enumerate(values):
            tone = tone_fn(val) if tone_fn else None

            cur.execute(
                "INSERT INTO readings (etymology_id, kind, category, tone, sort_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (etym_id, kind, category, tone, i + 1),
            )
            reading_id = cur.lastrowid

            cur.execute(
                "INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) "
                "VALUES (?, ?, ?)",
                (reading_id, transcription_system_id, val),
            )

            cur.execute(
                "INSERT INTO reading_sources (reading_id, source_id) VALUES (?, ?)",
                (reading_id, SOURCE_UNIHAN),
            )

            # Track first reading per character for definition attachment
            if cp not in primary_readings:
                primary_readings[cp] = reading_id

            count += 1

    return count


def import_mandarin(
    cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]], primary_readings: dict[int, int]
) -> None:
    """Phase 2: Mandarin etymologies + readings + transcriptions."""
    count = _insert_readings_for_language(
        cur, unihan,
        language_id=LANG_MANDARIN,
        parser=parse_mandarin_readings,
        transcription_system_id=TS_PINYIN,
        tone_fn=tone_from_pinyin,
        primary_readings=primary_readings,
    )
    print(f"  Mandarin: {count:,} readings")


def import_cantonese(
    cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]], primary_readings: dict[int, int]
) -> None:
    """Phase 3: Cantonese etymologies + readings + transcriptions."""
    count = _insert_readings_for_language(
        cur, unihan,
        language_id=LANG_CANTONESE,
        parser=parse_cantonese_readings,
        transcription_system_id=TS_JYUTPING,
        tone_fn=tone_from_jyutping,
        primary_readings=primary_readings,
    )
    print(f"  Cantonese: {count:,} readings")


def import_japanese(
    cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]], primary_readings: dict[int, int]
) -> None:
    """Phase 4: Japanese on + kun readings.

    Unihan's kJapaneseOn/kJapaneseKun may be UPPERCASE romaji (older format)
    or katakana/hiragana (current format).  We detect which and store
    into the appropriate transcription system (kana vs hepburn).
    """
    # Collect characters that have at least one Japanese reading
    chars_with_jp: set[int] = set()
    for cp, fields in unihan.items():
        if "kJapaneseOn" in fields or "kJapaneseKun" in fields:
            chars_with_jp.add(cp)

    count = 0
    for cp in chars_with_jp:
        fields = unihan[cp]

        cur.execute(
            "INSERT INTO etymologies (codepoint, language_id, etymology_order) VALUES (?, ?, 1)",
            (cp, LANG_TOKYO),
        )
        etym_id = cur.lastrowid
        sort_idx = 0

        # On-readings
        for val in parse_japanese_on(fields):
            sort_idx += 1
            # Detect if kana (contains CJK/kana codepoints) or romaji
            is_kana = any("\u3040" <= c <= "\u30FF" for c in val)
            ts_id = TS_KANA if is_kana else TS_HEPBURN

            cur.execute(
                "INSERT INTO readings (etymology_id, kind, category, sort_order) "
                "VALUES (?, 'reading', 'on', ?)",
                (etym_id, sort_idx),
            )
            reading_id = cur.lastrowid
            cur.execute(
                "INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) "
                "VALUES (?, ?, ?)",
                (reading_id, ts_id, val),
            )
            cur.execute(
                "INSERT INTO reading_sources (reading_id, source_id) VALUES (?, ?)",
                (reading_id, SOURCE_UNIHAN),
            )
            if cp not in primary_readings:
                primary_readings[cp] = reading_id
            count += 1

        # Kun-readings
        for val in parse_japanese_kun(fields):
            sort_idx += 1
            is_kana = any("\u3040" <= c <= "\u30FF" for c in val)
            ts_id = TS_KANA if is_kana else TS_HEPBURN
            has_okurigana = "." in val

            features = '{"okurigana": true}' if has_okurigana else None

            cur.execute(
                "INSERT INTO readings (etymology_id, kind, category, sort_order, features) "
                "VALUES (?, 'reading', 'kun', ?, ?)",
                (etym_id, sort_idx, features),
            )
            reading_id = cur.lastrowid
            cur.execute(
                "INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) "
                "VALUES (?, ?, ?)",
                (reading_id, ts_id, val),
            )
            cur.execute(
                "INSERT INTO reading_sources (reading_id, source_id) VALUES (?, ?)",
                (reading_id, SOURCE_UNIHAN),
            )
            if cp not in primary_readings:
                primary_readings[cp] = reading_id
            count += 1

    print(f"  Japanese: {count:,} readings")


def import_korean(
    cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]], primary_readings: dict[int, int]
) -> None:
    """Phase 5: Korean readings (Yale from kKorean, Hangul from kHangul)."""
    chars_with_ko: set[int] = set()
    for cp, fields in unihan.items():
        if "kKorean" in fields or "kHangul" in fields:
            chars_with_ko.add(cp)

    count = 0
    for cp in chars_with_ko:
        fields = unihan[cp]
        yale_vals = parse_korean_yale(fields)
        hangul_vals = parse_korean_hangul(fields)

        if not yale_vals and not hangul_vals:
            continue

        cur.execute(
            "INSERT INTO etymologies (codepoint, language_id, etymology_order) VALUES (?, ?, 1)",
            (cp, LANG_KOREAN),
        )
        etym_id = cur.lastrowid

        # Pair up yale and hangul where possible (often 1:1),
        # then handle any extras individually.
        max_len = max(len(yale_vals), len(hangul_vals))
        for i in range(max_len):
            cur.execute(
                "INSERT INTO readings (etymology_id, kind, sort_order) VALUES (?, 'reading', ?)",
                (etym_id, i + 1),
            )
            reading_id = cur.lastrowid

            if i < len(yale_vals):
                cur.execute(
                    "INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) "
                    "VALUES (?, ?, ?)",
                    (reading_id, TS_YALE_KO, yale_vals[i]),
                )
            if i < len(hangul_vals):
                cur.execute(
                    "INSERT INTO reading_transcriptions (reading_id, transcription_system_id, value) "
                    "VALUES (?, ?, ?)",
                    (reading_id, TS_HANGUL, hangul_vals[i]),
                )

            cur.execute(
                "INSERT INTO reading_sources (reading_id, source_id) VALUES (?, ?)",
                (reading_id, SOURCE_UNIHAN),
            )
            if cp not in primary_readings:
                primary_readings[cp] = reading_id
            count += 1

    print(f"  Korean: {count:,} readings")


def import_vietnamese(
    cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]], primary_readings: dict[int, int]
) -> None:
    """Phase 6: Vietnamese readings."""
    count = _insert_readings_for_language(
        cur, unihan,
        language_id=LANG_VIETNAMESE,
        parser=parse_vietnamese,
        transcription_system_id=TS_QUOC_NGU,
        primary_readings=primary_readings,
    )
    print(f"  Vietnamese: {count:,} readings")


def import_middle_chinese(
    cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]], primary_readings: dict[int, int]
) -> None:
    """Phase 7: Middle Chinese reconstructions from kTang."""
    # Ensure the Stimson transcription system exists
    cur.execute(
        "INSERT OR IGNORE INTO transcription_systems (id, language_id, name, code, sort_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (TS_STIMSON, LANG_MIDDLE_CHINESE, "Stimson (kTang)", "stimson_ktang", 4),
    )

    count = _insert_readings_for_language(
        cur, unihan,
        language_id=LANG_MIDDLE_CHINESE,
        parser=parse_tang,
        transcription_system_id=TS_STIMSON,
        kind="reconstruction",
        primary_readings=primary_readings,
    )
    print(f"  Middle Chinese (kTang): {count:,} readings")


def import_definitions(
    cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]], primary_readings: dict[int, int]
) -> None:
    """Phase 8: kDefinition → senses attached to the primary reading.

    kDefinition is character-level (not reading-specific), so we attach
    the glosses to the first Mandarin reading.  When no reading exists
    for the character at all, we skip.
    """
    count = 0
    skipped = 0
    for cp, fields in unihan.items():
        defs = parse_definitions(fields)
        if not defs:
            continue

        reading_id = primary_readings.get(cp)
        if reading_id is None:
            skipped += 1
            continue

        for i, defn in enumerate(defs):
            cur.execute(
                "INSERT INTO senses (reading_id, sort_order, definition) VALUES (?, ?, ?)",
                (reading_id, i + 1, defn),
            )
            sense_id = cur.lastrowid
            cur.execute(
                "INSERT INTO sense_sources (sense_id, source_id) VALUES (?, ?)",
                (sense_id, SOURCE_UNIHAN),
            )
            count += 1

    print(f"  Definitions: {count:,} senses ({skipped:,} chars skipped — no reading to attach to)")


def import_variants(cur: sqlite3.Cursor, unihan: dict[int, dict[str, str]]) -> None:
    """Phase 9: simplified/traditional variants from kSimplifiedVariant, kTraditionalVariant."""
    # variant_type IDs from schema.sql
    VT_SIMPLIFIED = 1
    VT_TRADITIONAL = 2

    # Collect all codepoints that appear in the characters table so we can
    # check whether variant targets exist.
    cur.execute("SELECT codepoint FROM characters")
    known_cps: set[int] = {row[0] for row in cur.fetchall()}

    count = 0
    for cp, fields in unihan.items():
        if cp not in known_cps:
            continue

        for field, vt_id in [
            ("kSimplifiedVariant", VT_SIMPLIFIED),
            ("kTraditionalVariant", VT_TRADITIONAL),
        ]:
            raw = fields.get(field, "")
            if not raw:
                continue
            for target_cp in parse_variant_codepoints(raw):
                if target_cp not in known_cps:
                    continue  # target not in DB — skip rather than break FK
                cur.execute(
                    "INSERT OR IGNORE INTO character_variants "
                    "(codepoint, variant_type_id, variant_codepoint, source_id) "
                    "VALUES (?, ?, ?, ?)",
                    (cp, vt_id, target_cp, SOURCE_UNIHAN),
                )
                count += 1

    print(f"  Variants: {count:,} relationships")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import Unihan data into omni-hanzi DB.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip download (use previously cached Unihan.zip)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found at {args.db}")
        print("Run  python scripts/create_db.py  first.")
        sys.exit(1)

    # Step 1: download
    if not args.skip_download:
        download_unihan()
    else:
        if not any(CACHE_DIR.glob("Unihan_*.txt")):
            print(f"No Unihan files in {CACHE_DIR} — run without --skip-download first.")
            sys.exit(1)
        print(f"Using cached Unihan files in {CACHE_DIR}")

    # Step 2: parse
    print("\nParsing Unihan files ...")
    unihan = parse_unihan_files()

    # Step 3: import
    print("\nImporting into database ...")
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    cur = con.cursor()

    # Track first reading per character for definition attachment
    primary_readings: dict[int, int] = {}

    try:
        cur.execute("BEGIN")

        import_characters(cur, unihan)
        import_mandarin(cur, unihan, primary_readings)
        import_cantonese(cur, unihan, primary_readings)
        import_japanese(cur, unihan, primary_readings)
        import_korean(cur, unihan, primary_readings)
        import_vietnamese(cur, unihan, primary_readings)
        import_middle_chinese(cur, unihan, primary_readings)
        import_definitions(cur, unihan, primary_readings)
        import_variants(cur, unihan)

        con.commit()
        print("\nCommitted.")

    except Exception:
        con.rollback()
        print("\nRolled back due to error.")
        raise

    finally:
        con.close()

    # Summary
    con = sqlite3.connect(args.db)
    for table in [
        "characters", "etymologies", "readings",
        "reading_transcriptions", "senses", "character_variants",
    ]:
        (n,) = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        print(f"  {table}: {n:,} rows")
    con.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
