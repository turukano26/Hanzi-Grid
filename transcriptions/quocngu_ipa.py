"""Vietnamese Quốc Ngữ → IPA (broad transcription), per dialect.

Turns a Quốc Ngữ syllable into a broad phonetic IPA transcription for one of the
three major dialect regions — **Northern** (Hà Nội), **Central** (Huế) and
**Southern** (Sài Gòn). This is a direct port of James Kirby's *vPhon*
(https://github.com/kirbyj/vPhon, GPL): the rule tables (onsets, glides, nuclei,
offglides, codas, tones) and the segmentation + dialect-transform logic are
vPhon's; only the surface conventions are adapted to match this repo's other IPA
systems. Used by `app.py` as the six derived Vietnamese IPA transcriptions — the
phonemes-only `quocngu_to_ipa_northern` / `_central` / `_southern` and the
with-tones `…_tones` variants, all from Quốc Ngữ (ts 50), so every Vietnamese
reading shows a per-dialect IPA without anything being stored.

In Vietnamese the dialect is the interesting axis — Northern *tr* [tɕ] vs
Southern/Central [ʈ], the Northern diphthongs /iə ɨə uə/ that surface as long
monophthongs [iː ɨː uː] in the South, the six-way vs five-way tone splits — so
each dialect is its own system. As with the other tonal languages (Mandarin,
Cantonese) each dialect comes in a phonemes-only / with-tones pair, giving six
systems in all: `quocngu_to_ipa_<dialect>` (phonemes) and
`quocngu_to_ipa_<dialect>_tones` (with a Chao tone letter per syllable, e.g.
˧˥, ˨˩ˀ; ˀ marks glottalisation).

Conventions, fixed to vPhon's defaults (its CLI flags collapsed to constants):
surface phonetic output (allophonic palatalised / labiodorsal codas: -ʲk -ʲŋ,
-k͡p -ŋ͡m), aspirated tʰ, labio-velar onset kʷ and glide ʷ, and a glottal-stop
onset ʔ prepended to onsetless syllables (Vietnamese has no true vowel-initial
syllables). Tones are derived from the Gedney A/B/C/D × 1/2 register the tone
diacritic + stop-coda encode, then mapped to the dialect's Chao contour.

Input is the diacritic Quốc Ngữ the DB stores (NFC or NFD, any case); one or
more space-separated syllables are each converted. Non-Vietnamese / unparseable
input is returned unchanged, never raised on — the value still renders, just
un-IPA'd. Kept stdlib-only and importable on its own.
"""

import string
import unicodedata

# --- vPhon rule tables (verbatim from vPhon's rules.py) ---------------------

_ONSETS = {
    'b': 'ɓ', 'c': 'k', 'ch': 'c', 'd': 'j', 'đ': 'ɗ', 'g': 'ɣ', 'gh': 'ɣ',
    'gi': 'z', 'h': 'h', 'k': 'k', 'kh': 'x', 'l': 'l', 'm': 'm', 'n': 'n',
    'ng': 'ŋ', 'ngh': 'ŋ', 'nh': 'ɲ', 'ph': 'f', 'p': 'p', 'qu': 'kʷ',
    'r': 'r', 's': 'ʂ', 't': 't', 'th': 'tʰ', 'tr': 'ʈ', 'v': 'v', 'x': 's',
}

_GI = {'gi': 'zi', 'gí': 'zi', 'gì': 'zi', 'gỉ': 'zi', 'gĩ': 'zi', 'gị': 'zi'}

_QU = {'quy': 'kʷi', 'quý': 'kʷi', 'quỳ': 'kʷi', 'quỷ': 'kʷi', 'quỹ': 'kʷi',
       'quỵ': 'kʷi'}

