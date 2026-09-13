"""A handful-of-documents RIS fixture for the sitter's real-Zotero smoke test.

Ticket 0784. The volume rig's `--menagerie` deliberately imports the 666 MB
Multilingual Menagerie so the sitter is doing real extraction work while it is
replaced under itself -- the right substrate for THAT experiment, and the wrong
one for a smoke test that has to census in seconds and run on every branch that
touches the sitter. This module writes three tiny, genuinely valid one-page PDFs
via `fixtures.make_attachment_fixtures.write_pdf` -- the same generator
`tests/test_attachment_format_fixtures.py` already holds to a validity check and
the exact function `verification/probes/run_sdt_diagnostic.py` calls for its own
PDF fixture -- rather than inventing a second minimal-PDF writer, or committing
static binaries the generator reproduces byte-identically anyway (the reasoning
`tests/test_attachment_format_fixtures.py`'s own docstring gives for not
committing its matrix).

Nothing here is committed as a binary. `write_smoke_library()` writes the RIS
and its three attachments fresh, into a directory you name -- always a scratch
directory, never `bench/fixtures/` itself.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixtures.make_attachment_fixtures import write_pdf  # noqa: E402

#: One item per attachment, kept to three: enough for the census to have more
#: than one item to count without turning the smoke test into a timing
#: exercise. `TI`/`AU`/`PY` are the fields `Zotero.Translate.Import`'s RIS
#: translator actually reads; nothing here exercises a corner the golden
#: fixture doesn't already cover in depth.
_ITEMS = [
    ("SMOKE0001", "Sitter smoke fixture, item one", "smoke-1.pdf"),
    ("SMOKE0002", "Sitter smoke fixture, item two", "smoke-2.pdf"),
    ("SMOKE0003", "Sitter smoke fixture, item three", "smoke-3.pdf"),
]

RIS_NAME = "smoke.ris"


def write_smoke_library(dest_dir: Path) -> Path:
    """Write `smoke.ris` and its `attachments/` beside it under `dest_dir`.

    Returns the RIS path. Refuses a `dest_dir` that already holds the RIS, on
    the same principle every throwaway-state check in this tree follows: a
    fixture writer that silently overwrote existing state could paper over a
    caller reusing a directory it should not be reusing.
    """
    ris_path = dest_dir / RIS_NAME
    if ris_path.exists():
        raise FileExistsError(f"refusing to overwrite {ris_path}; pass a fresh dest_dir")
    attachments_dir = dest_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for item_id, title, filename in _ITEMS:
        write_pdf(attachments_dir / filename)
        entries.append(
            "TY  - GEN\n"
            f"ID  - {item_id}\n"
            f"TI  - {title}\n"
            "AU  - Sitter Smoke Test\n"
            "PY  - 2026\n"
            f"L1  - attachments/{filename}\n"
            "ER  - \n"
        )
    ris_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
    return ris_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = write_smoke_library(args.output_dir)
    print(path)
