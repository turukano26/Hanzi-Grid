"""Hangul transcription (Yale, Revised Romanization, and IPA).

A precomposed Hangul syllable (U+AC00–U+D7A3) decomposes algorithmically into an
initial (초성), medial (중성) and optional final (종성) jamo. All three mappings
here are fixed per-jamo tables applied syllable-by-syllable, with no
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
  * `hangul_to_ipa`     — broad IPA for Standard (Seoul) Korean: 갈→"kal", 여→"jʌ",
                          성→"sʌŋ", 꽃→"k͈ot̚". Tense consonants take U+0348 (k͈ t͈
                          p͈ s͈ t͡ɕ͈); lenis onset stops are voiceless in isolation.
                          Used by app.py as the derived Korean IPA (from Hangul).

Syllable-final consonants take their representative sound (RR romanized, or an
unreleased stop in IPA), since a lone syllable has no following vowel to trigger
liaison: 학→"hak"/"hak̚", 국→"guk"/"kuk̚". Kept dependency-free and importable on
its own.
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

# --- IPA (broad, Standard/Seoul Korean) -------------------------------------
# Onset lenis stops are voiceless in isolation (no intervocalic voicing); tense
# consonants carry U+0348; ㅇ is a null onset. Codas take the representative
# (unreleased) sound, with the 27 finals collapsing to the seven [k̚ n t̚ l m p̚ ŋ].
_IPA_INITIALS = [
    "k", "k͈", "n", "t", "t͈", "ɾ", "m", "p", "p͈", "s",
    "s͈", "", "t͡ɕ", "t͡ɕ͈", "t͡ɕʰ", "kʰ", "tʰ", "pʰ", "h",
]
_IPA_MEDIALS = [
    "a", "ɛ", "ja", "jɛ", "ʌ", "e", "jʌ", "je", "o", "wa",
    "wɛ", "ø", "jo", "u", "wʌ", "we", "y", "ju", "ɯ", "ɰi", "i",
]
_IPA_FINALS = [
    "", "k̚", "k̚", "k̚", "n", "n", "n", "t̚", "l", "k̚",
    "m", "l", "l", "l", "p̚", "l", "m", "p̚", "p̚", "t̚",
    "t̚", "ŋ", "t̚", "t̚", "k̚", "t̚", "p̚", "t̚",
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


def hangul_to_ipa(text: str) -> str:
    """Broad IPA for a Hangul string (Standard/Seoul Korean, syllable in isolation)."""
    return _romanize(text, _IPA_INITIALS, _IPA_MEDIALS, _IPA_FINALS)
