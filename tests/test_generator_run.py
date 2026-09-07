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
from argparse import Namespace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

R = importlib.import_module("bench.generator.run")

PARA = ("The carbon tax was introduced in two thousand and fourteen under the name of the climate energy "
        "contribution, at a rate that rose every year until the protests froze it, and the freeze has held.")


class FakeServer:
    def __init__(self, states, extra=None):
        self.states = list(states)
        self.calls = []
        #: Extra status fields a real target reports and a test wants back
        #: (`embedderModel`, which the build record must not drop).
        self.extra = dict(extra or {})

    def call(self, method, params):
        self.calls.append(params)
        action = params["arguments"]["action"]
        if action == "build":
            return {"result": {"structuredContent": {"started": True}}}
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return {"result": {"structuredContent": {"state": state, "items": 3, "passages": 40, "vectors": 40,
                                                 "embedder": "local", "phase": "fulltext", **self.extra}}}


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
    assert doc["ladder"]["by_mode_and_cross_lingual"]["exact"]["cross-lingual"]["miss"] == 1
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


def test_refresh_recomputes_the_ladder_from_the_readings_and_keeps_the_identity(tmp_path):
    refresh = importlib.import_module("bench.generator.refresh")
    hit = {"itemKey": "ITEM1", "title": "T1", "snippet": "under the name of the climate energy contribution, at a rate"}
    target = FakeTarget({"q1": {"hits": [hit]}})
    secret = row(1, "q1")
    secret["chain"]["title"]["value"] = "SecretTitleXYZ"
    readings, _ = R.ask(target, [secret], top_k=10)
    work = tmp_path / "work"
    work.mkdir()
    (work / "readings.jsonl").write_text("\n".join(json.dumps(r) for r in readings) + "\n")
    out = tmp_path / "run.json"
    stale = {"identity": {"seed": 9}, "sample": {"n": 1}, "questions": {"n": 1}, "ladder": {}, "chain_in_reply": {}, "readings": {}}
    out.write_text(json.dumps(stale))
    doc = refresh.refresh(out, work)
    assert doc["identity"] == {"seed": 9} and doc["sample"] == {"n": 1}
    assert doc["ladder"]["by_lane"]["all"]["win"] == 1 and doc["ladder"]["by_mode"]["exact"]["n"] == 1
    assert doc["chain_in_reply"]["answer_rows_found"] == 1 and len(doc["refreshed"]) == 1
    assert "ITEM1" not in json.dumps(doc) and "SecretTitleXYZ" not in json.dumps(doc) and PARA[:25] not in json.dumps(doc)


# -- the embedder behind the vectors (ticket 0732) ---------------------------
#
# The 0719 artifact recorded `embedder: "local"` — a provider — and nothing
# else, and a near-zero cross-lingual reading has two opposite meanings
# depending on which model that provider loaded. These check that the model, at
# its resolved precision and pooling, reaches the artifact, and that the two
# defaults the target elides from its own stamp are written out rather than left
# implicit in exactly the arm the field exists to name.


def index_with_stamp(tmp_path, stamp):
    """A minimal index file carrying the embedder identity a build stamps on it."""
    path = tmp_path / "search-index.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('embedderId', ?)", (stamp,))
    con.commit()
    con.close()
    return path


class FakeDeclaration:
    def as_json(self):
        return {"target": "zoteus"}


class FakeWriter:
    name = "template"
    model = None


def identity_args(tmp_path):
    return Namespace(seed=1, base_url="http://127.0.0.1:23119/api", fulltext_cap=4000, top_k=10,
                     other_language_share=0.3333, census=tmp_path / "census.json")


def run_identity(tmp_path, status, stamp, env, evidence=None, models_dir=None):
    evidence = evidence if evidence is not None else {"combined": {"embedder": "local"}}
    index_file = index_with_stamp(tmp_path, stamp) if stamp is not None else None
    embedder = R.embedder_identity(status, R.index_embedder_stamp(index_file), evidence, env,
                                   models_dir or (tmp_path / "models"))
    target = type("T", (), {"declaration": FakeDeclaration()})()
    return R.identity(identity_args(tmp_path), {}, target, None, index_file, 3, FakeWriter(), None, None,
                      evidence, embedder)


def test_the_run_identity_names_the_model_and_not_only_the_provider(tmp_path):
    """The defect this closes: `local` is a provider, and both readings of the
    cross-lingual near-zero are `local`."""
    ident = run_identity(tmp_path, {"embedder": "local", "embedderActive": True},
                         "local:Xenova/multilingual-e5-small", {})
    assert ident["embedder"]["model"] == "Xenova/multilingual-e5-small"
    assert ident["embedder"]["model_source"] == "index stamp"
    assert "Xenova/multilingual-e5-small" in json.dumps(ident)


def test_a_default_run_writes_fp32_and_mean_out_though_the_stamp_elides_them(tmp_path):
    """The elision trap: the target leaves the default dtype and pooling OFF the
    stamp on purpose, so the arm that most needs them named is the one whose
    string is silent about them."""
    stamp = "local:Xenova/all-MiniLM-L6-v2"
    ident = run_identity(tmp_path, {"embedder": "local", "embedderActive": True}, stamp, {})
    e = ident["embedder"]
    assert e["index_stamp"] == stamp and "@" not in stamp and "#" not in stamp
    assert e["dtype"] == "fp32" and e["pooling"] == "mean"
    assert e["resolved_from_stamp_elision"] == ["dtype", "pooling"]


