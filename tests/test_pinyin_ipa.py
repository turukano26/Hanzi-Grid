"""Tests for transcriptions/pinyin_ipa.py — Mandarin Pīnyīn → broad IPA.

Expected values follow the Help:IPA/Mandarin scheme documented in the module
(tie-bar affricates, apical syllabic z̩/ʐ̩, non-syllabic off-glides, Chao tone
letters for the *_tones variant)."""

import unittest

from transcriptions.pinyin_ipa import pinyin_to_ipa, pinyin_to_ipa_tones

# Phonemes only, no tone letters.
IPA = {
    'yī': 'i', 'zhōng': 'ʈ͡ʂʊŋ', 'nǐ': 'ni', 'hǎo': 'xau̯', 'shì': 'ʂʐ̩',
    'sì': 'sz̩', 'èr': 'ɚ', 'wǒ': 'wɔ', 'jiā': 't͡ɕja', 'shàng': 'ʂaŋ',
    'lǜ': 'ly', 'nǚ': 'ny', 'rì': 'ʐ̩', 'zhī': 'ʈ͡ʂʐ̩', 'zì': 't͡sz̩',
    'ér': 'ɚ', 'wǔ': 'u', 'guì': 'kwei̯', 'jūn': 't͡ɕyn', 'xué': 'ɕɥɛ',
    'yuán': 'ɥɛn', 'bāo': 'pau̯', 'duì': 'twei̯', 'bō': 'pwɔ',
}

# With a Chao tone letter appended per syllable.
IPA_TONES = {
    'yī': 'i˥', 'zhōng': 'ʈ͡ʂʊŋ˥', 'nǐ': 'ni˨˩˦', 'hǎo': 'xau̯˨˩˦',
    'shì': 'ʂʐ̩˥˩', 'ér': 'ɚ˧˥', 'wǔ': 'u˨˩˦', 'xué': 'ɕɥɛ˧˥',
}


class TestPinyinIpa(unittest.TestCase):
    def test_phonemes(self):
        for src, expected in IPA.items():
            with self.subTest(src=src):
                self.assertEqual(pinyin_to_ipa(src), expected)

    def test_with_tones(self):
        for src, expected in IPA_TONES.items():
            with self.subTest(src=src):
                self.assertEqual(pinyin_to_ipa_tones(src), expected)

    def test_multisyllable_joined_with_space(self):
        self.assertEqual(pinyin_to_ipa('yī zhōng'), 'i ʈ͡ʂʊŋ')

    def test_unrecognised_passthrough(self):
        # Documented contract: unrecognised syllables are returned unchanged.
        self.assertEqual(pinyin_to_ipa('foo'), 'foo')
        self.assertEqual(pinyin_to_ipa(''), '')


if __name__ == '__main__':
    unittest.main()
