"""Rung 3's whole-corpus accounting, without a Zotero (ticket 0821).

The live half -- a whole-Menagerie run, and the red control that holds one
document queued -- is recorded under `verification/menagerie/`. What is
checkable here is the part that decides the verdict: which files the rung
imports, how a status is classed, and that an attachment left `queued` fails.
"""

import ast
import json
import re
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

import sitter_menagerie_test as rung  # noqa: E402
from fixtures.smoke_library import pick_menagerie_documents  # noqa: E402


def _package(tmp_path):
    attachments = tmp_path / "package" / "attachments"
    attachments.mkdir(parents=True)
    for name, size in [("a.pdf", 300), ("b.html", 10), ("c.epub", 200),
                       ("d.txt", 50), ("e.pdf", 100)]:
        (attachments / name).write_bytes(b"x" * size)
    return tmp_path / "package"


# -- which files ------------------------------------------------------------

def test_default_selection_stays_the_smoke_rungs_pdfs(tmp_path):
    picked = pick_menagerie_documents(_package(tmp_path))
    assert [f.name for f in picked] == ["e.pdf", "a.pdf"]


def test_suffixes_none_takes_every_file_smallest_first(tmp_path):
    picked = pick_menagerie_documents(_package(tmp_path), None, suffixes=None)
    assert [f.name for f in picked] == ["b.html", "d.txt", "e.pdf", "c.epub", "a.pdf"]


def test_a_count_slices_the_widened_listing(tmp_path):
    picked = pick_menagerie_documents(_package(tmp_path), 2, suffixes=None)
    assert [f.name for f in picked] == ["b.html", "d.txt"]


# -- the status vocabulary ----------------------------------------------------

SCHEDULER = REPO / "plugins/sdt-sitter/scheduler.js"


def _scheduler_classes(source: str) -> dict:
    """`SDT_STATUS_CLASSES` as `plugins/sdt-sitter/scheduler.js` declares it."""
    block = re.search(r"var SDT_STATUS_CLASSES = \{(.*?)\n\};", source, re.S)
    assert block, "SDT_STATUS_CLASSES not found in scheduler.js"
    body = "\n".join(line.split("//", 1)[0] for line in block.group(1).splitlines())
    return {name: re.findall(r"'([^']+)'", members)
            for name, members in re.findall(r"(\w+):\s*\[([^\]]*)\]", body)}


def test_embedded_status_classes_match_the_scheduler_verbatim():
    assert rung.SDT_STATUS_CLASSES == _scheduler_classes(SCHEDULER.read_text(encoding="utf-8"))


def test_the_drift_guard_sees_a_status_added_to_the_plugin():
    # Positive control: the parser reads a planted status, so the guard above
    # would go red on it rather than read past it.
    source = SCHEDULER.read_text(encoding="utf-8").replace(
        "queued: ['missing-pack',", "queued: ['new-status', 'missing-pack',")
    assert "new-status" in _scheduler_classes(source)["queued"]
    assert rung.SDT_STATUS_CLASSES != _scheduler_classes(source)


@pytest.mark.parametrize("status,cls", [
    ("current", "indexed"), ("empty-pack", "unindexed"),
    ("failed-session", "failed"), ("unsupported", "outOfScope"),
    ("missing-pack", "queued"), ("no-such-status", None),
])
def test_classify_status(status, cls):
    assert rung.classify_status(status) == cls


def test_a_session_verdict_is_taken_from_the_scheduler():
    assert rung.effective_status("missing-pack", "failed-session") == "failed-session"
    assert rung.effective_status("current", "missing-pack") == "current"
    assert rung.effective_status("missing-pack", None) == "missing-pack"


# -- completeness ---------------------------------------------------------------

def _row(key, status):
    return {"id": hash(key) % 1000, "key": key, "status": status,
            "class": rung.classify_status(status)}


SETTLED = [_row("A", "current"), _row("B", "empty-pack"),
           _row("C", "failed-session"), _row("D", "unsupported")]


def test_every_settled_class_passes_and_is_counted():
    counts = rung.account(SETTLED, expected=4)
    assert counts == {"indexed": 1, "unindexed": 1, "failed": 1,
                      "queued": 0, "outOfScope": 1}


