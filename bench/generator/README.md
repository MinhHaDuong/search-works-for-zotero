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
    --zotero-data-dir ~/data/Zotero --scope-items 300 \
    --census bench/results/0029-library-census/census.json --n 100 --seed 1 \
    --writer llama-server --endpoint http://127.0.0.1:18080 --endpoint-note "ssh tunnel to padme" \
    --fallback-model <hub id of an instruct model, ONNX weights> --cache-dir ~/data/cache/transformersjs \
    --work-dir ~/data/generator-0719/work --output bench/results/0719-generator/run.json
```

Zotero must be running with the local API on (the sampler reads it, and so
does the target, through the scope proxy), and nothing else may use that API
during the build. Each stage also runs alone: `sample`, `questions`, and `run`
with `--reuse-index` over an index and scope already in the arena.

| module | does | reads | writes |
|---|---|---|---|
| `scope.py` | a seeded random sample of items, and the read-only proxy that makes it the library the target sees | the local API (GET only) | nothing |
| `sample.py` | draws answer paragraphs from the scope, uniformly at random (or by census quota), with the citation chain per answer | the local API (GET only), the PDF's page labels through `pikepdf` | `sample.jsonl` (private), `sample-summary.json` (aggregates) |
| `text.py` | paragraphs, page index from form feeds, language, evident headings | strings | nothing |
| `questions.py` + `tjs_generate.mjs` | one question per paragraph, on the author's own inference server, on a local model, or on a template, in a declared lane | `sample.jsonl`, the server | `questions.jsonl` (private), `questions-summary.json` |
| `score.py` | the ladder and its aggregates | replies and answers | nothing |
| `run.py` | draws the scope, stands the proxy, builds the index through the target's own tool, samples inside the scope, asks in every mode, scores, reports | the index file (read-only), the API | `run.json` (aggregates and the run identity) |

## What is private and what is committed

`--work-dir` holds the answer key of a run: paragraph text, item keys, titles,
questions, per-reading scores. It is never committed. The artifact under
`bench/results/` and the report under `verification/` carry aggregates only,
with the run identity: seed, library version, Zotero version, target revision,
scope (the item keys the index actually held, counted), index counters and
build cost, question model, extraction configuration. Two runs are comparable
when their identity blocks say what changed.

## The scope and the sample

**Scope** (ruled 2026-09-06): a seeded random sample of `--scope-items`
top-level records — not the newest N, not a stratified sample — built into its
own index. The author's reason: thin cells are what the library has, and a
random sample reports them at their true weight where a stratified one would
manufacture precision. The target's build tool cannot take a list of keys, so
`scope.py` stands a read-only proxy in front of Zotero's local API that filters
the listings (`/items`, `/items/top`, `?format=versions`, the `/fulltext`
census) to the sampled records and their children and passes everything else
through; the target is pointed at it through its own `ZOTERO_LOCAL_PORT`. The
scope is read back off the index file afterwards, and the run identity records
seed, requested size, records, children and the proxy.

**Sample.** The frame is every (record, attachment) pair whose attachment has
extracted text and whose record the index holds. By default (`--sampling
random`) pairs are drawn uniformly, one paragraph each, and every lane, format
and type cell prints its count beside the census share it would have had. The
quota sampler (`--sampling quota`) that fills census cells by deficit is kept
for a run that wants the census's mix. Language is recorded from the
paragraph's own text (ruling 2: Zotero's field is a weak indicator; it stands
in only when the text decides nothing, and the row says so).

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
`llama-server` writer puts each prompt to an OpenAI-compatible endpoint — the
author's own second machine, admissible under R10 by the ruling of 2026-09-06;
the served model is read from `/v1/models`, never assumed, and recorded with
the endpoint and the server's build fingerprint. A server that listens on its
own loopback is reached through an ssh tunnel the operator opens; nothing is
started or installed there. When the server does not answer, the run says so
(`fallback_reason` in the identity) and falls back to `tjs`, a small instruct
model through transformers.js on CPU, the runtime the target already carries;
`template` is the deterministic last resort, and every row says which wrote
it. A question written from the paragraph it must retrieve is a
self-consistency probe, closer to a recall check than to a user need; the
report says so, and need-driven questions stay the Menagerie's.

## The score

A reply is read hit by hit within the first ten. The **answer row** is a hit
naming the answer's item whose snippet shares a five-word shingle with the
paragraph; the **same work** is a hit naming the item without the paragraph, or
another item with the same title or identifier. **win** (ruled 2026-09-06):
answer row found and the reply carries a resolvable item key, which satisfies
the identifier and work-identity part of the chain — except for a **compound
document** (book, book section, proceedings paper, dictionary or encyclopedia
entry), where a key alone is a near-win and a win needs the part's title with
its byline and the page in the reply. **near-win**: answer row found without
that, or only the same work found. **miss**: neither. Two mean reciprocal ranks
are reported, the row's and the work's, with a miss at zero. Counts sit beside
every rate, per lane, per format, per item type, compound against simple, per
length bucket, per reachability, per writer, and per retrieval mode.

The chain a reply carries is still read off the hit under `score.CHAIN_FIELDS`
and reported (`chain_complete`, `chain_in_reply`), since the ladder no longer
turns on it.

## The modes

Every question is asked in each of the interface's three retrieval modes
(`exact`, `meaning`, `combined`). Which target mode each maps to is read from
the adapter's own table, and what the target says it ran — embedder, active or
not, vectors — is read from its replies. The per-lane tables use `combined`,
the target's default path; the per-mode table sits beside them so a lane's
result can be read as a mode effect or a model effect.

## Tests

`tests/test_generator_*.py`, fast tier, no process spawned: the API and the
model are faked, the read-only property is asserted on the source and on the
URLs a fixture route served, and the aggregate-only property on the serialised
summary and artifact.