_NUCLEI = {
    'a': 'aː', 'á': 'aː', 'à': 'aː', 'ả': 'aː', 'ã': 'aː', 'ạ': 'aː',
    'â': 'ə', 'ấ': 'ə', 'ầ': 'ə', 'ẩ': 'ə', 'ẫ': 'ə', 'ậ': 'ə',
    'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'e': 'ɛ', 'é': 'ɛ', 'è': 'ɛ', 'ẻ': 'ɛ', 'ẽ': 'ɛ', 'ẹ': 'ɛ',
    'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'i': 'i', 'í': 'i', 'ì': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'o': 'ɔ', 'ó': 'ɔ', 'ò': 'ɔ', 'ỏ': 'ɔ', 'õ': 'ɔ', 'ọ': 'ɔ',
    'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'əː', 'ớ': 'əː', 'ờ': 'əː', 'ở': 'əː', 'ỡ': 'əː', 'ợ': 'əː',
    'u': 'u', 'ú': 'u', 'ù': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'ɨ', 'ứ': 'ɨ', 'ừ': 'ɨ', 'ử': 'ɨ', 'ữ': 'ɨ', 'ự': 'ɨ',
    'y': 'i', 'ý': 'i', 'ỳ': 'i', 'ỷ': 'i', 'ỹ': 'i', 'ỵ': 'i',
    'ia': 'iə', 'ía': 'iə', 'ìa': 'iə', 'ỉa': 'iə', 'ĩa': 'iə', 'ịa': 'iə',
    'iá': 'iə', 'ià': 'iə', 'iả': 'iə', 'iã': 'iə', 'iạ': 'iə',
    'iê': 'iə', 'iế': 'iə', 'iề': 'iə', 'iể': 'iə', 'iễ': 'iə', 'iệ': 'iə',
    'oo': 'ɔː', 'óo': 'ɔː', 'òo': 'ɔː', 'ỏo': 'ɔː', 'õo': 'ɔː', 'ọo': 'ɔː',
    'oó': 'ɔː', 'oò': 'ɔː', 'oỏ': 'ɔː', 'oõ': 'ɔː', 'oọ': 'ɔː',
    'ôô': 'oː', 'ốô': 'oː', 'ồô': 'oː', 'ổô': 'oː', 'ỗô': 'oː', 'ộô': 'oː',
    'ôố': 'oː', 'ôồ': 'oː', 'ôổ': 'oː', 'ôỗ': 'oː', 'ôộ': 'oː',
    'ua': 'uə', 'úa': 'uə', 'ùa': 'uə', 'ủa': 'uə', 'ũa': 'uə', 'ụa': 'uə',
    'uô': 'uə', 'uố': 'uə', 'uồ': 'uə', 'uổ': 'uə', 'uỗ': 'uə', 'uộ': 'uə',
    'ưa': 'ɨə', 'ứa': 'ɨə', 'ừa': 'ɨə', 'ửa': 'ɨə', 'ữa': 'ɨə', 'ựa': 'ɨə',
    'ươ': 'ɨə', 'ướ': 'ɨə', 'ườ': 'ɨə', 'ưở': 'ɨə', 'ưỡ': 'ɨə', 'ượ': 'ɨə',
    'yê': 'iə', 'yế': 'iə', 'yề': 'iə', 'yể': 'iə', 'yễ': 'iə', 'yệ': 'iə',
    'uơ': 'uə', 'uớ': 'uə', 'uờ': 'uə', 'uở': 'uə', 'uỡ': 'uə', 'uợ': 'uə',
}

