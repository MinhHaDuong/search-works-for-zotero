---
paths:
  - "SPEC.md"
  - "DECISIONS.md"
  - "README.md"
  - "STATE.md"
  - "verification/**"
  - "fork/**"
  - "fork-*/**"
---

# The document set: what an agent must do differently in each

Scoped from `AGENTS.md` § The document set, whose table says what each
document is for. These rules load when you touch the document they govern.

- **`DECISIONS.md` is append-only.** The author's rulings land there FIRST and
  `SPEC.md` is edited to match. Never edit a ratified entry. A narrow exception
  applies to a false factual statement proved by a reproducible measurement or
  authoritative source: stop first and trace the consequences through the
  design, requirements, tickets, evidence, and implementation. Correct the
  fact, propagate only forced factual consequences, and record the evidence
  and consequence analysis in `DECISIONS.md` in the same change, without
  waiting for ratification. Requirements, thresholds, design choices,
  interpretations, mechanism substitutions, and choices among consequences
  are decisions, not factual corrections, and still require the ruling first.
- **`SPEC.md` owns every design number**, and nothing else carries one: gate
  thresholds §5.2.8, the fixture contract's per-cell minima §5.2.10, experiment
  decision rules §5.3, budgets §5.2.9. §2
  Terminology and §6 Security own none and point at the owner instead, and §6
  discloses rather than decides, so closing a gap it names is a ruling in
  `DECISIONS.md` first and a requirement in §3 second. The header date is the
  version; bump it whenever the document changes substantively, and leave
  `Status: DRAFT` until the author himself declares otherwise. SPEC.md speaks
  only of the system: ruling provenance, ticket tracking and process narration
  belong in `DECISIONS.md`, the tickets, and `AGENTS.md`. Handles are
  position-independent and outlive a section's renumbering — R1–R36
  requirements, C1–C4 constraints, D1–D11 resolved decisions, X1–X8
  experiments. Cite a handle on its own; cite a section as `SPEC.md §N.M`.
- **`README.md` tracks deliverables, not the completed design process.** The
  specification owns requirements; README names the formal specification, the
  Multilingual Menagerie and the verification bench, expanding only the two
  unfinished deliverables. It carries no workflow procedure, design ledger,
  threshold, measurement history or per-requirement implementation board.
- **`STATE.md` stays under forty lines and stays pointer-only.** It owns no
  requirement, measurement, verdict, or history.
- **`verification/` is evidence, not authority.** A report is cited by path
  from the ticket it serves and never becomes a source of truth: where it
  touches the design, the owning section of `SPEC.md` is the record. Commit
  reports there rather than leaving them in an agent worktree, because an
  uncommitted artifact dies with the worktree and the report about the work is
  not the work.
- **`fork/` must never contain a `tickets/` directory**, or it shows up in a
  diff sent upstream.
