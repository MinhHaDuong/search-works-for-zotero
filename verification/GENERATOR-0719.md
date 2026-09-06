# The library-level bench — a hundred questions generated from a random sample of the author's library, put to the reviewed build in three modes (ticket 0719, measured 2026-09-06)

`SPEC.md` §5.2.8 decides every gate at the fixture level or at the library level.
The Menagerie (ticket 0029) is the fixture level. This is the library level made
routine: a sampler draws answer paragraphs from a random sample of the author's
real Zotero library, a model on the author's own second machine writes one
question per paragraph, the engine under test answers through the acceptance
harness's `query` verb in each of its three retrieval modes, and each reply is
scored on the ladder of rulings 5 and 7 of 2026-09-06 as amended the same day —
win, near-win, miss — on the rank of the answer paragraph and what the reply
carries of its citation chain. Regenerated at each run from a private library, it
cannot be tuned against.

This is the second run. The first (same day, earlier) scored the newest 300
items with a strict chain and a small local model; the author then ruled on the
three questions it raised (`DECISIONS.md`, 2026-09-06, last entry), and this run
applies the three changes: **the ladder** (a resolvable item key wins, except for
compound documents), **the scope** (a seeded random sample of items, not the
newest N), and **the question writer** (padme's llama-server, not a 1,5 B model on
this CPU). It also asks every question in every mode, as asked.

Artifact: `bench/results/0719-generator/run.json`, aggregates only — no paragraph,
no title, no key, swept for each before commit. Code: `bench/generator/` (its
README says what each module does). Tests: `tests/test_generator_*.py`. Machine:
**doudou** (Intel i5-8250U, 8 threads, no GPU — the reference machine §5.2.8
names) for the target and the sampler; **padme** for the question writer. Zotero
**10.0.1**, personal library at version **1257**, run identity dated 2026-09-06
19:17 UTC. Every number below comes from that one run unless it says otherwise.

## What was run

- **Target.** zoteus at the reviewed SHA `34d6c26` (v1.14.0), built from a fresh
  `make upstream-checkout`, in its default configuration through the acceptance
  adapter: local embedder (`Xenova/all-MiniLM-L6-v2` through transformers.js),
  SQLite backend, body text on, read-only against the library. Ten hits asked
  for. The process ran unwrapped, no posture: the run's subject is the
  operator's own library.
- **Scope** (ruled). A seeded random sample of **300** top-level records, seed 1,
  with their **412** children. The target's build tool cannot take a list of
  keys, so the harness stood a read-only proxy in front of Zotero's local API
  (`bench/generator/scope.py`) that answers the listings — `/items`,
  `/items/top`, `?format=versions`, the `/fulltext` census — from the sample,
  fetched by `itemKey=` chunks of fifty, and passes everything else through; the
  target was pointed at it through its own `ZOTERO_LOCAL_PORT`. The proxy served
  **309** requests, all GET, and refused **0** other methods. The index was built
  through the target's own tool in **609,6 s**: **6 458** passages, all embedded,
  231 of 300 items with body text, 108 own-words passages. The scope was read
  back from the index file — **300** items — and the sampler restricted to it.
  The build's status reports `localApiDegradedAt` at 19:05:55 UTC, three minutes
  in: the target's liveness probe, which runs on a deadline, found the proxy
  slow to answer once while Zotero itself was answering a page in four seconds,
  and the target fell back to its Web API for part of the crawl. The index
  holds exactly the 300 sampled items either way; the cause of Zotero's own
  slowness that evening (a sibling agent's acceptance runs against the same
  app, a fresh restart) is not isolated.
- **Sample.** **100** answer paragraphs drawn uniformly from the **318** (record,
  attachment) pairs with extracted text in the scope, one per pair, 3 pairs
  skipped for holding no eligible paragraph; no quota (ruled: thin cells at
  their true weight). Formats: PDF **71**, HTML **29**, against census shares of
  64,3 and 35,5. Item types: report 32, journal article 30, book 17, webpage 11,
  and seven types with one or two each. Length: 66 in the census's top quartile.
  Language, detected from the paragraph's own text: English **81**, Vietnamese
  **12**, French 3, Portuguese 2, undetermined 2.
- **Questions** (ruled). One per paragraph, written by **padme's llama-server**
  (build `b10542-521a64cd0`), serving the alias **`qwen3.8-27b`** — read from its
  `/v1/models`, not assumed — reached through an ssh tunnel from doudou to
  padme's loopback, thinking disabled, temperature 0. Nothing was started or
  installed on padme. All **100** questions came from the model, none from the
  fallback; the batch took **188 268 ms**, about 1,9 s per question. A declared
  third were written in another of R7's default-path languages: **30**
  cross-lingual questions (French 19 and Vietnamese 18 written in all, English
  63), 70 in the paragraph's own language.
