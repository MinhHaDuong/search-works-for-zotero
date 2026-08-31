# Search Works for Zotero

*An independent open workshop for advancing semantic retrieval in Zotero.*

Search should work across a whole scholarly library: records, notes,
annotations, articles, books, and very large reference works. It should find
meaning rather than merely matching strings, while remaining inspectable,
resource-bounded, current, and honest about what has and has not been indexed.

This repository is a public statement of that direction and a place to do the
work. It develops requirements, constraints, designs, executable experiments,
acceptance tests, and upstream contributions. It is not the home of a single
product and it does not assume that one implementation should win.

## The proposition

The lasting result should be a retrieval contract that the Zotero ecosystem can
implement in more than one way. Success may mean a change in Zotero itself, a
change in an independent server or plugin, a reusable test harness, or evidence
that causes a design to be abandoned. Shipping code here is one means, not the
definition of success.

Three work surfaces therefore have equal standing:

1. **Zotero itself.** [zotero/zotero#6012](https://github.com/zotero/zotero/pull/6012)
   and its successors are first-class design and influence points. Their result
   locations, saved-search representation, lifecycle, local-API surface, and
   retrieval semantics may decide which machinery outside Zotero remains
   necessary.
2. **Independent implementations.** [zoteus](https://github.com/oscardvs/zoteus)
   is the current working vehicle and upstream contribution target, not the
   project identity. Other servers, plugins, and future adapters are legitimate
   implementations of the same contract.
3. **The implementation-neutral workshop.** Requirements, measurements,
   fixtures, gates, and decision records live here so that claims can survive a
   change of implementation.

## What is already decided

The current design begins from three ratified rulings:

- **The unit of answer is the entry or section**, not necessarily the Zotero
  item. A dictionary is one item and many legitimate answers.
- **The bibliographic record is the semantic core.** Title, abstract, keywords,
  notes, annotations, and body text retain their identities rather than being
  flattened into an undifferentiated string.
- **Chunking respects document structure and carries context.** A chunk does not
  cross a detectable entry boundary; its heading path and item title travel
  with it.

Around those rulings, the system must converge without manual rebuilds, expose
honest coverage, avoid recomputing unchanged content, filter before truncating
answers, survive very large documents, and operate within explicit CPU and
memory budgets. These are testable requirements, not branding claims.

## How the workshop is organised

The specification chain lives in [`spec/`](spec/); what changes week to week
stays at the top level.

| Document or directory | Role |
|---|---|
| [`spec/REQUIREMENTS.md`](spec/REQUIREMENTS.md) | Testable promises made to users |
| [`spec/CONSTRAINTS.md`](spec/CONSTRAINTS.md) | Facts imposed by Zotero, upstream projects, and the operating environment |
| [`spec/DESIGN.md`](spec/DESIGN.md) | Current design and experiment decision rules |
| [`spec/TERMINOLOGY.md`](spec/TERMINOLOGY.md) | Glossary of the chain's vocabulary, marked ours or inherited |
| [`spec/FIELD-REVIEW.md`](spec/FIELD-REVIEW.md) | Survey of prior art: what others have built, and what is borrowable |
| [`spec/DECISIONS.md`](spec/DECISIONS.md) | Append-only record of ratified choices and later vetoes |
| [`GOVERNANCE.md`](GOVERNANCE.md) | How this repository conducts itself upstream: the bounds on our own conduct |
| [`SECURITY.md`](SECURITY.md) | What this system holds, where it can leak, and the design's current answer for each |
| [`SYNC.md`](SYNC.md) | Live account of Zotero and zoteus upstream movement |
| [`STATE.md`](STATE.md) | Operational handoff and measurement record |
| [`tickets/`](tickets/) | Work train, tracked with [git-erg](https://github.com/MinhHaDuong/git-erg) |
| [`bench/`](bench/) | Executable probes and acceptance-harness work |
| [`bench/results/`](bench/results/) | Committed raw evidence behind reported figures |
| [`verification/`](verification/) | Reports that settle a factual question, and the probes that produced them |
| [`UPSTREAM`](UPSTREAM) | Machine-readable zoteus review baseline |

The authoritative chain is: rulings enter `DECISIONS.md` first, and
`REQUIREMENTS.md`, `CONSTRAINTS.md` and `DESIGN.md` are edited to match. A
ratified line stays open to a later veto; the veto lands in `DECISIONS.md` as
a new entry, and the other documents then follow. Requirements and
constraints state the contract; `DESIGN.md` must satisfy it; experiments and
tickets test or implement it. `FIELD-REVIEW.md` sits beside that chain rather
than inside it: it surveys what already exists, owns no design number, and
points at the owning document wherever it touches ours. `TERMINOLOGY.md` serves
the chain without joining it: it defines the words the three documents share and
names their owner, it owns no design number, and it never decides. A guard
enforces that, since a glossary is the easiest place to leave a second copy of a
threshold. `GOVERNANCE.md` sits
outside the chain altogether: it holds the rules we set for our own upstream
conduct, which the specification has no use for and a reader of the upstream
relationship should not have to dig for. `SECURITY.md` sits outside it as
well: it discloses what the system holds and where that can leak, and it
decides nothing, so a gap it names closes as a ruling like any other. Panel
documents are inputs, not conclusions; the adversarial design-review record of
cycle 2 is gone, lost with the pre-restart history (DECISIONS.md, 2026-08-31), as are the
superseded design documents that preceded the current chain.

Each document in the chain has its own organising principle, and the chain
requires this. `DECISIONS.md` reads chronologically, because ratification
happens in time and the record must show what came before what.
`REQUIREMENTS.md` and `CONSTRAINTS.md` read enumeratively, as checklists (R1
to R30, C1 to C4), because a reader needs to check off one promise or one
fact about the world, not follow an argument. `DESIGN.md` reads
architecturally, by section and subsystem, because architecture has structure
that a chronological or enumerative spine would flatten. This follows from
the authority split above: a document organised around when something was
decided cannot also be organised around what it does. Forcing one spine on
all four would cost the property that makes the chain worth having, which is
each document readable the way its own content demands. A reader arriving
mid-chain should expect the difference rather than read it as inconsistency.

## How work leaves this repository

This is a personal working repository, made public so that its intentions,
evidence, and unfinished reasoning can be inspected. It is not organised as a
community project and no contribution workflow is implied.

The deliverables land where they belong: as focused pull requests and issues in
Zotero, Zoteus, or another affected repository. This repository keeps the
longer argument, experiments, acceptance criteria, and decision record behind
those upstream interventions. A proposal need not use Zoteus, SQLite, FTS5, or
the current vector machinery; implementation-specific choices should not be
smuggled into the implementation-neutral contract.

## Current posture

Zoteus has shipped its own SQLite/FTS5 backend since v1.7.0, closing
[#10](https://github.com/oscardvs/zoteus/issues/10), which the prototype and
measurements here helped argue. The original storage-layer experiment is
complete. Its code is archived as evidence; the live work is the broader
retrieval design, its acceptance harness, scoped upstream contributions, and
the checkpoint against Zotero PR #6012.

Tickets `0014`–`0037` contain the current work train as re-formed by the panel
reviews; completed work is under `tickets/closed/`. `make upstream-status`
compares the reviewed zoteus SHA in `UPSTREAM` with current upstream `main` and
reports the local checkout SHA when the git-ignored `fork/` exists. It exits
nonzero when upstream has moved, making staleness visible without automating a
review decision. `make upstream-checkout` recreates that checkout.

This is an independent project and is not affiliated with or endorsed by the
Zotero project.

## The prototype phase, kept as the record of the argument

Before v1.7.0, zoteus held its search index resident in JS objects and
snapshotted it with one `JSON.stringify`. On a 7 541-item library that cost
gigabytes of RAM, failed to serialise past V8's string limit, and could not be
reloaded by a stock Node. The same corpus in SQLite/FTS5 served from about
128 MiB of process memory and reloaded on a stock Node — which was the point.
It did **not** build faster: measured at the same chunk geometry, through the
same Zotero API, the build took about as long either way, because it is bound
by fetching from Zotero rather than by indexing.

Measured over **one corpus of 360 811 passages read by both backends** — the
same crawl's `search-index.json`, migrated in place, rather than two crawls that
ought to agree: **5 759,6 MiB against 128,0 MiB** resident, and **90,87 s
against 3,86 s** to first answer.

Read `STATE.md` (the prototype phase's measurement record) before quoting any
of that. The memory figure excludes the kernel page cache holding the database
file, where the JS heap figure has no such remainder; charge SQLite the whole
file and the win is 6,8x rather than 45x. Both numbers are measured and both
belong in any external claim. The figures are measurements of the fork's
prototype, not of upstream's backend.

## Bench

Two dependency sets, declared apart because they are needed apart. The gate is
`python3 -m pip install -r requirements-check.txt` — three packages, none of them
a model runtime — and `make check` runs from there. The drivers below want
`requirements-drivers.txt` on top of it, which is where the heavy two live. A
missing package is reported by name before any guard runs, never at the tail of
an otherwise green output.

Drivers take `--server` / `--data-dir` and record `VmHWM` (the kernel
high-water mark, which cannot miss a peak between samples) rather than sampled
RSS. None defaults `--node-options` to a heap flag: whether the server survives
on a stock heap is itself an exit criterion, so the flag under test is never
the default.

```bash
# full-library build, then serve and query it
python3 bench/run_build.py  --server fork/dist/index.js --data-dir <dir>
python3 bench/run_serve.py                       # restart, open, query
python3 bench/run_serve2.py                      # same, auto-refresh off

# JSON -> SQLite migration, isolated, with the environment recorded
node bench/migrate_measure.mjs <index.json> <out.sqlite>
node bench/slice_index.mjs <big.json> <small.json> <n-chunks>

# query both backends and compare result sets
python3 bench/query.py   --server fork/dist/index.js --data-dir <dir> --backend json
python3 bench/compare.py --a res_json.json --b res_sqlite.json

# vector benchmarks (need sqlite-vec)
node bench/vec_scaling.mjs        # is vec0 KNN sub-linear? it is not
node bench/vec_quantize.mjs       # float32 vs int8 vs binary
cd fork && npx tsx ../bench/vec_recall.ts   # recall of two-stage vs exact

# standalone FTS5 prototype, and resting memory
node bench/fts5_bench.mjs ~/data/Zotero/storage bench/data/keys.txt bench/index.sqlite
python3 bench/measure_resting.py --server fork/dist/index.js --data-dir <dir>

# probes behind specific tickets
python3 bench/fulltext_sequence.py --output <f.json>          # 0012: the two version sequences
node bench/fold_sweep.mjs --output <f.json>                   # 0009: JS fold vs what FTS5 indexes
node bench/index_concentration.mjs --db <index.sqlite> --output <f.json>   # 0013: concentration and ranking
node bench/bm25_idf_effect.mjs                                # 0013, superseded by the above
bash bench/results/json-baseline/rung.sh <label> <items> <chars>   # the JSON memory ladder
```

Three of these read the LIVE Zotero local API or a real index rather than a
fixture, so their output is a record of one library at one moment; each writes
its own provenance into its artifact. `fold_sweep.mjs` is the exception and is
fully deterministic — it builds its own in-memory FTS5 table.

`bench/run_serve.py` and `run_serve2.py` still carry hardcoded paths from the
run that produced `bench/results/0003-full-build/`; they need editing before
reuse elsewhere. `rung.sh` used to be in that category and no longer is: every
path it uses is overridable and defaults into the committed tree.