def test_a_non_default_stamp_is_read_as_written():
    expanded = R.expand_embedder_stamp("local:onnx-community/gte-multilingual-base@q8#cls")
    assert expanded["provider"] == "local" and expanded["model"] == "onnx-community/gte-multilingual-base"
    assert expanded["dtype"] == "q8" and expanded["pooling"] == "cls" and expanded["elided"] == []
    assert R.expand_embedder_stamp("") is None and R.expand_embedder_stamp(None) is None


def test_build_index_keeps_the_model_the_status_names():
    """`embedder` alone made the build record unreadable the same way."""
    target = FakeTarget({}, states=("done",))
    target.server.extra = {"embedderModel": "Xenova/all-MiniLM-L6-v2", "embedderConfigured": "local"}
    record = R.build_index(target, limit=3, timeout_s=60, poll_s=0.0)
    assert record["status"]["embedderModel"] == "Xenova/all-MiniLM-L6-v2"


def test_no_vectors_means_unmeasured_pooling_not_a_default_filled_in(tmp_path):
    """An index that wrote no vectors stamps the empty string. Nothing then
    witnessed the build, and an `auto` pooling lives in a table inside the
    target: that is a thing this run could not measure, and it says so rather
    than writing `mean` and being believed."""
    ident = run_identity(tmp_path, {"embedder": "local", "embedderActive": False,
                                    "embedderModel": "Xenova/all-MiniLM-L6-v2"}, "", {})
    e = ident["embedder"]
    assert e["index_stamp"] is None and e["model_source"] == "index status"
    assert e["pooling"] is None and "unmeasured" in e
    assert R.embedder_identity({}, None, {}, {"ZOTEUS_EMBEDDING_POOLING": "cls"},
                               tmp_path / "models")["pooling"] == "cls"


def test_a_stamp_that_disagrees_with_the_live_status_is_reported_as_the_vectors(tmp_path):
    ident = run_identity(tmp_path, {"embedder": "local", "embedderModel": "Xenova/multilingual-e5-small"},
                         "local:Xenova/all-MiniLM-L6-v2", {})
    e = ident["embedder"]
    assert e["model"] == "Xenova/all-MiniLM-L6-v2" and "disagreement" in e


def test_the_input_template_is_the_registrys_and_is_expected_never_observed(tmp_path):
    """The target applies the E5 markers by inference on the id and reports
    nothing about it, so the run records what the REGISTRY declares the model
    wants — one model name, one place — and marks the read-back unavailable."""
    declared = R.declared_template(R.registry_record("Xenova/multilingual-e5-small"))
    e = R.embedder_identity({"embedder": "local"}, "local:Xenova/multilingual-e5-small", {},
                            {}, tmp_path / "models")
    assert declared and e["prefixes"]["expected"] == declared
    assert e["registry"]["id"] == "multilingual-e5-small"
    assert e["revision"]["declared"] == R.registry_record("Xenova/multilingual-e5-small")["hf_revision"]
    assert e["prefixes"]["observed"] is None and e["query_reply_names_model"] is False
    # The incumbent declares an empty template, which is a declaration of "no
    # markers" and not an absence.
    mini = R.embedder_identity({"embedder": "local"}, "local:Xenova/all-MiniLM-L6-v2", {}, {},
                               tmp_path / "models")
    assert mini["prefixes"]["expected"] is None and mini["registry"]["id"] == "all-minilm-l6-v2"
    off = R.embedder_identity({"embedder": "local"}, "local:Xenova/multilingual-e5-small", {},
                              {"ZOTEUS_EMBEDDING_PREFIXES": "off"}, tmp_path / "models")
    assert off["prefixes"]["expected"] is None and off["prefixes"]["setting"] == "off"


def test_a_model_the_registry_does_not_declare_is_unresolved_not_marker_free(tmp_path):
    """A nil template from a missing record and a declared empty template are
    different facts, and only the second means the model wants no markers."""
    e = R.embedder_identity({"embedder": "local"}, "local:someone/an-undeclared-model", {}, {},
                            tmp_path / "models")
    assert e["registry"] is None and e["revision"]["declared"] is None
    assert e["prefixes"]["expected"] is None and "unresolved" in e["prefixes"]["expected_from"]


def test_pooling_that_departs_from_the_registry_is_called_out(tmp_path):
    """The stamp says how the vectors were pooled, the registry says how the
    model was trained; the two disagreeing is a silent retrieval loss."""
    e = R.embedder_identity({"embedder": "local"}, "local:Xenova/multilingual-e5-small#cls", {}, {},
                            tmp_path / "models")
    assert e["pooling"] == "cls" and "pooling_disagrees_with_registry" in e
    agreeing = R.embedder_identity({"embedder": "local"}, "local:Xenova/multilingual-e5-small", {}, {},
                                   tmp_path / "models")
    assert agreeing["pooling"] == "mean" and "pooling_disagrees_with_registry" not in agreeing


def test_the_weights_are_identified_by_content_since_the_target_pins_no_revision(tmp_path):
    models = tmp_path / "models"
    (models / "Xenova/all-MiniLM-L6-v2/onnx").mkdir(parents=True)
    (models / "Xenova/all-MiniLM-L6-v2/onnx/model.onnx").write_bytes(b"weights")
    d = R.weights_digest(models, "Xenova/all-MiniLM-L6-v2")
    assert d["present"] and d["bytes"] == 7
    assert d["files"][0]["path"] == "onnx/model.onnx" and len(d["files"][0]["sha256"]) == 64
    absent = R.weights_digest(models, "Xenova/multilingual-e5-small")
    assert absent["present"] is False and "reason" in absent
