from flask import Flask, render_template, request, jsonify
import json
import os
import pandas as pd
import regex

#import pinyin_jyutping


# Create a Flask application
app = Flask(__name__)


# pre-loads all the json data for the character sets
character_sets = []
for character_set in os.listdir('charactersets'):
    try:
        with open('charactersets/' + character_set, 'r', encoding='utf-8') as file:
            character_sets.append(json.load(file))
    
    except FileNotFoundError:
        # Log the error or print a message to help identify the issue
        print(f"File not found: {character_set}")

    except Exception as e:
        # Log the error or print a message to help identify the issue
        print(f"Error loading JSON file: {e}")

character_sets.sort(key=lambda x: x['label'])

# Load only columns used by current routes to reduce memory usage.
char_info_columns = [
    'kFrequency',
    'jd_freq',
    'jd_grade',
    'jd_romaji_kun',
    'jd_romaji_on',
    'kCantonese',
    'kTang',
    'jd_kor_r',
    'jd_viet',
]

mandarin_def_columns = [
    'character',
    'pinyin_num',
    'pinyin_accent',
    'definitions',
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
    character_info = char_info_df.loc[character]
    #TODO: fix some traditional characters not appearing in the lookup

    out = {}

    # Adds an element for Mandarin defintions and readings
    if json_data['chineseMandarinCheckbox']:
        try:
            mandarin_readings = mand_def_df[mand_def_df['character'] == character]
            readings = []
            for i, reading in mandarin_readings.iterrows():
                pinyin_num = reading['pinyin_num']
                tone = str(pinyin_num)[-1] if pinyin_num is not None else '5'
                defs = reading['definitions']
                if defs is None:
                    definitions = []
                else:
                    definitions = [str(d) for d in list(defs)]
                readings.append({
                    'pinyin_accent': str(reading['pinyin_accent']),
                    'tone': tone,
                    'definitions': definitions,
                })
            out['mandarin'] = {'readings': readings}
        except Exception:
            out['mandarin'] = {'error': 'error with dictionary lookup!!'}

    # Adds an element for Cantonese readings
    if json_data['chineseCantoneseCheckbox']:
        try:
            canto_readings = character_info['kCantonese']
            readings = [[canto_readings[:-1], canto_readings[-1]]]
            out['cantonese'] = {
                'segments': [
                    {'text': r[0], 'tone': str(r[1])}
                    for r in readings
                ]
            }
        except Exception:
            out['cantonese'] = {'error': 'No Cantonese Reading Found'}

    if json_data['chineseTangCheckbox']:
        try:
            tang_readings = character_info['kTang']
            out['tang'] = {'text': ', '.join(tang_readings.lower().split())}
        except Exception:
            out['tang'] = {'error': 'No Middle Chinese Readings'}

    if json_data['japaneseKunCheckbox']:
        try:
            kun_readings = character_info['jd_romaji_kun']
            out['japanese_kun'] = {'items': [str(x) for x in list(kun_readings)]}
        except Exception:
            out['japanese_kun'] = {'error': 'No Kun-Readings'}

    if json_data['japaneseOnCheckbox']:
        try:
            on_readings = character_info['jd_romaji_on']
            out['japanese_on'] = {'items': [str(x) for x in list(on_readings)]}
        except Exception:
            out['japanese_on'] = {'error': 'No On-Readings'}

    if json_data['koreanCheckbox']:
        try:
            korean_readings = character_info['jd_kor_r']
            out['korean'] = {'items': [str(x) for x in list(korean_readings)]}
        except Exception:
            out['korean'] = {'error': 'No Korean Readings'}

    if json_data['vietnameseCheckbox']:
        try:
            viet_readings = character_info['jd_viet']
            out['vietnamese'] = {'items': [str(x) for x in list(viet_readings)]}
        except Exception:
            out['vietnamese'] = {'error': 'No Vietnamese Readings'}

    return out


# Run the application
if __name__ == '__main__':
    app.run(debug=True)