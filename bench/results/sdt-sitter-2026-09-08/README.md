# Live sitter journals, doudou, 2026-09-08

Copied out of the plugin's own diagnostics clipboard by the author, from the
running Zotero (10.0.1, pid 3389020). These are evidence, not illustrations:
tickets 0727 and the pre-release review of the same morning cite them.

The channel is the scrubbed one. `scrubSDTRecord` drops `rootURI`, and the
2026-09-08 security review enumerated all 24 `emit` call sites and found no
title, filename or path among them — item ids, counts, byte sizes, page counts,
phase names and regex-validated error class names only.

## `0.3.5-livelock-journal.json`

One activation of the probe build 0.3.5 (ticket 0727 arm 3), captured ~09:35.
What it records, and why it was kept:

- **Two complete censuses, eight minutes of work, zero documents indexed.**
  Sweep 1 runs 367 s (six consecutive `census` heartbeats), writes its compact
  cache of 13 699 rows, and is refused `cpu-busy`. Sweep 2 starts exactly 30 s
  later, re-walks the whole library for 116 s, and is refused identically, with
  byte-identical counters.
- This is the pre-release safety review's finding that the census sits IN FRONT
  OF the admission gate, observed rather than deduced: `nextSweepDelayMS`
  returns 30 s while the phase is not `waiting`, so a machine the gate has
  judged busy is re-walked every 30 s for the cost of saying no.
- The refusal itself was CORRECT. Load was 11,56 on 8 cores at capture time,
  and `ps` put Firefox and its content processes above 80 % against 12,8 % for
  `zotero-bin`. The gate did its job; what is defective is the price of doing
  it.
- `completed: 0, failed: 367, pending: 39, scanned: 16706`. The 367 are CENSUS
  VERDICTS, not failed extractions — nothing was extracted. They come out of
  `inspect()`'s failure classification, which the same morning's coverage and
  validity reviews found to be exercised by no test at all (eight targeted
  mutations of that classification, eight silent).

## `0.3.5-all-admissions-fail.json`

The next capture, ~09:37, and the more serious of the two. The load fell, the
gate opened, and the 39 pending documents were admitted — **every one of them
failed**.

- **39 of 39, and the failure is instant.** `admit` to `settle` is 50–90 ms for
  PDFs of 380–660 kB; twelve documents pass through in 1,4 s. That is not
  extraction trying and losing, it is a refusal upstream of any real work.
  `failed` goes 367 → 406, exactly the 39 that were pending.
- **So the cause looks systemic, not documentary**, and that matters for ticket
  0606: "how many documents native extraction genuinely cannot handle" has a
  different answer if 39 documents are hard than if one path is broken. Nothing
  here establishes which — the shape of the evidence is what argues for
  systemic, and that is an observation, not a verdict.
- **The journal cannot say why.** `classifyError` keeps the class name only, and
  every one of the 39 records the bare `Error` — no information. The MESSAGE
  exists, but by design it goes only to `sitter.state.error` and the dialog's
  `textContent`; the 2026-09-08 security review confirmed by enumeration that no
  `emit` call site carries it. The screen is the only copy.
- **Every failing admission carries `pages: null`.** Recorded, not interpreted.
  Whether that is the cause, a correlate, or the separate `valueQueryAsync`
  finding of the same morning showing through is not established here.
- **The next sweep still starts 30 s later** although the phase fell back to
  `waiting` with `pending: 0`, where the idle cadence should be ten minutes.
  Either candidates remain, or a session-failed document is not leaving the
  queue. Open.
