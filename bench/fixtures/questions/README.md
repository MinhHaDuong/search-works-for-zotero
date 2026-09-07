# The Menagerie question bank — schema `menagerie-bank/v3`

Ticket 0722, implementing the author's rulings of 2026-09-06. One JSON file per
question, `q-NNNN.json`, in this flat directory; `bank.schema.json` is the same
record as a JSON Schema (draft 2020-12). `bench/golden_gate.py` reads the bank
(`validate`, `score`, `shape`), `bench/golden_run.py` drives it through a build
and writes the replies file the scorer reads.

## What a question is

An **answer** is a paragraph in a page in a file attached to a Zotero entry; a
pageless file locates by character number. A **reply** scores win, near-win or
miss on (a) the rank at which the answer paragraph appears in the first k
results (k is read from SPEC.md §5.2.8, today 10) and (b) the completeness of
its citation chain. The same work returned in another rendering or language in
place of the answer paragraph is a near-win. Rank and mean reciprocal rank are
reported per lane and never gated (D11).

The **primary set** is a set of rows. A row is what a reply can show apart: a
work, or a section of a work (R24 collapses declared renderings and
deduplicates per section). Two answer paragraphs in the same section of the
same work are one row with two `alternates`; any alternate found is the row
found. Paragraphs in different sections or works are separate rows, each scored
on the ladder by its own rank and chain completeness.

`set_kind` says how rows combine. **any-of**: the question scores on its best
row. **all-of**: the gate keeps R34's absolute reading (every primary row within
the first k, or the question fails) and the ladder reads on the weakest row —
win only if every row wins, near-win if every row is at least a near-win, miss
if any row is absent. An all-of set is small, a handful, never near k. The
report carries per-row detail: the fraction of rows found and each row's rank.

A **no-answer question** carries an empty primary set and `expected_miss: true`.
It passes when the reply's first k contain no primary row (there are none) and
is reported apart, never in the ladder. An answer that exists on the page but
is **unreachable in the export** — the attachment is a failure control, has no
text layer, or the quote cannot be located in what Zotero extracted — stays in
the bank as an expected-miss question naming its mechanism; the validator
refuses an unreachable alternate on any other question.

## The record

```json
{
  "schema": "menagerie-bank/v3",
  "id": "q-0001",
  "need": "Written before opening the document: ...",
  "query": "feed-in tariff for grid-connected solar power projects in Vietnam 2017",
  "question_language": "en",
  "answer_language": "en",
  "lane": "en->en",
  "signal": "exact",
  "mode": "any",
  "facet": "core",
  "stratum": "core",
  "mechanism": [],
  "generator": "need",
  "set_kind": "any-of",
  "primary": [
    {
      "work_id": "vn-decision-11-2017-qdttg-solar-fit-en",
      "recipe_id": "vn-decision-11-2017-qdttg-solar-fit-en",
      "attachment_id": null,
      "attachment_key": "L68LPREA",
      "section": "Article 12",
      "alternates": [
        {"page_printed": null, "char_offset": 10203, "quote": "The buyer has the responsibility to purchase ..."}
      ],
      "chain": {
        "title": "Decision No. 11/2017/QĐ-TTg on the mechanism ...",
        "author": "Thủ tướng Chính phủ (Prime Minister of Vietnam)",
        "date": "2017",
        "identifier": "https://faolex.fao.org/docs/pdf/vie179224.pdf",
        "section_heading": "Article 12. Feed in Tariff",
        "page_printed": null,
        "part_title": null,
        "part_byline": null
      }
    }
  ],
  "expected_miss": false,
  "expected_miss_mechanism": null,
  "reachability": { "...computed by validate --stamp, see below..." },
  "provenance": {"author": "...", "date": "2026-09-06", "page_read": true}
}
```

