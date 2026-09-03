"""The fold gate can fail, can fall back, and can say it could not look.

Three defects shipped together in `bench/fold_sweep.mjs`, and all three were the
same defect wearing different clothes: the gate could not report a red.

1. It always exited 0. On a miss it printed `WARNING: N codepoint(s) send a query
   where the index is not` and returned success, so `make` and every caller read
   it as green. Measured on 2026-09-02 against the reviewed SHA in `UPSTREAM`,
   the *unchanged* script found 16 misses and exited 0 — the committed artifact
   had said zero since ticket 0009 and nobody was told otherwise.
2. It crashed on any tree without `normalizeForSearch`. SPEC.md §5.2.8 requires
   the query side to fall back to `tokenize`-only there, so a pre-fold tree is
   red *by a recorded miss count* rather than by a `TypeError` with no artifact.
3. Its ranges stopped at Latin, Greek, Cyrillic and Vietnamese, so the three
   script classes R7 names that break a Latin-shaped fold — Arabic, Devanagari
   and Chinese — were never swept.

The subprocess tests below drive the real script against stub checkouts, because
the failure modes are the exit code and the fallback branch, and neither is
visible to a test that imports a function. They use `--blocks` so a stub run
sweeps one script class instead of thirty thousand codepoints; the exit-code
discipline is the same either way.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SWEEP = REPO / "bench" / "fold_sweep.mjs"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(
    NODE is None, reason="node is not on PATH; the gate is a Node script"
)

#: A pre-fold checkout: `tokenize` alone, matching upstream at v1.7.1 — lowercase,
#: split on non-alphanumerics, drop stopwords and 1-character tokens, no fold.
PRE_FOLD = """\
const STOPWORDS = new Set(['the', 'a', 'an', 'and', 'of', 'to', 'in', 'on', 'for']);
export function tokenize(text) {
  return (text.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(
    (t) => t.length > 1 && !STOPWORDS.has(t),
  );
}
"""

#: A checkout that folds everything to nothing. Every probe narrows and none
#: misses, so the gate must call it agreed: the gate's clause is about terms the
#: query side produces, and this one produces none. Without this arm the exit-code
#: assertions below would pass on a gate hardwired to fail.
NEVER_A_TOKEN = """\
export function normalizeForSearch(text) { return ''; }
export function tokenize(text) { return []; }
"""


def checkout(root: Path, module: str) -> Path:
    """A stub built checkout the gate can point `--fork` at."""
    built = root / "dist" / "features" / "search"
    built.mkdir(parents=True)
    (built / "tokenize.js").write_text(module, encoding="utf-8")
    (root / "package.json").write_text('{"version": "0.0.0-stub"}', encoding="utf-8")
    return root


def sweep(tmp_path: Path, tree: Path | None, *extra: str) -> tuple[int, str, dict | None]:
    """Run the real gate. Returns (exit code, stderr+stdout, artifact or None)."""
    out = tmp_path / "out.json"
    argv = [NODE, str(SWEEP), "--output", str(out)]
    if tree is not None:
        argv += ["--fork", str(tree)]
    argv += list(extra)
    done = subprocess.run(argv, capture_output=True, text=True, cwd=REPO)
    artifact = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    return done.returncode, done.stdout + done.stderr, artifact


@needs_node
def test_a_pre_fold_tree_is_red_by_classification_not_by_crash(tmp_path):
    """Defect 2, and the fallback path no green run exercises.

    A tree without `normalizeForSearch` must produce a miss count and a nonzero
    exit, and the artifact must say which arm produced the numbers — the two are
    not comparable and a reader of the counts has to be able to tell.
    """
    tree = checkout(tmp_path / "prefold", PRE_FOLD)
    code, output, artifact = sweep(tmp_path, tree, "--blocks", "Devanagari")

    assert "TypeError" not in output and "at querySide" not in output, output
    assert artifact is not None, "no artifact written: the gate crashed before recording"
    assert artifact["query_side"] == "tokenize-only", artifact["query_side"]
    assert artifact["query_side_caveat"], "the fallback arm must record why it under-reports"
    assert artifact["misses_total"] > 0, "a pre-fold tree must be red by a recorded miss count"
    assert artifact["verdict"] == "red"
    assert code == 1, f"expected exit 1 on a miss count, got {code}\n{output}"


@needs_node
def test_a_query_side_that_produces_no_term_is_agreed_and_exits_zero(tmp_path):
    """The discriminating control: the gate must be able to come out green.

    Every assertion above would also hold for a gate wired to fail always.
    """
    tree = checkout(tmp_path / "quiet", NEVER_A_TOKEN)
    code, output, artifact = sweep(tmp_path, tree, "--blocks", "Devanagari")

    assert artifact is not None
    assert artifact["query_side"] == "normalizeForSearch+class"
    assert artifact["misses_total"] == 0, artifact["misses"]
    assert artifact["verdict"] == "agreed"
    assert code == 0, f"expected exit 0 with no miss, got {code}\n{output}"


@needs_node
def test_a_miss_fails_the_gate_rather_than_printing_a_warning(tmp_path):
    """Defect 1, in its own right.

    The old script's whole failure was that this exact state — misses recorded in
    the artifact — came with exit 0. Asserted against the artifact rather than the
    message text, so a reworded warning does not silently retire the test.
    """
    tree = checkout(tmp_path / "prefold", PRE_FOLD)
    code, output, artifact = sweep(tmp_path, tree, "--blocks", "Devanagari")
    assert artifact["misses_total"] > 0
    assert code != 0, (
        "a recorded miss count with exit 0 is the defect this gate was rewritten for"
    )
    assert "WARNING" not in output, "a red is a nonzero exit, not a warning the caller must read"


@needs_node
def test_an_absent_checkout_is_not_run_and_never_green(tmp_path):
    """A gate that cannot look reports that it could not look (ticket 0578, Action 6)."""
    code, output, artifact = sweep(tmp_path, tmp_path / "nothing-here")
    assert code == 3, f"expected the could-not-look code, got {code}\n{output}"
    assert "NOT-RUN" in output, output
    assert "Error:" not in output and "at async" not in output, "a stack trace is not a diagnostic"
    assert artifact is None, "a run that could not look must not leave an artifact behind"


@needs_node
def test_an_unbuilt_checkout_is_not_run_and_names_what_is_missing(tmp_path):
    """The common case: the checkout exists and nobody ran the build in it."""
    (tmp_path / "unbuilt").mkdir()
    code, output, _ = sweep(tmp_path, tmp_path / "unbuilt")
    assert code == 3, output
    assert "not built" in output and "dist/features/search/tokenize.js" in output, output


@needs_node
def test_a_missing_output_is_a_usage_error(tmp_path):
    """Exit 2 stays what it was, so the three failure codes remain distinguishable."""
    done = subprocess.run([NODE, str(SWEEP)], capture_output=True, text=True, cwd=REPO)
    assert done.returncode == 2, done.stderr
    assert "usage:" in done.stderr


@needs_node
def test_a_block_filter_matching_nothing_is_a_usage_error_not_an_empty_green(tmp_path):
    """A filtered run that swept no block would otherwise report agreement it never measured."""
    tree = checkout(tmp_path / "quiet", NEVER_A_TOKEN)
    code, output, _ = sweep(tmp_path, tree, "--blocks", "no-such-script")
    assert code == 2, f"expected a usage error, got {code}\n{output}"


def test_the_exit_code_discipline_is_documented_in_the_file():
    """The header is where a caller wiring this into a Makefile reads the contract."""
    text = SWEEP.read_text(encoding="utf-8")
    header = text.split("import {")[0]
    for code in ("0", "1", "2", "3"):
        assert f"//   {code}  " in header, f"exit code {code} is not documented in the header"


def test_the_r7_script_classes_have_ranges():
    """Defect 3. R7's second tier names one language per script and morphology class;
    Arabic, Devanagari and CJK were the three with no range at all.

    Read off the RANGES table rather than off the whole file, so a mention in a
    comment cannot stand in for a swept block.
    """
    text = SWEEP.read_text(encoding="utf-8")
    table = text.split("const RANGES = [", 1)[1].split("\n];", 1)[0]
    # Positive control: the block the sweep has always carried must be found by the
    # same reader, or a drift in the table's shape would make every miss below vacuous.
    assert "Cyrillic" in table, "RANGES was not read — the table's shape has changed"
    for script in ("Arabic", "Devanagari", "CJK Unified Ideographs"):
        assert script in table, f"R7 names {script} and the sweep has no range for it"


def test_each_added_script_class_has_a_word_level_regression():
    """A codepoint range proves the block was swept; only a word proves the script's
    own morphology was tried — joining, short vowels, matras, a Han run with no
    boundaries. Each entry carries a `why`, as the eight original ones do.
    """
    text = SWEEP.read_text(encoding="utf-8")
    table = text.split("const REGRESSIONS = [", 1)[1].split("\n];", 1)[0]
    assert "théorie" in table, "REGRESSIONS was not read — the table's shape has changed"
    for word, script in (("مكتبة", "Arabic"), ("\\u0958", "Devanagari"), ("数据", "Chinese")):
        assert word in table, f"no word-level regression for {script}"


def test_the_committed_artifact_records_which_arm_produced_it():
    """The artifact is the standing record. A reader must be able to tell a full
    sweep on a folding tree from a filtered run on a pre-fold one without rerunning it.
    """
    artifact = json.loads(
        (REPO / "bench" / "results" / "0578-fold-sweep" / "codepoints.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact["query_side"] in {"normalizeForSearch+class", "tokenize-only"}
    assert artifact["blocks_filter"] is None, "the committed record must be a full sweep"
    assert artifact["verdict"] == ("red" if artifact["misses_total"] else "agreed")
    assert artifact["misses_codepoint"] + artifact["misses_word"] == artifact["misses_total"]


def test_the_gate_is_reachable_from_the_makefile():
    """A gate nothing can run is a gate nobody runs. It is deliberately outside
    `check` — see the Makefile comment — so its presence as a target is what the
    repository can assert.
    """
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "\nfold-gate:" in makefile, "no fold-gate target"
    assert "bench/fold_sweep.mjs" in makefile, "the fold-gate target does not run the sweep"
    phony = [line for line in makefile.splitlines() if line.startswith(".PHONY:")]
    assert len(phony) == 1, "expected exactly one .PHONY line; update this parser"
    assert "fold-gate" in phony[0].split(), (
        "fold-gate collides with no path today, but a .PHONY-less target is one "
        "`fold-gate` file away from a silent no-op (t0507)"
    )
