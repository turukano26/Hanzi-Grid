# Plan: Named / multiple color sets

## Goal

Let users keep several independently-named collections of character colorings
("color sets") and switch between them. Exactly **one set is active at a time**
and is what's drawn on the grid; switching swaps all colorings instantly.

This is a **frontend-only** change — no `app.py`, schema, or backend routes are
touched. All state stays in `localStorage`.

## Decisions (confirmed with user)

- **Display model:** one active set at a time (no overlay/blending).
- **UI location:** compact set dropdown in the top toolbar for quick switching;
  create / rename / delete live in the existing **Color Sets** menu tab next to
  Export/Import.
- **Export/Import:** per-set. Export writes the active set (`{name, colors}`);
  import adds it as a **new** set without clobbering others. Old flat `.json`
  files still import (as a new set).
- **Blank set (replaces "Hide Colors"):** a permanent, uneditable, always-empty
  set named `"Blank"`. Switching to it shows the grid with no colourings — the
  replacement for the old Hide Colors toggle, which is removed. It can't be
  painted into, renamed, or deleted; `loadColorSets` guarantees it always exists
  alongside at least one editable set. `isColoringEditable()` gates every paint
  path (`setCellColor`, the paint-mode click branches, and `changeColor`).

## Storage model

Today every colored character is its own flat `localStorage` entry: hex
codepoint → hex color (e.g. `"4e00"` → `"#ff6060"`), sharing the namespace with
reserved preference keys (`csScript`, `csSelectedSet`, `infoOptions`,
`csCollapse:<id>`, `coloringsHidden`).

New model — a **single** `localStorage` key, `colorSets`, holding all sets:

```json
{
  "active": "Default",
  "sets": {
    "Default":   { "4e00": "#ff6060", "4e8c": "#60a0ff" },
    "HSK focus": { "4e09": "#33cc33" }
  }
}
```

This is the single source of truth (cached in a module var `_colorSets`), so
there's no risk of the flat keys and the set store drifting out of sync.

### Migration (one-time, automatic)

On first `loadColorSets()` when no `colorSets` key exists yet: scan
`localStorage` for keys matching `/^[0-9a-f]+$/i` (the existing color-key test),
move them into a `"Default"` set, remove the flat keys, set `active="Default"`,
and persist. Reserved keys (`csScript`, etc.) don't match the hex regex, so
they're untouched. Existing users keep all their colorings under "Default".

Invariants enforced on every load: at least one set always exists, and `active`
always points to a real set (falls back to the first set otherwise).

## JS changes (`static/script.js`)

### New color-set module (insert near the existing color logic)

| Function | Responsibility |
|---|---|
| `loadColorSets()` | Parse `colorSets` (lazy, cached); run migration; enforce invariants. |
| `saveColorSets()` | Persist `_colorSets`. |
| `getActiveColors()` | The active set's `{codepoint: color}` object. |
| `getCellColor(cp)` | Active set's color for a codepoint, or `null`. |
| `setCellColor(cp, color)` | Write a color into the active set + save. |
| `colorSetNames()` / `getActiveSetName()` | Introspection for the UI. |
| `switchColorSet(name)` | Set active, save, refresh select, re-render grid, **and recolor the large box** to the new active set's color for its current character. |
| `createColorSet(name)` | Add empty set (unique, non-empty name) and activate it. |
| `renameColorSet(old, new)` | Rename (unique, non-empty); keep active pointer. |
| `deleteColorSet(name)` | Delete; if it was active/last, fall back to another/Default. |
| `refreshColorSetSelect()` | Rebuild the top-bar `<select>` from current sets. |
| `promptCreateColorSet()` / `promptRenameColorSet()` / `promptDeleteColorSet()` | Menu-tab handlers (use `prompt`/`confirm`/`alert`, matching the file's existing style). |

### Call-site swaps (flat localStorage → active set)

Replace direct flat-key access with the helpers:

- `activateCharacterFromInfoBox` — `getItem(unicodeKey)` ×3 → `getCellColor`;
  `setItem(unicodeKey, …)` → `setCellColor`.
- `makeCharCell` — `getItem(unicodeKey)` → `getCellColor`.
- `handleCellClick` — `setItem(unicodeKey, …)` → `setCellColor`.
- `changeColor` — `setItem(currentUnicodeKey, …)` → `setCellColor`.

### Export / Import / Clear rewrites

- `exportUserData()` → downloads `{ name: <active>, colors: {…} }` as
  `<active-name>.json`.
- `addToLocalStorage()` → accepts **both** the new `{name, colors}` shape and the
  legacy flat object; adds it under a **de-duplicated** name (`"Imported (2)"`,
  …), activates it, and re-renders. Never clears other sets.
- **Clear** button handler → clears only the **active** set's colorings (relabel
  to "Clear This Set"), instead of `localStorage.clear()` which wiped everything
  including preferences.

### Init wiring

In the bootstrap block: ensure `loadColorSets()` runs (lazily fine, but call it
explicitly), and `refreshColorSetSelect()` + the `<select>` change listener +
New/Rename/Delete button listeners are wired in `createMenu()`.

## HTML changes (`templates/index.html`)

1. **Top bar** — after the `#colorButtons` div, add a switcher:
   ```html
   <div class="color-set-switcher">
     <label for="colorSetSelect">Set:</label>
     <select id="colorSetSelect" class="character-set-dropdown"></select>
     <button id="newColorSetBtn" type="button">+ New</button>
   </div>
   ```
2. **Color Sets menu tab** (`#importexportmenu`) — add a "Manage Sets" block
   above Export/Import with **New**, **Rename**, **Delete** buttons; relabel
   "Clear All" → "Clear This Set".

## CSS changes (`static/styles.css`)

Minor: a `.color-set-switcher` rule (inline-flex, small gap, label spacing) so
the switcher sits cleanly in the flex top bar alongside the script toggle.

## Known limitations (intentional, to keep scope tight)

- Switching sets re-renders the **macro grid** only; the search-results grid
  keeps its old cell colors until the next search. Acceptable.
- No overlay/merge of sets (per the chosen display model).

The large box **is** refreshed on switch: `switchColorSet` reads the box's
current character (`largeBox.textContent`), computes its codepoint, and sets the
background to the new active set's `getCellColor(cp)` (or the default `#ffffff`
when unset) — so the preview tracks the active set immediately.

## Manual test checklist

1. Existing user (flat keys present) → first load migrates into "Default", all
   colors intact.
2. Create "HSK focus", switch — grid clears to that set's colors; paint a few;
   switch back to Default — original colors return. With a character shown in
   the large box, switching sets recolors the large box to that set's color (or
   white if unset).
3. Rename / delete (including deleting the active set and the last set).
4. Export active set → import into a fresh profile → appears as a new set.
5. Import a legacy flat `.json` → imported as a new set, others untouched.
6. "Clear This Set" empties only the active set; preferences and other sets
   survive.
