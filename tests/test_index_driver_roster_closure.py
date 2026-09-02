"""The roster of index-opening drivers is closed: a driver that ARRIVES cannot stay ungated.

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

WHAT THE CLASS IS, AND WHY THE OBVIOUS PROBE MISSES A THIRD OF IT
-----------------------------------------------------------------
An earlier probe looked for drivers that take an index path on the command line — `--db`,
`--index` — and it found two of the three. `issue30_codebuild_agreement.py` takes no index
argument at all: it derives `search-index.sqlite` from a data directory. An argv-shaped
probe cannot see that file no matter how carefully it is written, because the property it
tests is not the property that matters. So the class this module scans for is **opens a
SQLite database and names a zoteus index table in SQL**, which is what "pinned to a schema
upstream may rename" actually means.

The other finding, stated because it shapes every classification below: all three
uncovered files are Python, and `bench/index_schema.mjs` — the gate a rostered driver calls
before its first query — is a JavaScript module. `DRIVERS` is entirely `.mjs`. The roster's
hole is therefore not only hand-maintenance; a Python driver is structurally outside the
gate, and putting one inside it means a second Python mirror of the schema constants. This
repo's most expensive recurring defect is a fact stated twice (AGENTS.md, "One statement per
fact"), and `bench/check_models.py` exists because of it. That cost is real, and it is why
each of the three is excused on a reason of its own rather than gated by a duplicated
mirror. Should a Python driver ever need the gate for its own sake, the port is one module
and a test that asserts it agrees with the `.mjs` constants — not something to smuggle in
behind a roster entry.

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

import pytest

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"
ROSTER_SUITE = REPO / "tests" / "test_index_schema_fixtures.py"

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
    """The inventory, derived from the tree: path -> the index tables it names."""
    found: dict[str, list[str]] = {}
    for path in sorted((repo / "bench").rglob("*")):
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

#: Files the scan names that are deliberately not rostered, each with the reason that makes
#: the exclusion reviewable. A bare name would be the same undifferentiated cell the roster
#: already is — "this driver hides a gate it should have" and "this file has no generation
#: to be pinned to" are opposite findings, and a set of names cannot tell them apart. A
#: blank reason is refused; see `unreasoned` and its control.
EXCUSED: dict[str, str] = {
    # --- the guard's own substrate ---------------------------------------------------
    "bench/index_schema.mjs": (
        "the gate itself. The table names it appears to query are the ones it prints in its "
        "refusals, and the vocabulary this scan matches against is derived from its own "
        "exported constants — it is what the roster is held to, not a member of it"
    ),
    "bench/fixtures/make_index_fixture.mjs": (
        "the fixture generator. It WRITES both generations rather than reading one, and it "
        "is the other file the vocabulary is derived from; a generation gate on the thing "
        "that manufactures both generations would refuse its own output"
    ),
    "bench/upstream_catchup.py": (
        "never opens a database: it greps upstream's `sqlite-index.ts` for the `passages` "
        "DDL and for `SCHEMA_VERSION`, and reports a move. It is the detector that tells "
        "this roster it needs updating, not a driver that could be pinned to a stale "
        "generation. It appears here only because the sqlite test is a token search"
    ),
    # --- their own scratch corpus ------------------------------------------------------
    "bench/constrained_match.mjs": OWN_CORPUS,
    "bench/cosine_fusion.mjs": OWN_CORPUS,
    "bench/fts5_bench.mjs": OWN_CORPUS,
    "bench/fts5_keyword_arm.mjs": OWN_CORPUS,
    "bench/vec_scan_shapes.mjs": OWN_CORPUS,
    "bench/vec_recall.ts": (
        "builds its own corpus through upstream's own `Fts5PassageStore` into a scratch "
        "$TMPDIR database and then re-opens that file raw, to run the exact float32 ranking "
        "the store no longer takes. The schema is whatever that store wrote in the same "
        "process; there is no foreign index to drift from"
    ),
    # --- upstream's own code owns the check, in the same run ----------------------------
    "bench/derive_droplist.mjs": UPSTREAM_OWNS_IT,
    "bench/smoke_upstream.py": (
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
    "bench/issue30_arms.py": (
        "`geometry(MASTER)` describes the substrate the run hands to upstream's own "
        "binaries: every arm gets a `shutil.copy2` of that same file and a v1.9.0 or "
        "v1.10.0 server started on it, so an index of a generation upstream cannot read is "
        "refused by upstream, in the same run, seconds later. The read is a description of "
        "an accepted substrate rather than an independent gate — `derive_droplist.mjs`'s "
        "case seen from the server side — and it runs before the servers start, so a rename "
        "costs seconds rather than the hour the roster exists to protect"
    ),
    "bench/issue30_codebuild_agreement.py": (
        "it counts `vector_codes` in a file upstream's own v1.10.0 server wrote moments "
        "earlier in the same run — the codes ARE the thing under measurement, so whatever "
        "upstream writes is what it counts and there is no generation for it to be pinned "
        "to. The finding rests on the `status()` readings taken before the count; the sqlite "
        "read corroborates a file upstream had just produced. It is also the file an "
        "argv-shaped probe cannot see, since it derives `search-index.sqlite` from a data "
        "directory rather than taking it on the command line"
    ),
}


def unreasoned(excused: dict[str, str]) -> list[str]:
    """Excused entries whose reason is blank. The load-bearing half of the mapping.

    A reason a contributor may leave empty is the same set of bare names with a longer
    type: every entry passes `""`, nothing breaks, and the list says exactly what it said
    before. Precedent and argument: `tests/test_acceptance_unsupported_reason.py`.
    """
    return sorted(name for name, why in excused.items() if not (why or "").strip())


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
    assert unreasoned({"bench/whatever.py": blank}) == ["bench/whatever.py"]


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
