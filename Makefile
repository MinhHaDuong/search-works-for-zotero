# Gates for this repo's own harness code.
#
# The TypeScript under test lives in `fork/`, a separate checkout with its own
# suite (`npx vitest run` there) — nothing here runs it. What this covers is the
# measurement harness in `bench/` and the figure guard that keeps the prose
# honest about it.
#
# Added 2026-08-22 because `project-state.py` reported `tests.runner: none` on a
# repo that had acquired a pytest suite the same day: with no runner declared,
# every future healthcheck would have said "no tests" and skipped them. A suite
# nothing knows how to run is a suite nobody runs.

.PHONY: check check-fast lint figures help

help:
	@echo "make check       — everything: lint, figures, tests"
	@echo "make check-fast  — the tests alone"
	@echo "make lint        — ruff over the harness"
	@echo "make figures     — every figure quoted in the prose still matches its artifact"

check: lint figures check-fast

check-fast:
	python3 -m pytest tests/ -q

lint:
	ruff check bench/ tests/

# The guard against the defect this repo spent a session on: a figure updated in
# an artifact and left stale in the paragraph quoting it. Also run by the test
# suite, so `check-fast` alone still catches it; kept as its own target because
# it is the one to run after any re-measurement.
figures:
	python3 bench/check_figures.py
