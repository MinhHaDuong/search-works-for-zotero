#!/usr/bin/env bash
# Pack the plugin into an .xpi (a zip with manifest.json at its root).
# The package is written OUTSIDE the repository by default (the bench/ guards scan every file
# under bench/ as text, and a zip is not text): $HOME/fulltext-control.xpi, or the path given.
# Install it from Zotero: Tools → Plugins → gear → Install Plugin From File.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:-$HOME/fulltext-control.xpi}"
rm -f "$out"
(cd "$here" && zip -q -X "$out" manifest.json bootstrap.js)
echo "$out ($(stat -c %s "$out") bytes)"
