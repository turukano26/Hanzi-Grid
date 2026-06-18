from flask import Flask, render_template, request, jsonify
import json
import os
import sqlite3
import threading
import functools
import regex
import yaml

from transcriptions.romaji import _kana_to_romaji
from transcriptions.hangul_roman import hangul_to_revised, hangul_to_ipa
from transcriptions.pinyin_ipa import pinyin_to_ipa, pinyin_to_ipa_tones
from transcriptions.wade_giles import pinyin_to_wade_giles
from transcriptions.zhuyin import pinyin_to_zhuyin
from transcriptions.jyutping_ipa import jyutping_to_ipa, jyutping_to_ipa_tones
from transcriptions.kana_ipa import kana_to_ipa
from transcriptions.romaji_kana import romaji_to_kana



# Create a Flask application
app = Flask(__name__)


# ---------------------------------------------------------------------------
# Character sets (v2 typed-block YAML documents) — lazy loaded.
# Startup builds only a `label -> filepath` index (parsing each file solely for
# its `label`); each document is read + parsed on demand in /get_character_set
# (LRU-cached). The document body is opaque to the server — it is parsed from
# YAML, returned verbatim as JSON and rendered entirely client-side.
# See docs/flexible_character_sets_plan.md.
# ---------------------------------------------------------------------------
CHARSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'charactersets')


