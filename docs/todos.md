# TODOs

- option to merge simplified and traditional info + maybe also japanese versions if they exist?
- selecting sources
- fix cantonese duplicates in senses. ex. look at mandarin xing (to go)
- readd cccanto editorial notes somewhere else besides new glosses
- add other scripts
- witionary scraping?

- move unihan definitions into own catagory outside of any language?
- check how japanese defintions work, especially if theyre per reading

- check out skip-downloads flag

- remove / change option in languages menu for diabling entire groups
- move korean hangul to default being after romanization
- make it so menu entries can be dragged to change their order when rendering the info box
- create kana readings when missing them (unihan only)
- add source options
- add wade giles

- does eunhum's catagory make sense?

- how does vietnamese's different IPA transcriptions and 1 national script work?

- add simp/trad/jap switching for interactive sections too, plus regular text sections

## colorings

- fix saving character colorings
- add multiple colorings
- add dynamically made colorings

## character set rewrite

- make collapsable
- give recursive structure and layers to char sets
- look at characters_sets.json
- character set importers?
- character sets can either be the boxes, or just be regular text

-maybe move unihan defs into their own language section

- possible to add to Foundations: 画开井元也工士车爪打用動公文引计认甘世史囚永发存岁回吃同 伞次字安纪布平声余这朋周波品美洲区历止乐店识步爱

add back pronouns?
{
      "type": "section",
      "id": "pronouns",
      "title": "Pronouns",
      "blocks": [
        { "type": "text", "text": "Words for I, you, and them.", "size": 5 },
        { "type": "section", "id": "pronouns-first", "title": "First person (I)", "size": 3, "blocks": [
          { "type": "grid", "cells": "私我僕俺" }
        ] },
        { "type": "section", "id": "pronouns-second", "title": "Second person (you)", "size": 3, "blocks": [
          { "type": "grid", "cells": "君你您" }
        ] },
        { "type": "section", "id": "pronouns-third", "title": "Third person", "size": 3, "blocks": [
          { "type": "grid", "cells": "他她它" }
        ] },
        { "type": "section", "id": "pronouns-plural", "title": "Plural marker", "size": 3, "blocks": [
          { "type": "grid", "cells": "(們TJ们S)" }
        ] }
      ]
    },

add special japanese rendering,has a toggle of furigana and romaji,  makes kanji stand out.
