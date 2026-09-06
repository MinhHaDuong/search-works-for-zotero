"""The golden runner (ticket 0722), driven against a stub MCP server.

The stub answers canned hits per query; what is under test is the runner's own work: which
tool and mode it asks for, the k it passes, the replies shape it writes, the not-run modes
it declares, the chain it assembles from the reply plus the replay items, and that the
scorer accepts the result. The real build is exercised by `make golden-run`, not here.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_golden_gate import (
    ALPHA_QUOTE_ART2,
    SPEC,
    alpha_row,
    export_sha,
    make_export,
    question,
    write_bank,
)

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "bench" / "golden_run.py"
STUB = REPO / "tests" / "golden_stub_server.py"

sys.path.insert(0, str(REPO / "bench"))

from golden_gate import evaluate, load_bank, load_export, load_replies, load_thresholds  # noqa: E402


def run_runner(tmp_path, export, bank, hits, extra_args=()):
    hits_path = tmp_path / "hits.json"
    hits_path.write_text(json.dumps(hits), encoding="utf-8")
    log_path = tmp_path / "stub.log"
    output = tmp_path / "replies.json"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    done = subprocess.run(
        [sys.executable, str(RUNNER), "--export", str(export), "--bank", str(bank), "--server", str(STUB),
         "--server-command", sys.executable, "--data-dir", str(data_dir), "--output", str(output),
         "--skip-build", "--no-replay", "--spec", str(SPEC), *extra_args],
        cwd=REPO, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "GOLDEN_STUB_HITS": str(hits_path), "GOLDEN_STUB_LOG": str(log_path),
             "HOME": str(tmp_path)},
    )
    calls = [json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
    return done, output, calls


@pytest.mark.integration
def test_the_runner_asks_the_search_tool_in_keyword_mode_at_k_and_writes_v2_replies(tmp_path):
    export = make_export(tmp_path)
    bank = write_bank(tmp_path, question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)]))
    hits = {"query for q-0001": [
        {"itemKey": "P1ALPHA1", "title": "Alpha, a decision", "snippet": "... " + ALPHA_QUOTE_ART2 + " ...",
         "score": 0.9, "source": "fulltext"},
        {"itemKey": "P3BETA33", "title": "Beta, a treatise", "snippet": "Wealth is", "score": 0.4},
    ]}
    done, output, calls = run_runner(tmp_path, export, bank, hits)
    assert done.returncode == 0, done.stderr

    searches = [c for c in calls if c["method"] == "tools/call" and c["params"]["name"] == "zotero_semantic_search"]
    assert len(searches) == 1
    assert searches[0]["params"]["arguments"] == {
        "q": "query for q-0001", "mode": "keyword", "limit": load_thresholds(SPEC).k, "auto_build": False,
    }

    bundle = json.loads(output.read_text(encoding="utf-8"))
    assert bundle["schema"] == "menagerie-replies/v2"
    run = bundle["run"]
    assert run["export_sha256"] == export_sha(export)
    assert run["recipe_sha256"] == "c" * 64
    assert run["extraction"]["index_fulltext_max_chars"] == 200
    assert run["embedder"] == "none (stub)"
    assert run["chunker"] == "stub-chunker"
    assert run["tool"] == "zotero_semantic_search"
    assert run["reply_shape"]["hit_fields"] == ["itemKey", "score", "snippet", "source", "title"]
    assert run["reply_shape"]["attachment_key_carried"] is False
    assert run["reply_shape"]["page_carried"] is False
    assert run["build"] is None

    by_mode = {reply["mode"]: reply for reply in bundle["replies"]}
    assert set(by_mode) == {"lexical", "semantic", "hybrid"}
    assert by_mode["semantic"]["results"] is None and "embeddings are off" in by_mode["semantic"]["not_run_reason"]
    first = by_mode["lexical"]["results"][0]
    assert first["rank"] == 1 and first["item_key"] == "P1ALPHA1"
    assert first["attachment_key"] is None and first["page"] is None
    assert first["work_id"] == "alpha"
    assert first["evidence"].strip(". ").endswith("9.35 cents")
    assert first["chain"] == {
        "title": "Alpha, a decision", "author": "Author of alpha", "date": "1901",
        "identifier": "https://example.org/alpha", "section_heading": None, "page_printed": None,
        "part_title": None, "part_byline": None,
    }
    assert by_mode["lexical"]["results"][1]["work_id"] == "beta"

    report = evaluate(load_bank(bank), load_replies(bundle), load_export(export), load_thresholds(SPEC))
    entry = report["questions"]["q-0001/lexical"]
    assert entry["level"] == "win" and entry["rank"] == 1
    assert entry["chain"] == {"matched": 4, "of": 5, "fraction": 0.8, "missing": ["section_heading"], "mismatched": []}


@pytest.mark.integration
def test_the_runner_embeds_a_previous_run_and_refuses_a_foreign_one(tmp_path):
    export = make_export(tmp_path)
    bank = write_bank(tmp_path, question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)]))
    hits = {"query for q-0001": [{"itemKey": "P1ALPHA1", "title": "Alpha", "snippet": ALPHA_QUOTE_ART2, "score": 1}]}
    done, first, _ = run_runner(tmp_path, export, bank, hits)
    assert done.returncode == 0, done.stderr
    previous = tmp_path / "previous.json"
    previous.write_text(first.read_text())
    (tmp_path / "again").mkdir()
    done, second, _ = run_runner(tmp_path / "again", export, bank, hits, ["--previous", str(previous)])
    assert done.returncode == 0, done.stderr
    bundle = json.loads(second.read_text())
    assert bundle["previous_run"]["run"]["export_sha256"] == export_sha(export)
    report = evaluate(load_bank(bank), load_replies(bundle), load_export(export), load_thresholds(SPEC))
    assert report["readings"]["stability"]["state"] == "pass"
    assert report["state"] == "pass"

    previous.write_text(json.dumps({"schema": "golden-gate-input/v1"}))
    (tmp_path / "third").mkdir()
    done, _, _ = run_runner(tmp_path / "third", export, bank, hits, ["--previous", str(previous)])
    assert done.returncode == 2
    assert "menagerie-replies/v2" in done.stderr


@pytest.mark.integration
def test_no_hits_is_written_as_an_empty_result_list_not_as_not_run(tmp_path):
    export = make_export(tmp_path)
    bank = write_bank(tmp_path, question("q-0001", [alpha_row("Article 2", ALPHA_QUOTE_ART2)]))
    done, output, _ = run_runner(tmp_path, export, bank, {})
    assert done.returncode == 0, done.stderr
    bundle = json.loads(output.read_text())
    assert [r for r in bundle["replies"] if r["mode"] == "lexical"][0]["results"] == []
