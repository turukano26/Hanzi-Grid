// script.js

var currentInputString;

// ---- Script variants (Traditional / Simplified / Japanese) ----------------
// A grid's `cells` string may contain variant groups like "{東TJ东S}": one
// glyph per group, each tagged with the scripts (T/S/J) it belongs to. Bare
// characters are identical across all three. `currentScript` selects which
// glyph is displayed; every cell still records all of its variants' codepoints
// (data-variants) so search can match a form that isn't currently shown.
var SCRIPT_KEYS = ['T', 'S', 'J'];
var SCRIPT_FALLBACK = ['T', 'J', 'S']; // tried in order when the selection is absent
var currentScript = localStorage.getItem('csScript') || 'T';

// Split a cells string into tokens: a plain character string, or a variants
// object {T,S,J} (absent scripts omitted). Characters outside any group pass
// through unchanged, so existing sets parse exactly as before.
function parseCells(str) {
    var tokens = [];
    var i = 0;
    while (i < str.length) {
        if (str[i] === '{') {
            var end = str.indexOf('}', i);
            if (end === -1) { tokens.push('{'); i++; continue; } // malformed: literal '{'
            tokens.push(parseVariantGroup(str.slice(i + 1, end)));
            i = end + 1;
        } else {
            var glyph = String.fromCodePoint(str.codePointAt(i));
            tokens.push(glyph);
            i += glyph.length; // step over astral surrogate pairs as one unit
        }
    }
    return tokens;
}

// "東TJ东S" -> {T:'東', J:'東', S:'东'}. Each entry is one glyph followed by its
// 1-3 script tags; an untagged glyph contributes nothing.
function parseVariantGroup(inner) {
    var variants = {};
    var i = 0;
    while (i < inner.length) {
        var glyph = String.fromCodePoint(inner.codePointAt(i));
        i += glyph.length;
        while (i < inner.length && 'TSJ'.indexOf(inner[i]) !== -1) {
            variants[inner[i]] = glyph;
            i++;
        }
    }
    return variants;
}

// The glyph to display for the current script, with fallback exact -> T -> J -> S.
function glyphForToken(token) {
    if (typeof token === 'string') { return token; }
    if (token[currentScript]) { return token[currentScript]; }
    for (var k = 0; k < SCRIPT_FALLBACK.length; k++) {
        if (token[SCRIPT_FALLBACK[k]]) { return token[SCRIPT_FALLBACK[k]]; }
    }
    return '';
}

// Unique hex codepoints across every variant (or the single bare char).
function variantKeys(token) {
    var glyphs = typeof token === 'string'
        ? [token]
        : SCRIPT_KEYS.map(function (k) { return token[k]; }).filter(Boolean);
    var keys = [];
    glyphs.forEach(function (g) {
        var key = g.codePointAt(0).toString(16);
        if (keys.indexOf(key) === -1) { keys.push(key); }
    });
    return keys;
}

// Reflect `script` in state + the toggle UI; optionally persist the choice.
function applyScript(script, persist) {
    currentScript = script;
    if (persist) { localStorage.setItem('csScript', script); }
    var btns = document.querySelectorAll('#scriptToggle .script-btn');
    btns.forEach(function (b) {
        b.classList.toggle('active', b.getAttribute('data-script') === script);
    });
}

// Walk a set's blocks (recursing into sections) and record every script tag
// (T/S/J) that appears in a grid's variant groups into `acc`. Bare characters
// are identical across scripts and contribute nothing.
function collectScripts(blocks, acc) {
    (blocks || []).forEach(function (block) {
        if (!block || typeof block !== 'object') { return; }
        if (block.type === 'grid') {
            parseCells(block.cells || '').forEach(function (token) {
                if (typeof token === 'object') {
                    Object.keys(token).forEach(function (k) { acc[k] = true; });
                }
            });
        }
        if (block.blocks) { collectScripts(block.blocks, acc); }
    });
    return acc;
}

// Choose the active script for a freshly opened set so a *visible* button is
// always the one highlighted: keep the user's persisted choice when this set
// offers it, otherwise snap to the set's optional `defaultScript` (if the set
// uses it) or the first available form. Applied without persisting, so leaving
// for a set that does offer the user's choice restores it. No-op for sets with
// no variant groups (the toggle is hidden anyway).
function resolveActiveScript(characterSet) {
    if (SCRIPT_KEYS.every(function (k) { return !presentScripts[k]; })) { return; }
    var saved = localStorage.getItem('csScript');
    if (saved && presentScripts[saved]) { applyScript(saved, false); return; }
    var target = (characterSet.defaultScript && presentScripts[characterSet.defaultScript])
        ? characterSet.defaultScript
        : SCRIPT_FALLBACK.filter(function (k) { return presentScripts[k]; })[0];
    applyScript(target, false);
}

// Show the script toggle only for sets that actually distinguish scripts, and
// within it only the buttons for forms the set uses: a trad/simp-only set shows
// 繁/简 but not 日, and a set with no variant groups hides the toggle entirely.
// `scripts` is the {T,S,J} membership from collectScripts (presentScripts).
function updateScriptToggle(scripts) {
    var toggle = document.getElementById('scriptToggle');
    if (!toggle) { return; }
    var present = SCRIPT_KEYS.filter(function (k) { return scripts[k]; });
    toggle.hidden = present.length === 0;
    toggle.querySelectorAll('.script-btn').forEach(function (b) {
        b.hidden = scripts[b.getAttribute('data-script')] !== true;
    });
}

function initScriptToggle() {
    var toggle = document.getElementById('scriptToggle');
    if (!toggle) { return; }
    toggle.addEventListener('click', function (e) {
        var btn = e.target.closest('.script-btn');
        if (!btn) { return; }
        applyScript(btn.getAttribute('data-script'), true);
        generateMacroGrid(currentInputString); // re-render with the new forms
    });
    applyScript(currentScript, false); // reflect the initial state
}

// ---- Japanese poem reading aids -------------------------------------------
// A `poem` block is interactive reading flow (clickable Han cells) with kanji
// rendered larger than kana, plus two optional, top-bar-toggled aids: furigana
// (the kana reading shown as ruby above its kanji) and romaji (a Hepburn line
// beneath each verse line). Furigana is authored inline as {base|reading}
// groups, e.g. "{夏|なつ}{山|やま}に"; that same reading feeds the romaji line.
// Both toggles are global (apply to every poem) and persisted to localStorage.

// Kana → Hepburn. Direct port of transcriptions/romaji.py — keep in sync.
function kataToHira(text) {
    var out = '';
    for (var ch of text) {
        var cp = ch.codePointAt(0);
        out += (cp >= 0x30A1 && cp <= 0x30F6) ? String.fromCodePoint(cp - 0x60) : ch;
    }
    return out;
}

// Voicing (dakuten) of a base kana, for expanding the voiced iteration mark ゞ.
var ITER_VOICE = {
    'か': 'が', 'き': 'ぎ', 'く': 'ぐ', 'け': 'げ', 'こ': 'ご',
    'さ': 'ざ', 'し': 'じ', 'す': 'ず', 'せ': 'ぜ', 'そ': 'ぞ',
    'た': 'だ', 'ち': 'ぢ', 'つ': 'づ', 'て': 'で', 'と': 'ど',
    'は': 'ば', 'ひ': 'び', 'ふ': 'ぶ', 'へ': 'べ', 'ほ': 'ぼ',
    'う': 'ゔ'
};

// Expand hiragana iteration marks ゝ/ゞ to the (voiced, for ゞ) preceding kana,
// e.g. ほとゝぎす → ほととぎす, すゝき → すすき.
function expandIteration(hira) {
    var out = [];
    for (var ch of hira) {
        if ((ch === 'ゝ' || ch === 'ゞ') && out.length) {
            var prev = out[out.length - 1];
            out.push(ch === 'ゞ' ? (ITER_VOICE[prev] || prev) : prev);
        } else {
            out.push(ch);
        }
    }
    return out.join('');
}

