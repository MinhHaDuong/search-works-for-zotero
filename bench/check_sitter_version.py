#!/usr/bin/env python3
"""No two sitter payloads may answer to one version. Ticket 0688.

The XPI is hand-delivered to the author, so there is no registry, no release
feed and no installer to notice that the file he just dropped in is a different
plugin from the one already carrying that number. Zotero keys its add-on record
on the manifest `version`; two builds sharing one are indistinguishable to it,
to the author's `extensions.json`, and to any bug report either of them
produces. The sitter has already shipped several payloads under `2.2.0`.

WHAT IS COMPARED, and it is anchored at the tip rather than swept over the
whole history:

1. **No reuse.** No earlier commit carries the working tree's version over a
   DIFFERENT payload — the three files `build_sdt_sitter.DELIVERED` names,
   hashed together. Change one byte of `bootstrap.js` without bumping and this
   fires; bump and it clears.

2. **Release agreement, once a release exists (ticket 0764).** `update.json`
   ships exactly one entry for the working tree's version. Before a tag is cut
   that entry carries neither `tag` nor `update_link` — the steady state
   ticket 0727 put in place, and this guard is silent on it, same as before
   this ticket. One entry means the TIP and nothing else: builds carried by
   hand from a branch (ticket 0680's, and every payload
   `bench/sitter_volume_experiment.py` installs) are deliberately unlisted,
   because with no release there is no URL an entry for them could name —
   a cumulative list would enumerate an unreachable history. Ruled 2026-09-12
   on ticket 0776, and it is a statement about today rather than for ever: the
   question becomes real when a release does. Once a release IS cut, the entry gains both, and from then on
   they must agree with each other and with reality: `tag` must resolve to a
   revision whose OWN `manifest.json` carries this same version, and
   `update_link` must resolve to something. A HALF-FILLED entry — one key
   present, not the other — is always a finding: a release that names a tag
   but not where to fetch it, or a link with nothing anchoring which commit it
   came from, is not the two-key state this repository ships once a release
   exists, it is one someone left mid-edit.

3. **No two OPEN branches, either (ticket 0779).** No other open pull request's
   head carries the working tree's version over a different payload. Rules 1
   and 2 are anchored in this checkout, so a number a parallel lane has already
   spent is invisible to them: two lanes both take it, both pass on their own
   branch, and the collision comes into existence at the second merge — by
   which time both payloads are in history, which is the one state this
   docstring calls unfixable below. Ticket 0771 avoided it by hand, by reading
   an open pull request's diff before choosing a number. That is not a guard.
   The condition is the same DIFFERENT-payload one rule 1 uses, and it has to
   be: the ordinary state of two open pull requests here is that neither
   touched the plugin, so both carry main's version over main's payload, and a
   rule firing on that would redden every lane at once. A head that is already
   an ancestor of HEAD — a merged pull request, or the lane's own — is left to
   rule 1, which reads it directly, rather than reported twice. A finding
   carries a suggested version: the first one above the working tree's that no
   claim read has taken, history and open pull requests alike. Deliberately not
   one past the highest number anywhere — that would climb back into the
   abandoned `2.x` scheme this payload's history still carries and undo the
   2026-09-06 reset, which is what the positive control caught it doing.

THE NO-REGRESSION CHECK WAS REMOVED 2026-09-06 (author's ruling, this ticket's
DECISIONS.md entry): the sitter has never been released — no auto-update
channel, no user-facing install outside the author's own hand-delivered
XPI — so the numbering scheme itself was reset from `2.x.y` to `0.2.11`,
which is numerically a decrease against everything already in history. A
"no regression" rule protects against a number silently going backwards by
accident; it has nothing useful to say about a deliberate, once-only, ruled
reset, and firing on one anyway would only block it. What still matters, and
is unaffected by any scheme reset, is that no two DIFFERENT payloads ever
answer to the same number — that is rule 1 above, and it is unconditional.

IT BITES INSIDE A BRANCH TOO, and that is intended rather than tolerated. An
unbumped payload change fires against the branch's own previous commit, not
only against `main`. In another workshop that would be nagging; here it is the
case that matters, because this plugin is hand-delivered — ticket 0680 carried
an XPI to the author's home directory straight from a branch. A commit on a
branch is a payload someone can install, so it needs its own number.

WHERE IT IS DELIBERATELY BLIND, because a guard's blind spot is worth more
written down than discovered. It says nothing about a collision between two
purely historical versions — `2.2.0`'s several payloads are recorded and
unfixable, and a guard that reddened over them would be a guard nobody could
make green, which is a guard that gets deleted. Anchoring at the tip is what
makes it both true today and binding tomorrow: the very next unbumped payload
change is a collision with the tip's own version.

It needs real history to say anything, and every way of having none is a
NOT-RUN rather than a green — a gate that cannot look must never answer as
though it had. Four are covered, and they were found one at a time, each by a
control rather than by reading the code:

* **not a git tree** — nothing to compare against;
* **a shallow clone** — its boundary hides the earlier payload. Detected with
  `--is-shallow-repository`, NOT the `shallow` marker under
  `--absolute-git-dir`: that marker lives in the common git dir, so from a
  linked worktree, which is how every lane here works, the marker check looks
  where it never is;
* **a grafted history** — `git replace --graft` truncates the visible ancestry
  and sets no marker at all, so the shallow probe answers false;
* **no commit touching the payload path** — a fresh checkout, or a rename to a
  path whose history starts empty. Zero revisions compared is no comparison;
* **a payload that has moved** — `git log <path>` does not follow a rename
  across a directory, and `<sha>:<newpath>` does not exist on a commit older
  than the move. Ticket 0697 promoted the sitter out of `bench/`, so both the
  log pathspec and the blob reads name every historical home (`HOMES`), newest
  first. Half the fix is not a fix: with only the pathspec widened, the
  pre-move commits are listed and then skipped as manifest-less, and the count
  comes back the same as if they had never been listed;
* **a partial clone** — commits present, blobs absent. `git show` fails there
  exactly as it does on a path that never existed, and only the tree can say
  which, so the tree is asked;
* **a redirected environment** — `GIT_DIR` and its relatives answer about a
  different repository than `--root` names, so they are stripped rather than
  detected. There is no case where this guard wants one tree's files read
  against another tree's log.

Rule 3 adds a FIFTH way of being unable to look, and it is the only one that
does not redden the gate, which is a deliberate asymmetry rather than a
softening. The four above are ways of having no history, and history is what
rules 1 and 2 read, so a gate that cannot read it has nothing to say and says
nothing by exiting non-zero. An unreachable forge leaves rules 1 and 2 fully
evaluated: a lane offline still gets both, and blocking its commit over a
network it does not have is how this rule would get waived out of `make check`
and stop running at all. So the forge leg reports on its own line — NOT-RUN
with the reason, at error level, beside a green exit — and the closing OK
sentence never claims anything about open pull requests. The all-clear and the
could-not-look are different sentences, which is the whole of what "never
green" can mean for a rule the gate does not exit on. A PARTIAL enumeration
reads NOT-RUN too, while still reporting whatever it did find: a finding is
positive evidence and stands alone, but the absence of further findings is not
claimed by a sweep that did not finish.

WHERE THE FORGE IS TALKED TO, and it is one place on purpose. Rule 3's every
forge-specific act is a `subprocess` call to ONE replaceable command, named by
`FORGE_COMMAND` and overridable with `SITTER_FORGE_COMMAND` — a command, not an
imported client, so a workshop on another forge drops in its own executable and
edits nothing in this file, and so the guard's own tests can substitute a
stand-in and stay offline. The default is `bench/forge_open_prs.py`, which is
the only file in the repository that knows the forge is GitHub. That command's
docstring owns the protocol; what matters here is its shape, because the shape
is the fix: it answers about ONE pull request per invocation, so a caller cannot
express the one-shot list-plus-filter that `tickets/AGENTS.md` records as the
trap (`gh pr list --json files` does not populate `files`, so its empty answer
is the same output whatever the pull requests contain). A check whose all-clear
cannot be told from "I could not look" is not a check, and the remedy lives in
the protocol rather than in the discipline of whoever calls it.

NOTHING RUNS THIS ON A PUSH. This repository has no `.github/workflows/`, so
there is no continuous integration here and no gate between a branch and
`main` except a lane running `make check` and a coordinator reading what it
quoted (`AGENTS.md` § Merge authority says so explicitly: "The review this
repository has instead of continuous integration is the merge itself"). Rule 3
is therefore worth exactly what that habit is worth, and this comment is here
instead of a reassuring one about CI coverage that does not exist.

What it still cannot see: a rewritten history that keeps the same shape (a
filter-branch that edited an old manifest in place), and a payload delivered
outside this repository. Both are outside what a path's own log can evidence.
Rule 3 adds two of its own: a payload on a branch nobody has opened a pull
request for, and one on a pull request opened between this run and the merge.
The second is why the check belongs at the merge gate and not only at the
moment a version is chosen — the same reason `tickets/AGENTS.md` gives for
re-running its ticket-ID seat check before merging.

    python3 bench/check_sitter_version.py [--root .]
"""

