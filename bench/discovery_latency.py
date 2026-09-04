#!/usr/bin/env python3
"""Measure what one reconcile tick costs, for ticket 0503.

Upstream has no discovery cadence of its own: `startIndexUpdate` has exactly one
call site in `src/`, reached only when an MCP caller passes `action:"update"`
(verification/UPSTREAM-DISCOVERY-0503.md). So there is no upstream latency to
measure. What this script measures is the thing SPEC.md 5.2.4's 60 s reconcile
tick has to fit inside: the cost of one `action:"update"` run, plus the
item-census fetch that precedes it.

The update path is bimodal. `updateBlocker` (index-manager.ts:1409-1437 @
b0e0bc8) makes `action:"update"` fall back to a FULL REBUILD on six conditions,
and `index-tool.ts:124-131` is where the server itself labels which happened,
off `status.operation`. A mean over an unrecorded mix of the two reports
nothing, so every poll's `operation` is recorded and the two distributions are
emitted apart, never averaged.

Before any rep is trusted, a positive control runs: the first `action:"update"`
is issued against an EMPTY index (updateBlocker condition 3), so it is GUARANTEED
to fall back to a full rebuild. If this harness labels that tick "delta", the
classifier is broken and the run aborts -- without this control a harness that
always reported "delta" would pass silently on every rep.

The control has to be issued against an index that is empty AT THE MOMENT OF THE
CALL, which is subtler than it looks. A first attempt ran `action:"refresh"` and
polled it to `done` before calling `action:"update"`, per this ticket's own
sketch -- but `refresh` rebuilds the index, so by the time the update was issued
condition 3 no longer held and that tick was a genuine 1.0 s delta. The control
caught it and aborted the run, which is exactly why it runs before the reps
rather than after. Starting from a wiped data dir is what actually forces the
fallback, and it establishes the delta-path precondition in the same run instead
of paying for two rebuilds.

Writes go straight to Zotero's local API, never through the server (which runs
read-only). Every item written is a throwaway created for the measurement and
deleted again; no real library item is touched.
"""
import argparse
import json
import logging
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_drive import Server  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("0503")

PROBE_TAG = "zoteus-0503-throwaway"
TITLE_PREFIX = "ZOTEUS0503PROBE"


# --------------------------------------------------------------------------- MCP


def payload(resp: dict) -> dict:
    """Unwrap an MCP tool result into the structured dict the tools return."""
    r = resp.get("result", resp)
    if "structuredContent" in r:
        return r["structuredContent"]
    for block in r.get("content", []):
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return {"text": block["text"][:4000]}
    return r


def tool(s: Server, name: str, args: dict) -> dict:
    """Call one MCP tool, refusing to hand back an error as if it were data.

    JSON-RPC errors and `isError` tool results are both checked here rather than
    at each call site, because `payload()` unwraps an error's text block into
    something that reads like an ordinary result.
    """
    resp = s.call("tools/call", {"name": name, "arguments": args})
    if "error" in resp:
        raise RuntimeError(f"{name} rpc error: {json.dumps(resp['error'])[:400]}")
    if resp.get("result", {}).get("isError"):
        raise RuntimeError(f"{name} returned isError: {json.dumps(resp['result'])[:400]}")
    return payload(resp)


def classify(status: dict) -> str:
    """The server's own label, read exactly as src/tools/index-tool.ts:127-131 reads it.

    Reproduced rather than invented so the harness cannot disagree with the server
    about what a tick was.
    """
    if status.get("operation") == "update":
        return "delta"
    if status.get("resumedFrom"):
        return "resumed"
    return "rebuild"