var ROMAJI = {
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
    'ゃ': 'ya', 'ゅ': 'yu', 'ょ': 'yo', 'ゎ': 'wa'
};

// Convert kana to lowercase Hepburn. Unmapped characters (kanji, punctuation,
// spaces) pass through unchanged, mirroring the Python converter.
function kanaToRomaji(kana) {
    var hira = expandIteration(kataToHira(kana || ''));
    if (!hira) { return ''; }
    var out = [];
    var i = 0;
    while (i < hira.length) {
        var ch = hira[i];
        if (ch === '.' || ch === '-' || ch === 'ー') {  // markers; drop long-vowel mark
            if (ch !== 'ー') { out.push(ch); }
            i += 1;
            continue;
        }
        if (ch === 'は' || ch === 'へ') {  // bound particles: は→wa, へ→e when standing alone
            var prevBoundary = i === 0 || hira[i - 1] === ' ' || hira[i - 1] === '　';
            var nextBoundary = i + 1 >= hira.length || hira[i + 1] === ' ' || hira[i + 1] === '　';
            if (prevBoundary && nextBoundary) {
                out.push(ch === 'は' ? 'wa' : 'e');
                i += 1;
                continue;
            }
        }
        if (ch === 'っ') {  // sokuon: double the next consonant
            if (i + 1 < hira.length) {
                var nxt = ROMAJI[hira.slice(i + 1, i + 3)] || ROMAJI[hira[i + 1]] || '';
                if (nxt) { out.push(nxt[0]); }
            }
            i += 1;
            continue;
        }
        if (ch === 'ん') {
            var after = i + 1 < hira.length ? hira[i + 1] : '';
            out.push(after && 'あいうえおやゆよぁぃぅぇぉゃゅょん'.indexOf(after) !== -1 ? "n'" : 'n');
            i += 1;
            continue;
        }
        var pair = hira.slice(i, i + 2);
        if (pair.length === 2 && ROMAJI[pair]) {
            out.push(ROMAJI[pair]);
            i += 2;
            continue;
        }
        var rom = ROMAJI[ch];
        out.push(rom !== undefined ? rom : ch);
        i += 1;
    }
    return out.join('');
}

// Split one poem line into tokens: {base, reading} furigana groups and plain
// text runs. "{夏|なつ}に" -> [{base:'夏', reading:'なつ'}, {text:'に'}]. A '{'
// without a matching '|'…'}' is treated as literal text.
function parsePoemLine(line) {
    var tokens = [];
    var i = 0;
    while (i < line.length) {
        if (line[i] === '{') {
            var end = line.indexOf('}', i);
            var bar = end === -1 ? -1 : line.indexOf('|', i);
            if (end !== -1 && bar !== -1 && bar < end) {
                tokens.push({ base: line.slice(i + 1, bar), reading: line.slice(bar + 1, end) });
                i = end + 1;
                continue;
            }
        }
        var next = line.indexOf('{', i + 1);
        if (next === -1) { next = line.length; }
        tokens.push({ text: line.slice(i, next) });
        i = next;
    }
    return tokens;
}

// Append text to `parent`, Han characters as clickable study cells and the rest
// (kana, punctuation) as inert text — the poem counterpart of the interactive
// text renderer. Spaces are romaji word separators only (see poemLineRomaji) and
// are not shown in the verse, so authored word breaks don't disturb the kanji.
function appendPoemText(parent, text) {
    for (var ch of text) {
        if (ch === ' ' || ch === '　') {
            continue;
        }
        if (HAN_RE.test(ch)) {
            parent.appendChild(makeCharCell(ch));
        } else {
            parent.appendChild(document.createTextNode(ch));
        }
    }
}

// Romaji for a parsed line: furigana groups contribute their reading, plain
// runs their own kana (unannotated kanji pass through as-is). Spaces in the
// authored source mark word boundaries — collapsed to single spaces here and
// trimmed — so the author controls romaji spacing without affecting the verse.
function poemLineRomaji(tokens) {
    var raw = tokens.map(function (t) {
        return kanaToRomaji(t.reading != null ? t.reading : t.text);
    }).join('');
    return raw.replace(/[\s　]+/g, ' ').trim();
}

var poemFurigana = localStorage.getItem('poemFurigana') !== '0';  // default on
var poemRomaji = localStorage.getItem('poemRomaji') === '1';      // default off

// Reflect the current furigana/romaji state on every rendered poem and the
// top-bar buttons; optionally persist the choice.
function applyPoemToggles(persist) {
    if (persist) {
        localStorage.setItem('poemFurigana', poemFurigana ? '1' : '0');
        localStorage.setItem('poemRomaji', poemRomaji ? '1' : '0');
    }
    document.querySelectorAll('.cs-poem').forEach(function (p) {
        p.classList.toggle('show-furigana', poemFurigana);
        p.classList.toggle('show-romaji', poemRomaji);
    });
    var fb = document.querySelector('#poemToggle [data-aid="furigana"]');
    var rb = document.querySelector('#poemToggle [data-aid="romaji"]');
    if (fb) { fb.classList.toggle('active', poemFurigana); fb.setAttribute('aria-pressed', poemFurigana); }
    if (rb) { rb.classList.toggle('active', poemRomaji); rb.setAttribute('aria-pressed', poemRomaji); }
}

function initPoemToggle() {
    var toggle = document.getElementById('poemToggle');
    if (!toggle) { return; }
    toggle.addEventListener('click', function (e) {
        var btn = e.target.closest('.poem-btn');
        if (!btn) { return; }
        var aid = btn.getAttribute('data-aid');
        if (aid === 'furigana') { poemFurigana = !poemFurigana; }
        else if (aid === 'romaji') { poemRomaji = !poemRomaji; }
        applyPoemToggles(true);
    });
}

function fetchCharacterSetNames() {
    // Make an AJAX request to the Flask endpoint
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/get_character_set_names', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onload = function () {
        if (xhr.status === 200) {
            // Parse the JSON response from the server
            var response = JSON.parse(xhr.responseText);
            var inputStrings = response.charSetNames;

            // Populate the input strings dropdown with labels
            const inputStringsDropdown = document.getElementById('inputStrings');

            // Clear existing options and event listeners before populating
            inputStringsDropdown.innerHTML = '';
            inputStringsDropdown.removeEventListener('change', handleInputChange);


            inputStrings.forEach((inputString, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = inputString;
                inputStringsDropdown.appendChild(option);
            });

            // Pick the initial set: the user's last choice if still present,
            // otherwise "Foundations" on a first-ever visit, otherwise the
            // first available set.
            const savedSet = localStorage.getItem('csSelectedSet');
            let initialIndex = inputStrings.indexOf(savedSet);
            if (initialIndex < 0) { initialIndex = inputStrings.indexOf('Foundations'); }
            if (initialIndex < 0) { initialIndex = 0; }
            inputStringsDropdown.selectedIndex = initialIndex;

            // Event listener to handle input string changes
            inputStringsDropdown.addEventListener('change', handleInputChange);
            function handleInputChange() {
                const selectedIndex = inputStringsDropdown.value;
                const selectedInputString = inputStrings[selectedIndex];
                localStorage.setItem('csSelectedSet', selectedInputString);
                fetchCharacterSet(selectedInputString);
            }

            // Initialize with the chosen set
            fetchCharacterSet(inputStrings[initialIndex]);
        }
    };
    xhr.send('simptrad=0');
}


function fetchCharacterSet(selectedInputString) {
    // Make an AJAX request to the Flask endpoint
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/get_character_set', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onload = function () {
        if (xhr.status === 200) {
            // Parse the JSON response from the server
            var response = JSON.parse(xhr.responseText);
            var characterSet = response.inputString;
            generateMacroGrid(characterSet);
        }
    };
    xhr.send('charSet=' + selectedInputString);
}

var INFO_BOX_TONE_COLORS = {
    '1': '#e32200',
    '2': '#f2cf05',
    '3': '#17a30a',
    '4': '#008fcc',
    '5': '#8f8f8f',
    '6': '#aa8f2f'
};

