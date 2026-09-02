#!/usr/bin/env bash
# Pack the plugin into an .xpi (a zip with manifest.json at its root) next to this script.
# The .xpi is regenerable and git-ignored; install it from Zotero: Tools → Plugins → gear → Install Plugin From File.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$here/fulltext-control.xpi"
rm -f "$out"
(cd "$here" && zip -q -X "$out" manifest.json bootstrap.js)
echo "$out ($(stat -c %s "$out") bytes)"
