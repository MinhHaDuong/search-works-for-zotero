# The affected rows read at upstream v1.15.0

*Evidence, not authority. Read 2026-09-07 for ticket 0735. Where this report
touches design, `SPEC.md` remains the record.*

## Subject and method

The subject is `oscardvs/zoteus` at
`037bba8898add4b6d0eac54b44316c2732d5004d`, both the v1.15.0 release commit
and current `main` when read. The comparison base is the previous reviewed tip
`34d6c2681b1452aeaa2f8e8e90abe6e6b0f8df41`, which contained v1.14.0 plus two
documentation commits.

All 24 commit subjects and the 45-file path inventory were inspected from the
repository's bare mirror. Every changed watched file and the material adjacent
source, documentation and tests were read. The review follows the delta-bounded
rule ratified after the prior bump: source was read broadly enough to catch
mechanisms the release notes omit, while requirements were reconsidered only
where those mechanisms can change a verdict or invalidate evidence. No live-library
acceptance run was admitted. The current zoteus adapter still maps `pause` to
the old one-shot `stop`, has no `resume`, and the R22 master (0665) documents
the missing lifecycle and active-work arms; using it would test the wrong
control. The earlier v1.14 smoke remains historical wherever execution moved.

## Delta

The index schema remains generation 2. The material changes are:

- a durable `paused` value is persisted by both JSON and SQLite stores;
  `pause` cancels current work and gates build, refresh, update and semantic
  auto-build across restarts, `resume` only clears the hold, status exposes the
  value, and committed search remains available;
- JSON state saves are serialized from eager snapshots and awaited on close;
  the SQLite resume transition coordinates its pending commit;
- local ONNX inference moves from the main event loop to a shared worker
  thread; worker death rejects outstanding calls, the next call respawns it,
  and worker-start failure falls back in-thread with a warning;
- `ZOTEUS_LOG_FILE` can append the normal log stream to a named path; write
  failures fall back to stderr, and uninstall documentation names this
  outside-data-directory possibility along with API keys, usage storage,
  OAuth state and Zotero-side authorization residue;
- citation tools now forward `style` and `locale`, resolve renamed Chicago
  style ids, and consult the renamed-style map on a style 404. This is a real
  release change but lies outside the semantic-search requirement surface.

## Affected requirement rows

### Coverage, serving and cost

- **R1 and R4 — source improves; evidence grade unchanged.** Moving local
  inference off the main event loop removes a known source of service stalls
  while a build embeds. It does not establish newest-first coverage or a
  complete partial-index availability verdict, and no live acceptance run is
  promoted from the focused unit tests.
- **R6 — previous measurement is historical; current grade is `code`.** Query
  embedding now crosses the worker boundary. The v1.14 latency smoke cannot be
  represented as measurement of this executable path; focused tests establish
  behavior, not the required warm latency on the target machine.
- **R32 — source improves; no measured promotion.** Upstream's commit reports a
  20 ms ticker firing during three MiniLM batches where the old path starved it,
  but this is not the requirement's full-build laptop measurement and is not
  imported as one.

### Custody, observability and lifecycle

- **R10 — source still supports local-by-default; previous active-path
  measurement is historical.** Worker isolation does not add egress and its
  fallback stays local, but the current local execution path changed and was
  not exercised here against the real target.
- **R15 — source/documentation improves; verdict remains incomplete.** The new
  procedure declares the data directory, local API key, usage database, OAuth
  store, optional named log file, Zotero authorization record and legacy model
  cache. The v1.13 deletion diagnostic cannot grade this expanded v1.15
  inventory, and the R15 fidelity tracker (0648) still owns materialization,
  outside-arena and survivor controls.
- **R17 — source improves only at the log surface.** Optional durable logs add
  operational evidence but not the per-stage, trigger and outcome work counters
  the requirement asks for.
- **R22 — implementation changed from absent to present in source; acceptance
  remains open.** Upstream's control has the intended durable hold and
  resume-without-work semantics. It still needs ticket 0665's faithful active
  work, startup, crash, upgrade, exclusion, obviousness and resume arms before
  the requirement can receive a measured verdict.
- **R23 — schema verdict unchanged at generation 2.** Pause persistence touches
  both stores but adds meta/state, not a new schema generation or passage
  layout. Focused pause and index-tool tests cover reopen and persistence; no
  old migration measurement is relabelled.

### Unaffected rows

R3, R5, R7, R8, R12, R13, R16, R18, R19, R24, R29, R33, R34, R35 and R36 have
no changed mechanism in this range. The citation repair is adjacent product
work rather than a semantic-search requirement change. Their prior verdicts
stand, with prior artifacts remaining explicitly tied to their recorded
baselines.

## Focused verification

The upstream checkout built cleanly with Node 24.19.0. The bounded executable
check for the changed mechanisms passed **47/47 tests in seven files**:

- `tests/features/search-pause.test.ts`
- `tests/features/embedding-worker.test.ts`
- `tests/lib/logger.test.ts`
- `tests/tools/index-tool.test.ts`
- `tests/tools/search-tools.test.ts`
- `tests/tools/get-item.test.ts`
- `tests/features/styles.test.ts`

This repository's `upstream-status` and strict `schema-gate` passed. The
explicit old-to-new catch-up check reported 24 commits, twelve watched files
changed, and schema 2 unchanged. Three cited ranges changed: the two moved
`index-manager.ts` anchors were re-pointed, while the `build.ts:617-620` range
was re-read and remains the correct anchor. Ticket validation and the normal
repository suite passed: 1,270 tests, with 19 declared skips. This container
lacked the `sqlite3` executable, so its two CLI integration tests ran through a
temporary compatibility wrapper backed by Python's SQLite build, after FTS5
and DBSTAT support were checked; no wrapper or generated database is committed.

## Consequence

The reviewed baseline moves to v1.15.0 without an index-schema bump. R22 is no
longer absent in source and R15's declaration is materially fuller, but neither
is represented as measured. Measurement-dependent claims on the changed local
embedding path are not carried forward. The next work remains the existing,
bounded acceptance trackers; this rebaseline creates no new feature project.