def _build_charset_index():
    index = {}
    for fname in os.listdir(CHARSET_DIR):
        if not fname.endswith(('.yaml', '.yml')):
            continue
        path = os.path.join(CHARSET_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as file:
                label = yaml.safe_load(file).get('label')
            if label:
                index[label] = path
        except Exception as e:
            print(f"Error loading character set {fname}: {e}")
    return index


character_set_index = _build_charset_index()


@functools.lru_cache(maxsize=None)
def _load_character_set(path):
    with open(path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

# ---------------------------------------------------------------------------
# SQLite database (used by character info sheet)
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'omnihanzi.db')


# A single shared sqlite3.Connection is not safe to use from more than one thread
# at a time: the dev server (and gunicorn's thread workers) handle requests on
# multiple threads, so overlapping clicks would corrupt the shared connection's
# cursor state and raise sqlite3.InterfaceError / IndexError (intermittent 500s
# that look like the UI "hanging" on a click). Hand out one lazily-opened
# connection per thread instead; every query is a read and WAL already allows
# concurrent readers across connections. The proxy keeps the module-level `db`
# name and its `db.execute(...)` call sites unchanged.
class _ThreadLocalDB:
    def __init__(self, path):
        self._path = path
        self._local = threading.local()

    def _conn(self):
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return conn

    def execute(self, *args, **kwargs):
        return self._conn().execute(*args, **kwargs)


db = _ThreadLocalDB(DB_PATH)


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
    'hangul_revised': hangul_to_revised,
    'pinyin_ipa': pinyin_to_ipa,
    'pinyin_ipa_tones': pinyin_to_ipa_tones,
    'pinyin_wade_giles': pinyin_to_wade_giles,
    'pinyin_zhuyin': pinyin_to_zhuyin,
    'jyutping_ipa': jyutping_to_ipa,
    'jyutping_ipa_tones': jyutping_to_ipa_tones,
    'hangul_ipa': hangul_to_ipa,
    'kana_ipa': kana_to_ipa,
    # romaji_kana is category-sensitive (on'yomi → katakana, kun'yomi →
    # hiragana), so _resolve_ts_value calls romaji_to_kana directly with the
    # script flag rather than through this single-arg registry; the hiragana
    # default is registered for completeness/standalone use.
    'romaji_kana': romaji_to_kana,
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

# Full derivation metadata for *every* transcription system (not just the enabled
# leaves), keyed by id → (derived_from_ts_id, transform). _resolve_ts_value chains
# through this, so an enabled system can derive from a disabled intermediate one
# (e.g. IPA → Kana → Hepburn for an orphan reading that stores only romaji).
TS_META = {
    row[0]: (row[1], row[2]) for row in db.execute(
        "SELECT id, derived_from_ts_id, transform FROM transcription_systems")
}


def _resolve_ts_value(ts_id, stored, category, _seen=None):
    """One transcription system's value for a reading: its stored value, else the
    value derived from its source system — chaining through `derived_from`, with
    each level applying its own transform. `category` ('on'/'kun') picks the kana
    script for the romaji_kana transform. Returns None when nothing in the chain
    is stored. The `_seen` guard breaks the Hepburn⇄Kana derivation cycle (each is
    the other's source, but only one is ever stored for a given reading)."""
    if _seen is None:
        _seen = set()
    if ts_id in _seen:
        return None
    _seen.add(ts_id)

    value = stored.get(ts_id)
    derived_from, transform = TS_META.get(ts_id, (None, None))
    if value is None:
        if derived_from is None:
            return None
        value = _resolve_ts_value(derived_from, stored, category, _seen)
        if value is None:
            return None

    if transform == 'romaji_kana':
        return romaji_to_kana(value, katakana=(category == 'on'))
    if transform:
        return TRANSFORMS[transform](value)
    return value


# ---------------------------------------------------------------------------
# Search (Pinyin / Romaji) — queried straight from SQLite.
# IDs match the transcription_systems / languages seed data in schema.sql.
# ---------------------------------------------------------------------------
LANG_MANDARIN = 1
LANG_JAPANESE = 10            # Tokyo Standard
TS_PINYIN_NUM = 2            # numbered pinyin, e.g. "sheng1"
TS_HEPBURN = 30             # romaji; derives from kana via the kana_romaji transform
TS_KANA = 32
TS_EUMHUN = 44             # Korean eumhun (음훈) — raw libhangul string, own line
LIBHANGUL_SHORT = 'libhangul'  # sources.short_name, shown as the eumhun line's source

# Punctuation dropped from a romanized reading before matching (okurigana '.',
# affix '-', and stray separators) — mirrors the old jd_romaji search.
_ROMAJI_STRIP = {ord(c): None for c in ':..,-/_ ,'}


def _search_pinyin(search_string):
    """Characters with a Mandarin reading whose toneless numbered pinyin equals
    the query (e.g. "sheng" matches sheng1/sheng4/…). Ordered by Unihan grade
    level (a coarse frequency proxy) then codepoint."""
    rows = db.execute(
        "SELECT c.character FROM characters c "
        "JOIN etymologies e ON e.codepoint = c.codepoint AND e.language_id = ? "
        "JOIN readings r ON r.etymology_id = e.id "
        "JOIN reading_transcriptions rt ON rt.reading_id = r.id "
        "    AND rt.transcription_system_id = ? "
        "LEFT JOIN character_attributes g ON g.codepoint = c.codepoint "
        "    AND g.key = 'grade_level' "
        "WHERE lower(rtrim(rt.value, '0123456789')) = ? "
        "GROUP BY c.codepoint "
        "ORDER BY (g.value IS NULL), CAST(g.value AS INTEGER), c.codepoint",
        (LANG_MANDARIN, TS_PINYIN_NUM, search_string.lower())).fetchall()
    return ''.join(r[0] for r in rows)


def _search_romaji(search_string):
    """Characters with a Japanese (on/kun) reading whose Hepburn romaji equals the
    query. Romaji is resolved exactly as the info sheet does — COALESCE(hepburn,
    kana) then the kana_romaji transform — so directly-stored and kana-derived
    readings match alike. Ordered by Kanjidic frequency rank then Unihan grade."""
    target = search_string.lower()
    rows = db.execute(
        "SELECT c.codepoint, COALESCE(h.value, k.value) AS reading, "
        "  (SELECT value FROM character_attributes "
        "     WHERE codepoint = c.codepoint AND key = 'frequency_rank') AS freq, "
        "  (SELECT value FROM character_attributes "
        "     WHERE codepoint = c.codepoint AND key = 'grade_level') AS grade "
        "FROM characters c "
        "JOIN etymologies e ON e.codepoint = c.codepoint AND e.language_id = ? "
        "JOIN readings r ON r.etymology_id = e.id "
        "LEFT JOIN reading_transcriptions h ON h.reading_id = r.id "
        "    AND h.transcription_system_id = ? "
        "LEFT JOIN reading_transcriptions k ON k.reading_id = r.id "
        "    AND k.transcription_system_id = ? "
        "WHERE h.value IS NOT NULL OR k.value IS NOT NULL",
        (LANG_JAPANESE, TS_HEPBURN, TS_KANA)).fetchall()

    # Romanize in Python (the transforms are Python), then dedupe to one sort key
    # per matching character. Rows lacking the attribute sort last (None -> True).
    matches = {}
    for codepoint, reading, freq, grade in rows:
        romaji = _transform_kana_romaji(reading).translate(_ROMAJI_STRIP).lower()
        if romaji == target:
            matches[codepoint] = (
                freq is None, int(freq) if freq is not None else 0,
                grade is None, int(grade) if grade is not None else 0)
    ordered = sorted(matches, key=lambda cp: matches[cp] + (cp,))
    return ''.join(chr(cp) for cp in ordered)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_info_options', methods=['GET'])
def get_info_options():
    """The menu tree with all server-only fields stripped (handler, language_id,
    ts ids, derived_from/transform). The client gets ids, labels, nesting,
    render.type and default state only."""
    return jsonify({'tree': [_strip_node(n) for n in TREE]})


def _bad_request(message):
    """A uniform JSON 400 so malformed input is a clean error, not a 500."""
    return jsonify({'error': message}), 400


@app.route('/process_click_on_character', methods=['POST'])
def process_click_on_character():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _bad_request('expected a JSON object body')
    character = payload.get('character')
    # build_sections() does ord(character), so it must be exactly one codepoint.
    if not isinstance(character, str) or len(character) != 1:
        return _bad_request("'character' must be a single-character string")
    options = payload.get('options', [])
    if not isinstance(options, list):
        return _bad_request("'options' must be a list")
    sections = build_sections(character, options)
    return jsonify({'sections': sections})


@app.route('/get_character_set_names', methods=['POST'])
def get_character_set_names():
    character_set_names = sorted(character_set_index.keys())
    return jsonify({"charSetNames": character_set_names})


@app.route('/get_character_set', methods=['POST'])
def get_character_set():
    char_set_name = request.form.get('charSet')
    if not char_set_name:
        return _bad_request("missing 'charSet'")
    path = character_set_index.get(char_set_name)
    if path is None:
        return jsonify({"inputString": None})
    return jsonify({"inputString": _load_character_set(path)})

@app.route('/get_search_results', methods=['POST'])
def get_search_results():
    search_string = request.form.get('searchString')
    search_type = request.form.get('searchType')
    if search_string is None or search_type is None:
        return _bad_request("missing 'searchString' or 'searchType'")

    if search_type == 'Character':
         # Use regex to find CJK characters in the input string
        cjk_range = regex.compile(r'\p{Script=Han}')
        cjk_characters = cjk_range.findall(search_string)
        chars_to_return = ''.join(cjk_characters)

        return jsonify({"search": chars_to_return})

    elif search_type == 'Pinyin':
        return jsonify({"search": _search_pinyin(search_string)})

    elif search_type == 'Romaji':
        return jsonify({"search": _search_romaji(search_string)})

    elif search_type == 'Radical':
        # Not implemented yet — return no matches rather than a 500.
        return jsonify({"search": ""})

    else:
        return _bad_request(f"unknown searchType: {search_type!r}")


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
    # Eumhun is a transcription system, but renders on its own line (like a
    # definition) rather than inline in the headword — split it out here.
    inline_ts = [t for t in ts_order if t['ts_id'] != TS_EUMHUN]
    eumhun_enabled = any(t['ts_id'] == TS_EUMHUN for t in ts_order)

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
        for ts in inline_ts:
            value = _resolve_ts_value(ts['ts_id'], stored, category)
            if value is None:
                continue
            trs.append({'code': ts['code'], 'label': ts['label'], 'value': value})

        # Eumhun (raw libhangul string) is shown on its own line, appended to the
        # reading's definitions so it renders like a gloss rather than inline.
        eumhun = stored.get(TS_EUMHUN) if eumhun_enabled else None

        # A reading with inline transcriptions requested but none resolving — and
        # no eumhun to show — is empty. (When nothing inline is enabled, inline_ts
        # is empty and we keep the row for its definitions/eumhun — the
        # definitions-only path.)
        if inline_ts and not trs and eumhun is None:
            continue

        sources = [row[0] for row in db.execute(
            "SELECT src.short_name FROM reading_attestations ra "
            "JOIN sources src ON src.id = ra.source_id "
            "WHERE ra.reading_id = ? ORDER BY src.id", (reading_id,)).fetchall()]

        defs = []
        if definitions:
            defs = [
                {'text': d[0], 'source': d[1]} for d in db.execute(
                    "SELECT s.definition, src.short_name FROM senses s "
                    "JOIN sources src ON src.id = s.source_id "
                    "WHERE s.reading_id = ? ORDER BY s.source_id, s.sort_order",
                    (reading_id,)).fetchall()]
        if eumhun is not None:
            # Eumhun holds one or more comma-separated glosses ("별 성, 세월 성");
            # render each on its own line. Stored value stays verbatim.
            for part in eumhun.split(','):
                part = part.strip()
                if part:
                    defs.append({'text': part, 'source': LIBHANGUL_SHORT})

        row = {'transcriptions': trs, 'tone': tone, 'sources': sources}
        if defs:
            row['definitions'] = defs
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