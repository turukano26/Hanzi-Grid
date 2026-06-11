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
so A~B and B~C collapse A, B and C together.

Japanese kana/romaji bridge
---------------------------
The generic rule above leaves one big duplicate class untouched: Japanese
readings. Unihan writes each on/kun reading as UPPERCASE romaji (transcription
system 30, Hepburn) while Kanjidic2 writes the *same* pronunciation as kana
(system 32). Because the systems differ, the two rows never share a
(ts, value) pair, so Japanese has zero cross-source merges -- 'SEI'@30 and
'セイ'@32 look unrelated. A second pass bridges them: within the same
(etymology, kind, category, subcategory) it converts each kana value to
marker-stripped romaji (`_kana_to_romaji`) and matches it against the
lowercased Hepburn value. On a match the kana row is kept as the canonical
survivor (it is lossless -- it carries okurigana '.', affix '-' and the
hiragana/katakana distinction that the stripped uppercase romaji discards),
Unihan's attestation is moved onto it, and the lossy romaji row is dropped
(Hepburn is re-derivable from kana at render time). category/subcategory stay
in the key so an on-reading is never merged with a kun-reading that happens to
romanise the same. Unihan-only readings with no kana twin have nothing to
convert from, so they are left as-is (their system-30 value survives).

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

# Shared kana→Hepburn converter (single home in romaji.py, also used by app.py).
sys.path.insert(0, str(ROOT))
from romaji import _kana_to_romaji  # noqa: E402

# Japanese reading systems involved in the kana/romaji bridge (see module docstring).
LANG_TOKYO = 10
TS_HEPBURN = 30
TS_KANA = 32




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


def _ja_bridge_key(ts: int, value: str) -> str:
    """Normalised, marker-stripped romaji used to equate a kana row with its
    Unihan Hepburn twin. Returns '' for systems outside the bridge."""
    norm = _norm(value)
    if ts == TS_KANA:
        rom = _kana_to_romaji(norm)
    elif ts == TS_HEPBURN:
        rom = norm.lower()
    else:
        return ""
    return rom.replace(".", "").replace("-", "")


def _absorb_hepburn(cur: sqlite3.Cursor, survivor: int, dup: int) -> None:
    """Fold a Unihan Hepburn reading (`dup`) into its canonical kana twin
    (`survivor`): keep the kana, move attestations/senses, drop the lossy
    uppercase-romaji transcription rather than copying it (Hepburn is derivable
    from kana)."""
    cur.execute(
        "INSERT OR IGNORE INTO reading_attestations (reading_id, source_id, notes) "
        "SELECT ?, source_id, notes FROM reading_attestations WHERE reading_id = ?",
        (survivor, dup),
    )
    cur.execute("DELETE FROM reading_attestations WHERE reading_id = ?", (dup,))
    # Unihan Japanese readings normally carry no senses, but re-point any to be safe.
    cur.execute("UPDATE senses SET reading_id = ? WHERE reading_id = ?", (survivor, dup))
    cur.execute(
        "UPDATE readings SET features = COALESCE(features, "
        "(SELECT features FROM readings WHERE id = ?)) WHERE id = ? AND features IS NULL",
        (dup, survivor),
    )
    cur.execute("DELETE FROM reading_transcriptions WHERE reading_id = ?", (dup,))
    cur.execute("DELETE FROM readings WHERE id = ?", (dup,))


def merge_japanese_romaji(cur: sqlite3.Cursor) -> int:
    """Bridge Unihan Hepburn (ts 30) readings onto their Kanjidic2 kana (ts 32)
    twins. Returns the number of readings merged away. Run after the generic
    merge so it bridges already-collapsed survivors."""
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
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        WHERE e.language_id = ? AND rt.transcription_system_id IN (?, ?)
        """,
        (LANG_TOKYO, TS_KANA, TS_HEPBURN),
    )

    # (etym, kind, cat, sub) -> (kana_by_bridge, hepburn_rows)
    # kana_by_bridge: {bridge -> lowest kana reading id}; distinct kana that share
    #   a romaji (e.g. じ/ぢ both 'ji') keep separate rows -- only one becomes the
    #   merge target, the other is left untouched.
    groups: dict[tuple, tuple[dict[str, int], list[tuple[str, int]]]] = defaultdict(
        lambda: ({}, [])
    )
    for rid, etym, kind, cat, sub, ts, value in cur.fetchall():
        bridge = _ja_bridge_key(ts, value)
        if not bridge:
            continue
        kana_by_bridge, hepburn_rows = groups[(etym, kind, cat, sub)]
        if ts == TS_KANA:
            if bridge not in kana_by_bridge or rid < kana_by_bridge[bridge]:
                kana_by_bridge[bridge] = rid
        else:
            hepburn_rows.append((bridge, rid))

    merged = 0
    for kana_by_bridge, hepburn_rows in groups.values():
        for bridge, hep_id in hepburn_rows:
            survivor = kana_by_bridge.get(bridge)
            if survivor is None:
                continue  # orphan Hepburn: no kana twin, leave it as ts-30
            _absorb_hepburn(cur, survivor, hep_id)
            merged += 1
    return merged


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
        ja_merged = merge_japanese_romaji(cur)
        removed_senses = dedup_senses(cur)
        con.commit()
    except Exception:
        con.rollback()
        raise

    after = cur.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    con.close()

    print(
        f"Readings: {before:,} -> {after:,} "
        f"({merged_readings:,} merged into {len(components):,} survivors, "
        f"{ja_merged:,} Japanese Hepburn rows bridged onto kana); "
        f"{removed_senses:,} duplicate senses removed."
    )


if __name__ == "__main__":
    main()
