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
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

adapter = importlib.import_module("bench.acceptance.adapters.zoteus")
posture = importlib.import_module("bench.acceptance.posture")


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