function escapeHtml(str) {
    if (str == null) {
        return '';
    }
    return String(str).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

function sectionHeader(title) {
    return '<hr><span style="color:#999999 ;font-size: 12px">' + escapeHtml(title) + '</span><p>';
}

// Source attribution is shown only on hover, via a native `title` tooltip —
// invisible otherwise. Browsers fall back to an ancestor's title, so CJK spans
// nested inside a titled element still surface the source on hover.
function titleAttr(text) {
    if (!text) {
        return '';
    }
    return ' title="' + escapeHtml(text) + '"';
}

// Renderer registry. A section's `type` (set server-side from the node's
// render.type) selects the renderer; handler and render.type are independent.
var RENDERERS = {
    readings: function (s) {
        var parts = [sectionHeader(s.title)];
        var readings = (s.data && s.data.readings) || [];
        // Definitions-only (no transcription enabled anywhere): no headword to
        // anchor by, so merge every definition into one flat list.
        var anyTranscription = readings.some(function (r) {
            return r.transcriptions && r.transcriptions.length;
        });
        if (!anyTranscription) {
            readings.forEach(function (r) {
                (r.definitions || []).forEach(function (d) {
                    parts.push('<span class="info-source"' + titleAttr(d.source) + '> - ' +
                        escapeHtml(d.text) + '</span> <br>');
                });
            });
            return parts.join('');
        }
        readings.forEach(function (r) {
            var tr = r.transcriptions || [];
            var toneColor = INFO_BOX_TONE_COLORS[r.tone] || '#333333';
            // Enabled transcriptions inline, primary first (server-ordered).
            var headword = tr.map(function (t) { return escapeHtml(t.value); }).join(' / ');
            var sourcesTitle = (r.sources || []).join(', ');
            parts.push('<span class="info-source" style="color:' + toneColor +
                '; font-size: 30px "' + titleAttr(sourcesTitle) + '> • ' + headword + ' </span><br>');
            (r.definitions || []).forEach(function (d) {
                parts.push('<span class="info-source"' + titleAttr(d.source) + '> - ' +
                    escapeHtml(d.text) + '</span> <br>');
            });
            parts.push('<br>');
        });
        return parts.join('');
    },

    image_gallery: function (s) {
        var parts = [sectionHeader(s.title)];
        var images = (s.data && s.data.images) || [];
        images.forEach(function (img) {
            var src = img.url || img.data;
            if (!src) {
                return;
            }
            parts.push('<div style="display:inline-block; margin:4px; text-align:center; vertical-align:top">');
            parts.push('<img src="' + escapeHtml(src) + '" style="max-height:90px; max-width:90px"><br>');
            if (img.attribution) {
                parts.push('<span style="color:#bbbbbb; font-size:10px">' + escapeHtml(img.attribution) + '</span>');
            }
            parts.push('</div>');
        });
        return parts.join('');
    },

    key_value: function (s) {
        var parts = [sectionHeader(s.title)];
        var rows = (s.data && s.data.rows) || [];
        rows.forEach(function (row) {
            parts.push('<span class="info-source" style="color:#333333; font-size:16px"' +
                titleAttr(row.source) + '>' +
                escapeHtml(row.key) + ': ' + escapeHtml(row.value) + '</span><br>');
        });
        return parts.join('');
    }
};

function renderSections(sections) {
    var parts = [];
    (sections || []).forEach(function (s) {
        var renderer = RENDERERS[s.type];
        if (renderer) {
            parts.push(renderer(s));
        }
    });
    return parts.join('');
}

// ---------------------------------------------------------------------------
// Info-box options: DB-derived menu tree + enabled-leaf state (single
// `infoOptions` localStorage key — kept out of the colour namespace).
// ---------------------------------------------------------------------------
var INFO_TREE = [];
var enabledOptions = new Set();

function eachLeaf(nodes, fn) {
    nodes.forEach(function (n) {
        if (n.children && n.children.length) {
            eachLeaf(n.children, fn);
        } else {
            fn(n);
        }
    });
}

function allLeafIds() {
    var ids = [];
    eachLeaf(INFO_TREE, function (n) { ids.push(n.id); });
    return ids;
}

function defaultLeafIds() {
    var ids = [];
    eachLeaf(INFO_TREE, function (n) { if (n.default) { ids.push(n.id); } });
    return ids;
}

function initEnabledOptions() {
    var valid = new Set(allLeafIds());
    var stored = localStorage.getItem('infoOptions');
    if (stored !== null) {
        var arr = null;
        try { arr = JSON.parse(stored); } catch (e) { arr = null; }
        if (Array.isArray(arr)) {
            // Drop any stale ids (append-only contract: unknown ids are ignored).
            enabledOptions = new Set(arr.filter(function (id) { return valid.has(id); }));
            return;
        }
    }
    enabledOptions = new Set(defaultLeafIds());
}

function saveEnabledOptions() {
    localStorage.setItem('infoOptions', JSON.stringify(Array.from(enabledOptions)));
}

function fetchInfoOptions(callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/get_info_options', true);
    xhr.onload = function () {
        if (xhr.status === 200) {
            INFO_TREE = JSON.parse(xhr.responseText).tree || [];
            initEnabledOptions();
            renderLanguageTree();
        }
        if (callback) {
            callback();
        }
    };
    xhr.send();
}

function refreshInfoBox() {
    var largeBox = document.getElementById('largeBox');
    if (largeBox && largeBox.textContent) {
        fetchCharacterInfo(largeBox.textContent);
    }
}

// Build the nested checkbox menu. Parents toggle their whole subtree and show an
// indeterminate state for partial selection; only leaf ids are ever sent.
function renderLanguageTree() {
    var container = document.getElementById('languageTree');
    if (!container) {
        return;
    }
    container.innerHTML = '';
    INFO_TREE.forEach(function (node) {
        container.appendChild(buildMenuNode(node, 0));
    });
    refreshParentStates();
}

function buildMenuNode(node, depth) {
    var wrapper = document.createElement('div');
    wrapper.className = 'menu-node menu-depth-' + depth;
    var isLeaf = !(node.children && node.children.length);

    var row = document.createElement('label');
    row.className = 'menu-row';
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = isLeaf ? 'menu-leaf' : 'menu-parent';
    var text = document.createElement('span');
    text.textContent = node.label;
    row.appendChild(cb);
    row.appendChild(text);
    wrapper.appendChild(row);

    if (isLeaf) {
        cb.checked = enabledOptions.has(node.id);
        cb.addEventListener('change', function () {
            if (cb.checked) {
                enabledOptions.add(node.id);
            } else {
                enabledOptions.delete(node.id);
            }
            saveEnabledOptions();
            refreshParentStates();
            refreshInfoBox();
        });
        wrapper._leafIds = [node.id];
    } else {
        var childContainer = document.createElement('div');
        childContainer.className = 'menu-children';
        var leafIds = [];
        node.children.forEach(function (child) {
            var childEl = buildMenuNode(child, depth + 1);
            childContainer.appendChild(childEl);
            leafIds = leafIds.concat(childEl._leafIds || []);
        });
        wrapper.appendChild(childContainer);
        wrapper._leafIds = leafIds;
        cb._leafIds = leafIds;
        cb.addEventListener('change', function () {
            var on = cb.checked;
            leafIds.forEach(function (id) {
                if (on) { enabledOptions.add(id); } else { enabledOptions.delete(id); }
            });
            childContainer.querySelectorAll('input.menu-leaf').forEach(function (b) {
                b.checked = on;
            });
            saveEnabledOptions();
            refreshParentStates();
            refreshInfoBox();
        });
    }
    return wrapper;
}

function refreshParentStates() {
    var parents = document.querySelectorAll('#languageTree input.menu-parent');
    parents.forEach(function (cb) {
        var ids = cb._leafIds || [];
        var on = 0;
        ids.forEach(function (id) { if (enabledOptions.has(id)) { on++; } });
        cb.checked = ids.length > 0 && on === ids.length;
        cb.indeterminate = on > 0 && on < ids.length;
    });
}

// Appended to the info-box content so the Menu button scrolls with it and sits
// at the very bottom. The inline onclick is part of the markup, so it survives
// each innerHTML re-render with no rebinding needed.
var INFO_BOX_MENU_BUTTON =
    '<button id="info-popup-menu-btn" class="popup-menu-btn" onclick="openPopupMenu()">Menu</button>';

function fetchCharacterInfo(character) {
    const infoBox = document.getElementById('infoBox');
    var options = Array.from(enabledOptions);

    if (options.length === 0) {
        infoBox.innerHTML = '<span style="color:#666666;">Enable at least one option in Menu &gt; Languages to see character info.</span>' + INFO_BOX_MENU_BUTTON;
        infoBox.scrollTop = 0;
        wrapCjkCharactersInInfoBox(infoBox);
        updateInfoBoxFadeState();
        return;
    }

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/process_click_on_character', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () {
        if (xhr.status === 200) {
            var response = JSON.parse(xhr.responseText);
            infoBox.innerHTML = renderSections(response.sections || []) + INFO_BOX_MENU_BUTTON;
            wrapCjkCharactersInInfoBox(infoBox);
            updateInfoBoxFadeState();
        }
    };

    xhr.send(JSON.stringify({ character: character, options: options }));
}

