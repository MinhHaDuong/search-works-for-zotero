"""`bench/check_sitter_version.py` — and its own positive controls.

The guard is silent on this repository today, and a silent guard proves nothing
until it has been seen red. Two controls make it say something: a payload
changed without a bump, and a checkout with no history at all. The last is the
one that would otherwise pass as green — a gate that cannot look must not
answer as though it had. A third control locks in a deliberate design choice
rather than a defect: the no-regression check was removed 2026-09-06 (author's
ruling, this ticket's DECISIONS.md entry) for the sitter's unreleased-software
version-scheme reset, so a version that goes backwards is now expected to pass.
A fourth crosses ticket 0697's promotion out of `bench/`, where the payload's
history is split across two directories and reading only the current one comes
back green over a single revision.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "bench") not in sys.path:
    sys.path.insert(0, str(REPO / "bench"))

from build_sdt_sitter import DELIVERED  # noqa: E402
from check_sitter_version import HOMES  # noqa: E402

SITTER = REPO / "plugins" / "sdt-sitter"
GUARD = REPO / "bench" / "check_sitter_version.py"


def guard(root: Path, **environment: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GUARD), "--root", str(root)],
                          capture_output=True, text=True, timeout=120,
                          env={**os.environ, **environment} if environment else None)


def commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=guard@invalid", "-c", "user.name=guard",
                    "commit", "-q", "-m", message], cwd=repo, check=True, capture_output=True)


def set_version(sitter: Path, version: str) -> None:
    path = sitter / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = version
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def payload(root: Path, base: str = HOMES[0]) -> Path:
    """A throwaway checkout carrying only what the guard reads.

    `base` is the payload directory to build, relative to `root`. It defaults to
    the live one and is overridden only by the rename arm below, which has to
    seed history at the pre-promotion path the guard no longer reads directly.
    """
    sitter = root / base
    sitter.mkdir(parents=True)
    for name in DELIVERED:
        # A delivered name may be a path: the locale files of ticket 0692 sit
        # under `locale/<tag>/`, and a flat copy silently dropped them, which
        # made every arm below run against a payload the guard does not hash.
        destination = sitter / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SITTER / name, destination)
    return sitter


def seed(root: Path, version: str, base: str = HOMES[0]) -> Path:
    sitter = payload(root, base)
    set_version(sitter, version)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, capture_output=True)
    commit(root, f"seed {version}")
    return sitter


@pytest.mark.integration
def test_guard_is_green_on_the_live_repository():
    result = guard(REPO)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.integration
def test_guard_reddens_on_a_payload_shipped_twice_under_one_version(tmp_path):
    """The defect itself: `bootstrap.js` edited, manifest version left alone.

    The manifest still validates, the XPI still builds, and two different
    plugins now answer to one number in the author's `extensions.json`. Nothing
    but history can see it, which is why the guard reads history.
    """
    root = tmp_path / "repo"
    root.mkdir()
    sitter = seed(root, "2.3.0")
    assert guard(root).returncode == 0, "the seeded checkout must start green"

    (sitter / "bootstrap.js").write_text("// a different payload\n", encoding="utf-8")
    commit(root, "change the payload, keep the version")
    result = guard(root)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "2.3.0" in result.stdout + result.stderr

    set_version(sitter, "2.4.0")
    commit(root, "bump")
    assert guard(root).returncode == 0, "a bump must clear it, or nobody can make it green"


@pytest.mark.integration
def test_guard_is_silent_on_a_version_that_goes_backwards(tmp_path):
    """A deliberate, once-only scheme reset (0.2.11) is a numeric decrease.

    The no-regression check was removed for exactly this case: unreleased
    software has no installed base an older-looking number could confuse, and
    the reset is a one-time author's ruling, not a recurring risk. What must
    still fire is the reuse check — a DIFFERENT payload may never share a
    version with an earlier one, backwards or not.
    """
    root = tmp_path / "repo"
    root.mkdir()
    sitter = seed(root, "2.4.0")
    set_version(sitter, "0.2.11")
    (sitter / "bootstrap.js").write_text("// another payload\n", encoding="utf-8")
    commit(root, "reset the version scheme")
    assert guard(root).returncode == 0, "a backwards scheme reset must not redden"


@pytest.mark.integration
def test_guard_reddens_when_a_leading_zero_hides_the_reuse(tmp_path):
    """`2.03.0` and `2.3.0` are one version to any dotted-number comparator.

    String equality calls them two, which would let the reuse check miss the
    collision entirely. A changed payload must not go out green just because
    the manifest wrote its version with a leading zero.
    """
    root = tmp_path / "repo"
    root.mkdir()
    sitter = seed(root, "2.3.0")
    (sitter / "bootstrap.js").write_text("// a different payload\n", encoding="utf-8")
    set_version(sitter, "2.03.0")
    commit(root, "reformat the version, change the payload")
    result = guard(root)
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.integration
def test_guard_reports_not_run_where_there_is_no_history(tmp_path):
    """No git tree, no earlier payload, no verdict — and never a green one."""
    root = tmp_path / "bare"
    payload(root)
    result = guard(root)
    assert result.returncode != 0
    assert "NOT-RUN" in result.stdout + result.stderr


@pytest.mark.integration
def test_guard_reports_not_run_on_a_repository_with_no_commit_for_the_payload(tmp_path):
    """A git tree that is neither shallow nor grafted, and still has nothing to read.

    Zero revisions compared is no comparison, and it printed OK. Ticket 0697's
    rename would have landed here too — a new path whose history starts empty —
    had the guard not been taught every home the payload has had; the arm below
    covers that half, and this one covers a checkout with no history at all.
    """
    root = tmp_path / "fresh"
    payload(root)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, capture_output=True)
    result = guard(root)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "NOT-RUN" in result.stdout + result.stderr

    # And a repository with commits, none of them touching the payload path.
    other = tmp_path / "elsewhere"
    other.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=other, check=True, capture_output=True)
    (other / "README.md").write_text("unrelated\n", encoding="utf-8")
    commit(other, "something else entirely")
    payload(other)
    result = guard(other)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "NOT-RUN" in result.stdout + result.stderr


@pytest.mark.integration
def test_guard_reads_the_payload_history_across_the_promotion_rename(tmp_path):
    """Ticket 0697 moved the payload; the history before the move must still count.

    A rename across a directory is not followed by `git log <path>`, so a guard
    that names only the new path sees a history that starts at the rename
    commit — and every collision older than the move reads as absent. That is
    the guard's own read == 0 NOT-RUN case only when the move is the very first
    commit; with anything after it the count is nonzero and the verdict comes
    back a confident OK over one revision. Two arms, because either half of the
    fix alone still answers green: the `git log` pathspec must name both paths,
    AND `git show` must try both, since `<sha>:plugins/...` does not exist on a
    pre-move commit and an unreadable manifest is skipped, not counted.

    The fixture puts the ONLY collision in pre-move history: the working tree
    carries the first commit's version over the second commit's payload, and
    the rename commit itself bumps, so nothing after the move can redden it.
    """
    # Read off the guard's own roster rather than restated: the arm has to seed
    # at a path the guard no longer reads directly, and a literal here would
    # keep passing against a roster that had lost that entry.
    assert len(HOMES) >= 2, "this arm needs a superseded home to seed history at"
    current, previous = HOMES[0], HOMES[-1]

    root = tmp_path / "repo"
    root.mkdir()
    old = seed(root, "2.3.0", base=previous)                     # payload P1 as 2.3.0
    (old / "bootstrap.js").write_text("// a second payload\n", encoding="utf-8")
    set_version(old, "2.4.0")
    commit(root, "a second payload, bumped")                     # payload P2 as 2.4.0

    (root / current).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "mv", previous, current],
                   cwd=root, check=True, capture_output=True)
    new = root / current
    set_version(new, "2.5.0")
    commit(root, "promote the sitter to its current home, bumped")  # payload P2 as 2.5.0

    # P2 under 2.3.0 collides with commit 1 (P1 under 2.3.0) and with nothing else.
    set_version(new, "2.3.0")
    commit(root, "reuse a pre-move version over a later payload")
    result = guard(root)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "NOT-RUN" not in output, output
    assert "2.3.0" in output, output

    # And the green arm reports what it actually read. Five commits touch the
    # payload, two of them only at the pre-move path; a guard blind to the
    # rename reports three and calls that a clean comparison. The literal count
    # is the discriminator here, so it is asserted rather than bounded.
    set_version(new, "2.6.0")
    commit(root, "bump clear of every earlier version")
    result = guard(root)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "against 5 earlier revisions" in output, output


@pytest.mark.integration
def test_a_redirected_git_environment_cannot_answer_for_another_repository(tmp_path):
    """`--root` names the tree to read; `GIT_DIR` quietly named the history.

    Inherited from whoever ran the gate, and unfiltered, so the guard read one
    repository's files against another repository's log and printed OK about a
    checkout it had not looked at.
    """
    guilty = tmp_path / "guilty"
    guilty.mkdir()
    sitter = seed(guilty, "2.3.0")
    (sitter / "bootstrap.js").write_text("// a different payload\n", encoding="utf-8")
    commit(guilty, "change the payload, keep the version")
    assert guard(guilty).returncode != 0, "the positive control must be red first"

    innocent = tmp_path / "innocent"
    innocent.mkdir()
    seed(innocent, "1.0.0")

    for redirect in ({"GIT_DIR": str(innocent / ".git")},
                     {"GIT_DIR": str(innocent / ".git"), "GIT_WORK_TREE": str(innocent)},
                     {"GIT_COMMON_DIR": str(innocent / ".git")},
                     {"GIT_OBJECT_DIRECTORY": str(innocent / ".git" / "objects")}):
        result = guard(guilty, **redirect)
        assert result.returncode != 0, f"{redirect}: {result.stdout}{result.stderr}"


@pytest.mark.integration
def test_guard_reports_not_run_when_the_history_names_blobs_it_cannot_produce(tmp_path):
    """Commits present, contents absent — a partial clone, and it read as clean.

    `git show` fails identically on a blob that was filtered out and on a path
    that never existed, and only the second is a payload that was never there.
    The tree distinguishes them without needing the blob, so it is asked.
    """
    root = tmp_path / "repo"
    root.mkdir()
    sitter = seed(root, "2.3.0")
    (sitter / "bootstrap.js").write_text("// a different payload\n", encoding="utf-8")
    commit(root, "change the payload, keep the version")
    assert guard(root).returncode != 0, "the collision must be visible before it is hidden"

    # Remove the earlier bootstrap.js blob, which is what a blobless clone lacks.
    first = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=root,
                           check=True, capture_output=True, text=True).stdout.strip()
    blob = subprocess.run(["git", "rev-parse", f"{first}:plugins/sdt-sitter/bootstrap.js"],
                          cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "unpack-objects"], cwd=root, capture_output=True)  # keep loose
    loose = root / ".git" / "objects" / blob[:2] / blob[2:]
    if not loose.exists():
        pytest.skip("the blob is packed here, so it cannot be removed one object at a time")
    loose.unlink()

    result = guard(root)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "NOT-RUN" in result.stdout + result.stderr, result.stdout + result.stderr


@pytest.mark.integration
def test_guard_reports_not_run_on_a_grafted_history(tmp_path):
    """`git replace --graft` truncates the ancestry and sets no shallow marker.

    Same blindness as a shallow clone, reached by a route the shallow probe
    answers `false` for: the tip is identical, the visible history is not, and
    the guard printed the same OK sentence either way.
    """
    root = tmp_path / "repo"
    root.mkdir()
    sitter = seed(root, "2.3.0")
    (sitter / "bootstrap.js").write_text("// a different payload\n", encoding="utf-8")
    commit(root, "change the payload, keep the version")
    assert guard(root).returncode != 0, "the ungrafted history must see the collision"

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "replace", "--graft", head], cwd=root, check=True, capture_output=True)
    result = guard(root)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "NOT-RUN" in result.stdout + result.stderr, result.stdout + result.stderr


@pytest.mark.integration
def test_guard_reports_not_run_on_a_shallow_clone(tmp_path):
    """A truncated history hides the earlier payload that would have reddened it."""
    origin = tmp_path / "origin"
    origin.mkdir()
    sitter = seed(origin, "2.3.0")
    (sitter / "bootstrap.js").write_text("// a different payload\n", encoding="utf-8")
    commit(origin, "change the payload, keep the version")
    assert guard(origin).returncode != 0, "the full clone must see the collision"

    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{origin}", str(shallow)],
                   check=True, capture_output=True)
    result = guard(shallow)
    assert result.returncode != 0
    assert "NOT-RUN" in result.stdout + result.stderr, result.stdout + result.stderr

    # And from a LINKED worktree of that shallow clone, which is the layout every
    # lane in this repository actually runs in. The `shallow` marker lives in the
    # common git dir, so a check reading `--absolute-git-dir` finds nothing here
    # and answers green while blind — this arm is what caught that, and a clone
    # alone never reaches it because `git clone` yields a primary checkout.
    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "-q", str(linked), "-b", "side"],
                   cwd=shallow, check=True, capture_output=True)
    result = guard(linked)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "NOT-RUN" in result.stdout + result.stderr, result.stdout + result.stderr
