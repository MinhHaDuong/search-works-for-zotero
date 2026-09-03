"""The `bench/` roster of index-opening drivers is closed: an arriving driver cannot stay ungated.

Ticket 0101 landed `tests/test_index_schema_fixtures.py`, which drives every bench driver
that opens a zoteus-built index against a fixture of each schema generation. Its roster,
`DRIVERS`, is hand-maintained, and that makes the guard asymmetric in the one direction
nobody notices: it covers a driver being REMOVED from coverage — delete a rostered file and
the fixture cases die loudly — and it covers nothing at all when a driver arrives. A new
bench driver that opens an index joins the repo uncovered, silent, and is discovered the way
0100's defect was: an hour into a measurement session, on `no such table`.

The hole was not hypothetical. When this module was written, three files already on `main`
opened a zoteus-built index and were in neither `DRIVERS` nor 0101's list of deliberately
absent drivers: `bench/smoke_upstream.py`, `bench/issue30_arms.py` and
`bench/issue30_codebuild_agreement.py`. All three are classified in `EXCUSED` below, with
reasons; what matters here is that nothing named them until a scan derived the inventory
from the tree.

A FOURTH FILE ARRIVED WHILE THIS PR WAS OPEN, AND THE GUARD CAUGHT IT UNPROMPTED
--------------------------------------------------------------------------------
This is the strongest evidence in the module, and it was not staged. `97d1490` ("Ticket
0579: goal 2's gates, asserted over the same seven verbs") landed on `main` after this
branch was cut and took `bench/acceptance/adapters/zoteus.py` across the class boundary:
+143/-2 lines, `sqlite3` 0 -> 4, `FROM meta` 0 -> 2. `d81584c` ("Arm R23's two
directions…") then added a further +43/-2, taking `sqlite3` to 5 and leaving `FROM meta`
unchanged at 2. Over the whole range `5d2514d..8a5ad06` the file gained 184 lines, 0 -> 5
and 0 -> 2. Neither commit is an ancestor of the branch base `5d2514d`, so the driver did
arrive from another lane while this merge request was open. (An earlier round of this
module attributed the whole crossing to `d81584c` alone: that was wrong, and the per-commit
numbers above are `grep -c` counts on the file at each ref, plus `git show --stat`.) The
branch was green on its own base and red the moment current `main` was merged in, naming
exactly that file:

    AssertionError: bench files that open a zoteus-built index and are in neither
    DRIVERS (tests/test_index_schema_fixtures.py) nor EXCUSED:
    {'bench/acceptance/adapters/zoteus.py': ['meta']}

A real index-opening driver joined the repo, and the closure check named it on the first
run against real traffic rather than against a fixture. Every synthetic control below is an
argument that this would happen; this is the event. It is classified in `EXCUSED` on its
own substrate merits, argued there.

WHAT THE CLASS IS, AND WHY THE OBVIOUS PROBE MISSES A THIRD OF IT
-----------------------------------------------------------------
An earlier probe looked for drivers that take an index path on the command line — `--db`,
`--index` — and it found two of the three. `issue30_codebuild_agreement.py` takes no index
argument at all: it derives `search-index.sqlite` from a data directory. An argv-shaped
probe cannot see that file no matter how carefully it is written, because the property it
tests is not the property that matters. So the class this module scans for is **opens a
SQLite database and names a zoteus index table in SQL**, which is what "pinned to a schema
upstream may rename" actually means.

A SECOND FINDING, RETRACTED — AND THE RETRACTION IS THE POINT
-------------------------------------------------------------
An earlier draft of this module argued structurally: every uncovered file is Python,
`bench/index_schema.mjs` is a JavaScript module, `DRIVERS` is entirely `.mjs`, so a Python
driver is outside the gate and rostering one would mean a second Python mirror of the
schema constants — this repo's most expensive recurring defect (AGENTS.md, "One statement
per fact"). **That argument is withdrawn. It does not hold, and it is not offered here.**

The premise was measured and is false. All four Python drivers in the inventory already
spawn `node` themselves — `Server(["node", …])` in `smoke_upstream.py`, `issue30_arms.py`,
`issue30_codebuild_agreement.py` and `acceptance/adapters/zoteus.py`. Node is a hard
runtime dependency of each, so reaching the gate needs a `subprocess.run(["node",
"bench/index_schema_check.mjs", …])` shim, not a mirror of a single constant. The real
obstacle is narrower and mechanical: `test_index_schema_fixtures.py::run_driver` hardcodes
`["node", BENCH / spec["name"], …]`, so rostering a `.py` driver needs a suffix dispatch
there. A few lines, not a duplicated fact.

It is withdrawn now rather than quietly dropped because of where it would have led. The
fourth file above is also Python. Had the structural argument been load-bearing, every
Python driver that ever arrives would be excusable by the same sentence, and `EXCUSED`
would be empty of judgement — the class closed by construction rather than by measurement,
which is the failure this module was written against. None of the four excuses rests on it:
each is a substrate argument about what its file reads and who decides the same question
afterwards, and each stands or falls alone. A Python port of the gate remains a separate
decision, on its own merits, not something to smuggle in behind a roster entry.

HOW THE SCAN ERRS
-----------------
Broad, deliberately. A false positive costs one line of written reason in `EXCUSED`; a
false negative costs the whole guard, silently, which is the failure this module exists
against. So:

  * the "opens a database" test is a bare `sqlite` token anywhere in the file, not a parse
    of `.connect(` call sites — `bench/issue30_arms.py` reaches sqlite through
    `__import__("sqlite3").connect(...)`, and the next driver will find another spelling.
    Today that test excludes exactly one file (`bench/upstream_catchup.py`, which reads
    upstream's DDL as text). It is nearly vacuous, and it is kept because the vocabulary
    below is what carries the discrimination — see the negative control.
  * table names are matched only inside string literals, in SQL keyword position
    (`FROM`/`JOIN`/`INTO`/`UPDATE`/`TABLE`). Restricting to literals is what keeps prose
    like "read from passages" in a comment out of the inventory; it does not keep it out of
    a Python docstring, which is a literal. That too costs one line of reason.

WHERE THE SCAN LOOKS, AND WHAT THAT LEAVES OUT
----------------------------------------------
The search root is `bench/` and only `bench/` — `SEARCH_ROOT` below, asserted rather than
left as an implementation detail, because a module named for closure invites a reader to
take the closure as repo-wide.

It is not. `verification/probes/` holds sixteen files in exactly this class: they open a
real index and run raw SQL against `meta`, `passages` and `passages_fts`. Measured, not
guessed — the same predicates over that root name `corpus-language-mix.mjs`,
`degenerate-real-index.mjs`, `diacritic-collision-cost.mjs`,
`droplist-adapts-to-corpus.mjs`, `expansion-penalties-probe.mjs`,
`expansion-reach-probe.mjs`, `folding-cost-and-benefit.mjs`,
`keeping-diacritics-cost.mjs`, `keeping-diacritics-real-cost.mjs`, `lang_census.py`,
`migrate-real-index.mjs`, `scan-shape-v190-vs-fused.mjs`, `snippet-droplist-probe.mjs`,
`stoplist-cross-language.mjs`, `vocab-scan-cost.mjs` and `x4_probe_vocabulary.py`. The
count is a finding rather than a nil because the identical run over `bench/` returns the
known-positive inventory below, the four newly-classified files included.

They are out of scope deliberately, not overlooked. Several are one-off instruments pinned
to the pre-rename generation the way `vec_real_measure.mjs` is, so classifying them is the
same judgement 0101 made per driver, sixteen times over — an exercise of its own, and
sixteen reasons written in a hurry to keep a suite green would be sixteen bare names with a
longer type, which is the defect `EXCUSED` exists against. Ticket 0598's body records the
population and the deferral.

So `SEARCH_ROOT` is a constant with a test on it, and a control asserts that a file of this
exact class placed outside the root is NOT named. Widening the scan is then a deliberate
edit that reds a named test, rather than a silent change of what the module claims. That is
the same defect class this module closes: a scope claim true when written and retroactively
wrong once something moves.

Cost tier: FAST — pure Python over source text, no `node`, no subprocess, no database. It
deliberately does NOT live in `tests/test_index_schema_fixtures.py`, whose module-level
`pytestmark` carries `integration` plus a skipif on `node`. A closure check that skips on a
machine without node is a green that means "could not look", and this check is exactly the
one that must never say that.

    python3 -m pytest tests/test_index_driver_roster_closure.py -q
"""

