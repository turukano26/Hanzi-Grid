#!/usr/bin/env python3
"""
Import CC-CEDICT dictionary into the omni-hanzi SQLite database.

Downloads CC-CEDICT from MDBG, parses single-character entries, and adds
Mandarin readings + per-reading definitions with source attribution.

Designed to run AFTER import_unihan.py.  It will:
  - Add CC-CEDICT as a second source for readings Unihan already created
  - Create new readings for pinyin that Unihan didn't have
  - Add per-reading definitions (Unihan's kDefinition was character-level)
  - Add numbered-pinyin transcriptions alongside Unihan's accented pinyin

Usage:
    python scripts/import_cedict.py
"""

import argparse
import gzip
import sqlite3
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "omnihanzi.db"
CACHE_DIR = ROOT / "data" / "cedict"
CEDICT_URL = (
    "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
)

# ---------------------------------------------------------------------------
# IDs from schema.sql seed data
# ---------------------------------------------------------------------------

LANG_MANDARIN = 1
TS_PINYIN = 1       # accented pinyin
TS_PINYIN_NUM = 2   # numbered pinyin
SOURCE_CEDICT = 1   # CC-CEDICT in sources table


# ---------------------------------------------------------------------------
# Pinyin conversion: numbered → accented
# ---------------------------------------------------------------------------

_TONE_VOWELS = {
    "a": "āáǎà", "e": "ēéěè", "i": "īíǐì",
    "o": "ōóǒò", "u": "ūúǔù", "ü": "ǖǘǚǜ",
}


def numbered_to_accented(syllable: str) -> str:
    """Convert a single numbered-pinyin syllable to accented form.

    >>> numbered_to_accented('sheng1')
    'shēng'
    >>> numbered_to_accented('lu:4')
    'lǜ'
    >>> numbered_to_accented('de5')
    'de'
    """
    if not syllable:
        return syllable

    # Tone digit at the end
    if syllable[-1] not in "12345":
        return syllable

    tone_idx = int(syllable[-1]) - 1  # 0-based
    base = syllable[:-1]

    # CC-CEDICT uses "u:" for ü
    base = base.replace("u:", "ü").replace("U:", "Ü")

    # Tone 5 (neutral) → no diacritical
    if tone_idx == 4:
        return base

    lower = base.lower()

    # Rule 1: 'a' or 'e' always takes the mark
    for i, c in enumerate(base):
        if c.lower() in ("a", "e"):
            marked = _TONE_VOWELS[c.lower()][tone_idx]
            if c.isupper():
                marked = marked.upper()
            return base[:i] + marked + base[i + 1 :]

    # Rule 2: 'ou' → mark the 'o'
    ou = lower.find("ou")
    if ou >= 0:
        c = base[ou]
        marked = _TONE_VOWELS[c.lower()][tone_idx]
        if c.isupper():
            marked = marked.upper()
        return base[:ou] + marked + base[ou + 1 :]

    # Rule 3: mark the last vowel
    for i in range(len(base) - 1, -1, -1):
        if base[i].lower() in _TONE_VOWELS:
            c = base[i]
            marked = _TONE_VOWELS[c.lower()][tone_idx]
            if c.isupper():
                marked = marked.upper()
            return base[:i] + marked + base[i + 1 :]

    # No vowel found (rare edge case)
    return base


def tone_from_numbered(syllable: str) -> str:
    """Extract tone digit from numbered pinyin."""
    if syllable and syllable[-1] in "12345":
        return syllable[-1]
    return "5"


# ---------------------------------------------------------------------------
# CC-CEDICT parsing
# ---------------------------------------------------------------------------

