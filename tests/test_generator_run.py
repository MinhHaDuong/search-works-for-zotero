"""The ticket-0719 runner, with the target faked.

The runner's own logic is small — read the scope off the index file, put each
question through the `query` verb, aggregate — and each piece is exercised
here without a process: a fake target answers `query` from a table and its
`server.call` answers the build poll. The one thing that must not be faked is
the argument parser, whose two shared options (`--transformers-path`,
`--zotero-data-dir`) once collided at runtime and were caught only by a live
run; `build_parser()` is now built here on every test.
"""

import importlib
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

R = importlib.import_module("bench.generator.run")

PARA = ("The carbon tax was introduced in two thousand and fourteen under the name of the climate energy "
        "contribution, at a rate that rose every year until the protests froze it, and the freeze has held.")


class FakeServer:
    def __init__(self, states):
        self.states = list(states)
        self.calls = []

    def call(self, method, params):
        self.calls.append(params)
        action = params["arguments"]["action"]
        if action == "build":
            return {"result": {"structuredContent": {"started": True}}}
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return {"result": {"structuredContent": {"state": state, "items": 3, "passages": 40, "vectors": 40,
                                                 "embedder": "local", "phase": "fulltext"}}}


class FakeTarget:
    def __init__(self, replies, states=("building", "done")):
        self.replies = replies
        self.server = FakeServer(states)
        self.queries = []

    def query(self, q, mode, limit):
        self.queries.append((q, mode, limit))
        reply = dict(self.replies.get(q, {"hits": []}))
        reply.update({"embedder": "local", "embedderActive": mode != "exact", "vectors": 40})
        return reply


def row(i, q, lane="en->en", fmt="pdf", cross=False, cap=True):
    return {"item_key": f"ITEM{i}", "paragraph": PARA, "question": q, "lane": lane, "cross_lingual": cross,
            "format": fmt, "type_group": "journalArticle", "length_bucket": "short", "within_default_cap": cap,
            "writer": "template", "chain": {"title": {"value": f"T{i}"}, "identifier": {"value": None}}}


def test_index_item_keys_reads_the_index_file_identified_by_its_meta_table(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    con = sqlite3.connect(data / "aaa-not-an-index.sqlite")
    con.execute("CREATE TABLE items (item_key TEXT)")
    con.commit()
    con.close()
    con = sqlite3.connect(data / "search-index.sqlite")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("CREATE TABLE items (item_key TEXT PRIMARY KEY, title TEXT NOT NULL)")
    con.executemany("INSERT INTO items VALUES (?, ?)", [("K1", "a"), ("K2", "b")])
    con.commit()
    con.close()
    path, keys = R.index_item_keys(data)
    assert path.name == "search-index.sqlite" and sorted(keys) == ["K1", "K2"]
    assert R.index_item_keys(tmp_path / "empty") == (None, [])


def test_build_index_polls_until_done_and_records_the_cost():
    target = FakeTarget({}, states=("building", "building", "done"))
    record = R.build_index(target, limit=30, timeout_s=60, poll_s=0.0)
    assert record["limit"] == 30 and not record["timed_out"]
    assert record["status"]["state"] == "done" and record["status"]["vectors"] == 40
    build_call = target.server.calls[0]["arguments"]
    assert build_call == {"action": "build", "fulltext": True, "limit": 30, "auto_build": False}


def test_ask_puts_every_question_through_every_mode_and_reads_the_evidence():
    hit = {"itemKey": "ITEM1", "title": "T1", "snippet": "under the name of the climate energy contribution, at a rate"}
    target = FakeTarget({"q1": {"hits": [{"itemKey": "X", "title": "x", "snippet": "no"}, hit]},
                         "q2": {"hits": [], "isError": True}})
    readings, evidence = R.ask(target, [row(1, "q1"), row(2, "q2", lane="fr->en", cross=True)], top_k=10)
    assert [(q, m) for q, m, _ in target.queries] == [("q1", "combined"), ("q1", "exact"), ("q1", "meaning"),
                                                       ("q2", "combined"), ("q2", "exact"), ("q2", "meaning")]
    assert readings[0]["score"]["verdict"] == "win" and readings[0]["score"]["row_rank"] == 2
    assert readings[0]["by_mode"]["exact"]["verdict"] == "win" and readings[0]["by_mode"]["meaning"]["row_rank"] == 2
    assert readings[1]["score"]["verdict"] == "miss" and readings[1]["reply_error"]
    # The mode map is the adapter's own, and the evidence is what the reply said.
    assert evidence["combined"]["target_mode"] == "auto" and evidence["exact"]["target_mode"] == "keyword"
    assert evidence["exact"]["embedderActive"] is False and evidence["meaning"]["embedderActive"] is True
    doc = R.report(readings, {"n": 2}, {"n": 2})
    assert doc["ladder"]["by_lane"]["fr->en"]["miss"] == 1
    assert doc["ladder"]["by_mode"]["exact"]["win"] == 1 and doc["ladder"]["by_mode_and_lane"]["meaning"]["en->en"]["n"] == 1
    assert doc["ladder"]["by_cross_lingual"]["cross-lingual"]["n"] == 1
    assert doc["ladder"]["by_compound"]["simple"]["n"] == 2
    assert doc["ladder"]["by_reachability"]["within-cap"]["n"] == 2
    assert doc["chain_in_reply"]["answer_rows_found"] == 1
    assert "self-consistency" in doc["self_consistency_note"]
    md = R.markdown(doc)
    assert "| fr->en | 1 | 0 | 0 | 1 |" in md and "by retrieval mode" in md


def test_the_parser_builds_without_option_collisions():
    ap = R.build_parser()
    ns = ap.parse_args(["--entrypoint", "e", "--arena", "a", "--work-dir", "w", "--output", "o",
                        "--census", "c", "--transformers-path", "t", "--zotero-data-dir", "z", "--n", "7",
                        "--writer", "llama-server", "--endpoint", "http://127.0.0.1:1", "--scope-items", "50"])
    assert ns.transformers_path == "t" and ns.zotero_data_dir == "z" and ns.n == 7
    assert ns.scope_items == 50 and ns.endpoint == "http://127.0.0.1:1" and not ns.reuse_index
    assert ns.sampling == "random"


def test_the_artifact_carries_no_row_level_text():
    """The report is aggregates: a reading's paragraph, question and key never reach it."""
    hit = {"itemKey": "ITEM1", "title": "T1", "snippet": "under the name of the climate energy contribution, at a rate"}
    target = FakeTarget({"what is the carbon tax": {"hits": [hit]}})
    readings, _ = R.ask(target, [row(1, "what is the carbon tax")], top_k=10)
    text = json.dumps(R.report(readings, {"n": 1}, {"n": 1}))
    for secret in (PARA[:25], "what is the carbon tax", "ITEM1", "T1"):
        assert secret not in text
