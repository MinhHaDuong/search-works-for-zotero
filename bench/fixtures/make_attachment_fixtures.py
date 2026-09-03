#!/usr/bin/env python3
"""Write the attachment-format fixture matrix: one minimal, valid file per format.

Ticket 0599, the machine-free child of tracker 0593. The matrix exists so that
ticket 0600 can drive a real Zotero over a substrate whose contents are already
known. That order is what keeps the measurement from being circular: if the
fixtures' formats were asserted rather than detectable, Zotero would be graded
against a claim about the file instead of against the file.

Two properties every fixture carries, and both are load-bearing:

  * **It is genuinely valid.** The ZIP packages open, the OCF and ODF `mimetype`
    members are first and stored uncompressed as their specs require, the PDF's
    cross-reference offsets point at its object headers. A fixture that only
    looks like its format measures nothing about the format.
  * **It carries a unique body token.** `ZZFMT<FORMAT><6 hex>`, derived from the
    format name so it is stable across runs and machines. Without it, a later
    full-text probe cannot tell real body extraction from a hit on the shared
    record metadata -- which is the single most likely way an attachment-format
    measurement reports success it did not earn.

Deterministic by construction: fixed ZIP timestamps, no clock, no randomness. Two
runs produce identical bytes, which is what lets a fixture be a control.

## The stated gap: legacy `.doc`

**There is no `.doc` fixture, and there will not be one written from bytes here.**
A legacy `.doc` is an OLE2 compound binary whose `WordDocument` stream is a File
Information Block with a layout no hand-written fixture reproduces, and ticket
0593 explicitly authorizes no converter -- no LibreOffice, no Pandoc, no Tika --
to produce one. A plausible-looking fake would make every `.doc` row of ticket
0600's measurement a statement about the fixture rather than about the format,
and a matrix with one fictional row is a matrix nobody can cite. Eight honest
fixtures and one declared gap are worth more than nine of which one is fiction.

Ticket 0600 carries the gap as an open item, to be settled one of two ways: a
real `.doc` supplied from outside the repository and measured like every other
row, or the row ruled on the format's documented behaviour with the absence of a
measurement recorded beside the ruling rather than left to look like one.

Markdown is a second, milder case of the same honesty, and it lands in
`bench/attachment_format.py` rather than here: the `.md` fixture is real, but its
bytes are text and nothing in them says `markdown`.

    python3 bench/fixtures/make_attachment_fixtures.py --output-dir <dir>
    python3 bench/fixtures/make_attachment_fixtures.py --fixture epub --output f.epub
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

#: Fixed ZIP member timestamp. `zipfile` would otherwise stamp the clock, and a
#: fixture whose bytes change between runs cannot be a control.
ZIP_EPOCH = (2026, 9, 2, 0, 0, 0)


def token(fixture: str) -> str:
    """The unique body token for one fixture.

    Recognisably synthetic, one unbroken alphanumeric run so no tokenizer splits
    it, and derived from the fixture name so it is the same on every machine.
    """
    digest = hashlib.sha256(fixture.encode("utf-8")).hexdigest()[:6].upper()
    return f"ZZFMT{fixture.upper()}{digest}"


# --- the flat formats ---------------------------------------------------------------


def write_txt(path: Path) -> Path:
    body = f"Attachment format fixture, plain text.\n\n{token('txt')}\n"
    path.write_bytes(body.encode("utf-8"))
    return path


def write_markdown(path: Path) -> Path:
    """A real Markdown document, whose bytes are nevertheless just text.

    The heading and the emphasis are here so the file is what a `.md` attachment
    looks like, not so a sniffer can find them: `bench/attachment_format.py`
    deliberately does not look, and this fixture is the positive control for that
    refusal.
    """
    body = (
        "# Attachment format fixture\n"
        "\n"
        "Markdown, which is *text* and carries no content signature.\n"
        "\n"
        f"{token('markdown')}\n"
    )
    path.write_bytes(body.encode("utf-8"))
    return path


def write_html(path: Path) -> Path:
    body = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        '<head><meta charset="utf-8"><title>Attachment format fixture</title></head>\n'
        f"<body><p>{token('html')}</p></body>\n"
        "</html>\n"
    )
    path.write_bytes(body.encode("utf-8"))
    return path


def write_rtf(path: Path) -> Path:
    """Rich Text Format, which is plain ASCII with a `{\\rtf` header.

    Faithful without a converter: RTF is a text format by design, so a
    hand-written document is a real one rather than an imitation of one.
    """
    body = (
        "{\\rtf1\\ansi\\ansicpg1252\\deff0"
        "{\\fonttbl{\\f0\\froman\\fcharset0 Times New Roman;}}\n"
        "\\f0\\fs24 Attachment format fixture, rich text.\\par\n"
        f"{token('rtf')}\\par\n"
        "}\n"
    )
    path.write_bytes(body.encode("ascii"))
    return path


# --- PDF ----------------------------------------------------------------------------


def write_pdf(path: Path) -> Path:
    """A one-page PDF with an uncompressed content stream carrying the token.

    The stream is uncompressed on purpose. A `FlateDecode` stream would be just as
    valid and would hide the token from anything that greps the file, and the
    fixture's job downstream is to be found by a text extractor -- so the token
    sits in a plain `Tj` operator where `pdftotext` and Zotero's own extractor
    both reach it.

    Offsets are computed rather than written down, and the cross-reference table
    is built from them. `tests/test_attachment_format_fixtures.py` walks that
    table back to the object headers, which is the one structural validity check
    the standard library can make without a PDF parser.
    """
    stream = f"BT /F1 24 Tf 72 700 Td ({token('pdf')}) Tj ET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number
        out += payload
        out += b"\nendobj\n"

    startxref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    out += b"startxref\n%d\n%%%%EOF\n" % startxref

    path.write_bytes(bytes(out))
    return path


# --- the ZIP family -----------------------------------------------------------------


def _zip(path: Path, members, first_stored=None) -> Path:
    """Write a deterministic ZIP.

    `first_stored` is the OCF/ODF `mimetype` member, which both specs require to
    be the archive's FIRST entry and stored uncompressed. Writing it like any
    other member produces an archive that opens fine and that a reader following
    the spec rejects -- a fixture wrong in exactly the way this matrix exists to
    detect.
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        if first_stored is not None:
            name, payload = first_stored
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_STORED
            package.writestr(info, payload)
        for name, payload in members:
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, payload)
    return path


