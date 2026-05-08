#!/usr/bin/env python3
"""
Import Kanjidic2 into the omni-hanzi SQLite database.

Downloads Kanjidic2 XML from EDRDG, parses all kanji entries, and:
  - Updates characters.frequency_rank with newspaper frequency (1–2500)
  - Updates characters.stroke_count with Kanjidic2 data
  - Creates one kana reading per Kanjidic2 entry under SOURCE_KD2, without
    attempting to merge with existing Unihan readings — duplicates are
    deduplicated at display time by app.py's _get_japanese()
  - Adds English meanings as senses
  - Records Kanjidic2 source attribution throughout

Designed to run AFTER import_unihan.py.

Usage:
    python scripts/import_kanjidic2.py
    python scripts/import_kanjidic2.py --skip-download
"""

import argparse
import gzip
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "omnihanzi.db"
CACHE_DIR = ROOT / "data" / "kanjidic2"
KD2_URL = "https://www.edrdg.org/kanjidic/kanjidic2.xml.gz"

# ---------------------------------------------------------------------------
# IDs from schema.sql seed data
# ---------------------------------------------------------------------------

LANG_TOKYO = 10
TS_KANA = 32
SOURCE_KD2 = 3


# ---------------------------------------------------------------------------
# Download / decompress
# ---------------------------------------------------------------------------

