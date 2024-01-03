from flask import Flask, render_template, request, jsonify
from chinese_english_lookup import Dictionary
from pypinyin.contrib.tone_convert import to_tone
import json
from hanziconv import HanziConv
import os
import pinyin_jyutping

# Create a Flask application
app = Flask(__name__)
d = Dictionary()
j = pinyin_jyutping.PinyinJyutping()


tone_color_dict = {
    '1': '#e32200',
    '2': '#f2cf05',
    '3': '#17a30a',
    '4': '#008fcc',
    '5': '#8f8f8f',
    '6': '#aa8f2f'
}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_click_on_character', methods=['POST'])
def process_click_on_character():
    result = create_character_info_sheet(request.get_json())
    return jsonify(result=result)


@app.route('/get_input_strings', methods=['POST'])
def get_input_strings():
    input_strings = load_input_strings_from_file()
    return jsonify({"inputStrings": input_strings})


def load_input_strings_from_file():
    input_strings = []
    for character_set in os.listdir('charactersets'):
        try:
            with open('charactersets/' + character_set, 'r', encoding='utf-8') as file:
                input_strings.append(json.load(file))
        
        except FileNotFoundError:
            # Log the error or print a message to help identify the issue
            print(f"File not found: {character_set}")

        except Exception as e:
            # Log the error or print a message to help identify the issue
            print(f"Error loading JSON file: {e}")

    return input_strings



def create_character_info_sheet(json_data):

    character = json_data['character']
    character_entry = d.lookup(character)
    #TODO: fix some traditional characters not appearing in the lookup

    # a string that accumulates html elements based on which language options are enabled
    return_str = ''
    
    # Adds an element for the chinese simplified and traditional variants
    if json_data['chineseSimpTradCheckbox']:
        try:
            return_str += character_entry.simp + " | " + character_entry.trad + '<br><br>'
        except:
            return_str += 'error with dictionary lookup!!'

    # Adds an element for Cantonese readings
    if json_data['chineseCantoneseCheckbox']:
        try:
            readings = zip(j.jyutping_all_solutions(character)['solutions'][0], [x[-1] for x in j.jyutping_all_solutions(character, tone_numbers=True)['solutions'][0]])
            num_of_readings = len(j.jyutping_all_solutions(character)['solutions'][0])
            return_str += '<span style="color:#999999 ;font-size: 12px">Cantonese</span><p>'
            for i, (reading, tone) in enumerate(readings):
                return_str += f'<span style="color:{tone_color_dict[tone]}; font-size: 30px">{reading}{',' if i < num_of_readings-1 else ''} </span>'
            return_str += '</p>---------------------'
        except:
            return_str += 'No Cantonese Reading Found'

    # Adds an element for Mandarin defintions and readings
    if json_data['chineseMandarinCheckbox']:
        try:
            return_str += '<span style="color:#999999 ;font-size: 12px">Mandarin</span><p>'
            for dict_entry in character_entry.definition_entries:
                return_str += f'<span style="color:{tone_color_dict[dict_entry.pinyin[-1]]}; font-size: 30px "> • {to_tone(dict_entry.pinyin)} </span>'

                for definition in dict_entry.definitions:
                    return_str += f' - {definition} <br>'
                return_str += '<br>'
        except:
            return_str += 'error with dictionary lookup!!'

    return return_str


# Run the application
if __name__ == '__main__':
    app.run(debug=True)
