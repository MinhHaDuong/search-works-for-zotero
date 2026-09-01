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
(SQLite 3.51.3): baseline 32 tests green, 14 mutations applied, 14 caught, 0 survivors.

A first version of this file scored 12 of 12 and was wrong about two of them: it anchored
the char-range control on `CHECK (char_end >= char_start)`, which matches twice, so only
`slabs` was ever mutated while `entries` and `passages` reported "caught" without having
been touched. Hence the exactly-once rule and the per-mutation expected title below —
both of them guards against this file lying in the direction that feels like success.

Two later corrections, same family. The auto_vacuum mutation used to DELETE the pragma
rather than move it, so it controlled "the statement is present" while its name and the
finding it supports are about WHERE it sits. And a red was scored from `status !=
"passed"`, which counts a skipped test as a catch — a test that did not run has not
noticed anything.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

TEST = "tests/features/conductor-content-schema.test.ts"
LEDGER_REL = "src/features/search/conductor/ledger.ts"

#: (name, edits, expected-test-title), where `edits` is a list of (anchor, replacement)
#: applied together as one mutation.
#:
#: Three properties are enforced rather than documented, because each failure is silent.
#: Every anchor must occur EXACTLY once: zero means the mutation no longer applies, and
#: more than one means an arbitrary first site is patched while the others keep their
#: guard — a control that has quietly stopped covering what its name says. (Not
#: hypothetical: `CHECK (char_end >= char_start)` occurs twice, in `slabs` and in
#: `entries`, and a single ambiguous entry left `entries` and `passages` uncontrolled
#: while reporting "caught".) The expected title must be among the reds, so a mutation
#: that happens to break something unrelated is not scored as caught. And a mutation
#: whose subject is an ORDERING is expressed as a real reorder — a deletion would redden
#: the same test while controlling a weaker claim than the one being made.
MUTATIONS = [
    (
        "drop the 1 MiB slab CHECK",
        [("CHECK (length(bytes) <= ${MAX_SLAB_BYTES})", "CHECK (length(bytes) >= 0)")],
        "refuses a slab over the 1 MiB ceiling",
    ),
    (
        "plain UNIQUE instead of the ifnull expression index",
        [(
            "ON entries(lib, item_key, ifnull(attachment_key, ''), ordinal)",
            "ON entries(lib, item_key, attachment_key, ordinal)",
        )],
        "refuses two entries at the same ordinal in one source stream, attachment or not",
    ),
    (
        "drop the entry kind CHECK",
        [(
            "CHECK (kind IN ('record', 'note', 'annotation', 'body', 'synthetic'))",
            "CHECK (kind IS NOT NULL)",
        )],
        "refuses an entry kind outside the five §5.2.2 lists",
    ),
    (
        "drop the slab source CHECK",
        [(
            "CHECK (source IN ('attachment', 'record', 'note', 'annotation'))",
            "CHECK (source IS NOT NULL)",
        )],
        "refuses a slab source outside the four §5.2.2 lists",
    ),
    # Three separate sites, three separate controls. Anchored with enough surrounding
    # context to be unique, since the CHECK text alone is not.
    (
        "drop the char-range CHECK on slabs",
        [(
            "        content_hash TEXT NOT NULL,\n        CHECK (char_end >= char_start),",
            "        content_hash TEXT NOT NULL,\n        CHECK (char_end >= -1),",
        )],
        "refuses a backwards char range on an entry, a slab and a passage",
    ),
    (
        "drop the char-range CHECK on entries",
        [(
            "        page_est_kind  TEXT,\n        CHECK (char_end >= char_start)",
            "        page_est_kind  TEXT,\n        CHECK (char_end >= -1)",
        )],
        "refuses a backwards char range on an entry, a slab and a passage",
    ),
    (
        "drop the off-range CHECK on passages",
        [("CHECK (off_end >= off_start)", "CHECK (off_end >= -1)")],
        "refuses a backwards char range on an entry, a slab and a passage",
    ),
    # A real reorder: the statement is removed from before WAL and reinserted after it.
    # Every pragma is still executed; only the order changes, which is the whole claim.
    (
        "move auto_vacuum after WAL (the measured trap)",
        [
            (
                "    // Before WAL and before the first table. See the class docstring above.\n"
                "    db.exec('PRAGMA auto_vacuum = INCREMENTAL');\n",
                "",
            ),
            (
                "    db.exec('PRAGMA synchronous = NORMAL');",
                "    db.exec('PRAGMA synchronous = NORMAL');\n"
                "    db.exec('PRAGMA auto_vacuum = INCREMENTAL');",
            ),
        ],
        "leaves a real ledger file at auto_vacuum=INCREMENTAL",
    ),
    (
        "skip the snippet fingerprint comparison",
        [("return fingerprint(slice) === row.fp ? slice : null;", "return slice;")],
        "returns null rather than wrong words when the fingerprint does not match",
    ),
    (
        "accept a newer schema stamp",
        [(
            "if (stored === 'unstamped' || (typeof stored === 'number' && stored > LEDGER_SCHEMA_VERSION)) {",
            "if (false) {",
        )],
        "refuses a file stamped by a build this one cannot understand",
    ),
    (
        "one joined FTS column instead of eight",
        [("const cols = FTS_FIELDS.join(', ');", "const cols = 'title';")],
        "gives the FTS table one column per field, not v1s two joined ones",
    ),
    (
        "bare delete in the external FTS layout",
        [(
            "    this.db\n      .prepare(\n        `INSERT INTO fts(fts, rowid, ${FTS_FIELDS.join(', ')}) "
            "VALUES ('delete', ?, ${placeholders(FTS_FIELDS.length)})`,\n      )\n"
            "      .run(pid, ...FTS_FIELDS.map((f) => row[f]));\n",
            "",
        )],
        "indexes, scopes and retires a row through the shadow table",
    ),
    (
        "re-probe the FTS layout instead of reading the recorded one",
        [("  const recorded = readRecordedFtsStorage(db);\n  if (recorded) return recorded;", "")],
        "reopens a file in the layout its rows are in, not the one this runtime prefers",
    ),
    (
        "drop contentless_delete",
        [("           contentless_delete = 1", "           contentless_delete = 0")],
        "retires a row on delete, whichever storage mode was probed",
    ),
]


