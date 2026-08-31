#!/usr/bin/env python3
"""Committed artifacts identify a library document by its key, never by its name.

Ratified 2026-08-31 (`spec/DECISIONS.md`): a measurement record names a document
in the author's library by its Zotero item key and by nothing else. The reason is
not that a title is secret. It is that this repository is public and permanent,
so every provenance field naming what the author reads discloses the library one
figure at a time, and the disclosure outlives whatever the figure was for. A key
carries every property provenance needs — stable, unique, resolvable by whoever
holds the library — and none of the properties that make a title a leak.

The rule this enforces is structural rather than a denylist, because a denylist
of the author's own reading would have to contain the thing it protects. At the
root of an artifact, `title` names the artifact itself and is fine. Nested
anywhere below the root, a name-bearing field is describing something the run
touched, which is a library document, which is the leak.

The defect this exists to stop is recurrence by tooling rather than by hand:
two drivers wrote titles into every result they produced, and 4 630 name fields
reached the public tree before anyone read one. A rule with no guard is a habit,
and this repository's habits drift.

Scope note: `passage` and `snippet` fields carry library *text*, a larger
disclosure than a title, and the benchmark query sets are the author's own
research questions. Neither is decided by the ruling this guard enforces, so
neither is checked here. When they are ruled on, they belong in this guard.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Where measurement artifacts live. The only tree this guard reads.
ARTIFACTS = "bench/results"

#: Fields that name a document rather than addressing it. `titles` and
#: `first_title` are here because both actually shipped: the rule has to catch
#: the plural and the prefixed variant, not just the obvious singular.
NAME_FIELDS = frozenset(
    {"title", "titles", "first_title", "filename", "creator", "creators", "author"}
)


def offences(document: object, path: str = "", depth: int = 0) -> list[str]:
    """Every name-bearing field below the root of one artifact, by JSON path.

    Depth 0 is the artifact's own object, where `title` names the artifact. Every
    level below it describes something the run touched.
    """
    found: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            here = f"{path}/{key}"
            if depth > 0 and key in NAME_FIELDS:
                found.append(here)
            found.extend(offences(value, here, depth + 1))
    elif isinstance(document, list):
        for index, value in enumerate(document):
            found.extend(offences(value, f"{path}[{index}]", depth + 1))
    return found


def run(repo: Path) -> int:
    root = repo / ARTIFACTS
    if not root.is_dir():
        print(f"{ARTIFACTS}/ not found under {repo}", file=sys.stderr)
        return 1

    scanned = 0
    failures = 0
    for path in sorted(root.rglob("*.json")):
        relative = path.relative_to(repo).as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as why:
            print(f"{relative}: unreadable ({why})", file=sys.stderr)
            failures += 1
            continue
        scanned += 1
        for where in offences(document):
            print(
                f"{relative}: {where} names a document instead of addressing it. "
                f"Record the Zotero item key and drop the name.",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(
            f"\n{failures} name field(s) in committed artifacts. A library document "
            f"is identified by its item key (spec/DECISIONS.md, 2026-08-31).",
            file=sys.stderr,
        )
        return 1

    print(
        f"{scanned} artifacts scanned, {len(NAME_FIELDS)} name fields tracked: "
        f"documents are addressed by key, not named"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(REPO), help="repository root to check")
    args = parser.parse_args()
    return run(Path(args.repo))


if __name__ == "__main__":
    raise SystemExit(main())
