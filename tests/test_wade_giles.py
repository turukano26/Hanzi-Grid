"""Tests for transcriptions/wade_giles.py — Mandarin Pīnyīn → Wade-Giles.

Expected values are the verified cases used when the converter was implemented:
spiritus-asper aspiration (pʻ/tʻ/kʻ), palatal ch/chʻ/hs, apical -ih (shih) and
respelled dentals tzŭ/tzʻŭ/ssŭ, superscript Chao tone numbers."""

import unittest

from transcriptions.wade_giles import pinyin_to_wade_giles

CASES = {
    'běi': 'pei³', 'jīng': 'ching¹', 'máo': 'mao²', 'dōng': 'tung¹',
    'tái': 'tʻai²', 'xià': 'hsia⁴', 'shàng': 'shang⁴', 'zhōng': 'chung¹',
    'rì': 'jih⁴', 'zǐ': 'tzŭ³', 'cí': 'tzʻŭ²', 'sī': 'ssŭ¹', 'shì': 'shih⁴',
    'chī': 'chʻih¹', 'qù': 'chʻü⁴', 'jūn': 'chün¹', 'xué': 'hsüeh²',
    'yuán': 'yüan²', 'wǒ': 'wo³', 'yī': 'i¹', 'yǒu': 'yu³', 'wèi': 'wei⁴',
    'guó': 'kuo²', 'huǒ': 'huo³', 'zhuō': 'cho¹', 'luó': 'lo²', 'duō': 'to¹',
    'niú': 'niu²', 'lǜ': 'lü⁴', 'nǚ': 'nü³', 'er': 'êrh', 'gē': 'kê¹',
    'fēng': 'fêng¹', 'yáng': 'yang²', 'yīng': 'ying¹', 'wén': 'wên²',
    'xún': 'hsün²', 'jiǔ': 'chiu³', 'guì': 'kui⁴', 'lún': 'lun²',
    'bo': 'po', 'de': 'tê', 'ma': 'ma',
}


class TestWadeGiles(unittest.TestCase):
    def test_cases(self):
        for src, expected in CASES.items():
            with self.subTest(src=src):
                self.assertEqual(pinyin_to_wade_giles(src), expected)

    def test_multisyllable_joined_with_space(self):
        self.assertEqual(pinyin_to_wade_giles('zhōng huá'), 'chung¹ hua²')

    def test_unrecognised_passthrough(self):
        self.assertEqual(pinyin_to_wade_giles('foo'), 'foo')
        self.assertEqual(pinyin_to_wade_giles(''), '')


if __name__ == '__main__':
    unittest.main()
