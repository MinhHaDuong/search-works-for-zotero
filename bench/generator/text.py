"""Pure text helpers for the sampler: paragraphs, page index, language, headings.

Nothing here touches the network or the disk, so every function is tested on
literal strings. What each one can and cannot derive is stated on the function,
because the sampler records "not measured" wherever the answer here is None and
the report counts those honestly rather than as zeros.
"""

import re
import unicodedata
from dataclasses import dataclass

#: Paragraph eligibility. A paragraph shorter than the floor is a caption or a
#: heading; one longer than the ceiling is a page the extractor did not break.
MIN_CHARS = 200
MAX_CHARS = 1_500
MIN_WORDS = 30
#: Below this share of letters a block is a table, a reference list or a run of
#: numbers, none of which is a paragraph a question can be written from.
MIN_LETTER_RATIO = 0.6

STOPWORDS = {
    "en": {"the", "and", "of", "to", "in", "is", "that", "for", "with", "as", "are", "this", "by", "on", "be", "from", "which", "or", "an", "was"},
    "fr": {"le", "la", "les", "de", "des", "et", "en", "un", "une", "du", "que", "qui", "dans", "est", "pour", "pas", "sur", "par", "au", "ce", "une", "sont", "aux", "cette"},
    "de": {"der", "die", "und", "das", "ist", "nicht", "von", "mit", "sich", "des", "auf", "für", "dem", "ein", "eine", "auch", "werden", "wird", "als", "zu"},
    "es": {"el", "la", "los", "las", "de", "que", "y", "en", "un", "una", "por", "con", "para", "es", "del", "se", "no", "como", "más", "su"},
    "it": {"il", "di", "che", "la", "e", "un", "per", "non", "una", "del", "della", "gli", "sono", "con", "nel", "alla", "anche", "come", "più", "dei"},
    "pt": {"o", "a", "de", "que", "e", "do", "da", "em", "um", "para", "com", "não", "uma", "os", "no", "na", "por", "mais", "as", "dos"},
}

#: Letters that occur in Vietnamese and almost nowhere else in Latin-script text.
VIETNAMESE_MARKS = set("ăâđêôơưĂÂĐÊÔƠƯạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ")


@dataclass(frozen=True)
class Paragraph:
    offset: int
    text: str


def _letter_ratio(s: str) -> float:
    visible = [c for c in s if not c.isspace()]
    if not visible:
        return 0.0
    return sum(1 for c in visible if c.isalpha()) / len(visible)


def _clean(block: str) -> str:
    return re.sub(r"\s+", " ", block).strip()


def _eligible(text: str) -> bool:
    if not MIN_CHARS <= len(text) <= MAX_CHARS:
        return False
    if len(text.split()) < MIN_WORDS:
        return False
    if _letter_ratio(text) < MIN_LETTER_RATIO:
        return False
    letters = [c for c in text if c.isalpha()]
    # A block mostly in capitals is a running head, a table header or a scan's
    # front matter, not prose.
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.5:
        return False
    return True


def _split_long(block: str, offset: int) -> list[Paragraph]:
    """Cut a block the extractor did not break into sentence-bounded pieces.

    PDF text often arrives with one newline per line and no blank line between
    paragraphs, so a "block" is a whole page. Cutting at sentence ends around
    the ceiling keeps each piece a coherent stretch of prose; the offset of each
    piece is its position in the original text, so the page index stays right.
    """
    out: list[Paragraph] = []
    target = (MIN_CHARS + MAX_CHARS) // 2
    start = 0
    n = len(block)
    while start < n:
        end = min(n, start + target)
        if end < n:
            cut = -1
            for m in re.finditer(r"[.!?]\s", block[start:end + 200]):
                if m.end() >= target // 2:
                    cut = start + m.end()
                    if m.end() >= target:
                        break
            if cut > start:
                end = cut
        piece = block[start:end]
        lead = len(piece) - len(piece.lstrip())
        out.append(Paragraph(offset + start + lead, _clean(piece)))
        start = end
    return out


