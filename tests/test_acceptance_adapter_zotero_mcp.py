"""The zotero-mcp adapter's declaration is honest about what it can and cannot do.

Ticket 0585. Four defect classes, each of which turns one of the four states
into a lie, and none of which needs the target installed:

1. **A declaration and a method that disagree.** `not-offered` is only worth
   having if `Declaration.unsupported` and the methods that raise
   `UnsupportedVerb` name the same three verbs. Let them drift and a verb the
   adapter refuses is reported as a failure of the target, or a verb it declares
   absent quietly returns a result.
2. **A sandbox that is not one.** HOME is this target's only sandbox mechanism —
   `--config-path` relocates part of one root out of five — so a declaration
   whose roots are not all under the sandbox HOME points the residue sweep at
   the operator's real state. The sweep deletes.
3. **A mode reported as an empty result.** `Declaration.unsupported` is a set of
   verbs, so it cannot say that `combined` has no implementation and `meaning`
   needs an extra the documented install does not pull. The adapter says it in
   the returned dict instead, and this asserts it says it there — an unreachable
   mode answering "no hits" is indistinguishable from a target that found none.
4. **A silent mode substitution.** R33's clause is that the mode selected is the
   mode served. `zotero_search_items` escalates to semantic search on an empty
   result set and discloses it in prose only, so the parse of that prose is the
   whole measurement. Its failure mode is silent: an unrecognised note reads as
   "no escalation happened", which is the answer that passes.

Every test here runs offline, spawns nothing and writes only under tmp_path.
"""

import importlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

interface = importlib.import_module("bench.acceptance.interface")
adapter = importlib.import_module("bench.acceptance.adapters.zotero_mcp")


def build(tmp_path) -> object:
    """An adapter on a sandbox HOME and a venv prefix that need not exist."""
    return adapter.ZoteroMCP(home=tmp_path / "home", venv=tmp_path / "venv")


# --- 1. the declaration reads with nothing installed ------------------------


def test_the_declaration_reads_without_the_target_or_the_transport(tmp_path):
    """The cheapest contract check must not depend on the target being present.

    `declaration()` is a free function for this reason; if it ever reaches for
    the stdio driver or the venv, a contract check on a clean machine fails for
    a reason that has nothing to do with the contract.
    """
    declared = adapter.declaration(tmp_path / "home")
    assert isinstance(declared, interface.Declaration)
    assert declared.name == "54yyyu/zotero-mcp"
    assert declared.derived_state_roots, "a target that writes nothing is a claim"


def test_the_revision_pins_a_full_commit_and_names_the_distribution(tmp_path):
    """An abbreviated SHA and the repository's name are both wrong pins.

    The distribution on PyPI is `zotero-mcp-server`; `pip install zotero-mcp`
    installs an unrelated package. Both mistakes were live in the tree this
    adapter was written from — `server.json` there still says 0.9.1.
    """
    assert len(adapter.COMMIT) == 40 and all(c in "0123456789abcdef" for c in adapter.COMMIT)
    revision = adapter.declaration(tmp_path / "home").revision
    assert adapter.DISTRIBUTION in revision
    assert adapter.COMMIT in revision


def test_the_recorded_closure_exists_and_pins_the_declared_version():
    """`revision` points at a lock file; a pointer to a missing file pins nothing.

    The revision string cannot carry this target's behaviour on its own — most
    of its egress and most of its derived state come from fastmcp, chromadb and
    onnxruntime. The lock is the part that can, so it has to be there and it has
    to agree with the version the adapter declares.
    """
    assert adapter.LOCK.exists(), f"{adapter.LOCK} is named by the declaration"
    lines = adapter.LOCK.read_text(encoding="utf-8").splitlines()
    pins = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    assert f"{adapter.DISTRIBUTION}=={adapter.VERSION}" in pins
    assert "chromadb" not in " ".join(pins), (
        "the recorded closure is the DEFAULT install; a chromadb in it means the "
        "[semantic] extra was installed and the lock no longer describes what an "
        "ordinary user gets"
    )


