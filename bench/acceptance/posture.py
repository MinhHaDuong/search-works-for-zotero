"""The identity boundary DECISIONS.md ratified 2026-09-03: no target process
runs as the operator. Ticket 0625 owns the implementation; this module is its
executable form and restates the ruling only where the code needs it.

**The property, not the mechanism.** No target process runs under an identity
that can reach data the operator cares about. A dedicated account buys that on
a machine that also holds the operator's own data; a disposable container or a
throwaway VM already IS it, having no second identity within reach. The two are
not ranked, and this module treats them as two names for one thing it hands an
adapter before a spawn: a `Posture`. What stays forbidden is the case neither
name covers — a target running as the operator on a machine that has one.

**Which of two mechanisms, argued rather than picked by convenience.** The
harness could re-execute its own process under the dedicated account, or each
adapter could spawn its target under it while the harness itself keeps running
as the operator. The second is what this module implements, for a reason that
survives both readings of "one boundary, one place to get wrong": `wrap()`
below is that one place, called from every adapter that starts a real process,
so the boundary is exactly as singular as a full re-exec would have made it.
What a full re-exec would also have done, and does not need to, is force the
harness's OWN work across the account boundary too — the arena directories it
creates before a target ever runs, and the JSON artifact under
`bench/results/**` it writes after, which is committed as the operator's own
work and has no business belonging to `tester`. Re-executing the whole harness
would have to hand that writeback problem to every caller; spawning only the
target's own process avoids inventing it. `Declaration.process` already frames
the target's process as adapter-declared harness setup rather than the
harness's own concern (`interface.py`), so this module keeps the boundary at
the same seam that distinction already draws.

**Do NOT create accounts from here, ever.** Creating a system user needs root,
and a benchmark that can create users is a benchmark holding privilege it never
needs at run time. `tester` is provisioned once, out of band, by whoever runs
this harness: a dedicated account with **read** access to the Zotero library —
which the benchmark genuinely needs, since every target here is read-only
against it — and **write** access to nothing but the arena. The full recipe,
with the private-group-`$HOME` trap it was corrected against, lives beside
`ACCEPTANCE_ARENA` in the `Makefile`; the shape of it:

    sudo useradd --create-home --shell /usr/sbin/nologin tester
    sudo setfacl -m u:tester:x /home/<operator>                      # PARENT traverse first
    sudo setfacl -R -m u:tester:rX /home/<operator>/path/to/your/library
    sudo setfacl -R -d -m u:tester:rX /home/<operator>/path/to/your/library
    sudo install -d -o tester -g tester /path/to/the/acceptance/arena
    # then let the operator drive the harness without a password as tester:
    echo "operator ALL=(tester) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/acceptance-tester

The parent-traverse line is not decoration: verified on a second machine
("padme", 2026-09) where `$HOME` is `0750` under Ubuntu's private-group-per-
user scheme, `tester` could not step INTO the directory holding the library at
all without it, so the recursive grant on the library alone was unreachable.
The same two grants — parent traverse, then recursive `rX` — apply to every
built target checkout an adapter is pointed at via `--adapter-option`
(`application=`/`launcher=`/`zotero=`/`entrypoint=`/`venv=`), not only to the
library: `wrap()` below crosses the account boundary at the process spawn
alone, so `tester` reads the SAME checkout the operator already built, in
place, rather than a copy re-cloned under its own home — nothing here re-
executes the harness itself under `tester`, only the target's own process.

The sudoers line is the one `_works()` below actually exercises — a `tester`
account that exists but has no such sudoers rule is exactly the case it is
written to catch, distinctly from an absent account.

**Why `resolve()` runs rather than looks up.** Mirrors `sandbox.choose()`:
existence in the passwd database is not availability, the same way a binary on
PATH is not a working isolation mechanism. The sudoers rule above is exactly
the thing that can be missing while the account itself is present, and a probe
that only checked `pwd.getpwnam` would call that case available.

**Why the posture is asked rather than inferred, and the two probes rejected
rather than merely omitted.** No reliable predicate for "this environment is
already a boundary" is known, and the two tempting ones are worse than none:

- A flag saying *I am in CI* is exactly the kind of thing that gets set once on
  a workstation, for a one-off run, and then forgotten — after which every
  future run on that same workstation reads the flag and skips the account.
- A probe asking *can I write my own home* answers yes in most CI images too,
  because the container's only user typically owns everything in it; the
  answer that would distinguish a real boundary from an unprotected workstation
  is not available through that question.

So this module writes neither. `already-isolated` is a posture the operator
states on the command line, once, for a run whose environment is itself the
boundary; the harness does not verify the claim, because it has no way to.

**What the artifact must be able to show.** A run taken without the account,
in an environment claiming to be its own boundary, must be identifiable as
such afterwards — otherwise a green from an unprotected run is indistinguishable
from a green from a protected one, which is the shape of defect this project
keeps finding in its own instruments. `Posture.as_json()` is what `run.py`
attaches to every artifact for that reason; see its own docstring.

This module holds no target's name and no tool name. It runs an argv, the same
promise `sandbox.py` makes about itself.
"""

import pwd
import subprocess
from dataclasses import dataclass