function updateInfoBoxFadeState() {
    const infoBox = document.getElementById('infoBox');
    if (!infoBox) {
        return;
    }
    infoBox.classList.remove('show-top-fade', 'show-bottom-fade');
}

// Matches Han characters only (hanzi/kanji/hanja) — the clickable, grid-navigable
// units. Kana and Hangul are deliberately excluded: they aren't grid characters.
var INFO_BOX_CJK_REGEX = /[\p{Script=Han}]/gu;

// Walk a subtree and wrap each Han character in its text nodes in a clickable
// span (class `className`), skipping any text already inside `skipSelector`.
// Used both for the info box and for non-interactive character-set text, so a
// character anywhere can be clicked to view it. The spans carry no background
// and no padding/margin, so they never colour or reflow the surrounding text.
function wrapClickableCjk(root, className, skipSelector) {
    if (!root) {
        return;
    }
    var textNodes = [];
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
        if (node.parentElement && node.parentElement.closest(skipSelector)) {
            continue;
        }
        textNodes.push(node);
    }
    for (var i = 0; i < textNodes.length; i++) {
        var textNode = textNodes[i];
        var text = textNode.nodeValue;
        if (!text) {
            continue;
        }
        INFO_BOX_CJK_REGEX.lastIndex = 0;
        if (!INFO_BOX_CJK_REGEX.test(text)) {
            continue;
        }
        INFO_BOX_CJK_REGEX.lastIndex = 0;
        var parent = textNode.parentNode;
        if (!parent) {
            continue;
        }
        var fragment = document.createDocumentFragment();
        var lastIndex = 0;
        var match;
        while ((match = INFO_BOX_CJK_REGEX.exec(text)) !== null) {
            var ch = match[0];
            var start = match.index;
            if (start > lastIndex) {
                fragment.appendChild(document.createTextNode(text.slice(lastIndex, start)));
            }
            var span = document.createElement('span');
            span.className = className;
            span.textContent = ch;
            span.setAttribute('role', 'button');
            span.setAttribute('tabindex', '0');
            span.setAttribute('aria-label', 'View character ' + ch);
            fragment.appendChild(span);
            lastIndex = start + ch.length;
        }
        if (lastIndex < text.length) {
            fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
        }
        parent.replaceChild(fragment, textNode);
    }
}

function wrapCjkCharactersInInfoBox(infoBox) {
    wrapClickableCjk(infoBox, 'info-box-cjk', '.info-box-cjk');
}

// Make Han characters in non-interactive character-set text (prose, headings)
// clickable. Study cells ([data-unicode]) already handle their own clicks and
// keep their colouring; <summary> is skipped so clicking a title still toggles
// its section.
function wrapMacroGridCjk() {
    var macroGrid = document.getElementById('macroGrid');
    wrapClickableCjk(macroGrid, 'cjk-clickable', '[data-unicode], .cjk-clickable, summary');
}

function activateCharacterFromInfoBox(character) {
    var largeBox = document.getElementById('largeBox');
    var colorPicker = document.getElementById('colorPicker');
    var unicodeKey = character.codePointAt(0).toString(16);
    var matchingCells = document.querySelectorAll('span[data-unicode="' + unicodeKey + '"]');

    largeBox.textContent = character;

    var cellColor;
    if (matchingCells.length) {
        cellColor = window.getComputedStyle(matchingCells[0]).backgroundColor;
    } else if (getCellColor(unicodeKey)) {
        cellColor = getCellColor(unicodeKey);
    } else {
        cellColor = '#ffffff';
    }
    largeBox.style.backgroundColor = cellColor;

    fetchCharacterInfo(character);

    if (document.body.classList.contains('paintbrush-cursor') && isColoringEditable()) {
        var selectedColor = colorPicker.value;
        setCellColor(unicodeKey, selectedColor);
        largeBox.style.backgroundColor = selectedColor;
        matchingCells.forEach(function (span) {
            span.style.backgroundColor = selectedColor;
        });
    } else {
        if (matchingCells.length) {
            colorPicker.value = rgbToHex(window.getComputedStyle(matchingCells[0]).backgroundColor);
        } else if (getCellColor(unicodeKey)) {
            colorPicker.value = getCellColor(unicodeKey);
        }
    }
}

function initializeInfoBoxInteractions() {
    const infoBox = document.getElementById('infoBox');
    if (!infoBox) {
        return;
    }

    infoBox.addEventListener('scroll', updateInfoBoxFadeState);
    infoBox.addEventListener('click', function (event) {
        var target = event.target.closest('.info-box-cjk');
        if (!target || !infoBox.contains(target)) {
            return;
        }
        event.preventDefault();
        activateCharacterFromInfoBox(target.textContent);
    });

    infoBox.addEventListener('keydown', function (event) {
        if (event.target.classList && event.target.classList.contains('info-box-cjk')) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                activateCharacterFromInfoBox(event.target.textContent);
                return;
            }
        }
        const step = 40;
        const pageStep = Math.max(120, infoBox.clientHeight - 40);

        if (event.key === 'ArrowDown') {
            infoBox.scrollBy({ top: step, behavior: 'auto' });
            event.preventDefault();
        } else if (event.key === 'ArrowUp') {
            infoBox.scrollBy({ top: -step, behavior: 'auto' });
            event.preventDefault();
        } else if (event.key === 'PageDown' || (event.key === ' ' && !event.shiftKey)) {
            infoBox.scrollBy({ top: pageStep, behavior: 'auto' });
            event.preventDefault();
        } else if (event.key === 'PageUp' || (event.key === ' ' && event.shiftKey)) {
            infoBox.scrollBy({ top: -pageStep, behavior: 'auto' });
            event.preventDefault();
        } else if (event.key === 'Home') {
            infoBox.scrollTo({ top: 0, behavior: 'auto' });
            event.preventDefault();
        } else if (event.key === 'End') {
            infoBox.scrollTo({ top: infoBox.scrollHeight, behavior: 'auto' });
            event.preventDefault();
        }
    });

    updateInfoBoxFadeState();
}

// Delegated handling for clickable Han characters in non-interactive
// character-set text. Attached once to the persistent #macroGrid element, so it
// survives every re-render. Mirrors the info box: click/Enter/Space activates
// the character (large display box + info sheet) without colouring it.
function initializeMacroGridCjkInteractions() {
    const macroGrid = document.getElementById('macroGrid');
    if (!macroGrid) {
        return;
    }
    macroGrid.addEventListener('click', function (event) {
        var target = event.target.closest('.cjk-clickable');
        if (!target || !macroGrid.contains(target)) {
            return;
        }
        event.preventDefault();
        activateCharacterFromInfoBox(target.textContent);
    });
    macroGrid.addEventListener('keydown', function (event) {
        if (event.target.classList && event.target.classList.contains('cjk-clickable')) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                activateCharacterFromInfoBox(event.target.textContent);
            }
        }
    });
}


