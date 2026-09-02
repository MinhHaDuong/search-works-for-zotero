# FIELD REVIEW — what has already been built

## Intro

This document surveys the prior art: the Zotero AI, semantic-search, and
retrieval tools that already exist, what each one is, and what our design can
take from it. The specification chain had no such survey, so the design was
being derived without knowing what had been derived already.

Authority: this document owns the inventory, and each project's observed state
at the date its entry gives. It owns no design number, no requirement, and no
threshold — the chain that does is named once, in README.md. Where a finding
below bears on ours, it points at the owning document rather than restating
it.

Three rules bind every line.

**Provenance is visible.** We have run none of these tools. A number the
project asserts is marked `(claimed)`. A number someone else measured is marked
`(measured by <who>, <date>)`. No third party's figure enters
`bench/check_figures.py` — that guard covers our own artifacts in
`bench/results/`, and a README claim is not a measurement.

**Dates are attached because the field moves.** Everything below was observed
between 2026-08-27 and 2026-08-29, except the entries and rows dated 2026-09-02,
which a second pass added from two leads the author sent: a r/zotero thread of
2026-08-29 asking BibGenie or llm-for-zotero
(`reddit.com/r/zotero/comments/1w1gsdc/`), and Citation Styler's plugin
overview (`citationstyler.com/en/knowledge/ai-plugins-for-zotero/`, updated
2026-08-12). Nine of the first-pass projects pushed code in the week of the
survey. An entry six months old is a lead, not a fact; re-read the repository
before acting on it.

**A null is reported as a null.** Where a source could not be read — a
rate-limited API, a page drawn by client-side script, a closed-source binary —
the entry says "could not look" and names what blocked it. A search that
returned nothing is not evidence that nothing is there.

The survey found **47 projects**, against the roughly 20 the author recalled.
Twenty-eight get a full entry: every project that builds a retrieval index of
its own, plus four that build none but are cited often enough that recording
the absence is the useful result. Two of the twenty-eight are adjacent rather
than competing — the platform itself, and the ecosystem's largest plugin — and
say so. The remaining nineteen relay Zotero's own search, apply a model without
retrieval, or keep their retrieval on a server nobody can read; one table at
the end lists each with the evidence that put it there.

Licence is read from the LICENSE file, never from a badge. Eight projects,
including three of the most interesting, have no LICENSE file at all, and one
of the eight publishes no source to license. That is a finding, and it governs
the closing section.

---

## The inventory

| Project | Kind | Repository | Licence (read from file) | Last code activity |
|---|---|---|---|---|
| ZotSeek | Zotero plugin + MCP | `introfini/ZotSeek` | none (package.json says MIT) | 2026-08-27 |
| ZotSeek-Online | Zotero plugin | `BryceWG/ZotSeek-Online` | none | 2026-03-20 |
| Nodus | Desktop app + Zotero plugin | `Drakonis96/nodus` | AGPL-3.0-only | 2026-08-29 |
| Beaver | Zotero plugin + hosted backend | `jlegewie/beaver-zotero` | AGPL-3.0 | 2026-08-29 |
| PapersGPT | Zotero plugin + MCP | `papersgpt/papersgpt-for-zotero` | AGPL-3.0-only (engine closed) | 2026-08-28 |
| Awesome GPT for Zotero | Zotero plugin | `MuiseDestiny/zotero-gpt` | AGPL-3.0 | 2025-09-19 (feature) |
| seerai | Zotero plugin + MCP | `dralkh/seerai` | MIT | 2026-07-09 |
| zotero-agent | Zotero plugin + MCP | `psiQAQ/zotero-agent` | MIT | 2026-08-05 |
| zotero-mcp (cookjohn) | Zotero plugin + MCP | `cookjohn/zotero-mcp` | MIT | 2026-06-11 |
| zotero-rag (cboulanger) | Zotero plugin + Python backend | `cboulanger/zotero-rag` | none (README claims MPL-2.0) | 2026-08-06 |
| BibGenie | Zotero plugin + MCP, closed source | `BaiRuic/BibGenie` (releases only) | none (no source published) | 2026-08-30 (release) |
| Zotero AI (text70) | Zotero plugin | `text70/zotero_ai` | AGPL-3.0 | 2026-08-10 |
| zoteus | MCP server | `oscardvs/zoteus` | MIT | 2026-08-28 |
| zotero-mcp (54yyyu) | MCP server + CLI | `54yyyu/zotero-mcp` | MIT | 2026-08-25 |
| zotero-mcp-postgres-ollama-fulltext | MCP server | `tspspi/…` | MIT | 2025-11-28 |
| deep-zotero | MCP server | `ccam80/deep-zotero` | MIT | 2026-07-30 |
| ZotPilot | MCP server + agent skills | `xunhe730/ZotPilot` | MIT | 2026-06-28 |
| lit-lake | MCP server | `ElliotRoe/lit-lake` | none | 2026-07-04 |
| zotmcp | MCP server | `nicsuzor/zotmcp` | none | 2026-06-23 |
| zotero-rag (`zqa`) | Rust CLI | `zotero-rag/zotero-rag` | MIT (GUI crate GPL-3.0) | 2026-08-29 |
| zotero-cli-cc | Python CLI + MCP | `Agents365-ai/zotero-cli-cc` | AGPL-3.0-or-later + commercial | 2026-08-25 |
| zotero-rag (aaron-freedman) | Python web app + MCP | `aaron-freedman/zotero-rag` | none (README says MIT) | 2026-03-27 |
| zotero-rag-assistant | Python service | `AesZenz/zotero-rag-assistant` | none | 2026-08-13 |
| zotero-semantic-search | Flask web app | `a-meneghini/zotero-semantic-search` | GPL-3.0 | 2025-01-22 |
| cli-anything-zotero | Python CLI | `PiaoyangGuohai1/cli-anything-zotero` | Apache-2.0 | 2026-07-28 |
| llm-for-zotero | Zotero plugin | `yilewang/llm-for-zotero` | AGPL-3.0 | 2026-08-25 |
| Aria | Zotero plugin | `lifan0127/ai-research-assistant` | AGPL-3.0 | 2025-04-01 |
| zotero-arxiv-daily | Scheduled recommender | `TideDra/zotero-arxiv-daily` | AGPL-3.0 | 2026-08-25 |
| **Adjacent** — Zotero core "Best Match" | Platform, draft PR | `zotero/zotero` #6012 | AGPL-3.0 (SDT repo: none) | 2026-08-26 |
| **Adjacent** — Better Notes | Zotero plugin | `windingwind/zotero-better-notes` | AGPL-3.0 | 2026-08-24 |

Seventeen further projects were surveyed and set aside; see "Surveyed and set
aside" below for each one and the evidence that put it there.

---

## Plugins that index inside Zotero

### ZotSeek

**Position.** A Zotero 7/8 plugin that runs inside the Zotero process and adds
semantic search to the native UI, with an MCP server bolted on for coding
agents. Plugin first, server second — the mirror image of our shape. Observed
2026-08-29.

**Features.** Semantic search over embedded chunks, find-similar from a
selection, hybrid fusion with Zotero's own keyword search, section-aware chunk
labels (summary / methods / findings / content) from header pattern-matching,
two result modes (one hit per paper by best chunk, or every matching paragraph
with page and character offsets), automatic reference-section exclusion,
auto-indexing of new items, group libraries, and a choice of embedder including
a local OpenAI-compatible inference server on loopback.

**Licence.** No LICENSE file. Verified three ways: the repository contents API
lists no LICENSE at top level, `raw.githubusercontent.com/…/LICENSE` and
`…/LICENSE.md` both 404, and GitHub's own licence endpoint 404s. The GitHub API
reports `license: null` (re-checked 2026-08-29). `package.json` declares
`"license": "MIT"`, which is a self-description, not a grant.

**Architecture.** Embedding inference runs in a ChromeWorker thread on
Transformers.js, because Transformers.js cannot run on Zotero's main thread.
State lives in `zotseek.sqlite` in the Zotero data directory, separate from
`zotero.sqlite`: three tables, `items` keyed by `(library_key, item_key)`,
`chunks` keyed by `(item_pk, chunk_index, model_id)` holding base64 Float32
vectors plus location metadata, and `item_models` carrying per-model status,
content hash, and truncation flags. No FTS5 — keyword search is delegated to
Zotero. No vector index — search is a linear scan over pre-normalised vectors,
partitioned by `model_id`. Incremental update is auto-index on add plus
content-hash change detection.

**Limits.** The maintainer's own roadmap calls the paragraph chunker
overgrown and records that the search and hybrid-fusion paths have no
regression tests requiring real embeddings. GPU acceleration waits on WebGPU in
Zotero's Firefox ESR base. Deletion and orphan-row handling are undocumented.
Open issue #44 reports that the hybrid path's `minSimilarity` ignores keyword
hits; closed issue #33 was a database corruption on upgrade to 1.14.0.

**Performance.** All figures below are `(claimed)` by the maintainer on a
MacBook Pro M3: model load ~1,5 s; indexing ~3 s per chunk; first search
~200 ms; subsequent searches under 50 ms; ~75 MB resident for 1 000 papers;
~130 KB stored per 10 papers. Their own chunk-size ablation over 486
citation-pair queries on 646 papers `(claimed)` gives MRR 0,2514 at 512-token
chunks against 0,2550 at 2 000-token chunks, and concludes that chunk size
barely matters while the per-paper chunk ceiling (`maxChunksPerPaper`, default
100) does.

**Trends.** Created 2025-12-26, last push 2026-08-27, 191 stars, 10 forks, 2
open and 39 closed issues, not archived (GitHub API, re-checked by this reviewer
2026-08-29). Releases roughly every two weeks through 2026: v1.16.0 added the
MCP server (2026-06-11), v1.17.0 selectable multilingual models (2026-07-11),
v1.18.0 group libraries (2026-07-17), v1.19.0 local inference servers
(2026-08-12), v1.21.0 grounded keyword scores in hybrid search (2026-08-27).
One maintainer plus one minor contributor.

**What we learn.** Three things, and this is the most useful entry in the
survey. First, they converged independently on two of our ranking decisions:
reciprocal rank fusion at k = 60, and collapsing a document's chunks to its
best-scoring chunk before ranks are assigned. Their `SEARCH_ARCHITECTURE.md`
states the constant and the rule verbatim (read 2026-08-29). Two teams reaching
the same order of operations is corroboration for DESIGN.md §2.6, not a new
idea. Second, their `chunks`-keyed-by-`model_id` plus `item_models` coverage
table is a working answer to the embedder-change question DESIGN.md §2.7 (D3)
leaves open: switching model drops nothing, old vectors keep serving, and only
uncovered items queue for the new model. Third, and against them, the
maintainer told the Zotero forum on 2025-12-30 that books "lack the typical
paper structure (Abstract, Methods, Results) and are often too long to index
effectively", and confirmed on 2025-12-29 that 2 000 books at ten chapters each
would need about 16 hours to index, concluding that "for a library heavily
weighted toward long-form books rather than papers, the current architecture
might not be ideal". That is independent evidence that the 15 000-page-PDF
case DESIGN.md §2.2 stakes the segmenter on is genuinely unsolved, not
overthought. No code or corpus is borrowable: no licence, and the evaluation
set is not in the public repository.

### ZotSeek-Online

**Position.** A Zotero plugin, forked from ZotSeek, that moves embedding
inference from a bundled local model to an online API (Voyage AI). Observed
2026-08-29.

**Features.** ZotSeek's features, plus rate limiting and concurrency control
for outbound API calls. Abstract-only or full-document indexing modes, a
configurable token cap per chunk (800 on Zotero 7, 2 000 on Zotero 8), and
multi-query combination with AND/OR over up to four queries.

**Licence.** No LICENSE file. `raw.githubusercontent.com/…/LICENSE` and the
blob URL both 404; the GitHub API reports `license: null`. The README footer
says "MIT License - see LICENSE" and points at a file that was never added.

**Architecture.** Zotero plugin bootstrap, `zotero-plugin-toolkit`, TypeScript,
esbuild. Vectors cached in `zotseek.sqlite` in the Zotero data directory as in
the parent project. The dependency list carries no local-inference library,
consistent with the removal of on-device embedding.

**Limits.** Zero issues have ever been filed. That is not a clean bill of
health: the repository is a few hours of work with no users. The design's own
limit is that indexing is now priced and paced by an external provider, and
extracted text leaves the machine.

**Performance.** The README carries the parent project's figures unchanged
`(claimed)`: model load ~1,5 s, ~3 s per chunk, first search ~130 ms,
subsequent ~70 ms, ~130 KB per 10 papers. The ~3 s-per-chunk and model-load
figures read as local-inference timings retained after local inference was
removed; this reviewer did not diff the two READMEs to confirm.

**Trends.** Created 2026-03-20T11:35Z, last push 2026-03-20T13:16Z — a
two-hour window. Zero stars, zero forks, zero issues, two releases the same
day, nothing since. Not archived. Five months silent as of 2026-08-29.

**What we learn.** One thing, and it is about honesty rather than retrieval.
The fork inverted its own privacy posture and left the evidence contradicting
itself: the GitHub description still reads "100% local and private", the
CHANGELOG still describes a bundled local model, and only the README and
manifest record the switch. This is the duplicated-fact drift our own
one-statement-per-fact convention exists to prevent, observed in the wild. The
chunking parameters (800 or 2 000 tokens, page-driven, references filtered) are
a data point against DESIGN.md §2.2's token geometry, and coarser: nothing here
respects a structural boundary.

### Nodus

**Position.** A local-first Electron research workspace with a standalone
Zotero sidebar plugin that runs without the desktop application. Academic
research is one of five content areas the product covers. Observed 2026-08-29.

**Features.** The plugin indexes PDF, EPUB, and HTML attachments and answers
questions from them, combining keyword and semantic retrieval across languages,
returning exact passages with page citations that jump back to the source.
Embeddings come from a bundled local model or a configured provider — Anthropic,
OpenAI, OpenRouter, Groq, Cerebras, DeepSeek, Gemini, Ollama, LM Studio. A
separate feature queries about twenty public scholarly sources for works not yet
in the library.

**Licence.** AGPL-3.0-only, read at
`raw.githubusercontent.com/Drakonis96/nodus/main/LICENSE`. The README records
that versions through 3.2.7 were MIT and that AGPL applies from v4.0.0.

**Architecture.** Monorepo with `electron/`, `zotero-plugin/`, `server/`,
`browser-extension/`, `word-addin/`. The plugin folder holds only
`bootstrap.js`, `manifest.json`, and assets; it hooks Zotero through the native
plugin API and reads `~/.nodus/zotero-bridge.json` for a port and token, then
calls a local sidecar over `http://127.0.0.1:<port>`. The retrieval machinery
therefore lives in the sidecar, whose code was not reachable from the plugin
folder. Marketing says the index sits in the Zotero profile. Could not look: no
`zotero-plugin/README.md` exists (404), and no architecture document describes
chunking, storage, or staleness.

