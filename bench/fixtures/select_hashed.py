#!/usr/bin/env python3
"""Select the source recipe's currently-hashed subset for a real injection/export.

Ticket 0029's ``recipe.json`` carries records with no pinned ``sha256`` yet --
open, browser-only sourcing (ticket 0632's log).  ``golden_fixture.py``'s
``verify_source_bytes`` refuses the whole recipe if any one record is
unpinned, by design: an injection or export must never proceed on an
unverified document.  So a real run against "the 17 already-hashed
documents" (ticket 0029's own sequencing note) needs a recipe file that
holds exactly that subset, in the parent recipe's own order, and that file
is what ``inject``, ``export``, and the offline replay all read -- one file,
so the export manifest's ``recipe_sha256`` pins the same content the replay
later re-derives.

This is derived data, not hand-curated: re-run it whenever ``recipe.json``
gains a new pinned hash, rather than hand-editing the output.
"""

import argparse
import json
from pathlib import Path


def load_recipe(path: Path) -> list[dict]:
    """Deferred import, matching golden_fixture.py's own `_load_recipe`: the
    module must stay importable (e.g. by a test) without bench/fixtures
    already on sys.path, which only holds when this file is run directly as
    a script."""
    from fetch_recipe import load_recipe as _load_recipe

    return _load_recipe(path)


def select_hashed(recipe: list[dict]) -> list[dict]:
    """Keep only records whose every attachment source has a pinned sha256."""
    kept = []
    for doc in recipe:
        sources = doc.get("attachments", [doc])
        if all(isinstance(source.get("sha256"), str) and len(source["sha256"]) == 64 for source in sources):
            kept.append(doc)
    return kept


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", type=Path, default=Path(__file__).with_name("recipe.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    recipe = load_recipe(args.recipe)
    hashed = select_hashed(recipe)
    args.output.write_text(
        json.dumps(hashed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{len(hashed)} of {len(recipe)} records are pinned; wrote {args.output}")


if __name__ == "__main__":
    main()
