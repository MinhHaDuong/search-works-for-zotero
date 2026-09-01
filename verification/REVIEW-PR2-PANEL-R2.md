# Review panel — PR 2 round 2 (fork PR #5), six perspectives

Delivered 2026-09-01 by the panel launched against fork PR #5 (`pr2-diacritics-v2`,
round 2 of "keep diacritics in the index, and index the stripped form beside them").
Verdict: **request-changes**. Recorded here because the panel's own transcript dies with
its session; triage against round 3 (`pr2-diacritics-r3`, `f80d860`) appended at the end.
Evidence, not authority — where a finding touches the design, the owning document rules.

## Blockers (all executed, not argued)

- **B1 — Turkish `İ` shreds under the fold order.** `normalizeForSearch("İstanbul")`:
  JS lowercases `İ` to `i` + U+0307; NFC cannot compose it (no precomposed target);
  U+0307 falls outside `[\p{L}\p{N}]`, so tokenize returns `['i','stanbul']` and the
  1-char fragment is dropped — `tokenize("İstanbul") = ['stanbul']`. Unfindable both
  spellings on SQLite. Reproduced by three seats independently. Root cause: marks are
  stripped before case-folding can *introduce* one.
- **B2 — `makeSnippet`'s length-preservation premise is false.** ~92% of (ASCII base ×
  combining mark U+0300–U+036F) pairs have no NFC-composable target, so those sequences
  stay decomposed and stripping *shortens* the text; a snippet window can contain
  neither the accented nor the stripped form of the hit. Same root cause splits such
  words into fragments before `foldMarks` sees them, so their stripped extra token is
  never generated either — one cause, three symptoms.
- **B3 — a transient, retryable I/O error mid-migration discards a proven-intact
  database.** `ulimit -f`-induced write failure (same class as a full disk) mid-ladder:
  `runMigrations` catches any error and returns a message; `reconcileSchema` treats
  that unconditionally as "foreign schema" and sidelines the file, creating a fresh
  empty DB — reproduced twice, exit 0, 87 MB intact v1 renamed away. `isCorruptionError`
  (`corruption.ts`) exists for exactly this distinction and is never consulted on this
  path. The WAL transaction itself is sound; this is policy on top of a correct
  transaction.

## Verifiable, non-blocking (measured)

- Ranking distortions from the extra tokens: (a) ~17% BM25 length penalty on a
  controlled accented pair; (b) stripped-form IDF diluted 4,997 → 2,335; (c) TF-capped
  extra token can rank a document *about* an accented term below one mentioning the
  plain spelling once (−1,165 vs −1,747); (d) **corpus-level `avgdl` contamination**:
  unrelated unaccented documents' scores shift +38–41% when accent-heavy filler joins
  the corpus — this one is new relative to the checkpoint's cost list.
- Keyword injection: accenting one vowel per word injects the plain form as an
  invisible index-only token (50/50 unrelated keywords indexed and rankable against
  weak competition; cannot unseat strong matches; cannot leak into snippets).
- The sideline is silent where users look: `storageNotice` is never composed into
  `zotero_semantic_search`'s summary; a sidelined-and-rebuilt index reads as "index
  empty, building automatically".
- Shield self-collision: `show()` restores placeholder codepoints U+FDD0–FDD5 by value,
  so a passage genuinely containing those noncharacters (bad OCR) is silently rewritten
  to real letters and indexed. Low severity; untested case.

## Doc propagation (seven confirmed stale sites + CHANGELOG gap)

`docs/semantic-search.md:475`; the DDL comment in `sqlite-index.ts` above the
`remove_diacritics 0` line; two "never been bumped" comments above a populated ladder;
`normalizeForSearch`'s header; `query-terms.ts:30`'s `thé` → `the` worked example;
the two test headers describing the removed symmetric design. `[Unreleased]` silent on
a change that alters search semantics and forces a migration with a hard downgrade
break. These are the checkpoint's held findings, confirmed seat-by-seat.

## What held under attack (executed clean)

DROP+recreate of the external-content FTS5 table; paged migration correct at page
boundaries (1999/2000/2001/4000/4001); 24 kill-9 trials across all phases, zero torn
states; downgrade sideline preserves all rows and vector salvage reused every vector
with 0 embed calls; `indexText`/`foldMarks` pure over 3 000+ adversarial inputs; no
snippet leak of synthetic tokens; Vietnamese composes correctly; suite green.

## Triage against round 3 (added at recording time)

- B1 and B2's snippet-offset half are **already fixed in r3** — the checkpoint records
  both with controls that go red on revert; the panel reviewed round 2.
- **B3 is live in r3**, verified on `pr2-diacritics-r3` source at recording time: the
  `reconcileSchema` failure path still sidelines on any `runMigrations` failure and
  never consults `isCorruptionError`. Design-independent (the migration rung ships
  under either PR 2 shape); handed to the expansion-arm builder as an in-scope fix.
- The B2 mechanism (uncomposable base+mark pairs) and cost (d) are measurement inputs
  for the arm A / arm B comparison the author ordered; both are in the padme handoff.

## Process notes (the panel's own)

The first-round red-team and doc-propagation transcripts expired before delivery; both
seats were re-run fresh with confirmed findings pre-loaded. A worktree-isolation guard
refused every Bash command in the coordinating session; sub-agents were unaffected, and
the doc-propagation seat completed via read-only sweep, recommending a repo-wide
`grep -rn "remove_diacritics 2"` backstop when a shell is available.