import ast
import re
from pathlib import Path
from typing import NamedTuple

import pytest

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"
ROSTER_SUITE = REPO / "tests" / "test_index_schema_fixtures.py"

#: The one directory the scan walks, repository-relative. Named here rather than inlined,
#: and asserted by `test_the_search_root_is_the_one_the_module_documents`, because the
#: module's title says "closed" and a reader is entitled to know closed over WHAT. See
#: "WHERE THE SCAN LOOKS" above for the sixteen files this leaves out and why.
SEARCH_ROOT = "bench"

#: The root this scan deliberately does not walk, named so the exclusion is greppable and
#: so widening the scan means editing a constant a test reads.
UNSEARCHED_ROOT = "verification/probes"

#: Source files a bench driver can be written in.
SOURCE_SUFFIXES = {".py", ".mjs", ".js", ".cjs", ".ts"}

#: Any mention of sqlite, in any binding's spelling: `sqlite3`, `node:sqlite`,
#: `better-sqlite3`, `aiosqlite`. See "HOW THE SCAN ERRS" above for why this is a token
#: search rather than a call-site parse.
OPENS_SQLITE = re.compile(r"sqlite", re.I)

#: String literals in Python and in JavaScript/TypeScript, triple-quoted and template forms
#: included. SQL lives in literals; prose lives outside them.
LITERAL = re.compile(
    r"'''(?:[^\\]|\\.)*?'''"
    r'|"""(?:[^\\]|\\.)*?"""'
    r"|`(?:[^`\\]|\\.)*`"
    r"|'(?:[^'\\\n]|\\.)*'"
    r'|"(?:[^"\\\n]|\\.)*"',
    re.S,
)

