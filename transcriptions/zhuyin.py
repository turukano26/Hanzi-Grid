"""Mandarin Pīnyīn → Zhùyīn (Bopomofo).

Turns a Hanyu Pinyin syllable into its Zhùyīn Fúhào spelling, the phonetic
notation used in Taiwan: each syllable is an initial symbol (ㄅㄆㄇ…), an
optional medial glide (ㄧㄨㄩ) and a rime (ㄚㄛㄜ…), with the medial folded into
the multi-symbol finals (iang → ㄧㄤ, uo → ㄨㄛ, iong → ㄩㄥ). Tones are the
standard Bopomofo marks: tone 1 unmarked, 2 ˊ, 3 ˇ, 4 ˋ appended after the
syllable, and the neutral tone ˙ prepended. Used by `app.py` as the derived
Mandarin Zhùyīn transcription (`pinyin_zhuyin`, system 4) from Pinyin (system 1),
so every Mandarin reading that has a Pinyin shows a Zhùyīn without anything being
stored.

The input is the *diacritic* Pinyin the DB stores (e.g. "shàng"), but a trailing
tone digit ("shang4") is accepted too. Tone 5 / neutral gets the prepended dot.
Unrecognised input is returned unchanged, never raised on — the value still
renders, just un-Zhùyīn'd.

Pinyin's orthographic shorthands are undone before mapping: the zero-initial
y-/w- spellings (yi→i, yu→ü, ya→ia, wo→uo …), the j/q/x "u"-really-ü rule
(ju→jü), and the written-short finals iu→iou, ui→uei, un→uen. Kept stdlib-only
and importable on its own.
"""

import unicodedata

_TONE_MARKS = {
    '̄': 1,   # macron  ā
    '́': 2,   # acute   á
    '̌': 3,   # caron   ǎ
    '̀': 4,   # grave   à
}
# Bopomofo tone marks. Tone 1 is unmarked; tones 2-4 are appended after the
# syllable; the neutral tone (5) is the dot ˙ prepended before the syllable.
_TONE_OUT = {1: '', 2: 'ˊ', 3: 'ˇ', 4: 'ˋ'}
_NEUTRAL_DOT = '˙'

_INITIALS = {
    'b': 'ㄅ', 'p': 'ㄆ', 'm': 'ㄇ', 'f': 'ㄈ',
    'd': 'ㄉ', 't': 'ㄊ', 'n': 'ㄋ', 'l': 'ㄌ',
    'g': 'ㄍ', 'k': 'ㄎ', 'h': 'ㄏ',
    'j': 'ㄐ', 'q': 'ㄑ', 'x': 'ㄒ',
    'zh': 'ㄓ', 'ch': 'ㄔ', 'sh': 'ㄕ', 'r': 'ㄖ',
    'z': 'ㄗ', 'c': 'ㄘ', 's': 'ㄙ',
}
# Longest-match order so 'zh'/'ch'/'sh' beat 'z'/'c'/'s'.
_INITIAL_KEYS = ('zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l',
                 'g', 'k', 'h', 'j', 'q', 'x', 'r', 'z', 'c', 's')

# Finals keyed by their *underlying* form (after the y-/w-/ü shorthands are
# undone). The medial glide is folded into the symbol string, so the same table
# serves syllables with and without an initial (uo → ㄨㄛ is both "wo" and "duo").
_FINALS = {
    'a': 'ㄚ', 'o': 'ㄛ', 'e': 'ㄜ', 'ê': 'ㄝ', 'er': 'ㄦ',
    'ai': 'ㄞ', 'ei': 'ㄟ', 'ao': 'ㄠ', 'ou': 'ㄡ',
    'an': 'ㄢ', 'en': 'ㄣ', 'ang': 'ㄤ', 'eng': 'ㄥ', 'ong': 'ㄨㄥ',
    'i': 'ㄧ', 'ia': 'ㄧㄚ', 'ie': 'ㄧㄝ', 'iao': 'ㄧㄠ', 'iou': 'ㄧㄡ',
    'ian': 'ㄧㄢ', 'in': 'ㄧㄣ', 'iang': 'ㄧㄤ', 'ing': 'ㄧㄥ', 'iong': 'ㄩㄥ',
    'u': 'ㄨ', 'ua': 'ㄨㄚ', 'uo': 'ㄨㄛ', 'uai': 'ㄨㄞ', 'uei': 'ㄨㄟ',
    'uan': 'ㄨㄢ', 'uen': 'ㄨㄣ', 'uang': 'ㄨㄤ', 'ueng': 'ㄨㄥ',
    'ü': 'ㄩ', 'üe': 'ㄩㄝ', 'üan': 'ㄩㄢ', 'ün': 'ㄩㄣ',
}


def _split_tone(syllable):
    """(toneless lowercase base, tone 1-5). Handles a diacritic tone mark or a
    trailing tone digit; keeps the ü diaeresis intact."""
    syllable = syllable.strip()
    if syllable and syllable[-1] in '12345':
        return syllable[:-1].lower(), int(syllable[-1])
    tone = 5
    kept = []
    for ch in unicodedata.normalize('NFD', syllable):
        if ch in _TONE_MARKS:
            tone = _TONE_MARKS[ch]
        else:
            kept.append(ch)
    return unicodedata.normalize('NFC', ''.join(kept)).lower(), tone


def _undo_yw(s):
    """Undo the zero-initial y-/w- spellings, restoring the underlying final
    (yi→i, yu→ü, ya→ia, wu→u, wo→uo …)."""
    if s.startswith('y'):
        if s.startswith('yu'):
            return 'ü' + s[2:]
        if s.startswith('yi'):
            return s[1:]
        return 'i' + s[1:]
    if s.startswith('w'):
        if s.startswith('wu'):
            return s[1:]
        return 'u' + s[1:]
    return s


def _apply_tone(body, tone):
    """Attach the Bopomofo tone mark to an assembled syllable body."""
    if tone == 5:
        return _NEUTRAL_DOT + body
    return body + _TONE_OUT[tone]


def _syllable_to_zhuyin(syllable):
    base, tone = _split_tone(syllable)
    if not base:
        return syllable
    base = base.replace('v', 'ü').replace('u:', 'ü')
    base = _undo_yw(base)

    initial = ''
    for key in _INITIAL_KEYS:
        if base.startswith(key):
            initial, final = key, base[len(key):]
            break
    else:
        final = base

    # After j/q/x the written "u" is really ü (ju→jü, juan→jüan, jun→jün).
    if initial in ('j', 'q', 'x') and final.startswith('u'):
        final = 'ü' + final[1:]
    # Written-short finals.
    final = {'iu': 'iou', 'ui': 'uei', 'un': 'uen'}.get(final, final)

    # Apical "buzzing" vowels: zhi/chi/shi/ri and zi/ci/si are written with the
    # initial symbol alone, no rime.
    if final == 'i' and initial in ('zh', 'ch', 'sh', 'r', 'z', 'c', 's'):
        return _apply_tone(_INITIALS[initial], tone)

    if final not in _FINALS:
        return syllable                     # unrecognised final — leave as-is

    return _apply_tone(_INITIALS.get(initial, '') + _FINALS[final], tone)


def pinyin_to_zhuyin(pinyin: str) -> str:
    """Zhùyīn (Bopomofo) for a Mandarin Pinyin string (one or more
    space-separated syllables). Unrecognised syllables are passed through
    unchanged."""
    return ' '.join(_syllable_to_zhuyin(s) for s in pinyin.split())