def run_to_done(s: Server, action: str, poll_s: float, timeout_s: float) -> dict:
    """Start an index action and poll to `state:"done"`, recording every poll.

    Returns the wall-clock cost and the set of operation labels seen across the
    whole run -- not just the last one, because a run that starts as one mode and
    is re-labelled mid-flight would otherwise be recorded as whichever mode
    happened to be showing when it finished.
    """
    t0 = time.monotonic()
    started = tool(s, "zotero_index", {"action": action})
    polls = [{"t": 0.0, "operation": started.get("operation"), "state": started.get("state")}]
    labels = {classify(started)}
    last = started
    while True:
        if time.monotonic() - t0 > timeout_s:
            raise TimeoutError(f"{action} did not finish within {timeout_s}s")
        time.sleep(poll_s)
        last = tool(s, "zotero_index", {"action": "status"})
        labels.add(classify(last))
        polls.append({
            "t": round(time.monotonic() - t0, 3),
            "operation": last.get("operation"),
            "state": last.get("state"),
            "phase": last.get("phase"),
        })
        if last.get("state") == "done":
            break
    # A run is a rebuild if it was EVER labelled one; "delta" is the claim that
    # needs every poll to agree with it.
    label = "delta" if labels == {"delta"} else ("rebuild" if "rebuild" in labels else "resumed")
    return {
        "action": action,
        "elapsed_s": round(time.monotonic() - t0, 3),
        "label": label,
        "labels_seen": sorted(labels),
        "polls": polls,
        "status": last,
    }


# ----------------------------------------------------------------- Zotero local API


class LocalWrites:
    """Minimal Zotero 10+ local-API write client.

    Not a reimplementation of upstream's `src/api/local-writes.ts` for its own
    sake -- the server under test runs READ-ONLY here on purpose, so the mutations
    this measurement needs have to come from outside it. The protocol is the one
    that file documents: probe a `Zotero-Server-ID` with a GET, echo it on every
    write, carry the granted key, and send `If-Unmodified-Since-Version`.
    """

    def __init__(self, base: str, key: str):
        self.base = base.rstrip("/")
        self.key = key
        self.server_id, self.version = self._probe()

    def _probe(self) -> tuple[str, int]:
        req = urllib.request.Request(f"{self.base}/users/0/items/top?limit=1")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.headers["Zotero-Server-ID"], int(r.headers["Last-Modified-Version"])

    def _req(self, method: str, path: str, body: object | None) -> tuple[int, str]:
        self.server_id, self.version = self._probe()
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.base}{path}", data=data, method=method)
        req.add_header("Zotero-Server-ID", self.server_id)
        req.add_header("Zotero-API-Key", self.key)
        req.add_header("If-Unmodified-Since-Version", str(self.version))
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def create(self, title: str) -> str:
        code, text = self._req("POST", "/users/0/items", [{
            "itemType": "journalArticle",
            "title": title,
            "creators": [],
            "tags": [{"tag": PROBE_TAG}],
        }])
        if code != 200:
            raise RuntimeError(f"create failed HTTP {code}: {text[:400]}")
        body = json.loads(text)
        if body.get("failed"):
            raise RuntimeError(f"create rejected: {body['failed']}")
        return body["success"]["0"]

    def delete(self, key: str) -> None:
        code, text = self._req("DELETE", f"/users/0/items/{key}", None)
        if code not in (204, 404):
            raise RuntimeError(f"delete failed HTTP {code}: {text[:400]}")

    def sweep_probes(self) -> list[str]:
        """Delete every leftover throwaway this harness has ever created.

        The invariant this run must not break is that nothing of the author's is
        touched, so the sweep is keyed on the probe tag alone -- never on a title
        pattern that a real item could happen to match.
        """
        url = f"{self.base}/users/0/items/top?tag={PROBE_TAG}&limit=100"
        with urllib.request.urlopen(url, timeout=30) as r:
            items = json.loads(r.read().decode())
        keys = [i["key"] for i in items]
        for k in keys:
            self.delete(k)
        return keys


def item_census(base: str, since: int | None) -> dict:
    """Time SPEC.md 5.2.4's per-tick item census: the `?since=` fetch.

    This is the number 5.2.4 itself flags as unmeasured, unlike the full-text
    census beside it. Two arms, because a tick's cost depends on which it does:
    the incremental `?since=` fetch, and the full key-set fetch that
    deletion-by-subtraction needs.
    """
    out = {}
    for name, url in (
        ("since", f"{base}/users/0/items/top?since={since}&format=keys" if since is not None else None),
        ("full_keyset", f"{base}/users/0/items/top?format=keys&limit=100000"),
    ):
        if url is None:
            continue
        t0 = time.monotonic()
        with urllib.request.urlopen(url, timeout=300) as r:
            text = r.read().decode()
        out[name] = {
            "elapsed_s": round(time.monotonic() - t0, 3),
            "keys": len([ln for ln in text.splitlines() if ln.strip()]),
            "bytes": len(text),
        }
    return out


# ------------------------------------------------------------------------- search


