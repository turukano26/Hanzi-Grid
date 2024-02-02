from flask import Flask, render_template, request, jsonify
import json
import os
import pandas as pd
import regex

#import pinyin_jyutping


# Create a Flask application
app = Flask(__name__)

# load dictionaries
#jyut = pinyin_jyutping.PinyinJyutping()


tone_color_dict = {
    '1': '#e32200',
    '2': '#f2cf05',
    '3': '#17a30a',
    '4': '#008fcc',
    '5': '#8f8f8f',
    '6': '#aa8f2f'
}

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

char_info_df = pd.read_parquet('df.parquet')
mand_def_df = pd.read_parquet('mandarin_eng_dictionary.parquet')
        

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

    # a string that accumulates html elements based on which language options are enabled
    return_str = ''
    
    # Adds an element for the chinese simplified and traditional variants
    """if json_data['chineseSimpTradCheckbox']:
        try:
            return_str += character_entry.simp + " | " + character_entry.trad + '<br><br>'
        except:
            return_str += 'error with dictionary lookup!!'"""


    # Adds an element for Mandarin defintions and readings
    if json_data['chineseMandarinCheckbox']:
        try:
            mandarin_readings = mand_def_df[mand_def_df['character'] == character]
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Mandarin</span><p>'
            for i, reading in mandarin_readings.iterrows():
                return_str += f'<span style="color:{tone_color_dict[reading['pinyin_num'][-1]]}; font-size: 30px "> • {reading['pinyin_accent']} </span><br>'

                for definition in reading['definitions']:
                    return_str += f' - {definition} <br>'
                return_str += '<br>'
        except:
            return_str += '<hr>error with dictionary lookup!!'


    # Adds an element for Cantonese readings
    if json_data['chineseCantoneseCheckbox']:
        try:
            canto_readings = character_info['kCantonese']
            #readings = [[r[:-1], r[-1]]for r in canto_readings]
            readings = [[canto_readings[:-1], canto_readings[-1]]]

            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Cantonese</span><p>'

            for i, (reading, tone) in enumerate(readings):
                return_str += f'<span style="color:{tone_color_dict[tone]}; font-size: 30px">{reading}{',' if i < len([0])-1 else ''} </span>'
            
        except:
            return_str += '<hr>No Cantonese Reading Found<hr>'


    if json_data['chineseTangCheckbox']:
        try:
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Middle Chinese</span><p>'
            tang_readings = character_info['kTang']
            return_str += f'<span style="color:#333333 ;font-size: 30px">{", ".join(tang_readings.lower().split())}</span>'

        except:
            return_str += 'No Middle Chinese Readings'


    if json_data['japaneseKunCheckbox']:
        try:
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Kun-Reading</span><p>'
            kun_readings = character_info['jd_romaji_kun']
            return_str += f'<span style="color:#333333 ;font-size: 30px">{", ".join(kun_readings)}</span>'

        except:
            return_str += 'No Kun-Readings'


    if json_data['japaneseOnCheckbox']:
        try:
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">On-Reading</span><p>'
            on_readings = character_info['jd_romaji_on']
            return_str += f'<span style="color:#333333 ;font-size: 30px">{", ".join(on_readings)}</span>'

        except:
            return_str += 'No On-Readings'


    if json_data['koreanCheckbox']:
        try:
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Korean Reading</span><p>'
            korean_readings = character_info['jd_kor_r']
            return_str += f'<span style="color:#333333 ;font-size: 30px">{", ".join(korean_readings)}</span>'

        except:
            return_str += 'No Korean Readings'


    if json_data['vietnameseCheckbox']:
        try:
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Vietnamese Reading</span><p>'
            viet_readings = character_info['jd_viet']
            return_str += f'<span style="color:#333333 ;font-size: 30px">{", ".join(viet_readings)}</span>'

        except:
            return_str += 'No Vietnamese Readings'


    return return_str


# Run the application
if __name__ == '__main__':
    app.run(debug=True)