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

.PHONY: check check-fast deps lint figures models names progress tickets ticket-logs acceptance-fixtures help upstream-status upstream-checkout upstream-catchup upstream-rebaseline fold-gate

# Where the acceptance layer's arenas live: outside the repository, because the
# residue sweep fills them with a target's derived state and bench/ is scanned
# by the guards above. Override to put them elsewhere.
ACCEPTANCE_ARENA ?= $(HOME)/data/acceptance-arena

# A real run against a real target (not `make acceptance-fixtures`, which only
# drives the in-process stub adapters below and needs none of this) MUST run
# its target process under a dedicated account, never as the operator
# (DECISIONS.md, ratified 2026-09-03; ticket 0625). `bench/acceptance/run.py`
# defaults `--posture account` and refuses (`not-run`, never a fallback) when
# the account below is absent or its sudoers rule does not work — it does not
# create the account itself. A short, copyable recipe, once per machine:
#
#   sudo useradd --create-home --shell /usr/sbin/nologin tester
#   sudo setfacl -R -m u:tester:rX  /path/to/your/Zotero/library
#   sudo setfacl -R -m d:u:tester:rX /path/to/your/Zotero/library
#   sudo install -d -o tester -g tester "$(ACCEPTANCE_ARENA)"
#   echo "operator ALL=(tester) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/acceptance-tester
#
# `tester` gets READ on the library (every target here is read-only against
# it) and WRITE on nothing but the arena. Where the run's own environment is
# itself the boundary instead — a disposable container, a throwaway VM, with
# no second identity within reach — pass `--posture already-isolated`; the
# harness does not probe for this, the operator states it (see
# `bench/acceptance/posture.py`'s module docstring for why no probe is safe).

help:
	@echo "make check       — everything: lint, figures, tests"
	@echo "make check-fast  — the tests alone"
	@echo "make deps        — the gate's dependencies are declared, present and used"
	@echo "make lint        — ruff over the harness"
	@echo "make figures     — every figure quoted in the prose still matches its artifact"
	@echo "make progress    — the status page covers every requirement, and its bars match its rows"
	@echo "make models      — the registry is well formed and nothing else in bench/ names a model"
	@echo "make names       — committed artifacts address a document by key, never by name"
	@echo "make fold-gate   — R19: every token the query side produces is one the index can produce"
	@echo "make tickets     — erg check over the ticket store"
	@echo "make ticket-logs — no log entry is stamped after the commit that wrote it"
	@echo "make acceptance-fixtures — the acceptance layer's fail-controls still fail"
	@echo "make upstream-status   — compare the reviewed SHA with upstream main"
	@echo "make upstream-checkout — recreate fork/ at the reviewed SHA (only if absent)"
	@echo "make upstream-catchup  — QUIET or TOUCHED: did upstream move anything of ours"
	@echo "make upstream-rebaseline — the UPSTREAM block for the current tip, computed, and the recipe"

check: deps lint figures models names progress tickets ticket-logs check-fast

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

# The guard over bench/models.json. The embedder study's candidate field was
# discovered one repository at a time and the discoveries did not survive: a mirror
# ruled out on an unauthenticated 401 publishes the full dtype set. The registry
# holds each of those facts once, with the state it was observed in; this checks that
# it stays well formed and that no driver keeps a second copy of a model name.
# Ticket 0261.
models:
	python3 bench/check_models.py

# The public-repository leak: a measurement of a real library produces artifacts
# about real documents, and this tree is public and permanent. Keys address a
# document; names disclose one. Ruling 2026-08-31, DECISIONS.md.
names:
	python3 bench/check_names.py

# The guard over README.md's standing report. The status page restates nothing —
# every row is a status and an address — so the figure guard has nothing to
# anchor there. What can rot instead is coverage and arithmetic: a requirement
# added to the sheet and never given a row, or a status edited in the table and
# not in the bar above it. Both are silent, and both leave the page looking
# complete, which is worse than no page. Ticket 0300.
progress:
	python3 bench/check_progress.py

# AGENTS.md declares "erg check must pass" beside the guards, yet the gate ran
# fully green on a tree where it was red (a closed ticket outside closed/,
# t0507, 2026-08-31). The declared-mandatory check joins the target that makes
# the declaration true.
tickets:
	./tickets/erg check tickets/

# The other half of the ticket store: erg checks that a log entry is well
# formed, not that its time is real. Six tickets filed by one commit each
# claimed a stamp four hours ahead of it — `erg log` reads the clock, a typed
# stamp does not. Rule ruled 2026-09-01 (DECISIONS.md), ticket 0571. It is
# deliberately weaker than monotonicity: parallel sessions merge into one log,
# so out-of-order arrival is honest and only a time that has not happened is a
# defect. Needs real history — the guard says so on a shallow checkout.
ticket-logs:
	python3 bench/check_ticket_logs.py