**Limits.** Closed issue #577 (2026-08-26) is the interesting one: dictionary
generation "can occasionally replace the requested concept synthesis with a
heading named 'Evidence verifiable' followed by a sequence of evidence
excerpts". A degraded extractive fallback rendered identically to a real
answer. Closed issue #565 (2026-08-25) reports the evidence-gathering pipeline
stalling indefinitely. Nothing in the tracker discusses index size or large
libraries; the project is ten weeks old. The issue list view and the API
disagreed on the open count (0 against 6); could not reconcile.

**Performance.** No numbers of any kind — no latency, memory, throughput, or
corpus size in the README, site, releases, or issues. Nothing to label.

**Trends.** Created 2026-06-14, last push 2026-08-29, 117 stars, 9 forks, 1 534
commits, not archived. Releases run about one a day: v4.2.3 to v5.0.6 between
2026-08-22 and 2026-08-28. The Zotero forum announcement (approximately
2026-08-12) has no replies. Could not look: the contributors graph failed to
render.

**What we learn.** Issue #577 is the cleanest external argument for the honesty
requirement in REQUIREMENTS.md R18: a fallback that looks like an answer is
worse than an empty result that names its scope. Nothing else is borrowable.
AGPL-3.0 with a network clause rules out code reuse for us, and the retrieval
mechanics are not published anyway. Read the absence itself as a signal: a
fast-moving, well-funded-looking competitor ships Zotero semantic search without
publishing chunking, storage, or staleness behaviour, and its tracker has not
yet forced it to.

### Beaver

**Position.** A Zotero plugin by ZotFile's author, presenting an AI agent that
lives in the reference manager, answers research questions with sentence-level
citations, annotates PDFs, and reaches roughly 240 million external works.
It also exposes its own MCP server. Observed 2026-08-29.

**Features.** Library-wide search over metadata, semantic vectors, and full
text; sentence-level citation with hover previews; AI-generated highlights
written back as real Zotero annotations; batch library operations behind a
review-and-undo card (v0.24.0-beta.1, 2026-08-27); group libraries since v0.5.

**Licence.** AGPL-3.0, read at
`raw.githubusercontent.com/jlegewie/beaver-zotero/main/LICENSE` and confirmed by
the GitHub API (`AGPL-3.0`, re-checked by this reviewer 2026-08-29).

**Architecture.** Split client and cloud. The plugin is a React front end;
`package.json` lists no vector store and no embedding library in production
dependencies, and `better-sqlite3` appears only as a development dependency.
`@supabase/supabase-js` is a production dependency: the retrieval backend is
hosted Postgres. The free tier does local processing with semantic search over
titles and abstracts and states that files do not upload, while "some
processing still occurs remotely"; the paid tier syncs selected libraries to
Beaver's servers, and that is where full-document search and sentence-level
citation live. Attachments process in Zotero modification-date order against a
page budget, not against a coverage ledger.

**Limits.** Open issue #35, "Local version", is the maintainer's own tracking
issue for running entirely locally; it lists as unresolved which vector
database, which embedding model, how to handle large collections, and whether a
JavaScript-native stack is viable inside Zotero's plugin constraints. No
developer replies are recorded. Forum reports describe sync failures on
libraries above 22 000 PDFs, which the maintainer acknowledged needs dedicated
testing. PDFs yielding under 150 characters are classified "insufficient text"
rather than routed to OCR. Collection-level indexing filters were declined on
complexity grounds.

**Performance.** `(claimed, maintainer)`: a free-tier budget of 125 000 pages,
about 4 000 articles at 30 pages; a 150-character extraction floor; "strong
retrieval performance" on a modified LitQA2 set of 197 questions, with no
numeric score published. A forum user reported sync failures above 22 000 PDFs
`(reported, not measured)`.

**Trends.** Created 2025-02-10, last push 2026-08-29T01:21Z, 242 stars, 17
forks, 35 open and 69 closed issues, not archived (GitHub API, re-checked by
this reviewer 2026-08-29). Weekly releases through August 2026, v0.23.0 on
2026-08-07 through v0.24.0-beta.1 on 2026-08-27. One human contributor plus an
agent account.

**What we learn.** The most consequential negative result in the survey. A
funded, actively shipping competitor has been at this for eighteen months and
still cannot run locally, and its own tracking issue lists exactly the unknowns
we carry. That is evidence our local-by-default commitment (REQUIREMENTS.md
R10) is unploughed ground rather than a wheel being reinvented. Their tier
split also locates the hard part precisely: sentence-level citation is what the
cloud buys, and page-level is what stays local. Entry-level locators are the
harder honest route to the same precision. Two mistakes to avoid, both cheap:
ordering work by modification date against a page budget leaves users unable to
learn what was indexed, and a bare character-count floor misclassifies scanned
PDFs as empty instead of marking them metadata-only with a reason
(REQUIREMENTS.md R1 already requires the latter). No code is borrowable: AGPL
plus a cloud-first architecture.

### PapersGPT for Zotero

**Position.** A Zotero plugin that also serves MCP, marketed as a
professional-grade local AI plugin with a C++ engine, supporting many hosted and
local models. Observed 2026-08-29.

**Features.** Chat with one or many PDFs, library-wide synthesis with
click-through citations, an autonomous agent mode that searches, tags, and
imports, OCR from images, and an MCP server whose search is described as BM25
over titles, creators, tags, abstracts, and annotations, plus retrieval of a
PDF's text by Zotero key.

**Licence.** AGPL-3.0-only for the plugin, read at
`raw.githubusercontent.com/papersgpt/papersgpt-for-zotero/main/LICENSE` and
confirmed by the GitHub API. The `docsagent/docsagent` repository, which the
marketing names as the engine, has no licence populated by GitHub's detector
despite prose claiming Apache-2.0, and no LICENSE file was located.

**Architecture.** The claim of a C++ engine is not verifiable from source. The
plugin repository's language breakdown is JavaScript 4,25 MB, TypeScript
211 KB, CSS 25 KB, and no C++; its tree holds no `.cpp` and no native addon.
The `docsagent` repository is TypeScript and JavaScript totalling about 17 KB,
far too small to be an indexing engine. The MCP configuration launches
`npx -y papersgpt-for-zotero mcp`, a thin wrapper spawning or fetching a
separate agent process. Where that binary's source lives could not be
established. No index format, storage engine, or refresh policy is documented
anywhere.

**Limits.** CVE-2026-73032: `execTag` passed unsanitised LLM output into
`window.eval()` in Zotero's privileged chrome context, exploitable through
prompt injection in a PDF or a hostile model endpoint, giving arbitrary file
access and process execution across the Zotero install. Issue #154, fixed by
PR #155. Open issues cluster on resource use (#158 CPU load, #151 the agent
using too much RAM), contradicting the low-memory marketing. Also open: #150
models not loading, #141 asking whether local-model support was dropped, #140
Zotero 9 support. No issue discusses BM25 correctness, index corruption, or
scale — consistent with an opaque engine users cannot diagnose.

**Performance.** `(claimed, v1.2.0 release notes, on a Mac Intel i9)`: 1 506
documents and 4,5 GB indexed in 141 s; 227 MB average agent memory; ~15 ms
average retrieval. `(claimed, marketing)`: "10 000+ documents in minutes". No
methodology, no baseline, no independent measurement.

**Trends.** Created 2024-11-22, last push 2026-08-28, 2 615 stars, 93 forks, 75
open issues, not archived. Releases roughly monthly and accelerating: v0.5.1
(2026-04-24) through v1.2.0 (2026-08-28). Five contributors, two of them
substantive. The lineage is evidenced rather than asserted: `ljeagle/zotero-chatpdf`
is a registered fork of `MuiseDestiny/zotero-gpt`, and `ljeagle` is the second
contributor here with 106 commits; the leftover `langchain`, `pinecone`, and
`chromadb` dependencies and the `eval`-on-model-output pattern travel with it.

**Performance claims and the record.** The public materials contradict
themselves on whether the tool embeds anything: one page says it moves beyond
fuzzy embeddings, another says the RAG stack of embeddings, vector database,
and reranker runs locally. No primary source reconciles them.

**What we learn.** Nothing reusable. The licence blocks the plugin layer, the
engine is closed, and no published methodology, corpus, or measurement bears on
any of DESIGN.md §3's open experiments. Two transferable warnings. Routing
model output into a privileged execution context is how CVE-2026-73032
happened, which is worth remembering if agent-style write tools are ever
considered. And a project whose own pages disagree about whether it embeds is
the failure our provenance discipline is built against.

### Awesome GPT for Zotero (zotero-gpt)

**Position.** The ancestor of much of this field: a Zotero plugin offering
inline GPT chat over a selection or the open PDF, driven by `#Tag` command
templates. Observed 2026-08-29.

**Features.** Ask a selection of items or the open PDF; summarise; generate
outlines (v2.0.2); annotate PDFs with AI (v3.1.4). Retrieval lives in
`Meet.Zotero.getRelatedText(queryText)`, which parses the current selection or
open PDF into paragraph documents, sends the chunk texts to OpenAI's embeddings
endpoint, and computes cosine similarity locally.

**Licence.** AGPL-3.0, read at
`raw.githubusercontent.com/MuiseDestiny/zotero-gpt/master/LICENSE`. The file was
updated to AGPLv3 on 2025-12-05, so the earlier licence identity is a separate
question this survey did not settle. A Zotero forum thread (opened 2026-02-15,
author reply 2026-02-19) alleges the distributed `.xpi` releases are obfuscated
and gate paid features, diverging from the AGPL source; the author is reported
as acknowledging this. Reported as an allegation, not verified against a binary.

**Architecture.** In-process plugin using Zotero's internal object model and
the PDF reader's API. There is no persistent index. The source says so
directly: a comment in `src/modules/Meet/Zotero.ts` reads
"注意：这里目前是不储存得到向量的，因为条目一直在更新" — vectors are not stored,
because items keep changing. The only cache is an in-memory map of parsed text
chunks keyed by an MD5 of the selected item keys, gone at restart. Embeddings
are computed remotely on every query. `package.json` lists `langchain`,
`pinecone`, and `chromadb`, but no code path was found that persists to any of
them.

**Limits.** Not scalable to a library: cost and latency scale with query
frequency, and there is no notion of library coverage, only of the current
selection. 241 open issues at the time of the check, including #515 (Gemini
embeddings returning response objects instead of vectors) and #519 (Volcano
Engine and Alibaba Cloud embedding configuration failing) — the embedding path
is fragile across providers. Item text is truncated to the first 500 characters
on the item-based path.

**Performance.** No numbers anywhere, which is itself notable for a tool that
offers to search a library.

**Trends.** About 7 400 stars and 315 forks (repository page, 2026-08-29); the
last substantive feature commit found was 2025-09-19, with a README edit
2026-04-20 and the LICENSE change 2025-12-05. Newest open issue #521 was filed
2026-08-18, so users remain active while development has thinned. Not archived.

**What we learn.** They ran the experiment we are building for and abandoned
it. The refusal to persist vectors "because items keep updating" is our
staleness problem, met and declined. DESIGN.md §2.1's separation of version
signals from content keys is therefore addressing a real difficulty that
somebody with 7 400 stars chose to route around rather than solve. Their
geometric line-merging chunker (font size, spacing, indentation, header and
footer removal, stop at references) is the closest thing in the field to a
fallback geometry heuristic for DESIGN.md §2.2's segmenter, and their v1.4.0
note about merging short paragraphs shows the tuning cost. Reading it is worth
a session; lifting it is an AGPL decision, and only from the repository, given
the obfuscation dispute.

### Aria (A.R.I.A.)

**Position.** The earliest widely-adopted Zotero AI plugin: a chat assistant in
the Zotero UI, requiring the user's own OpenAI key. Observed 2026-08-29.

**Features.** Drag Zotero items or collections into the chat context, visual
analysis of PDF annotations through GPT-4 Vision, chats saved back as Zotero
notes, a prompt library. Later commits added OpenAI's Assistants API (2024-12)
and agentic workflows (2025-02).

**Licence.** AGPL-3.0, read at
`raw.githubusercontent.com/lifan0127/ai-research-assistant/main/LICENSE`.

**Architecture.** No index, no chunking, no embedding, no vector store.
`package.json` carries no vector client and no PDF parser; `dexie` and `typeorm`
hold chat and settings state, not content. It calls Zotero's own in-process
search object model, forwards metadata to OpenAI on every turn, and holds
nothing derived. Stateless per query, the exact inverse of a ledger.

**Limits.** Open issues #155 ("Does it really read documents or just
metadata?"), #144 and #175 (full text not reaching the model), #118 (a
`TypeError` in `Zotero.Search.prototype.addCondition`, breaking the query path)
and #157 (no non-OpenAI providers) are all unresolved. The forum thread carries
reports of quotations that are not in the PDF.

**Performance.** No numbers published anywhere, which follows from the
architecture: nothing is indexed, so nothing was benchmarked.

**Trends.** About 1 700 stars, 116 forks, 97 open issues, 346 commits. Last
commit found 2025-04-01; last release v0.7.5 on 2024-10-20. A forum reply dated
2026-02 states the developer has stopped updating it. Not archived. Sixteen
months quiet.

**What we learn.** A negative result worth citing rather than a technique. The
most-starred early entrant still fields "does it really read documents or just
metadata?" as a live question, alongside reports of fabricated quotations. That
is precisely the failure REQUIREMENTS.md R17 and R18 exist to preclude: an
assistant answering from titles while implying it read the paper, with no
sentence saying which. Nothing here is borrowable.

### llm-for-zotero

**Position.** One of the two projects the author named as a seed. A Zotero
7/8/9 plugin putting a chat and agent interface over the PDF reader, described
by its README as a research agent system. Observed 2026-08-29.

**Features.** Chat and agent modes over the open paper; agent tools for
searching items and passages; note generation; MinerU used as an external
PDF-to-Markdown layout extraction service, cached locally as ZIP and JSON.

**Licence.** AGPL-3.0, read at
`raw.githubusercontent.com/yilewang/llm-for-zotero/main/LICENSE`.

**Architecture.** No index. The dependency list is `fflate`, `highlight.js`,
`katex`, `marked`, `mermaid`, and `zotero-plugin-toolkit` — no embedding
library, no vector store, no FTS, no SQLite. The README's own account of its
retrieval is conversation-context bookkeeping: it tracks which papers and
passages have already been inspected and reuses them. The legacy direct mode
states plainly that embeddings are not supported.

**Limits.** 127 open issues. The agent's library tools are read tools handed to
a model, with nothing behind them, so recall is whatever the model thinks to ask
for.

**Performance.** No retrieval numbers published.

**Trends.** 2 800 stars, 158 forks, 1 617 commits, last commit 2026-08-25
(v3.9.2). Very active, not archived. The `micheleben/llm-for-zotero_fork` mirror
shows no divergent retrieval features; could not look: no timestamp rendered on
its commit list.

**What we learn.** Recording the absence is the result. A 2 800-star project
positioned as a research agent over a Zotero library builds no index at all,
which sets the field's baseline: most "AI for Zotero" is model plumbing, not
retrieval. Its MinerU integration is the one adjacent idea — layout-aware
extraction as an external service — and it is a third-party API, not code to
borrow.

