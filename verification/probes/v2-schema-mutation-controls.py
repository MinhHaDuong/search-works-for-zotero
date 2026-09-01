#!/usr/bin/env python3
"""Positive controls for ticket 0556's v2 content-schema tests.

A test suite that has never been red proves nothing about the defects it claims to
catch: an assertion can pass because the implementation is right, or because the
assertion looks at the wrong thing. This applies a deliberate defect to the fork's
`ledger.ts` one at a time and reports which tests notice.

Each mutation is aimed at one assertion. The run is a pass only when every mutation
goes red — a survivor names a test whose green is unearned.

Usage
-----
    python3 verification/probes/v2-schema-mutation-controls.py <path-to-fork-checkout>

The fork is the git-ignored `fork/` checkout (`make upstream-checkout`) on the branch
carrying the schema, with `npm ci` already run. The script patches `ledger.ts` in place
and restores it in a `finally`, so an interrupted run leaves the tree as it found it —
but it is still a working-tree mutator, so run it on a clean tree and check `git status`
after.

Result, 2026-09-01, fork branch `tranche-schema-v2-content` @ 05b40e0, node v22.23.1
(SQLite 3.51.3): baseline 32 tests green, 12 mutations applied, 12 caught, 0 survivors.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

TEST = "tests/features/conductor-content-schema.test.ts"
LEDGER_REL = "src/features/search/conductor/ledger.ts"

#: (name, anchor, replacement). The anchor must be unique in the file; a missing anchor
#: is reported rather than skipped silently, because a mutation that no longer applies is
#: a control that has stopped running, which is exactly the failure this file guards.
MUTATIONS = [
    (
        "drop the 1 MiB slab CHECK",
        "CHECK (length(bytes) <= ${MAX_SLAB_BYTES})",
        "CHECK (length(bytes) >= 0)",
    ),
    (
        "plain UNIQUE instead of the ifnull expression index",
        "ON entries(lib, item_key, ifnull(attachment_key, ''), ordinal)",
        "ON entries(lib, item_key, attachment_key, ordinal)",
    ),
    (
        "drop the entry kind CHECK",
        "CHECK (kind IN ('record', 'note', 'annotation', 'body', 'synthetic'))",
        "CHECK (kind IS NOT NULL)",
    ),
    (
        "drop the slab source CHECK",
        "CHECK (source IN ('attachment', 'record', 'note', 'annotation'))",
        "CHECK (source IS NOT NULL)",
    ),
    (
        "drop the char-range CHECKs",
        "CHECK (char_end >= char_start)",
        "CHECK (char_end >= -1)",
    ),
    (
        "set auto_vacuum after WAL (the measured trap)",
        "    db.exec('PRAGMA auto_vacuum = INCREMENTAL');\n    // WAL for the same reason",
        "    // WAL for the same reason",
    ),
    (
        "skip the snippet fingerprint comparison",
        "return fingerprint(slice) === row.fp ? slice : null;",
        "return slice;",
    ),
    (
        "accept a newer schema stamp",
        "if (stored === 'unstamped' || (typeof stored === 'number' && stored > LEDGER_SCHEMA_VERSION)) {",
        "if (false) {",
    ),
    (
        "one joined FTS column instead of eight",
        "const cols = FTS_FIELDS.join(', ');",
        "const cols = 'title';",
    ),
    (
        "bare delete in the external FTS layout",
        "    this.db\n      .prepare(\n        `INSERT INTO fts(fts, rowid, ${FTS_FIELDS.join(', ')}) "
        "VALUES ('delete', ?, ${placeholders(FTS_FIELDS.length)})`,\n      )\n"
        "      .run(pid, ...FTS_FIELDS.map((f) => row[f]));\n",
        "",
    ),
    (
        "re-probe the FTS layout instead of reading the recorded one",
        "  const recorded = readRecordedFtsStorage(db);\n  if (recorded) return recorded;",
        "",
    ),
    ("drop contentless_delete", "           contentless_delete = 1", "           contentless_delete = 0"),
]


def run_suite(fork: Path) -> dict[str, str]:
    """Test title -> status. Empty when the suite could not even load."""
    proc = subprocess.run(
        ["npx", "vitest", "run", TEST, "--reporter=json"],
        cwd=fork,
        capture_output=True,
        text=True,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("{"):
            report = json.loads(line)
            return {
                a["title"]: a["status"]
                for tr in report["testResults"]
                for a in tr["assertionResults"]
            }
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fork", type=Path, help="path to the fork checkout carrying the schema branch")
    args = ap.parse_args()

    ledger = args.fork / LEDGER_REL
    if not ledger.is_file():
        print(f"no {LEDGER_REL} under {args.fork}", file=sys.stderr)
        return 2

    pristine = ledger.read_text()
    survivors: list[str] = []
    missing: list[str] = []
    try:
        baseline = run_suite(args.fork)
        not_green = sorted(t for t, s in baseline.items() if s != "passed")
        print(f"baseline: {len(baseline)} tests, {len(not_green)} not passing {not_green}")
        if not baseline or not_green:
            # A control run against an already-red suite cannot attribute anything.
            print("REFUSING: the baseline must be green before a mutation means anything", file=sys.stderr)
            return 2
        print()

        for name, anchor, replacement in MUTATIONS:
            if anchor not in pristine:
                missing.append(name)
                print(f"MISSING  {name}: anchor no longer in the file")
                continue
            ledger.write_text(pristine.replace(anchor, replacement, 1))
            result = run_suite(args.fork)
            reds = sorted(t for t, s in result.items() if s != "passed")
            if not result:
                print(f"caught   {name}: the suite could not load (schema refused)")
            elif reds:
                print(f"caught   {name}: {len(reds)} red -> {reds[:3]}")
            else:
                survivors.append(name)
                print(f"SURVIVED {name}: nothing caught it")
            ledger.write_text(pristine)
    finally:
        ledger.write_text(pristine)

    print()
    print(
        f"{len(MUTATIONS)} mutations, {len(MUTATIONS) - len(survivors) - len(missing)} caught, "
        f"{len(survivors)} survived, {len(missing)} unapplied"
    )
    return 1 if survivors or missing else 0


if __name__ == "__main__":
    sys.exit(main())
