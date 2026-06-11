"""Hangul → Yale romanization.

A precomposed Hangul syllable (U+AC00–U+D7A3) decomposes algorithmically into an
initial (초성), medial (중성) and optional final (종성) jamo; Yale romanization is
a fixed per-jamo mapping with no liaison rules, so a syllable romanizes
independently of its neighbours. This is exactly the convention Unihan's kKorean
field uses (lowercased here): 갈→"kal", 애→"ay", 녀→"nye".

Used by dedup_readings.py to bridge Unihan's Yale-spelled Korean readings onto
their Hangul-spelled twins (the Korean analog of the kana/Hepburn bridge in
romaji.py). Kept dependency-free and importable on its own.
"""

# Jamo indices follow the Unicode Hangul syllable composition algorithm.
_S_BASE = 0xAC00
_S_COUNT = 11172          # 19 * 21 * 28
_V_COUNT = 21
_T_COUNT = 28

# Yale per-jamo tables, indexed by the decomposition index.
_INITIALS = [
    "k", "kk", "n", "t", "tt", "l", "m", "p", "pp", "s",
    "ss", "", "c", "cc", "ch", "kh", "th", "ph", "h",
]
_MEDIALS = [
    "a", "ay", "ya", "yay", "e", "ey", "ye", "yey", "o", "wa",
    "way", "oy", "yo", "wu", "we", "wey", "wi", "yu", "u", "uy", "i",
]
_FINALS = [
    "", "k", "kk", "ks", "n", "nc", "nh", "t", "l", "lk",
    "lm", "lp", "ls", "lth", "lph", "lh", "m", "p", "ps", "s",
    "ss", "ng", "c", "ch", "kh", "th", "ph", "h",
]


def hangul_to_yale(text: str) -> str:
    """Romanize a Hangul string to (lowercase) Yale.

    Precomposed syllables are decomposed and mapped jamo-by-jamo; any character
    outside the syllable block is passed through unchanged.
    """
    out = []
    for ch in text:
        s = ord(ch) - _S_BASE
        if 0 <= s < _S_COUNT:
            initial = s // (_V_COUNT * _T_COUNT)
            medial = (s % (_V_COUNT * _T_COUNT)) // _T_COUNT
            final = s % _T_COUNT
            out.append(_INITIALS[initial] + _MEDIALS[medial] + _FINALS[final])
        else:
            out.append(ch)
    return "".join(out)
