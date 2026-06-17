"""Tests for transcriptions/zhuyin.py — Mandarin Pīnyīn → Zhùyīn (Bopomofo).

Expected values are the verified cases used when the converter was implemented:
medial glides folded into multi-symbol finals (iang → ㄧㄤ), apical-vowel
syllables as the bare initial (zhi → ㄓ), tone 1 unmarked, 2/3/4 appended, the
neutral tone dot ˙ prepended."""

import unittest

from transcriptions.zhuyin import pinyin_to_zhuyin

CASES = {
    'shàng': 'ㄕㄤˋ', 'zhōng': 'ㄓㄨㄥ', 'wén': 'ㄨㄣˊ', 'yī': 'ㄧ', 'wǔ': 'ㄨˇ',
    'yuán': 'ㄩㄢˊ', 'jūn': 'ㄐㄩㄣ', 'jiǔ': 'ㄐㄧㄡˇ', 'guì': 'ㄍㄨㄟˋ', 'lùn': 'ㄌㄨㄣˋ',
    'zhī': 'ㄓ', 'rì': 'ㄖˋ', 'sì': 'ㄙˋ', 'bō': 'ㄅㄛ', 'yòng': 'ㄩㄥˋ', 'ér': 'ㄦˊ',
    'yáng': 'ㄧㄤˊ', 'wāng': 'ㄨㄤ', 'de': '˙ㄉㄜ', 'lǜ': 'ㄌㄩˋ', 'xué': 'ㄒㄩㄝˊ',
    'nǚ': 'ㄋㄩˇ', 'wèng': 'ㄨㄥˋ', 'hǎo': 'ㄏㄠˇ',
    # numbered-pinyin input is accepted too
    'er2': 'ㄦˊ', 'shang4': 'ㄕㄤˋ',
}


class TestZhuyin(unittest.TestCase):
    def test_cases(self):
        for src, expected in CASES.items():
            with self.subTest(src=src):
                self.assertEqual(pinyin_to_zhuyin(src), expected)

    def test_multisyllable_joined_with_space(self):
        self.assertEqual(pinyin_to_zhuyin('zhōng wén'), 'ㄓㄨㄥ ㄨㄣˊ')

    def test_unrecognised_passthrough(self):
        self.assertEqual(pinyin_to_zhuyin('foo'), 'foo')
        self.assertEqual(pinyin_to_zhuyin(''), '')


if __name__ == '__main__':
    unittest.main()
