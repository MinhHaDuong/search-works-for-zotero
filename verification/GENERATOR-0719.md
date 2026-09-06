# The library-level bench, first run — a hundred questions generated from the author's library, put to the reviewed build (ticket 0719, measured 2026-09-06)

`SPEC.md` §5.2.8 decides every gate at the fixture level or at the library level.
The Menagerie (ticket 0029) is the fixture level. This is the library level made
routine: a sampler draws answer paragraphs from the author's real Zotero library,
a local model writes one question per paragraph, the engine under test answers
through the acceptance harness's `query` verb, and each reply is scored on the
ladder of rulings 5 and 7 of 2026-09-06 — win, near-win, miss — on the rank of
the answer paragraph and the completeness of its citation chain. Regenerated at
each run from a private library, it cannot be tuned against.

Artifact: `bench/results/0719-generator/run.json`, aggregates only — no paragraph,
no title, no key. Code: `bench/generator/` (its README says what each module
does). Tests: `tests/test_generator_*.py`. Machine: **doudou** (Intel i5-8250U,
8 threads, no GPU — the reference machine §5.2.8 names), Zotero **10.0.1**,
personal library at version **1257**, run identity dated 2026-09-06 18:11 UTC.
Every number below comes from that one run on that one machine unless it says
otherwise.

## What was run

- **Target.** zoteus at the reviewed SHA `34d6c26` (v1.14.0), built from a fresh
  `make upstream-checkout`, in its default configuration through the acceptance
  adapter: local embedder (`Xenova/all-MiniLM-L6-v2` through transformers.js),
  SQLite backend, body text on, read-only against the library. Queries in the
  interface's `combined` mode, ten hits asked for. The process ran unwrapped, no
  posture: the run's subject is the operator's own library.
- **Scope.** The newest **300** items of the personal library, chosen so the build
  fits in an hour on this CPU, which embeds 3 to 8 passages per second: a
  full-library build with vectors would take 15 to 40 hours here. Built with the
  target's own `zotero_index` tool in **1 014,4 s**: **9 032** passages, all of
  them embedded, 260 of 288 items with body text. The scope is read back from
  the index file, not assumed from the request: the sampler was restricted to the
  300 item keys the index holds. A partial scope is a stated limit; the newest
  300 items are 99 % PDF and mostly long, which the strata table below shows.
  The build's own status reports `localApiDegradedAt` four minutes in — the
  target found Zotero's local API not answering and fell back to its Web API
  for part of the crawl. It ran alone on the API; a sibling agent worked against
  the same Zotero that evening, and the cause is not isolated.
- **Sample.** 100 answer paragraphs, seed 1, stratified against the census
  (`verification/LIBRARY-CENSUS-0029.md`) on item type, attachment format and
  document length; the frame held 264 (record, attachment) pairs with extracted
  text. Language is detected from the paragraph's own text: 89 English, 4 French,
  4 German, 1 Spanish, 1 Russian, 1 undetermined.
- **Questions.** One per paragraph, on **onnx-community/Qwen2.5-1.5B-Instruct**
  (q4 ONNX) through transformers.js 4.2.0 on CPU — the same runtime the target
  embeds with, the only local generation runtime this host has (no ollama, no
  llama.cpp, no torch). All 100 came from the model, none from the template
  fallback; the batch took **1 271 289 ms**, about 12,7 s per question. A declared
  third were written in another of R7's default-path languages: 31 cross-lingual
  questions (17 French, 14 Vietnamese written against non-French, non-Vietnamese
  paragraphs), 69 in the paragraph's own language.