#: A table name in SQL keyword position. The optional backtick/quote/bracket is not
#: decoration: `index_schema.mjs` names its tables as ``table `passages` `` inside the
#: refusal it raises, and a scan that missed that would be reading the gate as unrelated
#: to the schema it gates.
SQL_TABLE_REFERENCE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE(?:\s+IF\s+NOT\s+EXISTS)?)\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)",
    re.I,
)

CREATE_TABLE = re.compile(
    r"CREATE\s+(?:VIRTUAL\s+)?TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)",
    re.I,
)

#: The names the vocabulary must contain for the scan to mean anything. A restructure of
#: either source file that emptied the derivation would leave the closure test passing
#: vacuously — an all-clear indistinguishable from "I could not look" — so the derivation
#: is checked against these rather than trusted.
VOCABULARY_FLOOR = {"passages", "passages_fts", "passage_meta", "index_meta", "items", "meta"}


def index_vocabulary(bench: Path) -> set[str]:
    """Every zoteus index table name, derived from the two files that own them.

    `bench/fixtures/make_index_fixture.mjs` writes both generations and so states every
    table by `CREATE TABLE`; `bench/index_schema.mjs` exports the names the gate keys on.
    Neither is transcribed here: a vocabulary written down a third time would drift from
    both, which is the defect the whole family of guards exists against.
    """
    vocabulary: set[str] = set()
    for name in ("fixtures/make_index_fixture.mjs", "index_schema.mjs"):
        text = (bench / name).read_text(encoding="utf-8")
        vocabulary |= {m.lower() for m in CREATE_TABLE.findall(text)}
    schema = (bench / "index_schema.mjs").read_text(encoding="utf-8")
    for declaration in re.findall(
        r"^export const (?:FTS_TABLE|PRERENAME_TABLES)\s*=\s*(.*?);", schema, re.M | re.S
    ):
        vocabulary |= {s.lower() for s in re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", declaration)}
    return vocabulary


def index_tables_named(text: str, vocabulary: set[str]) -> set[str]:
    """Zoteus index tables this source names in SQL keyword position, inside a literal."""
    named: set[str] = set()
    for literal in LITERAL.findall(text):
        for table in SQL_TABLE_REFERENCE.findall(literal):
            if table.lower() in vocabulary:
                named.add(table.lower())
    return named


def drivers_that_open_an_index(repo: Path, vocabulary: set[str]) -> dict[str, list[str]]:
    """The inventory, derived from the tree: path -> the index tables it names.

    Walks `SEARCH_ROOT` alone. That bound is the module's scope claim, and it is asserted
    by two tests below rather than left for a reader to infer from this line.
    """
    found: dict[str, list[str]] = {}
    for path in sorted((repo / SEARCH_ROOT).rglob("*")):
        if path.suffix not in SOURCE_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not OPENS_SQLITE.search(text):
            continue
        named = index_tables_named(text, vocabulary)
        if named:
            found[path.relative_to(repo).as_posix()] = sorted(named)
    return found


def rostered(suite: Path) -> set[str]:
    """Driver filenames in `DRIVERS`, read off the source rather than imported.

    Read rather than imported for two reasons. The roster module is `integration` and
    skipped where `node` is absent, and importing a suite to interrogate it makes this
    check depend on that suite's import-time behaviour; parsing it depends only on its
    text. The failure direction is safe either way — a restructure this parser cannot read
    yields FEWER rostered names, so every rostered driver turns up unexcused and the
    closure test fails loudly rather than quietly widening.
    """
    tree = ast.parse(suite.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.List)):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "DRIVERS" for t in node.targets):
            continue
        for element in node.value.elts:
            if (
                isinstance(element, ast.Call)
                and isinstance(element.func, ast.Name)
                and element.func.id == "driver"
                and element.args
                and isinstance(element.args[0], ast.Constant)
            ):
                names.add(f"bench/{element.args[0].value}")
    return names


#: One situation, one sentence — five drivers share it exactly, and five paraphrases of one
#: reason is how a reviewable list stops being reviewable.
OWN_CORPUS = (
    "builds its own synthetic corpus: it CREATEs the tables it then queries, in a scratch "
    "file it wrote itself, so there is no upstream schema for it to drift from (0101's "
    "ruling, carried forward)"
)

