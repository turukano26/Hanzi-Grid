"""Tests for transcriptions/quocngu_ipa.py — Vietnamese Quốc Ngữ → broad IPA,
per dialect (Northern / Central / Southern), phonemes-only and with-tones.

The module is a direct port of vPhon (github.com/kirbyj/vPhon); these expected
values were checked syllable-for-syllable against vPhon's own output (run with
`-c`, i.e. Chao tones, superscript defaults) across its full sample wordlist,
with vPhon's superscript pitch digits rewritten as the tone letters this repo
uses. The cases below pick syllables that exercise the dialect contrasts:
Northern *tr* [tɕ] vs Central/Southern [ʈ], the Northern rising diphthongs
/iə uə/ that surface as long monophthongs [iː uː] in the South, the
palatalised vs coronal codas after front vowels, and the per-dialect tones.
The with-tones expected values are the phonemes-only ones plus a trailing Chao
tone letter, so the two tables also pin down that `…_tones` differs from the
bare variant only by the appended tone."""

import unittest

from transcriptions.quocngu_ipa import (
    quocngu_to_ipa_northern, quocngu_to_ipa_central, quocngu_to_ipa_southern,
    quocngu_to_ipa_northern_tones, quocngu_to_ipa_central_tones,
    quocngu_to_ipa_southern_tones,
)

# src -> (Northern, Central, Southern), phonemes only
PHONEMES = {
    'nhất': ('ɲət', 'ɲək', 'ɲək'),          # final -t → -k in C/S
    'trung': ('tɕuŋ͡m', 'ʈuŋ͡m', 'ʈuŋ͡m'),     # tr: N tɕ vs C/S ʈ; labiodorsal coda
    'quốc': ('kʷoːk', 'wɔk͡p', 'wɔk͡p'),       # qu: N kʷ vs C/S w
    'việt': ('viət', 'viːk', 'viːk'),         # iə diphthong N vs iː monophthong C/S
    'nam': ('naːm', 'naːm', 'naːm'),
    'giày': ('zaj', 'jaj', 'jaj'),            # gi: N z vs C/S j
    'hoa': ('hʷaː', 'hʷaː', 'hʷaː'),          # onglide labialises the onset
    'uống': ('ʔuəŋ', 'ʔuːŋ', 'ʔuːŋ'),        # onsetless → ʔ
    'bạn': ('ɓaːn', 'ɓaːŋ', 'ɓaːŋ'),         # -n → -ŋ after long vowel in C/S
    'yêu': ('ʔiəw', 'ʔiːw', 'ʔiːw'),
    'anh': ('ʔaʲŋ', 'ʔan', 'ʔan'),            # palatalised velar coda (N) vs coronal
    'sách': ('saʲk', 'sat', 'sat'),
    'xin': ('siːn', 'sɨn', 'sɨn'),            # x/s merge to s; pre-coronal i→ɨ in C/S
}

# src -> (Northern, Central, Southern), with a Chao tone letter per syllable
TONES = {
    'nhất': ('ɲət˦˥', 'ɲək˦˥', 'ɲək˦˥'),
    'trung': ('tɕuŋ͡m˧˧', 'ʈuŋ͡m˧˥', 'ʈuŋ͡m˧˧'),
    'quốc': ('kʷoːk˦˥', 'wɔk͡p˦˥', 'wɔk͡p˦˥'),
    'việt': ('viət˨˩', 'viːk˧˩', 'viːk˨˩˨'),
    'nam': ('naːm˧˧', 'naːm˧˥', 'naːm˧˧'),
    'giày': ('zaj˧˨', 'jaj˦˨', 'jaj˨˩'),
    'hoa': ('hʷaː˧˧', 'hʷaː˧˥', 'hʷaː˧˧'),
    'uống': ('ʔuəŋ˨˦', 'ʔuːŋ˨ˀ˦', 'ʔuːŋ˦˥'),
    'bạn': ('ɓaːn˨˩ˀ', 'ɓaːŋ˧˩', 'ɓaːŋ˨˩˨'),
    'yêu': ('ʔiəw˧˧', 'ʔiːw˧˥', 'ʔiːw˧˧'),
    'anh': ('ʔaʲŋ˧˧', 'ʔan˧˥', 'ʔan˧˧'),
    'sách': ('saʲk˦˥', 'sat˦˥', 'sat˦˥'),
    'xin': ('siːn˧˧', 'sɨn˧˥', 'sɨn˧˧'),
}

_PHONEMES_FNS = (quocngu_to_ipa_northern, quocngu_to_ipa_central,
                 quocngu_to_ipa_southern)
_TONES_FNS = (quocngu_to_ipa_northern_tones, quocngu_to_ipa_central_tones,
              quocngu_to_ipa_southern_tones)


class TestQuocNguIpa(unittest.TestCase):
    def test_phonemes(self):
        for src, expected in PHONEMES.items():
            for fn, exp in zip(_PHONEMES_FNS, expected):
                with self.subTest(src=src, fn=fn.__name__):
                    self.assertEqual(fn(src), exp)

    def test_with_tones(self):
        for src, expected in TONES.items():
            for fn, exp in zip(_TONES_FNS, expected):
                with self.subTest(src=src, fn=fn.__name__):
                    self.assertEqual(fn(src), exp)

    def test_multisyllable_joined_with_space(self):
        self.assertEqual(quocngu_to_ipa_northern('việt nam'), 'viət naːm')
        self.assertEqual(quocngu_to_ipa_northern_tones('việt nam'),
                         'viət˨˩ naːm˧˧')

    def test_case_and_nfd_input(self):
        # Uppercase and NFD (decomposed) input normalise to the same result.
        import unicodedata
        self.assertEqual(quocngu_to_ipa_northern_tones('NHẤT'), 'ɲət˦˥')
        self.assertEqual(
            quocngu_to_ipa_northern_tones(unicodedata.normalize('NFD', 'nhất')),
            'ɲət˦˥')

    def test_unrecognised_passthrough(self):
        self.assertEqual(quocngu_to_ipa_northern('xyz'), 'xyz')
        self.assertEqual(quocngu_to_ipa_northern_tones('xyz'), 'xyz')
        self.assertEqual(quocngu_to_ipa_northern(''), '')


if __name__ == '__main__':
    unittest.main()
