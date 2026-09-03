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
import warnings
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


SCHEMA_TS = "src/features/search/sqlite-index.ts"

#: Upstream's own declaration, as a pattern. A miss here is a finding, not a not-run: it
#: means the constant was renamed or moved and the mirror in `bench/index_schema.mjs` is
#: stale in a way no version comparison would notice.
SCHEMA_CONST = re.compile(r"^const SCHEMA_VERSION\s*=\s*(\d+)\s*;", re.M)


class SchemaLegNotRun(UserWarning):
    """Emitted when leg 3 could not reach upstream's constant at all.

    A skip and a pass are the same colour in a suite summary — that is the whole of ticket
    0620 — so the not-run outcome is also raised as a warning, which pytest prints in its
    warnings summary on every run, with or without `-rs`. Not-run is loud and it is not
    green; it is still not red, because a fresh clone has neither mirror nor checkout and a
    gate that a fresh clone cannot satisfy gets waived, which is a green meaning "we decided
    not to look" (the reasoning the Makefile records for `fold-gate`).
    """


def candidate_roots():
    """`REPO`, plus the main checkout when this one is a linked worktree.

    `upstream.git/` and `fork/` are git-ignored, so a `git worktree add` tree never carries
    either — the leg would go not-run in every worktree while the mirror sat one directory
    away. `.git` is a *file* in a linked worktree, naming `<main>/.git/worktrees/<name>`.
    """
    roots = [REPO]
    dotgit = REPO / ".git"
    if dotgit.is_file():
        pointer = dotgit.read_text().strip()
        if pointer.startswith("gitdir:"):
            gitdir = Path(pointer.split(":", 1)[1].strip())
            main = gitdir.parent.parent.parent  # <main>/.git/worktrees/<name> -> <main>
            if main.is_dir() and main not in roots:
                roots.append(main)
    return roots


def read_upstream_schema_version(roots, sha):
    """upstream's `SCHEMA_VERSION`, from the first source that can answer.

    Returns `(version, provenance, reasons)`. `version` is None when nothing could be read,
    and `reasons` then says of each candidate why not — a not-run must name what it could
    not look at, or it is indistinguishable from a check that never existed.

    Every source is a git repository and every read is `git show <reviewed sha>:<path>`,
    never the file lying in a working tree. That is the correction ticket 0620 asked for and
    it is worth stating why, because the weaker version of this fix was written first and
    went red on a correct declaration: the author's `fork/` was checked out at v1.12.0 while
    `UPSTREAM` correctly declared v1.13.0's generation, so reading the working file compared
    the declaration against the wrong commit. A checkout answers for whatever it happens to
    be at; only the pinned SHA answers the question this repository pins.

    The bare mirror comes first because `make upstream-catchup` maintains it with nothing
    built, so it is the source a fresh machine can have. A `fork/` clone is tried after it,
    as a repository rather than a directory of files — it fetches upstream too, so it often
    holds the reviewed object whether or not it is checked out there.
    """
    reasons = []
    for root in roots:
        for name, fix in (("upstream.git", "upstream-catchup"), ("fork", "upstream-checkout")):
            repo = root / name
            if not (repo / "HEAD").exists() and not (repo / ".git").exists():
                reasons.append(f"no repository at {repo} (run `make {fix}`)")
                continue
            done = subprocess.run(
                ["git", "-C", str(repo), "show", f"{sha}:{SCHEMA_TS}"],
                capture_output=True, text=True, timeout=60,
            )
            if done.returncode != 0:
                reasons.append(
                    f"{repo} does not hold {sha[:12]}:{SCHEMA_TS} — run `make {fix}`"
                )
                continue
            return _parse(done.stdout), f"{repo} at {sha[:12]}", reasons
    return None, None, reasons


def _parse(text):
    found = SCHEMA_CONST.search(text)
    assert found, (
        f"upstream no longer declares `const SCHEMA_VERSION` in {SCHEMA_TS} — the mirror in "
        "bench/index_schema.mjs is stale in a way no version comparison can see"
    )
    return int(found.group(1))


