"""End-to-end test of the info-sheet resolution chain through the real app.

Unlike the per-converter tests (which call the transcription functions directly),
this drives the whole server-side path for a single character click:

    build_sections() → _iter_groups(TREE) → _handler_readings()
        → _fetch_reading_rows() → _resolve_ts_value() → TRANSFORMS[...]

so it verifies the DB wiring: that a Mandarin reading which stores *only* Pīnyīn
fans out to its derived systems (Wade-Giles, Zhùyīn, IPA) via the
`transcription_systems.derived_from_ts_id` / `transform` metadata and the
`TRANSFORMS` registry — the layer the pure-function tests don't touch.

Requires the locally-built `omnihanzi.db` (gitignored); the whole module skips
cleanly when it isn't present, so a fresh checkout / CI without the DB is green.
`import app` is deferred behind that check because importing app builds the menu
tree from the DB at import time.
"""

import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, 'omnihanzi.db')
HAS_DB = os.path.exists(DB_PATH)

if HAS_DB:
    import app  # noqa: E402 — import builds TREE from the DB; guarded by HAS_DB


@unittest.skipUnless(HAS_DB, 'omnihanzi.db not present (gitignored / built locally)')
class TestResolveEndToEnd(unittest.TestCase):
    def _mandarin_section(self, character):
        """build_sections() for `character` with every Mandarin transcription leaf
        enabled, returning the single Mandarin readings section."""
        group = next(g for g in app._iter_groups(app.TREE)
                     if g.get('render', {}).get('title') == 'Mandarin')
        leaf_ids = [leaf['id'] for leaf in app._leaf_descendants(group)
                    if 'ts_id' in leaf]
        sections = app.build_sections(character, leaf_ids)
        mandarin = [s for s in sections if s['title'] == 'Mandarin']
        self.assertEqual(len(mandarin), 1, 'expected exactly one Mandarin section')
        return mandarin[0]

    def test_section_envelope(self):
        section = self._mandarin_section('中')
        # The uniform {id, type, title, data} shape build_sections() emits.
        self.assertEqual(section['type'], 'readings')
        self.assertEqual(section['title'], 'Mandarin')
        self.assertIn('id', section)
        self.assertTrue(section['data']['readings'], 'expected at least one reading')

    def test_pinyin_fans_out_to_derived_systems(self):
        section = self._mandarin_section('中')
        # Flatten every (system code -> value) across all reading rows.
        pairs = {(t['code'], t['value'])
                 for row in section['data']['readings']
                 for t in row['transcriptions']}
        # 中 is zhōng / zhòng. Only Pīnyīn is stored; the rest are derived through
        # the real resolve chain, so finding them here proves the wiring works.
        expected = {
            ('pinyin', 'zhōng'), ('pinyin_num', 'zhong1'),
            ('wade_giles', 'chung¹'), ('zhuyin', 'ㄓㄨㄥ'),
            ('ipa', 'ʈ͡ʂʊŋ'), ('ipa_tones', 'ʈ͡ʂʊŋ˥'),
            ('pinyin', 'zhòng'), ('zhuyin', 'ㄓㄨㄥˋ'),
            ('ipa_tones', 'ʈ͡ʂʊŋ˥˩'),
        }
        self.assertTrue(
            expected <= pairs,
            'missing derived transcriptions: %s' % sorted(expected - pairs))

    def test_disabled_systems_are_absent(self):
        # With only Pīnyīn enabled, the derived systems must not appear — proving
        # the section reflects the enabled-leaf set, not every system.
        sections = app.build_sections('中', ['cmn:pinyin'])
        section = next(s for s in sections if s['title'] == 'Mandarin')
        codes = {t['code']
                 for row in section['data']['readings']
                 for t in row['transcriptions']}
        self.assertEqual(codes, {'pinyin'})


if __name__ == '__main__':
    unittest.main()
