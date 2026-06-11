from flask import Flask, render_template, request, jsonify
import json
import os
import sqlite3
import pandas as pd
import regex

from romaji import _kana_to_romaji



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


# ---------------------------------------------------------------------------
# Info-box: DB-derived menu tree + handler registry
# (see docs/infobox-redesign-plan.md). The reading menu is built from the DB;
# only the tiny overlay.json is hand-authored.
# ---------------------------------------------------------------------------

def _transform_kana_romaji(value):
    """Romanize a kana value to Hepburn; lowercase an already-romaji (orphan
    Unihan) value. Reproduces the old _get_japanese kana/romaji branch."""
    if any('\u3040' <= c <= '\u30ff' for c in value):
        return _kana_to_romaji(value)
    return value.lower()


# Named by transcription_systems.transform; applied after the derived-value
# COALESCE in _fetch_reading_rows.
TRANSFORMS = {
    'kana_romaji': _transform_kana_romaji,
    'lower': str.lower,
}

# Hand-authored overlay: initial checked-state exceptions, category labels, and
# non-reading sources. Everything else in the menu is derived from the DB.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overlay.json'),
          'r', encoding='utf-8') as _ov:
    OVERLAY = json.load(_ov)

_DEFAULT_OFF = set(OVERLAY.get('default_off', []))
_CATEGORY_LABELS = OVERLAY.get('category_labels', {})
_NON_READING_SOURCES = OVERLAY.get('non_reading_sources', [])


def _build_info_tree():
    """Assemble the menu node tree from the DB plus the overlay's non-reading
    sources, once at startup. Each node carries client fields (id, label, default,
    render, children) and server-only fields (handler, language_id, category,
    ts_id, derived_from_ts_id, transform, code) that /get_info_options strips."""
    populated_ts = {row[0] for row in db.execute(
        "SELECT DISTINCT transcription_system_id FROM reading_transcriptions")}

    lang_categories = {}
    for lang_id, cat in db.execute(
            "SELECT DISTINCT e.language_id, r.category FROM readings r "
            "JOIN etymologies e ON e.id = r.etymology_id"):
        lang_categories.setdefault(lang_id, set()).add(cat)

    # Unihan's kDefinition is a generic per-character English gloss that the
    # importer attaches to one primary reading — not a curated per-language
    # definition set. So a Definitions leaf appears only where a language has
    # senses from a *dedicated* dictionary (CEDICT, CC-Canto, KD2…): i.e. any
    # source other than Unihan. This drops the incidental Unihan-only spillover
    # on Korean/Vietnamese/Middle Chinese (rare compatibility/extension
    # codepoints), and self-heals — a real dictionary importer for those
    # languages makes the leaf reappear automatically.
    unihan_row = db.execute("SELECT id FROM sources WHERE short_name = 'Unihan'").fetchone()
    unihan_id = unihan_row[0] if unihan_row else -1
    sense_cats = set()
    for lang_id, cat in db.execute(
            "SELECT DISTINCT e.language_id, r.category FROM senses s "
            "JOIN readings r ON r.id = s.reading_id "
            "JOIN etymologies e ON e.id = r.etymology_id "
            "WHERE s.source_id IS NULL OR s.source_id != ?", (unihan_id,)):
        sense_cats.add((lang_id, cat))

    ts_by_lang = {}
    for ts_id, lang_id, name, code, sort_order, derived_from, transform in db.execute(
            "SELECT id, language_id, name, code, sort_order, derived_from_ts_id, transform "
            "FROM transcription_systems ORDER BY language_id, sort_order"):
        # A leaf renders only if its system is populated, or it derives from a
        # populated one (e.g. Hepburn from Kana). Empty systems are skipped.
        if ts_id not in populated_ts and derived_from not in populated_ts:
            continue
        ts_by_lang.setdefault(lang_id, []).append({
            'ts_id': ts_id, 'name': name, 'code': code, 'sort_order': sort_order,
            'derived_from_ts_id': derived_from, 'transform': transform,
        })

    langs_by_family = {}
    for lang_id, family_id, name, code, sort_order in db.execute(
            "SELECT id, family_id, name, code, sort_order FROM languages "
            "ORDER BY family_id, sort_order"):
        langs_by_family.setdefault(family_id, []).append(
            {'id': lang_id, 'name': name, 'code': code, 'sort_order': sort_order})

    def make_leaves(lang_code, lang_id, category):
        prefix = lang_code + (':' + category if category else '')
        leaves = []
        for i, ts in enumerate(ts_by_lang.get(lang_id, [])):
            leaves.append({
                'id': prefix + ':' + ts['code'], 'label': ts['name'],
                'default': (i == 0),   # primary = lowest sort_order, on by default
                'code': ts['code'], 'ts_id': ts['ts_id'],
                'derived_from_ts_id': ts['derived_from_ts_id'],
                'transform': ts['transform'], 'sort_order': ts['sort_order'],
            })
        if (lang_id, category) in sense_cats:
            leaves.append({'id': prefix + ':definitions', 'label': 'Definitions',
                           'default': True, 'definitions': True})
        for leaf in leaves:
            if leaf['id'] in _DEFAULT_OFF:
                leaf['default'] = False
        return leaves

    families = []
    for fam_id, fam_name, _fam_sort in db.execute(
            "SELECT id, name, sort_order FROM language_families ORDER BY sort_order"):
        fam_children = []
        for lang in langs_by_family.get(fam_id, []):
            lang_id, lang_code = lang['id'], lang['code']
            if not lang_code:        # no stable code -> can't form a leaf id
                continue
            real_cats = sorted(c for c in lang_categories.get(lang_id, set()) if c)
            if real_cats and ts_by_lang.get(lang_id):
                cat_groups = []
                for cat in real_cats:
                    leaves = make_leaves(lang_code, lang_id, cat)
                    if not leaves:
                        continue
                    label = _CATEGORY_LABELS.get(cat, cat)
                    cat_groups.append({
                        'id': lang_code + ':' + cat, 'label': label,
                        'handler': 'readings', 'language_id': lang_id, 'category': cat,
                        'render': {'type': 'readings', 'title': lang['name'] + ' ' + label},
                        'children': leaves,
                    })
                if cat_groups:
                    fam_children.append({'id': lang_code, 'label': lang['name'],
                                         'children': cat_groups})
            else:
                leaves = make_leaves(lang_code, lang_id, None)
                if not leaves:
                    continue
                fam_children.append({
                    'id': lang_code, 'label': lang['name'],
                    'handler': 'readings', 'language_id': lang_id, 'category': None,
                    'render': {'type': 'readings', 'title': lang['name']},
                    'children': leaves,
                })
        if fam_children:
            families.append({'id': 'fam:%d' % fam_id, 'label': fam_name,
                             'children': fam_children})

    # Non-reading sources are self-contained leaves that also fetch (handler).
    for src in _NON_READING_SOURCES:
        families.append({
            'id': src['id'], 'label': src['label'], 'default': src.get('default', False),
            'handler': src['handler'], 'render': src['render'],
        })
    return families