UPSTREAM_OWNS_IT = (
    "opens the index through upstream's own code, which owns that check; a second gate here "
    "would assert upstream's invariant on upstream's behalf (0101's ruling)"
)

class Excuse(NamedTuple):
    """One excused file: the index tables its reason was written against, and the reason.

    `tables` is the load-bearing half at rest, and it is what stops an excuse outliving
    the file it describes. `test_no_excused_entry_is_stale` fires only when a file LEAVES
    the class; nothing fired when an excused file changed WHAT IT TOUCHES. If
    `smoke_upstream.py` gained a `SELECT … FROM passages_fts` tomorrow, its written reason
    — which turns on `meta` being a generation discriminator — would become false and every
    test would stay green. The reason would be human-checked once, at review, and never
    again. Pinning the set the scan found when the reason was written turns that into a
    red: `test_no_excused_entry_drifts_from_its_pinned_tables` reds by name, and the reason
    gets re-read by whoever changed the file.

    This is the idiom `VOCABULARY_FLOOR` already applies to the derivation, turned on
    `EXCUSED`. The fourth file's arrival is the argument for it: the guard caught a file
    ENTERING the class and would not have caught the identical change inside `EXCUSED`.

    Tables come first because the reasons run to a paragraph, and a pin appended after ten
    lines of prose is a pin nobody re-reads in a diff. The short machine-checked half sits
    where the eye lands.
    """

    tables: frozenset[str]
    why: str


#: Files the scan names that are deliberately not rostered, each with the reason that makes
#: the exclusion reviewable and the table set that reason was written against. A bare name
#: would be the same undifferentiated cell the roster already is — "this driver hides a gate
#: it should have" and "this file has no generation to be pinned to" are opposite findings,
#: and a set of names cannot tell them apart. A blank reason is refused (`unreasoned`); a
#: reason whose file has since moved to other tables is refused too (`drifted`).
EXCUSED: dict[str, Excuse] = {
    # --- the guard's own substrate ---------------------------------------------------
    "bench/index_schema.mjs": Excuse(
        frozenset({"passages"}),
        "the gate itself. The table names it appears to query are the ones it prints in its "
        "refusals, and the vocabulary this scan matches against is derived from its own "
        "exported constants — it is what the roster is held to, not a member of it"
    ),
    "bench/fixtures/make_index_fixture.mjs": Excuse(
        frozenset({"index_meta", "items", "meta", "passage_meta", "passages", "passages_fts", "vector_codes"}),
        "the fixture generator. It WRITES both generations rather than reading one, and it "
        "is the other file the vocabulary is derived from; a generation gate on the thing "
        "that manufactures both generations would refuse its own output"
    ),
    "bench/upstream_catchup.py": Excuse(
        frozenset({"passages"}),
        "never opens a database: it greps upstream's `sqlite-index.ts` for the `passages` "
        "DDL and for `SCHEMA_VERSION`, and reports a move. It is the detector that tells "
        "this roster it needs updating, not a driver that could be pinned to a stale "
        "generation. It appears here only because the sqlite test is a token search"
    ),
    # --- their own scratch corpus ------------------------------------------------------
    "bench/constrained_match.mjs": Excuse(frozenset({"passages", "passages_fts"}), OWN_CORPUS),
    "bench/cosine_fusion.mjs": Excuse(frozenset({"passages"}), OWN_CORPUS),
    "bench/fts5_bench.mjs": Excuse(frozenset({"passages"}), OWN_CORPUS),
    "bench/fts5_keyword_arm.mjs": Excuse(frozenset({"passages"}), OWN_CORPUS),
    "bench/vec_scan_shapes.mjs": Excuse(frozenset({"passages"}), OWN_CORPUS),
    "bench/vec_recall.ts": Excuse(
        frozenset({"passage_meta"}),
        "builds its own corpus through upstream's own `Fts5PassageStore` into a scratch "
        "$TMPDIR database and then re-opens that file raw, to run the exact float32 ranking "
        "the store no longer takes. The schema is whatever that store wrote in the same "
        "process; there is no foreign index to drift from"
    ),
    # --- upstream's own code owns the check, in the same run ----------------------------
    "bench/derive_droplist.mjs": Excuse(frozenset({"meta"}), UPSTREAM_OWNS_IT),
    "bench/smoke_upstream.py": Excuse(
        frozenset({"meta"}),
        "an acceptance smoke driver, and the only file in this inventory that READS "
        "`meta.schemaVersion` and reports the value it found. `_restamp_and_open` copies "
        "the index, records the original version into the artifact, then deliberately "
        "restamps the copy to a version upstream does not write and checks that upstream "
        "sidelines the file. That read is the declaration a roster entry would impose, made "
        "on the substrate instead of written down beside it, and it happens before any "
        "server starts — so a rename fails in seconds, naming the version it found, which "
        "is the cost the roster exists to avoid. The copy then goes to upstream's own "
        "server, so upstream decides the same question a second time"
    ),
    "bench/issue30_arms.py": Excuse(
        frozenset({"items", "meta", "passages"}),
        "`geometry(MASTER)` describes the substrate the run hands to upstream's own "
        "binaries: every arm gets a `shutil.copy2` of that same file and a v1.9.0 or "
        "v1.10.0 server started on it, so an index of a generation upstream cannot read is "
        "refused by upstream, in the same run, seconds later. The read is a description of "
        "an accepted substrate rather than an independent gate — `derive_droplist.mjs`'s "
        "case seen from the server side — and it runs before the servers start, so a rename "
        "costs seconds rather than the hour the roster exists to protect"
    ),
    "bench/acceptance/adapters/zoteus.py": Excuse(
        frozenset({"meta"}),
        "the fourth file — it crossed into the class on `main` in `97d1490` (0 -> 4 "
        "`sqlite3`, 0 -> 2 `FROM meta`, +143/-2) while this PR was open, and was extended "
        "by a further +43/-2 in `d81584c`; this module's closure check named it, "
        "unprompted, on the first run against real traffic. Excused on the same substrate reason as `bench/smoke_upstream.py`, and "
        "NOT on being Python: it is `_restamp_and_open` moved into an acceptance adapter, "
        "as its own file header says. Its whole SQL surface is three statements on "
        "`meta.schemaVersion` — `_index` opens each `*.sqlite` candidate and asks whether "
        "it carries the stamp (found by the stamp rather than by filename, because the "
        "name has changed across versions of this target), `_stamp` reports the value "
        "found, and `_restamp` writes `0` or `9999`, a version upstream MUST refuse, which "
        "is the R23 clause the adapter exists to drive. `meta` is a generation "
        "discriminator: the pre-rename generation calls it `index_meta` "
        "(`PRERENAME_TABLES`), so this file structurally cannot commit the "
        "right-name/wrong-content defect `index_schema.mjs` was written for. Rostering it "
        "would refuse the adapter's own instrument, exactly as it would for "
        "`smoke_upstream.py`. One difference from that file, recorded because it is real "
        "and cuts against this excuse: `_index` catches `sqlite3.Error` and moves to the "
        "next candidate, so a rename does not fail there — it reports no index, and "
        "`_restamp` / `_reset_to_seeded_index` then raise by name one step later. Loud, "
        "but not immediately, and no number read from a misread generation reaches an "
        "artifact, since every value it reports IS the schema stamp"
    ),
    "bench/issue30_codebuild_agreement.py": Excuse(
        frozenset({"vector_codes"}),
        "it counts `vector_codes` in a file upstream's own v1.10.0 server wrote moments "
        "earlier in the same run — the codes ARE the thing under measurement, so whatever "
        "upstream writes is what it counts and there is no generation for it to be pinned "
        "to. The finding rests on the `status()` readings taken before the count; the sqlite "
        "read corroborates a file upstream had just produced. It is also the file an "
        "argv-shaped probe cannot see, since it derives `search-index.sqlite` from a data "
        "directory rather than taking it on the command line"
    ),
}


