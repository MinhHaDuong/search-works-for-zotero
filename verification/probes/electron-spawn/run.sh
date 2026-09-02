#!/usr/bin/env bash
# Ticket 0576, portable arm + positive control.
#
# Order is the point. The POSITIVE CONTROL runs first, under standalone Node, where every
# arm MUST succeed. Only if it does may anything the Electron arm reports be read as a
# finding: a probe that cannot spawn anywhere is measuring its own harness, and its
# negative is indistinguishable from "I could not look".
#
# Usage: run.sh <run-dir>
# Leaves <run-dir>/summary.json plus the raw per-host reports.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="${1:?usage: run.sh <run-dir>}"
mkdir -p "$RUN"

ELECTRON_SPEC="${ELECTRON_SPEC:-electron@latest}"

say() { printf '[run] %s\n' "$*" >&2; }

# Wait for a file to appear, up to N seconds. Returns 1 on timeout rather than aborting,
# because a timeout is itself an observation this probe has to record.
wait_file() {
  local path="$1" secs="$2" i=0
  while [ "$i" -lt "$((secs * 4))" ]; do
    [ -f "$path" ] && return 0
    sleep 0.25
    i=$((i + 1))
  done
  return 1
}

# ---------------------------------------------------------------- positive control (Node)
say "positive control: standalone Node"
rm -f "$RUN"/control-*.json
ZOTEUS_PROBE_HOST=standalone-node \
ZOTEUS_PROBE_OUT="$RUN/control.json" \
ZOTEUS_PROBE_ARMED_FILE="$RUN/control-armed.json" \
ZOTEUS_PROBE_EOF_FILE="$RUN/control-eof.json" \
  node "$HERE/probe-payload.mjs" >"$RUN/control.stdout" 2>"$RUN/control.stderr" &
CONTROL_SUPERVISED=$!

if wait_file "$RUN/control-armed.json" 60; then
  CONTROL_HOST_PID="$(node -e 'process.stdout.write(String(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).hostPid))' "$RUN/control-armed.json")"
  say "control armed; killing host pid $CONTROL_HOST_PID to test stdin EOF at the child"
  kill -KILL "$CONTROL_HOST_PID" 2>/dev/null || true
  if wait_file "$RUN/control-eof.json" 15; then
    say "control: orphan observed stdin EOF"
  else
    say "control: orphan did NOT observe stdin EOF"
  fi
else
  say "control: payload never armed"
fi
wait "$CONTROL_SUPERVISED" 2>/dev/null || true

# ------------------------------------------------------------------------- Electron arm
say "installing $ELECTRON_SPEC into $RUN (this is the only network step)"
cd "$RUN"
[ -f package.json ] || npm init -y >/dev/null 2>&1
npm install --no-audit --no-fund --loglevel=error "$ELECTRON_SPEC" >"$RUN/npm-install.log" 2>&1 || {
  say "electron install FAILED; see $RUN/npm-install.log"
  exit 3
}
ELECTRON_BIN="$RUN/node_modules/.bin/electron"
"$ELECTRON_BIN" --no-sandbox --version >"$RUN/electron-version.txt" 2>&1 || true
say "electron: $(cat "$RUN/electron-version.txt")"

# --no-sandbox is passed on the COMMAND LINE, not by app.commandLine.appendSwitch.
# Chromium's SUID sandbox host runs before any JavaScript does, so a switch appended
# from main.mjs arrives too late: the first attempt here died at
# setuid_sandbox_host.cc:166 with SIGTRAP before the app ever started. This is a
# property of THIS Linux box (kernel.apparmor_restrict_unprivileged_userns=1, the same
# refusal that made `unshare -rn` unusable), not of the host under test.
rm -f "$RUN"/electron-*.json
ZOTEUS_PROBE_OUT="$RUN/electron.json" \
ZOTEUS_PROBE_ARMED_FILE="$RUN/electron-armed.json" \
ZOTEUS_PROBE_EOF_FILE="$RUN/electron-eof.json" \
ZOTEUS_PROBE_HOST_FILE="$RUN/electron-host.json" \
  "$ELECTRON_BIN" --no-sandbox "$HERE/electron-main.mjs" >"$RUN/electron.stdout" 2>"$RUN/electron.stderr" &
ELECTRON_SUPERVISED=$!

EOF_STEP="none"
if wait_file "$RUN/electron-armed.json" 120; then
  MAIN_PID="$(node -e 'try{process.stdout.write(String(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).mainPid))}catch(e){process.stdout.write("")}' "$RUN/electron-host.json")"
  UTIL_PID="$(node -e 'process.stdout.write(String(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).hostPid))' "$RUN/electron-armed.json")"
  say "electron armed; main=$MAIN_PID utility=$UTIL_PID"
  # Kill the APP first. That is the event the topology cares about: the host dying, not one
  # of its processes being singled out. If the orphan's stdin closes from that alone, the
  # UtilityProcess went down with the app.
  [ -n "$MAIN_PID" ] && kill -KILL "$MAIN_PID" 2>/dev/null || true
  if wait_file "$RUN/electron-eof.json" 8; then
    EOF_STEP="app-kill"
  else
    say "no EOF from the app kill; killing the utility process $UTIL_PID directly"
    kill -KILL "$UTIL_PID" 2>/dev/null || true
    if wait_file "$RUN/electron-eof.json" 8; then EOF_STEP="utility-kill"; else EOF_STEP="never"; fi
  fi
else
  say "electron: payload never armed (see $RUN/electron.stderr)"
fi
kill -KILL "$ELECTRON_SUPERVISED" 2>/dev/null || true
wait "$ELECTRON_SUPERVISED" 2>/dev/null || true
pkill -KILL -f 'probe-child.mjs' 2>/dev/null || true

printf '%s' "$EOF_STEP" >"$RUN/electron-eof-step.txt"
say "done; raw artifacts in $RUN"
