# Upstream PR body — the library-derived droplist (ticket 0091, PR 3 of the series)

Drafted here, sent as written. Branch `pr3-droplist-r5` on the author's fork at `11385a2`,
one commit stacked on `6b7c152` — the query-expansion design as it stood when PR 3 was
built — on `base-v1.12.0` (= upstream `b05ed69`). **Not filed**: the slot is granted
(2026-09-01, DECISIONS.md), and filing waits on the repo-side record merging through
review.

**Pre-filing step, verified on the fork 2026-09-01.** `pr2-expansion` has since advanced
to `6a201fa`, the commit making accent expansion optional (`ZOTEUS_ACCENT_EXPANSION`,
default on). `pr3-droplist-r5` still has `6b7c152` as its parent — the fork's compare
endpoint reads `6a201fa...pr3-droplist-r5` as diverged, one ahead and one behind — so
**PR 3 as it stands does not carry the flag commit**. That was deliberate at the time (it
kept PR 3's stack valid without a rebase) and it is harmless while PR 2 files first and
carries the flag itself. Decide before filing whether PR 3 is restacked onto `6a201fa`;
do not file it describing itself as stacked on the current PR 2 tip, because it is not.

Everything below the rule is the PR body verbatim. Its figures are declared in
`bench/check_figures.py` under the `u0091` key, so a re-measurement cannot leave this
document quoting a superseded number.

That guard reaches this file and stops there. The fork branch's own code comments, its
`docs/` changes and its commit message all reach the maintainer through the diff, and no
gate in this repo can see any of them; figures there are caught by reading, not by a
check. Round 4 read the diff and removed one (a five-run median no committed artifact
backs). Read the diff for figures before pushing it, the same way you read this.

**Round-5 provenance, repo-side, not part of the body.** The three-arm table below
(`query-477k.json`, 2026-08-31) was measured on the pre-expansion tree and under an
earlier fallback threshold; it is kept as the droplist-versus-deletion motivation, and the
body says so where it quotes it. The full stack as it now stands was re-measured
2026-09-01 (`arms-stack-{en,fr,vi,short}.json`), and those are the figures the stack
paragraph quotes. Whether the corpus-measured survivor `not` is an acceptable answer to
the soliloquy (it runs at 27,3% document frequency, under the 30% bar) remains a design
point the author may still rule on; the body presents the shipped rule.

---

## Replace the 29-word stoplist with a droplist measured from the library

### The problem

`tokenize()` carries 29 English function words and drops them from every query and every
document it sees. The list is doing real work — deleting it outright makes keyword search
several times slower on a large library — but it is the wrong shape for the job, in three
separate ways, and only the first is about English.

**It is a language rule applied to a token space that holds every language at once.** The
index does not record which language a passage is in, and it should not have to: German
`die` and English `die` are the same string in `passages_fts`. No per-language list can
drop one and keep the other, because at the point the list is consulted there is nothing
to distinguish them. A user with a bilingual library therefore either loses a content word
or keeps a stopword, and which one depends on a coincidence of spelling.

**It is a guess about frequency rather than a measurement of it.** The words that are
expensive to retrieve on are the words *this* library is saturated with, and that is a
different set for every library. Measured on a 7 541-item library,
`energy` appears in 26,2% of its passages,
more often than several words on the hard-coded list — and dropping
it would be a catastrophic answer to a query about energy. Meanwhile the same library is
saturated with vocabulary the list has never heard of.

**And it is silent about its own cost.** Dropping a term is worth doing because a posting
list is not walked. That is a property of the corpus, not of the word. BM25 already
down-weights common terms continuously and does it better than any cutoff can, so the
justification for a hard cutoff is never ranking quality — it is latency, and latency is
measurable.

### What this changes

The 29-word list is gone. `tokenize()` now folds, splits on non-alphanumerics, and drops
one-character tokens — nothing else, and nothing about any language.

In its place, at the end of a full build, the SQLite backend scans its own term vocabulary
through `fts5vocab` — a virtual table over the index that already exists, so no migration,
no rebuild, nothing new stored — and records the terms appearing in **30% or more** of the
passages. That list is applied **query-side only**, after `tokenize()` and before the
MATCH string is built.

Four details are worth stating because each was a decision:

**Why it is stored rather than computed.** `fts5vocab` is ordered by term, not by document
count, so "which terms exceed 30%" is a full scan of it. On a 477 512-passage library that
scan reads 639 888 terms and costs about 2 020 ms on a first call and 1 774 ms on a
second — both against a page cache the preceding work had already warmed, so read them as
floors rather than as cold-start figures, and an earlier pair on the same machine read
2 281 and 2 013 ms, so read the quantity as *about two seconds* rather than as a constant.
Either way far too slow for query time, and too slow to pay at startup.

Everything else about the answer is small — 23 terms, 75 bytes of text — so it goes in
`meta` beside `schemaVersion`, and the scan happens where a full walk of the corpus is
already being paid for: on that library a build takes minutes, and a couple of seconds is
a percent or so of it.

**Why a delta update does not redo it.** A handful of new items cannot move a 30%
threshold, and this scan is the one cost in the change a user could feel. The passage
count is stored alongside the list, and an update rescans only when it has moved by more
than 10% — or when there is no list at all, which is how an existing index adopts one.

**Why the fallback fires only when nothing survives.** A measured list can hold the
library's own subject words — derived over the English passages of this library alone,
`economics` reaches 35% — so a query it empties can be a real question about what the
library is about, and answering it with silence would look like an empty library. When no
term survives the prune, the raw token set runs instead. While any term survives, the
survivors are the query: they are, by measurement, the words this library can discriminate
on, and an earlier rule that second-guessed them (falling back whenever the prune dropped
more than it kept) put a document saying `in the` sixty times ahead of the one about
brains. Measured on the real library, `the brain` is 3,3 ms pruned against 716,5 ms
unpruned, and the pruned answer is the better of the two.

**Snippets take the list too, at a threshold of their own.** `makeSnippet` centres on the
earliest query term it finds, so without the list a term the corpus is saturated with is
found at character 0 of almost every passage and every snippet becomes the passage's
opening words — which, for a full-text chunk cut at a fixed length, is an arbitrary
mid-word fragment. Measured on the same library over the same twenty queries:
of 91 hits both arms return, **82** begin at the passage opening unpruned and **45** do so pruned, so **37** moved onto the match. One surviving term is enough to anchor a snippet, and with
none surviving the snippet uses the raw set rather than returning an empty window.

The JSON backend gets the same policy from a different place. It already holds exact
document frequencies resident and rebuilds them from the raw passage text on every load,
so it needs no stored list, no cadence rule and no adoption step — the pruning is live by
construction. Documents keep being indexed in full on both backends: pruning the document
side would destroy the frequencies the rule reads and leave the fallback with nothing to
match.

### Measurements

A real 7 541-item library, 477 512 passages, 465 110 of them attachment full text, one
938,8 MiB index.

**Why a droplist at all, and not just deleting the list.** Measured on the pre-expansion
tree (2026-08-31): twenty natural-language queries, each carrying at least three of the 29
words, six passes, warm passes pooled, all three arms against the same file so the page
cache is not a variable.

| arm | p50 | p95 |
|---|---:|---:|
| v1.12.0 as it stands, 29-word list | 222 ms | 392 ms |
| stoplist deleted, nothing pruned | 966 ms | 1 133 ms |
| droplist + degeneracy fallback | 282 ms | 696 ms |

Deleting the list without a replacement costs 3-4x across the board; the droplist keeps
almost all of the deletion's honesty at a fraction of its price. (That run predates the
final fallback threshold; the current stack's own figures follow.)

**The full stack, re-measured (2026-09-01).** The three PRs together — degeneracy fix,
keep-diacritics with query expansion, this droplist — against stock v1.12.0, six warm
passes, arms interleaved query by query. The two arms cannot share a file (stock reads
schema 1; the stack, schema 2), so the latency columns are cross-file — both files hold
the same corpus — while the result columns compare item-key lists, which no file identity
touches.

| query set | stock p50 / p95 | stack p50 / p95 | RBO vs stock | top-1 same |
|---|---:|---:|---:|---:|
| EN (adversarial, stoplist-heavy) | 143 / 264 ms | 187 / 341 ms | 0,916 | 20 of 20 |
| FR | 116 / 275 ms | 112 / 269 ms | 0,886 | 16 of 20 |
| VI | 83 / 228 ms | 64 / 215 ms | 0,692 | 14 of 20 |
| short | 53 / 161 ms | 55 / 172 ms | 0,937 | 18 of 20 |

Three readings. On the English set — built to oversample exactly the words a hand list
catches — the stack pays about 30% at the median and the first result never changes:
top-1 agreement is 20 of 20. On French and Vietnamese the stack is as fast as stock or
faster, and the lower agreement is the intended half of the series, not noise: stock's
folded index merged accented vocabulary onto unaccented strings, and the disagreements
are those collisions coming apart. And `to be or not to be` now keeps the one word of it
under the 30% bar — `not` — and runs on it at ordinary-query cost; the raw-set fallback
is reserved for queries in which nothing survives at all.

**What it costs, stated plainly.** A 30% cutoff is not a superset of the hand-written list.
It catches 19 of the 29 and adds `1`, `2`, `3` and `s`; it leaves `at`, `it`, `its`, `was`,
`we`, `were`, `our`, `their`, `these` and `those`, which are common enough to be expensive
and sit under 30% in this library. Every query in the set whose p50 is more than 50 ms
worse than the current release carries one of them. That is the price of not shipping a
word list, and it is visible here partly because these queries were chosen to carry
stoplist words — a query set built that way oversamples exactly the words a hand list
catches.

### Compatibility

- An index written by an earlier version has no stored list and prunes nothing, exactly as
  today, until its next build or update derives one. Nothing is stranded and no rebuild is
  forced.
- No schema version bump: `meta` takes two new keys, and an older build ignores keys it
  does not know, so a database written here still opens there.
- The `fts5vocab` table is created in `temp` and dropped again, so `sqlite_master` is
  unchanged.
- A derivation that fails for any reason leaves the previous list in force and logs a
  warning; it never fails a build. A corpus under 100 passages, or one where every
  vocabulary term clears the bar, derives an empty list rather than pruning everything.

### Tests

`tests/features/search-droplist.test.ts` covers the prune (including a control arm showing
the same query matching the whole library unpruned), the degenerate query as an identity
against the unfiltered token set, the one-survivor case against a decoy saturated with
common words, backend parity, the pre-existing-index case, adoption on the next build, the
drift bound on delta updates (a small delta keeps the stored list, past 10% it rederives),
the whole-vocabulary guard (an empty list is stored, not the vocabulary), and the snippet
case with and without a list. `npm run typecheck`, `npm run lint` and the full suite are
green.
