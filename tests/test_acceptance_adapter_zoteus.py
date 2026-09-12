"""The Zoteus adapter honours the identity boundary before it spawns anything.

Ticket 0626. When ticket 0625 wrapped every real adapter's process spawn with
`Posture.wrap()`, three of the five adapters -- this one among them -- were
verified by code reading only. Reading is not a guard: an edit that moves the
`wrap()` call below the line that starts the process leaves every existing test
green while every run of the target goes back to executing third-party code
under the operator's own identity, with the operator's own library reachable.
That is the defect this file exists to catch, and the review of PR #295 caught
exactly one live instance of it in a sibling adapter, so it is not hypothetical.

This target goes through the shared `mcp_drive.Server` helper rather than a
direct `Popen`, so the wrapping has to happen before that helper is even
constructed -- the same shape as the zotero-mcp adapter's test.

Everything here runs offline, starts no process and writes only under tmp_path.
"""

import importlib
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

adapter = importlib.import_module("bench.acceptance.adapters.zoteus")
posture = importlib.import_module("bench.acceptance.posture")
durability = importlib.import_module("bench.acceptance.durability")


def build(tmp_path, **kwargs) -> object:
    """An adapter on an arena that need not exist and an entrypoint that need not exist.

    `_env()` reads nothing off disk, so this is enough to exercise it without
    spawning `node` or building `mcp_drive.Server`.
    """
    return adapter.Zoteus(tmp_path / "arena",
                           entrypoint=tmp_path / "nowhere" / "index.js", **kwargs)


# --- HOME/TMPDIR/XDG redirection (ticket 0635) ------------------------------
#
# `running()` merges `_env()`'s dict over the *full* operator `os.environ`
# with no delete (`{**os.environ, **env}`), so an omitted key is not "unset" —
# it is whatever the operator's real shell has. The arena-scoped residue sweep
# (`Snapshot.of(arena)` in `assertions.py`) never looks outside `self.arena`,
# so a write under an unredirected `HOME`/`TMPDIR` is invisible to it, not
# merely uncounted. Four sibling adapters (`beaver.py`, `zotero_core_6012.py`,
# `zotero_mcp.py`, `zotseek.py`) already redirect `HOME`; this was the one
# adapter of the five that did not.


def test_the_environment_redirects_home_and_tmpdir_into_the_arena(tmp_path):
    """HOME and TMPDIR must resolve under the arena, never at any ambient value.

    `defaultZoteroDataDir()` in the reviewed upstream checkout falls back to
    `homedir() + "/Zotero"` whenever `zotero_data_dir` is not supplied — an
    unredirected HOME there would resolve to the operator's own home
    directory. TMPDIR is redirected defensively (no direct hit in this
    target's own runtime dependencies, but Node/npm and any native addon a
    dependency pulls in commonly consult it).
    """
    target = build(tmp_path)
    env = target._env()
    assert env["HOME"] == str(tmp_path / "arena" / "home")
    assert env["TMPDIR"] == str(tmp_path / "arena" / "tmp")
    # Both must actually be inside the arena, not merely non-empty strings.
    assert Path(env["HOME"]).is_relative_to(tmp_path / "arena")
    assert Path(env["TMPDIR"]).is_relative_to(tmp_path / "arena")


def test_the_environment_blanks_the_xdg_roots(tmp_path):
    """The XDG roots are present and blank, not merely absent from the dict.

    `mcp_drive.Server` merges the adapter's environment over `os.environ` and
    cannot delete a name, so "absent" has to be spelled as the empty string —
    an *absent* key is exactly the bug this ticket closes, not the fix. Blank
    rather than pointed at the arena, mirroring `zotero_mcp.py`'s treatment of
    `XDG_CACHE_HOME`: any fallback that consults them then resolves under the
    now-redirected HOME instead of an ambient operator override passing
    through.
    """
    env = build(tmp_path)._env()
    for name in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        assert name in env, f"{name} is absent, not blanked — the ambient value would leak through"
        assert env[name] == "", f"{name} is a channel into the default configuration"


def test_the_environment_leaves_the_existing_keys_unchanged(tmp_path):
    """Regression guard: this ticket is additive to `_env()`, not a restructuring.

    `ZOTEUS_DATA_DIR` and its siblings are the whole of what `_env()` declared
    before ticket 0635; none of them should move.
    """
    target = build(tmp_path)
    env = target._env()
    assert env["ZOTEUS_EMBEDDINGS"] == "local"
    assert env["ZOTEUS_DATA_DIR"] == str(tmp_path / "arena" / "data")
    assert env["ZOTEUS_INDEX_BACKEND"] == "sqlite"
    assert env["ZOTEUS_INDEX_AUTO_REFRESH"] == "false"
    assert env["ZOTEUS_INDEX_FULLTEXT"] == "1"
    assert env["ZOTEUS_READ_ONLY"] == "true"
    assert "ZOTEUS_TRANSFORMERS_PATH" not in env
    assert "ZOTERO_DATA_DIR" not in env


