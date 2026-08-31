"""The catch-up report's parsing, exercised without a network.

The report itself needs a remote, so what is testable here is the part that
decides what the report SAYS: how `UPSTREAM` is read, and which tokens count as
an upstream item or a release. Those are the two places a silent wrong answer
would look like a correct one — an item pattern that swallows a SHA prefix
prints items nobody filed, and a release pattern that admits any tag reports
releases that were never cut.

The git walking is deliberately not mocked. A test that stubs `git rev-list`
asserts that the stub was called, which is not a fact about upstream.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location(
        "uc", REPO / "bench" / "upstream_catchup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


uc = load()


def test_config_reads_the_live_upstream_file():
    """The real `UPSTREAM`, so a renamed key is caught here and not at runtime."""
    cfg = uc.upstream_config()
    for key in (
        "UPSTREAM_REPOSITORY",
        "UPSTREAM_BRANCH",
        "UPSTREAM_REVIEWED_SHA",
        "UPSTREAM_REVIEWED_VERSION",
        "UPSTREAM_REVIEWED_DATE",
    ):
        assert cfg[key], f"{key} missing or empty in UPSTREAM"


def test_config_ignores_comments_and_blank_lines(tmp_path, monkeypatch):
    """`UPSTREAM` is `include`d by the Makefile, so its comment form is fixed."""
    monkeypatch.setattr(uc, "REPO", tmp_path)
    (tmp_path / "UPSTREAM").write_text(
        "# a comment\n\nA=1\n  B = two  \n# B=wrong\n", encoding="utf-8"
    )
    assert uc.upstream_config() == {"A": "1", "B": "two"}


def test_item_pattern_finds_every_shape_a_commit_uses():
    subjects = "Merge x (#32)\nCloses #30, refs #7\nfix: thing #128"
    assert sorted({int(n) for n in uc.ITEM.findall(subjects)}) == [7, 30, 32, 128]


def test_item_pattern_does_not_invent_items_from_hashes():
    """A colour or a fragment is not an item, and four digits is not one here."""
    assert uc.ITEM.findall("#1234") == []
    assert uc.ITEM.findall("#abc123") == []


def test_release_pattern_admits_releases_only():
    for tag in ("v1.10.0", "v0.1.0", "v1.12.0"):
        assert uc.RELEASE.match(tag), tag
    for tag in ("v1.10", "1.10.0", "v1.10.0-rc1", "archive/fts5-storage-2026-08-21"):
        assert not uc.RELEASE.match(tag), tag


def test_schema_version_pattern_reads_the_constant():
    src = "const OTHER = 9;\nconst SCHEMA_VERSION = 1;\n"
    assert uc.SCHEMA_VERSION.search(src).group(1) == "1"
    assert uc.SCHEMA_VERSION.search("const SCHEMA_VERSION  =  12;").group(1) == "12"


def test_schema_version_absent_is_absent_not_zero():
    """A renamed constant must read as unknown, never as a version that moved."""
    assert uc.SCHEMA_VERSION.search("const INDEX_GENERATION = 3;") is None


def test_passages_ddl_pattern_captures_the_column_list():
    src = """
      CREATE TABLE IF NOT EXISTS passages (
        pid INTEGER PRIMARY KEY,
        source TEXT,
        vector BLOB
      );
      CREATE INDEX IF NOT EXISTS passages_item ON passages(item_key);
    """
    body = uc.PASSAGES_DDL.search(src).group(1)
    assert "pid INTEGER PRIMARY KEY" in body
    assert "vector BLOB" in body
    # It must stop at the table, not run on into the index statements — those
    # change for reasons that do not move the shape a driver opens.
    assert "CREATE INDEX" not in body


def test_watched_surface_is_the_layer_the_requirements_are_about():
    """A typo here silently reports QUIET forever, which is the worst failure
    this script has: it would say "none of it is yours" about everything."""
    assert uc.WATCHED == ["src/features/search/"]
    assert uc.SCHEMA_FILE.startswith(uc.WATCHED[0])