- **Modes.** Every question was asked in the interface's three modes. The
  adapter maps them `combined → auto`, `exact → keyword`, `meaning → semantic`
  (read from `bench/acceptance/adapters/zoteus.py`), and every reply in every
  mode reported `embedder: local`, `embedderActive: true`, body text on. So
  `exact` is the keyword half alone, `meaning` the vector half alone, and
  `combined` the target's default hybrid path, which the per-lane tables use.
  The first query took **720,2 ms**; the median of the rest was **21,6 ms**; none
  errored.

## The ladder, primary mode (`combined`)

| lane (question → answer) | n | win | near-win | miss | row MRR | work MRR |
|---|---|---|---|---|---|---|
| all | 100 | 22 | 51 | 27 | 0,226 | 0,548 |
| same language | 70 | 21 | 43 | 6 | 0,317 | 0,741 |
| cross-lingual | 30 | 1 | 8 | 21 | 0,013 | 0,097 |
| en → en | 59 | 20 | 35 | 4 | 0,370 | 0,764 |
| fr → en | 12 | 1 | 4 | 7 | 0,017 | 0,092 |
| vi → en | 10 | 0 | 0 | 10 | 0,000 | 0,000 |
| vi → vi | 8 | 1 | 5 | 2 | 0,042 | 0,479 |

The **answer row** — a hit naming the answer's item whose snippet overlaps the
paragraph — was within the first ten for **26** of the 100 questions; the **same
work** — the item, by key or by title, with or without the paragraph — for **73**.
The remaining lanes have one to three questions each (fr → fr 3, and five
pairs of two) and are in the artifact, not read here. A miss counts zero in
both MRRs.

**Wins exist now, and where the ruling put them.** Under the amended clause a
resolvable item key satisfies the identifier and work-identity part of the chain,
so the 26 answer rows are 22 wins and 4 near-wins: the four are compound
documents — three books and a book section — where a key alone stays a near-win
and a win would need the part's title with its byline and the page in the reply.
The reply still carries only the title beside the key: of the **26** answer rows
found, **26** carried the title and **0** carried creators, date, identifier,
section or page, so no reply's chain was complete and no compound document won
(**20** compound-document questions: 0 wins, 13 near-wins, 7 misses; books alone
17: 0, 11, 6). The chain-completeness reading is kept in the artifact beside the
verdict.

**The cross-lingual lanes are where the misses are, and it is a model effect,
not a mode effect.** Same-language questions found the work nine times in ten
(64 of 70) and won three times in ten; cross-lingual questions found the work
nine times in 30 and won once. That is the question this run was asked to
settle, and the per-mode table answers it below.

## The ladder per retrieval mode

| mode (adapter → target) | n | win | near-win | miss | row MRR | work MRR |
|---|---|---|---|---|---|---|
| combined → auto | 100 | 22 | 51 | 27 | 0,226 | 0,548 |
| exact → keyword | 100 | 23 | 42 | 35 | 0,233 | 0,560 |
| meaning → semantic | 100 | 17 | 51 | 32 | 0,158 | 0,486 |

| cross-lingual lane, per mode | n | win | near-win | miss | row MRR | work MRR |
|---|---|---|---|---|---|---|
| combined, cross-lingual | 30 | 1 | 8 | 21 | 0,013 | 0,097 |
| exact, cross-lingual | 30 | 0 | 3 | 27 | 0,011 | 0,051 |
| meaning, cross-lingual | 30 | 1 | 8 | 21 | 0,011 | 0,116 |
| combined, same language | 70 | 21 | 43 | 6 | 0,317 | 0,741 |
| exact, same language | 70 | 23 | 39 | 8 | 0,329 | 0,778 |
| meaning, same language | 70 | 16 | 43 | 11 | 0,220 | 0,645 |

Three readings. First, on this scope the keyword half alone is as good as the
hybrid on the row and slightly better on the work (23 wins against 22, work MRR
0,560 against 0,548), and the vector half alone is the weakest of the three
(17 wins, 0,158): the default embedder is a monolingual English model of 384
dimensions, and it does not add to BM25 on same-language questions here.
Second, the cross-lingual lanes miss in every mode: the keyword half finds the
work 3 times in 30 (**0** wins, **3** near-wins, **27** misses), the vector half
9 times (**1**, **8**, **21**), the hybrid the same 9. The `fr → en` lane (12
questions) is 0 near-wins in `exact` and **5** near-wins in `meaning`; the
`vi → en` lane (10) is **10** misses in all three modes. So the near-zero of the
cross-lingual lanes is not the hybrid path's fusion dropping what the vectors
found: the vectors find little to begin with, because the embedder does not
cross the language, and the keyword half cannot, because the words differ.
That is R29's clause as this run measures it. Third, the `vi → vi` lane (8
questions) reads the other way: **2** wins in `exact`, **0** in `meaning`, and
the hybrid keeps one — the English embedder does not place Vietnamese text
where a Vietnamese question lands, and the keyword half does the work.

