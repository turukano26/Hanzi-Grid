#!/usr/bin/env python3
"""
Import libhangul's hanja.txt into the omni-hanzi DB as Korean readings.

libhangul (https://github.com/libhangul/libhangul) ships a Korean→Hanja
dictionary, ``data/hanja/hanja.txt``, distributed as a colon-delimited UTF-8
text file with one entry per line:

    reading:hanja:description

  * reading     — a Hangul rendering of the entry (one syllable for single
                  characters, e.g. ``가``).
  * hanja       — the Han character(s).  e.g. ``可``.
  * description — optional ``eumhun`` (음훈): the traditional way of naming a
                  hanja, the native-Korean gloss (훈) followed by the reading
                  (음), e.g. ``옳을 가``.  Several comma-separated glosses may
                  appear (``값 가, 값/성 가``), and a minority of entries instead
                  hold variant cross-references (``歌와 同字``) or a bare gloss.
                  It is imported **verbatim** — no parsing or reconstruction.

The file is overwhelmingly a multi-character *word* dictionary; this importer
keeps only the single-Hangul→single-Hanja entries (~28k, covering ~27.5k
characters), which are the ones that map to a codepoint in our per-character
model.

For each kept entry we create a Korean reading mirroring the shape Unihan's
import_korean() produces (LANG_KOREAN, kind='reading', category=NULL, the Hangul
stored under TS_HANGUL), so that dedup_readings.py merges libhangul's Hangul
readings onto Unihan's identical ones, unioning their attestations.  The eumhun
string, when present, is stored as a second transcription on the same reading
under TS_EUMHUN.  Everything is attributed to the libhangul source.

Designed to run AFTER import_unihan.py (and alongside the other importers),
before dedup_readings.py.  Idempotent: a codepoint already attested by libhangul
is skipped on re-run.

Usage:
    python scripts/import_libhangul.py
    python scripts/import_libhangul.py --skip-download
"""

import argparse
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "omnihanzi.db"
CACHE_DIR = ROOT / "data" / "libhangul"

SOURCE_URL = (
    "https://raw.githubusercontent.com/libhangul/libhangul/main/data/hanja/hanja.txt"
)

# ---------------------------------------------------------------------------
# IDs from schema.sql seed data
# ---------------------------------------------------------------------------

LANG_KOREAN = 20
TS_HANGUL = 41        # Hangul
TS_EUMHUN = 44        # Eumhun (음훈) — raw description string
SOURCE_LIBHANGUL = 14  # libhangul in the sources table


# ---------------------------------------------------------------------------
# Han detection (single CJK ideograph)
# ---------------------------------------------------------------------------

# CJK ideograph blocks (Unified + extensions + compatibility).
_HAN_RANGES = (
    (0x3400, 0x4DBF),    # Ext A
    (0x4E00, 0x9FFF),    # Unified
    (0xF900, 0xFAFF),    # Compatibility Ideographs
    (0x20000, 0x2A6DF),  # Ext B
    (0x2A700, 0x2EBEF),  # Ext C–F
    (0x2F800, 0x2FA1F),  # Compatibility Supplement
)


