#!/usr/bin/env python3
"""One-time v1 -> v2 conversion for the JSON files in charactersets/.

v1 shape:  {"label": ..., "value": [{"label": ..., "value": "<chars>"}, ...]}
v2 shape:  {"version": 2, "label": ..., "blocks": [
               {"type": "section", "id": ..., "title": ...,
                "blocks": [{"type": "grid", "cells": "<chars>"}]},
               ...]}

Each old inner node becomes one `section` whose single child is a `grid`. Section
ids are slugified titles with a disambiguating counter on collision (and a
generic fallback when the title slugifies to nothing, e.g. all-CJK titles).

v1 detection is by shape: a top-level `value` key present and no `version`. Run
once and commit the converted files; this script (and the v1 files) are deleted
after the new app is tried out.
"""

import json
import os
import re
import sys

CHARSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'charactersets')


def slugify(title):
    """Lowercase ASCII slug; empty when the title has no ASCII alphanumerics
    (e.g. all-CJK), in which case the caller supplies a generic fallback."""
    slug = re.sub(r'[^a-z0-9]+', '-', (title or '').lower()).strip('-')
    return slug


def convert(doc):
    blocks = []
    used = set()
    for i, node in enumerate(doc.get('value', [])):
        title = node.get('label', '')
        base = slugify(title) or 'section'
        sid = base
        n = 1
        while sid in used:
            n += 1
            sid = '%s-%d' % (base, n)
        used.add(sid)
        blocks.append({
            'type': 'section',
            'id': sid,
            'title': title,
            'collapsed': False,  # collapsible, expanded by default
            'blocks': [{'type': 'grid', 'cells': node.get('value', '')}],
        })
    return {'version': 2, 'label': doc.get('label', ''), 'blocks': blocks}


def main(argv):
    paths = argv[1:]
    if not paths:
        paths = [os.path.join(CHARSET_DIR, f) for f in os.listdir(CHARSET_DIR)
                 if f.endswith('.json')]
    for path in paths:
        with open(path, 'r', encoding='utf-8') as fh:
            doc = json.load(fh)
        if doc.get('version') == 2 or 'value' not in doc:
            print('skip (already v2): %s' % path)
            continue
        out = convert(doc)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
        ids = [b['id'] for b in out['blocks']]
        print('converted %s -> %d sections %s' % (os.path.basename(path), len(ids), ids))


if __name__ == '__main__':
    main(sys.argv)
