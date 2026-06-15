"""Mandarin Pīnyīn → IPA (broad transcription).

Turns a Hanyu Pinyin syllable into a broad phonemic IPA transcription in the
convention used by Wiktionary / Wikipedia's *Help:IPA/Mandarin*: retroflex and
alveolo-palatal affricates written with tie bars (ʈ͡ʂ, t͡ɕ, t͡s …), the apical
"buzzing" vowels of zi/zhi as syllabic z̩/ʐ̩, diphthong off-glides marked
non-syllabic (ai̯, au̯ …), and (for `pinyin_to_ipa_tones`) a Chao tone letter
appended per tone. Used by `app.py` as the two derived Mandarin IPA
transcriptions — `pinyin_to_ipa` for "IPA" (phonemes only, system 5) and
`pinyin_to_ipa_tones` for "IPA (with tones)" (system 6) — both from Pinyin, so
every Mandarin reading that has a Pinyin shows an IPA without anything being
stored.

The input is the *diacritic* Pinyin the DB stores (e.g. "shàng"), but a trailing
tone digit ("shang4") is accepted too, so the function works on numbered Pinyin
as well. Tone 5 / neutral (no mark) gets no tone letter. Unrecognised input is
returned unchanged, never raised on — the value still renders, just un-IPA'd.

Pinyin's orthographic shorthands are undone before mapping: the zero-initial
y-/w- spellings (yi→i, yu→ü, wu→u, ya→ia, wo→uo …), the j/q/x "u"-really-ü rule
(ju→jü), and the written-short finals iu→iou, ui→uei, un→uen. Kept stdlib-only
and importable on its own.
"""

import unicodedata

# Tone-mark combining diacritics → Chao tone number. U+0308 (diaeresis on ü) is
# deliberately absent: it is part of the vowel, not a tone.
_TONE_MARKS = {
    '̄': 1,   # macron  ā
    '́': 2,   # acute   á
    '̌': 3,   # caron   ǎ
    '̀': 4,   # grave   à
}
_TONE_LETTERS = {1: '˥', 2: '˧˥', 3: '˨˩˦', 4: '˥˩', 5: ''}

_INITIALS = {
    'b': 'p', 'p': 'pʰ', 'm': 'm', 'f': 'f',
    'd': 't', 't': 'tʰ', 'n': 'n', 'l': 'l',
    'g': 'k', 'k': 'kʰ', 'h': 'x',
    'j': 't͡ɕ', 'q': 't͡ɕʰ', 'x': 'ɕ',
    'zh': 'ʈ͡ʂ', 'ch': 'ʈ͡ʂʰ', 'sh': 'ʂ', 'r': 'ʐ',
    'z': 't͡s', 'c': 't͡sʰ', 's': 's',
}
# Longest-match order so 'zh'/'ch'/'sh' beat 'z'/'c'/'s'.
_INITIAL_KEYS = ('zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l',
                 'g', 'k', 'h', 'j', 'q', 'x', 'r', 'z', 'c', 's')

# Finals keyed by their *underlying* form (after the y-/w-/ü shorthands are
# undone). Off-glides carry the non-syllabic mark U+032F.
_FINALS = {
    'a': 'a', 'o': 'ɔ', 'e': 'ɤ', 'ê': 'ɛ', 'er': 'ɚ',
    'ai': 'ai̯', 'ei': 'ei̯', 'ao': 'au̯', 'ou': 'ou̯',
    'an': 'an', 'en': 'ən', 'ang': 'aŋ', 'eng': 'əŋ', 'ong': 'ʊŋ',
    'i': 'i', 'ia': 'ja', 'ie': 'jɛ', 'iao': 'jau̯', 'iou': 'jou̯',
    'ian': 'jɛn', 'in': 'in', 'iang': 'jaŋ', 'ing': 'iŋ', 'iong': 'jʊŋ',
    'u': 'u', 'ua': 'wa', 'uo': 'wɔ', 'uai': 'wai̯', 'uei': 'wei̯',
    'uan': 'wan', 'uen': 'wən', 'uang': 'waŋ', 'ueng': 'wəŋ',
    'ü': 'y', 'üe': 'ɥɛ', 'üan': 'ɥɛn', 'ün': 'yn',
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


def _syllable_to_ipa(syllable, tones):
    base, tone = _split_tone(syllable)
    if not base:
        return syllable
    tone_letter = _TONE_LETTERS[tone] if tones else ''
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

    # Apical syllabic vowels: zi/ci/si → z̩, zhi/chi/shi → ʐ̩; ri → ʐ̩ with the
    # initial absorbed into the syllabic.
    if final == 'i' and initial in ('z', 'c', 's'):
        final_ipa = 'z̩'
    elif final == 'i' and initial in ('zh', 'ch', 'sh'):
        final_ipa = 'ʐ̩'
    elif final == 'i' and initial == 'r':
        return 'ʐ̩' + tone_letter
    elif final == 'o' and initial in ('b', 'p', 'm', 'f'):
        final_ipa = 'wɔ'                    # bo/po/mo/fo are really b/p/m/f + uo
    elif final in _FINALS:
        final_ipa = _FINALS[final]
    else:
        return syllable                     # unrecognised final — leave as-is

    return _INITIALS.get(initial, '') + final_ipa + tone_letter


def pinyin_to_ipa(pinyin: str) -> str:
    """Broad IPA (phonemes only, no tone letters) for a Mandarin Pinyin string
    (one or more space-separated syllables). Unrecognised syllables are passed
    through unchanged."""
    return ' '.join(_syllable_to_ipa(s, tones=False) for s in pinyin.split())


def pinyin_to_ipa_tones(pinyin: str) -> str:
    """Broad IPA with a Chao tone letter appended per syllable. Otherwise
    identical to `pinyin_to_ipa`."""
    return ' '.join(_syllable_to_ipa(s, tones=True) for s in pinyin.split())
