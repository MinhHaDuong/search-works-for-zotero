"""The schema-migration scratch dir must not default to /tmp.

`check_previous_schema_migrates_in_place` copies `a.index` — a real Zotero
search index, hundreds of MB in practice — into a `tempfile.TemporaryDirectory`.
Left at its default, that directory is `tempfile.gettempdir()`, `/tmp` on this
host: a quota'd tmpfs. A run killed outright (SIGKILL: OOM killer, a hard
timeout) skips Python's `with`-block cleanup and leaves the copy there, in RAM
(ticket 0714 — the same host filled its /tmp tmpfs from an unrelated vitest
leak the same day).

`dir=data_dir.parent` puts the scratch beside `--data-dir`, which the script
already requires to exist and already treats as disk-backed real storage.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRATCH_CALL_MARKER = 'prefix="zoteus-smoke-"'


def test_scratch_dir_is_anchored_to_the_disk_backed_data_dir():
    source = (REPO / "bench" / "smoke_upstream.py").read_text()
    calls = [line for line in source.splitlines() if SCRATCH_CALL_MARKER in line]
    assert len(calls) == 1, (
        f"positive control: expected exactly one line with {SCRATCH_CALL_MARKER}, "
        f"found {len(calls)}")
    call = calls[0].strip()
    assert "dir=data_dir" in call, (
        f"{call!r} does not set dir=data_dir.parent — the scratch defaults to "
        "tempfile.gettempdir() (/tmp) or anchors somewhere else, and a killed run "
        "leaks a copy of --index there")