# The acceptance layer's own positive control, and it reads backwards on
# purpose: the fail-controls MUST fail. A fixture built to break an assertion
# that comes back green means the assertion has stopped firing, and nothing else
# in this repository can see that — a layer whose checks have quietly gone inert
# passes every target it is pointed at. The driver exits nonzero when any
# assertion was never seen red, which is the state this target exists to catch.
#
# Deliberately NOT in `check`: it spawns sandboxed subprocesses and a tracer, so
# it is an integration gate rather than part of a 9-second loop. `make check`
# still covers the layer's logic through tests/test_acceptance_*.py.
#
# not-offered and not-run never redden this target. They are printed and counted
# apart from green instead, per ticket 0578's Action 6: a gate that cannot look
# reports that it could not look.
acceptance-fixtures:
	python3 bench/acceptance/run.py --fixtures \
	  --arena "$(ACCEPTANCE_ARENA)/fixtures" \
	  --output bench/results/smoke-1.12.0/acceptance-fixtures.json
# R19's gate, SPEC.md §5.2.8. Deliberately NOT a `check` prerequisite, for two reasons
# that would each be enough on their own. It reads a BUILT checkout of the tree under test,
# and `check` has to stay green on a machine that has none — a prerequisite that cannot look
# would have to be waived, and a waiver is a green that means "we decided not to look".
# And against stock at the reviewed SHA it is currently RED, for a real finding recorded in
# bench/results/0578-fold-sweep/codepoints.json: wiring a known-red gate into the default
# gate either paints `check` permanently red, which retires it, or forces that same waiver.
# It also rewrites a committed artifact, which a nine-second pre-commit gate should not do.
# The discipline `check` does carry is in tests/test_fold_sweep.py, which needs no checkout.
#
# Exit codes: 0 agreed, 1 misses recorded, 2 usage, 3 could not look (NOT-RUN, never green).
FOLD_TREE ?= fork
FOLD_OUTPUT ?= bench/results/0578-fold-sweep/codepoints.json

fold-gate:
	node bench/fold_sweep.mjs --fork "$(FOLD_TREE)" --output "$(FOLD_OUTPUT)"

upstream-status:
	@set -eu; \
	remote="$$(git ls-remote "$(UPSTREAM_REPOSITORY)" "refs/heads/$(UPSTREAM_BRANCH)" | awk 'NR == 1 { print $$1 }')"; \
	test -n "$$remote" || { echo "Could not resolve upstream $(UPSTREAM_BRANCH)" >&2; exit 2; }; \
	echo "reviewed  $(UPSTREAM_REVIEWED_SHA) ($(UPSTREAM_REVIEWED_VERSION), $(UPSTREAM_REVIEWED_DATE))"; \
	echo "upstream  $$remote ($(UPSTREAM_BRANCH))"; \
	if test -d fork/.git; then echo "checkout  $$(git -C fork rev-parse HEAD)"; else echo "checkout  absent"; fi; \
	test "$$remote" = "$(UPSTREAM_REVIEWED_SHA)" || { echo "STALE: upstream has moved; review before changing UPSTREAM" >&2; exit 1; }; \
	echo "OK: reviewed baseline is current"

# The other half of upstream-status: not THAT it moved, but what moved. Every
# step it prints was done by hand on 2026-08-31 and none of it was a judgement.
#
# Its verdict is computed from a path list, so the only way to know it can still
# say TOUCHED is to point it at a range where it must. The recorded positive
# control is a real upstream release in which the watched surface as it stood
# before 2026-09-03 was entirely empty while eighteen files changed outside it:
#
#     python3 bench/upstream_catchup.py --base v1.7.2 --head v1.7.3
#
# Run that before trusting a QUIET. Ticket 0622.
upstream-catchup:
	python3 bench/upstream_catchup.py

# The mechanical half of a re-baseline, which was hand work all three times it
# was done: the UPSTREAM block for the current tip with the SHA, the last
# release contained in the tree, the date and the index schema generation all
# READ rather than typed, the tag gap if the tip is past a release, and the list
# of everything else a re-baseline must touch.
#
# It is a recipe and not a gate, and it says so in its own output. What it
# cannot do is check that a row was re-read; the only thing that does is
# `check_progress`, which fails until the page names the release UPSTREAM does.
#
# It earned its place the day it was written: it computed a tag gap of four
# where the hand-written figure in four documents said three.
upstream-rebaseline:
	python3 bench/upstream_catchup.py --rebaseline

upstream-checkout:
	@test ! -e fork || { echo "Refusing to overwrite existing fork/" >&2; exit 1; }
	git clone --no-checkout "$(FORK_REPOSITORY)" fork
	git -C fork remote add upstream "$(UPSTREAM_REPOSITORY)"
	git -C fork fetch upstream "$(UPSTREAM_BRANCH)"
	git -C fork checkout --detach "$(UPSTREAM_REVIEWED_SHA)"
	@echo "fork/ recreated at $(UPSTREAM_REVIEWED_SHA); origin is the author fork, upstream is oscardvs/zoteus"
