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

import shutil
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


#: The Menagerie package on the author's machines, per the contract of
#: 2026-09-06. Not a hard dependency: `write_smoke_library` falls back to the
#: generated PDFs when it is absent, and says which it used.
DEFAULT_MENAGERIE = Path.home() / "data" / "menagerie-package"


def pick_menagerie_documents(package_dir: Path, count: int | None = 3,
                             suffixes: tuple[str, ...] | None = (".pdf",)) -> list[Path]:
    """The `count` smallest files in a Menagerie package, smallest first.

    Deterministic (size, then name) so two runs on one package census the same
    documents and their `source.hash` assertions compare. Smallest first
    because this is a smoke test: the volume rig is where big documents belong.

    The defaults are the smoke rung's selection -- three PDFs -- and stay so:
    smallest files of any type would hand it HTML with no pack (ticket 0821).
    Rung 3 widens by parameter instead: `suffixes=None` takes every file in
    `attachments/`, and `count=None` takes all of them.
    """
    attachments = package_dir / "attachments"
    if not attachments.is_dir():
        return []
    files = [f for f in attachments.iterdir() if f.is_file()
             and (suffixes is None or f.suffix in suffixes)]
    files.sort(key=lambda f: (f.stat().st_size, f.name))
    return files if count is None else files[:count]


def write_menagerie_subset(dest_dir: Path, documents: list[Path]) -> Path:
    """Write `smoke.ris` and copies of `documents` beside it under `dest_dir`.

    Copies rather than links the PDFs: the run's data directory is throwaway
    and Zotero is about to be pointed at these files, and a rig that handed a
    real library's bytes to a process it then kills has no business doing so
    through a link into the author's own storage.
    """
    ris_path = dest_dir / RIS_NAME
    if ris_path.exists():
        raise FileExistsError(f"refusing to overwrite {ris_path}; pass a fresh dest_dir")
    attachments_dir = dest_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for n, source in enumerate(documents, start=1):
        shutil.copy2(source, attachments_dir / source.name)
        # The stem is the Menagerie's own slug -- readable in a failure message
        # and stable across runs, which a synthesised title would not be.
        entries.append(
            "TY  - GEN\n"
            f"ID  - MENAGERIE{n:04d}\n"
            f"TI  - {source.stem}\n"
            "AU  - Sitter Smoke Test\n"
            "PY  - 2026\n"
            f"L1  - attachments/{source.name}\n"
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