_OFFGLIDES = {
    'ai': 'aːj', 'ái': 'aːj', 'ài': 'aːj', 'ải': 'aːj', 'ãi': 'aːj', 'ại': 'aːj',
    'ay': 'aj', 'áy': 'aj', 'ày': 'aj', 'ảy': 'aj', 'ãy': 'aj', 'ạy': 'aj',
    'ao': 'aːw', 'áo': 'aːw', 'ào': 'aːw', 'ảo': 'aːw', 'ão': 'aːw', 'ạo': 'aːw',
    'au': 'aw', 'áu': 'aw', 'àu': 'aw', 'ảu': 'aw', 'ãu': 'aw', 'ạu': 'aw',
    'ây': 'əj', 'ấy': 'əj', 'ầy': 'əj', 'ẩy': 'əj', 'ẫy': 'əj', 'ậy': 'əj',
    'âu': 'əw', 'ấu': 'əw', 'ầu': 'əw', 'ẩu': 'əw', 'ẫu': 'əw', 'ậu': 'əw',
    'eo': 'ɛw', 'éo': 'ɛw', 'èo': 'ɛw', 'ẻo': 'ɛw', 'ẽo': 'ɛw', 'ẹo': 'ɛw',
    'êu': 'ew', 'ếu': 'ew', 'ều': 'ew', 'ểu': 'ew', 'ễu': 'ew', 'ệu': 'ew',
    'iu': 'iw', 'íu': 'iw', 'ìu': 'iw', 'ỉu': 'iw', 'ĩu': 'iw', 'ịu': 'iw',
    'oi': 'ɔj', 'ói': 'ɔj', 'òi': 'ɔj', 'ỏi': 'ɔj', 'õi': 'ɔj', 'ọi': 'ɔj',
    'ôi': 'oj', 'ối': 'oj', 'ồi': 'oj', 'ổi': 'oj', 'ỗi': 'oj', 'ội': 'oj',
    'ui': 'uj', 'úi': 'uj', 'ùi': 'uj', 'ủi': 'uj', 'ũi': 'uj', 'ụi': 'uj',
    'uy': 'uj', 'úy': 'uj', 'ùy': 'uj', 'ủy': 'uj', 'ũy': 'uj', 'ụy': 'uj',
    'ơi': 'əːj', 'ới': 'əːj', 'ời': 'əːj', 'ởi': 'əːj', 'ỡi': 'əːj', 'ợi': 'əːj',
    'ưi': 'ɨj', 'ứi': 'ɨj', 'ừi': 'ɨj', 'ửi': 'ɨj', 'ữi': 'ɨj', 'ựi': 'ɨj',
    'ưu': 'ɨw', 'ứu': 'ɨw', 'ừu': 'ɨw', 'ửu': 'ɨw', 'ữu': 'ɨw', 'ựu': 'ɨw',
    'iêu': 'iəw', 'iếu': 'iəw', 'iều': 'iəw', 'iểu': 'iəw', 'iễu': 'iəw',
    'iệu': 'iəw',
    'yêu': 'iəw', 'yếu': 'iəw', 'yều': 'iəw', 'yểu': 'iəw', 'yễu': 'iəw',
    'yệu': 'iəw',
    'uôi': 'uəj', 'uối': 'uəj', 'uồi': 'uəj', 'uổi': 'uəj', 'uỗi': 'uəj',
    'uội': 'uəj',
    'ươi': 'ɨəj', 'ưới': 'ɨəj', 'ười': 'ɨəj', 'ưởi': 'ɨəj', 'ưỡi': 'ɨəj',
    'ượi': 'ɨəj',
    'ươu': 'ɨəw', 'ướu': 'ɨəw', 'ườu': 'ɨəw', 'ưởu': 'ɨəw', 'ưỡu': 'ɨəw',
    'ượu': 'ɨəw',
}

_ONGLIDES = {
    'oa': 'aː', 'oá': 'aː', 'oà': 'aː', 'oả': 'aː', 'oã': 'aː', 'oạ': 'aː',
    'óa': 'aː', 'òa': 'aː', 'ỏa': 'aː', 'õa': 'aː', 'ọa': 'aː',
    'oă': 'a', 'oắ': 'a', 'oằ': 'a', 'oẳ': 'a', 'oẵ': 'a', 'oặ': 'a',
    'oe': 'ɛ', 'oé': 'ɛ', 'oè': 'ɛ', 'oẻ': 'ɛ', 'oẽ': 'ɛ', 'oẹ': 'ɛ',
    'óe': 'ɛ', 'òe': 'ɛ', 'ỏe': 'ɛ', 'õe': 'ɛ', 'ọe': 'ɛ',
    'ua': 'aː', 'uá': 'aː', 'uà': 'aː', 'uả': 'aː', 'uã': 'aː', 'uạ': 'aː',
    'uă': 'a', 'uắ': 'a', 'uằ': 'a', 'uẳ': 'a', 'uẵ': 'a', 'uặ': 'a',
    'uâ': 'ə', 'uấ': 'ə', 'uầ': 'ə', 'uẩ': 'ə', 'uẫ': 'ə', 'uậ': 'ə',
    'ue': 'ɛ', 'ué': 'ɛ', 'uè': 'ɛ', 'uẻ': 'ɛ', 'uẽ': 'ɛ', 'uẹ': 'ɛ',
    'uê': 'e', 'uế': 'e', 'uề': 'e', 'uể': 'e', 'uễ': 'e', 'uệ': 'e',
    'uy': 'i', 'uý': 'i', 'uỳ': 'i', 'uỷ': 'i', 'uỹ': 'i', 'uỵ': 'i',
    'uya': 'iə', 'uyá': 'iə', 'uyà': 'iə', 'uyả': 'iə', 'uyã': 'iə', 'uyạ': 'iə',
    'uyê': 'iə', 'uyế': 'iə', 'uyề': 'iə', 'uyể': 'iə', 'uyễ': 'iə', 'uyệ': 'iə',
    'oen': 'ɛn', 'oén': 'ɛn', 'oèn': 'ɛn', 'oẻn': 'ɛn', 'oẽn': 'ɛn', 'oẹn': 'ɛn',
    'oet': 'ɛt', 'oét': 'ɛt', 'oèt': 'ɛt', 'oẻt': 'ɛt', 'oẽt': 'ɛt', 'oẹt': 'ɛt',
}

