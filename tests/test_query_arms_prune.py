"""The arm probe reads what an arm did, or refuses (ticket 0541).

`bench/query_arms.mjs` reported its fallback columns by re-deriving each arm's
pruning rule from two exports, `query-terms.MIN_MATCH_TERMS` and
`tokenize.isStopword`. The 0091 r5 arms export neither — pruning moved into
`pruneTerms(terms, prunable, whenNothingSurvives)`, and the rule changed shape as
well as name, so there is no minimum left to compare against. The comparison
therefore read `kept.length < undefined`, which is `false` for every query, and
the driver reported a clean zero in the column that was supposed to carry the
finding while the latency columns looked perfectly healthy.

What earns these tests their place is the r5 fallback case: it is red against the
committed expression and green against the probe. The others hold the repair to
the rest of its contract — the pre-r5 arms still read, and an arm whose shape
cannot be recognised stops the run instead of contributing zeros nobody measured.

Fixture arms rather than built dists: the defect is entirely in how the driver
reads an arm's exports, and a fixture can hold a shape no dist on this machine
has any more.
"""

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "bench" / "query_arms_lib.mjs"

TOKENIZE = "export function tokenize(text) { return (text.toLowerCase().match(/[a-z0-9]+/g) ?? []); }"

#: The r5 shape, copied from `fork-0091/src/features/search/query-terms.ts`: three
#: parameters, the third saying what to do when nothing survives, and no
#: `MIN_MATCH_TERMS` anywhere.
R5_QUERY_TERMS = """
export const MIN_PHRASE_TERMS = 3;
export const HIGH_DF_RATIO = 0.3;
export function pruneTerms(terms, prunable, whenNothingSurvives = 'phrase') {
  if (!prunable) return terms;
  const kept = terms.filter((t) => !prunable(t));
  if (kept.length) return kept;
  if (whenNothingSurvives === 'raw') return terms;
  return terms.length >= MIN_PHRASE_TERMS ? terms : kept;
}
"""

#: The pre-r5 shape: a minimum, and the arm's own stopword predicate.
LEGACY_QUERY_TERMS = """
export const MIN_MATCH_TERMS = 2;
export function pruneTerms(terms, prunable, min) {
  if (!prunable) return terms;
  const kept = terms.filter((t) => !prunable(t));
  return kept.length >= min ? kept : terms;
}
"""

LEGACY_TOKENIZE = (
    TOKENIZE + "\nconst STOP = new Set(['the', 'of', 'and', 'to']);"
    "\nexport function isStopword(t) { return STOP.has(t); }\n"
)

DROPLIST = ["the", "of", "and", "to", "be", "or", "not"]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def write_arm(root: Path, name: str, tokenize: str, query_terms: str | None) -> None:
    d = root / name / "features" / "search"
    d.mkdir(parents=True)
    (d / "tokenize.js").write_text(tokenize, encoding="utf-8")
    if query_terms is not None:
        (d / "query-terms.js").write_text(query_terms, encoding="utf-8")


@pytest.fixture(scope="module")
def arms(tmp_path_factory):
    root = tmp_path_factory.mktemp("arms")
    write_arm(root, "r5", TOKENIZE, R5_QUERY_TERMS)
    write_arm(root, "legacy", LEGACY_TOKENIZE, LEGACY_QUERY_TERMS)
    # A query-terms module the probe cannot read: no pruneTerms, no MIN_MATCH_TERMS.
    write_arm(root, "opaque", TOKENIZE, "export const SOMETHING_ELSE = 7;\n")
    write_arm(root, "stock", TOKENIZE, None)
    return root