### seerai

**Position.** A Zotero 7/9 plugin offering chat, retrieval-augmented search,
federated external search across eleven providers, a systematic-review workflow,
and data extraction, with some MCP tool surface. Observed 2026-08-29.

**Features.** Per-context embeddings with chunking and a vector store; agentic
tool use; PRISMA-style review workflow; structured extraction tables; OCR
through Mistral, DataLab, or local Marker; cloud storage connectors.

**Licence.** MIT, read at
`raw.githubusercontent.com/dralkh/seerai/main/LICENSE`, copyright 2025 dralkh.

**Architecture.** TypeScript plugin, in-process. `package.json` declares no
SQLite, no vector database, no ONNX, and no transformers dependency, so the
vector store is either hand-rolled or delegated to a provider API the README
does not name. Indexing is explicitly per chat context, not whole-library: open
issue #14 requests pre-indexing and bulk embedding for collections and the full
library, which means that capability does not exist.

**Limits.** Four issues opened in one week, none resolved. #14 (no whole-library
index), #13 (context-limit validation blocks medium models, and Mistral
embedding vectors are discarded), #12 (retrieval fails on parent items and the
system injects raw unprocessed context instead), #11 (UI jitter).

**Performance.** No numbers, claimed or measured.

**Trends.** Created 2025-12-10, last push 2026-07-09, latest release v1.9.4 on
2026-07-03, 77 stars, 5 forks, not archived. Roughly a dozen releases between
2026-03-04 and 2026-07-03, then silence while issues kept arriving through
2026-08-03. One maintainer.

**What we learn.** Issue #12 is the useful one: when retrieval fails, the tool
silently dumps raw context and answers anyway. A unit of answer that is never
defined cannot fail loudly, which is the argument for the entry ruling and for
the scoped empty result in REQUIREMENTS.md R18. Their #13 — embedding vectors
discarded under some provider condition — is a concrete integration hazard to
test against whichever multilingual embedder we adopt. Nothing in their storage
layer is reusable, because none is committed.

### zotero-agent

**Position.** A Zotero plugin embedding a full MCP server over Streamable HTTP
with bearer-token auth, turning the library into a workspace an external agent
can read and mutate. Observed 2026-08-29.

**Features.** 47 MCP tools: hybrid semantic and keyword search, Web of Science
integration, metadata repair, identifier import, bulk bibliography import,
preprint-to-published upgrade, duplicate detection and merge, citation-graph
traversal, annotation synthesis, and a privileged `run_javascript` tool with a
timeout and a 100 KB output cap.

**Licence.** MIT, read at
`raw.githubusercontent.com/psiQAQ/zotero-agent/main/LICENSE`. The copyright line
reads "Copyright (c) 2024 the Zotero-MCP project contributors", which suggests a
rename from an earlier project; that is an inference from boilerplate, not a
confirmed history.

**Architecture.** In-process plugin, TypeScript. Hybrid keyword and embedding
search fused by reciprocal rank fusion, with a documented zero-result fallback
ladder. `package.json` declares no SQLite, vector database, ONNX, or
transformers dependency, yet a `semantic_status` tool reports index statistics,
so an index exists whose storage was not identifiable from the manifest. Version
2.2.1 made `get_content` read a native cache before invoking workers, to stop
timeouts on large indexed PDFs — a cache-first, lazily populated design rather
than a converging ledger.

**Limits.** One open issue, a `run_javascript` enablement bug filed 2026-08-23.
The thin tracker reflects a small user base, not a battle-tested search path.

**Performance.** No numbers. Only operational caps: Web of Science throttling,
and the 100 KB output limit on `run_javascript`.

**Trends.** Seven releases between 2026-07-07 (v2.0.0) and 2026-08-05 (v2.2.2),
commits 2026-07-08 to 2026-08-05, 7 stars, 1 fork, 1 open issue, no archive
banner. Could not look: the GitHub API returned 403 and 429 repeatedly for this
repository, so the creation date and full contributor count are unknown.

**What we learn.** Two interface ideas. Their `semantic_status` tool exposes
index completeness as a machine-queryable surface, the machine-readable
complement to the coverage sentence in DESIGN.md §2.8 — worth having alongside
it rather than instead of it. Their documented zero-result fallback ladder has
the same shape as the fill ladder in DESIGN.md §2.6; reading their actual
sequence would be worthwhile, and could not be done this session because GitHub
code search was rate-limited. Their v2.2.1 PDF-worker timeout fix is another
implementer meeting the large-document wall and patching after the fact.

### zotero-mcp (cookjohn)

**Position.** A Zotero 7+ plugin hosting its own MCP server inside the Zotero
process, giving assistants read and write access to the library over Streamable
HTTP. Bilingual documentation. Observed 2026-08-29.

**Features.** Twenty MCP tools across search, collections, semantic search, a
cached full-text database, and writes. Semantic search uses OpenAI, Ollama,
DashScope, Gemini, or Zhipu embeddings with vectors in sqlite-vec. Version 1.4.0
added chunking with structure detection, OCR-garbage filtering, and
sentence-level overlap; no token parameters are published.

**Licence.** MIT, read at
`raw.githubusercontent.com/cookjohn/zotero-mcp/main/LICENSE` and confirmed by
the GitHub API.

**Architecture.** The HTTP server runs inside the Zotero process on port 23120
by default, hand-rolled on Firefox XPCOM stream APIs rather than a Node
framework; the only runtime dependency is `zotero-plugin-toolkit`. Zotero access
is through the internal JS API. State lives in a separate
`zotero-mcp-vectors.sqlite` using sqlite-vec, plus a separate cached full-text
store, neither inside Zotero's own database. Incremental update fires from a
Zotero notifier hook behind a five-second debounce.

**Limits.** Open issue #95 (2026-08-05, Chinese) is the sharpest external lesson
in this survey. With `semantic.autoUpdate` on, embedding ran on Zotero's main
thread against a 7,4 GB vector database carrying no `-wal` or `-shm` companion
files — default rollback-journal mode — and froze Zotero completely: "Responding:
False" with 0 ms CPU over three seconds, so blocked on I/O or a lock rather than
computing. A 7,6 GB `.corrupt.` remnant sat beside it from an earlier forced
interruption, and the guard against duplicate work was an in-memory
`isAutoIndexing` flag that resets on restart. Also open: #97 (the hand-rolled
body reader corrupts every non-ASCII request body when the body arrives in a
separate TCP segment), #100 (items indexed before their PDF attachment is added
stay abstract-only forever), #104 (PDF extraction silently fails on Zotero 10).

**Performance.** `(reported by user lwz20210407, issue #95, 2026-08-05)`: a
7,4 GB vector database; 53 295 rate-limit hits across 72 899 requests. Both are
symptom reports, not benchmarks. Release notes claim search optimisation
(v1.4.5, 2026-03-20) and that the semantic index no longer stalls on bad items
(v1.5.0, 2026-06-11), with no figures.

**Trends.** Created 2025-08-14, last commit 2026-06-11, 1 110 stars, 92 forks,
23 open issues, 18 releases from v1.2.4 (2025-08-27) to v1.5.0 (2026-06-11), not
archived. Bug reports of the concurrency class kept arriving through 2026-08-26
with no release answering them. Nine contributors, 102 of about 123
contributions from one.

**What we learn.** Issue #95 is field evidence for three of our own choices at
once, none of them decorative. WAL is not optional at this size, and DESIGN.md
§2.2 sets it. Embedding work belongs in a separate process from anything
latency-sensitive, which is what the conductor-and-worker topology in DESIGN.md
§2.5 buys. A duplicate-work guard held in process memory does not survive a
restart, which is why the claim lives in a durable lease row. Their #100 —
abstract-only forever once an attachment arrives late — is a ledger that never
re-arms, and it earns an explicit case in the convergence harness of DESIGN.md
§2.8: index an item with no attachment, add the attachment, assert extraction
fires. Nothing on the ranking side is reusable; their relevance scoring has no
published method, and there is no sign the bibliographic record is kept apart
from chunk text.

### zotero-rag (cboulanger)

**Position.** A Zotero plugin paired with a separately run Python and FastAPI
backend, answering questions about a library with citations rendered inside
Zotero. Built for groups as well as individuals: one backend can serve a team,
with each caller's own Zotero API key checked against group membership. Observed
2026-08-29.

**Features.** Indexes PDF, HTML, EPUB, and DOCX through the Kreuzberg extractor,
replacing an earlier pypdf and spaCy pipeline in v1.3. Three agent-routed query
types — content, catalogue, citation — the last answered from Zotero's own local
full-text index rather than the vector index. Chunking is fixed at 512
characters with 50 characters of overlap, tracking `first_page` per chunk.
Deduplication by SHA-256 within a library; across libraries an identical file's
chunks and vectors are copied and re-keyed rather than recomputed. Item edits
are debounced four seconds and patched into vector-store payload metadata
through `set_payload()` without re-embedding.

**Licence.** No LICENSE file. The GitHub API reports `license: null`; both
`LICENSE` and `LICENSE.md` 404 on raw. The README asserts public domain for
machine-generated code and otherwise MPL-2.0, which is prose, not a grant. Treat
as unlicensed.

**Architecture.** The plugin reads Zotero through its local JavaScript API plus
`IOUtils.read` for attachment bytes, explicitly not SQLite, not the local HTTP
API, and not the Web API. The backend has no Zotero access at all: documents are
pushed to it over HTTP, a model adopted in v1.5 replacing an earlier design
where the backend needed Zotero access. Storage is Qdrant, with three
collections — `document_chunks`, `deduplication`, `library_metadata`. Staleness
keys on Zotero's own per-item and per-attachment `version` integer, not on a
content hash; a separate `CURRENT_SCHEMA_VERSION` bump drives a metadata-only
patch path. Each indexing batch runs in a fresh process so the operating system
reclaims memory between batches.

**Limits.** Open issues: #28 (an author's publication list comes back
incomplete), #25 (duplicates within and across libraries unresolved), #34
(collection structure not modelled), #31 (extractor choice unsettled), #23
(plugin and backend protocol versioning unenforced), #42 (auto-indexing key
management being reworked). Nothing in the tracker addresses large libraries or
very large single documents.

**Performance.** `(claimed)`: memory from about 0,5 GB fully remote up to about
16 GB on the high-memory preset; 5 chunks at 384 tokens on the CPU preset, 10
chunks at 1 024 tokens higher up; a cross-library deduplication speed-up of 10
to 100 times. No latency or recall numbers.

**Trends.** Created 2025-11-08, last push 2026-08-06, 6 stars, 0 forks, 9 open
issues, 438 commits, not archived. Ten releases between 2026-07-07 and
2026-07-24 under semantic-release automation. Version 1.x is declared beta.
Could not look: the contributor graph did not finish loading.

**What we learn.** One technique worth taking and one road not taken. The
technique is `check_embedding_compat.py`: before certifying a preset swap as
vector-compatible, they require cosine similarity at or above 0,999 across probe
texts. That is a cheap empirical gate for the embedder-change question DESIGN.md
§2.7 leaves open, and their own documentation concedes that a genuine model or
dimension change still forces a manual reindex with no migration, which supports
treating a key bump as full re-derivation rather than something to special-case
away. The road not taken is trusting Zotero's version counter alone as the
staleness signal: simpler than the signal-and-key split in DESIGN.md §2.1, and
unable to distinguish "reprocessed under a new chunker" from "unchanged". Their
preset system makes the gap concrete, since changing a preset stales the whole
index with no warning and no versioning. No code is borrowable: there is no
licence.

### BibGenie

**Position.** A closed-source Zotero plugin, formerly "Zotero Copilot" and
renamed under Zotero's trademark guidelines, putting a chat and agent panel in
the sidebar with a freemium model: a free tier with monthly credits on the
vendor's own model proxy, paid Pro, Max and Lifetime tiers, bring-your-own-key
providers, and Ollama or LM Studio for local inference. It also runs a local
MCP server for Cursor, Claude Code and similar clients. The r/zotero thread of
2026-08-29 asked for it by name against llm-for-zotero; nobody in the thread
had used it. Observed 2026-09-02.

**Features.** Context insertion of items, PDFs, snapshots, notes, selected text
and images; read-and-explain over the open paper; library search described by
the README as "semantic search over the local index of Zotero item titles and
abstracts"; save results back as Zotero notes; on paid plans, web search, web
extraction and an OpenAlex search tool. The documentation states in its own
words that library search "is not PDF full-text search".

**Licence.** None, and nothing to license: the repository `BaiRuic/BibGenie`
holds two READMEs, a `docs/` folder, a `public/` folder and the release
assets, and its README says "The BibGenie application source code is not
published in this repository." No LICENSE file (raw 404; the GitHub API reports
null). The predecessor repository `BaiRuic/ZoteroCopilot` has none either and
last moved 2025-11-09.

**Architecture.** Read from the shipped bundle, since no source is published:
release v0.8.4's `bibgenie-0.8.4.xpi` (10,5 MB compressed, 40,9 MB unpacked,
49 files), whose `content/scripts/bibgenie.js` is a 28,2 MB esbuild bundle
that keeps its module paths, so the structure is legible without the source.
Nothing below was run.

- *Index.* `src/semanticIndex/`: one row per regular item, holding one
  embedding of the abstract, in a sidecar SQLite opened through Zotero's own
  `DBConnection` class under the name `bibgenie_sidecar`, which Zotero resolves
  to a separate `.sqlite` file in the data directory. Nothing is written into
  `zotero.sqlite`. The row carries `item_id`, `library_id`, `zotero_key`,
  `zotero_version`, `client_date_modified`, a `content_hash`, the float32
  `embedding` blob with its precomputed `embedding_norm`, and the model triple
  `(embedding_model_unique_id, embedding_model_id, embedding_dimensions)`, with
  a search-scope index on library plus that triple. A second table keeps
  per-library index state (the model triple, `last_scan_timestamp`,
  `max_client_date_modified`, `item_count`, `embedding_count`); a third keeps
  failures with a `failure_count` and a next-retry time.
- *Refresh.* Constants in `src/semanticIndex/constants.ts`: abstracts under 40
  characters are skipped; embedding calls go in batches of 64; edits are
  debounced 1,5 s; a failed item retries with exponential backoff from a 1 h
  base and is abandoned after 5 failures; a full diff of the library against
  the sidecar runs whenever the state row is missing, the model triple changed,
  the counts disagree with the library, a newer `clientDateModified` is seen,
  or two days have passed since the last scan.
- *Query.* The query is embedded through the same provider, every compatible
  row for the library is loaded (`SELECT * … ORDER BY item_id`), each blob is
  decoded and scored by cosine against the stored norm in JavaScript, and
  scores under 0,4 (`ITEM_ABSTRACT_MIN_SIMILARITY`) are dropped. A linear scan
  over one vector per item.
- *Embedder.* Remote only: the bundle wires the Vercel AI SDK's
  OpenAI-compatible and gateway embedding models and carries no ONNX runtime
  and no transformers library. The vendor's roster is fetched at run time from
  `llm.bibgenie.com/api/v1/models`, a proxy the bundle names as an OpenRouter
  front. Could not look: no default embedding model id appears in the bundle.
