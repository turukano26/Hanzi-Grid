#!/usr/bin/env python3
"""
Import CC-Canto (and CC-CEDICT Cantonese readings) into the omni-hanzi DB.

CC-Canto is a Creative-Commons Cantonese-to-English dictionary published at
https://cantonese.org.  It is distributed in CC-CEDICT line format with one
addition: a Jyutping reading enclosed in ``{ }`` after the Pinyin ``[ ]``:

    繁體 简体 [pin1 yin1] {jyut6 ping3} /def 1/def 2/

Two files are imported (both gitignored-cached under data/cccanto/):

  * cccanto-webdist.txt          — full Cantonese dictionary: Jyutping + English
                                   definitions.  Becomes Cantonese readings
                                   with senses attributed to CC-Canto.
  * cccedict-canto-readings.txt  — Jyutping readings keyed to CC-CEDICT entries,
                                   with NO definitions.  Adds reading-only
                                   coverage (still attributed to CC-Canto).

Designed to run AFTER import_unihan.py (and alongside import_cedict.py).  It
mirrors the Cantonese reading shape Unihan creates (LANG_CANTONESE / TS_JYUTPING,
kind='reading', category=NULL, Jyutping value stored *with* its tone digit) so
that dedup_readings.py merges CC-Canto readings with Unihan's, unioning their
attestations and senses.

Usage:
    python scripts/import_cccanto.py
    python scripts/import_cccanto.py --skip-download
"""

import argparse
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "omnihanzi.db"
CACHE_DIR = ROOT / "data" / "cccanto"

# Both archives live at the root of cantonese.org.  Versioned filenames; bump
# these if cantonese.org publishes a newer release.
SOURCES = [
    (
        "https://cantonese.org/cccanto-170202.zip",
        "cccanto-webdist.txt",
    ),
    (
        "https://cantonese.org/cccedict-canto-readings-150923.zip",
        "cccedict-canto-readings.txt",
    ),
]

# ---------------------------------------------------------------------------
# IDs from schema.sql seed data
# ---------------------------------------------------------------------------

LANG_CANTONESE = 2
TS_JYUTPING = 10     # Jyutping
SOURCE_CCCANTO = 13  # CC-Canto in sources table


# ---------------------------------------------------------------------------
# Jyutping helpers
# ---------------------------------------------------------------------------

def tone_from_jyutping(jyutping: str) -> str | None:
    """Return the trailing tone digit (1-6) of a Jyutping syllable, or None."""
    if jyutping and jyutping[-1].isdigit():
        return jyutping[-1]
    return None


# ---------------------------------------------------------------------------
# Download / extract
# ---------------------------------------------------------------------------