function fetchSearchResults(searchString, searchType) {
    // Make an AJAX request to the Flask endpoint
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/get_search_results', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onload = function () {
        if (xhr.status === 200) {
            const searchGrid = document.getElementById('searchGrid');
            searchGrid.innerHTML = '';
            // Parse the JSON response from the server
            var response = JSON.parse(xhr.responseText);
            highlightSearchResults(response.search)
            generateCharacterElements(searchGrid, response.search);
        }
    };
    xhr.send('searchString=' + searchString + '&searchType=' + searchType);
}


// ---------------------------------------------------------------------------
// Character-set rendering: recursive typed-block documents (v2). renderBlock
// dispatches on block.type via BLOCK_RENDERERS (mirroring the info sheet's
// RENDERERS); an unknown type is skipped with a console.warn. Cell clicks are
// handled by one delegated listener per container (attachCellDelegation) so a
// large interactive text never attaches thousands of per-cell listeners.
// See docs/flexible_character_sets_plan.md.
// ---------------------------------------------------------------------------
var COLLAPSE_PREFIX = 'csCollapse:';
var HAN_RE = /\p{Script=Han}/u;
// Set true while rendering a set that contains a `poem` block, so the top-bar
// furigana/romaji toggles are shown only when relevant.
var hasPoemBlock = false;

// Script tags (T/S/J) present in the current set's variant groups, so the script
// toggle only offers the forms a set actually distinguishes (and is hidden
// entirely for sets with no variant groups). Computed by collectScripts before
// rendering. See updateScriptToggle / resolveActiveScript.
var presentScripts = {};

// Build one <span data-unicode> study cell, applying any saved colour. No
// per-cell listener — click handling is delegated at the container level.
// `token` is a plain character (search grid, bare cells) or a variants object
// {T,S,J}; the displayed glyph follows the current script, while data-variants
// records every form's codepoint so search can match a hidden variant.
function makeCharCell(token) {
    var glyph = glyphForToken(token);
    var unicodeKey = glyph.codePointAt(0).toString(16);
    var span = document.createElement('span');
    span.textContent = glyph;
    span.setAttribute('data-unicode', unicodeKey);
    span.setAttribute('data-variants', variantKeys(token).join(' '));
    var saved = getCellColor(unicodeKey);
    if (saved) {
        span.style.backgroundColor = saved;
    }
    return span;
}

// Click behaviour for a study cell, shared by grids and interactive text.
function handleCellClick(span) {
    var largeBox = document.getElementById('largeBox');
    var colorPicker = document.getElementById('colorPicker');
    var character = span.textContent;
    var unicodeKey = span.getAttribute('data-unicode');

    // Single-click: show the character in the large box.
    largeBox.textContent = character;
    var cellColor = window.getComputedStyle(span).backgroundColor;
    largeBox.style.backgroundColor = cellColor;

    fetchCharacterInfo(character);

    // In paint mode, colour the cell; otherwise copy its colour to the picker.
    if (document.body.classList.contains('paintbrush-cursor') && isColoringEditable()) {
        var selectedColor = colorPicker.value;
        setCellColor(unicodeKey, selectedColor);
        largeBox.style.backgroundColor = selectedColor;
        span.style.backgroundColor = selectedColor;
    } else {
        colorPicker.value = rgbToHex(cellColor);
    }
}

// One delegated click listener per container, resolving the cell via closest().
// Idempotent so reused containers (e.g. the search grid) aren't double-bound.
function attachCellDelegation(container) {
    if (container._cellDelegated) {
        return;
    }
    container._cellDelegated = true;
    container.addEventListener('click', function (event) {
        var span = event.target.closest('span[data-unicode]');
        if (span && container.contains(span)) {
            handleCellClick(span);
        }
    });
}

// Optional 1-5 heading scale (1 = largest). Out-of-range clamps; missing -> ''.
function sizeClass(size) {
    if (typeof size !== 'number' || isNaN(size)) {
        return '';
    }
    var n = Math.round(size);
    if (n < 1) { n = 1; }
    if (n > 5) { n = 5; }
    return 'cs-size-' + n;
}

var BLOCK_RENDERERS = {
    section: function (block, container) {
        var bodyParent;
        // `collapsed` present => collapsible <details>; its value is only the
        // default. Live state comes from localStorage (csCollapse:<id>).
        if (Object.prototype.hasOwnProperty.call(block, 'collapsed')) {
            var details = document.createElement('details');
            var summary = document.createElement('summary');
            summary.textContent = block.title || '';
            var summaryClass = sizeClass(block.size);
            if (summaryClass) { summary.classList.add(summaryClass); }
            details.appendChild(summary);

            var storageKey = COLLAPSE_PREFIX + block.id;
            var saved = localStorage.getItem(storageKey);
            var collapsedNow = saved !== null ? saved === 'true' : !!block.collapsed;
            details.open = !collapsedNow;
            details.addEventListener('toggle', function () {
                localStorage.setItem(storageKey, (!details.open).toString());
            });
            container.appendChild(details);
            bodyParent = details;
        } else {
            var heading = document.createElement('div');
            heading.className = 'cs-heading';
            var headingClass = sizeClass(block.size);
            if (headingClass) { heading.classList.add(headingClass); }
            heading.textContent = block.title || '';
            container.appendChild(heading);
            bodyParent = container;
        }
        (block.blocks || []).forEach(function (child) {
            renderBlock(child, bodyParent);
        });
    },

    grid: function (block, container) {
        var gridDiv = document.createElement('div');
        gridDiv.className = 'grid';
        parseCells(block.cells || '').forEach(function (token) {
            gridDiv.appendChild(makeCharCell(token));
        });
        attachCellDelegation(gridDiv);
        container.appendChild(gridDiv);
    },

    text: function (block, container) {
        var el = document.createElement('div');
        el.className = 'cs-text';
        var textClass = sizeClass(block.size);
        if (textClass) { el.classList.add(textClass); }
        var text = block.text || '';
        if (block.interactive) {
            // Reading flow: Han chars become live cells; \n -> <br>; everything
            // else (punctuation, spaces) passes through as inert text.
            el.classList.add('cs-interactive');
            for (var ch of text) {
                if (ch === '\n') {
                    el.appendChild(document.createElement('br'));
                } else if (HAN_RE.test(ch)) {
                    el.appendChild(makeCharCell(ch));
                } else {
                    el.appendChild(document.createTextNode(ch));
                }
            }
            attachCellDelegation(el);
        } else {
            // Inert prose — textContent, never innerHTML (no parser/sanitizer).
            el.textContent = text;
        }
        container.appendChild(el);
    },

    // Japanese poem: one verse line per source line, kanji larger than kana and
    // clickable, with toggled furigana (ruby) + romaji (line beneath) aids. The
    // {base|reading} furigana groups are authored inline (see parsePoemLine).
    poem: function (block, container) {
        hasPoemBlock = true;
        var poem = document.createElement('div');
        poem.className = 'cs-poem';
        var poemClass = sizeClass(block.size);
        if (poemClass) { poem.classList.add(poemClass); }

        (block.text || '').split('\n').forEach(function (line) {
            var tokens = parsePoemLine(line);
            var lineEl = document.createElement('div');
            lineEl.className = 'poem-line';
            tokens.forEach(function (t) {
                if (t.reading != null) {
                    var ruby = document.createElement('ruby');
                    appendPoemText(ruby, t.base);
                    var rt = document.createElement('rt');
                    rt.textContent = t.reading;
                    ruby.appendChild(rt);
                    lineEl.appendChild(ruby);
                } else {
                    appendPoemText(lineEl, t.text);
                }
            });
            poem.appendChild(lineEl);

            if (line.trim() !== '') {
                var rom = document.createElement('div');
                rom.className = 'poem-romaji';
                rom.textContent = poemLineRomaji(tokens);
                poem.appendChild(rom);
            }
        });

        attachCellDelegation(poem);
        poem.classList.toggle('show-furigana', poemFurigana);
        poem.classList.toggle('show-romaji', poemRomaji);
        container.appendChild(poem);
    }
};

