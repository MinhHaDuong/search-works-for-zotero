# Provenance — the 2026-09-03 acceptance matrix

`MATRIX.md` is the assembled table and carries its own limitations section,
which is authoritative on what the matrix does and does not establish. This
file records where each artifact came from, because a reader cannot tell from
a JSON file which build produced it.

## What produced each column

| artifact | target | how it was driven |
|---|---|---|
| `acceptance-zoteus.json` | zoteus | run by hand, `bench/acceptance/run.py --adapter zoteus`, 2026-09-03, against a working checkout — superseded, see below |
| `acceptance-zoteus-v1130.json` | zoteus | run by hand against `fork/dist/index.js` built at the reviewed SHA `b0e0bc8` (v1.13.0), 2026-09-03, after the re-baseline landed — the current reading |
| `acceptance-zotero-core-6012.json` | Zotero core PR 6012 | staged by a workflow agent; ten clauses decided by calling the assertion functions directly, two left `not-staged` |
| `acceptance-zotero-core-6012-hosted.json` | Zotero core PR 6012 | `run.py --adapter zotero-core-6012` against that staging, later the same day, once the host prohibition lifted — all twelve clauses, Xvfb `:77`, port 23519 |
| `acceptance-zotseek.json` | ZotSeek | staged by a workflow agent; ten clauses decided by calling the assertion functions directly, two left `not-staged` |
| `acceptance-zotseek-hosted.json` | ZotSeek | `run.py --adapter zotseek` against that staging, later the same day — all twelve clauses, Xvfb `:77`, port 23219, host `/opt/zotero7/zotero` |
| `acceptance-zotero-mcp.json` | 54yyyu/zotero-mcp | staged from the committed lock file and run by a workflow agent |
| `acceptance-fixtures.json` | none — the instrument itself | `run.py --fixtures`, 16 fixtures x 12 assertions |

Beaver has no column here. Its adapter is ticket 0586's and was in flight in a
separate lane during this run; `bench/results/0586-beaver/` holds its own
artifacts.

## Two caveats that are this file's reason to exist

**RESOLVED 2026-09-03, same day.** The zoteus column was first measured
against a working checkout, not the reviewed SHA: the declaration read
`revision: 1.12.0` from `package.json`, accurate as a version string and
misleading as provenance, since the `fork/` tree it ran against sat at
`879b75b` on branch `droplist-df-pruning` while `UPSTREAM` named `b05ed69`.
That column (`acceptance-zoteus.json`) is superseded and kept only as the
historical record of what was first measured.

Upstream released v1.13.0 the same afternoon and the reviewed baseline moved to
its tip, `b0e0bc8` (`DECISIONS.md`, ratified: pin `main`, not the latest shipped
tag). `acceptance-zoteus-v1130.json` re-runs the layer against `fork/dist/index.js`
built at that exact SHA — `revision` now correctly reads `1.13.0` — and is the
current reading for this column. The verdicts are unchanged in shape: 3 pass, 1
fail, 1 not-offered, 7 not-run, and the egress fail still shows 4 DNS lookups on
the subject arm against 1 off-machine plus 3 DNS on the net-shared control —
consistent with the update-check hypothesis and not yet isolated from it (see
0613's log). What changed is provenance, not verdict: a reader can now cite this
column as a claim about the reviewed tree rather than about a branch that no
longer exists in that form.

**Four cells read `not-staged` for a scheduling reason, not a technical one —
and they were filled later the same day.** Zotero core 6012 and ZotSeek are
host-bound: their R10 and R15-install clauses walk into a lifecycle block that
launches a Zotero desktop host. A parallel session held the machine's Zotero and
its local API port for a full-library index build throughout this run, so every
agent was forbidden to launch one. The staging those agents did was the
expensive half and it survived: the #6012 build was still at
`src/app/staging/Zotero_linux-x86_64/` stamping `Version=11.0.SOURCE.19e79625b`,
and the ZotSeek XPI still matched its pinned sha256. Nothing was rebuilt or
re-downloaded. Both targets were then run end to end and the four cells decided
— three red, one green — into the two `-hosted` artifacts above.

Two facts about that later run belong here and not only in the artifacts. **The
peer's port was never in fact free**: 127.0.0.1:23119 stayed held by the
operator's own resident Zotero 10.0.1 throughout, which is simply what a running
Zotero desktop does, and it did not matter, because no adapter on this roster
uses that port — #6012 listens on 23519 and ZotSeek on 23219. What had blocked
the cells was a policy against launching a host, and it is the policy that
lifted. **Both egress runs died before their verbs ran**: the egress sandbox
mounts `/tmp` read-only, GTK's icon loader cannot write its temporary file
there, and the host aborts — so those two reds are read off runs that never
reached the retrieval path. The assertion decides that case itself and both
artifacts state it before their verdicts.

## The fixtures file is job-local, and newer than the committed one

`acceptance-fixtures.json` here is 16 fixtures x 12 assertions and includes the
two R22 checks. The repository's standing fail-control matrix,
`bench/results/smoke-1.12.0/acceptance-fixtures.json`, is dated 2026-09-02,
carries 14 x 10, and has no R22 rows at all. Both report an empty
`assertions_never_seen_red`; only this one can speak for the two assertions
that did not exist on 2026-09-02. Refreshing the standing artifact is not this
directory's business and is not done here.
