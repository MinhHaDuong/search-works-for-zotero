"""Tests for the delta/rebuild classifier in bench/discovery_latency.py (ticket 0503).

The whole measurement turns on one distinction. `action:"update"` falls back to a
FULL REBUILD on six `updateBlocker` conditions (index-manager.ts:1409-1437 @
b0e0bc8), so a tick costs either a cheap delta or a whole library. A harness that
labelled every tick "delta" would report a mean over an unrecorded mix and would
look exactly like a working one -- the "all clear indistinguishable from could
not look" shape. These tests are what make the label mean something.

Only the pure functions are covered. Driving the MCP server needs a built fork, a
live Zotero desktop, and a granted local-API write key; that is the workstation
substrate, not the fast tier.

    python3 -m pytest tests/test_discovery_latency.py -q
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location(
        "dl", REPO / "bench" / "discovery_latency.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dl = load()


# --- classify: the server's own label, not the harness's opinion ---------------------

def test_operation_update_is_a_delta():
    assert dl.classify({"operation": "update", "state": "done"}) == "delta"


def test_operation_build_is_a_rebuild():
    # This is the case the positive control forces: `refresh` empties the index
    # (updateBlocker condition 3), so the following `update` reports operation
    # "build". Reading that as a delta is the defect the control exists to catch.
    assert dl.classify({"operation": "build", "state": "running"}) == "rebuild"


def test_a_resumed_build_is_neither_delta_nor_rebuild():
    # index-tool.ts:127-131 distinguishes three outcomes, not two. Folding "resumed"
    # into either bucket would put a partial build's cost in a distribution that
    # claims to describe whole ones.
    assert dl.classify({"operation": "build", "resumedFrom": 4200}) == "resumed"


def test_a_status_with_no_operation_field_is_not_read_as_a_delta():
    # A missing field means the harness could not look. Defaulting it to "delta"
    # would turn every such tick into a silent false negative, so the safe reading
    # is the expensive one.
    assert dl.classify({}) == "rebuild"


# --- summarize: the two modes are never averaged together ---------------------------

def rep(kind, label, latency):
    return {"kind": kind, "label": label, "latency_s": latency}


def test_delta_and_rebuild_reps_land_in_separate_distributions():
    reps = [
        rep("add", "delta", 2.0),
        rep("add", "delta", 4.0),
        rep("add", "rebuild", 900.0),
    ]
    out = dl.summarize(reps)
    assert set(out) == {"add/delta", "add/rebuild"}
    assert out["add/delta"]["n"] == 2
    assert out["add/rebuild"]["n"] == 1
    # The load-bearing assertion: no key anywhere holds a figure computed across
    # both modes. 900 s must never be allowed to drag the delta median.
    assert out["add/delta"]["max_s"] == 4.0
    assert out["add/rebuild"]["min_s"] == 900.0


def test_add_and_delete_are_also_kept_apart():
    reps = [rep("add", "delta", 2.0), rep("delete", "delta", 8.0)]
    out = dl.summarize(reps)
    assert out["add/delta"]["median_s"] == 2.0
    assert out["delete/delta"]["median_s"] == 8.0


def test_a_rep_that_never_settled_is_excluded_rather_than_counted_as_zero():
    # `one_rep` returns latency_s None when the item never appeared or vanished.
    # Counting that as 0.0 would make a failure look like the fastest possible tick.
    out = dl.summarize([rep("add", "delta", None), rep("add", "delta", 3.0)])
    assert out["add/delta"]["n"] == 1
    assert out["add/delta"]["min_s"] == 3.0


def test_no_reps_yields_no_summary_rather_than_a_zero():
    assert dl.summarize([]) == {}


# --- a failed tool call must not read as data ---------------------------------------

class FakeServer:
    """Stands in for mcp_drive.Server, returning one canned JSON-RPC response."""

    def __init__(self, response):
        self.response = response

    def call(self, method, params=None):
        return self.response


def test_a_tool_returning_iserror_raises_rather_than_returning_a_result():
    # The defect this guards: `visible()` sent the query under the key `query`
    # where the schema names it `q`, so every call came back isError. Unwrapped
    # by payload() and swallowed by a bare except, it read as "not visible yet"
    # and the rep span until its timeout with the item indexed all along.
    s = FakeServer({"result": {"isError": True,
                               "content": [{"type": "text", "text": "invalid arguments"}]}})
    try:
        dl.tool(s, "zotero_semantic_search", {"q": "x"})
    except RuntimeError as e:
        assert "isError" in str(e)
    else:
        raise AssertionError("an isError result was returned as if it were data")


def test_a_json_rpc_error_raises():
    s = FakeServer({"error": {"code": -32602, "message": "Invalid params"}})
    try:
        dl.tool(s, "zotero_index", {"action": "status"})
    except RuntimeError as e:
        assert "rpc error" in str(e)
    else:
        raise AssertionError("a JSON-RPC error was returned as if it were data")


def test_an_ordinary_result_still_comes_back_unwrapped():
    # The control for the two above: they must not be passing because `tool`
    # raises on everything.
    s = FakeServer({"result": {"structuredContent": {"state": "done", "operation": "update"}}})
    assert dl.tool(s, "zotero_index", {"action": "status"}) == {"state": "done",
                                                                "operation": "update"}


# --- a rep that raises still deletes its throwaway ----------------------------------

class SpyWrites:
    """Records creates and deletes so a leak is visible to the test."""

    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, title):
        key = f"KEY{len(self.created)}"
        self.created.append(key)
        return key

    def delete(self, key):
        self.deleted.append(key)


class ExplodingServer:
    """Fails the way a real run fails: on the status poll inside the update."""

    def call(self, method, params=None):
        raise TimeoutError("update did not finish")


def test_an_add_rep_that_raises_still_deletes_its_throwaway():
    # The item is in the author's real library, so cleanup cannot be left to the
    # next invocation's startup sweep. Without the try/finally this leaks KEY0.
    w = SpyWrites()
    try:
        dl.one_rep(ExplodingServer(), w, "zotero_semantic_search", "add", 1,
                   poll_s=0.01, timeout_s=0.1, settle_s=0.1)
    except Exception:
        pass
    assert w.created == ["KEY0"]
    assert w.deleted == ["KEY0"], "the throwaway item was left in the library"


def test_a_delete_rep_that_raises_still_deletes_its_seed_item():
    # The delete rep creates a seed item before it can time anything, and that
    # seed is the one most likely to be stranded: it exists before the first
    # call that can raise.
    w = SpyWrites()
    try:
        dl.one_rep(ExplodingServer(), w, "zotero_semantic_search", "delete", 1,
                   poll_s=0.01, timeout_s=0.1, settle_s=0.1)
    except Exception:
        pass
    assert w.deleted == ["KEY0"], "the seed item was left in the library"


# --- the probe tag is what protects the author's library ----------------------------

def test_throwaway_items_are_identified_by_a_dedicated_tag():
    # The sweep deletes by tag, never by title pattern, so no real item can match.
    assert dl.PROBE_TAG == "zoteus-0503-throwaway"
    assert "0503" in dl.TITLE_PREFIX
