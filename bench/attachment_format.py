#!/usr/bin/env python3
"""Decide an attachment's format from its bytes, never from its name (ticket 0599).

Ticket 0593's invariant is that attachment-format policy is MIME/capability based
and not an extension allow-list. An invariant nothing executes is a sentence, so
this is the executable form of it: one function that reads bytes and answers a
format, and which has never been told what the file was called.

The vocabulary it answers in is deliberately small, and two of its entries are
admissions rather than identifications:

    pdf, epub, docx, odt, rtf, html   -- identified
    text                              -- identified, and it is where Markdown lands
    zip                               -- a ZIP container this does not recognise
    ole-compound                      -- the container family legacy `.doc` belongs to
    unknown                           -- nothing matched

**Markdown is not in the vocabulary, and that is a finding rather than a gap.**
Markdown has no content signature: a `.md` file and a `.txt` file with the same
bytes are the same file, and no amount of sniffing changes that. Ticket 0593
required Markdown to be probed separately precisely because a `.md` attachment
need not be exposed as `text/plain` -- but that is a fact about what *Zotero*
reports, measurable only against a running Zotero (ticket 0600), and inventing a
leading-`#` heuristic here would manufacture a content answer the content does
not carry. `tests/test_attachment_format_fixtures.py` asserts the
indistinguishability explicitly, so nobody can later add that heuristic quietly.

**`ole-compound` is the honest half of the `.doc` gap.** The 8-byte signature
identifies the OLE2 compound-document container, which a legacy `.doc` uses and
so does a legacy `.xls`. Separating them means walking the container's directory
for a `WordDocument` stream, and there is no `.doc` fixture in this repository to
exercise that walk against -- ticket 0593 authorizes no converter to produce one.
So this answers the family it can prove and refuses the member it cannot. When
ticket 0600 obtains a real `.doc`, the branch and its positive control arrive
together.

Stdlib only, and it must stay that way: `requirements-check.txt` is three names
and none of them is a file-type library. Nothing here shells out to `file(1)`
either -- it is not guaranteed present, and its output is a human-readable string
rather than a contract.
"""

import io
import zipfile
from dataclasses import dataclass

#: The closed answer set. A caller comparing against a literal not in here has a
#: typo, not a format.
FORMATS = (
    "pdf",
    "epub",
    "docx",
    "odt",
    "rtf",
    "html",
    "text",
    "zip",
    "ole-compound",
    "unknown",
)

#: Signatures read at offset 0.
PDF_MAGIC = b"%PDF-"
RTF_MAGIC = b"{\\rtf"
ZIP_MAGIC = b"PK\x03\x04"
#: The OLE2 / Compound File Binary header. Legacy `.doc`, `.xls` and `.ppt`
#: all carry it; it names the container, not the document.
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

#: The `mimetype` member of an OCF/ODF package, which the format spells out for
#: exactly this purpose: the first entry, stored uncompressed, saying what the
#: container holds.
CONTAINER_MIMETYPES = {
    "application/epub+zip": "epub",
    "application/vnd.oasis.opendocument.text": "odt",
}

#: How far into a text file the markup sniff looks. A document whose first half
#: kilobyte carries no HTML root is being read as text, which is what a consumer
#: extracting body text would do with it anyway.
SNIFF_WINDOW = 512

#: Root-element markers. Deliberately not a general tag sniff: an XML file that
#: merely contains a `<p>` is not HTML, and answering `html` for it would put a
#: format in the policy matrix that nothing measured.
HTML_MARKERS = ("<!doctype html", "<html", "<head")


@dataclass(frozen=True)
class Verdict:
    """A format, and what decided it.

    The evidence field is not decoration. A verdict of `text` reached by "no
    signature matched, and it decoded" is a much weaker statement than one of
    `epub` reached by reading the container's own declared mimetype, and a
    measurement pass that records only the format loses that difference.
    """

    format: str
    evidence: str

    def __post_init__(self):
        assert self.format in FORMATS, f"not a format in the closed set: {self.format!r}"


def _classify_zip(data: bytes) -> Verdict:
    """Inside the ZIP family, where EPUB, DOCX and ODT are indistinguishable by magic.

    Read in the order the formats themselves declare: the OCF/ODF `mimetype`
    member is authoritative when present, and OOXML has no such member, so it is
    identified by the package parts it must carry.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            names = set(package.namelist())
            if "mimetype" in names:
                declared = package.read("mimetype").decode("ascii", "replace").strip()
                found = CONTAINER_MIMETYPES.get(declared)
                if found:
                    return Verdict(found, f"zip container, mimetype member {declared!r}")
                return Verdict("zip", f"zip container, unrecognised mimetype {declared!r}")
            if "[Content_Types].xml" in names and "word/document.xml" in names:
                return Verdict("docx", "zip container, OOXML content types and word/document.xml")
            return Verdict("zip", f"zip container, {len(names)} entries, none identifying")
    except (zipfile.BadZipFile, KeyError, OSError) as broken:
        # A truncated or damaged archive is not a format. Saying so beats
        # guessing `docx` from the four bytes at the front, which is exactly the
        # extension-style reasoning this module exists to refuse.
        return Verdict("unknown", f"zip signature, unreadable container: {broken}")


def _classify_text(data: bytes) -> Verdict | None:
    """Text, and whether it is markup. None when the bytes are not text at all."""
    if b"\x00" in data:
        return None
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    window = decoded[:SNIFF_WINDOW].lstrip("﻿ \t\r\n").lower()
    for marker in HTML_MARKERS:
        if marker in window:
            return Verdict("html", f"utf-8 text whose head carries {marker!r}")
    return Verdict("text", "utf-8 text with no binary signature and no markup root")


def classify(data: bytes) -> Verdict:
    """The format of these bytes.

    Order matters and is not arbitrary: every binary signature is checked before
    anything is decoded, because a signature is a claim the format makes about
    itself and a successful UTF-8 decode is only the absence of one.
    """
    if data.startswith(PDF_MAGIC):
        return Verdict("pdf", "%PDF- header")
    if data.startswith(OLE_MAGIC):
        return Verdict("ole-compound", "OLE2 compound-document header")
    if data.startswith(RTF_MAGIC):
        return Verdict("rtf", "{\\rtf header")
    if data.startswith(ZIP_MAGIC):
        return _classify_zip(data)
    as_text = _classify_text(data)
    if as_text is not None:
        return as_text
    return Verdict("unknown", "no signature matched and the bytes are not utf-8 text")


def classify_path(path) -> Verdict:
    """The format of the file at `path`, read from its bytes.

    The name is used to open the file and for nothing else. That is the whole
    point, and it is why this takes a path at all rather than making every caller
    write the `read_bytes()` themselves and be trusted not to peek at the suffix.
    """
    with open(path, "rb") as handle:
        return classify(handle.read())