- **Queries.** The first took **1 403,6 ms** (the ONNX session's warm-up); the
  median of the 99 after it was **27,2 ms**. No reply errored.

## The ladder

| lane (question → answer) | n | win | near-win | miss | row MRR | work MRR |
|---|---|---|---|---|---|---|
| all | 100 | 0 | 62 | 38 | 0,197 | 0,464 |
| same language | 69 | 0 | 52 | 17 | 0,264 | 0,551 |
| cross-lingual | 31 | 0 | 10 | 21 | 0,048 | 0,269 |
| en → en | 63 | 0 | 47 | 16 | 0,273 | 0,557 |
| fr → en | 13 | 0 | 1 | 12 | 0,000 | 0,038 |
| vi → en | 13 | 0 | 7 | 6 | 0,115 | 0,449 |

The **answer row** — a hit naming the answer's item whose snippet overlaps the
paragraph — was within the first ten for **26** of the 100 questions; the **same
work** — the item, by key or by title, with or without the paragraph — for 62.
The row MRR counts a miss at zero. The remaining lanes have one to three
questions each (de → de 3, fr → fr 3, and five singletons) and are in the
artifact, not read here.

**No reply scored a win, and none could have.** A win needs the answer row with
the whole chain carried by the reply: title, creators, date, identifier, section
heading and printed page label. This target's hit carries an item key, a title,
a snippet and a score. Of the **26** answer rows found, **26** carried the title
and **0** carried any other element. Every found row is therefore a near-win by
construction, and the ladder's top rung is unreachable until the reply carries
the chain. The item key does let a user resolve author, date and identifier in
Zotero, but the reply does not carry them, and ruling 7 asks for them in the
reply — whether a resolvable key should count as the identifier is a question
for the author, noted below.

**Cross-lingual lanes are where the misses are.** Same-language questions found
the work three times in four (52 of 69) and the row once in three; cross-lingual
questions found the work once in three (10 of 31) and the row twice in 31.
French questions on English paragraphs missed 12 of 13; Vietnamese questions on
English paragraphs did better (7 near-wins of 13), which reads as the keyword
half matching untranslated proper nouns and numbers rather than as the semantic
half crossing the language — the default embedder is monolingual English, and
R29's clause is the one this lane exercises.

## Per stratum

| stratum | n | near-win | miss | row MRR |
|---|---|---|---|---|
| within the body-text cap | 71 | 49 | 22 | 0,277 |
| beyond the body-text cap | 29 | 13 | 16 | 0,000 |
| very long documents | 72 | 45 | 27 | 0,137 |
| journal articles | 41 | 25 | 16 | 0,298 |

The target indexes at most 40 000 characters of body text per item by default
(`DEFAULT_FULLTEXT_MAX_CHARS`). The sampler flags each paragraph's offset against
that cap: 71 within, 29 beyond. The answer row was found for **26** of the 71
within and for **0** of the 29 beyond — the flag predicted the mechanism, and the
13 near-wins beyond the cap are the work found through its metadata or an earlier
passage, never the paragraph. This is the expected-miss class of the Menagerie's
answer key (conception note, C.7) appearing on the real library: on a scope
whose documents are mostly long, a quarter of the paragraphs a user might want
are unreachable by construction. Per format and per item type the sample is too
concentrated to read: 99 of 100 paragraphs are PDF, and 72 of 100 are in the
census's top length quartile, against targets of 64,3 and 25 respectively —
the newest 300 items are not the library's mix.

## The chain, measured and not

| element | measured | not measured | how |
|---|---|---|---|
| title, creators, date | 100 | 0 | the record |
| identifier | **79** | 21 | DOI 51, URL 27, ISBN 1 |
| PDF page index | **94** | 6 | form feeds in Zotero's extracted text |
| printed page label | **26** | 74 | the PDF's `/PageLabels` tree: present in 26 files, absent in 68 (pages numbered by index only), 6 files not local or not a PDF |
| section heading | **76** | 24 | a numbered, capitalised or short heading line above the paragraph |
| compound part | 18 | 2 | 20 records are parts; container title measured for 18 |

The page index is derivable for most of this scope because the newest items were
extracted by a generation of Zotero's extractor that writes a form feed per page;
across the whole library 4 728 of 13 653 caches carry one, so on an older scope
this column would fall to about a third. The printed label is the scarce element:
most PDFs carry no `/PageLabels`, and their printed folio is then not derivable
from anything the sampler reads — it would take reading the page. The heading
heuristic fires where the text makes one evident and is not checked against the
document's structure; treat its 76 as an upper bound.

## What this run is and is not

- **A self-consistency probe.** Every question was written from the paragraph
  it must retrieve, so it asks whether the engine can find a paragraph from a
  paraphrase of it — closer to a recall check than to a user's need. Need-driven
  questions are the Menagerie's.
- **A bounded scope.** 300 of 7 553 items, the newest, 99 % PDF. The strata
  targets are the census's; the achieved counts are what this scope could supply,
  and the table in the artifact carries both.
- **One run, one seed.** No stability reading yet; the identity block is what a
  second run compares against.
- **Read-only, aggregate-only.** Every request to Zotero is a GET through the
  census's one call site; the PDF page labels are read from the file. The
  private rows — paragraphs, keys, titles, questions, per-reading scores — stay
  in the run's work directory and are not committed.

## Open for the author

1. Whether a reply carrying the item key, which resolves to author, date and
   identifier in Zotero, satisfies ruling 7's identifier clause, or whether the
   chain must be in the reply text. Under the strict reading used here no target
   returning `{itemKey, title, snippet}` can win.
2. Whether the library-level scope should be the newest N items (cheap, skewed
   to long PDFs) or a stratified item sample built into its own index (a fairer
   mix, a costlier build).
3. Whether padme's Qwen3-8B, the author's own machine on his own network, is an
   admissible question writer under R10, or whether "the machine" is this one.

## Reproduction

    python3 -m bench.generator.run --entrypoint fork/dist/index.js \
        --arena <arena> --transformers-path <a @huggingface/transformers directory> \
        --zotero-data-dir ~/data/Zotero --build-limit 300 \
        --census bench/results/0029-library-census/census.json --n 100 --seed 1 \
        --writer tjs --model <hub id of an instruct model, ONNX weights> --cache-dir <cache> \
        --work-dir <private dir> --output bench/results/0719-generator/run.json

Zotero must be running with the local API on, and nothing else may use that API
during the build: two clients at once saturated it within minutes on this host.
