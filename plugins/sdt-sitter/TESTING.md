# Testing the sitter: the ladder

A build climbs these rungs in order, and a failure stops the climb. Every rung
below the last runs outside the author's Zotero. The ruling is `DECISIONS.md`
2026-09-23; the tracker is ticket 0815.

| Rung | Library | Runs on | Instrument |
|---|---|---|---|
| 1. Unit | none | every commit | `make check` |
| 2. Smoke | three Menagerie documents, clean room | every change | `bench/sitter_smoke_test.py` |
| 3. Menagerie | the whole Menagerie, clean room | every build meant for the author | `bench/sitter_acceptance.py`, widened by 0817 |
| 4. Clone | a reflink copy of the author's library | every live install | 0818 |
| 5. Dogfood | the author's own Zotero | before any release | the author |

**Clean room** means a fresh profile and a throwaway data directory, with the
run's own log confirming Zotero opened that directory and not the author's.

**Integrity, from rung 2 up.** The sitter promises to change the SDT cache and
nothing else. Each rung compares the library before and after — every table of
`zotero.sqlite` by row content, every file under `storage/` by hash — and
fails on any difference outside the permitted set: the `.zotero-sdt-cache`
packs Zotero writes when the sitter calls `Zotero.SDT.ensure()`, and the
sitter's own `sdt-sitter-cache.jsonl`. Where the scenario itself edits the
library, the difference must be exactly those edits. Ticket 0816 builds the
check and shows it red on a build that breaks the promise.

**Rung 3 is the whole Menagerie, wild documents included.** The corpus is
where the extremes belong — the plates volume and the 3 666-page EIS arrive
through ticket 0794 — so size and wildness are one rung, not two. The behaviour
scenario runs over it, and lifecycle is part of that scenario rather than a
rung of its own: pause (including mid-document), the attachment and item
invalidation cycles, replace, disable and re-enable, restart, uninstall.

**Rung 5 comes before release.** The author installs on his live Zotero only
after rung 4 passes, with a reflink snapshot of the data directory taken first,
and a build is released only after he has used it himself.

**The bar** for rung 3 and above reads the author's values — Excellence,
Integrity, Care — as measured criteria: every eligible attachment ends with a
pack or a named reason, a pass repeats, the interface stays responsive, the
status tells the truth. Ticket 0819 measures and proposes the numbers;
`SPEC.md` will own them once ratified.