def visible(s: Server, search_tool: str, title: str) -> bool:
    """Is this item served by the index yet?

    A throwaway metadata-only item has no attachment, so there is no `/fulltext`
    entry to watch appear or vanish; the honest equivalent for both directions is
    whether the search perimeter serves it, which is what R35 promises anyway.

    A failed call RAISES rather than returning False. An earlier version sent the
    query under the key `query` where the tool's schema names it `q`
    (semantic-search.ts:22), so every call was a schema error caught by a bare
    `except` and read as "not visible yet" -- the poll loop then span until its
    30-minute timeout on a rep whose item was in the index all along. That is the
    all-clear-indistinguishable-from-could-not-look shape, one level down from
    the one the positive control guards, and it has to fail loudly instead.
    """
    r = tool(s, search_tool, {"q": title, "limit": 20})
    return title in json.dumps(r, ensure_ascii=False)


# --------------------------------------------------------------------------- reps


def one_rep(s: Server, w: LocalWrites, search_tool: str, kind: str, n: int,
            poll_s: float, timeout_s: float, settle_s: float) -> dict:
    """One add-rep or one delete-rep, timed from the library mutation.

    `t0` is the mutation, not the `action:"update"` call, so the figure includes
    everything a caller would wait through.
    """
    title = f"{TITLE_PREFIX} {kind} {n} {int(time.time())}"
    key = None
    if kind == "delete":
        # The item has to be in the index before its removal can be timed.
        key = w.create(title)
        run_to_done(s, "update", poll_s, timeout_s)
        if not visible(s, search_tool, title):
            return {"kind": kind, "n": n, "result": "skipped",
                    "why": "seed item never became visible; nothing to time its removal against"}

    t0 = time.monotonic()
    if kind == "add":
        key = w.create(title)
    else:
        w.delete(key)
        key = None

    run = run_to_done(s, "update", poll_s, timeout_s)
    want = (kind == "add")
    t_settled = None
    # Bounded separately from the build timeout: once the update run has
    # finished, the item either is served or is not, and a long spin here means a
    # broken check rather than a slow index.
    while time.monotonic() - t0 < settle_s:
        if visible(s, search_tool, title) == want:
            t_settled = time.monotonic() - t0
            break
        time.sleep(poll_s)

    if key is not None:
        w.delete(key)
    return {
        "kind": kind,
        "n": n,
        "result": "ok" if t_settled is not None else "not-settled",
        "latency_s": round(t_settled, 3) if t_settled is not None else None,
        "update_run": run,
        "label": run["label"],
    }


