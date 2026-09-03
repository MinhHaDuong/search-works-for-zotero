"""Every bench driver that opens a real index declares the schema generation it targets,
and is exercised against a fixture of each (ticket 0101).

Ticket 0100 repaired two drivers pinned to a schema upstream no longer writes, and landed
`bench/index_schema.mjs` to assert the shape before the first query. What it could not do
was cover the class: upstream owns the schema, this repo owns the drivers, nothing connects
them, and `make check` never opened a database at all. So the next rename lands the same
way the last one did — silently, surfacing an hour into a measurement session.

The suite is symmetric on purpose, and the symmetry is the point. For each driver:

  * against a fixture of the generation it targets, the gate must NOT fire;
  * against a fixture of the other generation, the driver must EXIT NON-ZERO and name what
    it found.

Only the second half would be a test of the error path. Only the first half would be a test
that passes on a driver whose gate is commented out. Together they are a test of the gate.

Three generations turned out to be two-and-a-half, and the finding is worth stating because
it changed what "repair" means here. `vec_real_measure.mjs`, `vec_mrl_recall.mjs` and
`issue30_build_index.mjs` do not target a stale *version* of the current schema: they target
the pre-rename generation, whose per-passage metadata lives in `passage_meta` and whose
vectors live in sqlite-vec `vec0` tables that upstream never shipped and does not have today.
Migrating them to the current schema would not repair a driver, it would replace a
measurement — and would silently invalidate the ticket-0008 artifacts they produced. So each
declares its generation instead, and the guard holds all of them to that declaration.

Cost tier: every case spawns `node`. The fixtures are written by a committed generator in
about a fifth of a second; nothing here touches the author's 939 MB index, a model, a GPU,
or the network.

    python3 -m pytest tests/test_index_schema_fixtures.py -q
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"
GENERATOR = BENCH / "fixtures" / "make_index_fixture.mjs"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed"),
]

#: The first line of each refusal, keyed by the generation the driver targets. Matching the
#: sentence rather than the exit code alone is what stops a driver that died of something
#: else — a missing file, a bad flag — from being read as a working gate.
REFUSAL = {
    "current": "not a current-schema zoteus index.",
    "prerename": "not a pre-rename zoteus index.",
}


def driver(name, generation, argv):
    return pytest.param({"name": name, "generation": generation, "argv": argv}, id=name)


#: Every driver that takes a path to a zoteus-built index on its command line and queries it
#: directly. Drivers that build their own synthetic corpus (`fts5_bench.mjs`,
#: `fold_sweep.mjs`, `constrained_match.mjs`, `slab_scan.mjs`, `vec_scan_shapes.mjs`,
#: `vec_scaling.mjs`, `vec_quantize.mjs`, `fts5_keyword_arm.mjs`, `cosine_fusion.mjs`,
#: `vec_recall.ts`) are deliberately absent: their `--db` names a scratch file they wrote
#: themselves, so there is no upstream schema for them to drift from. `derive_droplist.mjs`
#: and `bench/query.py` open the index through upstream's own code — a factory and a running
#: server — which owns that check; a second gate in front of it would assert upstream's
#: invariant on upstream's behalf.
#:
#: This roster is hand-maintained, which makes it asymmetric: it covers a driver being
#: REMOVED and covered nothing when one ARRIVED. `tests/test_index_driver_roster_closure.py`
#: (ticket 0598) closes that side — it derives the inventory of index-opening drivers from
#: the tree and refuses any that is neither listed here nor excused there with a written
#: reason. Three files had already arrived uncovered when it was written.
#:
#: `argv` is a callable so the fixture path and a scratch directory can be filled in.
DRIVERS = [
    driver(
        "index_concentration.mjs",
        "current",
        lambda db, tmp: ["--db", str(db), "--output", str(tmp / "concentration.json")],
    ),
    driver(
        "bm25_idf_effect.mjs",
        "current",
        lambda db, tmp: ["--db", str(db), "--output", str(tmp / "bm25.json")],
    ),
    driver(
        "year_scope.mjs",
        "current",
        lambda db, tmp: [
            "--db", str(db),
            "--years", str(_years_file(tmp)),
            "--output", str(tmp / "year-scope.json"),
            "--work", str(tmp / "year-scope-work.sqlite"),
        ],
    ),
    driver(
        "query_arms.mjs",
        "current",
        lambda db, tmp: [
            "--index", str(db),
            "--queries", str(BENCH / "queries.txt"),
            # No dist on this machine, and none needed: the gate has to fire before the arm
            # modules are imported, or a schema refusal arrives after minutes of loading.
            "--dists", str(tmp / "no-such-dist"),
        ],
    ),
    driver(
        "query_arms_multi.mjs",
        "current",
        lambda db, tmp: [
            "--pairs", f"stock={tmp / 'no-such-dist'}={db}",
            "--queries", str(BENCH / "queries.txt"),
        ],
    ),
    driver(
        "vec_real_measure.mjs",
        "prerename",
        lambda db, tmp: ["--db", str(db), "--output", str(tmp / "vec-real.json")],
    ),
    driver(
        "vec_mrl_recall.mjs",
        "prerename",
        lambda db, tmp: ["--db", str(db), "--output", str(tmp / "mrl.json")],
    ),
    driver(
        "issue30_build_index.mjs",
        "prerename",
        lambda db, tmp: [
            "--db", str(db),
            "--output", str(tmp / "issue30-built.sqlite"),
            "--dist", str(tmp / "no-such-dist"),
            "--slab", str(tmp / "no-such-slab.f32"),
        ],
    ),
]


def _years_file(tmp):
    """`year_scope.mjs` needs an item_key -> year map; the fixture's keys, invented years."""
    path = tmp / "years.json"
    if not path.exists():
        path.write_text(
            json.dumps({"ZZFIXT01": 1999, "ZZFIXT02": 2004, "ZZFIXT03": 2011, "ZZFIXT04": 2020})
        )
    return path


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory):
    """Both generations, written by the committed generator into a scratch directory."""
    out = tmp_path_factory.mktemp("index-fixtures")
    done = subprocess.run(
        ["node", str(GENERATOR), "--both", str(out)],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )
    assert done.returncode == 0, done.stderr
    paths = {k: Path(v) for k, v in json.loads(done.stdout).items()}
    for generation, path in paths.items():
        assert path.exists(), f"{generation} fixture was not written"
    return paths


