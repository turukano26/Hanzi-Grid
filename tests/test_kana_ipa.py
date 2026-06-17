"""Tests for transcriptions/kana_ipa.py — Japanese kana → broad IPA.

Expected values follow the module's Help:IPA/Japanese scheme: palatalised and
affricated allophones (チ → t͡ɕi, ツ → t͡sɯ, シ → ɕi), long vowels from ー and
vowel sequences (オウ → oː), moraic ン → ɴ, and sokuon (small っ) realised as
gemination of the following consonant. Okurigana '.' and affix '-' markers are
preserved."""

import unittest

from transcriptions.kana_ipa import kana_to_ipa

CASES = {
    'ア': 'a', 'オウ': 'oː', 'シュウ': 'ɕɯː', 'キ': 'ki', 'セン': 'seɴ',
    'ホウ': 'hoː', 'ニチ': 'ɲit͡ɕi', 'ガッ': 'ɡa', 'ジツ': 'd͡ʑit͡sɯ',
    'キョウ': 'kʲoː', 'チョウ': 't͡ɕoː',
    'つ.ぐ': 't͡sɯ.ɡɯ',          # okurigana boundary preserved
    'がっ.こう': 'ɡak.koː',       # sokuon geminates the following consonant
    'ー': '',                     # a lone long-vowel mark has nothing to lengthen
}


class TestKanaIpa(unittest.TestCase):
    def test_cases(self):
        for src, expected in CASES.items():
            with self.subTest(src=src):
                self.assertEqual(kana_to_ipa(src), expected)


if __name__ == '__main__':
    unittest.main()