TREE = _build_info_tree()

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


@app.route('/get_info_options', methods=['GET'])
def get_info_options():
    """The menu tree with all server-only fields stripped (handler, language_id,
    ts ids, derived_from/transform). The client gets ids, labels, nesting,
    render.type and default state only."""
    return jsonify({'tree': [_strip_node(n) for n in TREE]})


@app.route('/process_click_on_character', methods=['POST'])
def process_click_on_character():
    payload = request.get_json()
    sections = build_sections(payload['character'], payload.get('options', []))
    return jsonify({'sections': sections})


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


# ---------------------------------------------------------------------------
# Info-box dispatch + handlers
# ---------------------------------------------------------------------------

def _iter_groups(nodes):
    """Yield every data-fetching node (one that carries a 'handler')."""
    for node in nodes:
        if 'handler' in node:
            yield node
        yield from _iter_groups(node.get('children', []))


def _leaf_descendants(node):
    """Leaf nodes under a group. A non-reading source has no children, so the
    group node itself is its only leaf (its id is the toggle)."""
    children = node.get('children')
    if not children:
        return [node]
    out = []
    for child in children:
        out.extend(_leaf_descendants(child))
    return out


def _strip_node(node):
    """Client-facing projection of a tree node (server-only fields removed)."""
    out = {}
    for key in ('id', 'label', 'default', 'render'):
        if key in node:
            out[key] = node[key]
    if 'children' in node:
        out['children'] = [_strip_node(c) for c in node['children']]
    return out


def build_sections(character, enabled_ids):
    """Run each group whose subtree has an enabled leaf, in tree order. A group
    with no enabled leaf is skipped entirely — so heavy handlers (glyph BLOBs)
    only run when their option is toggled on."""
    cp = ord(character)
    enabled = set(enabled_ids)
    sections = []
    for group in _iter_groups(TREE):
        active = [leaf for leaf in _leaf_descendants(group) if leaf['id'] in enabled]
        if not active:
            continue
        if group['handler'] == 'readings':
            transcriptions = [leaf for leaf in active if 'ts_id' in leaf]
            want_defs = any(leaf.get('definitions') for leaf in active)
            data = _handler_readings(cp, group, transcriptions=transcriptions,
                                     definitions=want_defs)
        else:
            data = HANDLERS[group['handler']](cp, group)
        if 'error' not in data:
            sections.append({'id': group['id'], **group['render'], 'data': data})
    return sections