def is_han(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _HAN_RANGES)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def fetch_text(*, skip_download: bool) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    txt_path = CACHE_DIR / "hanja.txt"

    if txt_path.exists() and skip_download:
        print(f"Using cached {txt_path}")
        return txt_path

    if txt_path.exists():
        print(f"Using cached {txt_path}")
        return txt_path

    if skip_download:
        print(f"No cached {txt_path} — run without --skip-download.")
        sys.exit(1)

    print(f"Downloading {SOURCE_URL} ...")
    urllib.request.urlretrieve(SOURCE_URL, txt_path)
    print(f"Saved {txt_path}")
    return txt_path


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_hanja(txt_path: Path) -> dict[int, list[dict]]:
    """Parse hanja.txt into {codepoint: [{hangul, eumhun}, ...]}.

    Only single-Hangul→single-Hanja lines are kept.  ``eumhun`` is the raw
    third field (or None if absent/empty).  Entry order follows the file.
    """
    data: dict[int, list[dict]] = {}
    total = 0
    kept = 0
    with_eumhun = 0

    with open(txt_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            total += 1

            parts = line.split(":")
            if len(parts) < 2:
                continue
            reading, hanja = parts[0], parts[1]
            eumhun = parts[2].strip() if len(parts) > 2 else ""

            # Single Hangul syllable → single Han character only.
            if len(reading) != 1 or len(hanja) != 1 or not is_han(hanja):
                continue

            kept += 1
            if eumhun:
                with_eumhun += 1

            data.setdefault(ord(hanja), []).append({
                "hangul": reading,
                "eumhun": eumhun or None,
            })

    print(f"Parsed {total:,} data lines, kept {kept:,} single-char entries "
          f"({with_eumhun:,} with eumhun)")
    print(f"  → {len(data):,} codepoints, "
          f"{sum(len(v) for v in data.values()):,} reading entries")
    return data


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_libhangul(db_path: Path, hanja: dict[int, list[dict]]) -> None:
    """Insert libhangul data as Korean reading rows attributed to libhangul.

    Each entry becomes a reading (kind='reading', category=NULL) with a Hangul
    transcription and, when present, an Eumhun transcription, plus an attestation
    by SOURCE_LIBHANGUL.  Merging with Unihan's Hangul readings is left to
    dedup_readings.py, which keys on (transcription_system_id, value).
    """
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    cur = con.cursor()

    # Existing Korean etymologies: codepoint → etymology_id
    cur.execute(
        "SELECT codepoint, id FROM etymologies WHERE language_id = ?",
        (LANG_KOREAN,),
    )
    existing_etyms: dict[int, int] = dict(cur.fetchall())

    # Codepoints already imported from libhangul (idempotency on re-run)
    cur.execute(
        """
        SELECT DISTINCT e.codepoint
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_attestations ra ON ra.reading_id = r.id
        WHERE e.language_id = ? AND ra.source_id = ?
        """,
        (LANG_KOREAN, SOURCE_LIBHANGUL),
    )
    imported_codepoints: set[int] = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT codepoint FROM characters")
    known_chars: set[int] = {row[0] for row in cur.fetchall()}

    print(f"Pre-loaded: {len(existing_etyms):,} Korean etymologies, "
          f"{len(imported_codepoints):,} already imported, "
          f"{len(known_chars):,} characters")

    stats = {
        "chars_created": 0,
        "etyms_created": 0,
        "readings_created": 0,
        "eumhun_added": 0,
    }

    try:
        cur.execute("BEGIN")

        for cp, entries in hanja.items():
            if cp in imported_codepoints:
                continue

            if cp not in known_chars:
                cur.execute(
                    "INSERT OR IGNORE INTO characters (codepoint, character) VALUES (?, ?)",
                    (cp, chr(cp)),
                )
                known_chars.add(cp)
                stats["chars_created"] += 1

            etym_id = existing_etyms.get(cp)
            if etym_id is None:
                cur.execute(
                    "INSERT INTO etymologies (codepoint, language_id, etymology_order) "
                    "VALUES (?, ?, 1)",
                    (cp, LANG_KOREAN),
                )
                etym_id = cur.lastrowid
                existing_etyms[cp] = etym_id
                stats["etyms_created"] += 1

            for sort_idx, entry in enumerate(entries, start=1):
                cur.execute(
                    "INSERT INTO readings (etymology_id, kind, sort_order) "
                    "VALUES (?, 'reading', ?)",
                    (etym_id, sort_idx),
                )
                reading_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO reading_attestations (reading_id, source_id) VALUES (?, ?)",
                    (reading_id, SOURCE_LIBHANGUL),
                )
                cur.execute(
                    "INSERT INTO reading_transcriptions "
                    "(reading_id, transcription_system_id, value) VALUES (?, ?, ?)",
                    (reading_id, TS_HANGUL, entry["hangul"]),
                )
                stats["readings_created"] += 1

                if entry["eumhun"]:
                    cur.execute(
                        "INSERT INTO reading_transcriptions "
                        "(reading_id, transcription_system_id, value) VALUES (?, ?, ?)",
                        (reading_id, TS_EUMHUN, entry["eumhun"]),
                    )
                    stats["eumhun_added"] += 1

        con.commit()
        print("\nCommitted.")

    except Exception:
        con.rollback()
        print("\nRolled back due to error.")
        raise

    finally:
        con.close()

    print(f"\n  Characters created:  {stats['chars_created']:,}")
    print(f"  Etymologies created: {stats['etyms_created']:,}")
    print(f"  Readings created:    {stats['readings_created']:,}")
    print(f"  Eumhun added:        {stats['eumhun_added']:,}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import libhangul hanja.txt into omni-hanzi DB.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip download (use previously cached data/libhangul/hanja.txt)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found at {args.db}")
        print("Run  python scripts/create_db.py  and  python scripts/import_unihan.py  first.")
        sys.exit(1)

    txt_path = fetch_text(skip_download=args.skip_download)
    print(f"\nParsing {txt_path.name} ...")
    hanja = parse_hanja(txt_path)

    print("\nImporting into database ...")
    import_libhangul(args.db, hanja)

    print("\nDone.")


if __name__ == "__main__":
    main()
