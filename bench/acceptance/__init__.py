"""The target-neutral acceptance harness: one assertion layer, one adapter per target.

Ratified 2026-09-02 (`DECISIONS.md`); specified in `SPEC.md` §5.2.8. Neither is
restated here — this package cites addresses.

The split this package exists to hold: `interface.py` is the layer's vocabulary
and holds no target's name, `assertions.py` phrases requirement clauses over that
vocabulary, and `adapters/` holds one thin declaration per target. An assertion
that mentions a target has left the layer, and
`tests/test_acceptance_layer_is_target_neutral.py` is the guard that says so.
"""
