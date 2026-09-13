# SDT pack sitter 0.4.0 — pre-release test pass

Run 2026-09-13 on padme, against `worktree-t0754-610217` at the tip of `main`
plus the one bench fix recorded below. Every figure here is from a run made
during this pass; nothing is quoted from an earlier report without saying so.

## Verdict

The mechanical gates are green and one new experiment was run. Neither
establishes that the sitter is safe to publish, and this report does not say it
is. What the gates establish is that the tree is internally consistent; what the
new experiment establishes is one bounded negative, stated below in the only
terms it supports.

## Gates

| Gate | Result |
|---|---|
| `make check` (deps, lint, figures, models, names, progress, tickets, ticket-logs, sitter-version, sitter-mutants, check-fast) | exit 0 |
| `python3 -m pytest tests/ -q` | 1392 passed, 0 failed, 15 skipped |
| `bench/check_sitter_version.py` | OK, version 0.3.48 across 117 revisions; rule 3 read 6 open pull-request heads, none claiming that version over a different payload |
| `verification/probes/sdt_sitter_bootstrap_mutants.py` | 53/53 mutants caught |
| `verification/probes/sdt_sitter_scheduler_mutants.py` | 19/19 mutants caught |
| `bench/check_ticket_logs.py` | OK, 1937 entries across 339 tickets |

One note on the version gate's third rule, because a NOT-RUN there is invisible:
it ran. It reached the forge and read six open pull-request heads. A parallel
lane reported the same leg returning HTTP 403 in its own worktree during this
same session; the difference is unexplained and is not investigated here. Ticket
0780 owns that leg.

## Arm 6 — the first volume arm with a live sitter

Ticket 0727. This is the experiment ticket 0778 asked for: arm 5 cycled an
add-on that, headless, could never pass `initialize()`'s main-window check, so
its 17 clean cycles measured Zotero's add-on bookkeeping rather than a running
plugin. Arm 6 was run against a real X display so the plugin could arm.

**Setup.** `DISPLAY=:1`, not headless. Zotero 10.0.1 from
`~/.local/Zotero_linux-x86_64`. A throwaway profile. The Menagerie imported
first — 114 attachments named in the RIS, 114 present on disk — so the sitter
had real work in front of it. 8 burst cycles at 8 s, then spaced cycles at
120 s. Each cycle is a replace, a disable held 6 s, and an enable.

**Liveness, which is the whole point of this arm.** The rig's own read, one
minute in:

    {'ok': True, 'dataDir': '/home/haduong/Zotero', 'mainWindows': 1,
     'handle': True, 'phase': 'extracting', 'scanned': 114, 'total': 114,
     'cacheWritten': True}

The sitter armed, completed its census over all 114 attachments, wrote its
cache, and was in `extracting` when the cycling began. Arm 5 had none of this.

**Result.** 24 cycles over 36 minutes, zero disappearances. The disabled-state
positive control fired on every cycle — the log carries an `active=False` line
and then an `active=True` line for each — where arm 5's log carried no
`active=False` line at all despite 17 deliberate disable calls.

**What this supports, and only this.** Twenty-four rapid replace-disable-enable
cycles did not kill a live, extracting sitter over a 114-attachment library, in
a process that was never restarted, on Zotero 10.0.1, on one machine, in one
run. It is a bounded negative and a stronger one than arm 5's, because the
subject was alive. It is still a negative. It does not exonerate volume, it does
not narrow the cause, and 24 is not the ~50 the plan calls for. The phenomenon
itself is not in question — it has hard `extensions.json` and on-disk evidence
from 2026-09-06/07 — so what remains unreproduced is the trigger, not the
defect.

**A restart was not exercised.** `--restart-every` stayed 0, matching both
organic occurrences, which happened in continuously-running processes. That
leaves the restart axis untested here as in every previous arm.

## Two defects the run found

Neither was found by the cycles. Both were found by reading what the rig said
about itself against what it measured.

**The rig could not express this arm at all.** `--headless` was declared
`action="store_true", default=True`, so it was always on and no spelling turned
it off — while the rig's own refusal message, when the sitter fails to arm,
tells the operator to use a real session or Xvfb. The flag that refusal points
at did not exist. Fixed in this pass with `argparse.BooleanOptionalAction`;
`--no-headless` is how arm 6 ran. Ticket 0778's experiment was blocked on a
missing command-line option, not on a missing idea.

**The pinned data directory silently did not take.** The driver logged
`data directory: /home/haduong/data/arm6/data (pinned, not Zotero's default)`
and the liveness read above says `dataDir: /home/haduong/Zotero`, which is
Zotero's default. The pinned directory was still empty at the end of the run.
The Menagerie was imported into the default directory and the sitter extracted
against it. No harm followed, for a reason that is luck and not a guard: the
author's real library lives at `/home/haduong/data/Zotero-fresh` and the default
path happened to be empty. Filed as ticket 0782. The shape is one this
repository keeps meeting — the log line states an intention in the grammar of a
measurement, the real measurement was being taken a minute later, and nothing
compared them.

## What this pass did NOT establish

Listed because the announcement needs it, and because a gate that was not run
must never read as a gate that passed.

- **No macOS or Windows run exists**, here or anywhere in this repository. The
  admission policy reads `/proc/meminfo` and `/proc/loadavg` and refuses when it
  cannot; off Linux that is expected to mean the add-on installs and indexes
  nothing. That is a source reading, not a measured outcome. Ticket 0783.
- **No real screen-reader or keyboard session.** Ticket 0769. The panel's
  accessibility has been reviewed by reading code, on a version long superseded.
- **No fresh-profile install from a release asset**, which is the arm ticket
  0727 has never had and which cannot run until a signed tag exists. It is the
  author's own step and it is scheduled before the announcement.
- **Zotero 11 behaviour cannot be tested**, because Zotero 11 does not exist.
  The `10.*` ceiling is expected to leave the add-on installed and disabled;
  that expectation rests on Gecko lineage, not on this host's behaviour.
- **The gates deliberately outside `make check`** — `acceptance-fixtures`,
  `schema-gate`, `golden`, `fold-gate` — were not run in this pass. They are
  scoped to the search pipeline rather than to the sitter payload, and each has
  a recorded reason for sitting outside the default gate. Their absence here is
  a decision, not a result.

## Reproducing arm 6

    DISPLAY=:1 python3 bench/sitter_volume_experiment.py \
      --profile <fresh dir> --data-dir <fresh dir> --payload-dir <fresh dir> \
      --log <path>.txt --evidence-dir <dir> \
      --zotero-bin ~/.local/Zotero_linux-x86_64/zotero \
      --no-headless --menagerie <unzipped menagerie package> \
      --burst-cycles 8 --burst-interval-seconds 8 \
      --spaced-cycles 15 --spaced-interval-seconds 120 --max-minutes 45

Until ticket 0782 is fixed, read the liveness line's `dataDir` before trusting
`--data-dir`, and do not run this on a machine whose default Zotero data
directory holds a library you care about.