## Per stratum, primary mode

| stratum | n | win | near-win | miss | row MRR |
|---|---|---|---|---|---|
| within the body-text cap | 72 | 21 | 29 | 22 | 0,290 |
| beyond the body-text cap | 28 | 1 | 22 | 5 | 0,061 |
| PDF | 71 | 13 | 38 | 20 | 0,221 |
| HTML | 29 | 9 | 13 | 7 | 0,237 |
| journal articles | 30 | 11 | 12 | 7 | 0,367 |
| reports | 32 | 6 | 15 | 11 | 0,172 |
| very long documents | 66 | 11 | 38 | 17 | 0,208 |

The target indexes at most 40 000 characters of body text per item by default
(`DEFAULT_FULLTEXT_MAX_CHARS`); the sampler flags each paragraph's offset in its
attachment against that cap, 72 within and 28 beyond. The answer row was found
for **23** of the 72 within and for **3** of the 28 beyond: the flag predicts the
mechanism, and the three exceptions are the flag's approximation — it reads the
offset within one attachment where the target caps the item's text as a whole,
so a paragraph beyond 40 000 characters of one attachment can still sit under
the cap when the item has several. The 22 near-wins beyond the cap are the work
found through its metadata or an earlier passage, never the paragraph. HTML
snapshots (29) score as PDFs (71) here, which the first run's 99 % PDF scope
could not show; reports (32) score under journal articles (30), 6 wins against
11, on a sample where a "report" in this library is often a long institutional
document with the paragraph deep in it.

## The chain, measured and not

| element | measured | not measured | how |
|---|---|---|---|
| title, creators, date | 100 | 0 | the record |
| identifier | **83** | 17 | URL 52, DOI 26, ISBN 5 |
| PDF page index | **63** | 37 | form feeds in Zotero's extracted text; none in HTML |
| printed page label | **18** | 82 | the PDF's `/PageLabels` tree: present in 18 files, absent in 45 (pages numbered by index only), 37 not a local PDF |
| section heading | **89** | 11 | a numbered, capitalised or short heading line above the paragraph |
| compound part | 2 | 1 | 3 records are parts (book sections, a proceedings paper); container title measured for 2 |

A random scope carries the library's formats, and the chain shows it: 29 HTML
snapshots have no page at all, so the page index drops from the first run's 94
to **63**, the printed label from 26 to **18**. The identifier is a URL more
often than a DOI here (52 against 26), which is the web-native share of the
library speaking. The heading heuristic fires where the text makes one evident
and is not checked against the document's structure; its 89 is an upper bound.

## What this run is and is not

- **A self-consistency probe.** Every question was written from the paragraph
  it must retrieve, so it asks whether the engine can find a paragraph from a
  paraphrase of it — closer to a recall check than to a user's need. Need-driven
  questions are the Menagerie's.
- **A random scope of 300 of 7 553 items**, seed 1, built into its own index
  through the proxy. The cells print their counts; the thin ones (a single
  conference paper, two book sections) are what a random draw of this library
  supplies, and they are not read as rates.
- **One run, one seed.** No stability reading yet; the identity block — seed,
  scope, library version, target revision, writer, endpoint, server
  fingerprint, modes and their evidence — is what a second run compares against.
- **Read-only, aggregate-only.** Every request to Zotero is a GET, through the
  census's one call site or the proxy's; the PDF page labels are read from the
  file. The private rows — paragraphs, keys, titles, questions, per-reading
  scores in every mode — stay in the run's work directory and are not committed.
  The artifact's ladder was recomputed once from those rows
  (`bench/generator/refresh.py`) to add the per-mode cross-lingual table; the
  identity, sample and questions blocks are as the run wrote them, and the
  artifact says so.

## Reproduction

    ssh -N -L 18080:127.0.0.1:8080 padme &     # the writer's endpoint; nothing runs on padme but its own server
    python3 -m bench.generator.run --entrypoint fork/dist/index.js \
        --arena <arena> --transformers-path <a @huggingface/transformers directory> \
        --zotero-data-dir ~/data/Zotero --scope-items 300 \
        --census bench/results/0029-library-census/census.json --n 100 --seed 1 \
        --writer llama-server --endpoint http://127.0.0.1:18080 --endpoint-note "ssh tunnel to padme" \
        --fallback-model <hub id of an instruct model, ONNX weights> --cache-dir <cache> \
        --work-dir <private dir> --output bench/results/0719-generator/run.json

Zotero must be running with the local API on, and nothing else may use that API
during the build: two clients at once saturated it within minutes on this host.