#: The account name the recipe above provisions. Not configurable from the
#: command line on purpose: a harness that let the account name vary invites a
#: run against whichever account happens to be handy, which is the account
#: that was never granted the recipe's precise, and deliberately narrow, access.
ACCOUNT = "tester"

ACCOUNT_POSTURE = "account"
ISOLATED_POSTURE = "already-isolated"
POSTURES: tuple[str, ...] = (ACCOUNT_POSTURE, ISOLATED_POSTURE)


class PostureUnavailable(Exception):
    """Raised by `Posture.wrap` when this run has no identity boundary to use.

    Raised inside an adapter's `running()`, before any target process is
    spawned — never caught there and never anywhere that would let a caller
    fall back to spawning the argv unwrapped. `assess()`'s `record()` and the
    `--drive` subprocess's own guard both already convert an uncaught
    exception into `not-run`; this class exists so the message they carry
    names the actual reason a posture could not be established, rather than a
    generic transport failure.
    """


@dataclass(frozen=True)
class Posture:
    """What identity boundary a run has, and what a target's spawn does about it.

    `name` and `account` are what reaches the artifact via `as_json`. `refused`,
    when set, is why `wrap` raises instead of returning an argv — and `name`
    still carries what was ASKED for even then, so a reader of a `not-run`
    detail sees what was wanted and not merely that nothing was granted.
    """

    name: str
    account: str | None
    refused: str | None = None

    def wrap(self, argv: list[str], env: dict[str, str]) -> list[str]:
        """The argv a target's spawn actually runs, under this posture.

        Raises `PostureUnavailable` rather than returning anything if this
        posture could not be established. Every caller in this tree lets that
        propagate — there is no recovery path here that spawns `argv` as the
        operator instead, because that is precisely the fallback the ruling
        forbids "even for a fixture run".

        `already-isolated` returns `argv` unchanged: there is no second
        identity on this machine to cross into, by the operator's own
        declaration. `account` prepends the switch and carries `env` on the
        command line — via a bare `env` invocation inside the switch — rather
        than through the wrapping process's own environment, because `sudo`
        resets the environment by default and a sudoers rule that happens to
        keep it is exactly the configuration this module must not assume.
        `-n` is load-bearing: without it a `sudo` with no working NOPASSWD rule
        blocks on a password prompt nothing will ever answer, which is a hang
        dressed as a working boundary rather than the honest refusal `_works`
        below is written to observe instead.
        """
        if self.refused is not None:
            raise PostureUnavailable(self.refused)
        if self.account is None:
            return list(argv)
        assignments = [f"{key}={value}" for key, value in sorted(env.items())]
        return ["sudo", "-n", "-u", self.account, "--", "env", "-i", *assignments, *argv]

    def as_json(self) -> dict:
        """What a run's artifact records about its own identity boundary.

        `posture` is `None` only for a name this module refused to recognise at
        all (an unknown `--posture` value); a resolved-but-refused account
        posture still names itself `"account"`, because "asked for the account
        posture and could not get it" and "asked for nothing sensible" are
        different findings and must not land in one cell — the same argument
        `interface.py` makes for `unsupported`'s reason field.
        """
        return {
            "posture": self.name or None,
            "account": self.account,
            "refused": self.refused,
        }


def _account_exists(account: str) -> bool:
    try:
        pwd.getpwnam(account)
    except KeyError:
        return False
    return True


def _works(account: str) -> bool:
    """Run a trivial command as the account and see whether it actually ran.

    Not a PATH-style lookup and not a passwd-database lookup either, for the
    reason the module docstring gives: an account that exists but has no
    working sudoers rule must read as unavailable, not as available with a
    surprise later.
    """
    probe = Posture(ACCOUNT_POSTURE, account)
    try:
        done = subprocess.run(probe.wrap(["true"], {}), capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def resolve(posture_name: str, account: str = ACCOUNT) -> Posture:
    """The posture a run has, or a `Posture` whose `wrap` refuses and says why.

    Called once per process — the outer driver, and separately each `--drive`
    subprocess, since a resolved posture cannot be handed across a process
    boundary and re-resolving costs one passwd lookup or one trivial `sudo`
    invocation. Never falls back: on any refusal the returned `Posture` still
    describes what was asked for, and its `wrap` raises rather than a caller
    silently spawning a target as the operator.
    """
    if posture_name == ISOLATED_POSTURE:
        return Posture(ISOLATED_POSTURE, account=None)
    if posture_name != ACCOUNT_POSTURE:
        return Posture(posture_name, account=None, refused=(
            f"{posture_name!r} is not a posture this harness knows "
            f"({', '.join(POSTURES)})"
        ))
    if not _account_exists(account):
        return Posture(ACCOUNT_POSTURE, account=None, refused=(
            f"no {account!r} account on this machine. The harness does not create "
            "one; an operator provisions it once, out of band, with read access to "
            "the Zotero library and write access to nothing but the arena. Without "
            "it a target process would run as the operator, which the ratified "
            "posture forbids even for a fixture run."
        ))
    if not _works(account):
        return Posture(ACCOUNT_POSTURE, account=None, refused=(
            f"{account!r} exists but a run under it did not succeed here (checked by "
            "running a trivial command under it, not by looking the account up). The "
            "sudoers rule the recipe asks for is likely missing or misconfigured."
        ))
    return Posture(ACCOUNT_POSTURE, account=account)
