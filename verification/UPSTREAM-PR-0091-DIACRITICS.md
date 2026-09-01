# Upstream PR body — keep diacritics (series 2/3, ticket 0091)

Drafted here, to be sent as written once the author grants the slot (one slot per PR,
ruling of 2026-09-01). Branch `pr2-expansion` on the author's fork at `6b7c152`, three
commits stacked on `pr1-degenerate-r3` (`47461b7`) atop `b05ed69` (v1.12.0). **Not
filed.**

The design was decided by measurement, per the same day's ruling: the dual-token
alternative (`pr2-diacritics-r3`, `f80d860`, index the stripped form beside the written
one) was built and reviewed first, the query-expansion alternative was then built and
both were measured over copies of the same 477 512-passage index, each migrated by its
own code. Expansion won on every axis; the table below is the decision record, and the
artifacts under `bench/results/0091-droplist/` (`arms-expansion-*.json`,
`expansion-penalties.json`, `expansion-reach.json`, `expansion-migration.json`) are the
evidence. Gates on the exact commit (`6b7c152`, after a three-seat review round whose
fixes are the branch's third commit): typecheck, lint, 954 tests passed, 7 skipped.

## The two measured designs

Both keep the index at `remove_diacritics 0` and answer an accented query exactly; they
differ in how an unaccented query still reaches accented documents.

| | dual-token (`pr2-diacritics-r3`) | expansion (`pr2-expansion`) |
|---|---|---|
| mechanism | index the mark-stripped form beside each accented word | expand the query term to the accented spellings the vocabulary holds |
| BM25 length penalty on accented docs (controlled pair) | **23,5 %** | 0 % (= stock control) |
| document *about* `théorie` vs one mentioning `theorie` once, query `theorie` | ranked **last** (1,30 vs 1,59) | ranked first (3,13 vs 2,86), as stock |
| `avgdl` shift on an unrelated document when accent-heavy filler joins | +38,8 % (control arm: +34,9 %, so **+3,9 points** attributable) | +34,9 % (= control: **0 points** attributable) |
| top-1 agreement with stock, EN / FR / VI / short (20 queries each) | 19 / 16 / 14 / 19 | 19 / 17 / 12 / 20 |
| rank-biased overlap with stock, EN / FR / VI / short | 0,939 / 0,886 / 0,692 / 0,977 | 0,944 / 0,902 / 0,675 / 0,992 |
| schema 1 → 2 migration, 477 512 passages | 116,4 s | **43,5 s** |
| pinned Unicode mark-joining set (944 codepoints) | required — extra tokens must reproduce unicode61's joining | not needed — expansion terms come from the vocabulary itself, post-tokenizer |
| per-query cost | none | variants lookup, mean 0,02–0,06 ms, max 0,18 ms per query set |
| derived state | none | `accent_variants` map, 43 139 variant pairs at first derivation, one ~6,7 s vocabulary scan on the droplist cadence |

Latency columns are cross-file by construction (the designs differ in what the file
holds); the agreement columns are cache-independent. p50/p95 over the EN set, two runs:
stock 144,6–145,0 / 262,9–265,2 ms; dual-token 141,8–142,3 / 513,5–515,8 ms; expansion
139,2–139,5 / 485,0–486,8 ms — the elevated p95 on both candidates is the one degenerate
query's PR-1 fallback, not this change.

**The gate was itself forced by measurement.** Ungated expansion read well in fixtures
and failed on the corpus: every rare accented sibling of a common word joins the query at
a high idf — `trong` (25 771 passages) dragged in `trọng` and `trồng`, `le` dragged in
nine Vietnamese words, OCR's `enêrgy` outranked real hits for `energy` — and top-1
agreement fell to 15/12/10/10 of 20 across the four sets
(`arms-expansion-ungated-*.json`). The dominance gate (expand only where the accented
spellings outweigh the typed one, by document frequency) removed every one of those
cases and is corpus-derived, with no threshold to tune: `theorie` (214 as typed against
955 accented) expands, `trong` (25 771 against 7 027) runs as typed.

**Reach, verified on the real index** (`expansion-reach.json`): ten unaccented FR/VI
queries (`theorie generale`, `nang luong tai tao`, `developpement durable`, …) return
top-10s in which 5 to 10 of 10 items carry the accented spelling. `thé` returns 13 hits
where stock returns none (it folded to `the` and was stoplisted) — the fix working. PR 1
degenerate cases are coherent: `the` and `of the` still cost 0 ms and return nothing.

**One point the checkpoint's open question got wrong, settled by evidence**: expansion
does *not* avoid the migration. The tokenizer declaration changes under either design,
so the FTS table must be rebuilt and the stamp must move to 2 — a stock build sidelines a
schema-2 file either way. What expansion avoids is the dual-token rebuild's cost (43,5 s
against 116,4 s) and the 944-codepoint blocker; the migration-failure blocker (B3) is
therefore not moot and is fixed on this branch instead: a non-corruption failure now
leaves the file untouched at its old stamp and refuses with the reason, and only
corruption still sidelines (red-first test in `search-schema-migration.test.ts`).