def write_epub(path: Path) -> Path:
    """A minimal EPUB 3 package: OCF container, one package document, one chapter."""
    chapter = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">\n'
        "<head><title>Attachment format fixture</title></head>\n"
        f"<body><p>{token('epub')}</p></body>\n"
        "</html>\n"
    )
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="pub-id">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        '    <dc:identifier id="pub-id">urn:uuid:zzfixture-epub</dc:identifier>\n'
        "    <dc:title>Attachment format fixture</dc:title>\n"
        "    <dc:language>en</dc:language>\n"
        '    <meta property="dcterms:modified">2026-09-02T00:00:00Z</meta>\n'
        "  </metadata>\n"
        "  <manifest>\n"
        '    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>\n'
        "  </manifest>\n"
        '  <spine><itemref idref="chapter"/></spine>\n'
        "</package>\n"
    )
    container = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles>\n'
        "</container>\n"
    )
    return _zip(
        path,
        [
            ("META-INF/container.xml", container),
            ("OEBPS/content.opf", opf),
            ("OEBPS/chapter.xhtml", chapter),
        ],
        first_stored=("mimetype", "application/epub+zip"),
    )


def write_odt(path: Path) -> Path:
    """A minimal OpenDocument text package: mimetype, manifest, content."""
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'office:version="1.3">\n'
        "  <office:body><office:text>\n"
        f"    <text:p>{token('odt')}</text:p>\n"
        "  </office:text></office:body>\n"
        "</office:document-content>\n"
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest '
        'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.3">\n'
        '  <manifest:file-entry manifest:full-path="/" '
        'manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
        '  <manifest:file-entry manifest:full-path="content.xml" '
        'manifest:media-type="text/xml"/>\n'
        "</manifest:manifest>\n"
    )
    return _zip(
        path,
        [("META-INF/manifest.xml", manifest), ("content.xml", content)],
        first_stored=("mimetype", "application/vnd.oasis.opendocument.text"),
    )


