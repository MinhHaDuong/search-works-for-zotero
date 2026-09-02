"""The log-stamp guard, on fixture repositories and on the live one.

Each fixture is a real git checkout with real commit times, because the whole
predicate is a comparison against git: a guard tested against a stubbed history
would pass whatever it read. The controls that matter are the two the ruling
turns on — a stamp naming a time that has not happened is caught, and a log
that merely reads out of order is NOT, because parallel sessions merge into one
log and that case is honest.
"""

import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location(
        "ctl", REPO / "bench" / "check_ticket_logs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ctl = load()

TICKET = """%erg 0.1
Title: A ticket
Created: 2026-09-01
Author: claude

--- log ---
{log}

--- body ---
## Context
"""


def build(root: Path, log: str, when: str, *, commit: bool = True) -> Path:
    """A git checkout holding one ticket, committed at `when` (an ISO-8601 date)."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.org"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
    (root / "tickets").mkdir()
    path = root / "tickets" / "0001-a-ticket.erg"
    path.write_text(TICKET.format(log=log), encoding="utf-8")
    if commit:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "add"], cwd=root, check=True,
            env={"PATH": "/usr/bin:/bin", "HOME": str(root),
                 "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
        )
    return path


def test_stamp_before_its_commit_passes(tmp_path):
    build(tmp_path, "2026-09-01T11:00Z claude created", "2026-09-01T12:00:00+00:00")
    findings, entries, tickets, pending = ctl.run(tmp_path)
    assert findings == []
    assert (entries, tickets, pending) == (1, 1, 0)


def test_stamp_after_its_commit_is_caught(tmp_path):
    """The defect Copilot found on PR #150: a stamp naming a time that had not happened."""
    build(tmp_path, "2026-09-01T16:30Z claude created", "2026-09-01T11:51:24+00:00")
    findings, _, _, _ = ctl.run(tmp_path)
    assert len(findings) == 1
    assert "stamped 2026-09-01T16:30Z, written 2026-09-01T11:51Z" in findings[0]


def test_out_of_order_log_is_not_a_finding(tmp_path):
    """Parallel sessions merge into one log, so arrival order is not stamping order."""
    build(tmp_path, "2026-09-01T11:00Z claude created\n2026-09-01T10:00Z claude note earlier",
          "2026-09-01T12:00:00+00:00")
    findings, entries, _, _ = ctl.run(tmp_path)
    assert entries == 2
    assert findings == []


def test_uncommitted_future_stamp_is_caught_against_the_clock(tmp_path):
    """Caught while it is still cheap to fix, rather than one commit later."""
    build(tmp_path, "2126-09-01T11:00Z claude created", "2026-09-01T12:00:00+00:00",
          commit=False)
    findings, _, _, pending = ctl.run(tmp_path)
    assert pending == 1
    assert len(findings) == 1 and "uncommitted" in findings[0]


def test_the_second_of_two_entries_is_located(tmp_path):
    """The finding names the line, so a long log does not have to be read to find it."""
    build(tmp_path, "2026-09-01T11:00Z claude created\n2126-09-01T11:00Z claude note ahead",
          "2026-09-01T12:00:00+00:00")
    findings, _, _, _ = ctl.run(tmp_path)
    assert len(findings) == 1 and findings[0].startswith("tickets/0001-a-ticket.erg:8:")


def test_live_repository_is_clean():
    """The corpus itself, swept 2026-09-01 under the ruling."""
    findings, entries, tickets, _ = ctl.run(REPO)
    assert findings == [], f"{len(findings)} log stamps name a time that had not happened"
    assert entries > 500 and tickets > 100