function renderBlock(block, container) {
    if (!block || typeof block !== 'object') {
        return;
    }
    var renderer = BLOCK_RENDERERS[block.type];
    if (!renderer) {
        console.warn('Unknown character-set block type:', block.type);
        return;
    }
    renderer(block, container);
}

function generateMacroGrid(characterSet) {
    const macroGrid = document.getElementById('macroGrid');
    macroGrid.innerHTML = ''; // Clear the existing grid
    currentInputString = characterSet; // Update the global
    if (!characterSet) {
        return;
    }
    hasPoemBlock = false;
    presentScripts = collectScripts(characterSet.blocks, {});
    resolveActiveScript(characterSet); // snap to a form this set offers, before render
    (characterSet.blocks || []).forEach(function (block) {
        renderBlock(block, macroGrid);
    });
    wrapMacroGridCjk();
    var poemToggle = document.getElementById('poemToggle');
    if (poemToggle) { poemToggle.hidden = !hasPoemBlock; }
    updateScriptToggle(presentScripts);
    applyPoemToggles(false); // sync newly rendered poems to the current state
}

// Used by the search grid: append bare study cells to a (reused) container,
// wiring up delegated click handling once.
function generateCharacterElements(parentGrid, inputString) {
    attachCellDelegation(parentGrid);
    for (var character of inputString) {
        parentGrid.appendChild(makeCharCell(character));
    }
}

function createMenu() {

    // Event listener to handle color selection and update the large box and cell color
    colorPicker.addEventListener('change', () => {
        const selectedColor = colorPicker.value;
        changeColor(selectedColor);
    });
    // Live-tint the paint-bucket icon/cursor while the picker is being dragged.
    colorPicker.addEventListener('input', updatePaintColorUI);

    // Event listener for the Export Button
    const exportButton = document.getElementById('export')
    exportButton.addEventListener('click', () => {
        exportUserData();
    });

    // Event listener for when a file is selected to Import
    const inputElement = document.getElementById('fileInput');
    inputElement.addEventListener('change', function (e) {
        var file = e.target.files[0];
        // Check if a file is selected
        if (file) {
            // Call the function to add data to localStorage
            addToLocalStorage(file);
        } else {
            console.error('No file selected.');
        }
    });

    // Event listener and function to clear the active color set's colorings.
    const clearButton = document.getElementById('clear')
    clearButton.addEventListener('click', () => {
        var name = getActiveSetName();
        if (name === BLANK_SET_NAME) {
            alert('The "' + BLANK_SET_NAME + '" set is always empty.');
            return;
        }
        if (confirm('Clear all colorings in "' + name + '"?')) {
            var store = loadColorSets();
            store.sets[name] = {};
            saveColorSets();
            generateMacroGrid(currentInputString);
            alert('Color set "' + name + '" cleared.');
        }
    });

    // ----- Color-set switcher + management controls --------------------------
    refreshColorSetSelect();
    const colorSetSelect = document.getElementById('colorSetSelect');
    if (colorSetSelect) {
        colorSetSelect.addEventListener('change', function () {
            switchColorSet(this.value);
        });
    }
    const newColorSetBtn = document.getElementById('newColorSetBtn');
    if (newColorSetBtn) { newColorSetBtn.addEventListener('click', promptCreateColorSet); }
    const newColorSetMenuBtn = document.getElementById('newColorSet');
    if (newColorSetMenuBtn) { newColorSetMenuBtn.addEventListener('click', promptCreateColorSet); }
    const renameColorSetBtn = document.getElementById('renameColorSet');
    if (renameColorSetBtn) { renameColorSetBtn.addEventListener('click', promptRenameColorSet); }
    const deleteColorSetBtn = document.getElementById('deleteColorSet');
    if (deleteColorSetBtn) { deleteColorSetBtn.addEventListener('click', promptDeleteColorSet); }

    // Event listener to open the popup menu
    document.getElementById('open-popup-menu-btn').addEventListener('click', openPopupMenu);

    // The language menu is built dynamically from /get_info_options (see
    // fetchInfoOptions / renderLanguageTree); enabled-leaf state lives in the
    // single `infoOptions` localStorage key, not per-checkbox booleans.
}


// Helper function to convert RGB to HEX
function rgbToHex(rgb) {
    // Extract the RGB values
    const [r, g, b] = rgb.match(/\d+/g);

    // Convert to HEX format
    const hexValue = "#" + (+r).toString(16).padStart(2, '0') +
        (+g).toString(16).padStart(2, '0') +
        (+b).toString(16).padStart(2, '0');
    return hexValue;
}


// Function to create color buttons dynamically
function createColorButtons() {
    var colorButtonsContainer = document.getElementById('colorButtons');

    // Loop through the colors and create buttons
    colors.forEach(function (color) {
        var button = document.createElement('button');
        button.style.backgroundColor = color;
        button.style.marginRight = '10px';
        button.className = 'color-defaults'
        button.onclick = function () {
            changeColor(color);
        };

        colorButtonsContainer.appendChild(button);
    });
}

// Function to update the color of the currently selected character's cell 
// updates the largeBox, colorpicker, localStorage, and any matching grid cells
function changeColor(color) {

    const largeBox = document.getElementById('largeBox');

    // Get the color picker element
    var colorPicker = document.getElementById('colorPicker');
    // Set the value to the selected color
    colorPicker.value = color;

    // Reflect the new selection in the paint-bucket icon and cursor.
    updatePaintColorUI();

    // The Blank set is read-only — picking a colour does nothing.
    if (!isColoringEditable()) { return; }

    // Get the current character from the large box
    const currentCharacter = largeBox.textContent;
    const currentUnicodeKey = currentCharacter.codePointAt(0).toString(16);

    // Update the color for the most recent character in the active color set
    setCellColor(currentUnicodeKey, color);

    // Update the background color of the large box
    largeBox.style.backgroundColor = color;

    // Update the color of the matching cells
    const matchingCells = document.querySelectorAll(`span[data-unicode="${currentUnicodeKey}"]`);
    matchingCells.forEach(cell => {
        cell.style.backgroundColor = color;
    });
}

// ----- Paint-bucket cursor tinting -----------------------------------------
// While painting, the cursor is a paint bucket whose bottom half + drop are
// filled with the selected colour. The four icon paths (mirrored to pour left)
// are kept in sync with the plain, uncoloured outline inline SVG in index.html.
var BUCKET_PATHS = {
    body: 'm19 11-8-8-8.6 8.6a2 2 0 0 0 0 2.8l5.2 5.2c.8.8 2 .8 2.8 0L19 11Z',
    handle: 'm5 2 5 5',
    rim: 'M2 13h15',
    drop: 'M22 20a2 2 0 1 1-4 0c0-1.6 1.7-2.4 2-4 .3 1.6 2 2.4 2 4Z'
};

function currentPaintColor() {
    var picker = document.getElementById('colorPicker');
    return (picker && picker.value) || '#000000';
}

// Build a paint-bucket cursor (32px): the bucket's upper half is white, its
// bottom half + drop are filled with `color`, and a black outline sits on top
// (no halo). Returned as a `cursor` value with the pour-tip hotspot and a
// crosshair fallback.
function paintBucketCursorCss(color) {
    var P = BUCKET_PATHS;
    var allPaths = '<path d="' + P.body + '"/><path d="' + P.handle + '"/>'
        + '<path d="' + P.rim + '"/><path d="' + P.drop + '"/>';
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24">'
        + '<defs><clipPath id="b"><rect x="0" y="13" width="24" height="12"/></clipPath></defs>'
        + '<g transform="translate(24,0) scale(-1,1)">'
        + '<path fill="#ffffff" stroke="none" d="' + P.body + '"/>'  // white bucket (upper half)
        + '<g stroke="none" fill="' + color + '">'                  // paint: bottom half + drop
        + '<path clip-path="url(#b)" d="' + P.body + '"/><path d="' + P.drop + '"/></g>'
        + '<g fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        + allPaths + '</g>'                                         // black outline on top
        + '</g></svg>';
    return "url('data:image/svg+xml," + encodeURIComponent(svg) + "') 4 28, crosshair";
}

