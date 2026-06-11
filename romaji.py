"""Kana → Hepburn romanization.

Single shared home for `_kata_to_hira` / `_ROMAJI` / `_kana_to_romaji`, imported
by both `app.py` (the `kana_romaji` TRANSFORM) and `scripts/dedup_readings.py`
(the Japanese kana/romaji bridge). Kept import-light (stdlib only) so the build
scripts can import it without pulling in Flask/parquet.
"""


def _kata_to_hira(text: str) -> str:
    result = []
    for ch in text:
        cp = ord(ch)
        if 0x30A1 <= cp <= 0x30F6:
            result.append(chr(cp - 0x60))
        else:
            result.append(ch)
    return ''.join(result)


_ROMAJI: dict[str, str] = {
    'きゃ': 'kya', 'きゅ': 'kyu', 'きょ': 'kyo',
    'しゃ': 'sha', 'しゅ': 'shu', 'しょ': 'sho',
    'ちゃ': 'cha', 'ちゅ': 'chu', 'ちょ': 'cho',
    'にゃ': 'nya', 'にゅ': 'nyu', 'にょ': 'nyo',
    'ひゃ': 'hya', 'ひゅ': 'hyu', 'ひょ': 'hyo',
    'みゃ': 'mya', 'みゅ': 'myu', 'みょ': 'myo',
    'りゃ': 'rya', 'りゅ': 'ryu', 'りょ': 'ryo',
    'ぎゃ': 'gya', 'ぎゅ': 'gyu', 'ぎょ': 'gyo',
    'じゃ': 'ja',  'じゅ': 'ju',  'じょ': 'jo',
    'ぢゃ': 'ja',  'ぢゅ': 'ju',  'ぢょ': 'jo',
    'びゃ': 'bya', 'びゅ': 'byu', 'びょ': 'byo',
    'ぴゃ': 'pya', 'ぴゅ': 'pyu', 'ぴょ': 'pyo',
    'ふぁ': 'fa',  'ふぃ': 'fi',  'ふぇ': 'fe',  'ふぉ': 'fo',
    'てぃ': 'ti',  'でぃ': 'di',  'でゅ': 'dyu',
    'あ': 'a',  'い': 'i',  'う': 'u',  'え': 'e',  'お': 'o',
    'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
    'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
    'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
    'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
    'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
    'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
    'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
    'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
    'わ': 'wa', 'ゐ': 'i',  'ゑ': 'e',  'を': 'o',
    'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
    'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
    'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
    'ぁ': 'a',  'ぃ': 'i',  'ぅ': 'u',  'ぇ': 'e',  'ぉ': 'o',
    'ゃ': 'ya', 'ゅ': 'yu', 'ょ': 'yo', 'ゎ': 'wa',
}


def _kana_to_romaji(kana: str) -> str:
    """Convert kana to lowercase Hepburn, preserving okurigana '.' and affix '-' markers."""
    hira = _kata_to_hira(kana)
    if not hira:
        return ''
    out: list[str] = []
    i = 0
    while i < len(hira):
        ch = hira[i]
        if ch in ('.',  '-', 'ー'):   # preserve markers; drop long-vowel mark
            if ch != 'ー':
                out.append(ch)
            i += 1
            continue
        if ch == 'っ':
            if i + 1 < len(hira):
                nxt = _ROMAJI.get(hira[i + 1: i + 3]) or _ROMAJI.get(hira[i + 1], '')
                if nxt:
                    out.append(nxt[0])
            i += 1
            continue
        if ch == 'ん':
            if i + 1 < len(hira) and hira[i + 1] in 'あいうえおやゆよぁぃぅぇぉゃゅょん':
                out.append("n'")
            else:
                out.append('n')
            i += 1
            continue
        if i + 1 < len(hira):
            pair = hira[i: i + 2]
            if pair in _ROMAJI:
                out.append(_ROMAJI[pair])
                i += 2
                continue
        rom = _ROMAJI.get(ch)
        out.append(rom if rom is not None else ch)
        i += 1
    return ''.join(out)