# --- 2. the sandbox --------------------------------------------------------


def test_every_derived_state_root_is_inside_the_sandbox(tmp_path):
    """A root outside the sandbox HOME aims the residue sweep at real state.

    Five roots, three of them created by dependencies at paths this target's own
    source never names. Any one of them written with `Path.home()` instead of
    the declared home would still look right in a code review.
    """
    home = tmp_path / "home"
    for root in adapter.declaration(home).derived_state_roots:
        assert home in root.parents or root == home, f"{root} escapes the sandbox"


def test_construction_on_the_operators_own_home_is_refused():
    """The destructive reading of this declaration, blocked rather than documented.

    With no sandbox, the five roots land in the operator's real state and the
    sweep that reads this declaration then deletes from it. The alternative to a
    guard here is trusting that every future caller passes a sandbox.
    """
    with pytest.raises(ValueError, match="HOME"):
        adapter.ZoteroMCP(home=Path.home(), venv=Path("/nonexistent"))


def test_the_environment_blanks_every_variable_the_target_reads(tmp_path):
    """An exported OPENAI_API_KEY would silently stop this being the default config.

    `mcp_drive.Server` merges the adapter's environment over `os.environ` and
    cannot delete a name, so "absent" is spelled as the empty string. A variable
    dropped from the list is a hole nothing else closes.
    """
    env = build(tmp_path).environment()
    assert env["HOME"] == str((tmp_path / "home").resolve())
    for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "ZOTERO_API_KEY",
                 "ZOTERO_LOCAL", "XDG_CACHE_HOME", "ZOTERO_EMBEDDING_MODEL"):
        assert env[name] == "", f"{name} is a channel into the default configuration"


# --- 3. the declaration and the methods agree ------------------------------


def test_the_three_absent_verbs_raise_rather_than_return(tmp_path):
    """A declared-absent verb that returns a value is a `not-offered` nobody sees.

    `UnsupportedVerb` is an exception rather than a sentinel precisely so an
    assertion that forgets to consult `offers` cannot read a `None` as a red.
    """
    target = build(tmp_path)
    assert target.declaration.unsupported == frozenset({"uninstall", "pause", "resume"})
    for verb in sorted(target.declaration.unsupported):
        with pytest.raises(interface.UnsupportedVerb):
            getattr(target, verb)()


def test_every_offered_verb_exists_and_no_offered_verb_declares_itself_absent(tmp_path):
    """The other half of the drift: a verb the declaration offers must be callable.

    This does not call them — three need a process — it checks the pairing, which
    is what makes the four states mean anything.
    """
    target = build(tmp_path)
    for verb in interface.VERBS:
        assert callable(getattr(target, verb)), f"{verb} is not implemented"
        assert target.declaration.offers(verb) is (verb not in {"uninstall", "pause", "resume"})


def test_configure_writes_the_file_the_readme_documents_editing(tmp_path):
    """The wizard is a stdin dialogue; the file is the access an ordinary user has.

    Driving the wizard would be a workaround, which the contract forbids. What is
    checked here is that `configure` writes where the target reads and nowhere
    else — under the sandbox, not under the operator's config directory.
    """
    target = build(tmp_path)
    written = target.configure()
    path = Path(written["path"])
    assert path == tmp_path / "home" / ".config" / "zotero-mcp" / "config.json"
    assert path.exists()
    assert "semantic_search" in path.read_text(encoding="utf-8")


# --- 4. modes ---------------------------------------------------------------


def test_a_mode_with_no_implementation_is_not_reported_as_an_empty_result(tmp_path):
    """`combined` does not exist on this target and must not look like zero hits.

    No fusion of any kind is implemented — the reason belongs in the answer,
    because `Declaration.unsupported` holds verbs and cannot hold a mode. The
    call must also not need a process: an unreachable mode is decided by the
    declaration, not by asking the target.
    """
    answer = build(tmp_path).query("anything", "combined", 5)
    assert answer["served"] is False
    assert answer["mode_served"] is None
    assert answer["hits"] is None
    assert "fusion" in answer["why"]