def split_paragraphs(text: str) -> list[Paragraph]:
    """Every eligible paragraph of an extracted text, with its character offset.

    Blocks are separated by blank lines or by form feeds (page breaks). A block
    over the ceiling is cut at sentence boundaries. Offsets index the ORIGINAL
    text, which is what the page index and the reachability cap are computed on.
    """
    out: list[Paragraph] = []
    for m in re.finditer(r"[^\n\f]+(?:\n(?![ \t]*\n)[^\n\f]+)*", text):
        block = m.group(0)
        lead = len(block) - len(block.lstrip())
        offset = m.start() + lead
        if len(_clean(block)) > MAX_CHARS:
            pieces = _split_long(block.strip(), offset)
        else:
            pieces = [Paragraph(offset, _clean(block))]
        out.extend(p for p in pieces if _eligible(p.text))
    return out


def page_index(text: str, offset: int) -> int | None:
    """The 1-based PDF page index of an offset, or None when the text carries no
    page breaks. Zotero's extractor writes a form feed between pages in recent
    generations and nothing at all in older ones; without one the page cannot be
    derived from the text and is reported not measured rather than guessed."""
    if "\f" not in text:
        return None
    return text.count("\f", 0, offset) + 1


def detect_language(text: str) -> str:
    """A coarse language of a paragraph, from script and function words.

    Returns an ISO 639-1 code for the scripts and languages it knows and `und`
    otherwise. It is deliberately small: the lane is (question language, answer
    language), and a wrong guess here mislabels a lane rather than a score, so
    the report says how many paragraphs landed in `und`.
    """
    scripts: dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        script = name.split(" ", 1)[0] if name else ""
        if script in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL"):
            script = "CJK"
        scripts[script] = scripts.get(script, 0) + 1
    total = sum(scripts.values())
    if not total:
        return "und"
    if scripts.get("CJK", 0) / total > 0.3:
        return "zh"
    if scripts.get("CYRILLIC", 0) / total > 0.5:
        return "ru"
    if scripts.get("ARABIC", 0) / total > 0.5:
        return "ar"
    if scripts.get("DEVANAGARI", 0) / total > 0.5:
        return "hi"
    if sum(1 for ch in text if ch in VIETNAMESE_MARKS) / total > 0.03:
        return "vi"
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    if not words:
        return "und"
    best, best_hits = "und", 0
    for lang, stops in STOPWORDS.items():
        hits = sum(1 for w in words if w in stops)
        if hits > best_hits:
            best, best_hits = lang, hits
    if best_hits / len(words) < 0.04:
        return "und"
    return best


HEADING_NUMBERED = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.|[A-Z]\.)\s+\S")
HEADING_LOOKBACK = 4_000


def section_heading(text: str, offset: int) -> str | None:
    """The nearest preceding line that reads as a section heading, or None.

    Evident headings only: a numbered line ("3.2 Results", "IV. Method"), an
    all-capitals line, or a short capitalised line that ends without sentence
    punctuation and stands on its own line. Anything else is not measured: the
    extractor keeps no structure, so a heading the text does not make evident is
    not derivable from it.
    """
    window = text[max(0, offset - HEADING_LOOKBACK):offset]
    for raw in reversed(window.split("\n")):
        line = raw.strip()
        if not 3 <= len(line) <= 90 or line[-1] in ".,;:":
            continue
        words = line.split()
        if len(words) > 12:
            continue
        letters = [c for c in line if c.isalpha()]
        if not letters:
            continue
        if HEADING_NUMBERED.match(line):
            return line
        if len(letters) >= 4 and all(c.isupper() for c in letters):
            return line
        if len(line) <= 60 and line[0].isupper() and _letter_ratio(line) > 0.7 and len(words) <= 8:
            return line
    return None


def length_bucket(chars: int, cuts: tuple[int, int, int]) -> str:
    """One of four document-length strata against the census's quartile cuts."""
    p25, p50, p75 = cuts
    if chars < p25:
        return "short"
    if chars < p50:
        return "medium"
    if chars < p75:
        return "long"
    return "very-long"