def run_driver(spec, db, tmp):
    return subprocess.run(
        ["node", str(BENCH / spec["name"]), *spec["argv"](db, tmp)],
        capture_output=True, text=True, cwd=REPO, timeout=300,
    )


def other(generation):
    return "prerename" if generation == "current" else "current"


# --- the guard, in both directions -------------------------------------------------


@pytest.mark.parametrize("spec", DRIVERS)
def test_driver_refuses_an_index_of_the_other_generation(spec, fixtures, tmp_path):
    """The case that earns the suite its place: pointed at the wrong generation, the driver
    stops before it measures, and the message names the file, what it found, and a
    diagnosis. Anything less and a reader cannot tell "index a generation old" from "wrong
    file" from "not an index at all"."""
    wrong = fixtures[other(spec["generation"])]
    done = run_driver(spec, wrong, tmp_path)
    combined = done.stdout + done.stderr
    assert done.returncode != 0, f"accepted a {other(spec['generation'])} index:\n{combined}"
    assert REFUSAL[spec["generation"]] in combined, combined
    assert str(wrong) in combined, "the refusal must name the file it was pointed at"
    assert "found: tables:" in combined, "the refusal must report the schema it found"
    assert "diagnosis:" in combined, "the refusal must be actionable, not merely negative"


@pytest.mark.parametrize("spec", DRIVERS)
def test_driver_accepts_an_index_of_its_own_generation(spec, fixtures, tmp_path):
    """The half that keeps the guard from being satisfied by a driver that refuses
    everything. A driver may still fail here for want of a built dist or real vectors —
    what it may not do is refuse the substrate it targets."""
    right = fixtures[spec["generation"]]
    done = run_driver(spec, right, tmp_path)
    combined = done.stdout + done.stderr
    for sentence in REFUSAL.values():
        assert sentence not in combined, f"refused its own generation:\n{combined}"


# --- end to end, for the drivers a fixture can carry all the way --------------------
#
# Two of the eight run to completion on a fixture. The other six need something a fixture
# cannot hold — a built upstream dist (`query_arms*`, `issue30_build_index`), real
# embeddings and the sqlite-vec extension (`vec_real_measure`, `vec_mrl_recall`) — or a
# real date harvest (`year_scope`). For those, the two cases above are the assertion: the
# gate is driven in both directions through the real command line, which is where a schema
# break actually arrives.


