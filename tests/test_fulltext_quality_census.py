"""Positive control for the ticket-0480 full-text quality census.

The census classifies every `.zotero-ft-cache` under a Zotero `storage/` tree.
Before it is pointed at the author's real library it has to be shown to react —
a probe that reports "no old caches" and a probe that cannot see an old cache
produce the same output, and only one of them is a measurement.

So this builds a fixture `storage/` holding a *known* mix — pre-form-feed PDF
caches, current-generation ones, an empty cache, a mojibake'd one, a non-PDF
attachment — and asserts the census recovers exactly that mix. Each assertion
below fails against a classifier that always answers one way; that is what makes
it a control rather than a smoke test.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

import fulltext_quality_census as census  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def _write(root: Path, key: str, attachment: str, text: str | bytes) -> Path:
    d = root / key
    d.mkdir(parents=True)
    (d / attachment).write_bytes(b"%PDF-1.4 stub" if attachment.endswith(".pdf") else b"<html></html>")
    cache = d / ".zotero-ft-cache"
    cache.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return cache


#: A page of plausible extracted body text, long enough to clear the
#: near-empty floor without carrying any quality signal of its own.
PAGE = ("The estimated abatement cost falls with the discount rate applied. " * 40) + "\n\n"


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """A storage tree whose composition is known by construction."""
    root = tmp_path / "storage"
    root.mkdir()
    # Two current-generation PDF caches: pages separated by form feeds.
    _write(root, "AAAAAAAA", "a.pdf", PAGE + "\f" + PAGE + "\f" + PAGE)
    _write(root, "BBBBBBBB", "b.pdf", PAGE + "\f" + PAGE)
    # Three old-generation PDF caches: no form feed anywhere.
    _write(root, "CCCCCCCC", "c.pdf", PAGE + PAGE)
    _write(root, "DDDDDDDD", "d.pdf", PAGE)
    # ... one of which is also mojibake'd (UTF-8 read as cp1252).
    mojibake = ("Les coûts d'abattement estimés déclinent nettement. " * 40).encode("utf-8").decode("cp1252")
    _write(root, "EEEEEEEE", "e.pdf", mojibake)
    # A PDF with no text layer at all: cache present, effectively empty.
    _write(root, "FFFFFFFF", "f.pdf", "   \n\n  \n")
    # A non-PDF attachment: the form-feed signal does not apply to it.
    _write(root, "GGGGGGGG", "g.html", PAGE)
    # An attachment directory with no cache at all: not part of the census.
    (root / "HHHHHHHH").mkdir()
    (root / "HHHHHHHH" / "h.pdf").write_bytes(b"%PDF-1.4 stub")
    return root


def test_census_counts_the_known_mix(library: Path):
    r = census.census(library)
    assert r["caches"] == 7, "every directory holding a cache is counted, and only those"
    assert r["pdf_caches"] == 6
    assert r["non_pdf_caches"] == 1


def test_form_feed_split_is_the_known_split(library: Path):
    r = census.census(library)
    # Four of the six PDF caches carry no form feed: C, D, E and the empty F.
    assert r["pdf_no_form_feed"] == 4
    assert r["pdf_with_form_feed"] == 2
    keys = {c["key"] for c in r["caches_detail"] if c["is_pdf"] and not c["has_form_feed"]}
    assert keys == {"CCCCCCCC", "DDDDDDDD", "EEEEEEEE", "FFFFFFFF"}


def test_single_page_suspects_exclude_the_empty(library: Path):
    """The false-flag ceiling must not be padded with caches that have no text at all."""
    r = census.census(library)
    # D (one page of body) and E (mojibake, shorter still) are short but real;
    # F is near-empty and belongs to the other class; C is two pages.
    assert r["pdf_no_form_feed_single_page_suspect"] == 2


def test_form_feed_is_not_claimed_for_non_pdf(library: Path):
    """A signal that does not apply must be reported absent, not reported false."""
    g = next(c for c in r_detail(library) if c["key"] == "GGGGGGGG")
    assert g["is_pdf"] is False
    assert g["has_form_feed"] is None, "form feed dates the PDF extractor only"


def r_detail(library: Path) -> list[dict]:
    return census.census(library)["caches_detail"]


def test_empty_cache_is_its_own_class_not_an_old_extractor(library: Path):
    """A PDF with no text layer is a different defect from an old extraction."""
    f = next(c for c in r_detail(library) if c["key"] == "FFFFFFFF")
    assert f["near_empty"] is True
    d = next(c for c in r_detail(library) if c["key"] == "DDDDDDDD")
    assert d["near_empty"] is False
    assert r_detail(library) and census.census(library)["pdf_near_empty"] == 1
    # A cache with literally no words is its own sub-class: the prose separates
    # "too little text" from "no text at all", so the artifact has to as well.
    assert census.census(library)["pdf_zero_words"] == 1
    assert census.census(library)["by_form_feed"]["no_form_feed"]["zero_words"] == 1
    assert census.census(library)["by_form_feed"]["with_form_feed"]["zero_words"] == 0


def test_mojibake_is_detected_only_where_it_is(library: Path):
    """The detector must come out the other way on clean text, or it measures nothing."""
    fixer = census.resolve_mojibake_fixer()
    if fixer is None:
        pytest.skip("no mojibake fixer available (ftfy not installed)")
    r = census.census(library, mojibake_fixer=fixer)
    flagged = {c["key"] for c in r["caches_detail"] if c["mojibake"]}
    assert flagged == {"EEEEEEEE"}


def test_mojibake_signal_is_null_without_a_fixer(library: Path):
    """No fixer means unmeasured, and unmeasured must not read as clean."""
    r = census.census(library, mojibake_fixer=None)
    assert all(c["mojibake"] is None for c in r["caches_detail"])
    assert r["pdf_mojibake"] is None


def test_cross_tabulation_separates_the_two_groups(library: Path):
    """The form-feed split must be reported beside the text signals it claims to predict."""
    fixer = census.resolve_mojibake_fixer()
    r = census.census(library, mojibake_fixer=fixer)
    g = r["by_form_feed"]
    assert g["with_form_feed"]["caches"] == 2
    assert g["no_form_feed"]["caches"] == 4
    assert g["no_form_feed"]["near_empty"] == 1
    assert g["with_form_feed"]["near_empty"] == 0
    if fixer is not None:
        # The mojibake'd cache is in the no-form-feed group, and the other group is clean:
        # a cross-tab that could not come out that way would prove nothing.
        assert g["no_form_feed"]["mojibake"] == 1
        assert g["with_form_feed"]["mojibake"] == 0


def test_census_does_not_mutate_the_library(library: Path):
    before = sorted((str(p.relative_to(library)), p.stat().st_size, p.stat().st_mtime_ns) for p in library.rglob("*"))
    census.census(library)
    after = sorted((str(p.relative_to(library)), p.stat().st_size, p.stat().st_mtime_ns) for p in library.rglob("*"))
    assert before == after, "the probe is read-only over the author's storage tree"


def test_undecodable_bytes_are_counted_not_swallowed(tmp_path: Path):
    """Bytes that are not UTF-8 are counted rather than hidden by the replace read.

    Named for what it exercises: this is the *decode* path, which never raises.
    The `OSError` path has its own control above — an earlier version of this
    file claimed both under this one name and reached neither.
    """
    root = tmp_path / "storage"
    root.mkdir()
    cache = _write(root, "IIIIIIII", "i.pdf", PAGE)
    cache.write_bytes(b"\xff\xfe\x00" * 400)  # not decodable as UTF-8
    r = census.census(root)
    detail = r["caches_detail"][0]
    assert detail["decode_errors"] > 0
    assert r["decode_error_caches"] == 1


def test_a_directory_the_walker_cannot_enter_is_counted_not_skipped(library: Path):
    """The blocker this file exists to keep fixed.

    `Path.glob` swallows `PermissionError` inside its own recursion, so a
    permission-denied attachment directory vanishes from the walk with no count
    and no error — `unreadable_caches: 0` would then mean either "all readable"
    or "cannot see failures", which is the all-clear indistinguishable from
    could-not-look. This is the positive control: a directory made unreadable
    must show up in the failure count, not in silence.
    """
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions, so the control cannot fire")
    baseline = census.census(library)
    denied = library / "BBBBBBBB"
    denied.chmod(0o000)
    try:
        r = census.census(library)
    finally:
        denied.chmod(0o755)
    assert r["unreadable_caches"] == 1
    assert r["unreadable_detail"][0]["key"] == "BBBBBBBB"
    # And it is genuinely absent from the counted population — the failure is
    # reported *instead of* being folded in, not on top of it.
    assert r["caches"] == baseline["caches"] - 1


def test_orphaned_and_mixed_attachment_directories_are_counted(tmp_path: Path):
    """Two ways the directory-scoped `is_pdf` can be wrong, each bounded rather than assumed away."""
    root = tmp_path / "storage"
    root.mkdir()
    _write(root, "JJJJJJJJ", "j.pdf", PAGE)
    (root / "JJJJJJJJ" / "j.pdf").unlink()  # cache survives its attachment
    _write(root, "KKKKKKKK", "k.pdf", PAGE)
    (root / "KKKKKKKK" / "k.html").write_bytes(b"<html></html>")  # PDF and not-PDF together
    r = census.census(root)
    assert r["caches_with_no_attachment"] == 1
    assert r["pdf_caches_mixed_attachments"] == 1


def test_the_actionable_population_excludes_what_reextraction_cannot_help(library: Path):
    """The figure a policy acts on is not the raw no-form-feed count."""
    r = census.census(library)
    assert r["pdf_no_form_feed"] == 4
    assert r["pdf_near_empty"] == 1
    assert r["pdf_reextraction_population"] == 3


def test_a_stub_fixer_exercises_the_mojibake_path_without_ftfy(library: Path):
    """The cross-tabulation control must run in the gate, where ftfy is absent.

    The real-ftfy test above skips without it, so the claim the report headlines —
    that a text signal sorts with the form-feed split — would rest on one manual
    run. A stub fixer keyed on a marker the fixture carries exercises the same
    plumbing on every `make check`.
    """
    r = census.census(library, mojibake_fixer=lambda t: "Ã" in t)
    assert {c["key"] for c in r["caches_detail"] if c["mojibake"]} == {"EEEEEEEE"}
    assert r["by_form_feed"]["no_form_feed"]["mojibake"] == 1
    assert r["by_form_feed"]["with_form_feed"]["mojibake"] == 0


@pytest.mark.integration
def test_cli_no_detail_writes_the_summary_alone(library: Path, tmp_path: Path):
    """`--no-detail` produced the committed artifact, so it is the flag that needs a test."""
    out = tmp_path / "census.json"
    p = subprocess.run(
        [sys.executable, str(REPO / "bench" / "fulltext_quality_census.py"),
         "--storage", str(library), "--output", str(out), "--no-detail"],
        capture_output=True, text=True,
    )
    assert p.returncode == 0, p.stderr
    doc = json.loads(out.read_text())
    assert doc["caches_detail"] == []
    assert doc["summary"]["caches"] == 7, "the counts survive the row omission"
    assert not list(out.parent.glob("*.tmp")), "the write-then-rename leaves no scratch file"


@pytest.mark.integration
def test_cli_writes_a_provenanced_artifact(library: Path, tmp_path: Path):
    out = tmp_path / "census.json"
    p = subprocess.run(
        [sys.executable, str(REPO / "bench" / "fulltext_quality_census.py"),
         "--storage", str(library), "--output", str(out)],
        capture_output=True, text=True,
    )
    assert p.returncode == 0, p.stderr
    doc = json.loads(out.read_text())
    assert doc["storage"] == str(library)
    for field in ("host", "measured_at", "python", "ftfy_version"):
        assert field in doc["provenance"], f"{field} missing from provenance"
    assert doc["summary"]["pdf_no_form_feed"] == 4