def test_one_attachment_left_queued_fails():
    with pytest.raises(rung.MenagerieFailure, match=r"1 left queued.*E=missing-pack"):
        rung.account(SETTLED + [_row("E", "missing-pack")], expected=5)


def test_a_status_in_no_class_fails():
    with pytest.raises(rung.MenagerieFailure, match="in no status class"):
        rung.account(SETTLED + [_row("E", "threw")], expected=5)


def test_a_missing_attachment_fails():
    with pytest.raises(rung.MenagerieFailure, match="4 attachment.*5 listed"):
        rung.account(SETTLED, expected=5)


# -- the invalidation victim ------------------------------------------------------

def test_victim_is_the_smallest_attachment_with_a_pack():
    rows = [{"key": "HTML", "path": "/x.html", "size": 1},
            {"key": "BIG", "path": "/big.pdf", "size": 900},
            {"key": "SMALL", "path": "/small.pdf", "size": 90},
            {"key": "GONE", "path": None, "size": None}]
    packs = {"BIG": "h1", "SMALL": "h2"}
    assert rung.pick_victim(rows, packs)["key"] == "SMALL"
    assert rung.pick_victim(rows, {}) is None


# -- settling -------------------------------------------------------------------------

class _Run:
    def __init__(self, states):
        self.states = list(states)

    def state(self):
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]


class _Log:
    def write(self, _line):
        pass