def test_index_concentration_produces_its_artifact_on_the_current_fixture(fixtures, tmp_path):
    out = tmp_path / "concentration.json"
    done = subprocess.run(
        ["node", str(BENCH / "index_concentration.mjs"),
         "--db", str(fixtures["current"]), "--output", str(out)],
        capture_output=True, text=True, cwd=REPO, timeout=300,
    )
    assert done.returncode == 0, done.stderr
    art = json.loads(out.read_text())
    assert art["passages_total"] == 600
    # The dominant item is the one the fixture built to dominate — a driver reading the
    # wrong column would still find *an* item, so the assertion names which.
    assert art["dominant_item"]["item"] == "ZZFIXT01"
    assert art["passages_after_removing_dominant"] == 600 - art["dominant_item"]["passages"]
    # The schema it measured against, recorded beside the number: what a figure was
    # measured on belongs in the artifact, which is half of why 0100 landed the module.
    assert "passages_fts" in json.dumps(art["db_schema"])


def test_bm25_idf_effect_produces_its_artifact_on_the_current_fixture(fixtures, tmp_path):
    out = tmp_path / "bm25.json"
    done = subprocess.run(
        ["node", str(BENCH / "bm25_idf_effect.mjs"),
         "--db", str(fixtures["current"]), "--output", str(out)],
        capture_output=True, text=True, cwd=REPO, timeout=300,
    )
    assert done.returncode == 0, done.stderr
    art = json.loads(out.read_text())
    assert art["passages_total"] == 600
    assert art["excluded_item"] == "ZZFIXT01"
    assert art["passages_without_excluded"] == 600 - art["dominant_item"]["passages"]


# --- the declaration in UPSTREAM has teeth ------------------------------------------


def upstream_declarations():
    text = (REPO / "UPSTREAM").read_text()
    return dict(
        line.split("=", 1)
        for line in text.splitlines()
        if line and not line.startswith("#") and "=" in line
    )


def test_upstream_declares_the_index_schema_generation():
    declared = upstream_declarations()
    assert "UPSTREAM_INDEX_SCHEMA_VERSION" in declared, (
        "UPSTREAM must name the index schema generation the drivers target, so a future "
        "upstream bump has somewhere to land"
    )
    assert declared["UPSTREAM_INDEX_SCHEMA_VERSION"].isdigit()


def test_the_declared_generation_is_what_the_current_fixture_stamps(fixtures):
    """The declaration's teeth.

    `SCHEMA_VERSION` has been 1 since v1.7.0 and is still 1 at v1.12.0, so writing it into
    `UPSTREAM` would be decoration if nothing read it back. This reads it back: the fixture
    generator stamps `meta.schemaVersion` from the mirror in `bench/index_schema.mjs`, and
    the day that mirror and the declaration disagree, this fails.
    """
    import sqlite3

    declared = int(upstream_declarations()["UPSTREAM_INDEX_SCHEMA_VERSION"])
    conn = sqlite3.connect(f"file:{fixtures['current']}?mode=ro", uri=True)
    try:
        stamped = conn.execute("SELECT value FROM meta WHERE key = 'schemaVersion'").fetchone()
    finally:
        conn.close()
    assert stamped is not None, "the current fixture must stamp meta.schemaVersion"
    assert int(stamped[0]) == declared


def test_the_mirror_matches_upstreams_own_constant_when_a_fork_is_checked_out():
    """The third leg, present only when a fork checkout is.

    `fork/` is gitignored and absent on a fresh clone, so this is the one comparison that
    cannot be a standing assertion. Where it can run it is the strongest of the three: it
    reads upstream's own `const SCHEMA_VERSION` rather than anything this repo wrote down.
    """
    source = REPO / "fork" / "src" / "features" / "search" / "sqlite-index.ts"
    if not source.exists():
        pytest.skip("no fork checkout — run `make upstream-checkout` to enable this leg")
    found = re.search(r"^const SCHEMA_VERSION\s*=\s*(\d+)\s*;", source.read_text(), re.M)
    assert found, "upstream no longer declares `const SCHEMA_VERSION` — the mirror is stale"
    assert int(found.group(1)) == int(upstream_declarations()["UPSTREAM_INDEX_SCHEMA_VERSION"])
