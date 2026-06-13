// script.js

var currentInputString;

// ---- Script variants (Traditional / Simplified / Japanese) ----------------
// A grid's `cells` string may contain variant groups like "(東TJ东S)": one
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
        if (str[i] === '(') {
            var end = str.indexOf(')', i);
            if (end === -1) { tokens.push('('); i++; continue; } // malformed: literal '('
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

function wrapCjkCharactersInInfoBox(infoBox) {
    if (!infoBox) {
        return;
    }
    var textNodes = [];
    var walker = document.createTreeWalker(infoBox, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
        if (node.parentElement && node.parentElement.closest('.info-box-cjk')) {
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
            span.className = 'info-box-cjk';
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

function activateCharacterFromInfoBox(character) {
    var largeBox = document.getElementById('largeBox');
    var colorPicker = document.getElementById('colorPicker');
    var unicodeKey = character.codePointAt(0).toString(16);
    var matchingCells = document.querySelectorAll('span[data-unicode="' + unicodeKey + '"]');

    largeBox.textContent = character;

    var cellColor;
    if (matchingCells.length) {
        cellColor = window.getComputedStyle(matchingCells[0]).backgroundColor;
    } else if (localStorage.getItem(unicodeKey)) {
        cellColor = localStorage.getItem(unicodeKey);
    } else {
        cellColor = '#ffffff';
    }
    largeBox.style.backgroundColor = cellColor;

    fetchCharacterInfo(character);

    if (document.body.classList.contains('paintbrush-cursor')) {
        var selectedColor = colorPicker.value;
        localStorage.setItem(unicodeKey, selectedColor);
        largeBox.style.backgroundColor = selectedColor;
        matchingCells.forEach(function (span) {
            span.style.backgroundColor = selectedColor;
        });
    } else {
        if (matchingCells.length) {
            colorPicker.value = rgbToHex(window.getComputedStyle(matchingCells[0]).backgroundColor);
        } else if (localStorage.getItem(unicodeKey)) {
            colorPicker.value = localStorage.getItem(unicodeKey);
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
    var saved = localStorage.getItem(unicodeKey);
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
    if (document.body.classList.contains('paintbrush-cursor')) {
        var selectedColor = colorPicker.value;
        localStorage.setItem(unicodeKey, selectedColor);
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
    // Honour a set's preferred script, but only until the user picks one.
    if (!localStorage.getItem('csScript') && characterSet.defaultScript) {
        applyScript(characterSet.defaultScript, false);
    }
    (characterSet.blocks || []).forEach(function (block) {
        renderBlock(block, macroGrid);
    });
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

    // Event listener and function to clear all a user's colorings
    const clearButton = document.getElementById('clear')
    clearButton.addEventListener('click', () => {
        var isConfirmed = confirm('Are you sure you want to clear all your data?');
        // Check the user's response
        if (isConfirmed) {
            // User clicked "OK," proceed with clearing data
            localStorage.clear();
            generateMacroGrid(currentInputString);
            alert('Data cleared successfully!');
        } else {
            // User clicked "Cancel," do nothing
            alert('Data clearing canceled.');
        }
    });

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

    // Get the current character from the large box
    const currentCharacter = largeBox.textContent;
    const currentUnicodeKey = currentCharacter.codePointAt(0).toString(16);

    // Update the color for the most recent character in localStorage
    localStorage.setItem(currentUnicodeKey, color);

    // Update the background color of the large box
    largeBox.style.backgroundColor = color;

    // Update the color of the matching cells
    const matchingCells = document.querySelectorAll(`span[data-unicode="${currentUnicodeKey}"]`);
    matchingCells.forEach(cell => {
        cell.style.backgroundColor = color;
    });
}

// Function to toggle the paintbrush mode (cursor + click-to-colour behaviour).
// The `paintbrush-cursor` body class is the single source of truth.
function toggleCursor() {
    const on = document.body.classList.toggle('paintbrush-cursor');
    const btn = document.getElementById('togglePaintBtn');
    if (btn) {
        btn.textContent = on ? 'Disable Paint Mode' : 'Enable Paint Mode';
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    }
}

// Show/hide all cell colourings. The colours stay in localStorage and on the
// cells' inline styles; a body class just overrides them in CSS, so toggling
// back reveals them unchanged. The hidden/shown choice itself is persisted.
function applyColoringsVisibility(hidden) {
    document.body.classList.toggle('colorings-hidden', hidden);
    const btn = document.getElementById('toggleColoringsBtn');
    if (btn) {
        btn.textContent = hidden ? 'Show Colors' : 'Hide Colors';
        btn.setAttribute('aria-pressed', hidden ? 'true' : 'false');
    }
}

function toggleColorings() {
    const hidden = !document.body.classList.contains('colorings-hidden');
    localStorage.setItem('coloringsHidden', hidden ? 'true' : 'false');
    applyColoringsVisibility(hidden);
}

function intializeInfoColumn() {
    const largeBox = document.getElementById('largeBox');

    largeBox.textContent = '一';
    var unicodeKey = '一'.codePointAt(0).toString(16);

    fetchCharacterInfo('一');

    if (localStorage.getItem(unicodeKey)) {
        largeBox.style.backgroundColor = localStorage.getItem(unicodeKey);
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

function exportUserData() {
    // Exports the user's character colourings into a json file and downloads it.
    // Only colour keys are exported — `infoOptions` (menu state) is a UI
    // preference and is deliberately kept out of colour exports.
    var keys = Object.keys(localStorage);

    var dataObject = {};

    keys.forEach(function (key) {
        // Colour keys are hex codepoints (e.g. "4e00"); skip everything else
        // (infoOptions and any legacy per-checkbox orphans).
        if (!/^[0-9a-f]+$/i.test(key)) {
            return;
        }
        dataObject[key] = localStorage.getItem(key);
    });

    var jsonString = JSON.stringify(dataObject, null, 2);
    var blob = new Blob([jsonString], { type: 'application/json' });
    var link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);

    link.download = 'Hanzi_Colourings.json'; // TODO: Set the download attribute with a user pickedfile name
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

// Function to add data from JSON file to localStorage
function addToLocalStorage(jsonFile) {
    readJSONFile(jsonFile, function (error, data) {
        if (error) {
            console.error('Error reading JSON file:', error);
        } else {
            // Importing colourings must not wipe the user's menu preferences.
            var savedOptions = localStorage.getItem('infoOptions');
            localStorage.clear();
            if (savedOptions !== null) {
                localStorage.setItem('infoOptions', savedOptions);
            }
            // Add each imported key-value pair (colour keys) to localStorage
            Object.keys(data).forEach(function (key) {
                localStorage.setItem(key, data[key]);
            });
            console.log('Data added to localStorage successfully!');
            generateMacroGrid(currentInputString);
        }
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
applyColoringsVisibility(localStorage.getItem('coloringsHidden') === 'true');
fetchCharacterSetNames();
createColorButtons();
createMenu();
initializeSearchBar();
// Load the DB-derived menu tree + enabled options first, then seed the info column.
fetchInfoOptions(intializeInfoColumn);
initializeInfoBoxInteractions();
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