// While paint mode is active, set the cursor to a paint bucket filled with the
// currently selected colour. The toolbar button stays a plain outline.
function updatePaintColorUI() {
    // Set the colour-aware bucket cursor while painting; cleared when paint
    // mode is off so the default cursor returns.
    document.body.style.cursor = document.body.classList.contains('paintbrush-cursor')
        ? paintBucketCursorCss(currentPaintColor())
        : '';
}

// Function to toggle the paintbrush mode (cursor + click-to-colour behaviour).
// The `paintbrush-cursor` body class is the single source of truth.
function toggleCursor() {
    const on = document.body.classList.toggle('paintbrush-cursor');
    const btn = document.getElementById('togglePaintBtn');
    if (btn) {
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        btn.title = on ? 'Disable paint mode' : 'Enable paint mode';
    }
    updatePaintColorUI();
}

function intializeInfoColumn() {
    const largeBox = document.getElementById('largeBox');

    largeBox.textContent = '一';
    var unicodeKey = '一'.codePointAt(0).toString(16);

    fetchCharacterInfo('一');

    if (getCellColor(unicodeKey)) {
        largeBox.style.backgroundColor = getCellColor(unicodeKey);
    }
    else {
        largeBox.style.backgroundColor = '#ffffff'
    }


}

function initializeSearchBar() {
    var searchBar = document.getElementById('searchBar');

    // Add an event listener for the 'keyup' event
    searchBar.addEventListener('keyup', function (event) {
        // Check if the key pressed is Enter (key code 13)
        if (event.keyCode === 13) {
            // Call your custom function with the inputted text
            handleSearch(searchBar.value);
        }
    });
}


function handleSearch(searchText) {
    // Removes previous styling from previous searches
    var gridElements = document.querySelectorAll('.grid span');
    gridElements.forEach(function (element) {
        element.style.border = '';
        element.style.padding = '';
    });

    var searchTypeDropdown = document.getElementById('searchTypeDropdown')
    fetchSearchResults(searchText, searchTypeDropdown.value)
}


// Highlights the border of any characters in the search string
function highlightSearchResults(searchResults) {
    for (const character of searchResults) {

        var currentUnicodeKey = character.codePointAt(0).toString(16);
        // Match any variant of a cell, so a hit on a hidden form (e.g. 东 while
        // the grid shows 東) still highlights it. ~= matches one space-separated
        // word within data-variants.
        const clickedCell = document.querySelector(`span[data-variants~="${currentUnicodeKey}"]`);
        if (clickedCell) {
            clickedCell.style.border = '4px solid #000';
            clickedCell.style.padding = '7px';
        }
    }
}

// ===== Named color sets ====================================================
// Colourings are organised into named sets; exactly one is "active" and drawn
// on the grid. Everything lives under a single localStorage key, `colorSets`:
//   { active: "Default", sets: { "Default": {<codepoint>: <hex>}, ... } }
// Legacy installs stored each colouring as a flat hex-codepoint key; the first
// load migrates those into a "Default" set (see loadColorSets). `_colorSets` is
// the cached single source of truth — flat keys are never written again.
//
// "Blank" is a permanent, uneditable, always-empty set: switching to it shows
// the grid with no colourings (it replaces the old Hide Colors toggle). It
// can't be painted into, renamed, or deleted.
var COLOR_SETS_KEY = 'colorSets';
var DEFAULT_SET_NAME = 'Default';
var BLANK_SET_NAME = 'Blank';
var _colorSets = null;

function loadColorSets() {
    if (_colorSets) { return _colorSets; }

    var raw = localStorage.getItem(COLOR_SETS_KEY);
    if (raw) {
        try {
            var parsed = JSON.parse(raw);
            if (parsed && parsed.sets && typeof parsed.sets === 'object') {
                _colorSets = parsed;
            }
        } catch (e) { /* corrupt store: fall through and rebuild */ }
    }

    if (!_colorSets) {
        // First run on this profile: migrate any legacy flat hex-codepoint
        // colour keys into a Default set. Reserved keys (csScript, infoOptions,
        // …) contain non-hex letters and so fail this test, staying untouched.
        var colors = {};
        Object.keys(localStorage).forEach(function (key) {
            if (/^[0-9a-f]+$/i.test(key)) {
                colors[key] = localStorage.getItem(key);
                localStorage.removeItem(key);
            }
        });
        _colorSets = { active: DEFAULT_SET_NAME, sets: {} };
        _colorSets.sets[DEFAULT_SET_NAME] = colors;
        saveColorSets();
    }

    // Invariants. The uneditable Blank set always exists and stays empty.
    _colorSets.sets[BLANK_SET_NAME] = {};
    // There must always be at least one editable set to work in.
    var editable = colorSetNames().filter(function (n) { return n !== BLANK_SET_NAME; });
    if (editable.length === 0) {
        _colorSets.sets[DEFAULT_SET_NAME] = {};
    }
    // `active` must point at a real set.
    if (!_colorSets.sets[_colorSets.active]) {
        _colorSets.active = DEFAULT_SET_NAME;
    }
    return _colorSets;
}

// The Blank set is read-only: it can't be painted, renamed, or deleted.
function isColoringEditable() {
    return getActiveSetName() !== BLANK_SET_NAME;
}

function saveColorSets() {
    localStorage.setItem(COLOR_SETS_KEY, JSON.stringify(_colorSets));
}

function getActiveColors() {
    var store = loadColorSets();
    return store.sets[store.active];
}

function getCellColor(codepoint) {
    return getActiveColors()[codepoint] || null;
}

function setCellColor(codepoint, color) {
    if (!isColoringEditable()) { return; }  // Blank set stays empty
    getActiveColors()[codepoint] = color;
    saveColorSets();
}

function colorSetNames() {
    return Object.keys(loadColorSets().sets);
}

function getActiveSetName() {
    return loadColorSets().active;
}

// Make `name` the active set and reflect the change everywhere: the switcher,
// the grid, and the large-box preview (recoloured to this set's colour for the
// character it's currently showing).
function switchColorSet(name) {
    var store = loadColorSets();
    if (store.sets[name]) {
        store.active = name;
        saveColorSets();
    }
    refreshColorSetSelect();
    generateMacroGrid(currentInputString);

    var largeBox = document.getElementById('largeBox');
    var character = largeBox && largeBox.textContent;
    if (character) {
        var key = character.codePointAt(0).toString(16);
        largeBox.style.backgroundColor = getCellColor(key) || '#ffffff';
    }
}

// Returns the created name, or null if it was empty or already taken.
function createColorSet(name) {
    name = (name || '').trim();
    var store = loadColorSets();
    if (!name || store.sets[name]) { return null; }
    store.sets[name] = {};
    store.active = name;
    saveColorSets();
    return name;
}

function renameColorSet(oldName, newName) {
    newName = (newName || '').trim();
    var store = loadColorSets();
    if (oldName === BLANK_SET_NAME || newName === BLANK_SET_NAME) { return false; }
    if (!newName || !store.sets[oldName] || store.sets[newName]) { return false; }
    store.sets[newName] = store.sets[oldName];
    delete store.sets[oldName];
    if (store.active === oldName) { store.active = newName; }
    saveColorSets();
    return true;
}

function deleteColorSet(name) {
    var store = loadColorSets();
    if (name === BLANK_SET_NAME || !store.sets[name]) { return false; }
    delete store.sets[name];
    if (Object.keys(store.sets).length === 0) {
        store.sets[DEFAULT_SET_NAME] = {};
        store.active = DEFAULT_SET_NAME;
    } else if (store.active === name) {
        store.active = Object.keys(store.sets)[0];
    }
    saveColorSets();
    return true;
}