| field | meaning |
|---|---|
| `id` | `q-` + four or more digits; equals the file name's stem. |
| `need` | The information need in prose, written **before any document was opened** for a need-driven question. |
| `query` | The string sent to the system. |
| `question_language`, `answer_language` | BCP-47 primary tags; the answer language is that of the answer paragraph. |
| `lane` | The pair, `<question_language>-><answer_language>`; the validator checks it. |
| `signal` | `exact` (the query's words are on the page), `paraphrase` (the meaning is, the words are not), `agreement` (the page agrees with the query's claim). |
| `mode` | `lexical`, `semantic`, `hybrid`, or `any`; a reply in a mode the question does not allow is refused. |
| `facet` | `core`, `notes`, `group`, `deep-body` (the export's facets, SPEC §5.2.8). |
| `stratum` | `core` (the representative sample) or `reserve` (the adversarial one); never pooled unweighted. |
| `mechanism` | Names of the pathology rows the question consumes (the coverage ledger's vocabulary, free strings); a list, under the singular name SPEC.md §5.2.10 gives it. |
| `generator` | `need` (from an information need) or `hazard` (from a mechanism or tally sub-case). |
| `set_kind` | `any-of` or `all-of`. |
| `primary` | The primary answer set: the rows, never more than k of them; empty only on an expected-miss question. |
| `expected_miss`, `expected_miss_mechanism` | The flag and, when set, the mechanism in words; each requires the other. |
| `reachability` | **Computed, not authored** — see below. `null` until stamped. |
| `provenance` | Who pinned it, when (ISO date), and whether the printed page was read (`page_read`). |
| `retained_reason` | Optional; why an off-topic document is kept (the 2026-09-06 topic ruling). |

### A row

| field | meaning |
|---|---|
| `work_id` | The work, as the export's items carry it in `extra` (`ticket-0029 work id`). |
| `recipe_id` | The recipe record of the attachment; must match the export manifest's binding for `attachment_key`. |
| `attachment_id` | The recipe attachment id (ticket 0721's shape), so a re-export re-resolves the key; `null` where the recipe has no attachment ids yet. |
| `attachment_key` | The Zotero attachment key in the export manifest. Retrieval is item-level: the scorer resolves the parent item from the manifest. |
| `section` | The section the row stands for; `(work_id, section)` is the row's identity and may not repeat within a question. |
| `alternates` | One or more `{page_printed, char_offset, quote}`: the page number **as printed in the text** (front matter in roman numerals, never the PDF index; `null` for a pageless file), the character offset in the export's fulltext (resolved by the validator), and the quoted span. |
| `chain` | The citation chain a complete reply carries: `title`, `author`, `date`, `identifier` (DOI, ISBN or URL), `section_heading`, `page_printed`, and for a compound document `part_title` and `part_byline`; `null` where the document has none. |

The quote is located in the export's fulltext **whitespace-normalised,
apostrophe-folded (’ → '), case-preserving**. A span the extraction mangled
(an OCR scan) is unreachable as written; pick a span the extraction rendered
faithfully or flag the question expected-miss with the mechanism.

### Reachability (stamped, compared)

`golden_gate.py validate --stamp` locates every alternate, writes its
`char_offset`, and stores the block; `validate` without `--stamp` recomputes
and refuses a stale stamp, a different export, or an offset that moved.

```json
"reachability": {
  "computed_by": "bench/golden_gate.py validate --stamp",
  "export_sha256": "<sha256 of export/manifest.json>",
  "extraction": {
    "reindex_mode": "complete", "reindex_limits": "ignored",
    "caps": {"fulltext.pdfMaxPages": 100, "fulltext.textMaxLength": 500000},
    "index_fulltext_max_chars": 40000,
    "recipe_sha256": "<the manifest's>"
  },
  "reachable": true,
  "rows": [{"attachment_key": "L68LPREA", "alternates": [
    {"reachable": true, "char_offset": 10203, "occurrences": 1, "reason": null, "within_index_cap": true}
  ]}]
}
```

`within_index_cap` says whether the located span lies inside the product's
`ZOTEUS_INDEX_FULLTEXT_MAX_CHARS` as the export was built (40 000 characters
here): a reachable answer past the cap is in the export but not in the index,
and a question pinning only such answers should say so as its
`expected_miss_mechanism`.

## The replies — schema `menagerie-replies/v2`

Written by `bench/golden_run.py`; a `golden-gate-input/v1` bundle is refused by
name.

```json
{
  "schema": "menagerie-replies/v2",
  "run": {
    "date": "2026-09-06", "k": 10,
    "recipe_sha256": "...", "export_sha256": "...",
    "extraction": {"...the manifest's, as above..."},
    "embedder": "none (keyword-only)", "chunker": "...", "index_schema": "2",
    "retrieval_mode": "keyword (BM25 over passages) reported as lexical; semantic and hybrid not-run",
    "build_sha": "<git HEAD of the checkout that built the server>",
    "tool": "zotero_semantic_search",
    "reply_shape": {"hit_fields": ["itemKey", "score", "snippet", "source", "title"], "...": "..."}
  },
  "previous_run": {"run": {"...same shape..."}, "replies": ["...same shape..."]},
  "replies": [
    {"id": "q-0001", "mode": "lexical", "results": [
      {"rank": 1, "item_key": "GEWEZPJ4", "attachment_key": null, "work_id": "vn-decision-11-2017-qdttg-solar-fit-en",
       "evidence": "<the snippet>", "page": null,
       "chain": {"title": "...", "author": "...", "date": "2017", "identifier": "https://...",
                 "section_heading": null, "page_printed": null, "part_title": null, "part_byline": null},
       "score": 0.82, "source": "fulltext"}
    ]},
    {"id": "q-0001", "mode": "semantic", "results": null, "not_run_reason": "embeddings are off in the offline replay ..."}
  ]
}
```

`previous_run` is optional and feeds the stability reading (Jaccard of the
top-k item sets per question and mode, thresholds from SPEC §5.2.8). A reply
whose `results` is `null` is **not-run** for that mode and must say why; it is
never scored as a miss. `run.reply_shape` records what the tool's hits actually
carried and where each chain field came from: the chain-completeness ceiling of
the build, reported, not hidden.

## Scoring a row

- **Present** if any result within k has the row's item (its parent item key,
  or its attachment key when the reply carries one), or — via the export's work
  ids and declared `translation` / `same-work` relations — another rendering of
  the row's work.
- **Win** if the item is present and the evidence overlaps an alternate's quote
  (token overlap ≥ 0.5 of the quote's content words — word tokens of three
  characters or more, case-folded) or the printed page the reply states matches
  the alternate's `page_printed`.
- **Near-win** if the item is present without that overlap, or only the
  declared other-language / other-rendering twin is present.
- **Miss** otherwise.
- **Chain completeness** = the fraction of the primary chain's non-null fields
  the reply carries with a matching value (string-normalised; `page_printed`
  exact). A missing row is `not-run` for the chain.

## The report — schema `golden-gate-report/v3`

Per question and mode: level, rank, reciprocal rank, chain, rows found, per-row
detail. Aggregated per lane, format of the primary attachment (`pdf`, `html`,
`other`), signal, set_kind, mode and facet, **within each stratum**, with the
count beside every rate and `not-measured` at zero; a weighted pooled figure is
printed apart with a macro-average by lane beside it. R34 absolute over the
primary rows and the stability reading are the two
gated readings; the ladder is reported, never gated.

Exit codes of `golden_gate.py score`: 0 pass, 1 fail, 2 input error, 3 not-run
(no replies file, or a gated reading that could not run — a first run has no
previous run to compare with).

## Authoring

Need-driven questions first (`need` written before the document is opened),
then hazard-driven, one per mechanism and tally sub-case; at least five per
document with body text; total soft, about 200. Read the printed page number
on the page (`pdftotext -f N -l N -layout`), never from the PDF index. Then
`python3 bench/golden_gate.py validate --stamp` and commit the stamped file;
the diff of a re-stamp is the review artifact.