def fetch_text(url: str, member_hint: str, *, skip_download: bool) -> Path:
    """Download a CC-Canto zip and extract its dictionary .txt into the cache.

    member_hint is the expected text filename; the first .txt member matching it
    (or, failing that, the first .txt member at all) is extracted.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE_DIR / Path(url).name
    txt_path = CACHE_DIR / member_hint

    if txt_path.exists() and skip_download:
        print(f"Using cached {txt_path}")
        return txt_path

    if not zip_path.exists():
        if skip_download:
            print(f"No cached {zip_path} — run without --skip-download.")
            sys.exit(1)
        print(f"Downloading {url} ...")
        urllib.request.urlretrieve(url, zip_path)
    else:
        print(f"Using cached {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        txt_members = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not txt_members:
            print(f"No .txt member found inside {zip_path}")
            sys.exit(1)
        member = next((n for n in txt_members if Path(n).name == member_hint),
                      txt_members[0])
        with zf.open(member) as src:
            txt_path.write_bytes(src.read())
        print(f"Extracted {member} → {txt_path}")

    return txt_path


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_cccanto(txt_path: Path) -> dict[int, list[dict]]:
    """Parse a CC-Canto-format file into {codepoint: [{jyutping, tone, definitions}, ...]}.

    Only single-character entries are kept; both traditional and simplified
    forms are indexed.  Lines without a ``{jyutping}`` block are skipped.  The
    definitions list may be empty (the readings-only file has no ``/.../``).
    """
    data: dict[int, list[dict]] = {}
    total_lines = 0
    single_char_lines = 0

    with open(txt_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("%"):
                continue
            total_lines += 1

            try:
                # "trad simp [pinyin] {jyutping} /def1/def2/"
                bracket_close = line.index("]")
                head = line[: line.index("[")].strip()
                parts = head.split(" ", 1)
                if len(parts) != 2:
                    continue
                trad, simp = parts[0], parts[1]

                # Single characters only
                if len(trad) != 1 or len(simp) != 1:
                    continue

                # Jyutping in { } after the pinyin bracket
                brace_open = line.index("{", bracket_close)
                brace_close = line.index("}", brace_open)
                jyut_raw = line[brace_open + 1 : brace_close].strip().lower()
                # Single-char entries should be one syllable; skip multi-syllable
                if not jyut_raw or " " in jyut_raw:
                    continue

                single_char_lines += 1

                tone = tone_from_jyutping(jyut_raw)

                # Definitions (optional — readings-only file has none)
                defs_part = line[brace_close + 1 :].strip().strip("/")
                definitions = [d.strip() for d in defs_part.split("/") if d.strip()]

                entry = {
                    "jyutping": jyut_raw,
                    "tone": tone,
                    "definitions": definitions,
                }

                for char in {trad, simp}:
                    data.setdefault(ord(char), []).append(entry)

            except (ValueError, IndexError):
                continue

    print(f"Parsed {total_lines:,} lines, {single_char_lines:,} single-char entries")
    print(f"  → {len(data):,} codepoints, "
          f"{sum(len(v) for v in data.values()):,} reading entries")
    return data


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_cccanto(db_path: Path, cccanto: dict[int, list[dict]]) -> None:
    """Insert CC-Canto data as Cantonese reading rows attributed to CC-Canto.

    Each entry becomes a reading row (kind='reading', category=NULL) with a
    Jyutping transcription and an attestation by SOURCE_CCCANTO; definitions
    become senses.  Merging with Unihan's Jyutping readings is left to
    dedup_readings.py, which keys on (transcription_system_id, value).
    """
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    cur = con.cursor()

    # Existing Cantonese etymologies: codepoint → etymology_id
    cur.execute(
        "SELECT codepoint, id FROM etymologies WHERE language_id = ?",
        (LANG_CANTONESE,),
    )
    existing_etyms: dict[int, int] = dict(cur.fetchall())

    # Codepoints already imported from CC-Canto (idempotency on re-run)
    cur.execute(
        """
        SELECT DISTINCT e.codepoint
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_attestations ra ON ra.reading_id = r.id
        WHERE e.language_id = ? AND ra.source_id = ?
        """,
        (LANG_CANTONESE, SOURCE_CCCANTO),
    )
    imported_codepoints: set[int] = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT codepoint FROM characters")
    known_chars: set[int] = {row[0] for row in cur.fetchall()}

    print(f"Pre-loaded: {len(existing_etyms):,} Cantonese etymologies, "
          f"{len(imported_codepoints):,} already imported, "
          f"{len(known_chars):,} characters")

    stats = {
        "chars_created": 0,
        "etyms_created": 0,
        "readings_created": 0,
        "senses_added": 0,
    }

    try:
        cur.execute("BEGIN")

        for cp, entries in cccanto.items():
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
                    (cp, LANG_CANTONESE),
                )
                etym_id = cur.lastrowid
                existing_etyms[cp] = etym_id
                stats["etyms_created"] += 1

            for sort_idx, entry in enumerate(entries, start=1):
                cur.execute(
                    "INSERT INTO readings (etymology_id, kind, tone, sort_order) "
                    "VALUES (?, 'reading', ?, ?)",
                    (etym_id, entry["tone"], sort_idx),
                )
                reading_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO reading_attestations (reading_id, source_id) VALUES (?, ?)",
                    (reading_id, SOURCE_CCCANTO),
                )
                cur.execute(
                    "INSERT INTO reading_transcriptions "
                    "(reading_id, transcription_system_id, value) VALUES (?, ?, ?)",
                    (reading_id, TS_JYUTPING, entry["jyutping"]),
                )
                stats["readings_created"] += 1

                for i, defn in enumerate(entry["definitions"], start=1):
                    cur.execute(
                        "INSERT INTO senses (reading_id, source_id, sort_order, definition) "
                        "VALUES (?, ?, ?, ?)",
                        (reading_id, SOURCE_CCCANTO, i, defn),
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

    print(f"\n  Characters created:  {stats['chars_created']:,}")
    print(f"  Etymologies created: {stats['etyms_created']:,}")
    print(f"  Readings created:    {stats['readings_created']:,}")
    print(f"  Senses added:        {stats['senses_added']:,}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import CC-Canto into omni-hanzi DB.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip download (use previously cached files under data/cccanto/)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found at {args.db}")
        print("Run  python scripts/create_db.py  and  python scripts/import_unihan.py  first.")
        sys.exit(1)

    # Parse every source file and merge their entries per codepoint.
    merged: dict[int, list[dict]] = {}
    for url, member in SOURCES:
        txt_path = fetch_text(url, member, skip_download=args.skip_download)
        print(f"\nParsing {member} ...")
        for cp, entries in parse_cccanto(txt_path).items():
            merged.setdefault(cp, []).extend(entries)

    print(f"\nMerged total: {len(merged):,} codepoints, "
          f"{sum(len(v) for v in merged.values()):,} reading entries")

    print("\nImporting into database ...")
    import_cccanto(args.db, merged)

    print("\nDone.")


if __name__ == "__main__":
    main()
