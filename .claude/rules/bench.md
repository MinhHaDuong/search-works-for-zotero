---
paths:
  - "bench/**"
  - "verification/probes/**"
  - "requirements-check.txt"
  - "requirements-drivers.txt"
---

# The measurement harness

Scoped from `AGENTS.md` § Conventions and § Environment notes; loads when you
touch `bench/`, the probes, or the dependency declarations.

- **Two dependency sets.** `requirements-check.txt` is what the gate needs to
  run at all (`ruff`, `pytest`, `numpy`); `requirements-drivers.txt` is what a
  measurement driver needs on top, so nobody installs a model runtime to run a
  lint gate. `bench/check_deps.py` runs FIRST in `make check` and names a
  missing package before any guard prints, so a failure cannot hide in the
  tail of a green-looking run.
- **One model name, one place:** `bench/models.json`. Every driver names a
  model by registry id and resolves it — with its `pooling` mode and its
  `input_template` prefixes — through `bench/registry.mjs` or
  `bench/registry.py`, which also decide whether the run wants the ONNX mirror
  or the author's own repository. Adding a model means adding a record.
  `bench/check_models.py` fails on a model id, a pooling mode, or a declared
  input template written literally anywhere else under `bench/`, and on a
  candidate missing the `pooling` / `pooling_source` pair. Read pooling off the
  model's own `1_Pooling/config.json` and never infer it from a sibling: a
  wrong pooling degrades retrieval silently, so it reads as the model being
  worse rather than as a bug.
- **Throwaway probe state gets a lifecycle before it gets a path.** The
  acceptance runner allocates a fresh arena per run under
  `$ACCEPTANCE_ARENA/<date>/<time>-<check>` and, since ticket 0720, keeps
  only the three most recent runs per base. Nothing else under `~/data`
  is ever swept: not by version control, not by the `/tmp` wipe at
  reboot, not by the job directory's deletion. So a hand-made directory
  beside the run layout (`seed/`, `ladder/`, `r23-iso/`: five of them
  from one afternoon on 2026-09-03, 613 MB, each carrying its own copy of
  the model weights) is invisible to every cleanup that exists, and a
  subagent's report naming it dies with `/tmp`. Put an ad-hoc probe under
  a job's `tmp/` (deleted with the job), or under the run layout so
  retention bounds it; when a probe must live beside the arena, name it
  in the ticket or verification note that consumes it, with a line saying
  when it can go.
- Zotero's local API cannot request extraction, and Zotero 10 has no bulk
  reindex button, so the author's Zotero carries a small plugin of ours,
  `bench/zotero-fulltext-plugin/`: two endpoints on Zotero's own server that
  reindex named attachments in full and report their state; the client is
  `bench/zotero_fulltext.py`. Group-library items answer only under the group
  path of the local API (`/api/groups/<id>/…`), and the plugin resolves keys
  across libraries so callers need not know which. The page cap was lifted
  and the X5 arm documents re-extracted in full on 2026-09-02 (ticket 0025's
  log); every other cache still holds at most 100 pages, so census numbers
  measured before that date stand.
- The measurement corpora are NOT in this repo: real vectors, the 477k index,
  and the 44,9 MB extraction live on the author's machine, and `bench/results/`
  holds committed JSON summaries. Ticket 0025's substrate map says which
  experiments run where.
