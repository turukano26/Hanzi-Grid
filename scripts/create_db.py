#!/usr/bin/env python3
"""Create (or recreate) the omni-hanzi SQLite database from schema.sql."""

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "omnihanzi.db"
SCHEMA = ROOT / "schema.sql"


def main():
    parser = argparse.ArgumentParser(description="Create the omni-hanzi database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    parser.add_argument("--force", action="store_true", help="Overwrite without prompting")
    args = parser.parse_args()

    if args.db.exists():
        if not args.force:
            resp = input(f"{args.db} already exists. Drop and recreate? [y/N] ")
            if resp.lower() != "y":
                print("Aborted.")
                sys.exit(1)
        args.db.unlink()

    print(f"Creating database at {args.db} ...")
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