def unreasoned(excused: dict[str, Excuse]) -> list[str]:
    """Excused entries whose reason is blank. The load-bearing half of the mapping.

    A reason a contributor may leave empty is the same set of bare names with a longer
    type: every entry passes `""`, nothing breaks, and the list says exactly what it said
    before. Precedent and argument: `tests/test_acceptance_unsupported_reason.py`.
    """
    return sorted(name for name, e in excused.items() if not (e.why or "").strip())


def drifted(found: dict[str, list[str]], excused: dict[str, Excuse]) -> dict[str, dict]:
    """Excused files whose index tables no longer match the set their reason was written for.

    The complement of `test_no_excused_entry_is_stale`, which fires when a file LEAVES the
    class. This fires when it STAYS in the class and changes what it touches — the case
    where the written reason silently becomes false while every test stays green. Compared
    as sets so a reordering is not a drift; `found` is already sorted, the pin is a
    frozenset, and neither ordering is load-bearing.

    Files in `excused` that the scan does not name are ignored here on purpose: that is the
    staleness check's finding, and reporting it twice under two names would make one red
    look like two.
    """
    out: dict[str, dict] = {}
    for name, excuse in excused.items():
        if name not in found:
            continue
        now = frozenset(found[name])
        if now != excuse.tables:
            out[name] = {
                "pinned": sorted(excuse.tables),
                "found": sorted(now),
                "arrived": sorted(now - excuse.tables),
                "gone": sorted(excuse.tables - now),
            }
    return out


def unclassified(repo: Path) -> dict[str, list[str]]:
    """Files the scan names that are neither rostered nor excused."""
    vocabulary = index_vocabulary(repo / "bench")
    roster = rostered(repo / "tests" / "test_index_schema_fixtures.py")
    found = drivers_that_open_an_index(repo, vocabulary)
    return {p: t for p, t in found.items() if p not in roster and p not in EXCUSED}


