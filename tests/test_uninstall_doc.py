"""The staged UNINSTALL draft stays in step with what the adapter declares.

Ticket 0630, child of tracker 0613. `R15-uninstall-removes-declared-state` is
`not-offered` for zoteus, and the 2026-09-03 ruling settled the surface for
this architecture class: an external MCP server has no host uninstall
lifecycle to hook, so what R15 grades is a *published removal procedure* the
harness can execute verbatim and then sweep. This file guards the one thing
that makes such a procedure gradeable -- that the state it tells a user to
delete is the state the acceptance adapter declares as derived.

The correspondence asserted here is **symbolic, not literal**. The adapter's
`derived_state_roots` resolves to an arena-relative path (`<arena>/data`), a
test fixture no user ever sees; asserting that string appears in the prose
would be tautological, catching a typo in this file and nothing else. Both
sides instead share one symbol -- the `ZOTEUS_DATA_DIR` environment variable,
which the adapter sets to its declared root and which `defaultDataDir()` in
the target's `src/lib/paths.ts` reads first -- and that symbol is what is
matched.

Three clauses, each chosen because a plausible future edit makes it false
while every other gate stays green:

1. exactly one derived-state root is declared, so the doc's single removal
   step is still complete;
2. the removal step names `ZOTEUS_DATA_DIR` and does not name the harness's
   arena path, so the fixture cannot leak into a published document;
3. the model cache is stated to live *under* that root rather than as a
   second location -- the clause upstream PR #27 made true, and the one a
   regression would silently make false again.

Everything here is offline: it constructs the adapter to read its declaration
and reads one file from the repository. No process is spawned.
"""

import importlib
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

adapter = importlib.import_module("bench.acceptance.adapters.zoteus")

DRAFT = REPO / "verification" / "UNINSTALL-DRAFT-0630.md"

#: The symbol the adapter and the target's `defaultDataDir()` share. The doc
#: has to speak in this, not in a resolved path.
DATA_DIR_SYMBOL = "ZOTEUS_DATA_DIR"


@pytest.fixture
def declaration(tmp_path):
    """The adapter's own declaration, built over a throwaway arena."""
    return adapter.Zoteus(tmp_path / "arena",
                          entrypoint=tmp_path / "nowhere" / "index.js").declaration


@pytest.fixture
def draft():
    assert DRAFT.is_file(), f"the staged draft is missing: {DRAFT}"
    return DRAFT.read_text(encoding="utf-8")


def test_the_adapter_declares_exactly_one_derived_state_root(declaration):
    """One root is what makes a single removal step a complete procedure.

    Should a second root ever be declared, the published doc would describe
    an incomplete uninstall while saying nothing about it -- so the count is
    asserted here rather than left to a reader.
    """
    roots = declaration.derived_state_roots
    assert len(roots) == 1, (
        "the draft documents a single removal step; the adapter now declares "
        f"{len(roots)} derived-state roots: {[str(r) for r in roots]}"
    )


def test_the_declared_root_is_the_one_the_data_dir_symbol_carries(declaration, tmp_path):
    """The symbol the doc speaks in resolves, in the harness, to the declared root.

    This is the hinge of the whole correspondence: the doc says
    `ZOTEUS_DATA_DIR`, the adapter says `<arena>/data`, and they mean the same
    directory only because the adapter sets that variable to that path.
    """
    target = adapter.Zoteus(tmp_path / "arena",
                            entrypoint=tmp_path / "nowhere" / "index.js")
    env = target._env()
    assert DATA_DIR_SYMBOL in env, (
        f"the adapter no longer sets {DATA_DIR_SYMBOL}; the doc's removal step "
        "and the declared root no longer share a symbol"
    )
    assert env[DATA_DIR_SYMBOL] == str(target.declaration.derived_state_roots[0]), (
        f"{DATA_DIR_SYMBOL} and the declared derived-state root have diverged"
    )


def test_the_draft_names_the_symbol_and_not_the_arena_path(draft, declaration):
    """The removal step speaks in the env var / OS default, never the fixture.

    An arena path in the prose would mean the harness's own scaffolding had
    been published to users, which is the failure mode the symbolic check
    exists to prevent.
    """
    assert DATA_DIR_SYMBOL in draft, (
        f"the draft never names {DATA_DIR_SYMBOL}; its removal step cannot be "
        "traced to the adapter's declared derived state"
    )
    arena_path = str(declaration.derived_state_roots[0])
    assert arena_path not in draft, (
        f"the harness's arena path leaked into the published draft: {arena_path}"
    )
    assert "acceptance-arena" not in draft, (
        "the harness's arena directory name leaked into the published draft"
    )


def _removal_step(draft: str) -> str:
    """The text of the removal step alone -- list item 3 up to list item 4.

    Scoping matters more here than it looks. An unscoped search over the whole
    document passes on the very regression this file exists to catch: the
    historical 'If you installed before v1.10.0' section names the same symbol
    beside the same word, for the opposite purpose (weights that were *not*
    contained), so deleting the operative containment sentence from the
    removal step leaves an unscoped match standing. Round 1 of the review
    demonstrated exactly that against the first version of this check.
    """
    start = draft.find("\n3. **Delete the data directory.")
    assert start != -1, (
        "the removal step is no longer list item 3 titled 'Delete the data "
        "directory'; this check can no longer find the text it grades"
    )
    end = draft.find("\n4. ", start)
    assert end != -1, "the removal step is not followed by a further step"
    return draft[start:end]


def test_the_draft_places_the_model_cache_under_the_single_root(draft):
    """The removal step itself says the model cache is inside the one root.

    Before upstream PR #27 it was not -- `@huggingface/transformers` cached
    weights inside its own install -- and 'delete the data directory' was an
    incomplete uninstall for exactly that reason. The doc has to state the
    post-#27 containment *where a user acts on it*, in the step that deletes
    the directory, not only in the historical note explaining why it once was
    not true.
    """
    step = _removal_step(draft)
    # The clause is `<ZOTEUS_DATA_DIR>/models`, or the same containment said in
    # prose within one line: the symbol and `models` bound together, not two
    # separate mentions paragraphs apart.
    bound = re.compile(
        r"`?\$?\{?" + DATA_DIR_SYMBOL + r"\}?`?[^\n]{0,80}\bmodels\b",
    )
    assert bound.search(step), (
        "the removal step does not tie the model cache to the declared root; "
        f"it must state that weights live under `<{DATA_DIR_SYMBOL}>/models`, "
        "so that removing the one root removes them too"
    )
