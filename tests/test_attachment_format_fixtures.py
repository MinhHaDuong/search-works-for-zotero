"""The attachment-format matrix is real, and its formats are decided by content (0599).

Tracker 0593's invariant is that attachment-format eligibility is MIME/capability
based and never an extension allow-list. This is the mechanical form of it, and
the case that earns the suite its place is the fourth one below: a fixture renamed
to a *misleading* extension, classified correctly by
`bench/attachment_format.py` and incorrectly by a three-line extension-only
classifier written here, in the test, as the thing being falsified.

Everything else is the scaffolding that makes that control mean something:

  * each fixture carries a unique body token, so a downstream full-text probe can
    separate real extraction from a hit on shared record metadata;
  * each fixture is genuinely valid -- the ZIP packages open and their `mimetype`
    members are first and stored, the PDF's cross-reference offsets point at its
    object headers;
  * the three ZIP-container formats get three *different* answers, because a
    classifier answering `docx` for every archive would sail through a one-sided
    test;
  * a plain ZIP holding neither is not mistaken for a document.

Two honest absences are asserted rather than papered over. There is no `.doc`
fixture and the generator declares the gap; Markdown is indistinguishable from
plain text by content, and the test says so explicitly so that nobody can later
add a leading-`#` heuristic quietly and call it an improvement.

Cost tier: fast, unmarked. Pure Python, stdlib only, no subprocess, no network, no
Zotero, no converter. The fixtures are written into `tmp_path` rather than
committed: their bytes are deterministic, so committing eight small binaries would
add a second copy of something the generator reproduces exactly, and the
determinism test below is what keeps that claim true.

    python3 -m pytest tests/test_attachment_format_fixtures.py -q
"""

import ast
import re
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from attachment_format import FORMATS, classify, classify_path  # noqa: E402
from fixtures.make_attachment_fixtures import GAPS, MATRIX, token, write_all  # noqa: E402

#: The ZIP-container formats, which share the `PK\x03\x04` signature and are the
#: reason a magic-number-only classifier is not enough.
ZIP_FAMILY = ("epub", "docx", "odt")


@pytest.fixture(scope="module")
def matrix(tmp_path_factory):
    """The whole matrix, written once by the committed generator."""
    out = tmp_path_factory.mktemp("attachment-fixtures")
    written = {name: Path(p) for name, p in write_all(out).items()}
    for name, path in written.items():
        assert path.exists(), f"{name} fixture was not written"
    return written


def body_text(name: str, path: Path) -> str:
    """Everything a reader of this file could see, without a converter.

    For the ZIP packages that means the member payloads, since the token is
    inside a deflated entry and never appears in the archive's raw bytes; for the
    PDF it means the file itself, whose content stream is deliberately
    uncompressed.
    """
    if name in ZIP_FAMILY:
        with zipfile.ZipFile(path) as package:
            return "\n".join(
                package.read(member).decode("utf-8", "replace") for member in package.namelist()
            )
    return path.read_bytes().decode("latin-1")


# --- the tokens ---------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MATRIX))
def test_every_fixture_carries_its_unique_body_token(name, matrix):
    """Without this, a later `/fulltext` probe cannot tell body extraction from a
    metadata match: every fixture shares its record metadata by construction, so a
    search that finds the title finds all nine and proves nothing."""
    assert token(name) in body_text(name, matrix[name])


def test_the_tokens_are_unique_across_the_matrix():
    tokens = [token(name) for name in MATRIX]
    assert len(set(tokens)) == len(tokens), f"a token is shared: {tokens}"


# --- the fixtures are really their formats ------------------------------------------


@pytest.mark.parametrize("name", ZIP_FAMILY)
def test_the_zip_packages_are_readable_archives(name, matrix):
    with zipfile.ZipFile(matrix[name]) as package:
        assert package.testzip() is None, "a member fails its CRC"
        assert package.namelist(), "the archive is empty"


