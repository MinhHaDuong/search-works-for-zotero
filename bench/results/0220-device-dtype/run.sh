#!/usr/bin/env bash
# Reproduce the device/dtype probe matrix. One process per variant; see
# verification/probes/device-auto-probe.mjs for why.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PROBE="$HERE/../../../verification/probes/device-auto-probe.mjs"
PKG_ROOT="${PKG_ROOT:?set PKG_ROOT to a directory whose node_modules has @huggingface/transformers}"
CACHE_DIR="${CACHE_DIR:-}"

run() {
  local label="$1"
  shift
  local args=(--pkg-root "$PKG_ROOT" --label "$label")
  if [ -n "$CACHE_DIR" ]; then args+=(--cache-dir "$CACHE_DIR"); fi
  echo "--- $label"
  node "$PROBE" "${args[@]}" "$@" >"$HERE/$label.json" 2>"$HERE/$label.err" || true
}

# The second install shape, run separately because it needs its own PKG_ROOT:
#   npm install @huggingface/transformers@4.2.0 --onnxruntime-node-install=skip
#   PKG_ROOT=<that dir> ... run skipinstall-device-auto --device auto
# On linux/x64 the default install downloads the CUDA execution provider (it is the one
# platform whose install manifest requires cuda12); the skip flag is how a user opts out.
# `device: 'auto'` fails either way, which is why the finding is not about that download.

run no-options
run device-auto --device auto
run device-cpu --device cpu
run device-auto-q8 --device auto --dtype q8
run dtype-q8 --dtype q8
run dtype-fp16 --dtype fp16
run dtype-q7 --dtype q7