- *Keyword side.* Zotero's own quick search through `Zotero.Search`, with
  `quicksearch-fields` as the default mode and `quicksearch-everything` as an
  option. The platform's search, not theirs.
- *Full text.* PDFs are extracted in-process by a bundled MuPDF WebAssembly
  build (10 MB) in a worker hosted by Zotero's main window, sentences split by
  a bundled `sentencex` WebAssembly module, and the result cached in a second
  sidecar database, `bibgenie_document_cache`, keyed on file path, mtime and
  size. No table holds passage vectors: full text reaches the model as context
  and is never indexed.

**Limits.** The index covers the abstract and nothing else, by design and by
its own documentation ("Papers without abstracts may be harder to match"). An
item whose abstract is under 40 characters is not in the index at all. The
0,4 cosine floor is one constant applied to whichever embedding model the user
selects, although cosine scales differ by model, so the floor filters
differently for each. 2 open issues, 15 stars, 2 forks, 9 commits in the
public repository, which tracks releases rather than code.

**Performance.** No numbers, claimed or measured. The v0.8.4 asset shows 467
downloads at observation.

**Trends.** Repository created 2025-11-08; releases v0.8.2 and v0.8.3 on
2026-08-22, v0.8.4 on 2026-08-30; not archived. Manifest range Zotero 7 to 10.
The vendor site and a Discord server carry the community; the tracker is
nearly empty.

**What we learn.** Two things, pulling in opposite directions. The refresh
machinery is the field's second real ledger after lit-lake's: a content hash,
a per-model scope on every row so a model switch invalidates nothing it should
keep, a failures table with bounded exponential retry, and a periodic full
diff triggered by any disagreement between the state row and the library. The
count-mismatch trigger is a cheap reconciliation idea worth having, and the
sidecar-through-`DBConnection` route is the platform-sanctioned way to keep an
index beside `zotero.sqlite` without touching it. And then the ledger guards
an index of abstracts: the cap moved from "pages" to "the abstract", the most
severe in the survey, and the same choice Beaver's free tier and
`text70/zotero_ai` make. The user who started the Reddit thread wanted
semantic search over the full text of books; nothing in this bundle indexes a
page. Closed source means none of it is borrowable, and this description is
the whole of what can travel.

### Zotero AI (text70)

**Position.** A one-person Zotero 9 plugin, four days old at its last push,
offering a command interface (`#summarize`, `#ask`, `#translate`, `#search`,
`#web`) over any OpenAI-compatible endpoint. Listed by Citation Styler's
overview as early-stage. Observed 2026-09-02.

**Features.** Chat over the selected item's metadata and Zotero's full-text
index for that item; `#search`, described as "RAG over your library — embed
titles + abstracts locally, then run a vector search for the most relevant
passages (top-5), no heavy vector DB required"; `#web` through function
calling.

**Licence.** AGPL-3.0, read at
`raw.githubusercontent.com/text70/zotero_ai/main/LICENSE`.

**Architecture.** `src/modules/search.ts` is the retrieval layer, 82 lines.
`buildIndex` walks every top-level item, concatenates title and abstract,
truncates, and sends the texts to the configured `/embeddings` endpoint
(default model `text-embedding-3-small`; OpenRouter has no embeddings endpoint,
so the README points users at a local one). `search` embeds the query, scores
every vector by a hand-written cosine, sorts, and slices the top k. The index
lives in a module variable: nothing is persisted, so each session rebuilds it
and pays the embedding cost of the whole library again. Dependencies are
`katex`, `marked` and `node-html-parser`. The API key is stored in a
preference in plain text, which the README says itself.

**Limits.** Rebuild-per-session, so cost grows with the library on every use.
The README's roadmap leaves "Batch-embedded large libraries" unchecked.
`#search` throws when the build is stale. 3 stars, no open issues.

**Performance.** None claimed.

**Trends.** Created 2026-08-06, last push 2026-08-10, no releases beyond the
`.xpi` the README points at. Too young to read a trend.

**What we learn.** This is the floor of the field: a semantic search over a
Zotero library is 82 lines, an embeddings endpoint, and no storage, and it
ships within a week. Three independent projects now make the abstract-only
choice (this one, BibGenie, Beaver's free tier), which says the choice is the
path of least resistance rather than a considered cap. Nothing here is prior
art for storage, staleness, or scale, and the AGPL rules out the lines in any
case.

---

## Servers and command-line tools outside Zotero

### zoteus — the reference point

**Position.** The MCP server this project's design is being built into, and the
upstream contribution target. Announced on the Zotero forum 2026-06-07, framed
by its maintainer as "not a Zotero plugin — it runs alongside Zotero on your own
computer". Observed 2026-08-29.

**Features.** Hybrid keyword and semantic search across metadata, abstracts, and
attachment text, with passage extraction carrying page number, character offset,
and nearest heading. FTS5 keyword search. Vector embeddings with local, OpenAI,
or Gemini backends (`ZOTEUS_EMBEDDINGS`); full-text indexing opt-in
(`ZOTEUS_INDEX_FULLTEXT`). Citation formatting through citeproc-js over about
2 800 CSL styles. Transactional writes with optimistic locking and gated
permanent delete. Roughly thirty consolidated tools.

**Licence.** MIT, read at
`raw.githubusercontent.com/oscardvs/zoteus/main/LICENSE`, copyright 2026 Oscar
Devos.

**Architecture.** Two index backends behind a `SearchIndex` abstraction: the
legacy JSON path, and SQLite with FTS5 since v1.7.0. `src/features/search`
carries a vector store, an embeddings module, a chunker, and an index manager;
`docs/architecture.md` gives no schema, dimensionality, or chunk geometry, so
those live only in source. Transport prefers the local desktop HTTP API for
reads and personal-library writes, falling back to the Web API for group writes
or when the desktop application is down.

**Limits.** Four open issues, and three of them are the design's own agenda.
Issue #30 (filed 2026-08-28) reports semantic search taking 90–105 s per query
because the query decodes and dot-products every vector row in JavaScript.
Issue #29 (2026-08-28) reports that `zotero_get_fulltext` returns only what
Zotero already extracted, so recent additions, failed OCR, and `.eml`
attachments come back empty. Issue #26 (2026-08-28) reports that
`action:'update'` never sees full text extracted after the initial build. Issue
#24 (2026-08-27) reports that under the local API a stopped index resumes by
full rebuild, because the local API carries no library-version stamp. Closed
issue #10 recorded the prior JSON index failing silently near 400 000 passages
against V8's maximum string length while the build still reported success.

**Performance.** `(measured by Michael-Logies, issue #30, 2026-08-28)`: 90–105 s
per semantic query on an index of 10 184 items and 255 703 passages at 3 072
dimensions, against about 13 s for a ChromaDB-backed alternative on the same
task, with memory flat near 110 MB — CPU-bound, not memory-bound. `(claimed,
v1.7.1 release notes, 2026-08-26)`: startup 2 033 ms to 199 ms. `(measured by
the reporter of issue #10, 2026-08-21)`: a 7 540-item library produced 477 511
passages and 546 MB, past the JSON ceiling. No RAM, CPU, or warm-query budget is
published anywhere upstream.

**Trends.** 29 stars, 2 forks, MIT, 4 open against 12 or more closed issues, not
archived. Ten releases in nine days: v1.4.1 (2026-08-19) through v1.9.0
(2026-08-28), with v1.7.0 (2026-08-25) shipping the SQLite and FTS5 backend.
Eight pull requests, six of them merged; six of the eight are from this
project's author. Could not look: commit-list pagination did not reach the
repository's first commit, so the creation date rests on the 2026-06-07 forum
post.

**What the vehicle already provides.** A working SQLite and FTS5 backend, vector
search with the chunker and embeddings already factored apart, dual local and
cloud transport with a stated preference order, and accent folding on both index
and query sides since v1.7.2. The maintainer merges contained pull requests
within days.

**What the design still has to add, now with field evidence.** Issue #30 is the
strongest single measurement in this survey and it is about us: a linear
JavaScript vector scan is unusable at 255 703 passages, less than half the
passage count DESIGN.md §2.9 budgets for. That makes the X1 int8 experiment
(DESIGN.md §3) a live necessity rather than an optimisation. Issue #24 confirms
that the local API has no version stamp, which is exactly the gap the ledger of
DESIGN.md §2.1 and §2.4 closes. Issue #29 is a dependency we inherit through the
same transport and do not yet claim to close: extraction quality is Zotero's,
including its failures. Nothing upstream addresses the entry unit, the
15 000-page-PDF case, resource budgets, deletion and pause semantics, or
coverage honesty; those remain this project's additions rather than parity work.

### zotero-mcp (54yyyu)

**Position.** The field's most popular MCP server: a Python package exposing a
Zotero library to assistants, with an MCP server, a CLI, and Docker images.
Observed 2026-08-29.

**Features.** Keyword and advanced metadata search, collection and tag browsing,
BibTeX and Markdown export, full-text retrieval, annotation extraction, semantic
search over ChromaDB with four embedding backends, opt-in passage chunking with
character and page provenance, writes by DOI or URL with an open-access PDF
cascade, Scite citation intelligence, and an opt-in direct-SQL search backend for
speed on large libraries.

**Licence.** MIT, read at
`raw.githubusercontent.com/54yyyu/zotero-mcp/main/LICENSE`, copyright 2025
Zotero MCP Contributors.

**Architecture.** Talks to Zotero over the local HTTP API or the Web API, with a
hybrid mode doing local reads and web writes. State lives in
`~/.config/zotero-mcp/chroma_db/`, one vector store per install rather than per
library; multi-library results carry a `group_id` field. Incremental update uses
per-library watermark scalars, `last_sync_versions`, keyed by `group_id`.
Extraction moved to `pdf-inspector` behind a single seam at v0.8.0, replacing
`markitdown`. Indexing granularity is one attachment per item: a priority
function picks the largest attachment, and the rest are invisible to the index.

**Limits.** Open issue #494 (2026-08-25) records that second attachments are
silently dropped from the index. Open issues #495, #493, and #496 (late 2026-08)
record that duplicate and cross-library content is not deduplicated, so the same
PDF in two libraries produces duplicate hits. Open issue #492 records semantic
hits from group libraries rendering as bare item keys because metadata
enrichment fails. Historical issue #74 recorded full-text indexing hanging
indefinitely on individual PDFs in an 8 800-item library, over fifteen minutes
inside `pdfminer.layout.group_textboxes()` with no timeout; the v0.8.0
extraction overhaul is the likely mitigation, not a confirmed closure.
`pdf_max_pages` defaults to 50 and `fulltext_display_max_pages` to 10. 56 open
against 198 closed issues.

**Performance.** `(claimed, maintainer changelog v0.8.0)`: extraction from
1,6–2,4 s to about 0,1 s per paper. `(claimed, changelog v0.9.0, 2026-08-03)`:
tool surface from 62 tools and about 22 900 tokens to 37 and about 13 800.
`(claimed, README)`: 98 tokens of CLI frontmatter against 13 448 for the full
MCP server. No independent measurement found.

**Trends.** Created 2025-03-22, last push 2026-08-25, 4 829 stars, 383 forks,
not archived. Releases roughly weekly through the summer of 2026, v0.6.0
(2026-06-22) through v0.11.0 (2026-08-25). Eighty contributor logins, heavily
maintainer-driven. Two PyPI names exist and disagree: `zotero-mcp` sits at 0.3.1
(2026-08-07) while `zotero-mcp-server` sits at 0.11.0 (2026-08-25), against a
changelog asserting both names reference one distribution. Could not resolve
that discrepancy from public sources.

**What we learn.** Their v0.7.0 bug is the useful one: a single global
`last_sync_version` shared across libraries made a sync of one library read
another's documents as deleted and purge them. That is the failure the
per-library, per-stage scoping of DESIGN.md §2.2 and §2.4 makes unwritable, and
it happened to the field's most-installed server. Issue #494 is the item-unit
assumption breaking one level above ours: they lose a second attachment, we
would lose 1 849 dictionary entries, and it is the same defect class. Their
`pdf_max_pages` default of 50 is a data point for the synthesis below. Their
`db-status` command is their answer to coverage reporting; could not look: its
output schema is undocumented and `docs/semantic-search.md` 404s.

### zotero-mcp-postgres-ollama-fulltext (tspspi)

**Position.** A personal, manually copied derivative of 54yyyu/zotero-mcp
replacing ChromaDB and local sentence-transformers with PostgreSQL, pgvector,
and Ollama or OpenAI embeddings. The README states plainly that it is not the
official project. Observed 2026-08-29.

**Features.** The parent's tool surface, plus semantic search with a
configurable similarity threshold (default 0,7) and result limit (default 50),
full-text extraction and indexing, incremental and force-rebuild commands with
configurable worker and batch counts.

**Licence.** MIT, read at
`raw.githubusercontent.com/tspspi/zotero-mcp-postgres-ollama-fulltext/main/LICENSE`.

**Architecture.** `pyzotero`, toggled by `ZOTERO_LOCAL` between the local HTTP
API and the Web API. PostgreSQL 15+ with pgvector; four tables —
`zotero_embeddings` (a `vector(1536)` column, content hash, chunk index, parent
item), `zotero_attachments` (extraction status and retries), `zotero_config`,
`zotero_updates` (a batch audit log). The vector index is IVFFlat with
`lists = 100`, not HNSW. There is no `tsvector` or GIN index anywhere: despite
the repository name, "fulltext" means the pipeline embeds the whole extracted
body, not that lexical search exists.

**Limits.** Zero issues, open or closed. With 3 stars and no visible users, that
is an absence of reporters rather than an absence of defects. The structural
limit is an always-running PostgreSQL server.

**Performance.** No numbers of any kind. The `lists = 100` IVFFlat parameter is
a rule-of-thumb default, not a stated target, and should not be read as either
claim or measurement.

**Trends.** Created 2025-08-24, last code push 2025-11-28 — nine months stale.
3 stars, 0 forks, not archived. Commits clustered July to November 2025, then
nothing. Three distinct commit authors appear, including the parent project's
maintainer.

**What we learn.** Mostly the divergence. The fork's only stated motivation is
dependency weight, "removed heavy ML dependencies (torch, transformers)" —
a packaging concern, not a complaint about ChromaDB's recall or scale, and
therefore weak evidence about anything we chose. Two things are worth keeping.
The name is a false cognate: "fulltext" here is semantic-only, with no lexical
layer, so the project must not be cited as hybrid prior art. And a solo
maintainer preferred adding a PostgreSQL daemon to fixing an embedded store,
which is anecdotal market signal that embedded vector tooling in this ecosystem
is awkward enough to drive people to a full database server. Our one-process
constraint is a deliberate trade against exactly that.

### deep-zotero

**Position.** An MCP server, installable as a Claude Code plugin or a PyPI
wheel, driven by an agent rather than a human. Formerly `zotero-chunk-mcp`; the
old path 301-redirects to the new one, same repository ID, so this is a rename
and not a fork. Observed 2026-08-29.

**Features.** Extraction with section classification (abstract, introduction,
methods, results, discussion, conclusion, references, appendix, preamble),
vision-based table extraction, caption-driven figure detection, Tesseract OCR
fallback. Ten MCP tools including topic search, passage-context expansion,
citation-graph lookup through OpenAlex, and vision cost tracking. Reranking by a
composite score: similarity raised to alpha (default 0,7) times a section weight
(1,0 for results, conclusions, and tables, down to 0,1 for references) times a
journal-quartile weight (Q1 1,0 down to Q4 0,45) from a bundled Scimago table.

**Licence.** MIT, read at
`raw.githubusercontent.com/ccam80/deep-zotero/main/LICENSE`, copyright 2026
Chris Cameron; re-checked by this reviewer 2026-08-29.

**Architecture.** Reads `zotero.sqlite` directly through
`sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)`, with
attachment paths resolved by `linkMode`. State is split across ChromaDB, a
bespoke `index_stats.sqlite`, and flat files. Chunking is a fixed 400-token
sliding window with 100-token overlap, breaking at a sentence-ending mark in the
last fifth of the window, with a page number and a section label attached
afterwards. Staleness keys on a SHA-256 of the **first 64 KiB** of the PDF; a
separate config hash covering chunk size, overlap, embedding model, and OCR
language only warns on mismatch unless `--force` is passed.

**Limits.** One issue ever filed, a packaging confusion, closed 2026-03-03. From
the code and README rather than the tracker: the truncated hash cannot see an
edit past the first 64 KiB; a config change warns rather than re-deriving;
phrase search, stemming, and synonym expansion are unsupported; citation tools
need a DOI; the embedder is Gemini by default or an English-tuned MiniLM
locally, with nothing said about other languages; a single contributor and no
external review on any merged pull request.

**Performance.** No published benchmark. The one stress test runs against ten
papers from the maintainer's own library with qualitative pass and fail
expectations, no timings and no recall. `(claimed, README)`: about $0,016 per
table for vision extraction.

**Trends.** Created 2026-02-01, last push 2026-07-30, 106 commits by a single
author, 9 stars, 3 forks, 0 open and 1 closed issue, not archived. Activity is
two bursts: a handful of commits in February 2026, then fourteen pull requests
merged between 2026-07-28 and 2026-07-30. No GitHub releases; shipping is to
PyPI only, latest 0.2.2 on 2026-07-30.

**What we learn.** Their figure-detection pipeline is the field's most seriously
engineered heuristic segmenter: it merges overlapping and nearby graphics boxes,
detects side-by-side columns by y-range overlap, splits boxes when captions
outnumber regions, and falls back through picture boxes to image info to
vector-graphics clustering. It solves a different problem from ours, but it is
an existence proof that a multi-fallback geometric heuristic works in practice —
relevant to the confidence-and-fallback structure of the segmenter in DESIGN.md
§2.2. The truncated 64 KiB staleness hash is a named mistake to avoid, not a
hypothetical. Their `get_passage_context` tool locates body text that cites a
given table by regex-scanning the document's other chunks; the idea is
interesting and the mechanism would not survive our corpus. Their tool count
fell from thirteen to ten in one refactor by folding boolean search into the
semantic tool as parameters, which is worth remembering if our own tool surface
grows.

### ZotPilot

**Position.** A Python package bundling an MCP server of roughly twenty to
thirty tools with five packaged agent skills, aimed at a researcher with a few
hundred papers whose keyword search is failing. Observed 2026-08-29.

**Features.** Reads `zotero.sqlite` read-only plus PDF storage; extraction
through `pymupdf4llm` and `pymupdf-layout`; section classification and
section-tagged chunking; ChromaDB index; embedding backends including local
MiniLM, Gemini, DashScope, SiliconFlow, Zhipu, Ollama, and any OpenAI-compatible
endpoint, with the dimension set explicitly by the user and a mismatch raising
at collection load. Chapter-aware reranking with a `section_type` filter.
Citation graph through OpenAlex. Display-formula indexing since v0.5.3.

**Licence.** MIT, read at
`raw.githubusercontent.com/xunhe730/ZotPilot/main/LICENSE`, confirmed by the
GitHub API (re-checked by this reviewer 2026-08-29).

**Architecture.** Reads are direct SQLite (`mode=ro&immutable=1`); writes go
through the Zotero Web API via `pyzotero`, never direct SQLite writes.
Incremental indexing keys on a PDF content hash, with interruption recovery,
orphan cleanup, and cross-process locking between the CLI and the MCP server
added in v0.5.0 and v0.5.1. An `index_authority.py` module governs
reconciliation.

**Limits.** Documents over 40 pages are skipped by default; `--max-pages`
overrides. Open issue #39 (2026-06-22, from an outside contributor) reports that
the chunker sizes chunks by characters divided by four as a token estimate, so
dense academic text silently overflows the embedding window and "the tail of the
passage is never represented in the vector"; a token-aware chunker is proposed
and unmerged. Open issue #38 (2026-06-22) reports that orphan cleanup compares
indexed documents only against the personal library, so anything indexed from a
group library is treated as an orphan and deleted on the next run. Open issue
#50 (2026-07-28) reports the MCP server refusing to open an index the CLI had
just built, on Windows, root cause unidentified.

**Performance.** `(claimed, README)`: about 2–5 s per paper, roughly fifteen
minutes for 300 papers; preflight checking cut from 20 s to 3 s in v0.5.3. No
query latency, no memory figures, nothing above a few hundred papers.

**Trends.** Created 2026-03-16, last push 2026-06-28, 71 stars, 14 forks, eight
tagged releases from v0.2.1 (2026-03-22) to v0.5.3 (2026-06-16), then ten weeks
quiet with three unanswered issues, not archived.

**What we learn.** Their chapter detection answers a question we had open, and
answers it more simply than expected: regex and keyword matching of extracted
heading text against a fixed vocabulary, plus a second pass reclassifying spans
as references by content signals (DOI and URL density, numbered-reference
patterns, year-and-author patterns), using neither font size nor page position.
That is a lower bound on what heading detection can mean. Their fallback for a
document with no headings is a bare `unknown` label and a constant confidence,
which is a gap rather than an answer — independent confirmation that the
segmenter in DESIGN.md §2.2 is unploughed ground. Two mistakes to avoid, both
sharp. Their chunker windows raw character offsets first and attaches section
labels afterwards, so a chunk can straddle a section boundary: the exact
inversion of the boundary ruling. And issue #39 is a direct warning against
estimating tokens by a character ratio, which the token geometry in DESIGN.md
§2.2 must not repeat. Their 40-page default cap is the field's bluntest
statement about who its users are, and it is the opposite of REQUIREMENTS.md R8.

### lit-lake

**Position.** An MCP server packaged as a one-click Claude Desktop extension,
positioned against black-box AI services. Observed 2026-08-29.

**Features.** Library sync covering references, attachments, notes, annotations,
and web snapshots; full-text extraction with two swappable backends, local
(`pymupdf` plus `trafilatura`) or Gemini; local embeddings through `fastembed`
with `BAAI/bge-small-en-v1.5` and a `bge-reranker-base` reranker exposed as a
`rerank_score()` SQL function; vector search through sqlite-vec; PDF page
rasterisation so an agent can look at a figure; a durable job queue with a CLI
to inspect its depth.

**Licence.** No LICENSE file. The repository contents API lists none, and the
repository metadata's `license` field is null; re-checked by this reviewer
2026-08-29 against the repository page, whose sidebar shows no licence. Nothing
here is licensed for reuse.

**Architecture.** Reads `zotero.sqlite` directly. Change detection is
field-level diffing — title, authors, year for references; content, file id,
metadata for documents — not version counters. State is one SQLite database
under a configurable data directory: `reference_items`, `document_files`,
`documents` (chunks with a `kind` discriminator covering `fulltext_chunk`,
`note`, and `annotation`), and `vec_documents`, a sqlite-vec `vec0` table of
`float[384]`, unquantised. There is no FTS5 table: lexical access goes through
plain content columns. Chunking splits on paragraphs, falls back to sentences,
then to characters, at 512 tokens, with no overlap and no heading prefix.

The job ledger is the part worth reading. `jobs` carries queue name, job type,
entity, a UNIQUE `dedupe_key`, payload, status, priority, `available_at`,
`claimed_by`, `claim_token`, `claim_expires_at`, attempts, `max_attempts`, and
last error, indexed for polling and for claim-expiry sweeps. `job_attempts`
carries one row per attempt with worker id, backend name and version, start and
finish, outcome, error class, and metrics. `worker_runs` carries one row per
worker with heartbeat and status. Claim assigns a lease (default 180 s, minimum
15 s) and opens an attempt row; a renewal thread extends it; a sweep returns
expired claims to retry or to dead; failures are classified permanent or
transient, with exponential backoff at `base * 2^(attempts-1)`, capped, plus up
to 25 % jitter. Migrations are one-way smell-detection and repair with SHA-256
integrity checks and no downgrade path.

**Limits.** Open issue #16 reports "database is locked" during sync: extraction
failures leave chunks permanently pending, the embedding worker holds a lock on
them, and `sync_zotero` then fails indefinitely across restarts. Open #40 (no
way to reset dead jobs), #39 (items with several attached files are not all
processed), #35 (no CPU throttling; embedding takes all cores), #22
(reinstalling resets configured paths), #38 (poor support for non-paper item
types). Seventeen open against eight closed, with a backlog of unmerged feature
pull requests — multilingual embeddings, chunk context windows, annotation
handling, collections — open since March 2026.

