# The twenty-three rows read at upstream v1.14.0

*Evidence, not authority. Read 2026-09-04 for ticket 0670. Where this report
touches design, `SPEC.md` remains the record.*

## Subject and method

The subject is `oscardvs/zoteus` at
`34d6c2681b1452aeaa2f8e8e90abe6e6b0f8df41`, current `main` when read. It
contains v1.14.0 at `7a5622f` plus two documentation commits. The comparison
base is the previous reviewed tip `b0e0bc8` (v1.13.0-era main).

All intervening commits and all changed files were read from the repository's
bare mirror. The current tip was built from a detached checkout. Focused tests
for pooling, configuration, caller paths and usage endpoints passed. The smoke
ran against the real Zotero library, the existing current-generation index and
the explicitly supplied local model runtime; its raw result is
`bench/results/smoke-1.14.0/checks.json`.

The target-neutral acceptance run was attempted and rejected as evidence: the
dedicated `untrusted-runner` could not execute Node from the operator's private
installation. Its failed artifact is not committed. Persistent ACL expansion
was declined, so acceptance-only claims are downgraded below instead of being
carried across the baseline.

## Delta

Eighteen commits changed sixty-two files. The index schema remains generation
2 and the `passages` shape is unchanged. Material changes are:

- per-model pooling is curated and non-default pooling joins the embedder
  identity; unknown model ids retain mean pooling as an explicitly unvalidated
  escape hatch;
- the release check defaults off and is exposed as an opt-in desktop setting;
- opt-in local usage storage, per-tool metrics and protected operational
  endpoints were added;
- caller-supplied filesystem paths are confined to the data directory for
  remote callers, explicit overwrite is required for a supplied download path,
  and the container drops root;
- every writing tool now carries an explicit destructive hint;
- git-URL installation builds the package through `prepare`;
- the software privacy policy now distinguishes installed software from the
  separately governed hosted service.

## Requirement rows

### Coverage and convergence

- **R1, R4, R32 — unchanged.** Pooling changes vector correctness and identity,
  not crawl order, partial-index availability, or the performance contract.
- **R17 — text updated, verdict unchanged (`partial`/`code`).** The new metrics
  and usage ledger count calls, requests and latency. They do not report work
  per stage, trigger and outcome, nor a most-recent-covered date.

### Change and cost

- **R3 — evidence downgraded from `measured` to `code`.** The source still uses
  version watermarks and still exposes no work-counter object that can decide
  recomputation proportionality. The old acceptance artifact is historical,
  not evidence about this executable baseline.
- **R35 — unchanged.** The update path still has no timer, watcher, event stream
  or startup hook. The only changed timer is usage retention, unrelated to
  index freshness.

### Corpus

- **R8, R16 — unchanged.** Full-text and own-words sources did not change.

### Query

- **R5, R18, R24 — unchanged.** No scope-before-truncation, empty-answer or
  locator mechanism changed.
- **R6 — re-measured, verdict unchanged.** The populated-index smoke answered
  every query and the warm runs remained inside the requirement's budget.
- **R33 — text updated, verdict unchanged (`partial`/`measured`).** The hybrid
  modes are unchanged. Correct pooling repairs silent semantic degradation for
  curated non-mean models, but the agreement clause remains ungated.
- **R34 — unchanged.** No pinned task-answer set landed upstream.

### Multilingual

- **R7 — text updated, verdict unchanged (`partial`/`measured`).** Curated
  pooling removes a silent defect for the multilingual candidate field and the
  override makes the choice explicit. The default remains English MiniLM, so
  the MUST tier still fails by default.
- **R29 — text updated, verdict unchanged.** Correct pooling makes configured
  multilingual candidates faithful to their training, but no multilingual
  model is the default.

### Custody and lifecycle

- **R10 — re-measured, verdict unchanged (`shipped`/`measured`).** The local
  embedder is still the default and active in the smoke. The unsolicited
  release lookup identified at the previous baseline now defaults off. Opt-in
  usage stays local and records shapes rather than argument values.
- **R15 — re-measured, verdict unchanged (`partial`/`measured`).** The smoke
  again placed a newly materialized model cache under the data directory.
  Usage storage adds another declared derived-state file when enabled, and the
  container's non-root user narrows impact; uninstall completeness remains
  absent.
- **R22 — unchanged.** v1.14.0 adds no durable pause. Upstream PR #57 remains
  outside this reviewed tip.
- **R23 — re-measured, verdict unchanged.** The previous schema still migrates
  in place and foreign stamps are still sidelined. The schema did not move.

### Multi-library and multi-process

- **R12 — unchanged.** Library identity and salvage scoping did not move.
- **R13 — evidence downgraded from `measured` to `code`.** Locking and the
  single-writer shape are unchanged, but the executable-baseline acceptance
  rerun did not produce admissible evidence.

### Normalization

- **R19 — unchanged (`none`/`inferred`).** Pooling is not equivalent-form
  normalization, and the user-visible assertion still has not run.

## Consequence

No delivered verdict changes. Two acceptance-dependent evidence grades fall
from `measured` to `code`; four rows gain current source or smoke detail. The
baseline can move without changing the index-schema mirror.