_ONOFFGLIDES = {
    'oai': 'aːj', 'oái': 'aːj', 'oài': 'aːj', 'oải': 'aːj', 'oãi': 'aːj',
    'oại': 'aːj',
    'oay': 'aj', 'oáy': 'aj', 'oày': 'aj', 'oảy': 'aj', 'oãy': 'aj', 'oạy': 'aj',
    'oao': 'aw', 'oáo': 'aw', 'oào': 'aw', 'oảo': 'aw', 'oão': 'aw', 'oạo': 'aw',
    'oeo': 'ɛw', 'oéo': 'ɛw', 'oèo': 'ɛw', 'oẻo': 'ɛw', 'oẽo': 'ɛw', 'oẹo': 'ɛw',
    'óeo': 'ɛw', 'òeo': 'ɛw', 'ỏeo': 'ɛw', 'õeo': 'ɛw', 'ọeo': 'ɛw',
    'ueo': 'ɛw', 'uéo': 'ɛw', 'uèo': 'ɛw', 'uẻo': 'ɛw', 'uẽo': 'ɛw', 'uẹo': 'ɛw',
    'uêu': 'ew', 'uếu': 'ew', 'uều': 'ew', 'uểu': 'ew', 'uễu': 'ew', 'uệu': 'ew',
    'uyu': 'iw', 'uyú': 'iw', 'uyù': 'iw', 'uyủ': 'iw', 'uyũ': 'iw', 'uyụ': 'iw',
    'uýu': 'iw', 'uỳu': 'iw', 'uỷu': 'iw', 'uỹu': 'iw', 'uỵu': 'iw',
    'uai': 'aːj', 'uái': 'aːj', 'uài': 'aːj', 'uải': 'aːj', 'uãi': 'aːj',
    'uại': 'aːj',
    'uay': 'aj', 'uáy': 'aj', 'uày': 'aj', 'uảy': 'aj', 'uãy': 'aj', 'uạy': 'aj',
    'uây': 'əj', 'uấy': 'əj', 'uầy': 'əj', 'uẩy': 'əj', 'uẫy': 'əj', 'uậy': 'əj',
}

_CODAS = {
    'c': 'k', 'ch': 'c', 'k': 'k', 'm': 'm', 'n': 'n', 'ng': 'ŋ', 'nh': 'ɲ',
    'p': 'p', 't': 't',
}

