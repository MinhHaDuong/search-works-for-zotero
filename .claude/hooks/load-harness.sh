#!/bin/bash
# Load the Imperial Dragon Harness into a remote container at session start.
#
# The harness (MinhHaDuong/ImperialDragonHarness) is designed to BE `~/.claude`
# on the author's machine. In a remote container it cannot be: `$HOME/.claude`
# is the platform's own directory (plugins/synced, sessions/, skills/synced,
# platform hooks) and clobbering it breaks the session. So the harness is
# *loaded* instead of installed: cloned to a cache, then linked in piece by
# piece, and only where nothing already sits.
#
# Deliberately NOT installed: `settings.shared.json`. Its `env` block hardcodes
# /home/haduong for UV_ENV_FILE, BASH_ENV and the statusline; in this container
# those paths do not exist and BASH_ENV pointing at a missing file breaks every
# subsequent Bash call. Porting it to $HOME is its own change.
#
# Fail-soft by construction: a harness that will not load must never stop a
# session from starting. Every step is guarded and the hook always exits 0.
set -uo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

REPO_URL="https://github.com/MinhHaDuong/ImperialDragonHarness"
CACHE="${HOME}/.cache/imperial-dragon-harness"
DEST="${HOME}/.claude"

if [ ! -d "${CACHE}/.git" ]; then
  echo "harness: cloning the Imperial Dragon Harness"
  rm -rf "${CACHE}"
  if ! GIT_LFS_SKIP_SMUDGE=1 git clone --quiet --depth 1 "${REPO_URL}" "${CACHE}" 2>&1; then
    echo "harness: clone failed — session continues without it"
    exit 0
  fi
fi

# Link, never overwrite: an existing name belongs to the platform or to a
# previous run, and either way it is not ours to replace.
link_all() {
  local src_dir="$1" dst_dir="$2" pattern="$3" kind="$4" n=0
  [ -d "${src_dir}" ] || return 0
  mkdir -p "${dst_dir}" || return 0
  local path name
  for path in "${src_dir}"/${pattern}; do
    [ -e "${path}" ] || continue
    name="$(basename "${path}")"
    [ -e "${dst_dir}/${name}" ] && continue
    ln -s "${path}" "${dst_dir}/${name}" 2>/dev/null && n=$((n + 1))
  done
  echo "harness: ${n} ${kind} linked into ${dst_dir}"
}

link_all "${CACHE}/skills"   "${DEST}/skills"   "*"     "skill(s)"
link_all "${CACHE}/agents"   "${DEST}/agents"   "*.md"  "agent(s)"
link_all "${CACHE}/commands" "${DEST}/commands" "*.md"  "command(s)"

# The rules index is the one piece the harness itself specifies as injected at
# session start; the bodies are read on demand from the path printed below.
if [ -r "${CACHE}/rules/README.md" ]; then
  echo "harness: rule bodies live under ${CACHE}/rules/ — index follows"
  cat "${CACHE}/rules/README.md"
fi

echo "harness: scripts at ${CACHE}/scripts, utilities at ${CACHE}/bin (not on PATH)"
echo "harness: settings.shared.json NOT applied — it hardcodes /home/haduong paths"
exit 0
