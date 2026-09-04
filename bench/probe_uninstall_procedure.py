#!/usr/bin/env python3
"""Does the drafted removal procedure actually leave zero residue?

Ticket 0630, child of tracker 0613's gap B. `verification/UNINSTALL-DRAFT-0630.md`
names one thing to delete -- the directory `ZOTEUS_DATA_DIR` resolves to, which
`bench/acceptance/adapters/zoteus.py`'s `Declaration` declares as this target's
one `derived_state_roots` entry -- and `tests/test_uninstall_doc.py` checks that
the draft's PROSE names the right symbol. Nothing before this script had ever
run the procedure against a real installed target and swept for what remained.
That is what this closes: an end-to-end red-then-green, not a text assertion.

**Real state, not a fixture.** This drives the real adapter against a real
`fork/` build, under the ratified dedicated-account posture (`posture.py`,
ticket 0625), and calls `zotero_index` with `action:"build", limit:1` so the
run downloads real on-device model weights and writes a real SQLite index --
the two things the pre-#27 worked example in the draft says a naive "delete
the data directory" reading used to miss. `--limit` items is enough: R15 asks
whether every location that received a write survives a correct delete, and a
7 546-item build and a 1-item build write to the exact same set of paths.

**The removal itself never runs a shell.** Per the 2026-09-03T12:48Z safety
correction in tracker 0613's log: "the harness transcribes paths and executes
nothing." This script reads `target.declaration.derived_state_roots` -- the
adapter's own declared list, the same one the draft's removal step is checked
against -- and deletes exactly those paths with `shutil.rmtree`/`Path.unlink`.
It never parses or runs the draft's fenced shell commands; those are prose for
a human, and treating them as a script to execute is exactly the failure mode
the ruling closed off.

**Red before green, on the same run.** A single declared root can only be
right or wrong as a whole, so the interesting failure this script can still
exhibit is a *partial* delete -- exactly the pre-#27 case the draft's worked
example describes, where the model cache lived outside the one path a naive
uninstaller deleted. So the negative control here deletes everything the run
created under the declared root EXCEPT the `models/` subdirectory once, and
confirms the survivor sweep -- the same `Snapshot`/`residue` machinery
`assertions.py`'s `check_uninstall_removes_declared_state` and
`check_residue_inventory` use -- reports it. Only then does the real deletion
run, and only then is a zero-residue result trusted.

Diagnostic, like `bench/probe_getaddrinfo_shape.py`: it does not feed
`R15-uninstall-removes-declared-state`, whose `not-offered` verdict is
unchanged (the adapter's `uninstall()` still raises `UnsupportedVerb` -- that
is a separate, larger question about whether this harness should ever call a
verb the target does not offer, not this script's business). What this
answers is narrower and, for the ladder, sufficient: does the PUBLISHED
PROCEDURE, executed as written and swept the way the ratified interface
grades uninstall, leave zero residue.
"""

import argparse
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acceptance import posture as posture_mod  # noqa: E402
from acceptance.adapters import zoteus as zoteus_mod  # noqa: E402
from acceptance.assertions import Snapshot  # noqa: E402

log = logging.getLogger("probe_uninstall_procedure")


def _delete_paths(paths: list[Path]) -> None:
    """Delete exactly these paths, without a shell.

    Mirrors the ruling: the caller hands this function a list of paths it
    already resolved (from the Declaration, never from parsing prose), and
    this function's only job is to remove exactly them -- a file is
    `unlink()`ed, a directory is `shutil.rmtree()`d, and a path that is
    already gone is skipped rather than raising, since "already removed" is
    not a failure of a removal procedure.
    """
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def _survivors(declared_roots: tuple[Path, ...]) -> list[Path]:
    """The same computation `check_uninstall_removes_declared_state` makes."""
    return sorted(
        p for root in declared_roots for p in Snapshot.of(root).files
    )


