"""The schema-migration scratch dir must not default to /tmp.

`check_previous_schema_migrates_in_place` copies `a.index` — a real Zotero
search index, hundreds of MB in practice — into a `tempfile.TemporaryDirectory`.
Left at its default, that directory is `tempfile.gettempdir()`, `/tmp` on this
host: a quota'd tmpfs. A killed run (timeout, OOM, Ctrl-C via SIGKILL) skips
Python's `with`-block cleanup and leaves the copy there, in RAM (ticket 0714 —
the same host filled its /tmp tmpfs from an unrelated vitest leak the same day).

`dir=data_dir.parent` puts the scratch beside `--data-dir`, which the script
already requires to exist and already treats as disk-backed real storage.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

TEMPORARY_DIRECTORY_CALL = re.compile(
    r'tempfile\.TemporaryDirectory\(\s*prefix="zoteus-smoke-"[^)]*\)')


def _call_text() -> str:
    source = (REPO / "bench" / "smoke_upstream.py").read_text()
    match = TEMPORARY_DIRECTORY_CALL.search(source)
    assert match, "positive control: the TemporaryDirectory(...) call itself must be found"
    return match.group(0)


def test_scratch_dir_is_not_left_at_the_tempfile_default():
    call = _call_text()
    assert "dir=" in call, (
        f"{call!r} has no dir= — it defaults to tempfile.gettempdir(), "
        "which leaks a copy of --index onto /tmp on a killed run")


def test_scratch_dir_is_anchored_to_the_disk_backed_data_dir():
    call = _call_text()
    assert "data_dir" in call, (
        f"{call!r} does not derive its dir= from data_dir, "
        "the one path this script already requires to exist on disk")
