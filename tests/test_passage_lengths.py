"""Fast tests for bench/passage_lengths.py, the passage-length distribution of ticket 0029.

What earns a test here is not the arithmetic of a quantile. It is the two claims a reader
of R32 has to take on faith otherwise:

* **the population is the build's**, not a plausible re-chunking of the same text. The
  script re-implements `chunkText`, `itemText` and `createFulltextSource` in Python, and a
  re-implementation that agrees with nothing is a guess; the test that earns its place runs
  the counting model over the committed export and holds it against the four counters a
  built `fork/` reported after building that same export through the offline replay
  (`bench/results/golden/report.json`). It fails against a wrong population — a chunk size
  off by one, the per-item cap applied per attachment, a census-only attachment folded into
  "absent" — and it fails against the absence of the tool.
* **the artifact is pinned to the export**, so a distribution read against a moved export is
  caught rather than believed. That check is exercised in both directions: it passes on the
  committed pair and comes out red on a doctored one, because a staleness check that cannot
  fire is not a check.

The chunker port is tested against hand-computed boundaries rather than against itself.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "passage_lengths", REPO / "bench" / "passage_lengths.py")
passage_lengths = importlib.util.module_from_spec(_spec)
sys.modules["passage_lengths"] = passage_lengths
_spec.loader.exec_module(passage_lengths)


class _FakeExport:
    """The narrow surface `build_passages` reads, over a corpus written for one question.

    Only the parts of `golden_gate.Export` the counting model touches: the attachment rows,
    the items, the parent map and the fulltext accessor. Building a real export would take
    a manifest, a recipe and a validator, none of which is under test here.
    """

    def __init__(self, attachments: dict[str, tuple[str, str]]):
        self._text = {key: text for key, (_, text) in attachments.items()}
        self.attachments = {
            key: {"attachment_key": key, "attachment_id": f"slug-{key}", "parent_key": parent,
                  "fulltext_file": f"fulltext/{key}.json", "fulltext_version": 1,
                  "terminal_state": "indexed", "language": "en"}
            for key, (parent, _) in attachments.items()
        }
        self.parent_of = {key: parent for key, (parent, _) in attachments.items()}
        self.items = {"P": {"key": "P", "itemType": "book", "title": "Parent"}}
        for key, (parent, _) in attachments.items():
            self.items[key] = {"key": key, "itemType": "attachment", "parentItem": parent,
                               "contentType": "application/pdf"}

    def fulltext(self, key: str) -> str | None:
        return self._text.get(key)

    def format_of(self, key: str) -> str:
        return "pdf"


@pytest.fixture(scope="module")
def measured():
    """One measurement of the committed export, shared by every test that reads it."""
    golden_gate = passage_lengths._load_golden_gate()
    export = golden_gate.load_export(passage_lengths.EXPORT)
    status = passage_lengths.load_status(passage_lengths.REPORT)
    return passage_lengths.build(export, status)


# --------------------------------------------------------------------------- the chunker port


def test_short_text_is_one_passage_and_whitespace_is_collapsed():
    spans = passage_lengths.chunk_spans("a  b\n\nc", 512, 64)
    assert spans == [(0, 5)]  # "a b c"


def test_blank_text_yields_no_passage_rather_than_an_empty_one():
    assert passage_lengths.chunk_spans("   \n\t ", 512, 64) == []


def test_a_cut_snaps_back_to_the_last_space_past_the_halfway_mark():
    # The cut at 10 lands mid-word; the space at index 6 is past 0 + 10/2, so it wins.
    spans = passage_lengths.chunk_spans("abcdef ghijklmnop", 10, 2)
    assert spans[0] == (0, 6)


def test_a_cut_does_not_snap_when_the_only_space_is_before_the_halfway_mark():
    # One space at index 1, which is not past 0 + 10/2: the chunker cuts at `size`.
    spans = passage_lengths.chunk_spans("a " + "b" * 30, 10, 2)
    assert spans[0] == (0, 10)


def test_consecutive_passages_overlap_by_the_declared_amount():
    spans = passage_lengths.chunk_spans("x" * 100, 20, 5)
    assert spans[0] == (0, 20)
    assert spans[1][0] == 15  # 20 − 5


def test_an_unsplittable_run_still_advances_rather_than_looping():
    # `start = max(end - overlap, start + 1)` is what stops an overlap at or above the
    # size from standing still; without it the build never terminates.
    spans = passage_lengths.chunk_spans("x" * 50, 10, 10)
    assert len(spans) == len({s for s, _ in spans})
    assert spans[-1][1] == 50


def test_item_text_joins_the_builds_fields_in_the_builds_order():
    text = passage_lengths.item_text({
        "title": "T", "abstractNote": "A",
        "creators": [{"lastName": "Last"}, {"name": "Solo"}],
        "tags": [{"tag": "one"}, {"tag": "two"}],
        "date": "1871", "publicationTitle": "P", "bookTitle": "B", "note": "N",
    })
    assert text == "T. A. Last Solo. one two. 1871. P. B. N"


def test_item_text_drops_empty_fields_instead_of_leaving_a_bare_separator():
    assert passage_lengths.item_text({"title": "T", "date": "1871"}) == "T. 1871"
    assert passage_lengths.item_text({}) == ""


# --------------------------------------------------------------------------- the population


def test_the_counted_population_is_the_one_the_shipped_build_produced(measured):
    """The control: four counters computed here against four a real build reported.

    `bench/results/golden/report.json` holds the status a built `fork/` printed after
    building this export through the offline replay. Nothing in this file could produce
    those numbers by construction — they come from the TypeScript that ships — so an
    agreement on all four is evidence that the passage population modelled here is the one
    R32's rate would be divided by.
    """
    check = measured["cross_check"]
    assert check["compared"] is not None, "the golden-gate report is missing; cross-check void"
    assert check["agrees"], check["differences"]
    assert check["counted"]["passages"] == check["compared"]["passages"]


def test_the_cross_check_can_come_out_wrong(measured):
    """A cross-check whose disagreement is unrepresentable is not a cross-check."""
    status = {"passages": 7, "fulltextPassages": 4, "ownWordsPassages": 0,
              "items": 3, "fulltextItems": 2}
    passages = [passage_lengths.Passage("k#0", "k", "metadata", "text", ())]
    check = passage_lengths.cross_check(passages, status)
    assert check["agrees"] is False
    assert check["differences"]["passages"] == 1 - 7
    assert check["differences"]["fulltext_passages"] == 0 - 4


def test_a_missing_report_is_a_cross_check_not_taken_not_a_passing_one():
    check = passage_lengths.cross_check([], None)
    assert check["compared"] is None
    assert "agrees" not in check
    assert check["reason"]


def test_metadata_and_fulltext_are_cut_at_different_sizes(measured):
    """Two populations, two geometries; folding them would move every quantile.

    The two overlap at the short end — a body passage can be the last, sub-size one of its
    item — so the separation to assert is between the metadata ceiling and the body
    median, not between the extremes.
    """
    metadata = measured["distribution"]["metadata"]["chars"]
    fulltext = measured["distribution"]["fulltext"]["chars"]
    assert metadata["max"] <= passage_lengths.METADATA_CHUNK_SIZE
    assert fulltext["max"] <= passage_lengths.FULLTEXT_CHUNK_SIZE
    assert metadata["max"] < fulltext["p50"]


def test_the_character_cap_is_spent_per_item_not_per_attachment():
    """The plausible wrong reading of `fulltext-source.ts`, isolated.

    `textFor` accumulates ONE budget across every attachment of an item, so a second
    attachment gets only what the first left. Reading the cap per attachment would double
    the body text of a two-attachment item and every quantile downstream of it. The real
    corpus cannot separate the two — each of its 89 contributing attachments happens to
    belong to a different item — so the discriminating case is built here.
    """
    export = _FakeExport({
        "A1": ("P", "x " * 15000),   # 30 000 characters
        "A2": ("P", "y " * 15000),   # another 30 000
    })
    _, ledger = passage_lengths.build_passages(export, 40000)
    assert ledger["A1"]["chars_indexed"] == 30000
    assert ledger["A2"]["chars_indexed"] == 10000  # what the first left, not 30 000
    assert ledger["A1"]["chars_indexed"] + ledger["A2"]["chars_indexed"] == 40000


def test_an_attachment_reached_after_the_cap_is_spent_contributes_nothing():
    export = _FakeExport({"A1": ("P", "x " * 25000), "A2": ("P", "y " * 100)})
    _, ledger = passage_lengths.build_passages(export, 40000)
    assert ledger["A1"]["chars_indexed"] == 40000
    assert ledger["A2"]["chars_indexed"] == 0
    assert "cap" in ledger["A2"]["reason_no_passage"]


def test_no_attachment_is_indexed_past_the_cap(measured):
    cap = measured["export"]["index_fulltext_max_chars"]
    for row in measured["per_attachment"]["truncated_by_the_item_cap"]:
        assert row["chars_indexed"] <= cap
        assert row["chars_indexed"] < row["chars_available"]


def test_the_extremes_are_named_by_key_and_slug_not_by_title(measured):
    for row in measured["tails"]["heaviest_bytes"] + measured["tails"]["shortest_chars"]:
        assert "title" not in row
        for attachment in row["attachments"]:
            assert attachment["attachment_key"]
            assert attachment["attachment_id"]


def test_an_attachment_with_no_passages_says_which_kind_of_nothing_it_is(measured):
    """A count of zero and a measurement not taken are different findings.

    An attachment absent from Zotero's census, one listed but answering 404 on its route,
    one whose extraction returned an empty body, and one the item's character cap cut off
    all produce zero passages and are four different facts about the corpus. Every silent
    attachment carries its reason, and `chars_available` is null exactly when the export
    holds no body to measure.
    """
    silent = measured["per_attachment"]["no_passage"]
    assert silent, "the corpus was built to contain formats that extract nothing"
    for row in silent:
        assert row["reason"], row["attachment_id"]
    kinds = {row["reason"].split(":")[0] for row in silent}
    assert len(kinds) >= 3, kinds
    for row in silent:
        if row["chars_available"] is None:
            assert "404" in row["reason"] or "census" in row["reason"] or "cap" in row["reason"]


def test_every_body_passage_is_attributed_to_an_attachment(measured):
    """A passage nobody owns cannot be explained, and the tail is the point of the artifact."""
    attributed = measured["per_attachment"]["passages_per_attachment"]["total"]
    assert attributed == measured["population"]["by_source"]["fulltext"]


def test_the_language_split_covers_the_whole_body_population(measured):
    """Every body passage lands in exactly one language bucket, so the split can be read."""
    body = sum(block["passages"] for name, block in measured["by_language"].items()
               if name != "(metadata)")
    assert body == measured["population"]["by_source"]["fulltext"]
    assert measured["by_language"]["(metadata)"]["passages"] == \
        measured["population"]["by_source"]["metadata"]


def test_bytes_per_character_separates_the_scripts(measured):
    """The reason a rate does not transfer between corpora, as a measured quantity.

    A Latin-script passage costs about one byte per character and a Devanagari one about
    two and a half, at the same character length. If this ever collapsed to a single
    figure the artifact would have stopped saying anything R32 needs.
    """
    latin = measured["by_language"]["en"]["bytes_per_char"]
    heavy = max(block["bytes_per_char"] for name, block in measured["by_language"].items()
                if name not in {"(metadata)", "en"})
    assert latin < 1.1
    assert heavy > 2.0


def test_the_character_index_matches_javascripts(measured):
    """The port indexes in code points; the chunker indexes in UTF-16 code units.

    The two agree only while nothing is outside the BMP. This is measured rather than
    assumed, and a future export carrying an astral character makes the count non-zero.
    """
    assert measured["geometry"]["astral_characters"] == 0


# --------------------------------------------------------------------------- the pin


def test_the_committed_artifact_describes_the_committed_export(measured):
    """The whole reason the distribution is 'pinned beside the export'."""
    committed = json.loads(passage_lengths.ARTIFACT.read_text(encoding="utf-8"))
    assert passage_lengths.stale(committed, measured) == []
    assert committed["export"]["sha256"] == measured["export"]["sha256"]


def test_the_staleness_check_fires_when_the_export_moves(measured):
    """The positive control. A stamp nothing compares is decoration."""
    committed = json.loads(passage_lengths.ARTIFACT.read_text(encoding="utf-8"))
    moved = json.loads(json.dumps(committed))
    moved["export"]["sha256"] = "0" * 64
    findings = passage_lengths.stale(moved, measured)
    assert findings and "export.sha256" in findings[0]


def test_the_staleness_check_fires_when_the_population_moves_under_an_unchanged_stamp(measured):
    """The other half: the sha covers the manifest, the counts cover the bodies."""
    committed = json.loads(passage_lengths.ARTIFACT.read_text(encoding="utf-8"))
    edited = json.loads(json.dumps(committed))
    edited["population"]["passages"] += 1
    findings = passage_lengths.stale(edited, measured)
    assert any("population.passages" in finding for finding in findings)


def test_the_artifact_names_what_it_did_not_measure(measured):
    """Token lengths are absent, not estimated, and the experiment is named."""
    assert "tokens" in measured["not_measured"]
    assert "passage_census" in measured["not_measured"]["tokens"]
    assert "§5.2.2" in measured["geometry"]["not_this"]