**Performance.** `(claimed, README)`: about 500 MB of model download on first
run. `(reported by users)`: libraries of 401 references and 293 PDFs (issue #16,
filed 2026-02-23) and 699 files (issue #13) — small personal libraries, an order
of magnitude below our design point. The 180 s default lease implies jobs of
minutes. No latency, memory, or recall figures are published.

**Trends.** Created 2025-12-22, last push 2026-07-04, 87 stars, 5 forks, nine
releases from v0.1.0 (2025-12-23) to v0.4.2 (2026-02-27) and none since, not
archived. Version 0.4.0 was a full rewrite from Rust extraction to Python and
PyMuPDF, five weeks after v0.3.0.

**What we learn.** The most directly comparable ledger in the field, and worth
studying on two points. Separating the attempt audit trail (`job_attempts`, one
row per try, with error class and metrics) from the job's own retry counter is a
clean normalisation: it makes the transient-versus-permanent failure history
queryable per unit of work, which is exactly the raw material the work counters
of DESIGN.md §2.8 need, and it keeps that history out of the live row. Their
backoff formula and their permanent-versus-transient error classification are a
shipped reference for the failure policy DESIGN.md §1 carries forward. Against
them: their lease is single-process with in-process worker threads, so there is
no cross-process election to compare with DESIGN.md §2.5; their migrations have
no downgrade path, which REQUIREMENTS.md R23 forbids; and issue #16 is another
direct-SQLite lock failure. No code is borrowable, because there is no licence.

### zotmcp

**Position.** An MCP server for semantic search across one specific shared
Zotero group library, `prosocial` — a bespoke deployment for one research group
rather than a general tool. Observed 2026-08-29.

**Features.** Seven tools: semantic search, item retrieval, similar-item
discovery, collection statistics, author discovery through OpenAlex, broad paper
search, and citation retrieval. Full text comes from the Zotero group first,
falling back to extraction from the PDF.

**Licence.** No LICENSE file. `raw.githubusercontent.com/…/main/LICENSE` and the
`master` variant both 404; the GitHub API reports `license: null`, and the root
listing shows no LICENSE among eighteen files. Unlicensed, all rights reserved.

**Architecture.** A centrally hosted ChromaDB collection, not a per-machine
index: users either point at the shared instance with cloud credentials or
download roughly 8 GB of vectors. Embeddings are `gemini-embedding-001` at 3 072
dimensions. Ingestion runs through an external pipeline not vendored here.
Incremental update is checkpoint-based: a stored `last_version` gates a
per-item fetch, an existence filter deduplicates already-embedded items, and the
checkpoint advances only for items actually processed. Chunking is a generic
semantic splitter at about 1 000 tokens with 250 of overlap, with no structural
awareness. A URL-only attachment is skipped.

**Limits.** The README's own caveats are the useful part: embeddings are
"concept-literal, not strongly synonymic", so users are told to use the
literature's own vocabulary and try several phrasings; `n_results=15` often
returns three to five items because of an undocumented confidence threshold;
absolute scores are not calibrated across queries; and the response does not
report corpus total, count above threshold, or count returned, so a caller
cannot tell a small library from an aggressive filter. Open issue #7 (2025-11-25,
still open) asks for per-user Zotero API keys.

**Performance.** `(claimed, docs)`: about $0,002 per new item indexed; about
8 GB for the local vector download, with no stated item count behind it. No
latency, corpus size, or recall figures.

**Trends.** Created 2025-10-01, last push 2026-06-23, 0 stars, 0 forks, 1 open
issue, no releases, not archived. Recent commit subjects are CI plumbing. One
human maintainer plus bots.

**What we learn.** Their self-disclosed honesty gap is our requirement, stated
by someone who hit it: uncalibrated scores and an unreported
total-threshold-returned triad leave the caller unable to interpret a short
result list. REQUIREMENTS.md R18 and the `scope{}` block of DESIGN.md §2.6 are
the fix, and this is independent evidence that the problem bites in practice.
Their checkpoint-and-existence-filter incremental indexing is a coarse,
item-level cousin of our ledger; nothing in their documentation suggests it can
resume mid-pipeline after a partial failure, which is what the four-stage
staging buys. The group-library use case is confirmed real and their answer is
narrower than REQUIREMENTS.md R12: one hardcoded group behind one shared
credential.

### zotero-rag (`zqa`, Rust)

**Position.** A standalone Rust CLI answering natural-language questions over
Zotero PDFs, with a nascent GUI. Observed 2026-08-29.

**Features.** Own PDF extraction crate, dropping tables and figures
deliberately; two chunking strategies, whole-document or section-based;
embeddings through Voyage, Cohere, or Gemini; a separate reranking step;
generation through Anthropic, OpenAI, Ollama, Gemini, or OpenRouter; LanceDB
storage with an automatic IVF-PQ index on embeddings and a separate full-text
index on text columns; incremental indexing by set difference.

**Licence.** Dual, and both files were read. The root LICENSE at
`raw.githubusercontent.com/zotero-rag/zotero-rag/master/LICENSE` is MIT,
copyright 2024 Rahul Yedida. `crates/zqa-gui/LICENSE` is GPL-3.0. Note the
default branch is `master`; a `main` fetch 404s.

**Architecture.** Reads `zotero.sqlite` directly: `get_lib_path` resolves
`~/Zotero`, then two SQL queries join the item, field, and attachment tables and
concatenate authors, with PDFs at `storage/<library_key>/<filename>`. Storage is
a LanceDB table on local disk. Section-based chunking cuts at detected section
boundaries and splits oversized sections by a character budget, sub-chunks
inheriting the parent's page range. Incremental update compares the live library
against the table by `library_key + title` string equality.

