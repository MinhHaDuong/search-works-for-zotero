# Release-readiness review of upstream zoteus v1.16.0

*Evidence, not authority. Run 2026-09-08 for ticket 0739. The seat reports in
`verification/qa-v1.16.0/` are the record; this page is the triage over them.*

## Subject and method

The subject is `oscardvs/zoteus` at `910310b`, the v1.16.0 release commit. Five
seats read the tree in parallel on separate lenses — security, data safety,
correctness, dependencies, red team — each on Fable 5.1, decorrelated from the
Opus session that briefed them and triaged their returns. Each seat had the
same standing instructions: cite file and line, trace one concrete failure per
finding, fire a positive control before reporting a null, and rank for a
maintainer who closes issues by building the fix within hours.

**No seat executed anything.** The clone carries no `node_modules` and none was
installed, so the 949-test upstream suite never ran here and no finding rests
on a test result. Two seats ran their own out-of-tree probes: the dependencies
seat ran `npm audit --package-lock-only` (16 advisories, so its null concern
does not arise) and the security seat drove Node's `URL` and `net` against a
live loopback listener to confirm finding S1. Everything else is source
reading.

Three findings were re-verified against the source by the coordinator before
this page was written, marked **✓coord** below. The rest are the seats' own
readings, cited but not independently re-derived.

## What the round found

The conventional attack surface is closed, and that is worth recording so the
next round does not re-derive it: FTS5 term quoting with bound parameters,
prepared statements throughout, a 128 MB EPUB inflate cap with zip64 rejected,
a 20 MB PDF cap with `isEvalSupported:false`, realpath confinement on the
caller path, OAuth with PKCE and an encrypted token store, constant-time secret
comparison, key redaction before every log write, and no telemetry on the
default path. The red-team seat also established that the candidate-pool
widening shipped for #65 terminates — the non-termination hazard its brief
named is not present in this tree.

What the round did find divides in three: a family of silent-wrong-state
defects in the index machinery, one SSRF story told twice, and a design-sized
exposure that no patch closes.

## Triage

| # | Finding | Seat | Severity | Verified | Disposition |
|---|---|---|---|---|---|
| Q1 | Catch-up clears passages and leaves their `vector_codes`; every semantic query on a coded index then falls back to the exact scan, until a full rebuild | correctness F1 | high | **✓coord** | issue |
| Q2 | Incremental update drops an item's PDF passages on a transient full-text read failure, then stamps — the full-text sibling of the #63 fix that only the own-words lane received | safety 2 | high | seat | issue |
| Q3 | A second process on the same data dir overwrites stamp, checkpoint, library and pause from stale memory at `close()` — and the docs recommend that two-process setup | safety 1 | high | partial | issue |
| Q4 | The SSRF guard exists once and is bypassable: `isPrivateOrReservedIp` decodes only the dotted IPv4-mapped form, and `downloadAttachment` does not call it at all | security 1 + redteam 3 | high | **✓coord** | issue |
| Q5 | An item deleted mid-crawl shifts the page the opposite way from #59 and is never served, with no `?since=` delta to recover it | correctness F2 | high | seat | issue, with the test first |
| Q6 | `pdfjs-dist` is frozen on the last release that runs on Node 20.19, so the branch carrying CVE-2026-16633 cannot be patched without raising the engine floor | dependencies 1 | medium | seat | issue |
| Q7 | `citeproc` is CPAL-1.0/AGPL and the bundles and image redistribute it with no Exhibit B attribution | dependencies 2 | medium | seat | issue |
| Q8 | The shipped `fly.toml` enables `/metrics` with no token and no proxy, and `/usage.json` carries per-user Zotero ids | security 2 | medium | seat | issue |
| Q9 | `mode:"semantic"` answers `No matches` where it promises to refuse, when vectors exist but embeddings are off | correctness F3 | medium | seat | issue |
| Q10 | Library content reaches the calling model unframed, while only `delete_items` is confirmation-gated | redteam 1 + 2 | design | seat | issue proposing a threat model |

Below the line, recorded in the seat reports and not carried here: a re-parented
note lost from both items, a stale `If-Unmodified-Since-Version` reused across
permanent-delete chunks, `manage_collections action:"delete"` ungated, musl and
gnu skia binaries both shipped in the Linux bundle (≈32 % of 57 MB, derived not
measured), PRIVACY.md omitting the Hugging Face weight download, and the dev
tooling's own EOL advisories.

## The four to send first, and why those

**Q1 and Q4 are verified and self-contained.** Q1's asymmetry is visible in one
file: `deleteItem` runs `deleteItemCodes` and `invalidateCodes`
(`sqlite-index.ts:1316-1317`), and the per-source twins `clearFulltext`
(`:1360`) and `clearOwnWords` (`:1378`) run neither, though the prepared
statement they need already exists at `:1041`. Q4 is the same shape one
directory over: `cimd.ts:39-64` is a real guard, its IPv4-mapped branch matches
only `^::ffff:(\d+\.\d+\.\d+\.\d+)$`, and `new URL()` normalises a bracketed
literal to the hex form that falls through; `store.ts:88-103` then fetches a
caller-supplied URL without consulting the guard at all. Both are a few lines,
and both are the kind of finding this maintainer has merged from here before.

**Q2 continues work he has already accepted.** He built the #63 fix for the
own-words census five days after we filed it; the full-text lane has the same
cursor and did not get the same treatment. Filing it as the sibling of a closed
issue costs him no context.

**Q3 is the one with a user-visible cost.** Quitting the desktop app after a
headless build zeroes the stamp, and the next `update` becomes a full rebuild
that clears the finished index. The setup that triggers it is the one the
documentation recommends.

Q5 needs its test written before it is filed. The seat traced it on the #59
fixture and predicted the sibling case red; that prediction is not a
measurement, and this project's own standing bar — green tests are necessary,
not sufficient, and a check is worth nothing until it has been seen failing —
applies to a filing as much as to a patch.

## What this does not settle

No requirement row moves on this evidence. Grades stay where ticket 0738's
re-read puts them: source reading cannot promote a row to `measured`, and
nothing here was run against a live library. Q1 and Q3 both bear on rows about
coverage honesty and serving cost, and 0738 owns whether either mechanism
changes a verdict.

The seats' own limits are stated in each report and are not softened here. The
security seat could not audit the pinned SDK's call ordering, so whether Q4's
CIMD half is reachable unauthenticated is read from `provider.ts` alone. The
safety seat names three findings that a thirty-second live check against a real
Zotero would settle and asks that Q3's be run before it is filed. The
dependencies seat could not read the published Docker image. The red-team seat
did not touch the hosted instance, by instruction.
