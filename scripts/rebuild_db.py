#!/usr/bin/env python3
"""
Delete and fully rebuild the omni-hanzi database from scratch.

Runs all import scripts in order:
  1. create_db.py           — create schema
  2. import_unihan.py       — Unihan readings, definitions, variants
  3. import_kanjidic2.py    — Japanese readings, frequency, stroke counts
  4. import_cedict.py       — Mandarin definitions from CC-CEDICT
  5. import_cccanto.py      — Cantonese readings + definitions from CC-Canto
  6. import_libhangul.py    — Korean Hangul readings + eumhun from libhangul

Usage:
    python scripts/rebuild_db.py
    python scripts/rebuild_db.py --skip-downloads   # use cached data files
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_DB = ROOT / "omnihanzi.db"

STEPS = [
    ("Create schema",        ["create_db.py",            "--force"]),
    ("Import Unihan",        ["import_unihan.py",         "--skip-download"]),
    ("Import KANJIDIC2",     ["import_kanjidic2.py",      "--skip-download"]),
    ("Import CC-CEDICT",     ["import_cedict.py",         "--skip-download"]),
    ("Import CC-Canto",      ["import_cccanto.py",        "--skip-download"]),
    ("Import libhangul",     ["import_libhangul.py",      "--skip-download"]),
    ("Dedup readings",       ["dedup_readings.py"]),
]


def run_step(label: str, script_args: list[str], *, download: bool, db: Path) -> None:
    args = [sys.executable, str(SCRIPTS / script_args[0]), "--db", str(db)]

    # Strip --skip-download flags if the user wants fresh downloads,
    # but always keep --force and any other flags.
    for flag in script_args[1:]:
        if flag == "--skip-download" and download:
            continue
        args.append(flag)

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(args)
    if result.returncode != 0:
        print(f"\nStep '{label}' failed (exit {result.returncode}) — aborting.")
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete and rebuild the omni-hanzi database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument(
        "--skip-downloads", action="store_true",
        help="Use cached data files instead of re-downloading",
    )
    args = parser.parse_args()

    # Delete existing DB files (WAL mode creates -shm and -wal sidecar files)
    for suffix in ("", "-shm", "-wal"):
        path = args.db.parent / (args.db.name + suffix)
        if path.exists():
            path.unlink()
            print(f"Deleted {path}")

    for label, script_args in STEPS:
        run_step(label, script_args, download=not args.skip_downloads, db=args.db)

    print(f"\n{'='*60}")
    print("  Rebuild complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
