from flask import Flask, render_template, request, jsonify
from chinese_english_lookup import Dictionary
from pypinyin.contrib.tone_convert import to_tone
import json
# Create a Flask application
app = Flask(__name__)
d = Dictionary()

tone_color_dict = {
    '1': '#e32200',
    '2': '#f2cf05',
    '3': '#17a30a',
    '4': '#008fcc',
    '5': '#8f8f8f'
}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_click_on_character', methods=['POST'])
def process_click_on_character():
    character = request.form['character']
    # Replace with your actual Python function
    result = create_character_info_sheet(character)
    return jsonify(result=result)


@app.route('/get_input_strings')
def get_input_strings():
    input_strings = load_input_strings_from_file()
    return jsonify({"inputStrings": input_strings})


def load_input_strings_from_file():
    try:
        with open('character_sets.json', 'r', encoding='utf-8') as file:
            input_strings = json.load(file)
        return input_strings
    except FileNotFoundError:
        # Log the error or print a message to help identify the issue
        print("File not found: 'static/character_sets.json'")
        return []
    except Exception as e:
        # Log the error or print a message to help identify the issue
        print(f"Error loading JSON file: {e}")
        return []


def create_character_info_sheet(character):

    return_str = ''
    character_entry = d.lookup(character)
    return_str += character_entry.simp + " | " + character_entry.trad + '<br><br>'

    for dict_entry in character_entry.definition_entries:
        return_str += '<span style="color:' + \
            tone_color_dict[dict_entry.pinyin[-1]] + \
            '; font-size: 30px ">' + " • " + \
            to_tone(dict_entry.pinyin) + '</span>  '

        for definition in dict_entry.definitions:
            return_str += " - " + definition + '<br>'
        return_str += '<br>'

    return return_str


# Run the application
if __name__ == '__main__':
    app.run(debug=True)
