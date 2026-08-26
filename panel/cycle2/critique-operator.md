# Critique — cycle-2 OPERATOR & GATES memo

*Adversarial critic, 2026-08-26. Every number below recomputed from the artifacts; every cited line re-read in `/home/user/oscardvs/zoteus` at `edf2748`.*

Verdict in one line: the memo's instrument-panel thesis is right and most of its code citations are exact, but its flagship gate is calibrated against a misread of its own evidence, and the convergence harness — the memo's centerpiece — is specified with three mutually inconsistent accounting rules that its tie-free, quarantine-free, monster-free fixture is too gentle to ever expose.

---

## FATAL

### F1 — The golden gate's hard floor is refuted by the artifact that justifies it

b.4 claims: "the worst legitimate per-query value observed was 0.5385 (purposive set) … Legitimate ≥ 0.54, broken = 0.00: 0.5/0.8 sit inside that empty gap with margin." Confession #2 repeats it: "The gap [0.0, 0.54] is real but measured once."

Recomputed from `bench/results/0013-concentration/uncapped-477512.json`, the same file the memo cites for its mean (0.8753) and rest_retention (0.9693): the **random sample (n=60) has per-query Jaccard minimum 0.25**, with two queries under the 0.5 floor — `hyperinflation admit` (0.25) and `incompleteness dieback` (0.4286). The memo took the minimum from the 12-query purposive set and the mean from the 60-query random set, and the "empty gap" evaporates when both statistics come from the same distribution. There is no gap: legitimate perturbation reaches 0.25.

Consequence, in the memo's own logic: a per-query hard floor at 0.5 goes red on ~3% of legitimate queries per legitimate perturbation. With ~40 golden queries, expect a false red on roughly every legitimate ranking-adjacent change — including the section-collapse the design itself mandates. Reviewers re-pin, re-pins get rubber-stamped, the gate gets discounted — which is **the exact mechanism the memo names as "how 0009 happened"** when arguing against an order gate. The threshold pair as specified dies; the mean-≥0.8 half survives.

This also makes confession #2 a decoy: it worries the thresholds "transfer an argument, not a measurement" across perturbation families, while the measurement it transfers from already falsifies the floor.

**Repair (cheap):** re-derive from the full n=60 distribution: keep mean ≥ 0.8, replace the per-query floor with a quantile rule (e.g. ≤5% of queries below 0.35, or median ≥ 0.6, or floor at 0.2 — below the observed legitimate minimum). One paragraph and one constant; the gate's architecture is untouched.

## MAJOR

### M1 — The convergence harness's accounting contradicts itself three ways

The b.3 prefix equality is `covered == |{dateAdded ≥ boundary}| − partial − quarantined + outOfBand`. Attack it with one quarantined item:

**(a) Boundary vs the subtraction terms.** b.2 says the cursor "closes the head of the contiguous **terminal** run" (terminal = done|empty per b.1). A quarantined row is not terminal, so the cursor stops at it forever — boundary freezes at the quarantined item's date, everything older keeps getting covered, and the coverage sentence's "keyword-searchable back to 2016-04-11" understates reality permanently ("retries when Zotero re-extracts it" may be never). Under that literal spec, the quarantined item sits *below* the boundary, `|{dateAdded ≥ boundary}|` excludes it, and subtracting `quarantined` over-subtracts: the equality fails by the quarantine count on a correctly working system. The formula is only correct if the cursor passes quarantined and partial rows — which the spec text forbids. Same argument for `partial`.

**(b) outOfBand is double-defined.** Phase 1 uses it arithmetically: covered items *ahead of the frontier prefix*. Phase 2 uses it as *edit-triggered work*: edit a title, assert `outOfBand.embed == 1`, "then boundary arithmetic re-holds." But a title edit does not change `dateAdded`; at 100% coverage the edited item is inside the prefix, so the arithmetic meaning gives 0 while the asserted value is 1 — and with covered == total and prefix == total, the equality reads total == total + 1. Both phase-2 assertions cannot hold. The field the memo says "exists for the harness" is the field the harness cannot define consistently.

