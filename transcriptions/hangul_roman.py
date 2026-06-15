"""Hangul romanization (Yale and Revised).

A precomposed Hangul syllable (U+AC00–U+D7A3) decomposes algorithmically into an
initial (초성), medial (중성) and optional final (종성) jamo. Both romanizations
here are fixed per-jamo mappings applied syllable-by-syllable, with no
inter-syllable liaison — which is what we want for character readings, where each
reading is a lone syllable shown in isolation.

  * `hangul_to_yale`    — the convention Unihan's kKorean field uses (lowercased):
                          갈→"kal", 애→"ay", 녀→"nye". Used by dedup_readings.py to
                          bridge Unihan's Yale-spelled readings onto their Hangul
                          twins.
  * `hangul_to_revised` — Revised Romanization (RR, 2000), the modern South Korean
                          standard: 갈→"gal", 애→"ae", 여→"yeo", 성→"seong". Used by
                          app.py as a derived transcription (revised_rom from
                          Hangul), so every Hangul reading shows a romanization
                          even when Unihan supplied no Yale.

Syllable-final consonants in RR take their representative (unreleased) sound,
since a lone syllable has no following vowel to trigger liaison: 학→"hak",
국→"guk". Kept dependency-free and importable on its own.
"""

# Jamo indices follow the Unicode Hangul syllable composition algorithm.
_S_BASE = 0xAC00
_S_COUNT = 11172          # 19 * 21 * 28
_V_COUNT = 21
_T_COUNT = 28

# --- Yale -------------------------------------------------------------------
_YALE_INITIALS = [
    "k", "kk", "n", "t", "tt", "l", "m", "p", "pp", "s",
    "ss", "", "c", "cc", "ch", "kh", "th", "ph", "h",
]
_YALE_MEDIALS = [
    "a", "ay", "ya", "yay", "e", "ey", "ye", "yey", "o", "wa",
    "way", "oy", "yo", "wu", "we", "wey", "wi", "yu", "u", "uy", "i",
]
_YALE_FINALS = [
    "", "k", "kk", "ks", "n", "nc", "nh", "t", "l", "lk",
    "lm", "lp", "ls", "lth", "lph", "lh", "m", "p", "ps", "s",
    "ss", "ng", "c", "ch", "kh", "th", "ph", "h",
]

# --- Revised Romanization (RR) ----------------------------------------------
# Initials use the lenis g/d/b/j; the same jamo as a final takes its
# representative sound (k/t/p, l for ㄹ), since a lone syllable has no liaison.
_RR_INITIALS = [
    "g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s",
    "ss", "", "j", "jj", "ch", "k", "t", "p", "h",
]
_RR_MEDIALS = [
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa",
    "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i",
]
_RR_FINALS = [
    "", "k", "k", "k", "n", "n", "n", "t", "l", "k",
    "m", "l", "l", "l", "p", "l", "m", "p", "p", "t",
    "t", "ng", "t", "t", "k", "t", "p", "t",
]


def _romanize(text, initials, medials, finals):
    out = []
    for ch in text:
        s = ord(ch) - _S_BASE
        if 0 <= s < _S_COUNT:
            initial = s // (_V_COUNT * _T_COUNT)
            medial = (s % (_V_COUNT * _T_COUNT)) // _T_COUNT
            final = s % _T_COUNT
            out.append(initials[initial] + medials[medial] + finals[final])
        else:
            out.append(ch)
    return "".join(out)


def hangul_to_yale(text: str) -> str:
    """Romanize a Hangul string to (lowercase) Yale."""
    return _romanize(text, _YALE_INITIALS, _YALE_MEDIALS, _YALE_FINALS)


def hangul_to_revised(text: str) -> str:
    """Romanize a Hangul string to Revised Romanization (RR)."""
    return _romanize(text, _RR_INITIALS, _RR_MEDIALS, _RR_FINALS)