import argparse
import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from build_sdt_sitter import DELIVERED, SOURCE

#: Where the payload lives now, relative to the repository root. Imported from
#: the packager rather than restated: the file that builds the XPI is the one
#: that decides which directory is the payload, and two copies of that answer
#: would let a future move be packaged from one place and gated at another.
SITTER = SOURCE

#: Every directory the payload has ever lived in, newest first. History is read
#: through all of them, because a rename across a directory is invisible to both
#: `git log <path>` and `<sha>:<path>`: the first reports a history that begins
#: at the move, the second fails on every commit older than it. A guard reading
#: only `SITTER` after ticket 0697's promotion would have compared the working
#: tree against a single revision and called that clean. Old homes are appended
#: here and never removed — a version reused before a move is reused.
HOMES = (SITTER, "bench/sdt-sitter")

#: Environment that redirects git away from `--root`. Inherited from whoever ran
#: the gate, and every one of these silently answers the question about a
#: DIFFERENT repository — `--root` names the working tree to read and the
#: environment quietly names the history, so the guard reported OK about a
#: repository it had not looked at. Stripped rather than detected: there is no
#: case where this guard wants to read one tree's files against another's log.
REDIRECTING = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
               "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
               "GIT_CEILING_DIRECTORIES", "GIT_NAMESPACE")