def _state(pending, busy=False, completed=0, scanned=5):
    return {"completed": completed, "failed": 0, "pending": pending, "busy": busy,
            "total": scanned, "scanned": scanned, "active": None}


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(rung.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(rung.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    return now


def _args(**kw):
    return SimpleNamespace(**{"index_timeout": 1000.0, "settle_quiet": 60.0, **kw})


def test_drained_waits_for_the_census_to_reach_the_listing(clock):
    run = _Run([_state(0, scanned=0), _state(3, busy=True, scanned=5),
                _state(0, completed=3)])
    out = rung.wait_settled(run, _args(), _Log(), expected=5)
    assert out["how"] == "drained" and out["state"]["completed"] == 3


def test_a_queue_that_stops_moving_is_a_stall_not_a_timeout(clock):
    out = rung.wait_settled(_Run([_state(1, completed=4)]), _args(), _Log(), expected=5)
    assert out["how"] == "stalled"


def test_progress_past_the_deadline_is_a_timeout(clock):
    busy = [_state(3, busy=True, completed=n) for n in range(1000)]
    with pytest.raises(rung.RungTimeout, match="--index-timeout"):
        rung.wait_settled(_Run(busy), _args(index_timeout=50.0), _Log(), expected=5)


# -- lifecycle (ticket 0822) ------------------------------------------------------

def test_the_pinned_data_directory_passes_when_zotero_opened_it(tmp_path):
    assert rung.assert_pinned_data_dir({"dataDir": str(tmp_path)}, tmp_path, "t") \
        == tmp_path.resolve()


def test_another_data_directory_is_refused(tmp_path):
    with pytest.raises(rung.MenagerieFailure, match="REFUSING.*after the restart"):
        rung.assert_pinned_data_dir({"dataDir": str(tmp_path / "decoy")}, tmp_path,
                                    "after the restart")


@pytest.mark.parametrize("live", [{}, {"ok": False, "reason": "threw"}, None])
def test_an_unreadable_data_directory_is_refused_not_passed(tmp_path, live):
    with pytest.raises(rung.MenagerieFailure, match="could not read"):
        rung.assert_pinned_data_dir(live, tmp_path, "t")


def test_repointing_prefs_rewrites_the_one_datadir_line(tmp_path):
    prefs = tmp_path / "prefs.js"
    prefs.write_text('user_pref("extensions.zotero.dataDir", "/pinned");\n'
                     'user_pref("extensions.zotero.useDataDir", true);\n')
    rung.repoint_data_dir(prefs, tmp_path / "decoy")
    text = prefs.read_text()
    assert f'"extensions.zotero.dataDir", "{tmp_path / "decoy"}"' in text
    assert "/pinned" not in text
    assert 'useDataDir", true' in text


PACK = {"source": "s", "sha256": "b", "mtime_ns": 1}


def test_untouched_packs_compare_clean():
    assert rung.compare_packs({"A": PACK}, {"A": dict(PACK)}, allow_new=False) == []


@pytest.mark.parametrize("field_", ["source", "sha256", "mtime_ns"])
def test_a_pack_rewritten_in_any_field_is_named(field_):
    after = {"A": {**PACK, field_: "other"}}
    assert rung.compare_packs({"A": PACK}, after, allow_new=True) \
        == [f"A: pack {field_} {PACK[field_]!r} -> 'other'"]


def test_a_pack_redone_with_identical_bytes_is_still_named_by_its_mtime():
    # The resume red control's case: deleted while Zotero was down, extracted
    # again byte for byte. Count and hash set agree; only the mtime tells.
    after = {"A": {**PACK, "mtime_ns": 2}}
    assert rung.compare_packs({"A": PACK}, after, allow_new=False) \
        == ["A: pack mtime_ns 1 -> 2"]


def test_a_lost_pack_is_named():
    assert rung.compare_packs({"A": PACK, "B": PACK}, {"A": PACK}, allow_new=True) \
        == ["B: pack gone"]


def test_new_packs_pass_only_where_extraction_was_under_way():
    after = {"A": PACK, "N": PACK}
    assert rung.compare_packs({"A": PACK}, after, allow_new=True) == []
    assert rung.compare_packs({"A": PACK}, after, allow_new=False) \
        == ["N: pack appeared with no work outstanding"]


def test_pack_identities_read_bytes_and_mtime(tmp_path, monkeypatch):
    pack = tmp_path / "storage" / "KEY1" / ".zotero-sdt-cache"
    pack.parent.mkdir(parents=True)
    pack.write_bytes(b"pack")
    monkeypatch.setattr(rung, "read_pack_metadata", lambda _p: {"source": {"hash": "h"}})
    got = rung.pack_identities(tmp_path)
    assert got["KEY1"]["source"] == "h"
    assert got["KEY1"]["mtime_ns"] == pack.stat().st_mtime_ns
    assert len(got["KEY1"]["sha256"]) == 64


def test_a_zero_length_disabled_hold_is_unproven_not_passed():
    with pytest.raises(rung.MenagerieFailure, match="UNPROVEN"):
        rung.judge_disabled_hold([], 0.0)


def test_a_sitter_seen_alive_while_disabled_fails():
    readings = [{"handle": False, "isActive": False}, {"handle": True, "isActive": False}]
    with pytest.raises(rung.MenagerieFailure, match="still live while disabled in 1 of 2"):
        rung.judge_disabled_hold(readings, 10.0)


def test_an_observed_disabled_hold_passes():
    readings = [{"handle": False, "isActive": False}] * 3
    assert rung.judge_disabled_hold(readings, 3.0) == {"observations": 3, "hold_s": 3.0}


def test_the_replace_payload_is_the_given_one_with_a_bumped_version(tmp_path):
    src = tmp_path / "in.xpi"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("manifest.json", json.dumps({"version": "0.4.33", "name": "n"}))
        z.writestr("bootstrap.js", "mutant();")
    out = tmp_path / "out.xpi"
    assert rung.bump_payload(src, out) == "0.4.33.1"
    with zipfile.ZipFile(out) as z:
        assert json.loads(z.read("manifest.json"))["version"] == "0.4.33.1"
        assert z.read("bootstrap.js") == b"mutant();"


def test_the_volume_rigs_restart_closure_is_never_imported():
    # Ticket 0822: `restart_zotero()` is a closure inside the volume rig's
    # `main()`, blind to this rung's pinned data directory. The restart here is
    # composed from the rung's own launch; this holds the import out.
    tree = ast.parse((REPO / "bench/sitter_menagerie_test.py").read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert "restart_zotero" not in imported
    assert {"disable_enable_code", "liveness_code", "ADDON_ID"} <= imported
