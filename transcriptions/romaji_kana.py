"""Hepburn romaji → kana.

The inverse of `romaji.py`. Used by `app.py` as the `romaji_kana` transform on
the Kana system (ts 32): most Japanese readings store their kana (Kanjidic) and
Hepburn is *derived* from it, but a minority are orphan Unihan readings that
store only a romaji value under Hepburn (ts 30) — e.g. kJapaneseOn "KOU",
kJapaneseKun "TSURANARU". For those, Kana (and, in turn, IPA) is derived back
from the romaji so every reading offers both kana and Hepburn without anything
new being stored.

Like its `kana_romaji` sibling it is *dual-mode*: a value that already contains
kana is returned unchanged (so deriving Kana from a Kanjidic reading that already
has kana is a no-op), and only a pure-romaji value is converted. Hepburn long
vowels are written as plain vowel sequences in this data ("KOU", "NYOU"), so they
map mora-by-mora (こう, にょう); okurigana '.' and affix '-' markers pass through.
On'yomi are conventionally written in katakana and kun'yomi in hiragana, so the
caller selects the script via `katakana`. Kept stdlib-only and importable alone.
"""

# Hiragana per romaji syllable. Digraphs and three-letter syllables are listed so
# the greedy longest-match in `romaji_to_kana` reaches them before the bare vowel.
_ROMAJI_KANA: dict[str, str] = {
    'kya': 'きゃ', 'kyu': 'きゅ', 'kyo': 'きょ',
    'gya': 'ぎゃ', 'gyu': 'ぎゅ', 'gyo': 'ぎょ',
    # Unihan's kJapaneseOn/Kun romaji is Hepburn (し=shi, ち=chi, つ=tsu, じ=ji —
    # never the Kunrei si/ti/tu/zi/sya), but a few readings insert a redundant 'y'
    # into the palatals (shyu, chyu, shyo); cover the whole shy/chy/jy series so
    # they map exactly like shu/chu/sho.
    'shya': 'しゃ', 'shyu': 'しゅ', 'shyo': 'しょ',
    'chya': 'ちゃ', 'chyu': 'ちゅ', 'chyo': 'ちょ',
    'jya': 'じゃ',  'jyu': 'じゅ',  'jyo': 'じょ',
    'sha': 'しゃ', 'shu': 'しゅ', 'sho': 'しょ', 'shi': 'し',
    'cha': 'ちゃ', 'chu': 'ちゅ', 'cho': 'ちょ', 'chi': 'ち', 'tsu': 'つ',
    'ja': 'じゃ',  'ju': 'じゅ',  'jo': 'じょ',
    'nya': 'にゃ', 'nyu': 'にゅ', 'nyo': 'にょ',
    'hya': 'ひゃ', 'hyu': 'ひゅ', 'hyo': 'ひょ',
    'bya': 'びゃ', 'byu': 'びゅ', 'byo': 'びょ',
    'pya': 'ぴゃ', 'pyu': 'ぴゅ', 'pyo': 'ぴょ',
    'mya': 'みゃ', 'myu': 'みゅ', 'myo': 'みょ',
    'rya': 'りゃ', 'ryu': 'りゅ', 'ryo': 'りょ',
    'fa': 'ふぁ', 'fi': 'ふぃ', 'fe': 'ふぇ', 'fo': 'ふぉ',
    'a': 'あ', 'i': 'い', 'u': 'う', 'e': 'え', 'o': 'お',
    'ka': 'か', 'ki': 'き', 'ku': 'く', 'ke': 'け', 'ko': 'こ',
    'ga': 'が', 'gi': 'ぎ', 'gu': 'ぐ', 'ge': 'げ', 'go': 'ご',
    'sa': 'さ', 'su': 'す', 'se': 'せ', 'so': 'そ',
    'za': 'ざ', 'ji': 'じ', 'zu': 'ず', 'ze': 'ぜ', 'zo': 'ぞ',
    'ta': 'た', 'te': 'て', 'to': 'と',
    'da': 'だ', 'de': 'で', 'do': 'ど',
    'na': 'な', 'ni': 'に', 'nu': 'ぬ', 'ne': 'ね', 'no': 'の',
    # ふ is the one inconsistently-romanized mora: Unihan spells it 'hu' more often
    # than Hepburn 'fu' here (276 vs 134), so both map to ふ.
    'ha': 'は', 'hi': 'ひ', 'fu': 'ふ', 'hu': 'ふ', 'he': 'へ', 'ho': 'ほ',
    'ba': 'ば', 'bi': 'び', 'bu': 'ぶ', 'be': 'べ', 'bo': 'ぼ',
    'pa': 'ぱ', 'pi': 'ぴ', 'pu': 'ぷ', 'pe': 'ぺ', 'po': 'ぽ',
    'ma': 'ま', 'mi': 'み', 'mu': 'む', 'me': 'め', 'mo': 'も',
    'ya': 'や', 'yu': 'ゆ', 'yo': 'よ',
    'ra': 'ら', 'ri': 'り', 'ru': 'る', 're': 'れ', 'ro': 'ろ',
    'wa': 'わ', 'wo': 'を', 'wi': 'ゐ', 'we': 'ゑ',
}
_SYL_LENS = (4, 3, 2, 1)         # greedy longest-match window (shya/chyu/…)


def _hira_to_kata(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        out.append(chr(cp + 0x60) if 0x3041 <= cp <= 0x3096 else ch)
    return ''.join(out)


def romaji_to_kana(text: str, katakana: bool = False) -> str:
    """Convert a Hepburn romaji reading to kana (hiragana, or katakana when
    `katakana`). A value already containing kana is returned unchanged; '.' / '-'
    / ' ' markers pass through, as do unrecognised characters."""
    if not text:
        return ''
    if any('぀' <= c <= 'ヿ' for c in text):
        return text                              # already kana — no-op
    s = text.lower()
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in ('.', '-', ' '):
            out.append(ch)
            i += 1
            continue
        if ch == 'n':                            # moraic ん vs na/ni/nya…
            nxt = s[i + 1] if i + 1 < n else ''
            if nxt == "'":
                out.append('ん')
                i += 2
                continue
            if nxt == '' or nxt not in 'aiueoy':
                out.append('ん')
                i += 1
                continue
        if s[i:i + 3] == 'tch':                  # Hepburn geminate of ち
            out.append('っ')
            i += 1
            continue
        if ch not in 'aiueon' and i + 1 < n and s[i + 1] == ch:   # っ + consonant
            out.append('っ')
            i += 1
            continue
        for L in _SYL_LENS:
            syl = s[i:i + L]
            if syl in _ROMAJI_KANA:
                out.append(_ROMAJI_KANA[syl])
                i += L
                break
        else:
            out.append(s[i])                     # unrecognised — pass through
            i += 1
    kana = ''.join(out)
    return _hira_to_kata(kana) if katakana else kana
