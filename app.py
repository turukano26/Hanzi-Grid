from flask import Flask, render_template, request, jsonify
import json
import os
import sqlite3
import pandas as pd
import regex


# ---------------------------------------------------------------------------
# Kana → Hepburn romanization (used by _get_japanese for display)
# ---------------------------------------------------------------------------

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
        if ch in ('.',  '-', '\u30fc'):   # preserve markers; drop long-vowel mark
            if ch != '\u30fc':
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


# Create a Flask application
app = Flask(__name__)


# pre-loads all the json data for the character sets
character_sets = []
for character_set in os.listdir('charactersets'):
    try:
        with open('charactersets/' + character_set, 'r', encoding='utf-8') as file:
            character_sets.append(json.load(file))

    except FileNotFoundError:
        print(f"File not found: {character_set}")

    except Exception as e:
        print(f"Error loading JSON file: {e}")

character_sets.sort(key=lambda x: x['label'])

# ---------------------------------------------------------------------------
# SQLite database (used by character info sheet)
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'omnihanzi.db')
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute("PRAGMA journal_mode = WAL")

# Schema IDs (from schema.sql seed data)
LANG_MANDARIN = 1
LANG_CANTONESE = 2
LANG_MIDDLE_CHINESE = 7
LANG_TOKYO = 10
LANG_KOREAN = 20
LANG_VIETNAMESE = 30

TS_PINYIN = 1
TS_JYUTPING = 10
TS_HEPBURN = 30
TS_KANA = 32
TS_STIMSON = 60
TS_YALE_KO = 42
TS_QUOC_NGU = 50

SOURCE_CEDICT = 1
SOURCE_UNIHAN = 2

# ---------------------------------------------------------------------------
# Parquet DataFrames (still used by search routes)
# ---------------------------------------------------------------------------
char_info_columns = [
    'kFrequency',
    'jd_freq',
    'jd_grade',
    'jd_romaji_kun',
    'jd_romaji_on',
]

mandarin_def_columns = [
    'character',
    'pinyin_num',
]

char_info_df = pd.read_parquet('df.parquet', columns=char_info_columns)
mand_def_df = pd.read_parquet('mandarin_eng_dictionary.parquet', columns=mandarin_def_columns)
        

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_click_on_character', methods=['POST'])
def process_click_on_character():
    result = create_character_info_sheet(request.get_json())
    return jsonify(result=result)


@app.route('/get_character_set_names', methods=['POST'])
def get_character_set_names():
    character_set_names = [i['label'] for i in character_sets]
    return jsonify({"charSetNames": character_set_names})


@app.route('/get_character_set', methods=['POST'])
def get_character_set():
    char_set_name = request.form['charSet']
    for input_string in character_sets:
        if input_string['label'] == char_set_name:
            return jsonify({"inputString": input_string})
        
    return []

@app.route('/get_search_results', methods=['POST'])
def get_search_results():
    search_string = request.form['searchString']
    search_type = request.form['searchType']

    if search_type == 'Character':
         # Use regex to find CJK characters in the input string
        cjk_range = regex.compile(r'\p{Script=Han}')
        cjk_characters = cjk_range.findall(search_string)
        chars_to_return = ''.join(cjk_characters)

        return jsonify({"search": chars_to_return})

    elif search_type == 'Radical':
        pass

    elif search_type == 'Pinyin':

        matches = mand_def_df[mand_def_df['pinyin_num'].apply(lambda x: search_string.lower() == x.lower()[:-1].strip(": ,.-_"))]
        matches = matches.merge(char_info_df, left_on='character', right_index=True).sort_values('kFrequency')
        chars_to_return = ''.join(matches['character'].unique())
        return jsonify({"search": chars_to_return})
        
    elif search_type == 'Romaji':
        #searchs the jd_romaji_kun and jd_romaji_on columns for matches, then returns the characters that match
        exclude = {ord(x): None for x in ':..,-/_ ,'}
        results_kun = char_info_df[char_info_df['jd_romaji_kun'].apply(lambda x: search_string.lower() in [s.translate(exclude).lower() for s in x])]
        results_on = char_info_df[char_info_df['jd_romaji_on'].apply(lambda x: search_string.lower() in [s.translate(exclude).lower() for s in x])]

        chars_to_return = ''.join(list(pd.concat([results_kun, results_on]).sort_values(['jd_freq', 'jd_grade']).index))
        return jsonify({"search": chars_to_return})
    
    else:
        return "wtf"



def create_character_info_sheet(json_data):
    character = json_data['character']
    codepoint = ord(character)
    out = {}

    if json_data.get('chineseMandarinCheckbox'):
        out['mandarin'] = _get_mandarin(codepoint)

    if json_data.get('chineseCantoneseCheckbox'):
        out['cantonese'] = _get_cantonese(codepoint)

    if json_data.get('chineseTangCheckbox'):
        out['tang'] = _get_tang(codepoint)

    if json_data.get('japaneseKunCheckbox'):
        out['japanese_kun'] = _get_japanese(codepoint, 'kun')

    if json_data.get('japaneseOnCheckbox'):
        out['japanese_on'] = _get_japanese(codepoint, 'on')

    if json_data.get('koreanCheckbox'):
        out['korean'] = _get_korean(codepoint)

    if json_data.get('vietnameseCheckbox'):
        out['vietnamese'] = _get_vietnamese(codepoint)

    return out


