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

.PHONY: check check-fast deps lint figures governance terminology chain-dedup normative models progress help upstream-status upstream-checkout

help:
	@echo "make check       — everything: lint, figures, tests"
	@echo "make check-fast  — the tests alone"
	@echo "make deps        — the gate's dependencies are declared, present and used"
	@echo "make lint        — ruff over the harness"
	@echo "make figures     — every figure quoted in the prose still matches its artifact"
	@echo "make governance  — process bounds are stated in GOVERNANCE.md, not in the spec"
	@echo "make terminology — the glossary defines and points; it restates no design number"
	@echo "make progress    — the status page covers every requirement, and its bars match its rows"
	@echo "make chain-dedup — the authority chain is described once, in README.md"
	@echo "make normative   — every R-item declares its RFC 2119 force"
	@echo "make models      — the registry is well formed and nothing else in bench/ names a model"
	@echo "make names       — committed artifacts address a document by key, never by name"
	@echo "make upstream-status   — compare the reviewed SHA with upstream main"
	@echo "make upstream-checkout — recreate fork/ at the reviewed SHA (only if absent)"

check: deps lint figures governance terminology chain-dedup normative models names progress check-fast

check-fast:
	python3 -m pytest tests/ -q

# The preflight, and the only guard that runs before the dependencies it checks
# for. It is first in `check` for the reason ticket 0498 filed it: the gate died
# on `No module named pytest` at its LAST step, after eight guards had printed
# success, and a session reading the tail of that output can take it for green.
# What the gate needs is requirements-check.txt; what a driver needs is
# requirements-drivers.txt; this keeps both true.
deps:
	python3 bench/check_deps.py

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

# The sibling guard, against a different drift. The figure guard keeps a number
# from going stale where it is quoted; this one keeps a process rule from being
# restated where it is not owned. The repository is public and the upstream
# maintainer reads it, so "our governance never enters upstream text" had been a
# rule kept by care since the beginning. Ticket 0053, ratified 2026-08-29.
governance:
	python3 bench/check_governance.py

# The third guard, against the same drift as the figure guard but from the other
# side. That one keeps a quoted number current where the prose quotes it; this
# one keeps the glossary from quoting a number at all, since a definition is the
# most inviting place to leave a second copy of a threshold that nobody will
# remember to update. Default-deny on digits, and a citation beside a number
# does not excuse it. Ticket 0051.
terminology:
	python3 bench/check_terminology.py

# The fourth guard, for a rule rather than a number or a bound. The authority
# chain was described in its own words in each of the five chain documents;
# CLAUDE.md's "one statement per fact" says it belongs in one place. Ticket 0054.
chain-dedup:
	python3 bench/check_chain_dedup.py

# The fifth guard. RFC 2119 only pays if the convention holds: an R-item
# written next year with a lowercase "must" reads exactly like the ones that
# carry force. Two checks, failing in opposite directions — a stray lowercase
# modal inside a contract line, and an R-item with no keyword at all, which a
# lowercase-modal grep structurally cannot see. Ticket 0050.
normative:
	python3 bench/check_normative.py

# The sixth guard, over bench/models.json. The embedder study's candidate field was
# discovered one repository at a time and the discoveries did not survive: a mirror
# ruled out on an unauthenticated 401 publishes the full dtype set. The registry
# holds each of those facts once, with the state it was observed in; this checks that
# it stays well formed and that no driver keeps a second copy of a model name.
# Ticket 0261.
models:
	python3 bench/check_models.py

# The public-repository leak: a measurement of a real library produces artifacts
# about real documents, and this tree is public and permanent. Keys address a
# document; names disclose one. Ruling 2026-08-31, spec/DECISIONS.md.
names:
	python3 bench/check_names.py

# The fourth guard, over spec/README.md. The status page restates nothing —
# every row is a status and an address — so the figure guard has nothing to
# anchor there. What can rot instead is coverage and arithmetic: a requirement
# added to the sheet and never given a row, or a status edited in the table and
# not in the bar above it. Both are silent, and both leave the page looking
# complete, which is worse than no page. Ticket 0300.
progress:
	python3 bench/check_progress.py

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