def summarize(reps: list[dict]) -> dict:
    """Report the two modes apart. Never one mean over the mix -- that is the
    whole point of the 2026-09-02T21:04Z finding this ticket exists to honor."""
    out = {}
    for kind in ("add", "delete"):
        for label in ("delta", "rebuild", "resumed"):
            xs = [r["latency_s"] for r in reps
                  if r["kind"] == kind and r["label"] == label
                  and r.get("latency_s") is not None]
            if not xs:
                continue
            xs = sorted(xs)
            out[f"{kind}/{label}"] = {
                "n": len(xs),
                "min_s": xs[0],
                "median_s": xs[len(xs) // 2],
                "max_s": xs[-1],
            }
    return out


# ---------------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", required=True, help="path to the built fork's MCP entrypoint")
    ap.add_argument("--data-dir", required=True, help="index data dir (created if absent)")
    ap.add_argument("--local-api", default="http://127.0.0.1:23119/api")
    ap.add_argument("--local-key", required=True, help="granted Zotero local-API write key")
    ap.add_argument("--out", required=True, help="where to write the result JSON")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--poll", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--settle-timeout", type=float, default=300,
                    help="how long a rep waits for the item to appear/vanish after the update run")
    ap.add_argument("--zotero-data-dir", default=None)
    a = ap.parse_args()

    data_dir = Path(a.data_dir)
    # The positive control needs an index that is empty when the first
    # `action:"update"` is issued, so the dir starts wiped. It is a scratch dir
    # this script owns; nothing else reads it.
    if data_dir.exists():
        for f in data_dir.iterdir():
            if f.is_file():
                f.unlink()
    data_dir.mkdir(parents=True, exist_ok=True)
    env = {
        "ZOTEUS_EMBEDDINGS": "off",
        "ZOTEUS_DATA_DIR": str(data_dir),
        "ZOTEUS_INDEX_BACKEND": "sqlite",
        "ZOTEUS_INDEX_FULLTEXT": "1",
        "ZOTEUS_READ_ONLY": "true",
        "ZOTEUS_UPDATE_CHECK": "0",
        # Default is 5000, which silently indexes 5000 of the library's 7546
        # top-level items and would make every figure here describe a two-thirds
        # library while claiming SPEC.md's population.
        "ZOTEUS_INDEX_MAX_ITEMS": "100000",
    }
    if a.zotero_data_dir:
        env["ZOTERO_DATA_DIR"] = a.zotero_data_dir

    w = LocalWrites(a.local_api, a.local_key)
    swept = w.sweep_probes()
    if swept:
        log.info("swept %d leftover probe item(s) before starting: %s", len(swept), swept)

    s = Server(["node", a.server], env, timeout=a.timeout)
    s.handshake()
    tools = [t["name"] for t in s.call("tools/list")["result"]["tools"]]
    search_tool = next((t for t in ("zotero_semantic_search", "zotero_search") if t in tools), None)
    if search_tool is None:
        raise SystemExit(f"no search tool among {tools}")
    log.info("search tool: %s", search_tool)

    record: dict = {
        "machine": subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip(),
        "upstream_sha": Path("UPSTREAM").read_text().split("UPSTREAM_REVIEWED_SHA=")[1].split("\n")[0],
        "env": env,
        "search_tool": search_tool,
    }

    # --- POSITIVE CONTROL, and the precondition, in one run.
    # The data dir was wiped above, so this `action:"update"` meets updateBlocker
    # condition 3 (empty index) and MUST fall back to a full rebuild. If it is
    # labelled a delta, the classifier is broken and every "delta" below would be
    # a false negative -- so no rep is reported at all.
    log.info("positive control: update against an empty index (must classify as rebuild) ...")
    control = run_to_done(s, "update", a.poll, a.timeout)
    record["positive_control"] = control
    if control["label"] != "rebuild":
        record["positive_control"]["verdict"] = "FAILED"
        Path(a.out).write_text(json.dumps(record, indent=2, ensure_ascii=False))
        raise SystemExit(
            f"POSITIVE CONTROL FAILED: forced full rebuild classified as {control['label']!r}. "
            "The delta/rebuild classifier cannot be trusted; no rep is reported.")
    record["positive_control"]["verdict"] = "passed"
    log.info("positive control passed (%s, %.1fs)", control["label"], control["elapsed_s"])

    # That rebuild leaves a completed same-backend, same-embedder SQLite index,
    # which is the delta-path precondition: four of updateBlocker's six conditions
    # are satisfied by construction, and the remaining two (backend mismatch,
    # embedder mismatch) cannot fire because neither is switched from here on.
    st = control["status"]
    record["library_scope"] = {
        "endpoint": "/items/top",
        "items_indexed": st.get("items"),
        "items_available": st.get("itemsAvailable"),
        "libraryVersion": st.get("libraryVersion"),
        "fulltextItems": st.get("fulltextItems"),
        "fulltextPassages": st.get("fulltextPassages"),
    }
    if not st.get("libraryVersion"):
        raise SystemExit("rebuild carried no libraryVersion stamp -- delta path not established")
    if st.get("items") != st.get("itemsAvailable"):
        raise SystemExit(
            f"indexed {st.get('items')} of {st.get('itemsAvailable')} available items -- "
            "raise ZOTEUS_INDEX_MAX_ITEMS; a partial library would misreport the scope")

    # --- item census, measured against the stamp the rebuild recorded.
    record["item_census"] = item_census(a.local_api, st.get("libraryVersion"))

    # --- reps.
    reps: list[dict] = []
    for kind in ("add", "delete"):
        for n in range(1, a.reps + 1):
            log.info("rep %s #%d ...", kind, n)
            reps.append(one_rep(s, w, search_tool, kind, n, a.poll, a.timeout, a.settle_timeout))
    record["reps"] = reps
    record["summary"] = summarize(reps)

    leftover = w.sweep_probes()
    record["cleanup"] = {"leftover_probe_items_removed": leftover}

    s.p.terminate()
    Path(a.out).write_text(json.dumps(record, indent=2, ensure_ascii=False))
    log.info("wrote %s", a.out)
    print(json.dumps(record["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