#: The command rule 3 asks about open pull requests, relative to `--root`, and
#: the only forge-specific thing this file names. Its own docstring owns the
#: protocol. Overridable with the environment variable below, which is how the
#: test suite drives rule 3 without a network and how a workshop on another
#: forge points the rule at its own reader.
FORGE_COMMAND = "bench/forge_open_prs.py"
FORGE_ENV = "SITTER_FORGE_COMMAND"

#: The forge command's exit code for "that head does not carry this path" — an
#: absence, as against any other non-zero exit, which means it could not look.
#: Two nothings, and conflating them is the defect ticket 0779 exists for.
FORGE_ABSENT = 3

log = logging.getLogger("check_sitter_version")


class Unreadable(Exception):
    """A blob the tree names and the repository cannot produce.

    A partial (blobless) clone has the commits and not their contents. `git
    show` fails on both that and a path which never existed, and only one of
    those is a payload that was never there — conflating them turned a history
    the guard could not read into a history with nothing in it.
    """


class ForgeUnreadable(Exception):
    """Rule 3 could not look, which is never rule 1's or rule 2's problem.

    Kept apart from `Unreadable` precisely because the two answer differently:
    a history this checkout cannot read leaves the whole guard with nothing to
    say, while a forge it cannot reach leaves rules 1 and 2 untouched and only
    rule 3 unrun. One exception type for both would have made an offline lane's
    `make check` red over a rule that is not the reason it runs.
    """