**(c) The record stage vanishes from its own test.** (a)§2.1 promotes record to "a first-class ledger stage with its own counters." Phase 2 edits a title and asserts `Δwork.chunk.edit == 1, Δwork.embed.edit == 1, all other work cells 0`. If record is a stage, `Δwork.record.edit` must be 1, or edit-one-count-one (R27) is violated by the spec itself. And `Δwork.chunk.edit == 1` presumes the record is one section, while the record ruling gives title/abstract/keywords field identity — plausibly several passages.

None of this fires in the harness because the fixture is deliberately tie-free, quarantine-free, and (in phase 1) monster-optional — the harness is proven only on the corpus that cannot exercise its subtraction terms, the same failure shape as confession #1 but unconfessed.

**Repair:** define a "settled" state set (done|empty|quarantined|band0-done) as cursor-passable; define outOfBand purely as set-membership (covered items older than the current boundary, decremented as the boundary sweeps past); count edit work only in `work.*.edit`; fix phase-2 assertions to `outOfBand == 0`, `Δwork.record.edit == 1`, `Δwork.chunk.edit == sections(record)`; add a phase 3 whose fixture contains one quarantine and one monster.

### M2 — The fold gate crashes rather than measures against the tree it targets

b.4's wiring plan is "(1) repoint `--fork` … to `/home/user/oscardvs/zoteus`, (2) a 20-line assert script that fails on `misses > 0`," and claims "run against v1.7.0 stock the gate is red today." Verified: `fold_sweep.mjs:34` (memo says :35 — off by one, cosmetic) imports **both** `tokenize` and `normalizeForSearch`; `querySide()` calls `normalizeForSearch` at line 70. Upstream `tokenize.ts` exports **only `tokenize`** (11 lines, verified). Against stock upstream the sweep throws `TypeError: normalizeForSearch is not a function` at the first codepoint — red by crash, not by classification, so there is no miss count to record in the waiver, and the waiver-deletion ritual on #19's merge has no baseline number. Secondary: the memo's "misses > 0 **in the likely-typed set**" invents a classification the sweep does not have — "likely to type" exists only in a comment; the `misses` counter (line 155) is global. (Also for the record: the archived 0009 artifact shows 15 divergences, all `narrows`, not the delta's "12 escaping codepoints" — the memo wisely quotes neither.)