def _fetch_reading_rows(codepoint, language_id, *, transcriptions, category=None,
                        definitions=False):
    """The single SELECT the seven old _get_* functions duplicated. Returns the
    reading rows for one reading group, each resolving every enabled transcription
    as COALESCE(stored[ts], stored[derived_from]) then applying its transform, and
    carrying its attesting sources (+ senses when `definitions`)."""
    ts_order = sorted(transcriptions, key=lambda t: t['sort_order'])

    if category is None:
        reading_rows = db.execute(
            "SELECT r.id, r.tone FROM readings r "
            "JOIN etymologies e ON e.id = r.etymology_id "
            "WHERE e.codepoint = ? AND e.language_id = ? "
            "ORDER BY e.etymology_order, r.sort_order",
            (codepoint, language_id)).fetchall()
    else:
        reading_rows = db.execute(
            "SELECT r.id, r.tone FROM readings r "
            "JOIN etymologies e ON e.id = r.etymology_id "
            "WHERE e.codepoint = ? AND e.language_id = ? AND r.category = ? "
            "ORDER BY e.etymology_order, r.sort_order",
            (codepoint, language_id, category)).fetchall()

    out = []
    for reading_id, tone in reading_rows:
        stored = dict(db.execute(
            "SELECT transcription_system_id, value FROM reading_transcriptions "
            "WHERE reading_id = ?", (reading_id,)).fetchall())

        trs = []
        for ts in ts_order:
            value = stored.get(ts['ts_id'])
            if value is None and ts['derived_from_ts_id'] is not None:
                value = stored.get(ts['derived_from_ts_id'])
            if value is None:
                continue
            if ts['transform']:
                value = TRANSFORMS[ts['transform']](value)
            trs.append({'code': ts['code'], 'label': ts['label'], 'value': value})

        # A reading with transcriptions requested but none resolving is empty.
        # (When no transcription is enabled at all, ts_order is empty and we keep
        # the row for its definitions — the definitions-only path.)
        if ts_order and not trs:
            continue

        sources = [row[0] for row in db.execute(
            "SELECT src.short_name FROM reading_attestations ra "
            "JOIN sources src ON src.id = ra.source_id "
            "WHERE ra.reading_id = ? ORDER BY src.id", (reading_id,)).fetchall()]

        row = {'transcriptions': trs, 'tone': tone, 'sources': sources}
        if definitions:
            row['definitions'] = [
                {'text': d[0], 'source': d[1]} for d in db.execute(
                    "SELECT s.definition, src.short_name FROM senses s "
                    "JOIN sources src ON src.id = s.source_id "
                    "WHERE s.reading_id = ? ORDER BY s.source_id, s.sort_order",
                    (reading_id,)).fetchall()]
        out.append(row)
    return out


def _handler_readings(cp, group, *, transcriptions, definitions):
    rows = _fetch_reading_rows(cp, group['language_id'], transcriptions=transcriptions,
                               category=group['category'], definitions=definitions)
    if not rows:
        return {'error': 'no readings'}
    return {'readings': rows}


def _handler_glyph_images(cp, group):
    rows = db.execute(
        "SELECT image, image_path, attribution FROM character_glyphs "
        "WHERE codepoint = ? ORDER BY sort_order", (cp,)).fetchall()
    images = []
    for image, image_path, attribution in rows:
        if image_path:
            images.append({'url': image_path, 'attribution': attribution or ''})
        elif image is not None:
            import base64
            encoded = base64.b64encode(image).decode('ascii')
            images.append({'data': 'data:image/png;base64,' + encoded,
                           'attribution': attribution or ''})
    if not images:
        return {'error': 'no glyphs'}
    return {'images': images}


def _handler_attributes(cp, group):
    rows = db.execute(
        "SELECT a.key, a.value, src.short_name FROM character_attributes a "
        "LEFT JOIN sources src ON src.id = a.source_id "
        "WHERE a.codepoint = ? ORDER BY a.key", (cp,)).fetchall()
    if not rows:
        return {'error': 'no attributes'}
    return {'rows': [{'key': k, 'value': v, 'source': s or ''} for k, v, s in rows]}


HANDLERS = {
    'readings': _handler_readings,
    'glyph_images': _handler_glyph_images,
    'attributes': _handler_attributes,
}


# Run the application
if __name__ == '__main__':
    app.run(debug=True)