def test_meaning_is_unreachable_without_the_optional_extra(tmp_path):
    """A tool that is listed and answers with an install hint is not a capability.

    The documented install command pulls no `[semantic]` extra, so on the default
    configuration `zotero_semantic_search` is a surface with nothing behind it.
    Reporting that as a failed query would score the target for a mode it never
    claimed to serve by default.
    """
    target = build(tmp_path)
    assert target.semantic_installed() is False
    answer = target.query("anything", "meaning", 5)
    assert answer["served"] is False
    assert "[semantic]" in answer["why"]


def test_an_escalation_to_semantic_search_is_reported_as_the_mode_served(tmp_path, monkeypatch):
    """R33 measured: the mode selected must be the mode served, and here it isn't.

    `zotero_search_items` runs a four-strategy cascade on an empty result set and
    discloses the substitution as a prose note with no machine-readable field. If
    the parse of that note ever stops matching, the failure is silent and lands
    on the passing side: an unrecognised note reads as "exact answered".
    """
    target = build(tmp_path)
    note = ("*Note: Original search for 'x' returned no results. The following 3 "
            "item(s) are semantically related papers found via AI-powered search "
            "— they may be ABOUT the same topic…*")
    monkeypatch.setattr(target, "_tool", lambda name, args: _reply(note))
    answer = target.query("x", "exact", 5)
    assert answer["mode_requested"] == "exact"
    assert answer["mode_served"] == "meaning", "a substituted mode was reported as served"


def test_a_reply_carrying_no_escalation_note_keeps_the_requested_mode(tmp_path, monkeypatch):
    """The control for the test above: without a note, nothing may be substituted.

    Without this, a parse that matched every reply would pass the escalation test
    and report `meaning` for every search the target ever ran.
    """
    target = build(tmp_path)
    monkeypatch.setattr(target, "_tool",
                        lambda name, args: _reply("# Search Results for 'x'\n\n1. …"))
    answer = target.query("x", "exact", 5)
    assert answer["mode_served"] == "exact"
    assert answer["escalation"] is None


def test_the_full_text_escalation_is_recognised_too(tmp_path, monkeypatch):
    """The cascade has four exits, not one; three of them stay within `exact`.

    Recognising only the semantic exit would leave the other three reported as
    "no escalation", which is the same silent pass the control above guards.
    """
    target = build(tmp_path)
    note = "*Note: Original search for 'x' returned no results. Found 2 item(s) via full-text search — verify…*"
    monkeypatch.setattr(target, "_tool", lambda name, args: _reply(note))
    answer = target.query("x", "exact", 5)
    assert answer["mode_served"] == "exact"
    assert answer["escalation"] == "via full-text search"


def test_status_parses_the_targets_own_field_lines_and_keeps_the_block(tmp_path, monkeypatch):
    """Status here is prose; the parse is convenience and the raw block is evidence.

    An assertion that trusted only the parse would silently lose every term the
    target does not print — and it prints no denominator, no per-stage split, no
    coverage split and no pause line.
    """
    target = build(tmp_path)
    block = ("# Semantic Search Database Status\n\n## Collection Information\n"
             "**Name:** zotero_items\n**Document Count:** 0\n"
             "**Embedding Model:** default\n")
    monkeypatch.setattr(target, "_tool", lambda name, args: _reply(block))
    answer = target.status()
    assert answer["fields"]["Document Count"] == "0"
    assert answer["raw"] == block
    for absent in ("Denominator", "Paused", "Coverage"):
        assert absent not in answer["fields"]


def _reply(text: str) -> dict:
    """A tools/call reply in the shape the driver hands back."""
    return {"result": {"content": [{"type": "text", "text": text}]}}