def run(*, entrypoint: Path, transformers_path: str, arena: Path,
        posture_name: str, zotero_data_dir: str, build_limit: int,
        poll_timeout: float) -> dict:
    posture = posture_mod.resolve(posture_name)
    if posture.refused is not None:
        return {"error": f"posture {posture_name!r} unavailable: {posture.refused}"}

    arena.mkdir(parents=True, exist_ok=True)
    if any(Snapshot.of(arena).files):
        return {"error": f"arena {arena} is not clean; refusing to sweep from a dirty baseline"}
    before = Snapshot.of(arena)

    target = zoteus_mod.build(
        "zoteus", arena,
        entrypoint=str(entrypoint),
        transformers_path=transformers_path,
        zotero_data_dir=zotero_data_dir,
        posture=posture,
    )
    declared_roots = tuple(Path(p) for p in target.declaration.derived_state_roots)
    log.info("declared roots: %s", [str(p) for p in declared_roots])

    with target.running():
        install_event = target.install()
        configure_event = target.configure()
        build_kickoff = target._call(
            "zotero_index", {"action": "build", "limit": build_limit,
                              "own_words": False, "fulltext": False})
        deadline = time.time() + poll_timeout
        final_status = build_kickoff
        while time.time() < deadline:
            final_status = target._call("zotero_index", {"action": "status"})
            if final_status.get("state") in ("done", "error"):
                break
            time.sleep(2)
        else:
            return {"error": f"index build did not reach done/error within {poll_timeout}s",
                    "last_status": final_status}

    materialized = Snapshot.of(arena)
    created = materialized.since(before)
    survivors_after_install = _survivors(declared_roots)

    log.info("materialized %d files under the arena, %d under declared roots",
              len(created), len(survivors_after_install))

    # -- negative control: delete everything except the model cache once ----
    data_dir = declared_roots[0]  # the adapter declares exactly one root
    top_level = sorted(data_dir.iterdir()) if data_dir.is_dir() else []
    skip_name = "models"
    incomplete_targets = [p for p in top_level if p.name != skip_name]
    skipped = [p for p in top_level if p.name == skip_name]
    if not skipped:
        return {"error": f"no {skip_name!r} entry was created under {data_dir}; "
                          "the negative control has nothing to withhold, "
                          "so this run cannot demonstrate the check would catch a partial delete",
                "materialized": sorted(str(p) for p in created)}

    _delete_paths(incomplete_targets)
    survivors_after_partial = _survivors(declared_roots)
    negative_control_caught_it = len(survivors_after_partial) > 0

    # -- the real procedure: delete exactly the declared roots, no shell ----
    _delete_paths(list(declared_roots))
    survivors_after_full = _survivors(declared_roots)
    after_full = Snapshot.of(arena)
    residue_after_full = after_full.since(before)

    return {
        "posture": posture.as_json(),
        "declaration": {
            "revision": target.declaration.revision,
            "derived_state_roots": [str(p) for p in declared_roots],
        },
        "install_event": install_event,
        "configure_event": configure_event,
        "index_build": {"kickoff": build_kickoff, "final_status": final_status},
        "materialized_by_the_real_run": sorted(str(p) for p in created),
        "materialized_count": len(created),
        "survivors_after_install": sorted(str(p) for p in survivors_after_install),
        "negative_control": {
            "description": (
                f"deleted every top-level entry under the declared root EXCEPT "
                f"{skip_name!r} once, then re-swept -- this is the pre-#27 failure "
                "mode the draft's worked example describes, reproduced deliberately"
            ),
            "withheld": sorted(str(p) for p in skipped),
            "deleted": sorted(str(p) for p in incomplete_targets),
            "survivors_after_partial_delete": sorted(str(p) for p in survivors_after_partial),
            "caught_the_incomplete_delete": negative_control_caught_it,
        },
        "real_procedure": {
            "description": (
                "deleted exactly target.declaration.derived_state_roots -- the same "
                "paths the draft's step 3 names -- via shutil.rmtree/Path.unlink, "
                "never a shell, never the draft's own prose"
            ),
            "deleted": [str(p) for p in declared_roots],
            "survivors_after_full_delete": sorted(str(p) for p in survivors_after_full),
            "arena_residue_after_full_delete": sorted(str(p) for p in residue_after_full),
        },
        "verdict": {
            "positive_control_fired": negative_control_caught_it,
            "residue_after_real_procedure": len(residue_after_full),
            "pass": negative_control_caught_it and len(residue_after_full) == 0,
        },
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrypoint", required=True, type=Path,
                     help="the built fork/dist/index.js to run")
    ap.add_argument("--transformers-path", default="",
                     help="node_modules directory holding @huggingface/transformers")
    ap.add_argument("--zotero-data-dir", default="",
                     help="a real Zotero desktop data directory (optional -- the local "
                          "API is reachable over loopback regardless of user identity, "
                          "so a resident Zotero desktop answers even without this)")
    ap.add_argument("--arena", required=True, type=Path,
                     help="an empty, harness-owned directory this run may fill")
    ap.add_argument("--posture", default="account", choices=list(posture_mod.POSTURES))
    ap.add_argument("--build-limit", type=int, default=1,
                     help="items to index -- 1 is enough to exercise every declared path")
    ap.add_argument("--poll-timeout", type=float, default=120.0)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    result = run(
        entrypoint=args.entrypoint, transformers_path=args.transformers_path,
        arena=args.arena, posture_name=args.posture,
        zotero_data_dir=args.zotero_data_dir, build_limit=args.build_limit,
        poll_timeout=args.poll_timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")

    if "error" in result:
        log.error("FAILED: %s", result["error"])
        return 1
    verdict = result["verdict"]
    log.info("positive control (partial delete caught): %s", verdict["positive_control_fired"])
    log.info("residue after the real procedure: %d", verdict["residue_after_real_procedure"])
    log.info("PASS" if verdict["pass"] else "FAIL")
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
