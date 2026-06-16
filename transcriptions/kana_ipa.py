"""Kana → IPA (broad transcription of Tokyo Standard Japanese).

Turns a kana reading (the form stored under ts 32) into a broad phonemic IPA
transcription in the convention used by Wiktionary / Wikipedia's
*Help:IPA/Japanese*: /u/ as the compressed back-unrounded [ɯ], the /h/
allophones [h]/[ç]/[ɸ] before a-e-o / i / u (は[ha] ひ[çi] ふ[ɸɯ]), the /s/ and
/t/ palatals (し[ɕi] ち[t͡ɕi] つ[t͡sɯ]), affricated voiced obstruents in onset
(じ[d͡ʑi] ず[d͡zɯ]), the tap [ɾ] for /r/, gemination from the sokuon っ, and the
moraic nasal ん assimilating to [m]/[n]/[ŋ]/[ɴ] by following place. Used by
`app.py` as the derived Japanese IPA (ts 33, from Kana ts 32), so every Japanese
reading shows an IPA without anything being stored — the same path Hepburn (ts
30) takes from Kana.

Like its romaji sibling (`romaji.py`), it works mora by mora and preserves the
okurigana `.` and affix `-` markers, but it additionally collapses the standard
long vowels — おう/おお→[oː], えい/ええ→[eː], the katakana ー mark, etc. — since
length is phonemic in Japanese. There is no cross-mora liaison beyond that and
the sokuon/moraic-nasal sandhi: each reading is a lone citation form. Katakana is
folded to hiragana first; unrecognised characters pass through unchanged. Kept
stdlib-only and importable on its own.
"""

from transcriptions.romaji import _kata_to_hira

# Per-mora IPA. Digraphs (きゃ …) are listed first and matched greedily, exactly
# as in `romaji.py`'s table, so they beat the bare small-kana entries.
_KANA_IPA: dict[str, str] = {
    'きゃ': 'kʲa', 'きゅ': 'kʲɯ', 'きょ': 'kʲo',
    'しゃ': 'ɕa',  'しゅ': 'ɕɯ',  'しょ': 'ɕo',
    'ちゃ': 't͡ɕa', 'ちゅ': 't͡ɕɯ', 'ちょ': 't͡ɕo',
    'にゃ': 'ɲa',  'にゅ': 'ɲɯ',  'にょ': 'ɲo',
    'ひゃ': 'ça',  'ひゅ': 'çɯ',  'ひょ': 'ço',
    'みゃ': 'mʲa', 'みゅ': 'mʲɯ', 'みょ': 'mʲo',
    'りゃ': 'ɾʲa', 'りゅ': 'ɾʲɯ', 'りょ': 'ɾʲo',
    'ぎゃ': 'ɡʲa', 'ぎゅ': 'ɡʲɯ', 'ぎょ': 'ɡʲo',
    'じゃ': 'd͡ʑa', 'じゅ': 'd͡ʑɯ', 'じょ': 'd͡ʑo',
    'ぢゃ': 'd͡ʑa', 'ぢゅ': 'd͡ʑɯ', 'ぢょ': 'd͡ʑo',
    'びゃ': 'bʲa', 'びゅ': 'bʲɯ', 'びょ': 'bʲo',
    'ぴゃ': 'pʲa', 'ぴゅ': 'pʲɯ', 'ぴょ': 'pʲo',
    'ふぁ': 'ɸa',  'ふぃ': 'ɸi',  'ふぇ': 'ɸe',  'ふぉ': 'ɸo',
    'てぃ': 'ti',  'でぃ': 'di',  'でゅ': 'dʲɯ',
    'あ': 'a',  'い': 'i',  'う': 'ɯ',  'え': 'e',  'お': 'o',
    'か': 'ka', 'き': 'ki', 'く': 'kɯ', 'け': 'ke', 'こ': 'ko',
    'さ': 'sa', 'し': 'ɕi', 'す': 'sɯ', 'せ': 'se', 'そ': 'so',
    'た': 'ta', 'ち': 't͡ɕi', 'つ': 't͡sɯ', 'て': 'te', 'と': 'to',
    'な': 'na', 'に': 'ɲi', 'ぬ': 'nɯ', 'ね': 'ne', 'の': 'no',
    'は': 'ha', 'ひ': 'çi', 'ふ': 'ɸɯ', 'へ': 'he', 'ほ': 'ho',
    'ま': 'ma', 'み': 'mi', 'む': 'mɯ', 'め': 'me', 'も': 'mo',
    'や': 'ja', 'ゆ': 'jɯ', 'よ': 'jo',
    'ら': 'ɾa', 'り': 'ɾi', 'る': 'ɾɯ', 'れ': 'ɾe', 'ろ': 'ɾo',
    'わ': 'wa', 'ゐ': 'i',  'ゑ': 'e',  'を': 'o',
    'が': 'ɡa', 'ぎ': 'ɡi', 'ぐ': 'ɡɯ', 'げ': 'ɡe', 'ご': 'ɡo',
    'ざ': 'd͡za', 'じ': 'd͡ʑi', 'ず': 'd͡zɯ', 'ぜ': 'd͡ze', 'ぞ': 'd͡zo',
    'だ': 'da', 'ぢ': 'd͡ʑi', 'づ': 'd͡zɯ', 'で': 'de', 'ど': 'do',
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bɯ', 'べ': 'be', 'ぼ': 'bo',
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pɯ', 'ぺ': 'pe', 'ぽ': 'po',
    'ぁ': 'a',  'ぃ': 'i',  'ぅ': 'ɯ',  'ぇ': 'e',  'ぉ': 'o',
    'ゃ': 'ja', 'ゅ': 'jɯ', 'ょ': 'jo', 'ゎ': 'wa',
}

