"""Tests for transcriptions/jyutping_ipa.py — Cantonese Jyutping → broad IPA.

Expected values follow the module's scheme: finals looked up against a closed
rime table (tabulated vowel length and i/u→ɪ/ʊ allophony), unreleased coda
stops (p̚/t̚/k̚), syllabic nasals, and a Chao tone letter per syllable for the
*_tones variant."""

import unittest

from transcriptions.jyutping_ipa import jyutping_to_ipa, jyutping_to_ipa_tones

IPA = {
    'jat1': 'jɐt̚', 'zung1': 't͡sʊŋ', 'saam1': 'saːm', 'nei5': 'nei̯',
    'hou2': 'hou̯', 'hoeng1': 'hœːŋ', 'gong2': 'kɔːŋ', 'ngo5': 'ŋɔː',
    'm4': 'm̩', 'gwaai1': 'kʷaːi̯', 'haa6': 'haː', 'gwok3': 'kʷɔːk̚',
    'leoi5': 'lɵy̯', 'jyu5': 'jyː',
}

IPA_TONES = {
    'jat1': 'jɐt̚˥', 'zung1': 't͡sʊŋ˥', 'nei5': 'nei̯˩˧', 'hou2': 'hou̯˧˥',
    'm4': 'm̩˨˩', 'haa6': 'haː˨', 'gwok3': 'kʷɔːk̚˧',
}


class TestJyutpingIpa(unittest.TestCase):
    def test_phonemes(self):
        for src, expected in IPA.items():
            with self.subTest(src=src):
                self.assertEqual(jyutping_to_ipa(src), expected)

    def test_with_tones(self):
        for src, expected in IPA_TONES.items():
            with self.subTest(src=src):
                self.assertEqual(jyutping_to_ipa_tones(src), expected)

    def test_multisyllable_joined_with_space(self):
        self.assertEqual(jyutping_to_ipa('gwong2 zau1'), 'kʷɔːŋ t͡sɐu̯')

    def test_unrecognised_passthrough(self):
        self.assertEqual(jyutping_to_ipa('xyz'), 'xyz')
        self.assertEqual(jyutping_to_ipa(''), '')


if __name__ == '__main__':
    unittest.main()