Two documentation pages disagree about the schema. The LanceDB page describes
columns `library_key, title, file_path, pdf_text, embeddings` — one row per
document holding the whole extracted text, with no chunk id, page, or byte
range. The chunking page describes per-section chunks carrying `byte_range` and
`page_range` so the query stage can cite a location. Could not reconcile from
the documentation alone; resolving it needs a source read.

**Limits.** Open issue #335, filed 2026-08-29, the day of this survey: "When
Zotero is open, DB queries to it can fail since it is locked. We can get around
this by copying it to a different location and then querying it (probably)."
LaTeX environment parsing is acknowledged weak. Font-metric word-joining bugs in
extraction closed only between 2026-07-30 and 2026-08-07. Failed items during
`/process` are dropped silently with no coverage accounting. There is no
documented multi-process story. Changing embedding provider or dimension means
deleting the LanceDB directory and rebuilding.

**Performance.** `(claimed, README)`: about three hours locally, or forty
minutes using Voyage, for roughly 1 500 papers. No hardware, no methodology, no
independent measurement. No latency, memory, or recall numbers.

**Trends.** Created 2024-10-26, last push 2026-08-29, 20 stars, 3 forks, 76 open
against 73 closed issues, five tags from `v0.1.0a` to `v0.1.0`, not archived.
One human contributor with 1 110 contributions plus several bots; the repository
carries an `AI_POLICY.md`. Recent open issues cluster on the GUI.

**What we learn.** Issue #335, dated the day of this survey, is the sharpest
available evidence for the transport choice in DESIGN.md §2.4: a project that
reads `zotero.sqlite` directly is, today, broken by SQLite's lock while Zotero
runs, and its maintainer's proposed fix is to copy the database first. Their
embedder-change story is "delete the table and rebuild", which is a third
independent confirmation that this problem has no cheap answer in the field.
Their incremental check on `library_key + title` string equality cannot see a
replaced PDF under an unchanged title, which is the concrete argument for
separating version signals from content keys. Silent drop on failure is the same
mistake as the others: no coverage accounting, so the user cannot learn what is
missing.

### zotero-cli-cc

**Position.** A Python CLI and MCP server (`zot`, PyPI `zotero-cli-ai`) built
for agent ergonomics — a stable JSON envelope, typed exit codes, `--dry-run`,
idempotency keys, NDJSON streaming — over a local Zotero library. Observed
2026-08-29.

**Features.** Reads by direct SQLite; writes through the Web API; keyword search
across titles, abstracts, authors, tags, and full text; `search --ranked` for
BM25-ranked search scoped by collection; `ask`, which returns a citation-keyed
evidence pack of metadata and passages for the calling agent to synthesise from,
never calling a model itself; PDF extraction with a local cache, page-range
extraction, annotation extraction, table extraction, and reference parsing
through an external GROBID service; 39 MCP tools.

**Licence.** Dual. `raw.githubusercontent.com/Agents365-ai/zotero-cli-cc/main/LICENSE`
is the AGPL-3.0 text; a second file, `LICENSE-COMMERCIAL`, offers a paid licence
without the copyleft obligation. Contributions are taken under a Developer
Certificate of Origin, the mechanism that keeps dual licensing possible.

**Architecture.** Two designs in succession, and the second one is the finding.
Version 0.2.0 (2026-03-29) introduced named per-topic workspaces with a local
pure-Python BM25 index over each workspace's metadata and extracted text, plus
optional embeddings and hybrid fusion by reciprocal rank fusion. Version 0.13.0
(2026-08-17) removed the workspace group entirely. Retrieval is now index-free:
pull request #100 (2026-08-18) scores live with SQLite's own `bm25()` against
Zotero 10's contentless FTS5 table in `fulltext.sqlite` — the file the desktop
application builds and maintains — fused with a metadata-match score over title,
abstract, creators, tags, and notes by reciprocal rank fusion, with nothing to
build or keep in sync. Scoping moved from bespoke workspaces to Zotero's own
collections. On data directories predating Zotero 10 there is no
`fulltext.sqlite` and full-text scoring degrades to metadata-only with a
warning.

**Limits.** Could not look at a community backlog: the repository shows zero
open issues and returns "Issue creation is restricted in this repository", so
outside filers have no channel and discussions are off. What is visible: the
silent degradation to metadata-only on pre-Zotero-10 data directories; the
removal of the whole embedding and workspace line in v0.13 with no stated
reason; and an external GROBID dependency the user must run.

**Performance.** `(claimed)`: "millisecond response" for local SQLite reads and
"index-free, always fresh" for ranked search. No number, no methodology, no
corpus size. Could not look: no benchmark artifact surfaced in the README, docs
tree, or release notes.

**Trends.** Created 2026-03-20, latest commit 2026-08-25, 200 stars, 20 forks,
tags from v0.1.1 to v0.14.0 — seventeen or more releases in about five months,
with the workspace feature added at v0.2.0 and removed at v0.13.0. 244 of 248
commits from one account. Not archived.

**What we learn.** Two findings, one of them a platform fact this project should
carry into CONSTRAINTS.md rather than into this document. First, their pull
request #100 records that **Zotero 10 moved its full-text index out of
`zotero.sqlite` into a standalone contentless FTS5 database, `fulltext.sqlite`,
dropping the legacy `fulltextWords` and `fulltextItemWords` tables**, and that
their `core/fts.py` ports Zotero's own query-side `fulltext.js` semantics:
`normalizeForSearch`, CJK 2-gram routing to a `fulltextContentCJK` table, and
`getWordMatchClause` construction. That is the platform's own CJK handling,
observable today, and it is directly relevant to the 2-gram twin-table plan in
DESIGN.md §2.6. The claim is theirs and dated 2026-08-18; verifying it against
Zotero's source is a separate task, and it belongs in CONSTRAINTS.md if it
holds. Second, they built a maintained secondary BM25-and-embedding index, ran
it for five months, and deleted it in favour of scoring live against the
platform's own FTS5 index. That is one small project's judgement at an unstated
scale, so it is weak evidence. But it is evidence pointed at the maintenance
cost of any second index, and it independently reproduces two of our choices:
SQLite's own BM25 rather than hand-rolled scoring, and reciprocal rank fusion
across a metadata signal and a full-text signal. Nothing on scoping is
borrowable: their `--collection` reads as a predicate layered onto ranked
retrieval, with no evidence either way that it filters before truncation, which
is what REQUIREMENTS.md R5 requires. AGPL plus the commercial offer means any
code reuse — including their `fts.py` CJK port — needs a licence decision, or
reimplementation from the description.

### cli-anything-zotero

**Position.** A Python CLI and SDK giving agents command-line access to a local
Zotero 7/8/9 library. Version 1.0.0 (2026-05-03) removed MCP from the mainline
in favour of a CLI-first design; open issue #6 (2026-08-13) asks for it back.
Observed 2026-08-29.

**Features.** On the order of 110 subcommands by the documentation's own count,
against "70+" in the repository description — the two do not reconcile and
neither was audited. Search and browse, import by identifier with a PDF sourcing
cascade, export, PDF and annotation management, metadata operations, DOCX
citation integration, and arbitrary Zotero JavaScript execution. Semantic search
and AI analysis are optional and delegate to an external endpoint.

**Licence.** Apache-2.0, read at
`raw.githubusercontent.com/PiaoyangGuohai1/cli-anything-zotero/main/LICENSE` —
the full standard text, unmodified. The appendix names an "HKUDS CLI-Anything
Team" rather than the repository owner, likely a copied template.

**Architecture.** No index and no ledger; every command queries live. The
transport is the payload: three backends at once, and their documentation states
what each is for. Direct read-only SQLite reads serve item and collection
listing, get, and export, labelled "instant" and chosen to enrich listings with
DOI and attachment fields without extra round trips. The local Connector and
Local HTTP APIs, labelled about one second, serve item and attachment import,
citation rendering, and BibTeX export. A companion Zotero plugin, "CLI Bridge",
exposes a privileged JavaScript endpoint at `localhost:23119/cli-bridge/eval`,
labelled about half a second, and serves "everything else": attaching PDFs,
finding PDFs, full-text search, updates, tag operations, and sync triggers —
because those operations have no endpoint on the stock local API.

**Limits.** Five issues ever filed. Open #8 (2026-08-19): "Unable to install the
plugin 'CLI Bridge for Zotero'. It may not be compatible with Zotero 10." Open
#6 (MCP wrapper requested back) and #7 (no bulk operations). Closed #5 and #1.

**Performance.** `(claimed, project docs)`: SQLite reads "instant", Connector
and Local API about 1 s, JS Bridge about 0,5 s. No throughput, memory, or
large-library figures anywhere.

**Trends.** First public appearance on the Zotero forum 2026-04-08, earliest
release v0.9.0 on 2026-04-26, latest v1.2.1 on 2026-07-28, 131 stars, 13 forks,
68 commits, not archived. Release-driven bursts with multi-week gaps. Could not
look: the contributor graph needs client-side rendering and the GitHub REST API
was rate-limited unauthenticated, so the contributor count is unverified.

**What we learn.** It confirms the shape of the local API's gaps from the other
side. Their stated reason for shipping a privileged plugin is that PDF
attachment, full-text indexing, and dynamic writes have no endpoint on the stock
local API — the same family of gap CONSTRAINTS.md C2 records for `/deleted`.
Their answer was a plugin; ours is to route around each gap without one, and
their open issue #8 is the price of their answer, freshly paid: the bridge
plugin broke on the Zotero 10 upgrade. Direct SQLite reads and a companion
plugin both work, which sharpens rather than weakens the transport constraint —
each buys speed against a maintenance tax we decline. Nothing on the retrieval
side is borrowable: there is no chunking, no index, no ranking, and the roadmap
says explicitly that becoming a heavy semantic-search platform is not the goal.

---

## Standalone tools and one recommender

### zotero-rag (aaron-freedman)

**Position.** A "chat with your Zotero library" tool modelled on NotebookLM,
built by a historian for a dissertation, targeting the heterogeneous corpus we
also target: books, journal articles, archival manuscripts, congressional
hearings, government reports. Observed 2026-08-29.

**Features.** Natural-language question answering with numbered citations that
open the source PDF at the cited page; a web app, a CLI for search without
synthesis, and an MCP server. Adaptive chunking dispatched by document type:
congressional hearings split at speaker boundaries, books at chapter and section
boundaries, journal articles kept whole when short, archival sources chunked
with archive and collection metadata preserved. FlashRank cross-encoder
reranking after vector retrieval, chosen to avoid an API cost.

**Licence.** No LICENSE file. The root listing shows none, and
`raw.githubusercontent.com/…/main/LICENSE` returns 404. The README's "License"
section contains the single word "MIT", which is prose without a grant.

**Architecture.** Pinecone, a managed cloud vector database, with a free tier
cited as about 100 000 chunks; no local or embedded option and no lexical layer.
Text extraction results are cached locally as files, not as a pipeline ledger.
Zotero access is through the **Web API**, requiring a userID and a private key
with library access, so content passes through zotero.org and then Pinecone.
Incremental update runs from Zotero's library version number; switching
embedding provider forces a full Pinecone rebuild on a dimension mismatch.

**Limits.** Zero issues ever filed, so there is no defect record to read. From
the README: local Ollama indexing wants 8 GB or more and runs three to five
times slower than OpenAI on CPU; provider switches require deleting and
recreating the index; items with no PDF or EPUB get metadata-only indexing.
Nothing addresses very large single documents, notes, annotations, or
concurrency.

**Performance.** All `(claimed, README)`: about $0,10 per 1 000 documents to
index with OpenAI embeddings; about $0,01 per chat with Claude synthesis and
about $0,001 with GPT-4o-mini; about 1 000 items in fifteen to thirty minutes
with OpenAI embeddings; about 100 000 chunks on the Pinecone free tier. No
independent measurement found.

**Trends.** Five commits: 2026-02-10 (initial release plus two README edits),
2026-02-16, and 2026-03-27. 2 stars, 2 forks, zero issues, no releases, no
activity in five months, no archive banner observed.

**What we learn.** One idea, independently arrived at. Adaptive chunking
dispatched by document type — speaker boundaries for hearings, chapters for
books, whole when short — is the same instinct as the entry ruling, reached by
someone whose corpus is books and archives rather than papers. It is corroboration
that per-genre boundary rules matter to a real historian's library, and it
supplies no quantitative policy to port, only qualitative rules. Their local
cross-encoder rerank after vector retrieval is worth keeping in mind as a cheap
mitigation should int8 recall prove weak under the X1 gate (DESIGN.md §3).
Everything else argues the other way: cloud vector store, Web API transport, and
an embedder change answered by deleting the index.

### zotero-rag-assistant

**Position.** A single-author local pipeline over a personal library of about
600 papers, framed by its own status document as a learning project: a FastAPI
service plus CLI scripts orbiting Zotero. Observed 2026-08-29.

**Features.** PyMuPDF ingestion; 512-token sliding-window chunking with 50-token
overlap using `cl100k_base`; a noise filter dropping about 45 % of chunks
(reference lists, affiliations, funding); local `all-mpnet-base-v2` embeddings
at 768 dimensions on CPU; a FAISS `IndexFlatIP` store with L2-normalised vectors;
optional query decomposition, which the author measured as worse than baseline
and disabled; generation through Claude or Ollama; a 57-test suite and CI added
2026-08-13.

**Licence.** No LICENSE file. Confirmed twice: `raw.githubusercontent.com/…/main/LICENSE`
returns 404, and the GitHub community-standards page shows "License — missing".
The README does not mention one.

**Architecture.** Reads Zotero's `zotero.sqlite` read-only through a five-table
join, scoped to one named collection and its children, filtered to PDF
attachments under `storage:`. Newness is presence on disk: the script builds a
destination path and skips if the file exists. No manifest, no content hash, no
`dateModified` comparison, no version counter. Deletion is not handled at all —
the script never queries `deletedItems`, so a removed item's copied PDF and its
vectors persist. The trigger is an n8n schedule firing once a day at 18:00, not
a filesystem watcher.

**Limits.** The issue tracker is empty and restricted, so there is no external
record. The author's own status document lists: unused dependencies shipped;
a hardcoded batch size duplicated in two places; query decomposition disabled
because it hurt retrieval; no reranking; HTML snapshots silently skipped; and no
guard against a re-run duplicating vectors.

**Performance.** All `(claimed, README)`: about 600 papers, about 30 000
vectors, $0,01–0,02 per question with Claude, $0 for embeddings, 57 passing
tests. No latency, memory, or accuracy figures.

**Trends.** First commit 2026-03-25, latest 2026-08-13, 32 commits, single
committer, 0 stars, 0 forks, no releases, tracker restricted, not archived.

**What we learn.** A clean negative exemplar on two of our lifecycle
requirements. Presence-on-disk as the newness test cannot see a replaced file
and duplicates vectors on any re-run, which is the failure the content-hash key
of DESIGN.md §2.1 exists to prevent. Deletion handled nowhere at all is the
counterexample that makes REQUIREMENTS.md R15 worth stating as a requirement
rather than assuming. Also a naming caution: their README says the tool "watches
for new PDFs" and it polls once a day, a distinction worth keeping honest in our
own materials about update latency.

