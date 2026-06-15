"""Cantonese Jyutping → IPA (broad transcription).

Turns a Jyutping syllable into a broad phonemic IPA transcription in the
convention used by Wikipedia's *Help:IPA/Cantonese*: tie-bar affricates
(t͡s, t͡sʰ), labialised velars (kʷ, kʷʰ), long/short vowel contrast (aː vs ɐ),
unreleased final stops (p̚, t̚, k̚), non-syllabic diphthong off-glides
(aːi̯, ɐu̯ …), syllabic nasals (m̩, ŋ̩), and — for `jyutping_to_ipa_tones` — a
Chao tone letter per tone. Used by `app.py` as the two derived Cantonese IPA
transcriptions — `jyutping_to_ipa` for "IPA" (phonemes only, system 12) and
`jyutping_to_ipa_tones` for "IPA (with tones)" (system 13) — both from Jyutping,
so every Cantonese reading that has a Jyutping shows an IPA without anything
being stored.

A Jyutping syllable is initial + final + a tone digit 1-6. The final is looked
up whole (Cantonese has a closed ~60-rime inventory) rather than composed, so
the vowel-length and i/u→ɪ/ʊ-before-velar allophony is baked into the table
rather than computed. Unrecognised input is returned unchanged, never raised on.
Kept stdlib-only and importable on its own.
"""

# Chao tone letters for Jyutping tones 1-6 (55, 35, 33, 21, 13, 22).
_TONE_LETTERS = {1: '˥', 2: '˧˥', 3: '˧', 4: '˨˩', 5: '˩˧', 6: '˨'}

_INITIALS = {
    'b': 'p', 'p': 'pʰ', 'm': 'm', 'f': 'f',
    'd': 't', 't': 'tʰ', 'n': 'n', 'l': 'l',
    'g': 'k', 'k': 'kʰ', 'ng': 'ŋ', 'h': 'h',
    'gw': 'kʷ', 'kw': 'kʷʰ', 'w': 'w',
    'z': 't͡s', 'c': 't͡sʰ', 's': 's', 'j': 'j',
}
# Longest-match order so 'gw'/'kw'/'ng' beat 'g'/'k'/'n'.
_INITIAL_KEYS = ('gw', 'kw', 'ng', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l',
                 'g', 'k', 'h', 'w', 'z', 'c', 's', 'j')

# Whole-syllable nasals (no initial), e.g. 唔 m4, 五 ng5.
_SYLLABIC = {'m': 'm̩', 'ng': 'ŋ̩'}

# Finals keyed whole. Off-glides carry the non-syllabic mark U+032F; final stops
# the unreleased mark U+031A; i/u tense to ɪ/ʊ before a velar coda.
_FINALS = {
    # aa (long ɐ→aː)
    'aa': 'aː', 'aai': 'aːi̯', 'aau': 'aːu̯', 'aam': 'aːm', 'aan': 'aːn',
    'aang': 'aːŋ', 'aap': 'aːp̚', 'aat': 'aːt̚', 'aak': 'aːk̚',
    # a (short ɐ)
    'ai': 'ɐi̯', 'au': 'ɐu̯', 'am': 'ɐm', 'an': 'ɐn', 'ang': 'ɐŋ',
    'ap': 'ɐp̚', 'at': 'ɐt̚', 'ak': 'ɐk̚',
    # e
    'e': 'ɛː', 'ei': 'ei̯', 'eu': 'ɛːu̯', 'em': 'ɛːm', 'eng': 'ɛːŋ',
    'ep': 'ɛːp̚', 'ek': 'ɛːk̚',
    # i (ɪ before a velar coda)
    'i': 'iː', 'iu': 'iːu̯', 'im': 'iːm', 'in': 'iːn', 'ing': 'ɪŋ',
    'ip': 'iːp̚', 'it': 'iːt̚', 'ik': 'ɪk̚',
    # o
    'o': 'ɔː', 'oi': 'ɔːi̯', 'ou': 'ou̯', 'on': 'ɔːn', 'ong': 'ɔːŋ',
    'ot': 'ɔːt̚', 'ok': 'ɔːk̚',
    # u (ʊ before a velar coda)
    'u': 'uː', 'ui': 'uːi̯', 'un': 'uːn', 'ung': 'ʊŋ', 'ut': 'uːt̚',
    'uk': 'ʊk̚',
    # oe / eo
    'oe': 'œː', 'oeng': 'œːŋ', 'oek': 'œːk̚', 'oet': 'œːt̚',
    'eo': 'ɵ', 'eoi': 'ɵy̯', 'eon': 'ɵn', 'eot': 'ɵt̚',
    # yu
    'yu': 'yː', 'yun': 'yːn', 'yut': 'yːt̚',
}


def _syllable_to_ipa(syllable, tones):
    s = syllable.strip().lower()
    tone = None
    if s and s[-1] in '123456':
        s, tone = s[:-1], int(s[-1])
    if not s:
        return syllable
    tone_letter = _TONE_LETTERS.get(tone, '') if tones else ''

    if s in _SYLLABIC:
        return _SYLLABIC[s] + tone_letter

    initial = ''
    for key in _INITIAL_KEYS:
        if s.startswith(key):
            initial, final = key, s[len(key):]
            break
    else:
        final = s

    if final not in _FINALS:
        return syllable                     # unrecognised final — leave as-is
    return _INITIALS.get(initial, '') + _FINALS[final] + tone_letter


def jyutping_to_ipa(jyutping: str) -> str:
    """Broad IPA (phonemes only, no tone letters) for a Cantonese Jyutping string
    (one or more space-separated syllables). Unrecognised syllables are passed
    through unchanged."""
    return ' '.join(_syllable_to_ipa(s, tones=False) for s in jyutping.split())


def jyutping_to_ipa_tones(jyutping: str) -> str:
    """Broad IPA with a Chao tone letter appended per syllable. Otherwise
    identical to `jyutping_to_ipa`."""
    return ' '.join(_syllable_to_ipa(s, tones=True) for s in jyutping.split())
