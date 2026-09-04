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
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

adapter = importlib.import_module("bench.acceptance.adapters.zoteus")
posture = importlib.import_module("bench.acceptance.posture")


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
