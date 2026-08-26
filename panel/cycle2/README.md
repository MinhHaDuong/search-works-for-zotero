# panel/cycle2/ — the design-cycle-2 session record

The raw panel documents behind `DESIGN-V2.md` ("The Instrumented Ledger"),
preserved verbatim from the 2026-08-26 run. Cycle 1's equivalents were held in
the session record only and are gone with that session; from cycle 2 on, the
panel record is committed.

**How the cycle ran.** Six lens-architects each re-ran the design against sheet
v2 (DESIGN.md as amended by its ratification log, DESIGN-DELTA.md ratified by
delegation, SCOUTS.md's sharpenings as binding input, SYNC.md as the upstream
ground truth), with the incumbent DESIGN-V1.md as prior art to keep, amend, or
overthrow. Each memo then received an independent adversarial critique. One
synthesis assembled DESIGN-V2.md from what survived plus named repairs. Thirteen
agents in total; every load-bearing code claim was verified against upstream
`oscardvs/zoteus` at HEAD `edf2748` (v1.7.0); disputed numbers were recomputed
from `bench/results/` artifacts.

| lens | memo | critique | critique verdict |
|---|---|---|---|
| derivation & freshness | `design-derivation.md` | `critique-derivation.md` | 1 FATAL / 3 MAJOR / 5 MINOR |
| corpus & the entry ruling | `design-corpus.md` | `critique-corpus.md` | 1 FATAL / 5 MAJOR / 6 MINOR |
| privacy & lifecycle | `design-custody.md` | `critique-custody.md` | 1 FATAL / 5 MAJOR / 5 MINOR |
| multi-library & concurrency | `design-concurrency.md` | `critique-concurrency.md` | 2 FATAL / 5 MAJOR / 4 MINOR |
| query & ranking | `design-query.md` | `critique-query.md` | 0 FATAL / 4 MAJOR / 5 MINOR |
| operator & gates | `design-operator.md` | `critique-operator.md` | 1 FATAL / 4 MAJOR / 6 MINOR |

**How to read these.** The memos are inputs, not conclusions: several of their
design points were killed or repaired by their critiques, and the critiques
themselves were arbitrated in the synthesis (two of their disputes were settled
by recomputing the artifacts — the golden-floor and version-0 numbers in
DESIGN-V2's header). Where a memo and DESIGN-V2.md disagree, DESIGN-V2.md is
the record; §1 of DESIGN-V2 names what died and what killed it, and §3 lists
what was rejected this cycle. Nothing in this directory is authoritative on its
own.
