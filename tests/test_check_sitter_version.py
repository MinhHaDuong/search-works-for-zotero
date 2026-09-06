"""`bench/check_sitter_version.py` — and its own positive controls.

The guard is silent on this repository today, and a silent guard proves nothing
until it has been seen red. Three controls make it say something: a payload
changed without a bump, a version walked backwards, and a checkout with no
history at all. The last is the one that would otherwise pass as green — a gate
that cannot look must not answer as though it had.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "bench") not in sys.path:
    sys.path.insert(0, str(REPO / "bench"))

from build_sdt_sitter import DELIVERED  # noqa: E402

SITTER = REPO / "bench" / "sdt-sitter"
GUARD = REPO / "bench" / "check_sitter_version.py"


def guard(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GUARD), "--root", str(root)],
                          capture_output=True, text=True, timeout=120)


def commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=guard@invalid", "-c", "user.name=guard",
                    "commit", "-q", "-m", message], cwd=repo, check=True, capture_output=True)


def set_version(sitter: Path, version: str) -> None:
    path = sitter / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = version
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def payload(root: Path) -> Path:
    """A throwaway checkout carrying only what the guard reads."""
    sitter = root / "bench" / "sdt-sitter"
    sitter.mkdir(parents=True)
    for name in DELIVERED:
        shutil.copyfile(SITTER / name, sitter / name)
    return sitter


def seed(root: Path, version: str) -> Path:
    sitter = payload(root)
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
def test_guard_reddens_on_a_version_that_goes_backwards(tmp_path):
    """A number that shrinks makes the newer artifact look older to the host."""
    root = tmp_path / "repo"
    root.mkdir()
    sitter = seed(root, "2.4.0")
    set_version(sitter, "2.3.0")
    (sitter / "bootstrap.js").write_text("// another payload\n", encoding="utf-8")
    commit(root, "regress")
    result = guard(root)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "2.4.0" in result.stdout + result.stderr


@pytest.mark.integration
def test_guard_reports_not_run_where_there_is_no_history(tmp_path):
    """No git tree, no earlier payload, no verdict — and never a green one."""
    root = tmp_path / "bare"
    payload(root)
    result = guard(root)
    assert result.returncode != 0
    assert "NOT-RUN" in result.stdout + result.stderr


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
