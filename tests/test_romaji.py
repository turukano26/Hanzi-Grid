"""Tests for the Japanese kana⇄romaji pair:
  transcriptions/romaji.py      — _kana_to_romaji (kana → Hepburn)
  transcriptions/romaji_kana.py — romaji_to_kana (Hepburn → hiragana/katakana)

Both preserve okurigana '.' and affix '-' markers. romaji_to_kana renders
hiragana by default and katakana when katakana=True (the on'yomi script)."""

import unittest

from transcriptions.romaji import _kana_to_romaji
from transcriptions.romaji_kana import romaji_to_kana

# kana → Hepburn romaji
TO_ROMAJI = {
    'ショウ': 'shou', 'がく': 'gaku', 'キョウ': 'kyou', 'ジツ': 'jitsu',
    'ニチ': 'nichi', 'チョウ': 'chou', 'シュウ': 'shuu',
    'つ.ぐ': 'tsu.gu',           # okurigana boundary preserved
    'うつく.しい': 'utsuku.shii',
    'まな.ぶ': 'mana.bu',
    'こ-': 'ko-',                # affix marker preserved
    '-づ.ける': '-zu.keru',
}

# Hepburn romaji → kana (hiragana, katakana)
TO_KANA = {
    'shou': ('しょう', 'ショウ'),
    'gaku': ('がく', 'ガク'),
    'kyou': ('きょう', 'キョウ'),
    'jitsu': ('じつ', 'ジツ'),
    'nichi': ('にち', 'ニチ'),
    'manabu': ('まなぶ', 'マナブ'),
}


class TestKanaToRomaji(unittest.TestCase):
    def test_cases(self):
        for src, expected in TO_ROMAJI.items():
            with self.subTest(src=src):
                self.assertEqual(_kana_to_romaji(src), expected)


class TestRomajiToKana(unittest.TestCase):
    def test_hiragana(self):
        for src, (hira, _kata) in TO_KANA.items():
            with self.subTest(src=src):
                self.assertEqual(romaji_to_kana(src, katakana=False), hira)

    def test_katakana(self):
        for src, (_hira, kata) in TO_KANA.items():
            with self.subTest(src=src):
                self.assertEqual(romaji_to_kana(src, katakana=True), kata)


if __name__ == '__main__':
    unittest.main()