# --- the derivation is not vacuous -------------------------------------------------


def test_the_vocabulary_is_derived_and_not_empty():
    """Without this, an empty derivation makes every assertion below pass on nothing."""
    vocabulary = index_vocabulary(BENCH)
    missing = VOCABULARY_FLOOR - vocabulary
    assert not missing, (
        f"the index vocabulary no longer derives {sorted(missing)} from "
        "bench/index_schema.mjs and bench/fixtures/make_index_fixture.mjs — update this "
        "parser rather than letting the scan match nothing"
    )
    assert "vector_codes" in vocabulary, "the current generation's code table must be in scope"


def test_the_roster_parses_and_is_not_empty():
    roster = rostered(ROSTER_SUITE)
    assert len(roster) >= 5, (
        f"parsed only {sorted(roster)} out of DRIVERS in {ROSTER_SUITE.name} — the roster "
        "was restructured; update this parser"
    )
    assert all(name.startswith("bench/") for name in roster)


def test_the_scan_finds_the_rostered_drivers():
    """The positive control the live tree provides for free: every driver 0101 rosters by
    hand is a driver this scan derives. A scan that missed them would be reporting closure
    over an inventory that is not the one under discussion."""
    vocabulary = index_vocabulary(BENCH)
    found = set(drivers_that_open_an_index(REPO, vocabulary))
    missing = rostered(ROSTER_SUITE) - found
    assert not missing, f"rostered drivers the scan does not name: {sorted(missing)}"


# --- the scope claim is the one the module makes -------------------------------------


def test_the_search_root_is_the_one_the_module_documents():
    """A scope claim nothing checks is a scope claim that goes stale silently.

    The module's own title says the roster is *closed*; this is what says closed over what.
    Widening `SEARCH_ROOT` without rewriting the docstring's "WHERE THE SCAN LOOKS"
    section fails here, so the widening cannot happen by accident.
    """
    assert SEARCH_ROOT == "bench"
    assert (REPO / SEARCH_ROOT).is_dir()
    assert (REPO / UNSEARCHED_ROOT).is_dir(), (
        "the excluded root no longer exists — re-derive the exclusion rather than leaving "
        "a claim about a directory that is gone"
    )
    doc = __doc__ or ""
    assert f"`{SEARCH_ROOT}/`" in doc, "the docstring must name the root the scan walks"
    assert f"`{UNSEARCHED_ROOT}/`" in doc, "the docstring must name what the root leaves out"


def test_the_inventory_stays_inside_the_search_root():
    vocabulary = index_vocabulary(BENCH)
    outside = sorted(
        path
        for path in drivers_that_open_an_index(REPO, vocabulary)
        if not path.startswith(f"{SEARCH_ROOT}/")
    )
    assert not outside, f"the scan reached outside {SEARCH_ROOT}/: {outside}"


# --- the closure itself -------------------------------------------------------------


def test_every_index_opening_driver_is_rostered_or_excused():
    stray = unclassified(REPO)
    assert not stray, (
        "bench files that open a zoteus-built index and are in neither DRIVERS "
        f"(tests/test_index_schema_fixtures.py) nor EXCUSED: {stray}. Add a fixture case "
        "to the roster, or excuse it here with a written reason."
    )


def test_no_excused_entry_lacks_a_reason():
    assert not unreasoned(EXCUSED), (
        f"excused with no reason: {unreasoned(EXCUSED)} — a bare name records nothing"
    )


def test_no_excused_entry_is_stale():
    """An excuse for a file the scan no longer names is a claim nothing checks any more.

    Removing it is not tidiness: a stale entry silently pre-excuses a future file of the
    same name, which is exactly the arrival this module exists to catch.
    """
    vocabulary = index_vocabulary(BENCH)
    found = set(drivers_that_open_an_index(REPO, vocabulary))
    stale = sorted(set(EXCUSED) - found)
    assert not stale, f"EXCUSED names files the scan no longer finds: {stale}"


def test_no_excused_entry_drifts_from_its_pinned_tables():
    """An excuse that outlives the file it describes is a claim nothing checks any more.

    The staleness check above covers a file LEAVING the class. This covers the case it
    cannot see: the file stays, and starts naming a table its written reason was never
    about. Both `smoke_upstream.py` and `acceptance/adapters/zoteus.py` are excused on
    `meta` being a generation discriminator; the day either gains a `passages_fts` read,
    that argument stops holding and this reds by name rather than staying green.
    """
    vocabulary = index_vocabulary(BENCH)
    found = drivers_that_open_an_index(REPO, vocabulary)
    drift = drifted(found, EXCUSED)
    assert not drift, (
        "excused files now naming index tables their reason was not written against: "
        f"{drift}. Re-read the reason in EXCUSED against the file, then either rewrite it "
        "and re-pin the table set, or roster the driver."
    )


