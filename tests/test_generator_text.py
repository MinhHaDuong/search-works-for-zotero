"""The sampler's text helpers, on literal strings (ticket 0719).

Each helper answers None where the text does not make the answer evident, and
the sampler reports that as not measured. So the tests here check both
directions: the derivation fires on a known-positive string, and it stays
silent on a string that carries nothing to derive from.
"""

import importlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

T = importlib.import_module("bench.generator.text")

PROSE = ("The carbon tax was introduced in two thousand and fourteen under the name of the climate "
         "energy contribution, at a rate that rose every year until the protests of two thousand and "
         "eighteen froze it, and the freeze has held since, whatever the successive budgets promised.")


def test_split_paragraphs_on_blank_lines_and_offsets():
    text = "Heading\n\n" + PROSE + "\n\n" + PROSE.replace("carbon", "energy") + "\n"
    paragraphs = T.split_paragraphs(text)
    assert [p.text for p in paragraphs] == [PROSE, PROSE.replace("carbon", "energy")]
    assert text[paragraphs[0].offset:].startswith("The carbon tax")
    assert text[paragraphs[1].offset:].startswith("The energy tax")


def test_split_paragraphs_joins_wrapped_lines_and_cuts_unbroken_pages():
    wrapped = PROSE.replace(", ", ",\n")
    assert [p.text for p in T.split_paragraphs(wrapped)] == [PROSE]
    page = " ".join([PROSE] * 8)  # one block far over the ceiling, no blank line
    pieces = T.split_paragraphs(page)
    assert len(pieces) >= 3
    assert all(T.MIN_CHARS <= len(p.text) <= T.MAX_CHARS for p in pieces)
    for p in pieces:
        assert page[p.offset:].startswith(p.text[:40])


def test_split_paragraphs_rejects_tables_headings_and_capitals():
    table = "\n".join(f"{i}\t{i * 3.5}\t{i * 7}\t{i * 11}" for i in range(60))
    caps = " ".join(["ANNUAL REPORT OF THE COMMISSION"] * 12)
    assert T.split_paragraphs(table) == []
    assert T.split_paragraphs("Short heading") == []
    assert T.split_paragraphs(caps) == []


def test_page_index_needs_form_feeds():
    text = "page one\fpage two\fpage three"
    assert T.page_index(text, 0) == 1
    assert T.page_index(text, text.index("page two")) == 2
    assert T.page_index(text, text.index("three")) == 3
    assert T.page_index("no breaks here", 5) is None


def test_detect_language_by_script_and_function_words():
    assert T.detect_language(PROSE) == "en"
    assert T.detect_language("La taxe carbone a été introduite en France sous le nom de contribution "
                             "climat-énergie et les recettes sont affectées au budget de l'État.") == "fr"
    assert T.detect_language("Thuế các-bon được đưa vào Việt Nam với mức thuế ban đầu thấp và "
                             "được điều chỉnh theo lộ trình của chính phủ.") == "vi"
    assert T.detect_language("碳税于二零一四年在法国推出，税率逐年上升。") == "zh"
    assert T.detect_language("Углеродный налог был введён во Франции в две тысячи четырнадцатом году.") == "ru"
    assert T.detect_language("12 34 56 78 90") == "und"
    assert T.detect_language("xyzzy plugh frobnicate") == "und"


def test_section_heading_fires_on_evident_headings_only():
    numbered = "3.2 Results of the survey\n" + PROSE + "\n"
    assert T.section_heading(numbered, numbered.index("The carbon")) == "3.2 Results of the survey"
    caps = "METHODS AND DATA\n\n" + PROSE
    assert T.section_heading(caps, caps.index("The carbon")) == "METHODS AND DATA"
    short = "Abstract\n\n" + PROSE
    assert T.section_heading(short, short.index("The carbon")) == "Abstract"
    none = PROSE + "\n\n" + PROSE
    assert T.section_heading(none, len(PROSE) + 2) is None
    sentence = "This is a sentence that ends with a full stop.\n" + PROSE
    assert T.section_heading(sentence, sentence.index("The carbon")) is None


def test_length_bucket_against_census_cuts():
    cuts = (4_162, 8_141, 15_200)
    assert T.length_bucket(1_000, cuts) == "short"
    assert T.length_bucket(4_162, cuts) == "medium"
    assert T.length_bucket(10_000, cuts) == "long"
    assert T.length_bucket(1_000_000, cuts) == "very-long"
