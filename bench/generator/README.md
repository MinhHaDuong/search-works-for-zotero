# bench/generator/ — the library-level bench (ticket 0719)

About a hundred questions generated on the fly from the author's real Zotero
library, put to the engine under test through the acceptance harness's `query`
verb, and scored on the ladder of rulings 5 and 7 of 2026-09-06: win, near-win,
miss, on the rank of the answer paragraph and the completeness of its citation
chain. It is the library level of `SPEC.md` §5.2.8 made routine — private,
regenerated at each run, impossible to tune against — and the complement of the
Menagerie (ticket 0029), which stays pinned, public and hand-judged.

```bash
python3 -m bench.generator.run \
    --entrypoint fork/dist/index.js --arena ~/data/generator-0719/arena \
    --transformers-path <a @huggingface/transformers directory> \
    --zotero-data-dir ~/data/Zotero --build-limit 300 \
    --census bench/results/0029-library-census/census.json --n 100 --seed 1 \
    --writer tjs --model <hub id of an instruct model, ONNX weights> --cache-dir ~/data/cache/transformersjs \
    --work-dir ~/data/generator-0719/work --output bench/results/0719-generator/run.json
```

Zotero must be running with the local API on (the sampler reads it, and so
does the target). Each stage also runs alone: `sample`, `questions`, and `run`
with `--build-limit 0` over an index already in the arena.

| module | does | reads | writes |
|---|---|---|---|
| `sample.py` | draws answer paragraphs stratified against the census, with the citation chain per answer | the local API (GET only), the PDF's page labels through `pikepdf` | `sample.jsonl` (private), `sample-summary.json` (aggregates) |
| `text.py` | paragraphs, page index from form feeds, language, evident headings | strings | nothing |
| `questions.py` + `tjs_generate.mjs` | one question per paragraph, on a local model or a template, in a declared lane | `sample.jsonl` | `questions.jsonl` (private), `questions-summary.json` |
| `score.py` | the ladder and its aggregates | replies and answers | nothing |
| `run.py` | builds a bounded index through the target's own tool, samples inside its scope, asks, scores, reports | the index file (read-only), the API | `run.json` (aggregates and the run identity) |

## What is private and what is committed

`--work-dir` holds the answer key of a run: paragraph text, item keys, titles,
questions, per-reading scores. It is never committed. The artifact under
`bench/results/` and the report under `verification/` carry aggregates only,
with the run identity: seed, library version, Zotero version, target revision,
scope (the item keys the index actually held, counted), index counters and
build cost, question model, extraction configuration. Two runs are comparable
when their identity blocks say what changed.

## The sample

The frame is every (record, attachment) pair whose attachment has extracted
text and whose record the index holds. The target distribution is the product
of three census marginals (`bench/results/0029-library-census/census.json`):
item type, attachment format among attachments with text, and document length
in the census's `totalChars` quartiles. The sampler fills the (type, format)
cell with the largest deficit first and turns a draw away when its length
bucket is over quota, up to a bounded number of tries; the summary reports
target against achieved on every marginal, so a cell the frame cannot supply is
visible rather than silently reweighted. Language is recorded from the
paragraph's own text (ruling 2: Zotero's field is a weak indicator; it stands
in only when the text decides nothing, and the row says so) and is not quota'd.

## The chain, and what is measurable

Every element carries a `measured` flag.

| element | source | not measured when |
|---|---|---|
| title, creators, date | the record | the field is empty |
| identifier | DOI, then ISBN, then URL of the record | all three are empty |
| PDF page index | form feeds in Zotero's extracted text (recent extractor generations write one per page) | the text carries none — about a third of this library's caches do |
| printed page label | the PDF's own `/PageLabels` tree, read through `pikepdf` from the local file | the file is not local, not readable, or numbers its pages by index only (`no-page-labels`) |
| section heading | a numbered, all-capitals or short capitalised line above the paragraph | the text makes none evident |
| compound part | the record's title, with `bookTitle` / `proceedingsTitle` as container | the record is not a part |

Reachability is recorded beside the chain: whether the paragraph's offset sits
under the target's default per-item body-text cap (`DEFAULT_FULLTEXT_MAX_CHARS`,
40 000 characters in the reviewed build). A paragraph beyond it is an expected
miss by construction and is reported in its own row, never dropped.

## The questions

One per paragraph, in the paragraph's language, except a declared share (a
third by default) written in another of R7's default-path languages, so the
lane pair (question language, answer-paragraph language) is exercised. The
`tjs` writer runs a small instruct model through transformers.js on CPU — the
runtime the target already carries — with the one-time model download as the
sole network use; `template` is the deterministic fallback, and every row says
which wrote it. A question written from the paragraph it must retrieve is a
self-consistency probe, closer to a recall check than to a user need; the
report says so, and need-driven questions stay the Menagerie's.

## The score

A reply is read hit by hit within the first ten. The **answer row** is a hit
naming the answer's item whose snippet shares a five-word shingle with the
paragraph; the **same work** is a hit naming the item without the paragraph, or
another item with the same title or identifier. **win**: answer row found and
the reply carries the whole chain. **near-win**: answer row found with an
incomplete chain, or only the same work found. **miss**: neither. Two mean
reciprocal ranks are reported, the row's and the work's, with a miss at zero.
Counts sit beside every rate, per lane, per format, per item type, per length
bucket, per reachability, per writer.

The chain a reply carries is read off the hit under `score.CHAIN_FIELDS`. A
target whose hits carry only a title and an item key cannot score a win here;
the report says which elements the reply carried rather than relaxing the ladder.

## Tests

`tests/test_generator_*.py`, fast tier, no process spawned: the API and the
model are faked, the read-only property is asserted on the source and on the
URLs a fixture route served, and the aggregate-only property on the serialised
summary and artifact.
