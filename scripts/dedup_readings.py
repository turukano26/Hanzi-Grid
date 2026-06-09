#!/usr/bin/env python3
"""Post-import pass: merge duplicate reading rows.

The per-source importers each insert readings independently, so the same
pronunciation under one etymology ends up as several reading rows -- one per
source -- that differ only in which source attests them. This pass collapses
those into a single reading carrying all of its sources' attestations,
transcriptions and senses. It is meant to run once, last, after every importer.

Merge rule
----------
Two readings are merged when, within the same
(etymology_id, kind, category, subcategory), they share at least one identical
(transcription_system_id, NFC-normalised value) -- i.e. they spell the same
pronunciation in the same system. Merging is transitive (connected components),
so A~B and B~C collapse A, B and C together. Readings that share no transcription
system (e.g. a Unihan romaji reading vs. a Kanjidic2 kana reading) are left
alone, since equating them would require cross-system conversion.

The pass is idempotent: re-running it on an already-deduped database is a no-op.
"""

import argparse
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "omnihanzi.db"


class DSU:
    """Minimal union-find over reading ids."""

    def __init__(self):
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # path compression
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # keep the lower id as the representative (it becomes the survivor)
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            self.parent[hi] = lo


def _norm(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def build_components(cur: sqlite3.Cursor) -> dict[int, list[int]]:
    """Return {survivor_id: [duplicate_id, ...]} for every reading with >1 member."""
    cur.execute(
        """
        SELECT r.id,
               r.etymology_id,
               r.kind,
               IFNULL(r.category, ''),
               IFNULL(r.subcategory, ''),
               rt.transcription_system_id,
               rt.value
        FROM readings r
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        """
    )

    dsu = DSU()
    # (etymology, kind, category, subcategory, ts, normalised value) -> first reading id
    seen: dict[tuple, int] = {}
    for rid, etym, kind, cat, sub, ts, value in cur.fetchall():
        dsu.find(rid)  # ensure singleton readings are registered too
        key = (etym, kind, cat, sub, ts, _norm(value))
        if key in seen:
            dsu.union(rid, seen[key])
        else:
            seen[key] = rid

    components: dict[int, list[int]] = defaultdict(list)
    for rid in dsu.parent:
        components[dsu.find(rid)].append(rid)

    # Keep only real merges; survivor is the representative (lowest id).
    return {
        survivor: sorted(m for m in members if m != survivor)
        for survivor, members in components.items()
        if len(members) > 1
    }


def merge(cur: sqlite3.Cursor, survivor: int, dups: list[int]) -> None:
    for dup in dups:
        # Attestations: move, ignoring (reading_id, source_id) PK collisions.
        cur.execute(
            "INSERT OR IGNORE INTO reading_attestations (reading_id, source_id, notes) "
            "SELECT ?, source_id, notes FROM reading_attestations WHERE reading_id = ?",
            (survivor, dup),
        )
        cur.execute("DELETE FROM reading_attestations WHERE reading_id = ?", (dup,))

        # Transcriptions: move any system the survivor lacks; UNIQUE(reading_id,
        # transcription_system_id) keeps the survivor's own value on collision.
        cur.execute(
            "INSERT OR IGNORE INTO reading_transcriptions (reading_id, transcription_system_id, value) "
            "SELECT ?, transcription_system_id, value FROM reading_transcriptions WHERE reading_id = ?",
            (survivor, dup),
        )
        cur.execute("DELETE FROM reading_transcriptions WHERE reading_id = ?", (dup,))

        # Senses keep their own source_id; just re-point them at the survivor.
        cur.execute("UPDATE senses SET reading_id = ? WHERE reading_id = ?", (survivor, dup))

        # Preserve a feature flag (e.g. okurigana) if the survivor lacks one.
        cur.execute(
            "UPDATE readings SET features = COALESCE(features, "
            "(SELECT features FROM readings WHERE id = ?)) WHERE id = ? AND features IS NULL",
            (dup, survivor),
        )

        cur.execute("DELETE FROM readings WHERE id = ?", (dup,))


def dedup_senses(cur: sqlite3.Cursor) -> int:
    """Drop senses that became exact (reading, source, definition) duplicates."""
    cur.execute(
        """
        DELETE FROM senses
        WHERE id NOT IN (
            SELECT MIN(id) FROM senses GROUP BY reading_id, source_id, definition
        )
        """
    )
    return cur.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge duplicate reading rows.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Database path")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(args.db)
    cur = con.cursor()

    before = cur.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    components = build_components(cur)
    merged_readings = sum(len(d) for d in components.values())

    try:
        cur.execute("BEGIN")
        for survivor, dups in components.items():
            merge(cur, survivor, dups)
        removed_senses = dedup_senses(cur)
        con.commit()
    except Exception:
        con.rollback()
        raise

    after = cur.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    con.close()

    print(
        f"Readings: {before:,} -> {after:,} "
        f"({merged_readings:,} merged into {len(components):,} survivors); "
        f"{removed_senses:,} duplicate senses removed."
    )


if __name__ == "__main__":
    main()
