# Upstream PR body — the degenerate query (series 1/3, ticket 0091)

Drafted here, sent as written. Branch `pr1-degenerate-r3` on the author's fork at
`47461b7`, one commit atop `b05ed69` (v1.12.0), pushed 2026-09-01. **Not filed**: nothing
goes upstream without the author's authorization. When it is authorized, the PR opens
from a cleanly named fork branch at the same commit against `oscardvs/zoteus` `main`.

Gates re-verified on the exact commit before drafting this body, 2026-09-01: typecheck,
lint, and the full suite — 939 tests passed, 7 skipped.

Its figures are declared in `bench/check_figures.py` under the `u0091a` key, so a
re-measurement cannot leave this document quoting a superseded number. The guard reaches
this file and stops there: the fork branch's code comments, its `docs/` changes and its
commit message all reach the maintainer through the diff, and no gate here can see them —
read the diff for figures before pushing, the same way you read this.

---

## Answer a query of common words on what the user typed

### The problem

`to be or not to be` returns a confidently-ranked page of results about nothing.
Twenty-nine English function words are dropped from every query, and every word of that
line is on the list except `not` — so the search that actually runs is a single-term OR
on a word that appears in a quarter of an academic library's passages, and what comes
back is whatever prose happens to contain it. Not an empty result, which would at least
be honest: a wrong one, with no way for the user to tell.

### What this changes

Two changes, and the second is smaller than it looks.

**`not` joins the list.** It is added alone and deliberately: the list omits plenty of
other common words — `no`, `but`, `which`, `when` — but which of them matter is a
property of the corpus rather than of English, and guessing further here is a habit this
list should be losing. With `not` on it, the line prunes to nothing rather than to one
meaningless term.

**A query that prunes to nothing runs as typed, if it was a phrase.** One or two common
words are not a question — `the`, `of the` — and search has always answered those with
nothing, instantly; the fold makes that path reachable from real words in other
languages, since `thé` is French for tea and lands on `the`. Three or more are a phrase,
and a phrase the user typed is worth running.

**The rule never fires while anything survives, and that restraint is the whole design.**
An earlier version fell back whenever the prune dropped more terms than it kept. That
sounds careful and is not: `in the brain` keeps one content word, drops two common ones,
and would have run unpruned — putting a document that says `in the` sixty times ahead of
the one about brains. That is the same defect arriving from the other direction, on a far
more ordinary query than the one being fixed. Nothing distinguishes an accidental
survivor like `not` from a real one like `brain` except how common each is, and a fixed
list cannot know that. So it must not guess: if a term survived, it is the query.

**The list also comes off the document side.** `tokenize()` was both the in-memory
backend's document tokenizer and its query tokenizer, so the list was deleting these
terms from that index — and a term that is not indexed cannot be matched even
deliberately: the phrase fallback would have had nothing to find. Both backends now index
every term, and only queries prune. On the SQLite backend nothing changes there: FTS5
tokenizes the document side itself and always held these terms. One visible consequence,
stated because "results are unchanged" would be false: on the in-memory backend
`doc.length` and `avgdl` now count common words, so BM25's length normalization shifts —
toward FTS5, which has always counted every token, so the two backends' scoring
converges rather than diverging. `Doc.tokens`, a per-document array of every token that
nothing in the tree ever read, is removed in the same commit as dead code.

### Measured

On a real 477 512-passage library, against this same build with the change reverted:
every ordinary query returns the same documents in the same order — `the brain`, `in the
brain`, `on the moon`, `is it a bird`, `of energy`, and a French query made only of
French function words. `the`, `thé` and `of the` still cost 0 ms and return nothing.
Only the soliloquy differs, which is the contract: it now runs as the phrase the user
typed.

### Tests

`tests/features/search-degenerate-query.test.ts` asserts the defect before asserting the
fix — with the list as it shipped, the line prunes to the single term `not` — and pins
the property the design rests on: a query with one content word stays pruned however many
common words surround it, with a fixture item that would outrank the real answer if it
did not.