// Rebuild the top-bar <select> from the current sets, marking the active one.
function refreshColorSetSelect() {
    var select = document.getElementById('colorSetSelect');
    if (!select) { return; }
    var store = loadColorSets();
    select.innerHTML = '';
    colorSetNames().forEach(function (name) {
        var opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (name === store.active) { opt.selected = true; }
        select.appendChild(opt);
    });
}

// ----- Color Sets menu-tab handlers (prompt/confirm/alert match file style) --

function promptCreateColorSet() {
    var name = prompt('Name for the new color set:');
    if (name === null) { return; }
    if (!createColorSet(name)) {
        alert('Please enter a unique, non-empty name.');
        return;
    }
    switchColorSet(getActiveSetName());
}

function promptRenameColorSet() {
    var current = getActiveSetName();
    if (current === BLANK_SET_NAME) {
        alert('The "' + BLANK_SET_NAME + '" set can\'t be renamed.');
        return;
    }
    var name = prompt('Rename "' + current + '" to:', current);
    if (name === null) { return; }
    if (!renameColorSet(current, name)) {
        alert('Please enter a unique, non-empty name.');
        return;
    }
    refreshColorSetSelect();
}

function promptDeleteColorSet() {
    var current = getActiveSetName();
    if (current === BLANK_SET_NAME) {
        alert('The "' + BLANK_SET_NAME + '" set can\'t be deleted.');
        return;
    }
    if (!confirm('Delete color set "' + current + '"? This cannot be undone.')) { return; }
    deleteColorSet(current);
    switchColorSet(getActiveSetName());
}

function exportUserData() {
    // Download the active color set as { name, colors } JSON.
    var store = loadColorSets();
    var dataObject = { name: store.active, colors: getActiveColors() };

    var jsonString = JSON.stringify(dataObject, null, 2);
    var blob = new Blob([jsonString], { type: 'application/json' });
    var link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);

    link.download = (store.active || 'Hanzi_Colourings').replace(/[^\w\-]+/g, '_') + '.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Function to read and parse a JSON file
function readJSONFile(file, callback) {
    var reader = new FileReader();

    reader.onload = function (e) {
        try {
            var data = JSON.parse(e.target.result);
            callback(null, data);
        } catch (error) {
            callback(error, null);
        }
    };

    reader.readAsText(file);
}

// Import a color set from a JSON file as a NEW set (never clobbering existing
// ones). Accepts both the current { name, colors } shape and legacy flat files
// ({ "<codepoint>": "<hex>", ... }).
function addToLocalStorage(jsonFile) {
    readJSONFile(jsonFile, function (error, data) {
        if (error) {
            console.error('Error reading JSON file:', error);
            alert('Could not read that file.');
            return;
        }

        var name, colors;
        if (data && data.colors && typeof data.colors === 'object') {
            name = (data.name || 'Imported').toString();
            colors = data.colors;
        } else if (data && typeof data === 'object') {
            // Legacy flat format: keep only hex-codepoint colour keys.
            name = 'Imported';
            colors = {};
            Object.keys(data).forEach(function (key) {
                if (/^[0-9a-f]+$/i.test(key)) { colors[key] = data[key]; }
            });
        } else {
            alert('That file is not a valid color set.');
            return;
        }

        // De-duplicate the name so existing sets survive, then activate it.
        var store = loadColorSets();
        var unique = name;
        var n = 2;
        while (store.sets[unique]) { unique = name + ' (' + (n++) + ')'; }
        store.sets[unique] = colors;
        saveColorSets();

        switchColorSet(unique);
        console.log('Imported color set "' + unique + '".');
    });
}


// Functions to open, close, and manage the popup menu
function openPopupMenu() {
    document.getElementById('popup-menu-container').style.display = 'flex';
}

function closePopupMenu() {
    document.getElementById('popup-menu-container').style.display = 'none';

    // Menu state is saved live as options are toggled; just refresh the infobox.
    refreshInfoBox();
}

function showSubmenu(submenuId) {
    // Hide all submenus
    const submenus = document.querySelectorAll('.submenu');
    submenus.forEach(submenu => submenu.classList.remove('active'));

    // Show the selected submenu
    document.getElementById(submenuId).classList.add('active');
}

function initializeColumnResizers() {
    const leftResizer = document.getElementById('leftResizer');
    const rightResizer = document.getElementById('rightResizer');
    const infoColumn = document.getElementById('infoColumn');
    const gridColumn = document.getElementById('gridColumn');
    const searchColumn = document.getElementById('searchColumn');

    setupColumnResizer(leftResizer, infoColumn, gridColumn);
    setupColumnResizer(rightResizer, gridColumn, searchColumn);
}

function setupColumnResizer(resizer, leftColumn, rightColumn) {
    if (!resizer || !leftColumn || !rightColumn) {
        return;
    }

    resizer.addEventListener('mousedown', function (event) {
        event.preventDefault();

        const startX = event.clientX;
        const startLeftWidth = leftColumn.getBoundingClientRect().width;
        const startRightWidth = rightColumn.getBoundingClientRect().width;
        const totalWidth = startLeftWidth + startRightWidth;
        const minLeftWidth = parseInt(window.getComputedStyle(leftColumn).minWidth, 10) || 120;
        const minRightWidth = parseInt(window.getComputedStyle(rightColumn).minWidth, 10) || 120;
        const maxLeftWidth = getMaxColumnWidth(leftColumn);
        const maxRightWidth = getMaxColumnWidth(rightColumn);

        document.body.classList.add('resizing');

        function onMouseMove(moveEvent) {
            const deltaX = moveEvent.clientX - startX;
            const minDeltaFromLeft = minLeftWidth - startLeftWidth;
            const maxDeltaFromLeft = maxLeftWidth - startLeftWidth;
            const maxDeltaFromRightMin = startRightWidth - minRightWidth;
            const minDeltaFromRightMax = startRightWidth - maxRightWidth;

            const minAllowedDelta = Math.max(minDeltaFromLeft, minDeltaFromRightMax);
            const maxAllowedDelta = Math.min(maxDeltaFromLeft, maxDeltaFromRightMin);
            const clampedDelta = Math.min(maxAllowedDelta, Math.max(minAllowedDelta, deltaX));

            const newLeftWidth = startLeftWidth + clampedDelta;
            const newRightWidth = totalWidth - newLeftWidth;

            leftColumn.style.flex = `0 0 ${newLeftWidth}px`;
            rightColumn.style.flex = `0 0 ${newRightWidth}px`;
        }

        function onMouseUp() {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            document.body.classList.remove('resizing');
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

function getMaxColumnWidth(column) {
    const maxWidth = window.getComputedStyle(column).maxWidth;
    if (!maxWidth || maxWidth === 'none') {
        return Number.POSITIVE_INFINITY;
    }

    const parsed = parseFloat(maxWidth);
    if (Number.isNaN(parsed)) {
        return Number.POSITIVE_INFINITY;
    }

    return parsed;
}


// List of colors
var colors = [
    '#ff6060',
    '#ADD8E6',
    '#90FF80',
    '#E9B1FF',
    '#fed9a6',
    '#ffffcc',
    '#e5d8bd',
    '#fddaec',
    '#FFFFFF'
];

// Call the functions to create UI elements when the page loads
initScriptToggle();
initPoemToggle();
fetchCharacterSetNames();
createColorButtons();
createMenu();
updatePaintColorUI();  // tint the paint-bucket icon with the initial colour
initializeSearchBar();
// Load the DB-derived menu tree + enabled options first, then seed the info column.
fetchInfoOptions(intializeInfoColumn);
initializeInfoBoxInteractions();
initializeMacroGridCjkInteractions();
initializeColumnResizers();


/* To dos:
Bugs:
fix traditional not getting mandarin definitions
add other backup mandarin defs

Features:
add japanese definitions
add japanese hiragana and katakana

Database Stuff:
cantonese fix to use jyutping
also look at sinopy lib
fix 'u:' in pinyin
*/