def run_suite(fork: Path) -> dict[str, str] | None:
    """Test title -> status, or None when the runner produced no report at all.

    None and an empty dict are deliberately different. A suite whose module fails to
    import reports zero assertions, which reads exactly like a runner that could not
    start — and scoring an infrastructure failure as a caught mutation is the same
    "all-clear indistinguishable from could-not-look" this probe exists to prevent.
    """
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
    return None


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
    unapplied: list[str] = []
    try:
        baseline = run_suite(args.fork)
        if baseline is None:
            print("REFUSING: the runner produced no report; fix the checkout first", file=sys.stderr)
            return 2
        not_green = sorted(t for t, s in baseline.items() if s != "passed")
        print(f"baseline: {len(baseline)} tests, {len(not_green)} not passing {not_green}")
        if not baseline or not_green:
            # A control run against an already-red suite cannot attribute anything.
            print("REFUSING: the baseline must be green before a mutation means anything", file=sys.stderr)
            return 2
        # Every expected title must exist, or the mutation is aimed at nothing.
        for name, _edits, expects in MUTATIONS:
            if expects not in baseline:
                print(f"REFUSING: {name} expects a test that does not exist: {expects!r}", file=sys.stderr)
                return 2
        print()

        for name, edits, expects in MUTATIONS:
            # Zero occurrences and many are the same failure: the control is not running
            # where it says it is. Neither may be scored as a pass. Checked for every edit
            # before any is applied, so a multi-edit mutation is all-or-nothing.
            counts = [pristine.count(anchor) for anchor, _ in edits]
            if any(n != 1 for n in counts):
                unapplied.append(name)
                print(f"UNAPPLIED {name}: anchor occurrences {counts} in {LEDGER_REL}, need exactly 1 each")
                continue
            mutated = pristine
            for anchor, replacement in edits:
                mutated = mutated.replace(anchor, replacement, 1)
            ledger.write_text(mutated)
            result = run_suite(args.fork)
            ledger.write_text(pristine)
            if result is None:
                unapplied.append(name)
                print(f"UNAPPLIED {name}: the runner produced no report — infrastructure, not a catch")
                continue
            # Only an actual failure counts. A test the mutation caused to be SKIPPED has
            # not noticed anything, and scoring it as red would credit the control for a
            # test that did not run.
            reds = sorted(t for t, s in result.items() if s == "failed")
            if expects in reds:
                print(f"caught    {name}: {len(reds)} red, incl. the aimed-at test")
            elif reds:
                # Red, but not where it was aimed. The aimed-at test did not notice.
                survivors.append(name)
                print(f"MISAIMED  {name}: {len(reds)} red but {expects!r} stayed green -> {reds[:3]}")
            else:
                survivors.append(name)
                print(f"SURVIVED  {name}: nothing caught it")
    finally:
        ledger.write_text(pristine)

    caught = len(MUTATIONS) - len(survivors) - len(unapplied)
    print()
    print(
        f"{len(MUTATIONS)} mutations, {caught} caught, "
        f"{len(survivors)} survived or misaimed, {len(unapplied)} unapplied"
    )
    return 1 if survivors or unapplied else 0


if __name__ == "__main__":
    sys.exit(main())
