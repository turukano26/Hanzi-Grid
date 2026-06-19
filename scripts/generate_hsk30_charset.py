#!/usr/bin/env python3
"""Generate charactersets/HSK 3.0.yaml from data/hsk30/hsk30-chars.csv.

Source: ivankra/hsk30 `hsk30-chars.csv` (3000 chars; columns Hanzi, Level,
WritingLevel, Traditional, Freq, Examples). `Hanzi` is the simplified form,
`Traditional` is `/`-separated traditional variants (possibly empty).

Output is a v2 character set in the same shape as the hand-authored sets in
charactersets/: one `section` per HSK level (1-6 and a combined 7-9), each with a
single `grid`. Cells use the Traditional/Simplified variant syntax `{<trad>T<simp>S}`
read by static/script.js's parseCells; characters identical across scripts are
written bare. No Japanese (J) variant is emitted -- simp/trad only.

Per-character traditional form is chosen as:
  1. an explicit OVERRIDE, where the dataset's first-listed variant is a rare/bound
     form and a more representative one exists (see OVERRIDES);
  2. a GAP_FILL, for rows whose Traditional is blank but which do change in
     traditional (surname/place chars the dataset omitted);
  3. otherwise the first `/`-separated variant (the dataset's primary), or the
     simplified char itself when Traditional is blank/unchanged.
The remaining `/`-separated variants are dropped: a cell shows one trad glyph.
"""

import csv
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSV_PATH = os.path.join(ROOT, 'data', 'hsk30', 'hsk30-chars.csv')
OUT_PATH = os.path.join(ROOT, 'charactersets', 'HSK 3.0.yaml')


# Render multi-line strings (e.g. the intro paragraph) as literal block scalars
# (|) for readability; never line-wrap so long `cells` strings stay on one line.
def _str_representer(dumper, data):
    style = '|' if '\n' in data else None
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style=style)


class _YamlDumper(yaml.SafeDumper):
    pass


_YamlDumper.add_representer(str, _str_representer)

# The first-listed variant is a rare/bound form; use a representative one instead.
# (恶/佛/卜/铲 high-confidence; 迹/伙 borderline, included per request.)
OVERRIDES = {
    '恶': '惡',  # 噁 only in 噁心 (nausea)
    '佛': '佛',  # 彿 only in 仿彿; 佛 = Buddha (-> bare)
    '卜': '卜',  # 蔔 only in 蘿蔔; 卜 = divination/surname (-> bare)
    '铲': '鏟',  # 鏟 is the standard form for shovel
    '迹': '跡',  # 跡 more standard (痕跡, 跡象) than 蹟 (古蹟)
    '伙': '伙',  # 伙 (伙伴/伙食) more basic than 夥 (-> bare)
}

# Rows whose Traditional is blank in the source but which do have a distinct
# traditional form (all level 7-9 surname/place chars).
GAP_FILLS = {
    '邓': '鄧', '冯': '馮', '韩': '韓', '沪': '滬', '刘': '劉',
    '吕': '呂', '欧': '歐', '吴': '吳', '粤': '粵', '赵': '趙',
}

# HSK levels in order; the source lumps 7-9 into one bucket.
LEVELS = ['1', '2', '3', '4', '5', '6', '7-9']

INTRO = (
    "Vocabulary characters from HSK 3.0 (the 2021 Chinese Proficiency Standards), "
    "3000 characters graded across levels 1–9 (levels 7–9 are a single "
    "advanced band).\n"
    "Use the 繁 / 簡 switch by the set dropdown to show Traditional or "
    "Simplified forms."
)


def traditional_for(simp, trad_field):
    """Pick the single traditional glyph to display for one row."""
    if simp in OVERRIDES:
        return OVERRIDES[simp]
    if simp in GAP_FILLS:
        return GAP_FILLS[simp]
    trad_field = trad_field.strip()
    if not trad_field:
        return simp  # no traditional given and not a known gap: unchanged
    return trad_field.split('/')[0]  # dataset's primary variant


def cell_for(simp, trad):
    """Bare char when identical across scripts, else a {trad T simp S} group."""
    if trad == simp:
        return simp
    return '{%sT%sS}' % (trad, simp)


def build():
    # Within each level, collect (Freq, cell). `Freq` is a frequency count
    # (higher = more common); the source's blank-free 0..207 range needs no
    # cleaning. Sorted descending below so common characters lead each level.
    by_level = {lvl: [] for lvl in LEVELS}
    with open(CSV_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            simp = row['Hanzi']
            level = row['Level']
            trad = traditional_for(simp, row['Traditional'])
            by_level[level].append((int(row['Freq']), cell_for(simp, trad)))

    blocks = [{'type': 'text', 'text': INTRO, 'size': 4}]
    for lvl in LEVELS:
        title = 'Level %s' % lvl.replace('7-9', '7–9')
        # Stable sort by descending frequency: ties keep the source's order.
        cells = sorted(by_level[lvl], key=lambda fc: -fc[0])
        blocks.append({
            'type': 'section',
            'id': 'level-%s' % lvl,
            'title': title,
            'collapsed': False,
            'blocks': [{'type': 'grid', 'cells': ''.join(c for _, c in cells)}],
        })

    return {'version': 2, 'label': 'HSK 3.0', 'blocks': blocks}


def main():
    doc = build()
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(doc, f, Dumper=_YamlDumper, allow_unicode=True,
                  sort_keys=False, width=10**9, indent=2)
    counts = {b['id']: len(b['blocks'][0]['cells']) for b in doc['blocks'] if b['type'] == 'section'}
    print('wrote', OUT_PATH)
    for k, v in counts.items():
        print('  %-10s cells string len %d' % (k, v))


if __name__ == '__main__':
    main()
