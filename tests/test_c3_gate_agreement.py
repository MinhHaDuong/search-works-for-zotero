"""C3's RAM ceiling and DESIGN §2.8's RSS gate carry one number, together.

Ticket 0268's test: the constraint and the gate threshold were re-pinned in one
change (DECISIONS.md 2026-08-30, the 750 MB ruling), and this keeps them from
drifting apart again. Run against the pre-ruling tree it fails on both counts —
that red state is what made it a check rather than a null (the 300-era text
carried the number in CONSTRAINTS and §2.8 independently).
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CEILING = "750 MB"
OLD = "300 MB"


def test_constraint_and_gate_carry_the_same_ceiling():
    # Whitespace-normalized: the documents hard-wrap at ~72 columns, so the
    # gate line may break between the comparator and the figure.
    constraints = " ".join((REPO / "spec" / "CONSTRAINTS.md").read_text(encoding="utf-8").split())
    design = " ".join((REPO / "spec" / "DESIGN.md").read_text(encoding="utf-8").split())
    assert f"RSS ≤ ~{CEILING}" in constraints, "C3's budget line does not carry the ratified ceiling"
    assert f"p95 ≤ {CEILING}" in design, "DESIGN §2.8's RSS gate does not carry the ratified ceiling"


def test_the_old_ceiling_survives_only_in_the_ledger():
    # DECISIONS.md is append-only history and legitimately keeps the 300 MB era;
    # everywhere else in the chain the old number is drift.
    for name in ("CONSTRAINTS.md", "DESIGN.md", "REQUIREMENTS.md", "README.md"):
        text = (REPO / "spec" / name).read_text(encoding="utf-8")
        assert OLD not in text, f"spec/{name} still carries the superseded {OLD} ceiling"
