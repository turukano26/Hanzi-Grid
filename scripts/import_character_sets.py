#!/usr/bin/env python3
"""
Import character sets into the omni-hanzi SQLite database.

Currently imports:
  - Jōyō Kanji (grades 1–6, secondary school) from KANJIDIC2
  - Jinmeiyō Kanji (standard and variant forms) from KANJIDIC2

Designed to run AFTER import_kanjidic2.py (which downloads and caches
the KANJIDIC2 XML file used here).

Usage:
    python scripts/import_character_sets.py
    python scripts/import_character_sets.py --skip-download
    python scripts/import_character_sets.py --force   # overwrite existing sets
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
# Grade → (set name, level name, level sort_order)
# ---------------------------------------------------------------------------

GRADE_MAP = {
    1: ("Jōyō Kanji",     "First Grade",             1),
    2: ("Jōyō Kanji",     "Second Grade",            2),
    3: ("Jōyō Kanji",     "Third Grade",             3),
    4: ("Jōyō Kanji",     "Fourth Grade",            4),
    5: ("Jōyō Kanji",     "Fifth Grade",             5),
    6: ("Jōyō Kanji",     "Sixth Grade",             6),
    8: ("Jōyō Kanji",     "Secondary School",        7),
    9: ("Jinmeiyō Kanji", "Jinmeiyō Kanji",          1),
   10: ("Jinmeiyō Kanji", "Jinmeiyō Variant Forms",  2),
}


# ---------------------------------------------------------------------------
# Download / decompress
# ---------------------------------------------------------------------------

def get_kanjidic2_xml() -> Path:
    """Return path to kanjidic2.xml, downloading and decompressing if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gz_path = CACHE_DIR / "kanjidic2.xml.gz"
    xml_path = CACHE_DIR / "kanjidic2.xml"

    if not gz_path.exists():
        print(f"Downloading {KD2_URL} ...")
        urllib.request.urlretrieve(KD2_URL, gz_path)
    else:
        print(f"Using cached {gz_path}")

    print("Decompressing ...")
    with gzip.open(gz_path, "rb") as gz, open(xml_path, "wb") as out:
        out.write(gz.read())

    return xml_path


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def parse_kanjidic2(xml_path: Path) -> dict[int, list[int]]:
    """Parse KANJIDIC2 XML → {grade: [codepoint, ...]} for grades in GRADE_MAP."""
    print(f"Parsing {xml_path} ...")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    by_grade: dict[int, list[int]] = {g: [] for g in GRADE_MAP}

    for char_elem in root.findall("character"):
        literal = char_elem.findtext("literal", "")
        if not literal or len(literal) != 1:
            continue
        misc = char_elem.find("misc")
        if misc is None:
            continue
        grade_text = misc.findtext("grade")
        if grade_text is None:
            continue
        try:
            grade = int(grade_text)
        except ValueError:
            continue
        if grade not in GRADE_MAP:
            continue
        by_grade[grade].append(ord(literal))

    for grade, cps in by_grade.items():
        print(f"  Grade {grade:>2}: {len(cps):,} characters")

    return by_grade


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _delete_subtree(cur: sqlite3.Cursor, node_id: int) -> None:
    """Delete a node, all its descendants, and their members."""
    all_ids = [node_id]
    queue = [node_id]
    while queue:
        placeholders = ",".join("?" * len(queue))
        children = cur.execute(
            f"SELECT id FROM character_set_nodes WHERE parent_id IN ({placeholders})",
            queue,
        ).fetchall()
        queue = [row[0] for row in children]
        all_ids.extend(queue)

    placeholders = ",".join("?" * len(all_ids))
    cur.execute(f"DELETE FROM character_set_members WHERE node_id IN ({placeholders})", all_ids)
    cur.execute(f"DELETE FROM character_set_nodes   WHERE id      IN ({placeholders})", all_ids)