### zotero-semantic-search

**Position.** A small Flask web application doing semantic search and
unsupervised topic discovery over a Zotero library's bibliographic metadata —
titles, abstracts, authors, DOI — and nothing else. Observed 2026-08-29.

**Features.** Semantic search over title and abstract embeddings;
topic modelling by HDBSCAN over the embedding space with UMAP reduction and
TF-IDF keyword labels; progress tracking during embedding; a disk cache to avoid
recomputation; an interactive results table.

**Licence.** GPL-3.0, read from the LICENSE header at
`raw.githubusercontent.com/a-meneghini/zotero-semantic-search/main/LICENSE`.

**Architecture.** No database. Embeddings and clustering results cache to disk
as files; retrieval is a linear scan over numpy arrays. There is no Zotero
integration of any kind: the user exports the library to `zotero_data.csv` by
hand and drops it in the project directory. The model is
`sentence-transformers/all-MiniLM-L6-v2` by default, English-centric,
user-substitutable.

**Limits.** Zero issues ever filed, so there is nothing external to read. The
structural limits are the design: manual CSV ingestion, no live sync, no full
text, no stated multilingual support, no stated scale ceiling.

**Performance.** No numbers of any kind. Nothing to label.

**Trends.** Six commits by one author between 2024-12-09 and 2025-01-22, then
nothing for nineteen months. 4 stars, 1 fork, no issues, no releases, no archive
banner observed.

**What we learn.** One positive data point for the record ruling, from the
extreme. This tool drops full text entirely and still delivers usable semantic
search and topic clusters from title and abstract alone, which supports the
premise that the bibliographic record carries real semantic signal and deserves
to be indexed first (REQUIREMENTS.md ruling 2, DESIGN.md §2.3 phase A). Nothing
else transfers: manual CSV export is the "no incremental, no live sync" failure
R1 rules out, and topic modelling is a corpus-level feature orthogonal to
query-time retrieval.

### zotero-arxiv-daily

**Position.** A scheduled recommender, not a search tool: a daily email matching
new arXiv, bioRxiv, medRxiv, and chemRxiv preprints against the interests
expressed by a Zotero library. It appears here because it embeds a whole Zotero
library, which the rest of its category does not. Observed 2026-08-29.

**Features.** Embeds each library item's abstract, scores each new preprint by
a recency-weighted average cosine similarity against every library item, and
mails the ranked result. Default embedding model
`jinaai/jina-embeddings-v5-text-nano`, run locally through
`sentence-transformers`, with an API embedding service as an alternative.
`pymupdf4llm` and `pymupdf-layout` supply text for summary generation.

**Licence.** AGPL-3.0, read from the raw LICENSE file.

**Architecture.** No persistent index. Every run — a daily GitHub Actions cron —
re-embeds the whole Zotero library and the day's new preprints from scratch, so
cost scales linearly with library size on every run rather than amortising into
a stored vector store.

**Limits.** The design is the limit: no stored vectors, so nothing amortises and
nothing can be queried between runs.

**Performance.** No numbers published.

**Trends.** 5 900 stars and 5 200 forks — an unusual ratio, explained by users
forking to run their own scheduled instance rather than to contribute. 221
commits, latest 2026-08-25. Very active, not archived.

**What we learn.** It is the naive baseline stated cleanly: embed everything,
every time, keep nothing. That is the design a durable ledger replaces, and its
5 900 stars show the baseline is good enough for a recommender that runs
overnight and answers nobody in real time. The distinction is worth keeping
straight — the ledger of DESIGN.md §2.1 buys interactive query latency and
bounded recompute, neither of which a nightly cron needs. Its embedding-model
choice is a second data point on what people run successfully against real
Zotero libraries.

---

## Adjacent work

### Zotero core, "Best Match" (pull request #6012)

**Position.** Not a plugin: Zotero core building semantic search into the
desktop application, surfaced through the existing quick-search and
advanced-search interface as a "Best Match" condition with a relevance-bar
column. Observed 2026-08-29.

**Features.** Hybrid ranking, semantic fused with lexical. The strategy depends
on query length: over two terms leans semantic with the lexical side narrowed to
title and abstract, because, in a commit message, "lexical matches from a longer
natural language query add a good amount of noise"; two terms or fewer run both
semantic and full lexical matching. Title-and-abstract embeddings for regular
items, chunk embeddings for attachment text. An optional `bge-reranker-base`
second pass. Mean-vector subtraction to suppress a shared direction bias. Items
with almost no extractable text are excluded.

**Licence.** AGPL-3.0 for `zotero/zotero`, read at
`raw.githubusercontent.com/zotero/zotero/main/COPYING`. The companion
`zotero/structured-document-text` repository has **no LICENSE, LICENSE.md,
LICENSE.txt, or COPYING file** in its root listing, and no description; treat it
as all rights reserved until one appears.

**Architecture.** A separate `embeddings.sqlite`, kept out of sync and lazily
attached to the main database. Chunk location is stored as block start and end
offsets rather than chunk text, so content re-derives from the source pack
instead of being duplicated. `sqlite-vec` accelerates similarity search.
Embedding models are `bge-small-en-v1.5` and `multilingual-e5-small`, run
in-process through Firefox's ML runtime. Indexing runs as background batches off
the main thread with a stopping state that finishes the current batch. Sync of
embeddings is explicitly not implemented. The SDT pack itself is a compact
binary container: header, index, compressed metadata and catalogue as JSON, and
content split into compressed chunks of top-level blocks with a block offset
table, so one block extracts without loading the whole pack.

**Limits.** No sync. A contributor asked on 2026-08-21 whether requiring the SDT
extractor to run for every attachment is a problem, and the question is
unresolved. Passages below a calibrated per-model score are excluded with no
stated fallback. **Nothing in the pull request reaches Zotero's local HTTP
API**: the changed files are internal search, embeddings, lexical, full-text,
and UI modules, so platform semantic results are not observable to an external
tool today.

**Performance.** `(claimed, a pull-request comment, author and date not
resolved)`: "on a large 5K library it's fast". `(claimed, unattributed within
the pull request)`: complete searches can take 10 s or more on large libraries.
No dated, attributable measurement was readable.

**Trends.** Still a draft, 67 commits across several contributors, last activity
observed 2026-08-26 (a force-push). No merge date, no release channel, no
roadmap statement located.

**What we learn, and one correction to make.** The reusable idea is score
calibration: `Zotero.Embeddings.Calibration` builds a query-by-passage score
matrix from a labelled corpus of relevant and irrelevant pairs and sets a
per-model minimum relevance threshold, rejecting models outright below it. Our
design defers calibration to ticket 0031 with a stated pair-generation protocol;
the platform's version is more complete, and the description above is what 0031
builds from — reading it at source was instructed here once and is withdrawn
(ruling, `spec/DECISIONS.md` 2026-08-31; see the closing section). The separate `embeddings.sqlite` kept out of sync is a structural
parallel to our sidecar, reached differently. And the confirmation that nothing
reaches the local API answers a question our design carried: there is no
platform surface to reconcile with today, which is what CONSTRAINTS.md C2
already states.

**A gap this survey could not close.** Four claims that CONSTRAINTS.md C2
attributes to #6012 could not be re-verified from the publicly readable pull
request text: the token chunk geometry, the never-crosses-a-section rule, the
smallest-first attachment ordering, and the CJK 2-gram geometry. The readable material says only that the chunker tries to "chunk as
close to outline as possible". This is a "could not look", not a refutation:
CONSTRAINTS.md records these as scout findings from a direct code read, which is
a stronger instrument than a summarised page fetch, and CONSTRAINTS.md remains
the owning statement. Re-reading `Zotero.Utilities.Internal.Chunking` at source
would settle it. One warning from the same pass: a figure pair attributed to
this project's own author and August 2026 surfaced inside a #6012 fetch. It is
our own benchmark data leaking back through a search index, and it must never be
cited as a Zotero core measurement.

### Better Notes

**Position.** The ecosystem's largest plugin by installs, and not a search tool:
note editing and note management, with no retrieval or indexing engine at all.
It is here for two narrow reasons — it is the reference example of a mature,
long-lived Zotero plugin, and it is what makes notes first-class, and our corpus
includes notes. Observed 2026-08-29.

**Features, on the three points that matter.** Notes are ordinary Zotero notes,
rich HTML edited through a ProseMirror editor and persisted through Zotero's own
item API. Note-to-note and note-to-item linking is first-class, with inbound and
outbound links in a context pane and a relation-graph window. Two-way sync
between Zotero notes and external Markdown files runs on a remark and rehype
pipeline. There is no search or index feature: outline and link previews are
navigation over Zotero's own content. No embeddings, no vectors, no model calls
in this repository; the `dexie` package appears only as a transitive dependency,
never imported.

**Licence.** AGPL-3.0, read at
`raw.githubusercontent.com/windingwind/zotero-better-notes/master/LICENSE` and
confirmed against the GitHub API.

**Architecture, on schema and migration.** The plugin owns no database inside
the Zotero profile. Note content lives entirely in Zotero's own storage, reached
through Zotero's item API, and searches of the repository for "migrate",
"dataVersion", and "sqlite" return nothing — it delegates upgrades entirely to
Zotero core rather than versioning any state of its own.

**Limits.** One open issue: a Markdown import above roughly 32 000 characters
silently drops the beginning of the note and keeps the tail. 947 closed issues,
9 open pull requests.

**Performance.** No numbers published in the README or release notes.

**Trends.** Created 2022-04-27, last push 2026-08-24, latest release v3.3.3 the
same day, 8 149 stars, 269 forks, 1 353 commits, 17 contributors, not archived.
Releases weekly to fortnightly through 2025 and 2026. One tooling note from the
surveying pass: a page-summarising fetch of the releases page returned fabricated
2024 dates for 2026 releases, and every date here was taken from the raw API
instead.

**What we learn.** The architectural contrast is the point. A widely-installed,
actively maintained plugin can own no schema and no migration machinery at all
by delegating to Zotero's native storage — and it can do that precisely because
it holds nothing derived. Our design holds a great deal that is derived, which
is why REQUIREMENTS.md R23 has to carry upgrade and downgrade explicitly. That
nothing in the ecosystem, including this plugin, indexes note and annotation
content is confirmation that REQUIREMENTS.md R16 covers real ground. Their
inbound and outbound note-link graph is a possible future ranking signal our
ledger does not model; noted, not actionable. Their open truncation issue is a
reminder to test our own note ingestion against a note of comparable size.

---

## Surveyed and set aside

These seventeen build no index of their own, or build one where nobody can read
it. Each row states what was read and what it turned out to be. Nothing here is
prior art for retrieval, and none of it was investigated further. The last six
rows date from the 2026-09-02 pass.

| Project | What it is | Evidence it builds no index |
|---|---|---|
| `kujenga/zotero-mcp` | Minimal MCP relay, three tools, MIT, 160 stars, last release 2026-08-07 | Dependencies are `mcp`, `pydantic`, `python-dotenv`, `pyzotero` only; no numpy, no embedding or vector library. Every search re-queries Zotero live |
| `Xevos117/mcp-zotero` | MCP server, MIT, 34 stars, last push 2026-05-18 | `get_item_fulltext` reads "Zotero's fulltext index"; PDF import triggers Zotero's own indexing. The "fulltext indexing" claim means it asks Zotero to index, not that it indexes |
| `danielostrow/zotero-mcp-server` | MCP server, MIT, 7 stars | Created and last pushed the same day, 2026-01-07; search is API pass-through, no embeddings or FTS in the README |
| `TomasSchweizer/Zotero-MCP-Server` | MCP server for the 5ire client, Apache-2.0, 2 stars, last push 2026-08-09 | Calls `search_zotero_library()` through Pyzotero, i.e. Zotero's native search. GitHub's licence detector reports null despite the file being present |
| `RaulSimpetru/zotero-library-mcp` | MCP server for adding papers by identifier, 2 stars, last push 2026-08-09 | Search calls the Zotero API with a client-side fuzzy fallback over the results; no index. README claims MIT, the licence endpoint 404s and the root listing has no LICENSE |
| `introfini/mcp-server-zotero-dev` | MCP bridge over the Remote Debugging Protocol for plugin *development*, MIT, 38 stars, last push 2026-08-20 | README contains no search, index, or retrieval language; SQLite access is stated as read-only for debugging. Out of scope by design |
| MCP for Zotero (hosted) | Closed-source hosted service at `mcpforzotero.alejandroarnaud.dev` | No public repository found — that absence is the finding. Claims search "by content from PDFs" with no method stated; unverifiable. Relays the user's Zotero API key to a third party |
| `l0o0/MagicZotero` | Paid translation and summarisation plugin, Chinese README, 32 stars, last push 2026-08-28 | No embeddings, vector, FTS, or BM25 anywhere in the README. MinerU and pdf2zh are translation preprocessors. No LICENSE file (raw 404) |
| `steven-jianhao-li/zotero-AI-Butler` | Auto-reads PDFs and writes Zotero notes, AGPL-3.0, 1 700 stars, last push 2026-08-25 | Content goes whole to the model as base64 or extracted text behind a producer-consumer queue; "document structure extraction" describes the note it writes, not the input it reads |
| `kazgu/zotero-chatgpt` | ChatGPT API wrapper in Zotero, AGPL-3.0, 301 stars | Direct pass-through with PDF text or metadata as context; no index. `main` shows commits dated 2025-11-20, roughly nine months quiet; `master` shows no history |
| `syt2/Zotero-TLDR` | Fetches Semantic Scholar TLDR summaries, AGPL-3.0, 62 stars | Pure API consumer, no model call of its own. **Archived** — banner seen: "This repository was archived by the owner on Dec 25, 2025. It is now read-only." |
| `Visterainer/aidea-zotero` (AIdea) | Sidebar chat with OAuth login, OpenAI-compatible and local models, AGPL-3.0 read from file, 113 stars, last push 2026-08-30 | Dependencies are `katex` and `zotero-plugin-toolkit` only; the README (1 600 words) contains no search, index, embedding, or retrieval language. Chat over the open item |
| AskYourPDF Zotero plugin | Hosted document chat at `askyourpdf.com`, closed, freemium | The plugin uploads the document to the vendor ("When you upload a document to our platform"); retrieval, if any, is theirs and unreadable. No library index |
| `scitedotai/scite-zotero-plugin` | Citation-statement counts (supporting, contrasting, mentioning) from scite's hosted service, 864 stars, last push 2026-02-02 | No model call and no index: a column of counts fetched per item. No LICENSE file (API reports null). Already noted as an integration under `54yyyu/zotero-mcp` |
| Zotero AI Bar (`zotero.fukeke.com`) | Sidebar summarise, translate, Q&A, per Citation Styler | Could not look: the site is drawn by client-side script and the fetch fails on its certificate chain; no repository link, no licence, no search language found on the page |
| `Addy-ad/wordbot` | Word add-in with a Flask backend that formats Markdown, chats, and cites from Zotero, CC BY-NC 4.0 read from file, 7 stars, last push 2026-08-19 | Named in the Reddit thread. Its library retrieval is delegated to ZotSeek, already surveyed; `requirements.txt` lists `beautifulsoup4`, `Flask`, `openai`, `requests`, `waitress`, no embedding or vector library |
| Agent Bayes (`agentbayes.com`) | Hosted research workspace over a mindmap with a Zotero sync plugin, closed | Named in the Reddit thread. Papers are "indexed and semantically searchable" on the vendor's servers; no public repository found by forge search. Same class as "MCP for Zotero (hosted)" above |

