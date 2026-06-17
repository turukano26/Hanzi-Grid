"""Tests for transcriptions/hangul_roman.py — Korean Hangul romanizations + IPA:
  hangul_to_revised — Revised Romanization (the default-on primary)
  hangul_to_yale    — Yale Romanization
  hangul_to_ipa     — broad Standard/Seoul IPA

The Revised cases are the verified set used when the romanizer was implemented;
Yale and IPA cover the same syllables (representative unreleased codas k̚/t̚/p̚,
tense consonants like k͈, the 두음법칙 y-/n- onsets)."""

import unittest

from transcriptions.hangul_roman import (
    hangul_to_revised, hangul_to_yale, hangul_to_ipa,
)

REVISED = {
    '학': 'hak', '국': 'guk', '박': 'bak', '발': 'bal', '성': 'seong',
    '여': 'yeo', '녀': 'nyeo', '애': 'ae', '갈': 'gal', '가': 'ga', '고': 'go',
    '력': 'ryeok', '김': 'gim', '십': 'sip', '꽃': 'kkot', '값': 'gap',
    '젊': 'jeom', '한': 'han', '글': 'geul',
}

YALE = {
    '학': 'hak', '국': 'kwuk', '박': 'pak', '발': 'pal', '성': 'seng',
    '여': 'ye', '녀': 'nye', '갈': 'kal', '가': 'ka', '고': 'ko',
    '력': 'lyek', '김': 'kim', '십': 'sip', '한': 'han', '글': 'kul',
    '꽃': 'kkoch', '값': 'kaps',
}

IPA = {
    '학': 'hak̚', '국': 'kuk̚', '박': 'pak̚', '발': 'pal', '성': 'sʌŋ',
    '여': 'jʌ', '녀': 'njʌ', '갈': 'kal', '가': 'ka', '고': 'ko',
    '력': 'ɾjʌk̚', '김': 'kim', '십': 'sip̚', '한': 'han', '글': 'kɯl',
    '꽃': 'k͈ot̚', '값': 'kap̚',
}


class TestHangulRevised(unittest.TestCase):
    def test_cases(self):
        for src, expected in REVISED.items():
            with self.subTest(src=src):
                self.assertEqual(hangul_to_revised(src), expected)


class TestHangulYale(unittest.TestCase):
    def test_cases(self):
        for src, expected in YALE.items():
            with self.subTest(src=src):
                self.assertEqual(hangul_to_yale(src), expected)


class TestHangulIpa(unittest.TestCase):
    def test_cases(self):
        for src, expected in IPA.items():
            with self.subTest(src=src):
                self.assertEqual(hangul_to_ipa(src), expected)


if __name__ == '__main__':
    unittest.main()