**Repair:** third wiring change — querySide falls back to `tokenize`-only when `normalizeForSearch` is absent (upstream's shred is fully visible through `tokenize` alone: "théorie" → th/orie vs index "theorie" is a textbook `misses`), or the assert script treats module-shape mismatch as an explicit red-with-reason.

### M3 — Census-intersect has a version-0 blind spot the memo does not disclose

The §2.5 kill is correct (see SURVIVED below), but the replacement is oversold as "the only safe close." Recomputed from `0012-fulltext-sequence/sequences.json`: **584 of 8,037 entries (7.3%) carry version 0** — the scout's third class, local extraction. Equality-compare detects a change only when the stored value differs from the current one; a local re-extraction that stamps 0 again is 0 → 0, invisible. For those attachments the freshness block reports "current" while serving stale text — a coverage report that lies, the exact sin the memo's thesis is built against. The scouts even hand the memo its own absolution: Zotero's SDT layer documents an accepted staleness residue of the same shape.

**Repair (cheap):** disclose it as an accepted residue in the contract (platform-aligned), and/or spot-check a bounded batch of version-0 entries per tick by content hash.

### M4 — The pipeline lease can be stolen from a live worker mid-monster

b.6: lease "renewed each micro-batch, stealable when expired," expiry unspecified. The monster fetch is a **single HTTP request for a 44.9MB body** (§2.3 of v1, inherited) — no micro-batch boundary exists inside it, so no renewal happens for the duration of the slowest single operation the pipeline performs. A second zoteus observing an expired lease steals it while the first worker is alive and mid-fetch; both then extract and embed — R13's "no passage extracted or embedded twice" violated by the very mechanism introduced to observe R13. The `claimed_input` commit guard prevents corruption and double-*commit*, but not double-*work*, and duplicate embedding is the one cost class the sheet's C3/consent lines care most about.

**Repair:** heartbeat renewal on a timer decoupled from batch progress, expiry sized above worst-case single-fetch; or renew immediately before any long fetch with a stated bound.

## MINOR

1. **Flagship example arithmetic:** extract `covered=6100` = 5,562 + 538, plus `quarantined=1` ⇒ 6,101 items with attachments, but the sentence says "of 6,100." Also b.1's definition (covered = every eligible unit terminal) makes attachment-less items vacuously covered at extract (7,541), while the JSON's 6,100 says they are not counted — this ambiguity decides whether `covered.embed == items.total` can ever hold on a real library, i.e. whether R26's terminal assertion is even stateable outside the fixture.
2. **"30-row counters table"** is ~45 rows (4 covered + 1 empty + 1 partial + 4 outOfBand + 4 quarantined + items.total + drift + 4×7 work + batches). Sub-ms claim unaffected.
3. **§2.7's FTS amendment is one clause from violating R5:** "MATCH unconstrained, bitmap applied to candidates after, in JS" must mean *filter the full match enumeration then take top-k* (#6012's actual practice), not *filter a truncated top-N pool* — the latter is literally the "post-filtering a top-k" R5 forbids and yields false empties for tiny scopes. State it.
4. **Census-intersect is an O(library) fetch every 60s tick** — forced by the API (`fulltext_last_modified_version_header = None`, verified), but v1 disclosed its O(library) census as every-Nth-tick; the standing cost and the cadence knob deserve the same disclosure, and R3's "cost ∝ change" letter deserves the acknowledgment.
5. **Pause vs explicit build is unspecified** (b.5): does `action:"build"` while paused refuse or override? Either is defensible; silence is not.
6. **Line cites:** fold_sweep import at :34 not :35; everything else checked exact.

## SURVIVED ATTACK

- **Every headline number checked out exactly**: 2,084.9 MiB / 404.1 MiB / 5.16× / 44,906,152 chars (0011); 8,037 entries, since=410 → 7,453, 0.9273 (0012); mean 0.8753, rest_retention 0.9693, identical_ordered 22/60, dominant in top-10 of 28/60, purposive min 0.5385 (0013); Makefile:21 verbatim.
- **The pause verdict and design (b.5)**: `semantic-search.ts:48` `auto_build !== false` and `index-tool.ts:56-64` requestStop-only verified line-exact; the persisted DB row scoped by dataDir is the minimal correct fix and even covers R13's second process for free.
- **The §2.5 kill is justified**: v1's ascending version-group sweep permanently strands all 584 version-0 entries below any positive watermark — the replacement's 7.3% blind spot (M3) is strictly smaller than the disease.
- **The counter contract (b.2) core**: same-transaction increments + idle reconciliation + *surfaced* drift that fails the harness is the right C4 shape; 374ms-scan vs sub-ms point-read cost basis holds.
- **statusSummary (`build.ts:135`), warn-once (`fulltext-source.ts:131-137`), `dropStaleVectors` (:286/:304/:890), write-only `SCHEMA_VERSION` (:26/:153)** — all verified as claimed; the memo's upstream homework is genuinely clean.
- **The PR9→issue reshaping** (c): SYNC's two-for-two asymmetry is real and the acceptance-spec-as-issue-body is the correct C2 move; could not construct a scenario where it loses to a code PR.

**Counts: 1 FATAL, 4 MAJOR, 6 MINOR.** The memo's operator machinery is sound in shape and dishonest in exactly two numbers-adjacent places: a gate floor its own artifact refutes, and a harness formula its own fixture is designed never to test.
