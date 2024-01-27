from flask import Flask, render_template, request, jsonify
from chinese_english_lookup import Dictionary
from pypinyin.contrib.tone_convert import to_tone
import json
import os
import pandas as pd
#import pinyin_jyutping


# Create a Flask application
app = Flask(__name__)

# load dictionaries
eng_chin_dict = Dictionary()
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


char_info_df = pd.read_parquet('df.parquet')
        

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
    print(search_type)

    if search_type == 'Character':
        return search_string
    elif search_type == 'Radical':
        pass
    elif search_type == 'Pinyin':
        pass
    elif search_type == 'Romaji':
        result = j.lookup(search_string)
        pass
    else:
        return "wtf"



def create_character_info_sheet(json_data):

    character = json_data['character']
    character_info = char_info_df.loc[character]
    character_entry = eng_chin_dict.lookup(character)
    #TODO: fix some traditional characters not appearing in the lookup

    # a string that accumulates html elements based on which language options are enabled
    return_str = ''
    
    # Adds an element for the chinese simplified and traditional variants
    if json_data['chineseSimpTradCheckbox']:
        try:
            return_str += character_entry.simp + " | " + character_entry.trad + '<br><br>'
        except:
            return_str += 'error with dictionary lookup!!'


    # Adds an element for Mandarin defintions and readings
    if json_data['chineseMandarinCheckbox']:
        try:
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Mandarin</span><p>'
            for dict_entry in character_entry.definition_entries:
                return_str += f'<span style="color:{tone_color_dict[dict_entry.pinyin[-1]]}; font-size: 30px "> • {to_tone(dict_entry.pinyin)} </span><br>'

                for definition in dict_entry.definitions:
                    return_str += f' - {definition} <br>'
                return_str += '<br>'
        except:
            return_str += '<hr>error with dictionary lookup!!'


    # Adds an element for Cantonese readings
    if json_data['chineseCantoneseCheckbox']:
        try:
            """readings = zip(j.jyutping_all_solutions(character)['solutions'][0], [x[-1] for x in jyut.jyutping_all_solutions(character, tone_numbers=True)['solutions'][0]])
            num_of_readings = len(jyut.jyutping_all_solutions(character)['solutions'][0])
            return_str += '<hr><span style="color:#999999 ;font-size: 12px">Cantonese</span><p>'
            for i, (reading, tone) in enumerate(readings):
                return_str += f'<span style="color:{tone_color_dict[tone]}; font-size: 30px">{reading}{',' if i < num_of_readings-1 else ''} </span>'
            return_str += '</p>'"""
            return_str += '<hr>No Cantonese Reading Found<hr>'
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