def parse(version: str) -> tuple[int, ...]:
    """`"2.10.0"` → `(2, 10, 0)`. A dotted version sorts as numbers, not as text.

    String equality calls `"2.03.0"` and `"2.3.0"` two different versions;
    numerically they are one, and the reuse check below needs to see that to
    catch a changed payload hiding behind a reformatted number. A component
    that is not an integer is a manifest this guard cannot order, and it says
    so rather than guessing.
    """
    return tuple(int(part) for part in version.split("."))


def payload(read) -> str | None:
    """One digest over every delivered file, or None if the manifest is not there.

    `read(name)` returns the file's bytes or None. A revision missing the
    manifest predates the plugin (or removed it); it carries no version and is
    not compared. A revision missing some OTHER delivered file is compared
    anyway, with that file's absence folded into the digest — a payload that
    lost a file is a different payload.
    """
    manifest = read("manifest.json")
    if manifest is None:
        return None
    digest = hashlib.sha256()
    for name in DELIVERED:
        content = read(name)
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00" if content is None else b"\x01")
        digest.update(content or b"")
    return digest.hexdigest()


def version_of(read) -> str | None:
    """The manifest `version` at one revision; None if unreadable rather than absent."""
    manifest = read("manifest.json")
    if manifest is None:
        return None
    try:
        value = json.loads(manifest.decode("utf-8")).get("version")
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, str) else None


def addon_id_of(read) -> str | None:
    """`applications.zotero.id`, read rather than restated, so one place names it."""
    manifest = read("manifest.json")
    if manifest is None:
        return None
    try:
        return json.loads(manifest.decode("utf-8"))["applications"]["zotero"]["id"]
    except (ValueError, UnicodeDecodeError, KeyError, TypeError):
        return None


def update_entry(update_json: dict, addon_id: str, version: str) -> dict | None:
    """The `update.json` entry for `version`, or None if it names no such entry
    exactly once. Two entries claiming the same shipped version is exactly as
    much a collision as zero: either way there is no single answer to "what
    does update.json say about this version".
    """
    updates = update_json.get("addons", {}).get(addon_id, {}).get("updates", [])
    matches = [entry for entry in updates
              if isinstance(entry, dict) and entry.get("version") == version]
    return matches[0] if len(matches) == 1 else None


def asset_exists(url: str, timeout: float = 10.0) -> bool:
    """Whether `url` resolves to something, without downloading it when the scheme allows a HEAD.

    A `file://` URL — what this guard's own tests use, to check the logic
    without a live network dependency — has no HEAD verb and raises
    `URLError` for one, so a plain open is the fallback; it is what both a
    real GitHub release asset and a local test fixture answer. Any failure —
    a 404, a refused connection, an unresolvable host, a missing file — reads
    as "does not exist"; nothing here needs to distinguish why.
    """
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"),
                                    timeout=timeout):
            return True
    except (urllib.error.URLError, ValueError):
        pass
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except (urllib.error.URLError, ValueError, OSError):
        return False


def check_release(root: Path, version: str, addon_id: str) -> list[str]:
    """`update.json`'s own release-entry agreement — see the module docstring's item 2.

    Silent when `update.json` is absent: that is a different guard's concern
    (this one has never asserted the file's mere existence, before or after
    this ticket), and every payload-reuse fixture in this repository's test
    suite is a bare `manifest.json`/`bootstrap.js`/`scheduler.js` triple with
    no `update.json` beside it — making absence a finding here would redden
    every one of them over a file this function was never asked to require.
    """
    path = root / SITTER / "update.json"
    if not path.is_file():
        return []
    try:
        update_json = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError, OSError) as error:
        return [f"{path} is present but unreadable as JSON: {error}"]
    entry = update_entry(update_json, addon_id, version)
    if entry is None:
        return [f"{path} names no single update entry for version {version} under {addon_id} "
                "(zero, or more than one)"]
    tag, link = entry.get("tag"), entry.get("update_link")
    if tag is None and link is None:
        return []  # the pre-release steady state ticket 0727 put in place
    if tag is None or link is None:
        missing = "tag" if link is not None else "update_link"
        return [f"{path}'s {version} entry carries {'update_link' if link else 'tag'} but no "
                f"{missing} — a release entry needs both or neither"]
    findings = []
    tagged_version = version_of(commit_reader(root, tag))
    if tagged_version != version:
        findings.append(f"{path}'s tag {tag!r} " +
                         (f"ships manifest version {tagged_version!r}, not {version!r} as "
                          "update.json claims" if tagged_version is not None
                          else "does not resolve, or carries no readable manifest.json"))
    if not asset_exists(link):
        findings.append(f"{path}'s update_link {link!r} does not resolve to anything")
    return findings


