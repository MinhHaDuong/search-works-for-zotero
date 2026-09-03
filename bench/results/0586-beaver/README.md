# Ticket 0586 — the Beaver adapter's measurements

Target: `jlegewie/beaver-zotero`, release **v0.23.3**, commit
`bec71e141413a1a6d6ab80697e398feed8d45f4d`, installed from the release artifact
`beaver.xpi` (7 107 803 bytes, sha256
`e4846067f1d1d400d19893a9fb821aa6ea41999e072e822f951125ce2974915d`), in its
shipped default configuration, **with no account and no credentials**. Run on
padme, Zotero 10.0.1 build 20260824184709, display `:1`, isolation
`podman unshare unshare -n`, tracer `strace -f -e trace=network`.

## `acceptance.json` — the verdict

The target-neutral layer against this adapter: **1 pass, 2 fail, 2 not-offered,
0 not-run**. `R15-uninstall-removes-declared-state` fails with `beaver.sqlite`
and `beaver.sqlite-wal` surviving; `R10-no-egress` fails on 60 name lookups
under isolation. Read the second one against the destination cells below before
concluding anything about the product: the host application alone already fails
that clause on this machine.

`R15-residue-inventory` passes having compared **1143 created files** against
the declaration — the number matters, because a residue sweep that saw nothing
would report the same green. What absorbed those 1143 is three
`not_derived_state` entries for the host's own directories, and each entry
states what exempting it costs.

## `acceptance-prefix-control.json` — the false green, measured

The identical run against the identical product, with the one-branch fix to
`Snapshot.of` removed: `R15-uninstall-removes-declared-state` reports **`pass`**
with `survivor_count: 0`, while `beaver.sqlite` (32 768 bytes) and
`beaver.sqlite-wal` (2 295 472 bytes) sit in the directory the check had just
swept. `os.walk` yields nothing for a regular file, and every declared root of
the first two targets is a directory, so nothing on the roster could see it
before a target that keeps its state in files beside its host's.

Note what the summary line does: **2 pass, 1 fail** rather than 1 and 2. A fix
that turns a green into a red is the only kind whose absence is invisible.

## `control-arms.json` — the reds

Sixteen planted defects, each run against the committed tree, each required to
turn one guard red: **16/16**. A guard never seen red is a habit.

## `destinations-*.json` — the observation, not a verdict

Inside a namespace with no route every hostname dies at resolution, so the
tracer sees one loopback stub resolver and a destination has no name. These
cells read the other arm, where addresses are real. They assert nothing.

| cell | arm | off_machine | dns |
|---|---|---|---|
| `with-plugin-isolated` | isolated | 0 | **430** |
| `host-only-isolated` | isolated | 0 | **426** |
| `with-plugin-shared` | route intact | 261 | 42 |
| `host-only-shared` | route intact | 446 | 82 |

The two isolated cells are the controlled A/B: identical profile shape, identical
90-second window, virgin profile in both, the **only** difference being the
pinned artifact in `profile/extensions`. The plugin adds **4** name lookups to
the host's 426 — and under isolation neither cell can say to whom.

The shared cells can. Destinations present with the plugin and absent without it:

- `185.199.108.133`, `.109.133`, `.110.133`, `.111.133` — exactly the four
  addresses `objects.githubusercontent.com` resolves to — and `140.82.121.4`
  (`lb-…-fra.github.com`). This is the add-on's own `update_url`
  (`manifest.json`), polled by the **host application** because the plugin is
  installed. Egress caused by the target and performed by its host.
- `172.64.149.23` and `104.18.38.233` — the same Cloudflare /24s that
  `xxvxklysvpobontwhwoz.supabase.co`, the Supabase project the shipped bundle is
  compiled against, resolves to (`172.64.149.246`, `104.18.38.10`). Cloudflare
  is anycast and rotates within a prefix, so this is **consistent with** that
  destination and is not proof of it.
- `13.33.153.35:443` (67 attempts, CloudFront) and two AWS EC2 addresses.

What is **absent** is as much of the finding: `api.beaverapp.ai` resolves to
`172.217.16.243`, and no address in that range appears in the with-plugin cell.
That agrees with what the source establishes — every backend call passes
`getAuthHeaders`, which throws before `fetch` when there is no session
(`packages/agent-core/src/transport/apiService.ts:281-290`). The disclosed
remote processing is not exercised here because there is nothing to exercise it
with, which is exactly why the clauses that need it are recorded as unreachable
rather than as passed.

## An open question this lane did not settle

The acceptance layer's own subject arm counts **60** name lookups where an
otherwise-matched raw launch counts **430**. Two hypotheses were tested by
intervention and both failed:

- *the host stalled on an unread pipe* — `destinations-with-plugin-isolated-via-drive.json`
  (60) versus `-via-drive-drained.json` (60, after the lifecycle began draining
  the host's output). The fix is right on its own merits; it was not the cause.
- *the window was shorter* — `destinations-with-plugin-isolated-78s.json`: 430
  at 78 seconds, the same as at 90.
- *the host ran in a session of its own* — `destinations-with-plugin-isolated-setsid.json`:
  430 with `setsid`.

A timestamped trace of the raw cell puts all 430 attempts inside the first 70
seconds (274 of them in the first 10), so no late burst explains it either. The
one experiment that would settle it: trace both regimes with `strace -f -tt` and
compare the arrival profiles and the number of host content processes each
spawns. Until then this is an observation, not a residual to attribute.

## Cited, not re-derived

The host-only R10 baseline measured by the ladder lane lead —
`bench/results/r10-host-baseline/hostbase.json`, driver
`bench/r10_host_baseline.py` (pending in PR #234 at the time of writing) — reads
426 name lookups on a virgin isolated profile. The `host-only-isolated` cell
here reproduces that number **to the digit** on an independently prepared
profile, which is what makes the +4 above readable as a difference rather than
as noise.