def test_no_driver_is_both_rostered_and_excused():
    both = sorted(rostered(ROSTER_SUITE) & set(EXCUSED))
    assert not both, f"rostered and excused at once — one of the two is wrong: {both}"


# --- positive controls ---------------------------------------------------------------
#
# Built the way `tests/test_guard_completeness.py` builds its own: a synthetic tree in
# `tmp_path`, so each control fires on a case known to be positive rather than on the live
# repository, where a green means only that today's tree happens to be clean.


def _fixture_tree(tmp_path: Path) -> Path:
    """A minimal tree the scan can run against: the two vocabulary sources, copied."""
    (tmp_path / "bench" / "fixtures").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    for name in ("index_schema.mjs", "fixtures/make_index_fixture.mjs"):
        (tmp_path / "bench" / name).write_text(
            (BENCH / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "tests" / "test_index_schema_fixtures.py").write_text(
        "DRIVERS = [\n    driver('index_concentration.mjs', 'current', lambda db, tmp: []),\n]\n"
    )
    return tmp_path


def test_an_arriving_index_driver_is_named(tmp_path):
    """The case that earns this module its place: a new driver that opens a database and
    queries `passages` is named by the scan, with no roster edit and no probe rewritten."""
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "newcomer.py").write_text(
        "import sqlite3\n"
        "con = sqlite3.connect('search-index.sqlite')\n"
        "print(con.execute('SELECT COUNT(*) FROM passages').fetchone())\n"
    )
    assert "bench/newcomer.py" in unclassified(tree)


def test_an_arriving_driver_that_hides_its_import_is_still_named(tmp_path):
    """`bench/issue30_arms.py`'s spelling, reduced: an AST or import-shaped probe looking
    for `import sqlite3` sees nothing here."""
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "sneaky.py").write_text(
        "con = __import__('sqlite3').connect('file:x?mode=ro', uri=True)\n"
        "con.execute(\"SELECT value FROM meta WHERE key='embedderId'\")\n"
    )
    assert "bench/sneaky.py" in unclassified(tree)


def test_a_driver_with_no_index_path_on_argv_is_still_named(tmp_path):
    """`bench/issue30_codebuild_agreement.py`'s shape, reduced. The file an argv-shaped
    probe structurally cannot see: the index path is derived from a data directory, so
    there is no `--index` or `--db` flag to key on."""
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "datadir_driver.py").write_text(
        "import sqlite3\n"
        "from pathlib import Path\n"
        "d = Path('/somewhere/data')\n"
        "con = sqlite3.connect(f\"file:{d / 'search-index.sqlite'}?mode=ro\", uri=True)\n"
        "con.execute('SELECT COUNT(*), SUM(length(code)) FROM vector_codes').fetchone()\n"
    )
    assert "bench/datadir_driver.py" in unclassified(tree)


def test_a_driver_that_builds_its_own_corpus_is_not_named(tmp_path):
    """The half without which the scan proves nothing.

    A scan that names every file passes the three controls above and is worthless: the
    inventory would be the whole of `bench/`, every entry would need a reason, and nobody
    would read the list. This is the negative that gives the positives their meaning —
    a driver over its own scratch tables is not in the class, and must not be named.
    """
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "scratch_bench.mjs").write_text(
        "import { DatabaseSync } from 'node:sqlite';\n"
        "const db = new DatabaseSync('/tmp/scratch.sqlite');\n"
        "db.exec('CREATE TABLE probe(id INTEGER PRIMARY KEY, v BLOB)');\n"
        "db.prepare('SELECT COUNT(*) FROM probe').get();\n"
    )
    assert "bench/scratch_bench.mjs" not in unclassified(tree)
    assert "bench/scratch_bench.mjs" not in drivers_that_open_an_index(
        tree, index_vocabulary(tree / "bench")
    )


def test_a_matching_file_outside_the_search_root_is_not_named(tmp_path):
    """The bound made testable.

    The same driver, byte for byte, in `bench/` and in `verification/probes/`: one is named
    and one is not, and the only difference is the root. That is the module's scope claim
    stated as an experiment rather than as a sentence — and it is what makes a future
    widening a deliberate edit, since widening the scan reds this test by name.

    `verification/probes/` really does hold sixteen files of this class today; the
    docstring names them and ticket 0598 records the deferral.
    """
    tree = _fixture_tree(tmp_path)
    driver = (
        "import sqlite3\n"
        "con = sqlite3.connect('search-index.sqlite')\n"
        "con.execute(\"SELECT value FROM meta WHERE key='schemaVersion'\")\n"
        "con.execute('SELECT COUNT(*) FROM passages')\n"
    )
    (tree / SEARCH_ROOT / "inside.py").write_text(driver)
    (tree / UNSEARCHED_ROOT).mkdir(parents=True)
    (tree / UNSEARCHED_ROOT / "outside.py").write_text(driver)

    named = drivers_that_open_an_index(tree, index_vocabulary(tree / "bench"))
    assert f"{SEARCH_ROOT}/inside.py" in named
    assert f"{UNSEARCHED_ROOT}/outside.py" not in named
    assert not any(p.startswith(UNSEARCHED_ROOT) for p in named)