def test_the_declared_environment_overrides_an_ambient_override(tmp_path, monkeypatch):
    """Positive control: the declared dict must actually win the merge `running()` performs.

    A dict with the right keys proves nothing on its own if the merge order
    ever changes underneath it. This reproduces `running()`'s own merge
    (`{**os.environ, **env}`) against an ambient environment deliberately set
    to something else, and asserts the declared value survives — for every
    var this ticket added, not just one.
    """
    ambient_home = tmp_path / "definitely-not-the-arena" / "home"
    ambient_tmp = tmp_path / "definitely-not-the-arena" / "tmp"
    monkeypatch.setenv("HOME", str(ambient_home))
    monkeypatch.setenv("TMPDIR", str(ambient_tmp))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "definitely-not-the-arena" / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "definitely-not-the-arena" / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "definitely-not-the-arena" / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "definitely-not-the-arena" / "state"))

    target = build(tmp_path)
    merged = {**os.environ, **target._env()}

    assert merged["HOME"] == str(tmp_path / "arena" / "home")
    assert merged["TMPDIR"] == str(tmp_path / "arena" / "tmp")
    for name in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        assert merged[name] == "", f"the ambient {name} survived the merge `running()` performs"


def test_running_refuses_before_spawning_when_the_posture_is_unavailable(tmp_path):
    """A refused posture stops the lifecycle before `mcp_drive.Server` is built.

    The entrypoint need not exist and `node` need not be installed: the
    refusal happens before the command reaches the server helper, which is
    the assertion. If it did not, this would fail with a spawn error instead
    -- a different exception, so the test cannot pass for the wrong reason.
    """
    refused = posture.Posture(
        posture.ACCOUNT_POSTURE, account=None,
        refused="synthetic refusal for this test",
    )
    target = adapter.Zoteus(tmp_path / "arena",
                            entrypoint=tmp_path / "nowhere" / "index.js",
                            posture=refused)
    with pytest.raises(posture.PostureUnavailable, match="synthetic refusal"):
        with target.running():
            pytest.fail("the lifecycle yielded despite a refused posture")
    assert target.server is None, "a server was constructed despite the refusal"


# --- R23 seed reset and stamp selection (ticket 0623) ----------------------


def _index(path: Path, stamp: str, marker: str) -> None:
    """Write the smallest index shape the adapter's storage probes need."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            ((adapter.STAMP_KEY, stamp), ("marker", marker)),
        )
        con.commit()
    finally:
        con.close()


def _meta(path: Path, key: str) -> str:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]
    finally:
        con.close()


def _set_meta(path: Path, key: str, value: str) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("UPDATE meta SET value=? WHERE key=?", (value, key))
        con.commit()
    finally:
        con.close()


def test_reset_removes_the_old_sqlite_family_before_copying_the_seed(tmp_path):
    """A stale WAL must not replay over the seed copied into the old file's path.

    Malformed bytes make the control stricter than checking names after the fact:
    before the fix, `_stamp()` tries to open the copied database beside this WAL
    and raises (or reads the wrong generation on SQLite builds that accept it).
    The reset must remove every file in the destination database's family first,
    while leaving an unrelated database alone.
    """
    seed = tmp_path / "seed" / "search-index.sqlite"
    _index(seed, "2", "seeded")
    target = build(tmp_path, seed_index=str(seed))
    target.data_dir.mkdir(parents=True)
    destination = target.data_dir / seed.name
    _index(destination, "2", "stale")
    for suffix in ("-wal", "-shm", "-journal", ".incompatible-old"):
        destination.with_name(destination.name + suffix).write_bytes(b"stale sidecar")
    unrelated = target.data_dir / "other.sqlite"
    unrelated.write_bytes(b"unrelated")

    event = target._reset_to_seeded_index()

    assert _meta(destination, "marker") == "seeded"
    assert event["removed_before_copy"] == [
        "search-index.sqlite",
        "search-index.sqlite-journal",
        "search-index.sqlite-shm",
        "search-index.sqlite-wal",
        "search-index.sqlite.incompatible-old",
    ]
    assert unrelated.read_bytes() == b"unrelated"
    assert list(target.data_dir.glob(f"{destination.name}*")) == [destination]


def test_older_restamp_is_one_rung_below_the_index_this_build_wrote(tmp_path):
    """R23's ordinary upgrade arm is N-1, not an obsolete fixed stamp."""
    seed = tmp_path / "seed" / "search-index.sqlite"
    _index(seed, "2", "seeded")
    target = build(tmp_path, seed_index=str(seed))
    target.data_dir.mkdir(parents=True)
    destination = target.data_dir / seed.name
    _index(destination, "2", "current")

    event = target._restamp(durability.RESTAMP_OLDER)

    assert event["was"] == "2"
    assert event["restamped_to"] == "1"
    assert event["stamp_case"] == "one-rung-older migration candidate"
    assert _meta(destination, adapter.STAMP_KEY) == "1"


