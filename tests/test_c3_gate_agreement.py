"""C3's RAM ceiling and SPEC.md §5.2.8's RSS gate carry one number, together.

Ticket 0268's test: the constraint and the gate threshold were re-pinned in one
change (DECISIONS.md 2026-08-30, the 750 MB ruling), and this keeps them from
drifting apart again. Run against the pre-ruling tree it fails on both counts —
that red state is what made it a check rather than a null (the 300-era text
carried the number in C3 and §5.2.8 independently). CONSTRAINTS and DESIGN
merged into one SPEC.md on 2026-09-01 (DECISIONS.md); both halves are read
from the same file since, which is why every check below reads it twice
under two names rather than once — the point is that both sections still
carry the number, not that they live apart.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CEILING = "750 MB"
OLD = "300 MB"


def test_constraint_and_gate_carry_the_same_ceiling():
    # Whitespace-normalized: the document hard-wraps at ~72 columns, so the
    # gate line may break between the comparator and the figure.
    spec = " ".join((REPO / "SPEC.md").read_text(encoding="utf-8").split())
    assert f"RSS ≤ ~{CEILING}" in spec, "C3's budget line does not carry the ratified ceiling"
    assert f"p95 ≤ {CEILING}" in spec, "SPEC.md §5.2.8's RSS gate does not carry the ratified ceiling"


def test_the_old_ceiling_survives_only_in_the_ledger():
    # DECISIONS.md is append-only history and legitimately keeps the 300 MB era;
    # everywhere else in the chain the old number is drift.
    for name in ("SPEC.md", "README.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert OLD not in text, f"{name} still carries the superseded {OLD} ceiling"


# The sole-writer ruling (DECISIONS.md 2026-08-31) re-pinned the pipeline
# ceiling on the same 0263 evidence: the one pipeline worker is the model plus
# one batch, and no multilingual candidate fit under the 500 MB figure ratified
# against the English-embedder picture. Same shape as above: constraint and
# gate carry the number together, the ledger alone keeps the old era.
PIPELINE_CEILING = "750 MB"
OLD_PIPELINE = "500 MB"


def test_pipeline_constraint_and_gate_carry_the_same_ceiling():
    spec = " ".join((REPO / "SPEC.md").read_text(encoding="utf-8").split())
    assert f"pipeline worker peak ≤ ~{PIPELINE_CEILING}" in spec, (
        "C3's pipeline budget line does not carry the re-pinned ceiling"
    )
    assert f"pipeline-worker peak ≤ {PIPELINE_CEILING}" in spec, (
        "SPEC.md §5.2.8's RSS gate does not carry the re-pinned pipeline ceiling"
    )


def test_the_old_pipeline_ceiling_survives_only_in_the_ledger():
    # "500 MB" never names anything else in the chain: the token budget's 500
    # is unitless, so the string with the unit is unambiguous drift.
    for name in ("SPEC.md", "README.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert OLD_PIPELINE not in text, (
            f"{name} still carries the superseded {OLD_PIPELINE} pipeline ceiling"
        )
