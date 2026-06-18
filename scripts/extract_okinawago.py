#!/usr/bin/env python3
"""
Extract single-character Okinawan (Shuri-Naha) readings from NINJAL's
"沖縄語辞典 データ集" (Okinawago Jiten Data Collection).

Source: https://mmsrv.ninjal.ac.jp/okinawago/  (CC BY 4.0)
  Digitised text of NINJAL's 1963 reference dictionary 『沖縄語辞典』
  (revised 2001). Three XLSX files are published:

    okinawa_01.xlsx  main dictionary  (Okinawan -> Japanese, ~14.5k entries).
                     Headwords are in NINJAL phonetic romanisation, not kanji,
                     so this file carries NO character mapping.
    okinawa_02.xlsx  index            (Japanese -> Okinawan, ~10.2k rows).
                     THE one file with a kanji column. Columns:
                       辞書ページ | 見出し(JP kana) | 見出しの漢字(〔…〕)
                       | 見出しの説明 | 内容(Okinawan forms)
    okinawa_03.xlsx  appendix         (place names / admin divisions). Unused.

This script reads okinawa_02.xlsx and keeps only the rows whose kanji field is
exactly ONE Han character (~1k of ~10k). For each it parses the 内容 cell into
clean Okinawan reading tokens and groups the results by codepoint.

What the readings ARE: the Okinawan word for the Japanese kana headword, i.e. a
native/kun-type reading reached via the Japanese gloss — NOT a syllable-level
Sino-Okinawan on-reading. Notation is NINJAL romanisation (? = glottal stop,
j = y, N = moraic nasal, Q = gemination, doubled vowels = length, ' = glottal
onset), left verbatim.

内容 parsing: the cell packs variants (，-separated), example phrases and
sub-senses (/-separated), Japanese fragments, and cross-references (→…). We take
the segment before the first '/', split it on '，', drop any '→…' cross-ref
token, and keep tokens that are pure NINJAL romanisation ([?'A-Za-z]+).

This is an EXTRACTOR, not a DB importer: it writes JSON to data/ for review.
Wiring the readings into the schema (a Ryukyuan/Okinawan language + transcription
system, attributed to NINJAL under CC BY 4.0) is a separate step.

Usage:
    python scripts/extract_okinawago.py
    python scripts/extract_okinawago.py --skip-download
    python scripts/extract_okinawago.py --out data/okinawago_readings.json
"""

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "okinawago"
DEFAULT_OUT = ROOT / "data" / "okinawago_readings.json"

INDEX_FILE = "okinawa_02.xlsx"
SOURCE_URL = "https://mmsrv.ninjal.ac.jp/okinawago/" + INDEX_FILE
ATTRIBUTION = (
    "NINJAL 『沖縄語辞典 データ集』 (https://mmsrv.ninjal.ac.jp/okinawago/), "
    "CC BY 4.0"
)

# A clean Okinawan reading in NINJAL romanisation: ?, ', ASCII letters only.
_READING_RE = re.compile(r"^[?'A-Za-z]+$")


def _is_han(ch: str) -> bool:
    try:
        return "CJK" in unicodedata.name(ch)
    except ValueError:
        return False


def _single_han(kanji_cell) -> str | None:
    """Return the lone Han char of a 見出しの漢字 cell, or None if not exactly one."""
    if not kanji_cell:
        return None
    core = re.sub(r"[〔〕\s]", "", str(kanji_cell))
    return core if len(core) == 1 and _is_han(core) else None


def _parse_readings(content) -> list[str]:
    """Pull clean Okinawan reading tokens out of an 内容 cell (order-preserving)."""
    if not content:
        return []
    first_segment = str(content).split("/", 1)[0]
    out: list[str] = []
    for tok in first_segment.split("，"):
        tok = tok.strip()
        if not tok or "→" in tok:
            continue
        if _READING_RE.match(tok) and tok not in out:
            out.append(tok)
    return out


def download_index(skip_download: bool) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / INDEX_FILE
    if path.exists() and skip_download:
        return path
    if path.exists() and not skip_download:
        return path  # already cached; the source is a static release
    print(f"Downloading {SOURCE_URL} -> {path}")
    urllib.request.urlretrieve(SOURCE_URL, path)
    return path


def extract(index_path: Path) -> dict:
    try:
        import openpyxl
    except ImportError:
        sys.exit("openpyxl is required: pip install openpyxl")

    wb = openpyxl.load_workbook(index_path, read_only=True)
    ws = wb.active

    by_codepoint: dict[str, dict] = {}
    rows_total = rows_single_han = rows_with_readings = 0

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:  # header
            continue
        cells = (row + (None,) * 5)[:5]
        _page, head, kanji, expl, content = cells
        rows_total += 1

        char = _single_han(kanji)
        if char is None:
            continue
        rows_single_han += 1

        readings = _parse_readings(content)
        if not readings:
            continue
        rows_with_readings += 1

        cp = f"{ord(char):x}"
        entry = by_codepoint.setdefault(
            cp, {"codepoint": cp, "char": char, "readings": [], "senses": []}
        )
        for r in readings:
            if r not in entry["readings"]:
                entry["readings"].append(r)
        entry["senses"].append(
            {
                "jp": head,
                "gloss": expl,
                "raw": content,
            }
        )

    entries = sorted(by_codepoint.values(), key=lambda e: int(e["codepoint"], 16))
    return {
        "source": ATTRIBUTION,
        "license": "CC BY 4.0",
        "note": (
            "Single Han character -> Okinawan (Shuri-Naha) native/kun-type "
            "readings in NINJAL romanisation, extracted from the index file's "
            "見出しの漢字 / 内容 columns. See scripts/extract_okinawago.py."
        ),
        "stats": {
            "index_rows": rows_total,
            "single_han_rows": rows_single_han,
            "single_han_rows_with_readings": rows_with_readings,
            "codepoints": len(entries),
        },
        "entries": entries,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--skip-download",
        action="store_true",
        help="reuse the cached data/okinawago/okinawa_02.xlsx instead of fetching",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output JSON path (default: {DEFAULT_OUT.relative_to(ROOT)})",
    )
    args = ap.parse_args()

    index_path = download_index(args.skip_download)
    result = extract(index_path)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    s = result["stats"]
    print(f"index rows:                 {s['index_rows']}")
    print(f"single-Han-char rows:       {s['single_han_rows']}")
    print(f"  ...with usable readings:  {s['single_han_rows_with_readings']}")
    print(f"distinct codepoints:        {s['codepoints']}")
    print(f"wrote {args.out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