@pytest.mark.parametrize("name", ("epub", "odt"))
def test_the_ocf_and_odf_mimetype_member_is_first_and_stored(name, matrix):
    """Both specs require it, and an archive that merely *contains* a `mimetype`
    entry somewhere is one a conforming reader rejects. A fixture wrong in that way
    would be wrong in exactly the direction this matrix exists to detect."""
    with zipfile.ZipFile(matrix[name]) as package:
        entries = package.infolist()
    assert entries[0].filename == "mimetype", f"first entry is {entries[0].filename!r}"
    assert entries[0].compress_type == zipfile.ZIP_STORED


def test_the_docx_package_carries_the_parts_that_identify_it(matrix):
    with zipfile.ZipFile(matrix["docx"]) as package:
        names = set(package.namelist())
    assert "[Content_Types].xml" in names
    assert "word/document.xml" in names
    assert "mimetype" not in names, "OOXML has no mimetype member; the fixture invented one"


def test_the_pdf_cross_reference_table_points_at_its_objects(matrix):
    """The one structural validity check the standard library can make without a
    PDF parser, and it is not a formality: the offsets are computed by the
    generator, so an edit that changes any object's length silently invalidates
    every later entry."""
    raw = matrix["pdf"].read_bytes()
    assert raw.startswith(b"%PDF-")
    assert raw.rstrip().endswith(b"%%EOF")

    start = int(re.search(rb"startxref\s+(\d+)", raw).group(1))
    assert raw[start:start + 4] == b"xref", "startxref does not point at the table"

    table = raw[start:].split(b"\n")
    count = int(table[1].split()[1])
    for number in range(1, count):
        offset = int(table[2 + number].split()[0])
        assert raw[offset:].startswith(b"%d 0 obj" % number), (
            f"xref entry {number} points at {raw[offset:offset + 16]!r}"
        )


def test_the_generator_is_deterministic(tmp_path):
    """Two runs, identical bytes. A fixture whose bytes move between runs cannot be
    a control, and the ZIP writers are where that breaks first -- `zipfile` stamps
    the clock unless it is told not to."""
    first = {name: Path(p).read_bytes() for name, p in write_all(tmp_path / "a").items()}
    second = {name: Path(p).read_bytes() for name, p in write_all(tmp_path / "b").items()}
    assert first == second


# --- the classifier, by content -----------------------------------------------------


@pytest.mark.parametrize("name", sorted(MATRIX))
def test_the_classifier_answers_the_matrix_from_bytes_alone(name, matrix):
    """`classify` is handed bytes, not a path: it cannot consult a name it never
    received."""
    verdict = classify(matrix[name].read_bytes())
    assert verdict.format == MATRIX[name]["expected"], verdict
    assert verdict.evidence, "a verdict without evidence cannot be audited"


def test_the_three_zip_container_formats_get_three_different_answers(matrix):
    """The control that stops a one-sided reading of the test above.

    EPUB, DOCX and ODT are all `PK\\x03\\x04`. A classifier that answered `docx`
    for every archive would pass one of the three cases above and fail two -- but a
    classifier that answered by *magic alone* would collapse all three into one
    answer, and this is the assertion that names that failure directly."""
    answers = {name: classify(matrix[name].read_bytes()).format for name in ZIP_FAMILY}
    assert len(set(answers.values())) == 3, f"the ZIP family collapsed: {answers}"
    assert answers == {"epub": "epub", "docx": "docx", "odt": "odt"}


def test_a_plain_zip_is_not_mistaken_for_a_document(tmp_path):
    """The negative arm of the same control: an archive that identifies itself as
    nothing is reported as an unrecognised container, not guessed into the matrix."""
    plain = tmp_path / "archive.zip"
    with zipfile.ZipFile(plain, "w") as package:
        package.writestr("notes.txt", "nothing here identifies a document format")
    verdict = classify(plain.read_bytes())
    assert verdict.format == "zip", verdict


def test_markdown_and_plain_text_are_indistinguishable_by_content(matrix):
    """Asserted on purpose, so it cannot be "fixed" quietly.

    Markdown carries no content signature. Ticket 0593 requires Markdown to be
    probed separately because a `.md` attachment need not be exposed as
    `text/plain` -- but that is a fact about Zotero, measurable only by ticket 0600.
    A leading-`#` heuristic here would manufacture a content answer the content
    does not carry, and this test is what makes adding one a visible act."""
    assert "markdown" not in FORMATS
    assert MATRIX["markdown"]["expected"] == "text"
    assert classify(matrix["markdown"].read_bytes()).format == "text"
    assert classify(matrix["txt"].read_bytes()).format == "text"