# Tone diacritic → Gedney register class (A/B/C × upper-1 / lower-2). A1 (the
# unmarked "ngang" tone) has no diacritic and is the default; D1/D2 are the B
# classes redirected onto a stop coda (see _trans).
_TONES = {
    'á': 'B1', 'à': 'A2', 'ả': 'C1', 'ã': 'C2', 'ạ': 'B2',
    'ấ': 'B1', 'ầ': 'A2', 'ẩ': 'C1', 'ẫ': 'C2', 'ậ': 'B2',
    'ắ': 'B1', 'ằ': 'A2', 'ẳ': 'C1', 'ẵ': 'C2', 'ặ': 'B2',
    'é': 'B1', 'è': 'A2', 'ẻ': 'C1', 'ẽ': 'C2', 'ẹ': 'B2',
    'ế': 'B1', 'ề': 'A2', 'ể': 'C1', 'ễ': 'C2', 'ệ': 'B2',
    'í': 'B1', 'ì': 'A2', 'ỉ': 'C1', 'ĩ': 'C2', 'ị': 'B2',
    'ó': 'B1', 'ò': 'A2', 'ỏ': 'C1', 'õ': 'C2', 'ọ': 'B2',
    'ố': 'B1', 'ồ': 'A2', 'ổ': 'C1', 'ỗ': 'C2', 'ộ': 'B2',
    'ớ': 'B1', 'ờ': 'A2', 'ở': 'C1', 'ỡ': 'C2', 'ợ': 'B2',
    'ú': 'B1', 'ù': 'A2', 'ủ': 'C1', 'ũ': 'C2', 'ụ': 'B2',
    'ứ': 'B1', 'ừ': 'A2', 'ử': 'C1', 'ữ': 'C2', 'ự': 'B2',
    'ý': 'B1', 'ỳ': 'A2', 'ỷ': 'C1', 'ỹ': 'C2', 'ỵ': 'B2',
}

# Gedney class → Chao contour, as tone letters (˩=1 low … ˥=5 high; ˀ marks
# glottalisation). Adapted from vPhon's chao_{n,c,s} tables (its superscript
# digit strings rewritten in the tone-letter notation this repo's other tonal
# IPA systems use). One table per dialect.
_CHAO = {
    'n': {'A1': '˧˧', 'A2': '˧˨', 'B1': '˨˦', 'B2': '˨˩ˀ',
          'C1': '˧˩˨', 'C2': '˧ˀ˥', 'D1': '˦˥', 'D2': '˨˩'},
    'c': {'A1': '˧˥', 'A2': '˦˨', 'B1': '˨ˀ˦', 'B2': '˧˩',
          'C1': '˧˨ˀ', 'C2': '˧˨ˀ', 'D1': '˦˥', 'D2': '˧˩'},
    's': {'A1': '˧˧', 'A2': '˨˩', 'B1': '˦˥', 'B2': '˨˩˨',
          'C1': '˨˩˦', 'C2': '˨˩˦', 'D1': '˦˥', 'D2': '˨˩˨'},
}

# Surface conventions, fixed to vPhon's superscript defaults.
_LD_NAS, _LD_PLO = 'ŋ͡m', 'k͡p'          # labiodorsal final nasal / plosive
_PAL_NAS, _PAL_PLO = 'ʲŋ', 'ʲk'         # palatalised dorsal final nasal / plosive
_LV_GLI = 'ʷ'                           # labiovelar glide


