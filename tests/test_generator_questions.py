"""The ticket-0719 question writer, with the model mocked.

The lane assignment is the load-bearing part — a run's cross-lingual share is
a declared number and the seed must reproduce it — and the model is a process
boundary this tier never crosses: the node driver is replaced by a function
returning what a model would print, including the blank reply the fallback
exists for.
"""

import importlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

Q = importlib.import_module("bench.generator.questions")

PARA = ("The carbon tax was introduced in two thousand and fourteen under the name of the climate energy "
        "contribution, at a rate that rose every year until the protests froze it, and the freeze has held.")


def rows(n: int, language: str = "en") -> list[dict]:
    return [{"paragraph": PARA, "language": language, "item_key": f"K{i}"} for i in range(n)]


def test_lanes_follow_the_declared_share_and_cycle_the_other_languages():
    lanes = Q.assign_lanes(rows(300), 1 / 3, seed=1)
    cross = [lang for lang in lanes if lang != "en"]
    assert 70 <= len(cross) <= 130
    assert set(cross) == {"fr", "vi"} and abs(cross.count("fr") - cross.count("vi")) <= 1
    assert Q.assign_lanes(rows(300), 1 / 3, seed=1) == lanes
    assert Q.assign_lanes(rows(300), 0.0, seed=1) == ["en"] * 300
    assert set(Q.assign_lanes(rows(50, "vi"), 1.0, seed=2)) == {"en", "fr"}
    assert Q.assign_lanes(rows(3, "und"), 0.0, seed=0) == ["en"] * 3


def test_template_question_is_deterministic_and_in_the_lane_language():
    q = Q.template_question(PARA, "fr")
    assert q.startswith("Que dit le texte sur") and q.endswith("?")
    assert q == Q.template_question(PARA, "fr")
    assert Q.template_question(PARA, "vi").startswith("Văn bản")
    assert Q.template_question(PARA, "und").startswith("What does")
    words = Q.distinctive_words(PARA)
    assert len(words) == 3 and all(len(w) >= 6 for w in words) and "contribution" in words


def test_clean_and_acceptable():
    assert Q.clean_question('  "Question: When was the carbon tax introduced?"\nsecond line') == "When was the carbon tax introduced?"
    assert Q.clean_question("") == ""
    assert Q.acceptable("When was the carbon tax introduced in France?", PARA)
    assert not Q.acceptable("Yes", PARA)
    assert not Q.acceptable(PARA[:60], PARA)


def fake_run(stdout_lines):
    calls = []

    def run(cmd, input, capture_output, text):
        calls.append({"cmd": cmd, "input": input})
        return subprocess.CompletedProcess(cmd, 0, stdout="\n".join(stdout_lines) + "\n", stderr="")
    run.calls = calls
    return run


def test_tjs_writer_parses_the_model_and_falls_back_on_a_blank_reply():
    out = [json.dumps({"id": 0, "question": "When was the carbon tax introduced?", "elapsed_ms": 120}),
           json.dumps({"id": 1, "question": "", "elapsed_ms": 90})]
    run = fake_run(out)
    writer = Q.TjsWriter("/tp", "some/model", "/cache", run=run)
    rs = rows(2)
    rs[0]["question_language"] = "en"
    rs[1]["question_language"] = "fr"
    written = writer.write(rs)
    assert written[0] == {"question": "When was the carbon tax introduced?", "writer": "tjs", "elapsed_ms": 120}
    assert written[1]["writer"] == "template-fallback" and written[1]["question"].startswith("Que dit")
    cmd = run.calls[0]["cmd"]
    assert cmd[0] == "node" and cmd[1].endswith("tjs_generate.mjs") and "--model" in cmd
    sent = [json.loads(line) for line in run.calls[0]["input"].splitlines()]
    assert [s["language"] for s in sent] == ["en", "fr"] and sent[0]["paragraph"] == PARA


def test_tjs_writer_reports_a_failed_process():
    def run(cmd, input, capture_output, text):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
    writer = Q.TjsWriter("/tp", "m", "/c", run=run)
    try:
        writer.write([{"paragraph": PARA, "question_language": "en"}])
    except RuntimeError as e:
        assert "boom" in str(e)
    else:
        raise AssertionError("a failed writer must raise, not return template questions silently")


def test_write_questions_records_lane_writer_and_model():
    writer = Q.TemplateWriter()
    rs = Q.write_questions(rows(6, "fr"), writer, share=0.5, seed=3)
    assert all(r["lane"] == f"{r['question_language']}->fr" for r in rs)
    assert any(r["cross_lingual"] for r in rs) and any(not r["cross_lingual"] for r in rs)
    assert all(r["writer"] == "template" and r["model"] == "deterministic template" for r in rs)
    summary = Q.questions_summary(rs, writer, 0.5)
    assert summary["n"] == 6 and summary["cross_lingual"] == sum(r["cross_lingual"] for r in rs)
    assert set(summary["lanes"]) <= {"fr->fr", "en->fr", "vi->fr"}
    assert "paragraph" not in json.dumps(summary) and PARA[:30] not in json.dumps(summary)


def test_the_driver_script_ships_beside_the_writer():
    script = REPO / "bench" / "generator" / "tjs_generate.mjs"
    assert script.is_file()
    source = script.read_text()
    assert "text-generation" in source and "cacheDir" in source
    assert "fetch(" not in source.replace("do_sample", ""), "the driver reaches no service of its own"