def download_cedict() -> Path:
    """Download CC-CEDICT .gz file, return path to extracted .txt."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gz_path = CACHE_DIR / "cedict.txt.gz"
    txt_path = CACHE_DIR / "cedict.txt"

    if not gz_path.exists():
        print(f"Downloading {CEDICT_URL} ...")
        urllib.request.urlretrieve(CEDICT_URL, gz_path)
    else:
        print(f"Using cached {gz_path}")

    # Decompress
    print("Decompressing ...")
    with gzip.open(gz_path, "rb") as gz, open(txt_path, "wb") as out:
        out.write(gz.read())

    return txt_path


def parse_cedict(txt_path: Path) -> dict[int, list[dict]]:
    """Parse CC-CEDICT into {codepoint: [{pinyin_num, pinyin_accent, tone, definitions}, ...]}.

    Only single-character entries are kept.
    Both traditional and simplified forms are indexed.
    """
    data: dict[int, list[dict]] = {}
    total_lines = 0
    single_char_lines = 0

    with open(txt_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            total_lines += 1

            try:
                # Format: "traditional simplified [pin1 yin1] /def1/def2/"
                bracket_open = line.index("[")
                bracket_close = line.index("]")

                head = line[:bracket_open].strip()
                parts = head.split(" ", 1)
                if len(parts) != 2:
                    continue
                trad, simp = parts[0], parts[1]

                # Filter: single characters only
                if len(trad) != 1 or len(simp) != 1:
                    continue

                single_char_lines += 1

                pinyin_raw = line[bracket_open + 1 : bracket_close].strip()
                # Single-char entries should have exactly one syllable,
                # but some have spaces (e.g., "xx5 r5").  Take the full string
                # and treat as a single reading if no space, skip otherwise.
                if " " in pinyin_raw:
                    continue

                pinyin_num = pinyin_raw.lower()
                pinyin_accent = numbered_to_accented(pinyin_num)
                tone = tone_from_numbered(pinyin_num)

                # Definitions
                defs_part = line[bracket_close + 1 :].strip()
                defs_part = defs_part.strip("/")
                definitions = [d.strip() for d in defs_part.split("/") if d.strip()]
                if not definitions:
                    continue

                entry = {
                    "pinyin_num": pinyin_num,
                    "pinyin_accent": pinyin_accent,
                    "tone": tone,
                    "definitions": definitions,
                }

                # Index under both traditional and simplified codepoints
                for char in {trad, simp}:
                    cp = ord(char)
                    data.setdefault(cp, []).append(entry)

            except (ValueError, IndexError):
                continue

    print(f"Parsed {total_lines:,} total lines, {single_char_lines:,} single-char entries")
    print(f"  → {len(data):,} unique codepoints, {sum(len(v) for v in data.values()):,} reading entries")
    return data


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_cedict(db_path: Path, cedict: dict[int, list[dict]]) -> None:
    """Insert CC-CEDICT data into the database as its own reading rows.

    Each CEDICT entry becomes a new reading row with source_id = SOURCE_CEDICT.
    No attempt is made to merge with existing Unihan readings; deduplication by
    pinyin value happens at display time in _get_mandarin().
    """
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    cur = con.cursor()

    # ------------------------------------------------------------------
    # Pre-load existing state for efficient lookups
    # ------------------------------------------------------------------

    # Existing Mandarin etymologies: codepoint → etymology_id
    cur.execute(
        "SELECT codepoint, id FROM etymologies WHERE language_id = ?",
        (LANG_MANDARIN,),
    )
    existing_etyms: dict[int, int] = dict(cur.fetchall())

    # Codepoints that already have CEDICT readings (idempotency on re-run)
    cur.execute(
        """
        SELECT DISTINCT e.codepoint
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        WHERE e.language_id = ? AND r.source_id = ?
        """,
        (LANG_MANDARIN, SOURCE_CEDICT),
    )
    imported_codepoints: set[int] = {row[0] for row in cur.fetchall()}

    # Existing characters (for checking FK safety)
    cur.execute("SELECT codepoint FROM characters")
    known_chars: set[int] = {row[0] for row in cur.fetchall()}

    print(f"Pre-loaded: {len(existing_etyms):,} etymologies, "
          f"{len(imported_codepoints):,} already imported, {len(known_chars):,} characters")

    # ------------------------------------------------------------------
    # Process entries
    # ------------------------------------------------------------------

    stats = {
        "chars_created": 0,
        "etyms_created": 0,
        "readings_created": 0,
        "senses_added": 0,
    }

    try:
        cur.execute("BEGIN")

        for cp, entries in cedict.items():
            # Skip if already imported (idempotency)
            if cp in imported_codepoints:
                continue

            # Ensure character exists
            if cp not in known_chars:
                cur.execute(
                    "INSERT OR IGNORE INTO characters (codepoint, character) VALUES (?, ?)",
                    (cp, chr(cp)),
                )
                known_chars.add(cp)
                stats["chars_created"] += 1

            # Get or create Mandarin etymology
            etym_id = existing_etyms.get(cp)
            if etym_id is None:
                cur.execute(
                    "INSERT INTO etymologies (codepoint, language_id, etymology_order) "
                    "VALUES (?, ?, 1)",
                    (cp, LANG_MANDARIN),
                )
                etym_id = cur.lastrowid
                existing_etyms[cp] = etym_id
                stats["etyms_created"] += 1

            for sort_idx, entry in enumerate(entries, start=1):
                pinyin_accent = unicodedata.normalize("NFC", entry["pinyin_accent"])
                pinyin_num = entry["pinyin_num"]
                tone = entry["tone"]
                defs = entry["definitions"]

                # Create new reading row under SOURCE_CEDICT
                cur.execute(
                    "INSERT INTO readings (etymology_id, source_id, kind, tone, sort_order) "
                    "VALUES (?, ?, 'reading', ?, ?)",
                    (etym_id, SOURCE_CEDICT, tone, sort_idx),
                )
                reading_id = cur.lastrowid

                # Both accented and numbered pinyin transcriptions
                cur.execute(
                    "INSERT INTO reading_transcriptions "
                    "(reading_id, transcription_system_id, value) VALUES (?, ?, ?)",
                    (reading_id, TS_PINYIN, pinyin_accent),
                )
                cur.execute(
                    "INSERT INTO reading_transcriptions "
                    "(reading_id, transcription_system_id, value) VALUES (?, ?, ?)",
                    (reading_id, TS_PINYIN_NUM, pinyin_num),
                )
                stats["readings_created"] += 1

                # Definitions as senses
                for i, defn in enumerate(defs, start=1):
                    cur.execute(
                        "INSERT INTO senses (reading_id, source_id, sort_order, definition) "
                        "VALUES (?, ?, ?, ?)",
                        (reading_id, SOURCE_CEDICT, i, defn),
                    )
                    stats["senses_added"] += 1

        con.commit()
        print("\nCommitted.")

    except Exception:
        con.rollback()
        print("\nRolled back due to error.")
        raise

    finally:
        con.close()

    # Print stats
    print(f"\n  Characters created:  {stats['chars_created']:,}")
    print(f"  Etymologies created: {stats['etyms_created']:,}")
    print(f"  Readings created:    {stats['readings_created']:,}")
    print(f"  Senses added:        {stats['senses_added']:,}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import CC-CEDICT into omni-hanzi DB.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip download (use previously cached cedict.txt.gz)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found at {args.db}")
        print("Run  python scripts/create_db.py  and  python scripts/import_unihan.py  first.")
        sys.exit(1)

    # Step 1: download
    if not args.skip_download:
        txt_path = download_cedict()
    else:
        txt_path = CACHE_DIR / "cedict.txt"
        if not txt_path.exists():
            print(f"No cached cedict.txt at {txt_path} — run without --skip-download.")
            sys.exit(1)
        print(f"Using cached {txt_path}")

    # Step 2: parse
    print("\nParsing CC-CEDICT ...")
    cedict = parse_cedict(txt_path)

    # Step 3: import
    print("\nImporting into database ...")
    import_cedict(args.db, cedict)

    # Summary
    con = sqlite3.connect(args.db)
    print("\nRow counts after import:")
    for table in ["characters", "etymologies", "readings", "reading_transcriptions", "senses"]:
        (n,) = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        print(f"  {table}: {n:,} rows")

    # How many codepoints have readings from both Unihan and CEDICT?
    (both,) = con.execute("""
        SELECT COUNT(DISTINCT e.codepoint)
        FROM etymologies e
        WHERE e.language_id = 1
          AND EXISTS (SELECT 1 FROM readings r WHERE r.etymology_id = e.id AND r.source_id = 1)
          AND EXISTS (SELECT 1 FROM readings r WHERE r.etymology_id = e.id AND r.source_id = 2)
    """).fetchone()
    print(f"\n  Characters with both Unihan + CEDICT Mandarin readings: {both:,}")

    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