---

## Keep diacritics in the keyword index; expand unaccented queries instead

### The problem

The keyword index strips diacritics from every token on both sides
(`remove_diacritics 2` plus a matching JS fold), and in a library that holds more than
one language that does not normalize spelling — it merges vocabulary. Measured on a real
477 512-passage EN/FR/VI library: Vietnamese `án` lands on English `an`, `bé` on `be`,
`thể` and `thế` on `the`. A tone mark in Vietnamese is part of the word, not an accent on
it — `ma má mà mả mã mạ` are six words — and once merged into a token that common they
cannot be searched for at all. `thé` (French for tea) folds onto `the` and is stoplisted
into silence.

### What this changes

**Each word is indexed exactly as written.** The FTS5 table is declared
`remove_diacritics 0`, nothing strips marks on the way in, and an accented query is
answered exactly: `năm` (year) no longer returns documents about a river called Nam.

**An unaccented query still reaches accented documents, by expanding the query rather
than the index.** `theorie` runs as `("theorie" OR "théorie")`: the accented spellings
come from a small folded-form → spellings map (`accent_variants`) each backend derives
from its own vocabulary — derived state on the same cadence as the binary vector codes,
refreshed when a build finishes or the passage count drifts past ~10 %. Because nothing
extra is indexed, document length, term frequency and idf are what the text says they
are; the alternative (indexing the stripped form beside the written one) was built and
measured first, and it charges every accented document about a fifth of its BM25 score
on every query and can rank a document *about* `théorie` below one mentioning `theorie`
in passing — a change motivated by Vietnamese must not demote Vietnamese documents.

**Expansion is dominance-gated, in one direction only.** A term expands only when the
accented spellings outweigh the typed one in this library (document frequency, compared
at derivation): `theorie` expands, `trong` — a Vietnamese function word held 25 771
times as typed — does not get dragged toward its rarer accented siblings, whose high idf
would otherwise outrank what the user typed. An accented term never expands toward its
stripped form: that is the merge this change exists to end. The gate is corpus-derived;
there is no threshold to tune.

**Existing indexes are migrated in place, and a failed migration no longer destroys an
intact one.** Schema 1 → 2 rides the migration ladder: the keyword table is re-tokenized
(43,5 s on 477 512 passages), no vectors are re-computed, nothing re-reads Zotero. On
the same path, a rung that fails for a transient reason — a full disk, a size limit —
used to be treated exactly like a foreign schema: the database was moved aside and a
fresh empty one silently took its place. Now only corruption sidelines; anything else
leaves the file at its old stamp and search refuses with the reason, retrying on the
next open.

### Measured

On copies of the same real 477 512-passage index, arms interleaved query by query,
warm-up discarded, six passes: top-1 agreement with stock is 19/20 (EN), 17/20 (FR),
12/20 (VI), 20/20 (short queries) — the divergences are the exactness the change is for.
A controlled accented/unaccented document pair scores identically (the dual-token
design penalizes the accented one 23,5 %). Ten unaccented FR/VI probe queries return
top-10s in which 5–10 of 10 items carry the accented spelling. Per-query expansion cost:
a variants lookup of 0,02–0,06 ms mean, 0,18 ms max.

### Tests

`accent-folding.test.ts` asserts the asymmetry on both backends — accented queries
exact, unaccented queries reaching accented documents through expansion, and the
dominance gate from both sides (a corpus that predominantly writes `năm` expands a `nam`
query; one that predominantly writes `nam` does not). `search-schema-migration.test.ts`
pins the rung (documents, vectors and embedder calls preserved; the re-indexed text
answers with the new tokenizer) and the refusal: a rung failing with a transient error
leaves the file at its old stamp, unsidelined, and the retry succeeds; the same failure
wearing a corruption sentence still sidelines.