def write_docx(path: Path) -> Path:
    """A minimal OOXML WordprocessingML package.

    No `mimetype` member: OOXML declares itself through `[Content_Types].xml` and
    the package parts instead, which is why the classifier needs a second rule for
    this family and why all three ZIP formats need their own control.
    """
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
        '2006/main">\n'
        "  <w:body>\n"
        f"    <w:p><w:r><w:t>{token('docx')}</w:t></w:r></w:p>\n"
        "  </w:body>\n"
        "</w:document>\n"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/word/document.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
        "</Types>\n"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships">\n'
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
        "</Relationships>\n"
    )
    return _zip(
        path,
        [
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", rels),
            ("word/document.xml", document),
        ],
    )


# --- the matrix ---------------------------------------------------------------------

#: One row per fixture: the file name it is written under, the writer, and the
#: answer `bench/attachment_format.py` must give for its bytes.
#:
#: `markdown` expecting `text` is not an oversight. Markdown has no content
#: signature, and recording the honest answer here is what makes the expectation
#: checkable; see the classifier's docstring.
#:
#: `doc` has no row at all. See this module's docstring: the gap is stated, not
#: filled with a fake.
MATRIX = {
    "pdf": {"filename": "fixture.pdf", "writer": write_pdf, "expected": "pdf"},
    "epub": {"filename": "fixture.epub", "writer": write_epub, "expected": "epub"},
    "html": {"filename": "fixture.html", "writer": write_html, "expected": "html"},
    "txt": {"filename": "fixture.txt", "writer": write_txt, "expected": "text"},
    "markdown": {"filename": "fixture.md", "writer": write_markdown, "expected": "text"},
    "docx": {"filename": "fixture.docx", "writer": write_docx, "expected": "docx"},
    "odt": {"filename": "fixture.odt", "writer": write_odt, "expected": "odt"},
    "rtf": {"filename": "fixture.rtf", "writer": write_rtf, "expected": "rtf"},
}

#: The formats ticket 0593 named that this generator does NOT produce, and why.
#: Read by the test suite so the gap cannot be quietly forgotten, and carried into
#: ticket 0600 as an open item.
GAPS = {
    "doc": (
        "legacy .doc is an OLE2 compound binary whose WordDocument stream cannot be "
        "synthesized faithfully from bytes, and ticket 0593 authorizes no converter "
        "to produce one; ticket 0600 settles the row"
    ),
}


def write_all(directory: Path) -> dict[str, str]:
    """Every fixture of the matrix into one directory. Returns name to path."""
    directory.mkdir(parents=True, exist_ok=True)
    return {
        name: str(row["writer"](directory / row["filename"])) for name, row in MATRIX.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, help="write the whole matrix here")
    parser.add_argument("--fixture", choices=sorted(MATRIX), help="write one fixture")
    parser.add_argument("--output", type=Path, help="where --fixture writes")
    args = parser.parse_args()

    if args.output_dir:
        print(json.dumps(write_all(args.output_dir), indent=2, sort_keys=True))
        return 0
    if args.fixture and args.output:
        MATRIX[args.fixture]["writer"](args.output)
        print(args.output)
        return 0
    parser.error("give --output-dir, or --fixture with --output")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
