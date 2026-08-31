"""The names guard, exercised against fixture artifacts and the live repository.

Same shape as tests/test_check_chain_dedup.py: each test builds a small artifact
tree under tmp_path and runs the real `run()` against it, so the wiring is
covered and not just the predicate. The defects worth catching are the ones that
actually shipped — a plural `titles`, a prefixed `first_title`, a name nested
three levels down inside a hit list — plus the exemption that makes the rule
usable at all: an artifact may title itself.
"""

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("cn", REPO / "bench" / "check_names.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cn = load()


def build(root, artifacts: dict[str, object]):
    """A fixture repository holding `artifacts` under the results tree."""
    results = root / cn.ARTIFACTS
    results.mkdir(parents=True, exist_ok=True)
    for name, document in artifacts.items():
        path = results / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
    return root


def test_keys_alone_pass(tmp_path):
    build(tmp_path, {"clean.json": {"hits": [{"itemKey": "DH8EXSVA", "score": 0.9}]}})
    assert cn.run(tmp_path) == 0


def test_a_nested_title_fails(tmp_path):
    build(tmp_path, {"leak.json": {"hits": [{"itemKey": "DH8EXSVA", "title": "A Book"}]}})
    assert cn.run(tmp_path) == 1


def test_an_artifact_may_title_itself(tmp_path):
    """Depth 0 is the artifact describing itself, not a document it touched."""
    build(tmp_path, {"summary.json": {"title": "Memory baseline", "peak_mib": 2046.1}})
    assert cn.run(tmp_path) == 0


def test_the_plural_and_the_prefixed_variant_are_caught(tmp_path):
    """Both shipped. A rule that only knows `title` would have missed both."""
    build(tmp_path, {"a.json": {"runs": [{"titles": ["A Book"]}]},
                     "b.json": {"per_query": [{"first_title": "a-file.pdf"}]}})
    assert cn.run(tmp_path) == 1


def test_a_name_deep_inside_a_list_is_found(tmp_path):
    build(tmp_path, {"deep.json": {"passes": [{"queries": [{"hits": [{"creators": "Someone"}]}]}]}})
    assert cn.offences(json.loads((tmp_path / cn.ARTIFACTS / "deep.json").read_text()))


def test_unreadable_artifact_fails_rather_than_passing_quietly(tmp_path):
    (tmp_path / cn.ARTIFACTS).mkdir(parents=True)
    (tmp_path / cn.ARTIFACTS / "broken.json").write_text("{not json", encoding="utf-8")
    assert cn.run(tmp_path) == 1


def test_missing_results_tree_fails(tmp_path):
    assert cn.run(tmp_path) == 1


def test_the_live_repository_names_no_documents():
    assert cn.run(REPO) == 0