def test_a_file_that_only_mentions_a_table_in_prose_is_not_named(tmp_path):
    """A comment is not a query. Literal-scoped matching is what keeps the inventory small
    enough to carry a reason per entry."""
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "prose_only.mjs").write_text(
        "// Reads from passages and joins items, one day. No sqlite here yet.\n"
        "export const TODO = 1;\n"
    )
    assert "bench/prose_only.mjs" not in unclassified(tree)


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_excuse_reason_is_refused(blank):
    """Widening the type without refusing the empty value changes nothing at all."""
    excused = {"bench/whatever.py": Excuse(frozenset({"passages"}), blank)}
    assert unreasoned(excused) == ["bench/whatever.py"]


def test_an_excuse_that_gains_a_table_is_named(tmp_path):
    """The degradation control, on a case known to be positive.

    A file excused for reading `meta` alone, which now also reads `passages`. Nothing else
    about it changed: it is still in the class, still excused, still carries a non-blank
    reason. Every other test in this module stays green on it, which is precisely why this
    one has to exist — before the pin, that file's written reason could become false
    without a single red.
    """
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "drifter.py").write_text(
        "import sqlite3\n"
        "con = sqlite3.connect('search-index.sqlite')\n"
        "con.execute(\"SELECT value FROM meta WHERE key='schemaVersion'\")\n"
        "con.execute('SELECT COUNT(*) FROM passages')\n"
    )
    found = drivers_that_open_an_index(tree, index_vocabulary(tree / "bench"))
    excused = {"bench/drifter.py": Excuse(frozenset({"meta"}), "reads the stamp, nothing else")}

    drift = drifted(found, excused)
    assert "bench/drifter.py" in drift
    assert drift["bench/drifter.py"]["arrived"] == ["passages"]
    assert drift["bench/drifter.py"]["gone"] == []

    # …and the same entry, pinned to what the file actually reads, is not named.
    honest = {"bench/drifter.py": Excuse(frozenset({"meta", "passages"}), "re-read and re-pinned")}
    assert drifted(found, honest) == {}


def test_an_excuse_that_loses_a_table_is_named(tmp_path):
    """The other direction, and it is not symmetric with the one above.

    A file that stops reading a table its reason turned on is the quieter half: the reason
    now over-claims rather than under-claims, so no argument in it is falsified by new
    behaviour — it is merely describing a file that no longer exists. Named anyway, because
    a pin that only ever grows is a pin that drifts upward forever and stops discriminating.
    """
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "shrinker.py").write_text(
        "import sqlite3\n"
        "con = sqlite3.connect('search-index.sqlite')\n"
        "con.execute('SELECT COUNT(*) FROM passages')\n"
    )
    found = drivers_that_open_an_index(tree, index_vocabulary(tree / "bench"))
    excused = {
        "bench/shrinker.py": Excuse(frozenset({"meta", "passages"}), "reads the stamp too")
    }
    drift = drifted(found, excused)
    assert drift["bench/shrinker.py"]["gone"] == ["meta"]
    assert drift["bench/shrinker.py"]["arrived"] == []


def test_drift_is_not_reported_for_a_file_the_scan_no_longer_names(tmp_path):
    """Staleness is one finding with one name, not two reds for one cause.

    An excuse whose file has left the class entirely is `test_no_excused_entry_is_stale`'s
    to report. If `drifted` also named it, a single deletion would red two tests and read
    as two independent defects.
    """
    tree = _fixture_tree(tmp_path)
    found = drivers_that_open_an_index(tree, index_vocabulary(tree / "bench"))
    gone = {"bench/deleted.py": Excuse(frozenset({"meta"}), "a file that is not there")}
    assert "bench/deleted.py" not in found
    assert drifted(found, gone) == {}


def test_an_absent_excuse_is_refused_by_the_closure_check(tmp_path):
    """The other half of "rostered or excused": an entry that is simply missing.

    A file present in the tree, named by the scan, and absent from both mappings is the
    default state of every driver that arrives — so this is the control for the path the
    module is actually built to walk.
    """
    tree = _fixture_tree(tmp_path)
    (tree / "bench" / "unlisted.mjs").write_text(
        "import { DatabaseSync } from 'node:sqlite';\n"
        "const db = new DatabaseSync(process.argv[2]);\n"
        "db.prepare('SELECT item_key FROM passages JOIN items USING (item_key)').all();\n"
    )
    stray = unclassified(tree)
    assert "bench/unlisted.mjs" in stray
    assert stray["bench/unlisted.mjs"] == ["items", "passages"]