def check_declaration_against_upstream(roots, declared):
    """Leg 3's whole body, taken out of the test so a control can drive it.

    A leg that can only ever be observed passing is what ticket 0620 is about; this is what
    lets `test_leg_three_goes_red_...` below run the real comparison against a tree built to
    disagree. Raises `AssertionError` on a mismatch, returns the not-run message when nothing
    could be read, and returns None when the declaration is right.
    """
    version, provenance, reasons = read_upstream_schema_version(
        roots, declared["UPSTREAM_REVIEWED_SHA"].strip()
    )
    if version is None:
        return "NOT-RUN: leg 3 could not read upstream's SCHEMA_VERSION — " + "; ".join(reasons)
    assert version == int(declared["UPSTREAM_INDEX_SCHEMA_VERSION"]), (
        f"UPSTREAM_INDEX_SCHEMA_VERSION={declared['UPSTREAM_INDEX_SCHEMA_VERSION']} but "
        f"upstream declares SCHEMA_VERSION = {version} ({provenance}) — re-baseline"
    )
    return None


def test_the_declaration_matches_upstreams_own_constant():
    """The third leg, and the only one that reads anything upstream wrote.

    Legs 1 and 2 are satisfied by a tree that agrees with itself: the fixture is stamped
    *from* the mirror, so they hold whether or not either is right. This one compares the
    declaration against upstream's own constant at the reviewed SHA. On 2026-09-03 upstream
    moved `SCHEMA_VERSION` 1 -> 2 for the first time since v1.7.0 and this leg said nothing,
    because it read a git-ignored `fork/` checkout that was not there. It reads the bare
    mirror now, which `make upstream-catchup` maintains and which needs nothing built.
    """
    not_run = check_declaration_against_upstream(candidate_roots(), upstream_declarations())
    if not_run:
        warnings.warn(not_run, SchemaLegNotRun, stacklevel=2)
        pytest.skip(not_run)


# --- and the third leg's own controls -----------------------------------------------
#
# The leg above is a check; these two are what earn it. Ticket 0620 was filed because the
# leg looked green on a tree it disagreed with, so a version of it that can only be seen
# passing is worth nothing. Both cases run the real reader against a synthetic tree.


def _mirror_of(tmp_path, ts_body):
    """A bare mirror holding one commit that carries `sqlite-index.ts` — no fork/ anywhere."""
    work = tmp_path / "work"
    (work / Path(SCHEMA_TS).parent).mkdir(parents=True)
    (work / SCHEMA_TS).write_text(ts_body)
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
    }
    def git(*argv, cwd):
        done = subprocess.run(["git", *argv], cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done.stderr
        return done.stdout
    git("init", "--quiet", "-b", "main", cwd=work)
    git("add", "-A", cwd=work)
    git("commit", "--quiet", "-m", "upstream", cwd=work)
    sha = git("rev-parse", "HEAD", cwd=work).strip()
    root = tmp_path / "root"
    root.mkdir()
    git("clone", "--bare", "--quiet", str(work), str(root / "upstream.git"), cwd=tmp_path)
    return root, sha


def test_leg_three_goes_red_against_a_wrong_declaration_with_only_a_mirror(tmp_path):
    """The red the repaired leg owes, in exactly the shape the tree was in on 2026-09-03: a
    declaration naming a generation upstream does not declare, no `fork/` anywhere, and only
    the bare mirror to look at. The old leg skipped here, and the skip was the defect."""
    root, sha = _mirror_of(tmp_path, "const SCHEMA_VERSION = 2;\n")
    assert not (root / "fork").exists(), "the point of the case is that there is no checkout"
    wrong = {"UPSTREAM_REVIEWED_SHA": sha, "UPSTREAM_INDEX_SCHEMA_VERSION": "99"}
    with pytest.raises(AssertionError, match="upstream declares SCHEMA_VERSION = 2"):
        check_declaration_against_upstream([root], wrong)


def test_leg_three_is_green_on_the_same_mirror_when_the_declaration_is_right(tmp_path):
    """The other side of the control: the red above must come from the disagreement and not
    from the synthetic tree being unreadable. Same mirror, same absent checkout, correct
    declaration — and the leg passes rather than reporting not-run."""
    root, sha = _mirror_of(tmp_path, "const SCHEMA_VERSION = 2;\n")
    right = {"UPSTREAM_REVIEWED_SHA": sha, "UPSTREAM_INDEX_SCHEMA_VERSION": "2"}
    assert check_declaration_against_upstream([root], right) is None, "must not report not-run"


def test_leg_three_reports_not_run_when_neither_mirror_nor_checkout_is_present(tmp_path):
    """The other half: with nothing to read, the reader returns no version and says of each
    candidate why — never a version, and never silence."""
    empty = tmp_path / "bare-clone"
    empty.mkdir()
    version, provenance, reasons = read_upstream_schema_version([empty], "0" * 40)
    assert version is None and provenance is None
    assert any("upstream-catchup" in r for r in reasons)
    assert any("upstream-checkout" in r for r in reasons)
