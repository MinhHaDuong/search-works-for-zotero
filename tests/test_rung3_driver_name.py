"""Rung 3 of the sitter's test ladder is not called "acceptance" (ticket 0820).

The author ruled on 2026-09-23 that acceptance is his own use. The rung-3
driver moved to `bench/sitter_menagerie_test.py` and its records to
`verification/menagerie/`. This fails while a live file still names either old
path. Append-only history keeps its words: `DECISIONS.md`, `tickets/closed/`,
the committed records' own `"script"` fields, and dated verification reports
are outside the scan. The rename's own ticket records the old names by design
and is skipped until its close files it under `tickets/closed/`.

The unrelated acceptance layer (`bench/acceptance/`, `ACCEPTANCE_ARENA`) is
untouched: the scan matches the two literal paths, never the bare word.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Split so this file does not match itself.
OLD_PATHS = ("bench/sitter_" + "acceptance.py", "verification/" + "acceptance/")
RENAME_TICKET = "0820-"


def live_files(repo: Path) -> list[Path]:
    files = [*repo.glob("bench/**/*.py"), *repo.glob("tests/**/*.py")]
    files += [repo / "Makefile", repo / "plugins/sdt-sitter/TESTING.md", repo / "STATE.md"]
    files += [p for p in repo.glob("tickets/*.erg") if not p.name.startswith(RENAME_TICKET)]
    return [p for p in files if p.is_file()]


def stale_references(repo: Path) -> list[str]:
    hits = []
    for path in live_files(repo):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for old in OLD_PATHS:
                if old in line:
                    hits.append(f"{path.relative_to(repo)}:{number}: {old}")
    return hits


def test_no_live_file_names_the_old_rung3_paths():
    assert stale_references(REPO) == []


def test_the_scan_sees_a_planted_reference(tmp_path):
    (tmp_path / "STATE.md").write_text(f"see `{OLD_PATHS[1]}x.json`\n", encoding="utf-8")
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "0999-x.erg").write_text(OLD_PATHS[0], encoding="utf-8")
    (tmp_path / "tickets" / "0820-x.erg").write_text(OLD_PATHS[0], encoding="utf-8")
    assert stale_references(tmp_path) == [
        f"STATE.md:1: {OLD_PATHS[1]}",
        f"tickets/0999-x.erg:1: {OLD_PATHS[0]}",
    ]


def test_the_records_resolve_at_their_new_home():
    records = sorted((REPO / "verification/menagerie").glob("*.json"))
    assert records, "no rung-3 record under verification/menagerie/"
    assert (REPO / "bench/sitter_menagerie_test.py").is_file()