# --- the case that earns the suite its place ----------------------------------------


def naive_by_extension(path):
    """An extension-only classifier, written here because it is the thing being
    falsified. Three lines, and it is what the tracker's invariant forbids."""
    return {
        ".pdf": "pdf", ".epub": "epub", ".html": "html", ".txt": "text",
        ".md": "text", ".docx": "docx", ".odt": "odt", ".rtf": "rtf",
    }.get(Path(path).suffix.lower(), "unknown")


#: Fixture, the misleading name it is copied under, and what each classifier says.
#: Chosen so the naive answer is a *plausible* format rather than `unknown`: a
#: control the naive classifier fails by shrugging would not distinguish an
#: extension-only policy from a broken one.
MISLEADING = [
    ("epub", "report.docx", "epub", "docx"),
    ("docx", "book.epub", "docx", "epub"),
    ("odt", "page.html", "odt", "html"),
    ("pdf", "notes.txt", "pdf", "text"),
    ("txt", "paper.pdf", "text", "pdf"),
]


@pytest.mark.parametrize("name,misleading,by_content,by_extension", MISLEADING)
def test_a_misleading_extension_defeats_extension_dispatch_and_not_content(
    name, misleading, by_content, by_extension, matrix, tmp_path
):
    """The load-bearing control, in both directions at once.

    Only the second assertion would be a test of the classifier. Only the first
    would be a test that an extension table is imperfect, which nobody doubts.
    Together they are the executable form of "MIME/capability based, not an
    extension allow-list": the content classifier is right where the extension one
    is wrong, on the same bytes, differing only in the name on disk."""
    lying = tmp_path / misleading
    lying.write_bytes(matrix[name].read_bytes())

    assert naive_by_extension(lying) == by_extension, "the naive classifier changed"
    assert naive_by_extension(lying) != by_content, (
        "this case no longer discriminates: both classifiers agree"
    )
    assert classify_path(lying).format == by_content, (
        f"content classification followed the name {misleading!r}"
    )


# --- the declared gaps --------------------------------------------------------------


def test_legacy_doc_is_a_declared_gap_and_not_a_fixture():
    """Report a state you could not produce as not-produced, never as a negative.

    A hand-written `.doc` would be fiction, and every `.doc` row of ticket 0600's
    measurement would then be a statement about the fixture rather than about the
    format. The gap is declared in the generator so it travels with the matrix."""
    assert "doc" not in MATRIX, "a .doc fixture appeared; it cannot be faithful"
    assert "doc" in GAPS and GAPS["doc"].strip(), "the gap must be declared with its reason"
    assert "doc" not in FORMATS, "the classifier must not claim to identify legacy .doc"


def test_the_ole_signature_answers_the_container_family_it_can_prove():
    """The positive control for the branch the `.doc` gap leaves unexercised.

    This is NOT a `.doc` fixture: eight bytes of OLE2 header are not a Word
    document, and the classifier is asserted to say `ole-compound` -- the family --
    precisely because it cannot say more. When ticket 0600 obtains a real `.doc`,
    the member-level branch and its own positive control arrive together."""
    verdict = classify(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 24)
    assert verdict.format == "ole-compound", verdict
    assert "OLE2" in verdict.evidence


def test_unrecognisable_bytes_are_unknown_rather_than_guessed():
    assert classify(b"\x89\x01\x02\x00\xff\xfe").format == "unknown"


# --- no new dependency --------------------------------------------------------------


def test_the_classifier_and_the_generator_import_nothing_but_the_standard_library():
    """`requirements-check.txt` is three names, none of them a file-type library, and
    a lint-tier gate must not need a fourth. Checked by reading the imports rather
    than by trusting the docstring that claims it."""
    for source in (
        REPO / "bench" / "attachment_format.py",
        REPO / "bench" / "fixtures" / "make_attachment_fixtures.py",
    ):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module.split(".")[0]]
            else:
                continue
            for module in modules:
                assert module in sys.stdlib_module_names, (
                    f"{source.name} imports {module}, which is not standard library"
                )