def _trans(word, dialect):
    """Segment one Quốc Ngữ syllable into (onset, glide, nucleus, coda, tone)
    IPA pieces for `dialect` ('n'/'c'/'s'), or (None, …) if non-Vietnamese.

    Direct port of vPhon's `trans()` with its flags pinned: surface phonetic
    output (phonemic=False), Chao tones, superscript codas/glides (nosuper=False)
    and glottal-stop onsets retained (glottal=False)."""
    ons = gli = nuc = cod = ''
    o_off = c_off = 0
    length = len(word)
    if length == 0:
        return (None, None, None, None, None)

    # Greedy longest-match onset (ngh > nh/gh > single) and coda (two-char > one).
    if word[0:3] in _ONSETS:
        ons, o_off = _ONSETS[word[0:3]], 3
    elif word[0:2] in _ONSETS:
        ons, o_off = _ONSETS[word[0:2]], 2
    elif word[0] in _ONSETS:
        ons, o_off = _ONSETS[word[0]], 1

    if word[length - 2:length] in _CODAS:
        cod, c_off = _CODAS[word[length - 2:length]], 2
    elif word[length - 1] in _CODAS:
        cod, c_off = _CODAS[word[length - 1]], 1

    nucl = word[o_off:length - c_off]

    # Onsetless syllables get a glottal-stop onset.
    if o_off == 0:
        ons = 'ʔ'

    # qu + i finals (quy, quý…) and gi- (gi, giền, giêng) need word-level fixups.
    if word in _QU:
        ons = _QU[word][0]
        nuc = _QU[word][-1]
        if len(_QU[word]) > 2:
            gli = _LV_GLI
    if word[0:2] in _GI:
        if word == 'giền':
            nucl = 'â'                  # Emeneau 1951: 30
        elif length == 2 or (length == 3 and word[2] in ('n', 'm')):
            nucl = 'i'
        elif nucl in _NUCLEI and word[2] in ('ê', 'ế', 'ề', 'ể', 'ễ', 'ệ'):
            nucl = 'iê'
        ons = _ONSETS['gi']

    # Nucleus, resolving on/off glides into onset labialisation / coda glides.
    if nucl in _NUCLEI:
        nuc = _NUCLEI[nucl]
    elif nucl in _ONGLIDES:
        nuc = _ONGLIDES[nucl]
        ons = ons + _LV_GLI if ons != 'ʔ' else 'w'
    elif nucl in _ONOFFGLIDES:
        ons = ons + _LV_GLI if ons != 'ʔ' else 'w'
        nuc = _ONOFFGLIDES[nucl][0:-1]
        cod = _ONOFFGLIDES[nucl][-1]
    elif nucl in _OFFGLIDES:
        cod = _OFFGLIDES[nucl][-1]
        nuc = _OFFGLIDES[nucl][:-1]
    else:
        return (None, None, None, None, None)   # not a Vietnamese syllable

    # Split a labialised onset (kʷ, tʰʷ) back into onset + glide.
    if len(ons) == 2 and ons[1] == _LV_GLI:
        ons, gli = ons[0], _LV_GLI
    if len(ons) == 3 and ons[2] == _LV_GLI:
        ons, gli = ons[0:2], _LV_GLI

    # Tone: last diacritic wins; default A1; B→D before a stop coda.
    tonelist = [_TONES[c] for c in word if c in _TONES]
    ton = tonelist[-1] if tonelist else 'A1'
    if ton == 'B1' and cod in ('p', 't', 'c', 'k'):
        ton = 'D1'
    if ton == 'B2' and cod in ('p', 't', 'c', 'k'):
        ton = 'D2'
    ton = _CHAO[dialect][ton]

    # Velar fronting: aː before a palatal coda → ɛ.
    if nuc == 'aː' and cod in ('c', 'ɲ'):
        nuc = 'ɛ'
    # ɛ/e lengthen before a velar coda.
    if cod in ('ŋ', 'k'):
        if nuc == 'ɛ':
            nuc = 'ɛː'
        if nuc == 'e':
            nuc = 'eː'

    if dialect == 'n':
        # No surface palatal codas.
        if cod == 'c':
            cod = 'k'
        elif cod == 'ɲ':
            cod = 'ŋ'
        # Onset mergers.
        if ons in ('j', 'r'):
            ons = 'z'
        elif ons in ('c', 'ʈ'):
            ons = 'tɕ'
        elif ons == 'ʂ':
            ons = 's'
        # Palatalised / labiodorsal velar codas by vowel place.
        if cod in ('k', 'ŋ'):
            if nuc in ('e', 'ɛ', 'i'):
                cod = _PAL_PLO if cod == 'k' else _PAL_NAS
            elif nuc in ('u', 'ɔ', 'o') and word != 'quốc':
                cod = _LD_PLO if cod == 'k' else _LD_NAS
        # Pre-palatal vowel centralisation.
        if cod in (_PAL_NAS, _PAL_PLO) and nuc == 'ɛ':
            nuc = 'a'
        # Lengthen surface monophthongs where length is not contrastive.
        if len(nuc) == 1 and nuc not in ('a', 'ə'):
            if len(cod) == 1 and nuc != 'ɨ':
                nuc += 'ː'
            elif len(cod) == 0:
                nuc += 'ː'

    else:   # 'c' / 's' — Central and Southern share most rules
        if ons == 'z':
            ons = 'j'
        if ons == 'k' and gli == _LV_GLI:
            ons, gli = 'w', ''
        if ons == 'ɣ':
            ons = 'ɡ'
        # Hanoi diphthongs are long monophthongs before a coda.
        if cod and nuc in ('iə', 'uə', 'ɨə'):
            nuc = {'iə': 'iː', 'ɨə': 'ɨː', 'uə': 'uː'}[nuc]
        # Partial ɔ/o merger.
        if nuc == 'ɔ' and cod in ('n', 't'):
            nuc = 'ɔː'
        if nuc == 'o' and cod in ('ŋ', 'k'):
            nuc = 'ɔ'
        if nuc == 'ɛ' and cod in ('n', 't'):
            if cod == 'n':
                cod = 'ŋ'
            nuc = 'ɛː'
        # No coronals after long or central vowels.
        if cod and len(nuc) == 2:
            if cod == 'n':
                cod = 'ŋ'
            elif cod == 't':
                cod = 'k'
        if cod and nuc in ('ɨ', 'ə', 'a', 'u', 'o'):
            if cod == 'n':
                cod = 'ŋ'
            elif cod == 't':
                cod = 'k'
        # No dorsals after short front vowels.
        if cod and nuc in ('i', 'e', 'ɛ'):
            if cod == 'ŋ':
                cod = 'n'
            elif cod == 'k':
                cod = 't'
        # Remaining non-labial palatal codas go dorsal/coronal.
        if cod == 'ɲ':
            cod = 'n'
        elif cod == 'c':
            cod = 't'
        # Surface <x>/<s> merger.
        if ons == 'ʂ':
            ons = 's'
        # Pre-coronal centralisation.
        if cod in ('n', 't'):
            if nuc == 'i':
                nuc = 'ɨ'
            elif nuc == 'ɛ':
                nuc = 'a'
            elif nuc == 'e':
                nuc = 'əː'
        # Centralisation of /u/ before labials.
        if nuc == 'u' and cod in ('m', 'p'):
            nuc = 'ɨ'
        # No short surface /e ɛ o ɔ/ (except before labiodorsals).
        if nuc in ('e', 'ɛ', 'o', 'ɔ'):
            if nuc == 'e':
                nuc = 'eː'
            elif nuc == 'ɛ':
                nuc = 'ɛː'
            if cod not in ('ŋ', 'k'):
                if nuc == 'o':
                    nuc = 'oː'
                elif nuc == 'ɔ':
                    nuc = 'ɔː'
        # Labiodorsals after [u ɔ oː].
        if nuc in ('u', 'ɔ', 'oː') and cod in ('ŋ', 'k'):
            cod = _LD_NAS if cod == 'ŋ' else _LD_PLO

    return (ons, gli, nuc, cod, ton)