def import_sets(
    cur: sqlite3.Cursor,
    by_grade: dict[int, list[int]],
    known_cps: set[int],
    *,
    force: bool,
) -> None:
    """Insert character_set_nodes and character_set_members for all grades."""

    # Collect the distinct set names in the order they first appear
    set_names: list[str] = []
    for grade in sorted(GRADE_MAP):
        name = GRADE_MAP[grade][0]
        if name not in set_names:
            set_names.append(name)

    # Build or reuse root nodes
    root_ids: dict[str, int] = {}
    for set_name in set_names:
        existing = cur.execute(
            "SELECT id FROM character_set_nodes WHERE name = ? AND parent_id IS NULL",
            (set_name,),
        ).fetchone()

        if existing:
            if not force:
                print(f"  '{set_name}' already exists — skipping (use --force to overwrite)")
                root_ids[set_name] = -1  # sentinel: skip this set
                continue
            _delete_subtree(cur, existing[0])
            print(f"  Deleted existing '{set_name}' subtree")

        cur.execute(
            "INSERT INTO character_set_nodes (parent_id, name, sort_order) VALUES (NULL, ?, ?)",
            (set_name, set_names.index(set_name) + 1),
        )
        root_ids[set_name] = cur.lastrowid
        print(f"  Created root node '{set_name}' (id={cur.lastrowid})")

    # Insert level nodes and members
    skipped_chars = 0
    for grade in sorted(GRADE_MAP):
        set_name, level_name, level_order = GRADE_MAP[grade]
        root_id = root_ids.get(set_name)
        if root_id == -1:
            continue  # set was skipped

        cur.execute(
            "INSERT INTO character_set_nodes (parent_id, name, sort_order) VALUES (?, ?, ?)",
            (root_id, level_name, level_order),
        )
        level_id = cur.lastrowid

        codepoints = by_grade[grade]
        for sort_order, cp in enumerate(codepoints, start=1):
            if cp not in known_cps:
                print(f"  Warning: U+{cp:04X} not in characters table — skipping")
                skipped_chars += 1
                continue
            cur.execute(
                "INSERT OR IGNORE INTO character_set_members (node_id, codepoint, sort_order) "
                "VALUES (?, ?, ?)",
                (level_id, cp, sort_order),
            )

        print(f"  {set_name} / {level_name}: {len(codepoints):,} characters")

    if skipped_chars:
        print(f"\n  Warning: {skipped_chars} characters skipped (not in characters table)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import character sets into omni-hanzi DB from KANJIDIC2."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Use cached kanjidic2.xml.gz without re-downloading",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite sets that already exist in the database",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found at {args.db}")
        print("Run  python scripts/create_db.py  first.")
        sys.exit(1)

    # Step 1: get XML
    if not args.skip_download:
        xml_path = get_kanjidic2_xml()
    else:
        xml_path = CACHE_DIR / "kanjidic2.xml"
        if not xml_path.exists():
            gz_path = CACHE_DIR / "kanjidic2.xml.gz"
            if gz_path.exists():
                print(f"Decompressing cached {gz_path} ...")
                with gzip.open(gz_path, "rb") as gz, open(xml_path, "wb") as out:
                    out.write(gz.read())
            else:
                print(f"No cached file found — run without --skip-download.")
                sys.exit(1)
        else:
            print(f"Using cached {xml_path}")

    # Step 2: parse
    print("\nParsing KANJIDIC2 ...")
    by_grade = parse_kanjidic2(xml_path)

    # Step 3: import
    print("\nImporting into database ...")
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    cur = con.cursor()

    cur.execute("SELECT codepoint FROM characters")
    known_cps: set[int] = {row[0] for row in cur.fetchall()}
    print(f"Known characters in DB: {len(known_cps):,}\n")

    try:
        cur.execute("BEGIN")
        import_sets(cur, by_grade, known_cps, force=args.force)
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
    (nodes,) = con.execute("SELECT count(*) FROM character_set_nodes").fetchone()
    (members,) = con.execute("SELECT count(*) FROM character_set_members").fetchone()
    con.close()
    print(f"\n  character_set_nodes:   {nodes:,}")
    print(f"  character_set_members: {members:,}")
    print("\nDone.")


if __name__ == "__main__":
    main()
