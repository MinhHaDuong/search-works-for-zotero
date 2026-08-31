# Upstream PR body — the library-derived droplist (ticket 0091)

Drafted here, sent as written. Branch `t0091-droplist` on the author's fork at `4510bb0`,
one commit atop `b05ed69` (v1.12.0), pushed 2026-08-31. **Not filed**: nothing goes
upstream without the author's authorization. When it is authorized, the PR opens from
`MinhHaDuong:t0091-droplist` against `oscardvs/zoteus` `main`.

Everything below the rule is the PR body verbatim. Its figures are declared in
`bench/check_figures.py` under the `u0091` key, so a re-measurement cannot leave this
document quoting a superseded number — which matters more here than anywhere else in the
repo, because this is the one text with a reader outside it.

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
different set for every library. Measured on a 7 541-item library: `energy` appears in more than
a quarter of its passages, more often than several words on the hard-coded list — and
dropping it would be a catastrophic answer to a query about energy. Meanwhile the same
library is saturated with `zoteus`-shaped domain vocabulary the list has never heard of.

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

Three details are worth stating because each was a decision:

**Why it is stored rather than computed.** `fts5vocab` is ordered by term, not by document
count, so "which terms exceed 30%" is a full scan of it. On a 477 512-passage library that
scan reads 639 888 terms and costs about 2 281 ms on a first call and 2 013 ms on a
second. Far too slow for query time, and too slow to pay at startup. Everything else about
the answer is small — 23 terms, 75 bytes of text — so it goes in `meta` beside
`schemaVersion`, and the scan happens where a full walk of the corpus is already being
paid for. On that library the build costs minutes; this is about 1% on top.

**Why a delta update does not redo it.** A handful of new items cannot move a 30%
threshold, and this scan is the one cost in the change a user could feel. The passage
count is stored alongside the list, and an update rescans only when it has moved by more
than 10% — or when there is no list at all, which is how an existing index adopts one.

**Why the fallback triggers on degeneracy, not on emptiness.** `to be or not to be` keeps
exactly one term at a 30% cutoff — `not`, which sits just under the threshold — so the set
is never empty, an empty-set fallback never fires, and a one-term OR query returns
whatever ordinary prose happens to contain `not`. Measured, that answer overlaps the right
one on 5 items of 35. So when **fewer than two** terms survive the prune, the raw token
set is sent instead.

Snippets take the list too. `makeSnippet` centres on the earliest query term it finds, so
without it a term the corpus is saturated with is found at character 0 of almost every
passage and every snippet becomes the passage's opening words. Its threshold is one
surviving term rather than two: a snippet only needs somewhere to centre, and one content
word is a good anchor.

The JSON backend gets the same policy from a different place. It already holds exact
document frequencies resident and rebuilds them from the raw passage text on every load,
so it needs no stored list, no cadence rule and no adoption step — the pruning is live by
construction. Documents keep being indexed in full on both backends: pruning the document
side would destroy the frequencies the rule reads and leave the fallback with nothing to
match.

### Measurements

A real 7 541-item library, 477 512 passages, 465 110 of them attachment full text, one
938 MB index. Twenty natural-language queries, each carrying at least three of the 29
words, run end-to-end through the MCP server with `mode: "keyword"` and embeddings off;
six passes, warm passes pooled. **All three arms run against the same file**, so the page
cache is not a variable — an earlier attempt with one copy per arm produced differences of
an order of magnitude between two structurally identical files and was discarded.

| arm | p50 | p95 |
|---|---:|---:|
| v1.12.0 as it stands, 29-word list | 222 ms | 392 ms |
| stoplist deleted, nothing pruned | 1 012 ms | 1 151 ms |
| this PR: droplist + degeneracy fallback | 282 ms | 696 ms |

Fidelity against the current release: mean Jaccard 87% over the twenty result sets, no
query emptied.

**Where the p95 goes.** Nineteen of the twenty queries are ordinary; the twentieth is
`to be or not to be`, which is fully degenerate and therefore takes the fallback. Excluding
it, this PR's arm reads **492 ms** p95 — so the tail is the fallback, not the pruning. That
is the fallback working rather than failing: on that query this PR returns exactly the
result set an unfiltered query returns, where the current release overlaps it on 5 items of
35. It is also not tunable by moving the threshold, since the fallback sends the raw token
set at any cutoff.

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
  warning; it never fails a build.

### Tests

`tests/features/search-droplist.test.ts` covers the prune (including a control arm showing
the same query matching the whole library unpruned), the degenerate query as an identity
against the unfiltered token set, backend parity, the pre-existing-index case, adoption on
the next build, and the snippet case with and without a list. `npm run typecheck`,
`npm run lint` and the full suite are green.