_VOWELS = 'aiɯeo'

# A standalone vowel kana lengthens the preceding vowel only for the canonical
# Japanese long-vowel pairs (so おう/おお→oː, えい/ええ→eː, but あう stays a diphthong).
_LONG_PAIRS = {
    ('a', 'あ'), ('i', 'い'), ('ɯ', 'う'),
    ('e', 'え'), ('e', 'い'), ('o', 'お'), ('o', 'う'),
}
_VOWEL_KANA = set('あいうえお')


def _moraic_n(next_ipa: str | None) -> str:
    """Realize the moraic nasal ん by the place of the following mora; [ɴ] before
    a vowel/glide/fricative or phrase-finally."""
    if not next_ipa:
        return 'ɴ'
    c = next_ipa[0]
    if c in 'pbm':
        return 'm'
    if c in 'kɡ':
        return 'ŋ'
    if c in 'tdnszɾɕʑ':
        return 'n'
    return 'ɴ'


def kana_to_ipa(kana: str) -> str:
    """Broad IPA for a kana reading (one citation-form mora string). Preserves
    okurigana '.' and affix '-' markers; unrecognised characters pass through."""
    hira = _kata_to_hira(kana)
    if not hira:
        return ''

    # Pass 1: tokenize into moras. Each token is (kind, ipa, src_kana) where
    # src_kana is the source char for a standalone vowel mora (else None).
    tokens: list[tuple] = []
    i, n = 0, len(hira)
    while i < n:
        ch = hira[i]
        if ch in ('.', '-'):
            tokens.append(('marker', ch, None))
        elif ch == 'ー':
            tokens.append(('long', '', None))
        elif ch == 'っ':
            tokens.append(('sokuon', '', None))
        elif ch == 'ん':
            tokens.append(('moraic_n', '', None))
        elif i + 1 < n and hira[i:i + 2] in _KANA_IPA:
            tokens.append(('ipa', _KANA_IPA[hira[i:i + 2]], None))
            i += 2
            continue
        elif ch in _KANA_IPA:
            tokens.append(('ipa', _KANA_IPA[ch], ch if ch in _VOWEL_KANA else None))
        else:
            tokens.append(('raw', ch, None))
        i += 1

    def _next_ipa(start: int) -> str | None:
        for kind, ipa, _ in tokens[start + 1:]:
            if kind in ('ipa', 'raw'):
                return ipa
        return None

    # Pass 2: render, applying long-vowel collapse and sokuon/moraic-n sandhi.
    out: list[str] = []
    for idx, (kind, ipa, src) in enumerate(tokens):
        if kind in ('ipa', 'raw'):
            if src and out and out[-1] and (out[-1][-1], src) in _LONG_PAIRS:
                out.append('ː')
            else:
                out.append(ipa)
        elif kind == 'marker':
            out.append(ipa)
        elif kind == 'long':
            if out and out[-1] and out[-1][-1] in _VOWELS:
                out.append('ː')
        elif kind == 'sokuon':
            nxt = _next_ipa(idx)
            if nxt:
                out.append(nxt[0])   # geminate the following consonant
        elif kind == 'moraic_n':
            out.append(_moraic_n(_next_ipa(idx)))
    return ''.join(out)
