"""Guard on the truncation-regression artifact (ticket 0140).

The embedding run needs node, transformers.js and a cached model — workstation
substrate, not the fast tier — so the regression is a committed artifact
(bench/truncation_regression.mjs writes it) and this guard makes the suite red
whenever the artifact stops proving what the ticket demands:

- its positive control must discriminate (head and tail dissimilar), because
  without it truncation and similarity are indistinguishable;
- the 768 arm must exhibit the defect (chunk vector identical to its head's) —
  the regression "fails against a 768-token cap" is this line;
- the settled arm must not;
- the budget it ran at must equal the ratified construction resolved against
  the current window census, so a moved ceiling or a re-measured census
  reddens this guard instead of leaving a stale artifact standing
  (a judgement must not outlive its subject).
"""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ARTIFACT = REPO / "bench" / "results" / "0140-truncation-regression" / "regression.json"
CENSUS = REPO / "bench" / "results" / "0140-model-windows" / "candidate-windows.json"


def load_geometry():
    spec = importlib.util.spec_from_file_location("geometry", REPO / "bench" / "geometry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


art = json.loads(ARTIFACT.read_text())
census = json.loads(CENSUS.read_text())
g = load_geometry()

WINDOW = census["min_window"]


def test_positive_control_head_and_tail_are_dissimilar():
    # Without this the other two assertions are vacuous: a head similar to its
    # tail embeds the same truncated or not.
    assert art["cosines"]["head_vs_tail"] < 0.95


def test_the_premise_holds_the_head_exceeds_the_window():
    # A head shorter than the window means the old arm never truncates and the
    # regression proves nothing — the second false construction the ticket names.
    assert art["tokens"]["head"] > WINDOW


def test_the_old_768_cap_exhibits_silent_truncation():
    # The defect, demonstrated: the 768-cap chunk embeds identically to its
    # head alone; the tail left no trace. This is the arm that makes the
    # regression red against cycle 2's geometry.
    assert art["old_cap"] > WINDOW
    assert art["cosines"]["old_arm_long_vs_head"] > 0.999


def test_the_settled_budget_does_not_truncate():
    assert art["cosines"]["settled_arm_seam_vs_a_part"] < 0.999


def test_every_settled_chunk_fits_the_window():
    # ntok includes the special tokens, so the comparison is against the
    # window itself, not window minus specials.
    assert art["tokens"]["settled_chunks"], "artifact carries no settled chunks"
    for n in art["tokens"]["settled_chunks"]:
        assert n <= WINDOW


def test_the_artifact_ran_at_the_ratified_budget():
    # Ties the committed run to SPEC.md §5.2.2's construction as implemented in
    # bench/geometry.py, resolved against the committed census. If the ceiling
    # moves or the census is re-measured, this fails until the regression is
    # re-run — the artifact cannot outlive the ratification it certifies.
    prefix_tokens = 0 if art["model"]["passage_prefix"] == "" else None
    assert prefix_tokens is not None, "non-empty prefix: recompute its token count in the driver"
    expected = g.resolve_budget(WINDOW, art["special_tokens"], prefix_tokens)
    assert art["budget"] == expected