def download_kanjidic2() -> Path:
    """Download and decompress Kanjidic2 XML. Returns path to the .xml file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gz_path = CACHE_DIR / "kanjidic2.xml.gz"
    xml_path = CACHE_DIR / "kanjidic2.xml"

    if not gz_path.exists():
        print(f"Downloading {KD2_URL} ...")
        urllib.request.urlretrieve(KD2_URL, gz_path)
    else:
        print(f"Using cached {gz_path}")

    print("Decompressing ...")
    with gzip.open(gz_path, 'rb') as gz, open(xml_path, 'wb') as out:
        out.write(gz.read())

    return xml_path


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

def _try_int(text: str | None) -> int | None:
    try:
        return int(text) if text else None
    except (ValueError, TypeError):
        return None


def parse_kanjidic2(xml_path: Path) -> list[dict]:
    """Parse Kanjidic2 XML → list of kanji entry dicts.

    Each dict has:
        codepoint    int
        character    str
        grade        int | None   — PRC/Japan school grade (1–6, 8=jōyō, 9–10=jinmeiyō)
        stroke_count int | None
        freq         int | None   — newspaper frequency rank (1 = most common, max ~2500)
        jlpt         int | None   — JLPT level 1–4 (pre-2010 scale)
        rmgroups     list[dict]   — each has 'on', 'kun', 'meanings' (English only)
    """
    print(f"Parsing {xml_path} ...")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    entries = []
    for char_elem in root.findall('character'):
        literal = char_elem.findtext('literal', '')
        if not literal or len(literal) != 1:
            continue

        misc = char_elem.find('misc')
        grade = stroke_count = freq = jlpt = None
        if misc is not None:
            grade        = _try_int(misc.findtext('grade'))
            stroke_count = _try_int(misc.findtext('stroke_count'))
            freq         = _try_int(misc.findtext('freq'))
            jlpt         = _try_int(misc.findtext('jlpt'))

        rmgroups = []
        rm_elem = char_elem.find('reading_meaning')
        if rm_elem is not None:
            for rmg in rm_elem.findall('rmgroup'):
                on_readings  = [r.text for r in rmg.findall('reading')
                                if r.get('r_type') == 'ja_on'  and r.text]
                kun_readings = [r.text for r in rmg.findall('reading')
                                if r.get('r_type') == 'ja_kun' and r.text]
                meanings     = [m.text for m in rmg.findall('meaning')
                                if m.get('m_lang') is None and m.text]
                if on_readings or kun_readings:
                    rmgroups.append({
                        'on':       on_readings,
                        'kun':      kun_readings,
                        'meanings': meanings,
                    })

        entries.append({
            'codepoint':    ord(literal),
            'character':    literal,
            'grade':        grade,
            'stroke_count': stroke_count,
            'freq':         freq,
            'jlpt':         jlpt,
            'rmgroups':     rmgroups,
        })

    print(f"  Parsed {len(entries):,} kanji entries")
    return entries


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_kanjidic2(db_path: Path, entries: list[dict]) -> None:
    """Insert Kanjidic2 data into the database.

    Each Kanjidic2 reading is stored as a separate row under SOURCE_KD2 with a
    kana transcription. No attempt is made to merge with existing Unihan readings;
    deduplication by pronunciation happens at display time in _get_japanese().
    """
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    cur = con.cursor()

    # ------------------------------------------------------------------
    # Pre-load existing state
    # ------------------------------------------------------------------

    # Existing Japanese etymologies: codepoint → etymology_id
    cur.execute(
        "SELECT codepoint, id FROM etymologies WHERE language_id = ?",
        (LANG_TOKYO,),
    )
    existing_etyms: dict[int, int] = dict(cur.fetchall())

    # Etymologies that already have KD2 readings (for idempotency on re-run)
    cur.execute(
        """
        SELECT DISTINCT r.etymology_id
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        WHERE e.language_id = ? AND r.source_id = ?
        """,
        (LANG_TOKYO, SOURCE_KD2),
    )
    imported_etyms: set[int] = {row[0] for row in cur.fetchall()}

    # Known characters
    cur.execute("SELECT codepoint FROM characters")
    known_chars: set[int] = {row[0] for row in cur.fetchall()}

    print(f"Pre-loaded: {len(existing_etyms):,} etymologies, "
          f"{len(imported_etyms):,} already imported, {len(known_chars):,} characters")

    # ------------------------------------------------------------------
    # Process entries
    # ------------------------------------------------------------------

    stats = {
        'chars_created':  0,
        'chars_updated':  0,
        'etyms_created':  0,
        'readings_created': 0,
        'senses_added':   0,
    }

    try:
        cur.execute("BEGIN")

        for entry in entries:
            cp = entry['codepoint']

            # Ensure character row exists
            if cp not in known_chars:
                cur.execute(
                    "INSERT OR IGNORE INTO characters "
                    "(codepoint, character, stroke_count, frequency_rank) "
                    "VALUES (?, ?, ?, ?)",
                    (cp, entry['character'], entry['stroke_count'], entry['freq']),
                )
                known_chars.add(cp)
                stats['chars_created'] += 1
            else:
                # Update frequency and stroke count — Kanjidic2 is authoritative for Japanese
                updates, values = [], []
                if entry['freq'] is not None:
                    updates.append("frequency_rank = ?")
                    values.append(entry['freq'])
                if entry['stroke_count'] is not None:
                    updates.append("stroke_count = ?")
                    values.append(entry['stroke_count'])
                if updates:
                    cur.execute(
                        f"UPDATE characters SET {', '.join(updates)} WHERE codepoint = ?",
                        (*values, cp),
                    )
                    stats['chars_updated'] += 1

            if not entry['rmgroups']:
                continue

            # Get or create Japanese etymology
            etym_id = existing_etyms.get(cp)
            if etym_id is None:
                cur.execute(
                    "INSERT INTO etymologies (codepoint, language_id, etymology_order) "
                    "VALUES (?, ?, 1)",
                    (cp, LANG_TOKYO),
                )
                etym_id = cur.lastrowid
                existing_etyms[cp] = etym_id
                stats['etyms_created'] += 1

            # Skip readings if already imported from KD2 (idempotency)
            if etym_id in imported_etyms:
                continue

            # Process each rmgroup (usually one per kanji)
            sort_counter = 0
            for rmg in entry['rmgroups']:
                first_reading_id = None

                for category, kana_list in [('on', rmg['on']), ('kun', rmg['kun'])]:
                    for kana_val in kana_list:
                        has_okurigana = '.' in kana_val
                        features = '{"okurigana": true}' if has_okurigana else None

                        sort_counter += 1
                        cur.execute(
                            "INSERT INTO readings "
                            "(etymology_id, source_id, kind, category, sort_order, features) "
                            "VALUES (?, ?, 'reading', ?, ?, ?)",
                            (etym_id, SOURCE_KD2, category, sort_counter, features),
                        )
                        reading_id = cur.lastrowid

                        cur.execute(
                            "INSERT INTO reading_transcriptions "
                            "(reading_id, transcription_system_id, value) VALUES (?, ?, ?)",
                            (reading_id, TS_KANA, kana_val),
                        )

                        if first_reading_id is None:
                            first_reading_id = reading_id
                        stats['readings_created'] += 1

                # Attach English meanings to the first reading of this rmgroup
                if first_reading_id is not None and rmg['meanings']:
                    for i, meaning in enumerate(rmg['meanings'], start=1):
                        cur.execute(
                            "INSERT INTO senses (reading_id, source_id, sort_order, definition) "
                            "VALUES (?, ?, ?, ?)",
                            (first_reading_id, SOURCE_KD2, i, meaning),
                        )
                        stats['senses_added'] += 1

        con.commit()
        print("\nCommitted.")

    except Exception:
        con.rollback()
        print("\nRolled back due to error.")
        raise

    finally:
        con.close()

    print(f"\n  Characters created:  {stats['chars_created']:,}")
    print(f"  Characters updated:  {stats['chars_updated']:,}")
    print(f"  Etymologies created: {stats['etyms_created']:,}")
    print(f"  Readings created:    {stats['readings_created']:,}")
    print(f"  Senses added:        {stats['senses_added']:,}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import Kanjidic2 into omni-hanzi DB.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip download (use previously cached kanjidic2.xml.gz)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found at {args.db}")
        print("Run  python scripts/create_db.py  and  python scripts/import_unihan.py  first.")
        sys.exit(1)

    # Step 1: download
    if not args.skip_download:
        xml_path = download_kanjidic2()
    else:
        xml_path = CACHE_DIR / "kanjidic2.xml"
        if not xml_path.exists():
            # Try decompressing from cached gz
            gz_path = CACHE_DIR / "kanjidic2.xml.gz"
            if gz_path.exists():
                print(f"Decompressing cached {gz_path} ...")
                with gzip.open(gz_path, 'rb') as gz, open(xml_path, 'wb') as out:
                    out.write(gz.read())
            else:
                print(f"No cached file at {xml_path} — run without --skip-download.")
                sys.exit(1)
        else:
            print(f"Using cached {xml_path}")

    # Step 2: parse
    print("\nParsing Kanjidic2 ...")
    entries = parse_kanjidic2(xml_path)

    # Step 3: import
    print("\nImporting into database ...")
    import_kanjidic2(args.db, entries)

    # Summary
    con = sqlite3.connect(args.db)
    print("\nRow counts after import:")
    for table in ["characters", "etymologies", "readings", "reading_transcriptions", "senses"]:
        (n,) = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        print(f"  {table}: {n:,} rows")

    # Characters with Japanese readings from both Unihan and Kanjidic2
    (both,) = con.execute("""
        SELECT COUNT(DISTINCT e.codepoint)
        FROM etymologies e
        WHERE e.language_id = 10
          AND EXISTS (SELECT 1 FROM readings r WHERE r.etymology_id = e.id AND r.source_id = 2)
          AND EXISTS (SELECT 1 FROM readings r WHERE r.etymology_id = e.id AND r.source_id = 3)
    """).fetchone()
    print(f"\n  Characters with both Unihan + Kanjidic2 Japanese readings: {both:,}")

    # Kana coverage for Japanese readings
    (n,) = con.execute("""
        SELECT COUNT(*)
        FROM reading_transcriptions rt
        JOIN readings r ON r.id = rt.reading_id
        JOIN etymologies e ON e.id = r.etymology_id
        WHERE e.language_id = 10 AND rt.transcription_system_id = 32
    """).fetchone()
    print(f"  Japanese kana transcriptions: {n:,}")

    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