def _get_mandarin(codepoint):
    # Fetch all Mandarin readings with their source; prefer CEDICT (source 1) over Unihan (source 2)
    rows = db.execute("""
        SELECT r.id, r.tone, ra.source_id, rt.value AS pinyin
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_attestations ra ON ra.reading_id = r.id
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        WHERE e.codepoint = ? AND e.language_id = ? AND rt.transcription_system_id = ?
        ORDER BY e.etymology_order, ra.source_id ASC, r.sort_order
    """, (codepoint, LANG_MANDARIN, TS_PINYIN)).fetchall()

    if not rows:
        return {'error': 'No Mandarin readings found'}

    # Deduplicate by NFC-normalised pinyin, preferring CEDICT rows (lower source_id)
    seen: dict[str, dict] = {}  # pinyin → reading dict
    import unicodedata
    for reading_id, tone, source_id, pinyin in rows:
        key = unicodedata.normalize("NFC", pinyin)
        if key in seen:
            continue  # already recorded a preferred (lower source_id) row

        defs = db.execute("""
            SELECT definition FROM senses
            WHERE reading_id = ? AND source_id = ?
            ORDER BY sort_order
        """, (reading_id, source_id)).fetchall()

        seen[key] = {
            'pinyin_accent': pinyin,
            'tone': tone or '5',
            'definitions': [d[0] for d in defs],
        }

    return {'readings': list(seen.values())}


def _get_cantonese(codepoint):
    rows = db.execute("""
        SELECT r.id, r.tone, rt.value AS jyutping
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        WHERE e.codepoint = ? AND e.language_id = ? AND rt.transcription_system_id = ?
        ORDER BY e.etymology_order, r.sort_order
    """, (codepoint, LANG_CANTONESE, TS_JYUTPING)).fetchall()

    if not rows:
        return {'error': 'No Cantonese Reading Found'}

    # Deduplicate by full jyutping (incl. tone digit); definitions come from
    # CC-Canto senses unioned onto the surviving reading by dedup_readings.py.
    seen: dict[str, dict] = {}  # jyutping → segment
    for reading_id, tone, jyutping in rows:
        if not jyutping or jyutping in seen:
            continue

        # Strip trailing tone digit from jyutping for display
        if jyutping[-1].isdigit():
            text = jyutping[:-1]
            disp_tone = jyutping[-1]
        else:
            text = jyutping
            disp_tone = tone or '1'

        defs = db.execute("""
            SELECT definition FROM senses
            WHERE reading_id = ?
            ORDER BY source_id, sort_order
        """, (reading_id,)).fetchall()
        # CC-Canto prefixes editorial notes with '#'; these aren't glosses.
        definitions = [d[0] for d in defs if not d[0].startswith('#')]

        seen[jyutping] = {
            'text': text,
            'tone': str(disp_tone),
            'definitions': definitions,
        }

    return {'segments': list(seen.values())}


def _get_tang(codepoint):
    rows = db.execute("""
        SELECT rt.value
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        WHERE e.codepoint = ? AND e.language_id = ? AND rt.transcription_system_id = ?
        ORDER BY r.sort_order
    """, (codepoint, LANG_MIDDLE_CHINESE, TS_STIMSON)).fetchall()

    if not rows:
        return {'error': 'No Middle Chinese Readings'}

    return {'text': ', '.join(row[0].lower() for row in rows)}


def _get_japanese(codepoint, category):
    # Prefer kana (TS_KANA=32) as source so we can convert to romaji while
    # preserving okurigana '.' and affix '-' markers. Fall back to stored
    # Hepburn (TS_HEPBURN=30) for any readings that have no kana transcription.
    rows = db.execute("""
        SELECT COALESCE(kana.value, hep.value)
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        LEFT JOIN reading_transcriptions kana
               ON kana.reading_id = r.id AND kana.transcription_system_id = ?
        LEFT JOIN reading_transcriptions hep
               ON hep.reading_id = r.id AND hep.transcription_system_id = ?
        WHERE e.codepoint = ? AND e.language_id = ? AND r.category = ?
          AND (kana.value IS NOT NULL OR hep.value IS NOT NULL)
        ORDER BY r.sort_order
    """, (TS_KANA, TS_HEPBURN, codepoint, LANG_TOKYO, category)).fetchall()

    label = 'Kun' if category == 'kun' else 'On'
    if not rows:
        return {'error': f'No {label}-Readings'}

    seen: set[str] = set()
    items = []
    for (val,) in rows:
        romaji = _kana_to_romaji(val) if any('\u3040' <= c <= '\u30ff' for c in val) else val.lower()
        if romaji not in seen:
            seen.add(romaji)
            items.append(romaji)
    return {'items': items}


def _get_korean(codepoint):
    rows = db.execute("""
        SELECT rt.value
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        WHERE e.codepoint = ? AND e.language_id = ? AND rt.transcription_system_id = ?
        ORDER BY r.sort_order
    """, (codepoint, LANG_KOREAN, TS_YALE_KO)).fetchall()

    if not rows:
        return {'error': 'No Korean Readings'}

    return {'items': [row[0] for row in rows]}


def _get_vietnamese(codepoint):
    rows = db.execute("""
        SELECT rt.value
        FROM readings r
        JOIN etymologies e ON e.id = r.etymology_id
        JOIN reading_transcriptions rt ON rt.reading_id = r.id
        WHERE e.codepoint = ? AND e.language_id = ? AND rt.transcription_system_id = ?
        ORDER BY r.sort_order
    """, (codepoint, LANG_VIETNAMESE, TS_QUOC_NGU)).fetchall()

    if not rows:
        return {'error': 'No Vietnamese Readings'}

    return {'items': [row[0] for row in rows]}


# Run the application
if __name__ == '__main__':
    app.run(debug=True)