def _syllable_to_ipa(syllable, dialect, tones):
    word = unicodedata.normalize('NFC', syllable).strip(string.punctuation).lower()
    pieces = _trans(word, dialect)
    if None in pieces:
        return syllable                     # unrecognised — leave as-is
    ons, gli, nuc, cod, ton = pieces
    if not tones:
        ton = ''
    return ''.join(p for p in (ons, gli, nuc, cod, ton) if p)


def _convert(text, dialect, tones):
    return ' '.join(_syllable_to_ipa(s, dialect, tones) for s in text.split())


def quocngu_to_ipa_northern(text: str) -> str:
    """Broad Northern (Hà Nội) IPA, phonemes only, for a Quốc Ngữ string (one or
    more space-separated syllables). Unrecognised syllables pass through
    unchanged."""
    return _convert(text, 'n', tones=False)


def quocngu_to_ipa_central(text: str) -> str:
    """Broad Central (Huế) IPA, phonemes only. Otherwise like
    `quocngu_to_ipa_northern`."""
    return _convert(text, 'c', tones=False)


def quocngu_to_ipa_southern(text: str) -> str:
    """Broad Southern (Sài Gòn) IPA, phonemes only. Otherwise like
    `quocngu_to_ipa_northern`."""
    return _convert(text, 's', tones=False)


def quocngu_to_ipa_northern_tones(text: str) -> str:
    """Broad Northern (Hà Nội) IPA with a Chao tone letter per syllable.
    Otherwise identical to `quocngu_to_ipa_northern`."""
    return _convert(text, 'n', tones=True)


def quocngu_to_ipa_central_tones(text: str) -> str:
    """Broad Central (Huế) IPA with tones. Otherwise like
    `quocngu_to_ipa_central`."""
    return _convert(text, 'c', tones=True)


def quocngu_to_ipa_southern_tones(text: str) -> str:
    """Broad Southern (Sài Gòn) IPA with tones. Otherwise like
    `quocngu_to_ipa_southern`."""
    return _convert(text, 's', tones=True)
