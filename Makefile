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

include UPSTREAM

.PHONY: check check-fast lint figures help upstream-status upstream-checkout

help:
	@echo "make check       — everything: lint, figures, tests"
	@echo "make check-fast  — the tests alone"
	@echo "make lint        — ruff over the harness"
	@echo "make figures     — every figure quoted in the prose still matches its artifact"
	@echo "make upstream-status   — compare the reviewed SHA with upstream main"
	@echo "make upstream-checkout — recreate fork/ at the reviewed SHA (only if absent)"

check: lint figures check-fast

check-fast:
	python3 -m pytest tests/ -q

lint:
	# Ruff's default selection has changed across releases. Spell out the
	# historical default so this gate means the same thing on every machine.
	# verification/probes/ is in scope too: a probe script that produced a
	# committed figure is code we depend on, and moving one out of bench/
	# must not move it out of the lint gate.
	ruff check --select E4,E7,E9,F bench/ tests/ verification/probes/

# The guard against the defect this repo spent a session on: a figure updated in
# an artifact and left stale in the paragraph quoting it. Also run by the test
# suite, so `check-fast` alone still catches it; kept as its own target because
# it is the one to run after any re-measurement.
figures:
	python3 bench/check_figures.py

upstream-status:
	@set -eu; \
	remote="$$(git ls-remote "$(UPSTREAM_REPOSITORY)" "refs/heads/$(UPSTREAM_BRANCH)" | awk 'NR == 1 { print $$1 }')"; \
	test -n "$$remote" || { echo "Could not resolve upstream $(UPSTREAM_BRANCH)" >&2; exit 2; }; \
	echo "reviewed  $(UPSTREAM_REVIEWED_SHA) ($(UPSTREAM_REVIEWED_VERSION), $(UPSTREAM_REVIEWED_DATE))"; \
	echo "upstream  $$remote ($(UPSTREAM_BRANCH))"; \
	if test -d fork/.git; then echo "checkout  $$(git -C fork rev-parse HEAD)"; else echo "checkout  absent"; fi; \
	test "$$remote" = "$(UPSTREAM_REVIEWED_SHA)" || { echo "STALE: upstream has moved; review before changing UPSTREAM" >&2; exit 1; }; \
	echo "OK: reviewed baseline is current"

upstream-checkout:
	@test ! -e fork || { echo "Refusing to overwrite existing fork/" >&2; exit 1; }
	git clone --no-checkout "$(FORK_REPOSITORY)" fork
	git -C fork remote add upstream "$(UPSTREAM_REPOSITORY)"
	git -C fork fetch upstream "$(UPSTREAM_BRANCH)"
	git -C fork checkout --detach "$(UPSTREAM_REVIEWED_SHA)"
	@echo "fork/ recreated at $(UPSTREAM_REVIEWED_SHA); origin is the author fork, upstream is oscardvs/zoteus"