def probe(arms: Path, arm: str, queries: list[str]) -> dict:
    """Drive the real module through node, the way the drivers do."""
    script = textwrap.dedent(
        f"""
        const {{ makeArmProbe }} = await import({str(LIB)!r});
        const tk = await import({str(arms)!r} + '/{arm}/features/search/tokenize.js');
        let qt;
        try {{ qt = await import({str(arms)!r} + '/{arm}/features/search/query-terms.js'); }}
        catch {{ qt = undefined; }}
        const droplist = new Set({json.dumps(DROPLIST)});
        try {{
          const p = makeArmProbe(
            {{ name: {arm!r}, tokenize: tk.tokenize, queryTerms: qt, isStopword: tk.isStopword }},
            droplist,
          );
          const rows = {json.dumps(queries)}.map((q) => ({{ query: q, ...p.termsFor(q) }}));
          console.log(JSON.stringify({{ ok: true, shape: p.shape,
                                       predicate: p.predicate_source, rows }}));
        }} catch (e) {{
          console.log(JSON.stringify({{ ok: false, error: String(e.message) }}));
        }}
        """
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


def committed_terms_for(arm_exports: dict, query: str) -> dict:
    """The committed expression, transcribed, so the red step is in the suite.

    `MIN_MATCH_TERMS` absent makes the comparison `kept.length < undefined`, which
    is `false` — in JavaScript and, written this way, in Python too.
    """
    raw = list(dict.fromkeys(query.lower().split()))
    predicate = arm_exports["predicate"]
    kept = [t for t in raw if not predicate(t)]
    minimum = arm_exports.get("MIN_MATCH_TERMS")
    fell_back = False if minimum is None else len(kept) < minimum
    return {"terms": raw if fell_back else kept, "fellBack": fell_back}


# --- the case that goes red against the committed expression -------------------

R5_DEGENERATE = "to be or not to be"


def test_committed_expression_is_blind_to_the_r5_fallback():
    """The red step, kept in the suite so the repair cannot silently regress.

    Every term of this query is on the droplist, so the r5 arm prunes to nothing
    and — with `whenNothingSurvives: 'raw'`, which is what every shipped call site
    passes — answers on the raw set. The committed expression says the opposite
    twice over: no fallback, and a search on no terms at all.
    """
    committed = committed_terms_for({"predicate": lambda t: t in DROPLIST}, R5_DEGENERATE)
    assert committed["fellBack"] is False
    assert committed["terms"] == []


def test_probe_sees_the_r5_fallback(arms):
    out = probe(arms, "r5", [R5_DEGENERATE])
    assert out["ok"], out.get("error")
    assert out["shape"] == "prune-terms-r5"
    row = out["rows"][0]
    assert row["fellBack"] is True
    # The terms the arm actually searches on, not an idealisation of them.
    assert row["terms"] == ["to", "be", "or", "not"]


def test_probe_reports_an_ordinary_r5_query_as_pruned_not_fallen_back(arms):
    out = probe(arms, "r5", ["the carbon tax and the revenue"])
    row = out["rows"][0]
    assert row["fellBack"] is False
    assert row["terms"] == ["carbon", "tax", "revenue"]
    assert sorted(row["pruned"]) == ["and", "the"]


# --- the shapes the repair must keep reading ----------------------------------


def test_pre_r5_arm_still_reads_through_its_own_min_and_predicate(arms):
    out = probe(arms, "legacy", ["to be or not to be", "carbon tax revenue"])
    assert out["ok"], out.get("error")
    assert out["shape"] == "prune-terms-min"
    # This arm exports its own stopword list, so the probe must prune by that and
    # not by the index droplist.
    assert out["predicate"] == "arm.tokenize.isStopword"
    degenerate, ordinary = out["rows"]
    # 'be', 'or', 'not' survive its four-word list, so it clears MIN_MATCH_TERMS 2.
    assert degenerate["fellBack"] is False
    assert ordinary["fellBack"] is False


def test_stock_arm_is_named_as_structurally_zero_not_measured(arms):
    out = probe(arms, "stock", ["the carbon tax"])
    assert out["ok"], out.get("error")
    assert out["shape"] == "tokenize-only"
    # No separable prune stage to introspect. The shape is what tells a reader the
    # zero in the fallback column was not measured.
    assert out["rows"][0]["fellBack"] is False


# --- the refusal --------------------------------------------------------------


def test_unreadable_arm_refuses_rather_than_reporting_zeros(arms):
    out = probe(arms, "opaque", ["the carbon tax"])
    assert out["ok"] is False
    message = out["error"]
    # The message has to name what it found, or the next reader repeats this hour.
    assert "cannot introspect its pruning" in message
    assert "SOMETHING_ELSE" in message
    assert "pruneTerms arity: absent" in message
