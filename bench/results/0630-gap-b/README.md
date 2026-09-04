# Gap B — does the drafted removal procedure actually leave zero residue?

Ticket 0630, a child of tracker 0613 (goal 1). `verification/UNINSTALL-DRAFT-0630.md`
and `tests/test_uninstall_doc.py` existed before this directory; neither had
ever been checked against a real installed target. `tests/test_uninstall_doc.py`
reads the draft's PROSE and confirms it names the right symbol
(`ZOTEUS_DATA_DIR`) and mentions the model cache — a text assertion, not a
removal. This directory is the missing red-then-green: a real `fork/` build,
a real index, a real downloaded model, one incomplete delete that the residue
sweep catches, and the real procedure that clears it.

**Finding: yes, on this run.** `bench/probe_uninstall_procedure.py` →
`uninstall-e2e.json`. Deleting exactly `target.declaration.derived_state_roots`
— the same one root the draft's step 3 names — leaves zero files behind, and
a deliberately incomplete delete (withholding the model-cache subdirectory,
the pre-#27 failure the draft's own worked example describes) is caught by
the same survivor sweep first. Both halves ran in the same arena, on the
same materialized state, so the green is a green against the exact residue
the red demonstrated the sweep could see.

This is an **ungraded diagnostic**, the same status `bench/results/0629-gap-a/`
carries for gap A. `R15-uninstall-removes-declared-state`'s verdict for
zoteus is unchanged: still `not-offered`, because the adapter's `uninstall()`
still raises `UnsupportedVerb` (`bench/acceptance/adapters/zoteus.py`) — this
script does not call it and does not change that. What it answers is
narrower: *if* the harness executes the published procedure's declared paths
the way the 2026-09-03 ruling permits, does the result the residue check
would read come out clean. It does.

## What ran

Real `fork/` checked out fresh at the reviewed SHA
(`b0e0bc872b5727d21ea83aba8bfe834293013264`, v1.13.0 — `make upstream-checkout`,
then `npm install && npm run build`, so this run carries no staleness caveat).
The on-device embedder resolved through the standalone
`@huggingface/transformers` install at `~/.zoteus-deps/node_modules`, per the
`project-live-smoke-recipe` memory. The target process ran under the
dedicated `tester` account (`--posture account`, ticket 0625), reaching this
operator's real, resident local Zotero library over the loopback API — the
identity boundary is about the target's own writes, not about network
reachability, and a local API on `127.0.0.1` answers any local user
regardless of which one asked. `zotero_index` built with `limit:1` against
that library (7 546 items available, 1 indexed): a 1-item build writes to
every path a full build would, which is what R15 asks about — whether every
location that received a write survives a correct delete, not how many items
it holds.

**The arena needed a write grant this repo's Makefile recipe does not
provide.** `ACCEPTANCE_ARENA`'s documented recipe makes the top-level arena
`tester`-owned so the target can write and the operator can read
(`Makefile`, `posture.py`'s module docstring: "write on nothing but the
arena"). This run also asked the *operator's own process* to delete files
afterward — the harness-does-the-deleting design the 2026-09-03T12:48Z
safety correction in tracker 0613's log asks for — which a bare `tester`-owned
755 directory refuses (`other` gets `r-x`, no `w`). Fixed with a POSIX ACL
granted by `tester` on its own directory, the same primitive the library
grant already uses in the other direction:

```sh
sudo -n -u tester mkdir -p "$ARENA"
sudo -n -u tester setfacl   -m u:haduong:rwx "$ARENA"
sudo -n -u tester setfacl -d -m u:haduong:rwx "$ARENA"
```

Scoped to this run's own arena subdirectory, not `ACCEPTANCE_ARENA` itself,
and not committed to the Makefile recipe — this script is a diagnostic, not
a new standing requirement, and folding it into the provisioning recipe is a
call for whoever owns that file next, not this ticket.

**Ticket 0633 (gap A's `sandbox.py`/`sudo` composition bug) does not apply
here.** That ticket found `--posture account` unusable *inside* the
`podman-unshare` fallback `sandbox.choose()` picks when `bwrap` cannot start
(`sudo` cannot function inside any rootless user namespace by construction).
This script never composes the two: it builds the adapter and calls
`target.running()` directly, in-process, and never imports
`bench.acceptance.sandbox` — `Posture.wrap()`'s `sudo -n -u tester -- …` runs
as an ordinary subprocess of the (unsandboxed) harness process, which is
exactly the path that worked. Only `bench/acceptance/run.py`'s `--drive`
subprocess, used by the R10 egress assertion, nests posture inside the
sandbox; this diagnostic's own posture usage was never at risk from it.

## The removal itself, and how it stayed off a shell

`_delete_paths()` in `bench/probe_uninstall_procedure.py` takes a list of
`Path` objects and calls `shutil.rmtree`/`Path.unlink` on exactly them. The
paths it is handed come from `target.declaration.derived_state_roots` — the
adapter's own declared list, read once, in Python — never from parsing the
draft's fenced shell commands. That mirrors the ruling by construction rather
than by care: there is no code path in this script that turns the draft's
prose into anything executable.

## Red, then green, on the same materialized state

| step | what happened | survivors under the declared root |
|---|---|---|
| after install + 1-item build | 8 files: 4 under `models/Xenova/all-MiniLM-L6-v2/` (`config.json`, `tokenizer.json`, `tokenizer_config.json`, `onnx/model.onnx`), 3 index files (`search-index.sqlite`, `-shm`, `-wal`), 1 `update-check.json` | 8 |
| **negative control** — delete everything except `models/`, once | the model cache directory withheld on purpose | **4** (every file under `models/`) — caught |
| **real procedure** — delete the declared root itself | `shutil.rmtree(data_dir)` | **0** |

The negative control is not a hypothetical: it is the pre-#27 case the draft's
own worked example names, reproduced deliberately rather than argued about.
`verdict.positive_control_fired: true` and `verdict.residue_after_real_procedure: 0`
in `uninstall-e2e.json` are what `probe_uninstall_procedure.py`'s exit code
gates on; the script exits 1 if either fails, so a future re-run that stops
catching the partial delete — or stops clearing the full one — fails loudly
rather than needing to be read by eye.

**Arena-wide, not just declared-root.** `arena_residue_after_full_delete` in
the artifact is the same before/after `Snapshot` comparison
`check_residue_inventory` makes, applied across the whole install → build →
delete cycle rather than only across install: zero, meaning nothing this run
created anywhere in the harness-owned arena survives the real procedure —
stronger than "the one declared root is empty," which alone would not catch
a stray file the target wrote beside it.

## What this does not establish

- **Not a re-grade of `R15-uninstall-removes-declared-state`.** That clause's
  `not-offered` verdict is about whether the target *offers* a callable
  `uninstall`, which it still does not; this script never calls
  `target.uninstall()` and never will, since the adapter raises
  `UnsupportedVerb` by design (`SPEC.md` §5.2.7's stance on not substituting a
  maintenance verb).
- **Not a resolution of the TMPDIR/XDG precondition.** `zoteus.py`'s `_env()`
  still redirects only `ZOTEUS_*` variables (ticket 0630's log, re-measured
  2026-09-03), merged onto the operator's full `os.environ` — this run's
  target process ran with the operator's own `HOME` in its environment,
  unchanged from that finding. Nothing in this run surfaced a *leak* traceable
  to it: no file appeared outside the arena, and no operation failed against
  `$HOME`. That is expected rather than reassuring — an arena-relative sweep
  cannot see a write outside the arena by construction (the same limitation
  `check_model_cache_under_declared_roots`'s docstring states about itself),
  so this run neither confirms nor further narrows that gap; it stays exactly
  as open as ticket 0630 already recorded it.
- **One item, one run, one machine.** A 1-item build exercises every path a
  full build writes to, but not e.g. two concurrent builds or a build large
  enough to hit a different code path. Not this ticket's question.

## Reproducing

```sh
sudo -n -u tester mkdir -p "$ARENA"
sudo -n -u tester setfacl   -m u:$(whoami):rwx "$ARENA"
sudo -n -u tester setfacl -d -m u:$(whoami):rwx "$ARENA"
python3 bench/probe_uninstall_procedure.py \
  --entrypoint fork/dist/index.js \
  --transformers-path ~/.zoteus-deps/node_modules \
  --arena "$ARENA" --posture account --build-limit 1 \
  --output bench/results/0630-gap-b/uninstall-e2e.json
```

Needs a built `fork/` at the reviewed SHA (`make upstream-checkout`, then
`npm install && npm run build` inside it), the `tester` account and sudoers
rule from the `Makefile`'s `ACCEPTANCE_ARENA` recipe (ticket 0625), and a
resident Zotero desktop reachable on the local API (any real library works;
the script asks for one item).
