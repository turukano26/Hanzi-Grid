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
    """Insert CC-CEDICT data into the database, merging with existing Unihan data."""
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

    # Existing Mandarin readings: (codepoint, accented_pinyin) → reading_id
    cur.execute(
        """
        SELECT e.codepoint, rt.value, r.id
        FROM readings r
        JOIN etymologies e  ON e.id  = r.etymology_id
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        WHERE e.language_id = ? AND rt.transcription_system_id = ?
        """,
        (LANG_MANDARIN, TS_PINYIN),
    )
    existing_readings: dict[tuple[int, str], int] = {}
    for cp, pinyin, reading_id in cur.fetchall():
        key = (cp, unicodedata.normalize("NFC", pinyin))
        existing_readings[key] = reading_id

    # Max reading sort_order per etymology (to append new readings correctly)
    cur.execute(
        """
        SELECT e.id, COALESCE(MAX(r.sort_order), 0)
        FROM etymologies e
        LEFT JOIN readings r ON r.etymology_id = e.id
        WHERE e.language_id = ?
        GROUP BY e.id
        """,
        (LANG_MANDARIN,),
    )
    max_reading_sort: dict[int, int] = dict(cur.fetchall())

    # Max sense sort_order per reading (to continue numbering)
    cur.execute("SELECT reading_id, MAX(sort_order) FROM senses GROUP BY reading_id")
    max_sense_sort: dict[int, int] = dict(cur.fetchall())

    # Existing characters (for checking FK safety)
    cur.execute("SELECT codepoint FROM characters")
    known_chars: set[int] = {row[0] for row in cur.fetchall()}

    print(f"Pre-loaded: {len(existing_etyms):,} etymologies, "
          f"{len(existing_readings):,} readings, {len(known_chars):,} characters")

    # ------------------------------------------------------------------
    # Process entries
    # ------------------------------------------------------------------

    stats = {
        "chars_created": 0,
        "etyms_created": 0,
        "readings_matched": 0,
        "readings_created": 0,
        "pinyin_num_added": 0,
        "senses_added": 0,
    }

    try:
        cur.execute("BEGIN")

        for cp, entries in cedict.items():
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
                max_reading_sort[etym_id] = 0
                stats["etyms_created"] += 1

            for entry in entries:
                pinyin_accent = unicodedata.normalize("NFC", entry["pinyin_accent"])
                pinyin_num = entry["pinyin_num"]
                tone = entry["tone"]
                defs = entry["definitions"]

                # --- Match or create reading ---
                reading_id = existing_readings.get((cp, pinyin_accent))

                if reading_id is not None:
                    # Reading exists (from Unihan) — add CEDICT as second source
                    cur.execute(
                        "INSERT OR IGNORE INTO reading_sources (reading_id, source_id) "
                        "VALUES (?, ?)",
                        (reading_id, SOURCE_CEDICT),
                    )
                    # Add numbered pinyin transcription if missing
                    cur.execute(
                        "INSERT OR IGNORE INTO reading_transcriptions "
                        "(reading_id, transcription_system_id, value) VALUES (?, ?, ?)",
                        (reading_id, TS_PINYIN_NUM, pinyin_num),
                    )
                    if cur.rowcount > 0:
                        stats["pinyin_num_added"] += 1
                    stats["readings_matched"] += 1

                else:
                    # New reading — create under existing etymology
                    max_reading_sort[etym_id] = max_reading_sort.get(etym_id, 0) + 1
                    cur.execute(
                        "INSERT INTO readings (etymology_id, kind, tone, sort_order) "
                        "VALUES (?, 'reading', ?, ?)",
                        (etym_id, tone, max_reading_sort[etym_id]),
                    )
                    reading_id = cur.lastrowid

                    # Transcriptions: both accented and numbered
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

                    # Source
                    cur.execute(
                        "INSERT INTO reading_sources (reading_id, source_id) VALUES (?, ?)",
                        (reading_id, SOURCE_CEDICT),
                    )

                    existing_readings[(cp, pinyin_accent)] = reading_id
                    stats["readings_created"] += 1

                # --- Add definitions as senses ---
                base_sort = max_sense_sort.get(reading_id, 0)
                for i, defn in enumerate(defs):
                    cur.execute(
                        "INSERT INTO senses (reading_id, sort_order, definition) "
                        "VALUES (?, ?, ?)",
                        (reading_id, base_sort + i + 1, defn),
                    )
                    sense_id = cur.lastrowid
                    cur.execute(
                        "INSERT INTO sense_sources (sense_id, source_id) VALUES (?, ?)",
                        (sense_id, SOURCE_CEDICT),
                    )
                    stats["senses_added"] += 1

                max_sense_sort[reading_id] = base_sort + len(defs)

        con.commit()
        print("\nCommitted.")

    except Exception:
        con.rollback()
        print("\nRolled back due to error.")
        raise

    finally:
        con.close()

    # Print stats
    print(f"\n  Characters created:        {stats['chars_created']:,}")
    print(f"  Etymologies created:       {stats['etyms_created']:,}")
    print(f"  Readings matched (Unihan): {stats['readings_matched']:,}")
    print(f"  Readings created (new):    {stats['readings_created']:,}")
    print(f"  Numbered pinyin added:     {stats['pinyin_num_added']:,}")
    print(f"  Senses added:              {stats['senses_added']:,}")


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
    for table in [
        "characters", "etymologies", "readings",
        "reading_transcriptions", "senses", "reading_sources", "sense_sources",
    ]:
        (n,) = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        print(f"  {table}: {n:,} rows")

    # How many readings are attested by both sources?
    (both,) = con.execute("""
        SELECT COUNT(DISTINCT rs1.reading_id)
        FROM reading_sources rs1
        JOIN reading_sources rs2 ON rs2.reading_id = rs1.reading_id
        WHERE rs1.source_id = 1 AND rs2.source_id = 2
    """).fetchone()
    print(f"\n  Readings attested by BOTH Unihan + CEDICT: {both:,}")

    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
