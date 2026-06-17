"""Mandarin Pīnyīn → Wade-Giles.

Turns a Hanyu Pinyin syllable into its Wade-Giles spelling, the romanization
standard before Pinyin: voiceless/aspirated stops distinguished by a spiritus
asper (pʻ, tʻ, kʻ, chʻ, tsʻ rather than Pinyin's b/p, d/t …), the palatal series
written ch/chʻ/hs, the retroflex apical vowel as -ih (shih, chih) and the dental
apical as -ŭ with z/c/s respelled tz/tzʻ/ss (tzŭ, tzʻŭ, ssŭ), and a superscript
Chao tone number per syllable (neutral tone unmarked). Used by `app.py` as the
derived Mandarin Wade-Giles transcription (`pinyin_wade_giles`, system 3) from
Pinyin (system 1), so every Mandarin reading that has a Pinyin shows a
Wade-Giles without anything being stored.

The input is the *diacritic* Pinyin the DB stores (e.g. "shàng"), but a trailing
tone digit ("shang4") is accepted too. Tone 5 / neutral (no mark) gets no tone
number. Unrecognised input is returned unchanged, never raised on — the value
still renders, just un-Wade-Giles'd.

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
_TONE_SUPER = {1: '¹', 2: '²', 3: '³', 4: '⁴', 5: ''}

# Aspiration is written with the spiritus asper / turned comma (U+02BB).
_INITIALS = {
    'b': 'p', 'p': 'pʻ', 'm': 'm', 'f': 'f',
    'd': 't', 't': 'tʻ', 'n': 'n', 'l': 'l',
    'g': 'k', 'k': 'kʻ', 'h': 'h',
    'j': 'ch', 'q': 'chʻ', 'x': 'hs',
    'zh': 'ch', 'ch': 'chʻ', 'sh': 'sh', 'r': 'j',
    'z': 'ts', 'c': 'tsʻ', 's': 's',
}
# Longest-match order so 'zh'/'ch'/'sh' beat 'z'/'c'/'s'.
_INITIAL_KEYS = ('zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l',
                 'g', 'k', 'h', 'j', 'q', 'x', 'r', 'z', 'c', 's')

# Finals keyed by their *underlying* form (after the y-/w-/ü shorthands are
# undone), for syllables that have a consonant initial. 'uo' is handled
# specially (kept after g/k/h/sh, reduced to -o elsewhere).
_FINALS = {
    'a': 'a', 'o': 'o', 'e': 'ê', 'ê': 'eh', 'er': 'êrh',
    'ai': 'ai', 'ei': 'ei', 'ao': 'ao', 'ou': 'ou',
    'an': 'an', 'en': 'ên', 'ang': 'ang', 'eng': 'êng', 'ong': 'ung',
    'i': 'i', 'ia': 'ia', 'ie': 'ieh', 'iao': 'iao', 'iou': 'iu',
    'ian': 'ien', 'in': 'in', 'iang': 'iang', 'ing': 'ing', 'iong': 'iung',
    'u': 'u', 'ua': 'ua', 'uai': 'uai', 'uei': 'ui',
    'uan': 'uan', 'uen': 'un', 'uang': 'uang',
    'ü': 'ü', 'üe': 'üeh', 'üan': 'üan', 'ün': 'ün',
}
# Zero-initial syllables spell the medial glide as y-/w-.
_FINALS_ZERO = {
    'a': 'a', 'o': 'o', 'e': 'ê', 'ê': 'eh', 'er': 'êrh',
    'ai': 'ai', 'ei': 'ei', 'ao': 'ao', 'ou': 'ou',
    'an': 'an', 'en': 'ên', 'ang': 'ang', 'eng': 'êng',
    'i': 'i', 'ia': 'ya', 'ie': 'yeh', 'iao': 'yao', 'iou': 'yu',
    'ian': 'yen', 'in': 'yin', 'iang': 'yang', 'ing': 'ying', 'iong': 'yung',
    'u': 'wu', 'ua': 'wa', 'uo': 'wo', 'uai': 'wai', 'uei': 'wei',
    'uan': 'wan', 'uen': 'wên', 'uang': 'wang', 'ueng': 'wêng',
    'ü': 'yü', 'üe': 'yüeh', 'üan': 'yüan', 'ün': 'yün',
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


def _syllable_to_wg(syllable):
    base, tone = _split_tone(syllable)
    if not base:
        return syllable
    tone_super = _TONE_SUPER[tone]
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

    # Apical "buzzing" vowels: after retroflexes -i → -ih (chih, shih, jih);
    # after dentals z/c/s the whole onset is respelled and -i → -ŭ (tzŭ, ssŭ).
    if final == 'i' and initial in ('zh', 'ch', 'sh', 'r'):
        return _INITIALS[initial] + 'ih' + tone_super
    if final == 'i' and initial in ('z', 'c', 's'):
        return {'z': 'tz', 'c': 'tzʻ', 's': 'ss'}[initial] + 'ŭ' + tone_super

    # -uo keeps its medial after velars and sh (kuo, huo, shuo) but reduces to
    # -o elsewhere (cho, tso, lo).
    if final == 'uo' and initial:
        final_wg = 'uo' if initial in ('g', 'k', 'h', 'sh') else 'o'
    else:
        table = _FINALS if initial else _FINALS_ZERO
        if final not in table:
            return syllable                 # unrecognised final — leave as-is
        final_wg = table[final]

    return _INITIALS.get(initial, '') + final_wg + tone_super


def pinyin_to_wade_giles(pinyin: str) -> str:
    """Wade-Giles for a Mandarin Pinyin string (one or more space-separated
    syllables). Unrecognised syllables are passed through unchanged."""
    return ' '.join(_syllable_to_wg(s) for s in pinyin.split())
