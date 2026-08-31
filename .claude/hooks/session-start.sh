#!/bin/bash
# Make `make check` runnable in a fresh container, with no hand-installation.
#
# Ticket 0498: twice in two days a remote session opened on a container with
# neither pytest nor numpy, discovered it only at the tail of a long green-looking
# run, and installed both by hand. The declaration files are what a human reads;
# this is what makes the machine's case work without one.
#
# Remote only. A contributor's own machine keeps whatever environment it has —
# `python3 -m pip install -r requirements-check.txt` is the same command, run
# when they choose it.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

echo "session-start: installing the gate's dependencies (requirements-check.txt)"
python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore \
  -r requirements-check.txt

# Confirmation, not a second gate: `make check` runs this guard first anyway, and
# a session should still start if the declaration has drifted.
python3 bench/check_deps.py || echo "session-start: the dependency guard is red; \`make check\` will say why"