def test_r23_decides_when_the_concrete_adapter_reset_has_stale_sidecars(tmp_path):
    """The repaired adapter arms both R23 directions instead of stopping at not-run.

    Transport is replaced, but storage is not: both resets, both restamps and the
    stale sidecars are handled by the concrete Zoteus adapter. The synthetic
    query models the reviewed target's two schema outcomes — N-1 migrates and
    serves; newer cannot serve — so the expected verdict is FAIL, not a false
    green. What this test guards is that the harness reaches that verdict after
    measuring both arms.
    """
    seed = tmp_path / "seed" / "search-index.sqlite"
    _index(seed, "2", "seeded")
    target = build(tmp_path, seed_index=str(seed))
    target.data_dir.mkdir(parents=True)
    target._seed()
    destination = target.data_dir / seed.name
    starts = 0

    @contextmanager
    def running():
        nonlocal starts
        starts += 1
        try:
            yield
        finally:
            # The older arm's post-restamp process has now stopped. These are
            # the files the old reset left beside the copied seed, causing the
            # newer arm to observe zero rows instead of its own starting state.
            if starts == 3:
                for suffix in ("-wal", "-shm"):
                    destination.with_name(destination.name + suffix).write_bytes(b"stale")

    def query(_q: str, _mode: str, _limit: int) -> dict:
        stamp = _meta(destination, adapter.STAMP_KEY)
        if stamp == "1":
            _set_meta(destination, adapter.STAMP_KEY, "2")
            return {"hits": [{"id": "seeded"}]}
        if stamp == adapter.NEWER_FOREIGN_STAMP:
            return {"hits": []}
        return {"hits": [{"id": "seeded"}]}

    target.running = running
    target.query = query

    check = durability.check_foreign_stamp_ends_up_serving(target)

    assert check.result == "fail", "the newer schema still cannot serve; this is not a green"
    assert set(check.detail["arms"]) == {
        durability.RESTAMP_OLDER, durability.RESTAMP_NEWER}
    assert check.detail["arms"][durability.RESTAMP_OLDER]["serving"] is True
    assert check.detail["arms"][durability.RESTAMP_NEWER]["hits_before_restamp"] == 1
    assert check.detail["arms"][durability.RESTAMP_NEWER]["serving"] is False


@pytest.mark.parametrize("verb", ["pause", "resume"])
def test_background_control_calls_the_named_action(tmp_path, verb):
    target = build(tmp_path)
    calls = []

    class Server:
        def call(self, method, params):
            calls.append((method, params))
            return {"result": {"structuredContent": {"paused": verb == "pause"}}}

    target.server = Server()
    assert target.declaration.offers(verb)
    assert getattr(target, verb)() == {"paused": verb == "pause"}
    assert calls == [("tools/call", {"name": "zotero_index", "arguments": {"action": verb}})]


@pytest.mark.parametrize("body", [
    {"structuredContent": {"message": "Index is paused", "hits": []}},
    {"content": [{"type": "text", "text": '{"message":"Index is paused","hits":[]}'}]},
    {"content": [{"type": "text", "text": "Index is paused"}]},
])
@pytest.mark.parametrize("wrapped", [False, True])
def test_payload_retains_tool_error_and_body(body, wrapped):
    result = {**body, "isError": True}
    response = {"result": result} if wrapped else result
    payload = adapter._payload(response)
    assert payload["isError"] is True
    assert "Index is paused" in str(payload)
    assert "isError" not in body.get("structuredContent", {})


@pytest.mark.parametrize("verb", ["query", "status", "pause", "resume"])
def test_tool_refusal_cannot_be_reported_as_a_success(tmp_path, verb):
    target = build(tmp_path)

    class Server:
        def call(self, method, params):
            return {"result": {"isError": True, "structuredContent": {
                "message": "synthetic refusal", "hits": []}}}

    target.server = Server()
    with pytest.raises(adapter.ToolError, match="synthetic refusal") as error:
        if verb == "query":
            target.query("test", "exact", 1)
        else:
            getattr(target, verb)()
    assert error.value.payload["isError"] is True
    assert error.value.payload["hits"] == []


def test_paused_embedding_perturbation_retains_expected_refusal(tmp_path):
    target = build(tmp_path, seed_index=str(tmp_path / "seed.sqlite"))
    calls = []

    class Server:
        def call(self, method, params):
            calls.append(params["arguments"])
            return {"result": {"isError": True, "structuredContent": {"message": "Index is paused"}}}

    target.server = Server()
    event = target.perturb(durability.RESUME_EMBEDDING)
    assert event["build_started"]["isError"] is True
    assert calls == [{"action": "build", "own_words": False, "fulltext": False}]


def test_successful_empty_search_remains_an_empty_search():
    assert adapter._payload({"result": {"structuredContent": {"hits": []}}}) == {"hits": []}