def environment() -> dict[str, str]:
    """This process's environment with the git redirections stripped.

    Shared by the git calls and the forge command, for one reason in both
    cases: each is asked a question about the repository `--root` names, and an
    inherited `GIT_DIR` answers it about a different one. The forge command
    resolves the repository's own remote, so it is redirectable exactly as the
    log reads were.
    """
    return {name: value for name, value in os.environ.items() if name not in REDIRECTING}


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    cleaned = environment()
    # A promisor remote would otherwise fetch a missing blob mid-gate, turning
    # the partial-clone case into a network call instead of the NOT-RUN below.
    cleaned["GIT_NO_LAZY_FETCH"] = "1"
    return subprocess.run(["git", *arguments], cwd=root, capture_output=True, env=cleaned)


def forge(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    """Ask the forge one question. # harness-extension-point

    THE ONLY forge-specific call in this file, and the whole of what another
    workshop replaces: point `SITTER_FORGE_COMMAND` at an executable of your
    own, or ship a different `bench/forge_open_prs.py`, and rule 3 works on any
    forge without a line of this guard changing. A command rather than an
    imported client for three reasons, and each would be enough: an MCP or REST
    client would put a forge's vocabulary inside the guard, which is what makes
    a port a rewrite; a command can be swapped by environment variable, which
    is how the test suite exercises rule 3 offline and how the positive control
    for it is run against real forge data; and a command's exit code is a
    contract narrow enough to be got right, where an exception hierarchy
    crossing a library boundary is not.

    The protocol is the command's own docstring. Its shape is load-bearing and
    is repeated here because a future edit could quietly break it: every form
    answers about at most ONE pull request, so no caller can ask a question
    whose empty answer might mean either "nothing matched" or "I could not
    look". `tickets/AGENTS.md` names that trap in its GitHub-CLI spelling; this
    is the same trap and the protocol is the fix.
    """
    command = shlex.split(os.environ.get(FORGE_ENV, "")) or \
        [sys.executable, str(Path(__file__).resolve().parents[1] / FORGE_COMMAND)]
    try:
        return subprocess.run([*command, *arguments], cwd=root, capture_output=True,
                              env=environment(), timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise ForgeUnreadable(f"the forge command {command[0]!r} could not be run: {error}") \
            from error


def answered(root: Path, *arguments: str) -> bytes:
    """One forge answer, with every non-zero exit turned into `ForgeUnreadable`.

    `FORGE_ABSENT` is not handled here: only the caller reading a payload path
    knows that "this head has no such file" is a fact about the payload rather
    than about the reader, so that caller checks the code itself.
    """
    answer = forge(root, *arguments)
    if answer.returncode != 0:
        reason = answer.stderr.decode("utf-8", "replace").strip() or \
            f"it exited {answer.returncode} without saying why"
        raise ForgeUnreadable(reason)
    return answer.stdout


def open_pull_requests(root: Path) -> list[str]:
    """Every open pull request's number. Empty only as a positive claim.

    The command exits non-zero rather than printing nothing when it could not
    look, so an empty list here really does mean a forge with no open pull
    requests — which is the one distinction this rule stands or falls on.
    """
    return answered(root).decode("utf-8", "replace").split()


def pull_request_reader(root: Path, number: str):
    """Read a delivered file at one open pull request's head.

    Only `SITTER` is tried, not every entry in `HOMES`: a pull request open
    today is not older than the last rename, and a head that genuinely carries
    no manifest is an absence rule 3 has nothing to say about either way.
    Answers are memoised because `payload()` and `version_of()` each read the
    manifest and every read is a request.
    """
    cache: dict[str, bytes | None] = {}

    def read(name: str) -> bytes | None:
        if name not in cache:
            answer = forge(root, number, f"{SITTER}/{name}")
            if answer.returncode == FORGE_ABSENT:
                cache[name] = None
            elif answer.returncode != 0:
                raise ForgeUnreadable(
                    answer.stderr.decode("utf-8", "replace").strip() or
                    f"pull request {number} exited {answer.returncode} without saying why")
            else:
                cache[name] = answer.stdout
        return cache[name]
    return read


def in_our_history(root: Path, sha: str) -> bool:
    """Whether `sha` is already an ancestor of HEAD, so rule 1 reads it directly.

    True for a merged pull request and for the running lane's own, which are
    the two heads rule 3 must stay quiet about — the first because reporting it
    would double-report what rule 1 already says, the second because every lane
    would otherwise redden against itself. `--is-ancestor` answers 1 for "no"
    and 128 for an object this clone does not have, and only 0 is a yes; a sha
    that is not here is a head on a branch we have not fetched, which is
    exactly the case rule 3 is for.
    """
    return git(root, "merge-base", "--is-ancestor", sha, "HEAD").returncode == 0


def next_free(version: str, claimed: list[str]) -> str:
    """The first version above the working tree's that nobody has claimed yet.

    Stepping up from the CURRENT version rather than to one past the highest
    number anywhere, which the first draft of this did and which the positive
    control caught: this payload's history still carries the abandoned `2.x`
    scheme the author reset away from on 2026-09-06, so "one past the maximum"
    suggested `2.11.2` and would have quietly undone the reset. A suggestion
    has to stay inside the scheme in force and merely step over what is taken —
    which is also exactly what ticket 0771 did by hand when it read an open
    pull request's diff and took the number after it.

    It steps over every claim read, this checkout's history and the open pull
    requests alike, so the lane is not handed a second collision. Versions this
    guard cannot order are dropped rather than guessed at. Terminates: each
    turn of the loop either answers or consumes one of a finite set of claims.
    """
    taken = set()
    for other in claimed:
        try:
            taken.add(parse(other))
        except ValueError:
            continue
    candidate = list(parse(version))
    while True:
        candidate[-1] += 1
        if tuple(candidate) not in taken:
            return ".".join(str(part) for part in candidate)


def check_open_branches(root: Path, version: str, digest: str | None,
                        seen: list[str]) -> tuple[list[str], int, str | None]:
    """Rule 3: findings, how many pull-request heads were read, and why not more.

    The third element is None when the enumeration finished, and a NOT-RUN
    reason otherwise. Findings and a reason can both be non-empty: a collision
    found is a fact, and a sweep cut short simply does not claim the rest was
    clean.
    """
    try:
        numbers = open_pull_requests(root)
    except ForgeUnreadable as error:
        return [], 0, str(error)
    findings, claims, read = [], list(seen), 0
    # `done` counts pull requests the loop got through, which is what the
    # NOT-RUN reason below has to report: `read` counts heads whose payload was
    # actually fetched, and the two differ by the ones left to rule 1, so
    # quoting `read` there would overstate how much of the sweep was missing.
    for done, number in enumerate(numbers):
        try:
            head = answered(root, number).decode("utf-8", "replace").strip()
            if not head:
                raise ForgeUnreadable(f"pull request {number} named no head commit")
            if in_our_history(root, head):
                continue
            reader = pull_request_reader(root, number)
            claimed = version_of(reader)
            read += 1
            if claimed is None:
                continue
            claims.append(claimed)
            if parse(claimed) == parse(version) and payload(reader) != digest:
                findings.append(
                    f"open pull request {number} (head {head[:12]}) already claims version "
                    f"{version} for a DIFFERENT payload. Whichever of the two merges second "
                    "puts a second payload under one number, and history cannot be "
                    "un-shipped: bump the manifest version clear of every claim.")
        except ValueError:
            # A version at that head this guard cannot order. Not this tree's
            # defect and not rule 3's business — rule 1 says it about our own
            # manifest, where it is actionable.
            continue
        except ForgeUnreadable as error:
            return findings, read, (
                f"{error} — the open pull requests were enumerated and then "
                f"{len(numbers) - done} of {len(numbers)} were left unread, so whatever is "
                "reported below stands and nothing at all is claimed about the rest")
    if findings:
        findings.append("the first version above this one that no claim read has taken: "
                        f"{next_free(version, claims)}")
    return findings, read, None


def worktree_reader(root: Path):
    def read(name: str) -> bytes | None:
        path = root / SITTER / name
        return path.read_bytes() if path.is_file() else None
    return read


def commit_reader(root: Path, sha: str):
    """Read a delivered file at one revision, from whichever home held it then.

    `HOMES` is tried newest first, so a commit that carries both — the rename
    itself — is read at the new path. A revision predating a move has nothing
    at the new path and everything at the old one, and only trying both keeps
    it comparable instead of silently manifest-less.
    """
    def read(name: str) -> bytes | None:
        unreadable = None
        for home in HOMES:
            address = f"{sha}:{home}/{name}"
            shown = git(root, "show", address)
            if shown.returncode == 0:
                return shown.stdout
            # `git show` failed. The tree says which of the two reasons it was,
            # and it can say so without the blob: a name the tree lists is a
            # payload that exists and could not be produced, which is a gap in
            # the clone rather than a file that was never committed. Held, not
            # raised, until every home has been tried: an older home the clone
            # cannot produce must not mask a newer one it can.
            listed = git(root, "ls-tree", "--name-only", sha, "--", f"{home}/{name}")
            if listed.returncode == 0 and listed.stdout.strip():
                unreadable = f"{address} is listed by the tree but its object is not here"
        if unreadable is not None:
            raise Unreadable(unreadable)
        return None
    return read


def history(root: Path) -> list[str]:
    """Every commit that touched the payload at any of its homes, newest first."""
    listed = git(root, "log", "--format=%H", "--", *HOMES)
    return listed.stdout.decode("utf-8", "replace").split()


def run(root: Path) -> tuple[list[str], str, int, tuple[list[str], int, str | None]]:
    """Findings, the working tree's version, how many revisions were read, and
    rule 3's own verdict — kept separate because it is the one leg whose
    inability to look does not redden the gate."""
    current_version = version_of(worktree_reader(root))
    if current_version is None:
        return ([f"{root / SITTER}/manifest.json is absent or carries no string version"],
                "", 0, ([], 0, "the working tree carries no version to compare against"))
    current = parse(current_version)
    current_payload = payload(worktree_reader(root))
    addon_id = addon_id_of(worktree_reader(root))
    findings = [f"{root / SITTER}/manifest.json carries no readable applications.zotero.id"] \
        if addon_id is None else check_release(root, current_version, addon_id)
    read, seen = 0, []
    for sha in history(root):
        reader = commit_reader(root, sha)
        was = version_of(reader)
        if was is None:
            continue
        read += 1
        seen.append(was)
        # Numerically, not as text: `"2.03.0"` and `"2.3.0"` are one version to
        # any dotted-number comparator, Zotero's included; string equality
        # calls them two, so a leading zero would otherwise slip a changed
        # payload past this check.
        if parse(was) == current and payload(reader) != current_payload:
            findings.append(
                f"{sha[:12]} already shipped a DIFFERENT payload under version "
                f"{current_version}. Bump the manifest version: two builds sharing "
                "one number are indistinguishable in the author's extensions.json.")
    cross = check_open_branches(root, current_version, current_payload, seen)
    return findings, current_version, read, cross


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="repository root to check (default: the working directory)")
    root = parser.parse_args().root.resolve()

    if not (root / SITTER / "manifest.json").is_file():
        log.error("FAIL: no %s/manifest.json under %s", SITTER, root)
        return 1
    if git(root, "rev-parse", "--git-dir").returncode:
        log.error("NOT-RUN: %s is not a git checkout, so no earlier payload can be read. "
                  "This guard compares the working tree against history and has none.", root)
        return 1
    # `--is-shallow-repository`, and not the `shallow` marker under
    # `--absolute-git-dir`: that marker lives in the COMMON git dir, so a linked
    # worktree — which is how every lane in this repository works — looks for it
    # in its own per-worktree dir, never finds it, and answers green while blind.
    # Probed three ways (full clone, shallow primary, shallow linked worktree);
    # only this form is right in all three.
    if git(root, "rev-parse", "--is-shallow-repository").stdout.decode().strip() == "true":
        log.error("NOT-RUN: this checkout is shallow, so a payload older than its boundary "
                  "is invisible and a reused version would read as unused. Run "
                  "`git fetch --unshallow` before trusting a verdict here.")
        return 1
    # A grafted history is a truncated one that sets no marker: `git replace
    # --graft` cuts the visible ancestry while `--is-shallow-repository` still
    # answers false. Reproduced — 17 real revisions against 3 after grafting,
    # same tip, opposite truth, and the same OK sentence either way. A replace
    # ref in a checkout being gated is not a state to reason under.
    if git(root, "for-each-ref", "--format=%(refname)", "refs/replace/").stdout.strip():
        log.error("NOT-RUN: this checkout carries replace/graft refs, so the history read "
                  "here is not the history that was written and a truncated ancestry would "
                  "read as an absent one. Run `git replace --list` and clear them first.")
        return 1

    try:
        findings, version, read, (cross, heads, unrun) = run(root)
    except Unreadable as exc:
        log.error("NOT-RUN: %s. This checkout has the commits and not their contents — a "
                  "partial or filtered clone — so an earlier payload cannot be hashed and a "
                  "reused version would read as unused. Run `git fetch --refetch` or clone "
                  "without a filter before trusting a verdict here.", exc)
        return 1
    except ValueError as exc:
        log.error("FAIL: a manifest version this guard cannot order: %s", exc)
        return 1
    # Rule 3 on its own line, always, and before anything else is reported: the
    # sentence that says it could not look and the sentence that says it looked
    # and found nothing must never be the same sentence, and neither may be
    # folded into the closing OK, which speaks only of this checkout's history.
    # The leg is named in both sentences because this gate now has two kinds of
    # NOT-RUN — the four that redden it and this one that does not — and a
    # reader who cannot tell them apart has the false-green problem back.
    if unrun is not None:
        log.error("NOT-RUN (rule 3): the open pull requests of this repository could not be "
                  "read (%s), so a version another open branch has already claimed would "
                  "read as unclaimed here. Rules 1 and 2 are unaffected and still ran.", unrun)
    elif not cross:
        log.info("OK (rule 3): %d open pull-request head(s) read, and none claims version %s "
                 "over a different payload", heads, version)
    # And no third line when the rule ran and DID find something: the findings
    # below say it. Printing the all-clear beside them is what the first draft
    # did, and the positive control read `OK (rule 3)` directly above two FAILs
    # naming the very pull requests it had just cleared.

    if not findings and not cross and read == 0:
        # The last way to be blind and look green: a checkout that is neither
        # shallow nor grafted and simply has no commit touching the payload —
        # a fresh `git init`, or the payload moved to a new path whose history
        # starts empty. Ticket 0697's rename was exactly that second case, and
        # `HOMES` is what answers it; a move to a home not listed there lands
        # back here. Zero revisions compared is not a clean comparison, it is
        # no comparison.
        log.error("NOT-RUN: no commit under %s touches any of %s, so there is no earlier "
                  "payload to compare against. If the directory was just moved, add its "
                  "previous path to HOMES in this file; if the checkout is fresh, this "
                  "guard has nothing to say yet.", root, ", ".join(HOMES))
        return 1
    for finding in findings + cross:
        log.error("FAIL: %s", finding)
    if findings or cross:
        return 1
    log.info("OK: version %s, checked across %d revisions of %s, and no earlier "
             "revision shipped a different payload under it", version, read, SITTER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