---

## What the field teaches

Twenty-eight projects, one platform pull request, and about eighteen months of
public history produce eight findings. Each is stated with the evidence that
carries it. Where a finding bears on one of our own decisions, the owning
document is named and its content is not repeated here.

### Everyone caps the document, and the caps are the tell

The field's defaults, gathered: ZotPilot skips documents over 40 pages;
`54yyyu/zotero-mcp` extracts at most 50 pages and returns at most 10; ZotSeek
truncates at 100 chunks per paper and its maintainer told the forum on
2025-12-30 that books "lack the typical paper structure … and are often too long
to index effectively"; Beaver runs a 125 000-page account budget and drops any
attachment yielding under 150 characters; upstream zoteus truncates full text at
40 000 characters. Not one of these is presented as a limitation. They are
presented as configuration.

The caps agree because the field's users agree: a few hundred short papers. That
makes REQUIREMENTS.md R8 the position with no company in it, and it explains why
so little of the field's machinery survives contact with our corpus. It also
means no competitor's default protects a reader from the failure R8 exists to
prevent — a document silently half-indexed, with nothing saying so.

### Nobody has an entry, and the defect class shows up one level up

No project in the survey treats a section or entry as the unit of answer. Most
treat the item; a few treat the attachment; several treat the raw chunk. The
consequence is visible in the trackers of the field's most-installed tools. Open
issue #494 on `54yyyu/zotero-mcp` (2026-08-25) records that a priority function
picks one attachment per item and the rest are silently invisible to the index.
That is our defect class at a coarser granularity: they lose a second PDF, we
would lose 1 849 dictionary entries, and neither loss announces itself.

ZotPilot goes furthest and then inverts the rule: its chunker windows raw
character offsets first and attaches a section label afterwards, so a chunk can
straddle a boundary. The boundary ruling in REQUIREMENTS.md is therefore not a
refinement of a solved problem. It is the problem, unattempted.

### Structural segmentation of an unstructured document is unsolved, by everyone

Four projects attempt heading detection, and each stops at the same place.
ZotPilot matches heading text against a fixed vocabulary and labels anything
else `unknown` with a constant confidence. deep-zotero classifies sections by
the same fixed vocabulary. `zotero-gpt` merges lines geometrically by font size,
spacing, and indentation, stops at the references, and its v1.4.0 note about
merging short paragraphs records the tuning cost. ZotSeek detects section
headers by pattern and its maintainer says on the record that the result does
not suit books.

Not one publishes a fallback for a document with no detectable headings. The
segmenter of DESIGN.md §2.2 is called the design's biggest unmeasured bet in its
own text; the field confirms the bet is on ground nobody has crossed. The one
piece of real engineering to learn from is deep-zotero's figure detection —
multi-fallback, geometric, with caption-count reconciliation — which solves a
different problem and demonstrates that the shape works.

### Direct SQLite reads keep producing lock bugs, on dated evidence

Six projects read `zotero.sqlite` directly. Three have the failure on the
record. `zotero-rag` (Rust) issue #335, opened **2026-08-29**, the day of this
survey: "When Zotero is open, DB queries to it can fail since it is locked",
with the maintainer's own fix being to copy the file first. lit-lake issue #16:
"database is locked" during sync, leaving chunks permanently pending and the
sync failing across restarts. `zotero-cli-cc` pull request #99, merged
2026-08-18, "WAL-safe reads under Zotero 10's exclusive database lock". A
fourth, `cli-anything-zotero`, pays a different instalment of the same tax: its
privileged bridge plugin broke on Zotero 10 (open issue #8, 2026-08-19).

The local-HTTP-API transport of DESIGN.md §2.4 is slower per read and immune to
all of this. That trade now has four dated instances behind it rather than a
prediction.

### One process, one host: two projects froze the application they lived in

`cookjohn/zotero-mcp` issue #95 (2026-08-05) is the field's most instructive
failure. Embedding ran on Zotero's main thread against a 7,4 GB vector database
in default rollback-journal mode, with a 7,6 GB corrupt remnant beside it and an
in-memory flag as the only guard against duplicate work. Zotero stopped
responding with 0 ms of CPU over three seconds: blocked on a lock, not
computing. lit-lake issue #35 asks for CPU throttling because embedding takes
every core. ZotPilot issue #50 has the CLI and the MCP server refusing each
other's index on Windows, root cause unknown.

Three of our design choices are answered by that one issue, and DESIGN.md owns
each: WAL from the first table (§2.2), the background worker in its own process
at low priority (§2.5), and the claim held in a durable lease row rather than a
process variable (§2.5). No project in the survey publishes a memory or CPU
budget of any kind. The budgets of CONSTRAINTS.md C3 are, as far as this survey
found, the only ones in the field.

### The linear vector scan has now been measured, and it fails below our design point

Upstream zoteus issue #30, filed by a third party on 2026-08-28, reports
**90–105 s per semantic query on 255 703 passages** across 10 184 items at 3 072
dimensions, against about 13 s for a ChromaDB-backed alternative, with memory
flat near 110 MB — CPU-bound in a JavaScript decode-and-dot-product loop. That is
less than half the passage count DESIGN.md §2.9 budgets for, at a latency
thirty times the R6 ceiling.

The X1 int8 experiment of DESIGN.md §3 was written as an optimisation with a
recall gate. This measurement makes it the load-bearing experiment of the
design, and it arrived from outside the project, on a real library, six days
before this survey. ZotSeek runs the same linear scan and reports sub-50 ms warm
queries `(claimed)` at a corpus one to two orders of magnitude smaller, which is
consistent rather than contradictory: the scan works until it does not.

### Reciprocal rank fusion is the field's settled answer; honest status is not

Five projects independently fuse a lexical signal with a semantic one by
reciprocal rank fusion: ZotSeek at the constant DESIGN.md §2.6 sets, with
best-chunk collapse before ranking, `zotero-agent`, `zotero-cli-cc` (metadata against FTS5 `bm25()`),
ZotSeek-Online, and Zotero core in a query-length-dependent variant. Convergence
that broad is corroboration for DESIGN.md §2.6 rather than novelty, and it is
worth citing when the choice is defended externally.

Coverage honesty has no such convergence. zotmcp's own README concedes that
scores are uncalibrated across queries and that the response reports neither the
corpus total, nor the count above threshold, nor the count returned, so a caller
cannot distinguish a small library from an aggressive filter. Nodus issue #577
records a synthesis silently replaced by a raw evidence dump, rendered
identically to a real answer. seerai issue #12 records retrieval failing and raw
context being injected instead, with the answer produced anyway. Aria, two years
and 1 700 stars in, still fields "does it really read documents or just
metadata?" as an open question.

Four projects, four different ways of answering confidently from less than they
implied. That is the single most common defect in the field, and REQUIREMENTS.md
R4, R17, and R18 are the direct response.

### Incremental update: four answers, all weaker than a ledger

The field's staleness mechanisms, ranked by strength. Zotero's own version
counter alone (`cboulanger/zotero-rag`, `aaron-freedman/zotero-rag`, zotmcp),
which cannot distinguish a re-chunk from no change. A content hash of the file
(ZotPilot; deep-zotero, but only of the first 64 KiB, which cannot see an edit
past it). Field-level diffing of title, author, and year (lit-lake). Presence of
a copied file on disk (`zotero-rag-assistant`), which cannot see a replaced PDF
and duplicates vectors on every re-run. Set difference on `library_key + title`
(`zotero-rag`, Rust), with the same blindness.

Three consequences are on the record. `54yyyu/zotero-mcp` v0.7.0 shared one
global sync watermark across libraries, so syncing one library read another's
documents as deleted and purged them — the failure the per-library scoping of
DESIGN.md §2.2 makes unwritable. `cookjohn/zotero-mcp` issue #100 leaves items
indexed before their attachment arrived "abstract-only forever", a ledger that
never re-arms. And ZotPilot issue #38 has orphan cleanup deleting every
group-library document because reconciliation compares against the personal
library only.

Deletion is worse. `zotero-rag-assistant` never queries `deletedItems` at all,
so removed items' vectors persist indefinitely. `zotero-rag` (Rust) drops failed
items silently with no accounting. Nobody in the survey propagates a deletion
through every derived store, which is what REQUIREMENTS.md R15 asks for.

The one durable job ledger in the field is lit-lake's: `jobs` with a UNIQUE
dedupe key and a lease, `job_attempts` with one row per try carrying error class
and metrics, `worker_runs` with heartbeats. Separating the attempt audit trail
from the job's own retry counter is a normalisation worth adopting — it is
exactly the raw material the work counters of DESIGN.md §2.8 consume, and it
keeps that history out of the live row.

The 2026-09-02 pass found a second one, in BibGenie's shipped bundle: a
content hash per row, the model triple on every row and on the per-library
state row, a failures table with exponential retry capped at five attempts,
and a full library diff whenever the state row's counts disagree with the
library or two days have passed. It is the only mechanism in the survey that
reconciles on a count mismatch rather than trusting its own watermark, which
is the cheapest possible check against the "abstract-only forever" failure
above. It guards an index of abstracts, and it is closed source, so the idea
travels and the code does not.

### What the field answers, and what it leaves open

Answered, and we should stop treating these as unknowns:

- **Ranking shape.** Reciprocal rank fusion at the constant DESIGN.md §2.6
  sets, with per-document collapse by best chunk before ranks are assigned, is
  what five independent implementations converged on.
- **Serving through an embedder change.** ZotSeek keys chunk rows by
  `(item, chunk_index, model_id)` and tracks per-model coverage in a separate
  table, so a model switch drops nothing and only uncovered items queue. That is
  a working shape for the serve-stale ruling. `cboulanger/zotero-rag` adds a
  cheap pre-flight: require cosine similarity at or above 0,999 on probe texts
  before calling two models vector-compatible.
- **Whether a linear vector scan suffices.** It does not, above roughly a
  quarter of a million passages. Measured, by a third party, on our own vehicle.

Open, and nobody has an answer to borrow:

- **Segmenting a structureless 15 000-page PDF into entries.** Four attempts, four
  fallbacks to a label rather than a strategy.
- **The FTS5 constrained-MATCH threshold.** Almost nobody in the field uses
  FTS5: the exceptions are Zotero core, upstream zoteus, and `zotero-cli-cc`,
  and none of them constrains MATCH to a row set. There is no external data
  point, so experiment X4 has to produce it.
- **Whether local re-extraction re-stamps fulltext version 0.** No project
  engages with the mixed local sequence at all; several are broken by it without
  saying so.
- **Two processes over one index.** Every project is single-writer by
  construction or by accident. ZotPilot's open issue #50 is the only attempt,
  and it is unresolved.

One platform fact arrived from an unexpected direction and belongs in
CONSTRAINTS.md, not here, once verified at source. `zotero-cli-cc` pull request
#100 (2026-08-18) states that **Zotero 10 moved its full-text index out of
`zotero.sqlite` into a standalone contentless FTS5 database, `fulltext.sqlite`,
dropping the legacy `fulltextWords` and `fulltextItemWords` tables**, and that
their `core/fts.py` ports Zotero's query-side `fulltext.js` semantics including
CJK 2-gram routing to a `fulltextContentCJK` table. If that holds, the platform
already ships the 2-gram geometry DESIGN.md §2.6 schedules, and it is observable
today rather than after #6012 merges.

---

## What is license-compatible to borrow

Reading the LICENSE file rather than the badge changed the answer for seven
projects, and it rules out most of what is worth having.

**Permissively licensed, and safe to borrow from with attribution.** MIT:
`54yyyu/zotero-mcp`, `kujenga/zotero-mcp`, `cookjohn/zotero-mcp`, deep-zotero,
ZotPilot, seerai, `zotero-agent`, the tspspi fork, upstream zoteus itself, and
the core crates of `zotero-rag` (Rust). Apache-2.0: `cli-anything-zotero`,
`TomasSchweizer/Zotero-MCP-Server`. Of these, three hold something we would
actually want: deep-zotero's multi-fallback figure and caption geometry,
ZotPilot's section classifier and its reference-detection pass, and ZotSeek's
per-model chunk keying — except that the last one is not on this list.

**Copyleft, and out of reach for this project's purposes.** AGPL-3.0: Beaver,
Nodus, PapersGPT, `zotero-gpt`, Aria, llm-for-zotero, `zotero-arxiv-daily`,
Better Notes, Zotero core, `text70/zotero_ai`, and `zotero-cli-cc` (whose
commercial option is a separate negotiation rather than a licence we hold). GPL-3.0:
`zotero-semantic-search`, and the GUI crate of `zotero-rag`. The network clause
in AGPL reaches a server that answers queries, which is what zoteus is. Read
these for ideas; do not copy lines.

**No licence at all, therefore all rights reserved.** ZotSeek, ZotSeek-Online,
`cboulanger/zotero-rag`, lit-lake, zotmcp, `zotero-rag-assistant`,
`aaron-freedman/zotero-rag`, and BibGenie, which publishes no source at all and
whose design above was read from its shipped bundle. Two of these carry a
licence claim in prose that no file backs: ZotSeek declares MIT in `package.json`, and
`aaron-freedman/zotero-rag`'s README says "MIT" under a License heading with no
LICENSE file beneath it. A claim in a README is not a grant.

That last list is the uncomfortable one, because it holds the two most
transferable designs in the survey. ZotSeek's `(item, chunk_index, model_id)`
keying with a per-model coverage table is the clearest working answer to serving
through an embedder change; lit-lake's three-table job ledger is the closest
thing in the field to what DESIGN.md §2.1 specifies. Both can be read,
described, and reimplemented from the description — which is what this document
has just done — and neither can be copied. The same applies to
`cboulanger/zotero-rag`'s 0,999 cosine-similarity compatibility probe, a
five-line idea that needs no code at all.

Where an idea is worth having from an unlicensed or copyleft project, the route
is the same one this survey used: read the design, write the paragraph, build it
independently. This document once excepted Zotero core's calibration procedure,
instructing ticket 0031 to read `Zotero.Embeddings.Calibration` at source on the
ground that an algorithm with parameters cannot travel as a description. **That
instruction is withdrawn** (ruling, `spec/DECISIONS.md` 2026-08-31): the
paragraph describing it above carries the whole algorithm, so nothing is
withheld, and what the source would add is their parameter values — the one part
that must not be reused, since a threshold calibrated on their corpus and their
task is wrong for ours by construction. Ticket 0031 builds from that description
and derives its own thresholds. The route has no exception.
