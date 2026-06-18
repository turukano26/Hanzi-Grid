#!/usr/bin/env python3
"""
Build the rare-CJK web-font subsets served by the app.

Some character sets (e.g. "Rivers of China") include ideographs from the
Unicode supplementary planes — CJK Extension B and beyond (codepoints
>= U+20000). No operating system ships a default font with glyphs for these, so
in the browser they show up blank / as tofu.  We fill that gap with the
Plangothic font (a Source-Han-shaped sans whose whole reason for existing is to
cover the CJK extension blocks), but two things make us *subset* it rather than
ship it whole:

  1. The full files are ~12 MB each.
  2. The full Plangothic cmap contains an invalid format-12 group (codepoints
     0x110000-0x110002, past Unicode's U+10FFFF maximum) mapped to glyph 0.
     Chrome runs every web font through OTS (the OpenType Sanitiser), which
     rejects that cmap and therefore the whole font, so the extension glyphs
     render blank.  Subsetting rebuilds the cmap from only the kept codepoints,
     dropping the junk group, so OTS accepts the result — and it's a few dozen
     KB.  (Confirmed via `ots-sanitize`; FreeType tolerates the bad group, which
     is why the glyphs rasterise fine outside the browser.)

Plangothic ships its coverage in two files that span DISJOINT planes, so the
output is two subsets, each wired up in static/styles.css with the unicode-range
it covers:

  * plangothic-sip-1.woff2  — Ext B–F + Ext I + Compat-Supplement (U+20000-2FFFF)
  * plangothic-sip-2.woff2  — Ext G–H                              (U+30000-3FFFF)

Plangothic deliberately has no Ext A (U+3400-4DBF) glyphs — that BMP block is
already covered by every system CJK font (Source Han / Noto / YaHei / PingFang)
— so Ext A is left to the system font and is not subset here.

Re-run this whenever a character set gains a new supplementary-plane character;
it scans every charactersets/*.yaml, so the subsets always match the corpus.

Usage:
    python scripts/build_ext_font_subset.py                 # download Plangothic fresh
    python scripts/build_ext_font_subset.py --skip-download  # reuse cached data/plangothic/

Requires fonttools[woff2] (fontTools + brotli), already used elsewhere in dev.
"""

import argparse
import glob
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CHARSET_DIR = ROOT / "charactersets"
FONT_DIR = ROOT / "static" / "fonts"
CACHE_DIR = ROOT / "data" / "plangothic"

# Plangothic "Static edition" zip ships the two standalone TTFs we subset from.
PLANGOTHIC_VERSION = "V2.9.5792"
RELEASE_BASE = (
    "https://github.com/Fitzgerald-Porthmouth-Koenigsegg/Plangothic_Project"
    f"/releases/download/{PLANGOTHIC_VERSION}"
)
SOURCE_FILES = {
    "PlangothicP1-Regular.ttf": f"{RELEASE_BASE}/PlangothicP1-Regular.ttf",
    "PlangothicP2-Regular.ttf": f"{RELEASE_BASE}/PlangothicP2-Regular.ttf",
}

# Which output file each source covers, and the plane split between them. P1
# holds everything below U+30000, P2 holds U+30000 and up.
OUTPUTS = [
    {"src": "PlangothicP1-Regular.ttf", "out": "plangothic-sip-1.woff2",
     "lo": 0x20000, "hi": 0x2FFFF},
    {"src": "PlangothicP2-Regular.ttf", "out": "plangothic-sip-2.woff2",
     "lo": 0x30000, "hi": 0x3FFFF},
]


def collect_sip_codepoints():
    """Every supplementary-plane (>= U+20000) codepoint used anywhere in the
    character-set YAML files."""
    cps = set()

    def walk(o):
        if isinstance(o, str):
            for ch in o:
                if ord(ch) >= 0x20000:
                    cps.add(ord(ch))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for fn in sorted(glob.glob(str(CHARSET_DIR / "*.yaml"))):
        with open(fn, encoding="utf-8") as fh:
            walk(yaml.safe_load(fh))
    return cps


def download_sources(skip_download):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCE_FILES.items():
        dest = CACHE_DIR / name
        if dest.exists() and skip_download:
            continue
        if dest.exists() and not skip_download:
            continue  # already cached; the TTFs are versioned/immutable
        print(f"downloading {name} ...")
        urllib.request.urlretrieve(url, dest)
    missing = [n for n in SOURCE_FILES if not (CACHE_DIR / n).exists()]
    if missing:
        sys.exit(f"missing source font(s) {missing}; run without --skip-download")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-download", action="store_true",
                    help="reuse cached fonts in data/plangothic/ instead of downloading")
    args = ap.parse_args()

    try:
        from fontTools.ttLib import TTFont
        from fontTools.subset import Subsetter, Options
    except ImportError:
        sys.exit("fonttools is required: pip install 'fonttools[woff2]'")

    download_sources(args.skip_download)

    sip = collect_sip_codepoints()
    print(f"{len(sip)} supplementary-plane codepoints across {CHARSET_DIR.name}/")
    FONT_DIR.mkdir(parents=True, exist_ok=True)

    covered = set()
    for spec in OUTPUTS:
        font = TTFont(CACHE_DIR / spec["src"])
        have = set(font.getBestCmap())
        want = sorted(c for c in sip
                      if spec["lo"] <= c <= spec["hi"] and c in have)
        covered |= set(want)

        opts = Options()
        opts.flavor = "woff2"
        opts.desubroutinize = True
        sub = Subsetter(options=opts)
        sub.populate(unicodes=want)
        sub.subset(font)
        out = FONT_DIR / spec["out"]
        font.flavor = "woff2"
        font.save(out)
        print(f"  {spec['out']}: {len(want)} glyphs, {out.stat().st_size // 1024 or 1} KB")

    missing = sorted(sip - covered)
    if missing:
        print("WARNING: not covered by Plangothic (left to the system font):",
              " ".join(f"{chr(c)}(U+{c:X})" for c in missing))


if __name__ == "__main__":
    main()
