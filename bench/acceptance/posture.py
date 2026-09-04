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
work and has no business belonging to `untrusted-runner`. Re-executing the whole harness
would have to hand that writeback problem to every caller; spawning only the
target's own process avoids inventing it. `Declaration.process` already frames
the target's process as adapter-declared harness setup rather than the
harness's own concern (`interface.py`), so this module keeps the boundary at
the same seam that distinction already draws.

**Do NOT create or rename accounts from here, ever.** Either operation needs root,
and a benchmark that can create users is a benchmark holding privilege it never
needs at run time. `untrusted-runner` is provisioned once, out of band, by whoever runs
this harness: a dedicated account with **read** access to the Zotero library —
which the benchmark genuinely needs, since every target here is read-only
against it — and **write** access to nothing but the arena. The full recipe,
with the private-group-`$HOME` trap it was corrected against, lives beside
`ACCEPTANCE_ARENA` in the `Makefile`; the shape of it:

    # Existing host: preserve the UID, owned files and named ACL entries.
    sudo usermod --login untrusted-runner tester
    sudo groupmod --new-name untrusted-runner tester
    sudo usermod --home /path/to/untrusted-runner-home --move-home untrusted-runner
    sudo visudo -f /etc/sudoers.d/acceptance-tester  # replace tester in the rule
    sudo mv /etc/sudoers.d/acceptance-tester /etc/sudoers.d/untrusted-runner

    # Fresh host instead:
    sudo useradd --create-home --shell /usr/sbin/nologin untrusted-runner

    # Both paths:
    sudo setfacl -m u:untrusted-runner:x /home/<operator>           # PARENT traverse first
    sudo setfacl -R -m u:untrusted-runner:rX /home/<operator>/path/to/your/library
    sudo setfacl -R -d -m u:untrusted-runner:rX /home/<operator>/path/to/your/library
    install -d /path/to/the/acceptance/arena                          # OPERATOR-owned …
    setfacl -m u:untrusted-runner:rwx -m d:u:untrusted-runner:rwx /path/to/the/acceptance/arena
    # then let the operator drive the target without a password as untrusted-runner,
    # AND forward the named environment variables wrap() lists on --preserve-env
    # (SETENV) rather than sudo silently dropping them (see wrap()'s own docstring):
    echo "operator ALL=(untrusted-runner) NOPASSWD:SETENV: ALL" | sudo tee /etc/sudoers.d/untrusted-runner
    sudo chown root:root /etc/sudoers.d/untrusted-runner
    sudo chmod 0440 /etc/sudoers.d/untrusted-runner
    sudo visudo -c
    sudo -n -u untrusted-runner -- true

The parent-traverse line is not decoration: verified on a second machine
("padme", 2026-09) where `$HOME` is `0750` under Ubuntu's private-group-per-
user scheme, `untrusted-runner` could not step INTO the directory holding the library at
all without it, so the recursive grant on the library alone was unreachable.
The same two grants — parent traverse, then recursive `rX` — apply to every
built target checkout an adapter is pointed at via `--adapter-option`
(`application=`/`launcher=`/`zotero=`/`entrypoint=`/`venv=`), not only to the
library: `wrap()` below crosses the account boundary at the process spawn
alone, so `untrusted-runner` reads the SAME checkout the operator already built, in
place, rather than a copy re-cloned under its own home. The outer harness and
artifact writer never move; normally only the target process does. R10's
egress arm also encloses its tracer, isolation mechanism and inner target-driving
re-invocation, as the one-crossing explanation below specifies.

The sudoers line is the one `_works()` below actually exercises — an `untrusted-runner`
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

**One crossing, and it happens before any other apparatus, not after (ticket
0637).** R10's egress arm re-invokes this driver in `--drive` mode under a
tracer and an isolation mechanism (`sandbox.py`), and the adapter inside that
re-invocation then reaches `wrap()` from within both. `sudo` cannot run from
there, for three separate reasons, each measured on padme (2026-09-04): inside
a rootless user namespace the files it must trust literally (`/etc/sudo.conf`,
`/etc/sudoers`) appear owned by the unmapped uid and it refuses on principle
(`podman unshare unshare -n -- sudo -n -u untrusted-runner -- true` → "owned by uid 65534,
should be 0"); under an unprivileged tracer a setuid exec is neutralised by the
kernel and it refuses again (`strace -f sudo -n -u untrusted-runner -- true` → "effective
uid is not 0"), with no namespace anywhere in sight; and `bwrap` sets
no-new-privs on everything inside it, which is the same refusal by a third
route. None of these is a misconfiguration; each is `sudo` declining to trust
an environment it cannot verify, and the fix works with that rather than around
it. So on that one arm the crossing moves OUTERMOST — the identity switch
encloses the tracer, which encloses the mechanism, which encloses the
re-invoked driver (`sandbox.run_traced`'s `under`; `run.py` composes it) — and
the re-invoked process spawns its target unwrapped, holding `inherited()`
below, because it already IS the account. That is still one crossing at one
seam: the parent crossed it, once, for the whole of a subprocess that does
nothing but seed a data directory, spawn the target and drive its verbs — all
of it target-owned derived state under the arena, none of it the harness's own
work. The outer driver, which writes the arena directories and the artifact,
never moves. Ticket 0625's argument against a full re-exec (above) is about
THAT process and stands untouched.

**What the artifact must be able to show.** A run taken without the account,
in an environment claiming to be its own boundary, must be identifiable as
such afterwards — otherwise a green from an unprotected run is indistinguishable
from a green from a protected one, which is the shape of defect this project
keeps finding in its own instruments. `Posture.as_json()` is what `run.py`
attaches to every artifact for that reason; see its own docstring.

This module holds no target's name and no tool name. It runs an argv, the same
promise `sandbox.py` makes about itself.
"""

import os
import pwd
import subprocess
from dataclasses import dataclass

#: The account name the recipe above provisions. Not configurable from the
#: command line on purpose: a harness that let the account name vary invites a
#: run against whichever account happens to be handy, which is the account
#: that was never granted the recipe's precise, and deliberately narrow, access.
ACCOUNT = "untrusted-runner"

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
    #: True in a process the outer driver has ALREADY placed under `account`
    #: (`inherited()`): the boundary was crossed once, by the parent, and
    #: `wrap` returns `argv` unchanged rather than attempting a second `sudo`
    #: from a place where it is refused (module docstring, ticket 0637).
    inherited: bool = False

    def wrap(self, argv: list[str], env: dict[str, str]) -> list[str]:
        """The argv a target's spawn actually runs, under this posture.

        Raises `PostureUnavailable` rather than returning anything if this
        posture could not be established. Every caller in this tree lets that
        propagate — there is no recovery path here that spawns `argv` as the
        operator instead, because that is precisely the fallback the ruling
        forbids "even for a fixture run".

        `already-isolated` returns `argv` unchanged: there is no second
        identity on this machine to cross into, by the operator's own
        declaration. An `inherited` account posture returns it unchanged too,
        for the opposite reason: this process is already the account.

        `account` prepends the switch, and this is the one place a first
        version of this module got the boundary itself wrong, corrected in
        review before it merged: `env` is NOT written onto this argv, in any
        form. An earlier draft carried `env -i KEY=VALUE ...` here, which
        moved every value in `env` — including anything ambient in the
        operator's own shell, an API key or a token among them — from
        `Popen`'s `env=` (visible only via `/proc/<pid>/environ`, to the
        owning uid or root) onto this process's OWN argv, which any local
        user can read for as long as the process lives via `ps` or
        `/proc/<pid>/cmdline`, and which a process-accounting or auditd setup
        logs durably regardless. That is a strictly worse channel than the one
        this ticket exists to close, for the sake of the account boundary this
        ticket exists to open.

        The fix keeps values off every argv, on both sides of the switch, by
        forwarding them through the environment `sudo`'s OWN process receives
        instead — which is exactly what the caller already sets via `Popen`'s
        `env=` on the wrapped argv this method returns, unchanged from before
        this ticket. `--preserve-env=<names>` only carries NAMES: `KEY`, never
        `KEY=VALUE`, so nothing secret reaches an argv anyone can list. `sudo`
        then forwards those names' values from ITS OWN received environment to
        the account-switched child via `execve`'s `envp`, the same channel
        `Popen`'s `env=` always used and the same visibility rule as before —
        readable via `/proc/<child-pid>/environ` by the child's own uid (now
        `untrusted-runner`) or root, never by an arbitrary local account. This needs the
        `SETENV` sudoers tag (the recipe below carries it): without it `sudo`
        ignores `--preserve-env` outright rather than silently ignoring only
        the listed names, so a misconfigured sudoers rule fails the `_works`
        probe rather than quietly narrowing what reaches the target.

        `-n` is load-bearing: without it a `sudo` with no working NOPASSWD rule
        blocks on a password prompt nothing will ever answer, which is a hang
        dressed as a working boundary rather than the honest refusal `_works`
        below is written to observe instead.
        """
        if self.refused is not None:
            raise PostureUnavailable(self.refused)
        if self.account is None or self.inherited:
            return list(argv)
        names = ",".join(sorted(env))
        preserve = [f"--preserve-env={names}"] if names else []
        return ["sudo", "-n", "-u", self.account, *preserve, "--", *argv]

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


#: Environment names that describe WHO is running rather than WHAT is being run.
#: `forwardable()` strips them from what the re-invoked `--drive` process
#: inherits across the account switch: a rootless container engine started as
#: `untrusted-runner` with the operator's `HOME` or runtime directory looks for its own
#: state under a home it cannot write, and fails for a reason that has nothing
#: to do with egress. `sudo` sets the account's own values for these. This
#: list is NOT applied by `wrap()` itself: several adapters set `HOME` on
#: purpose, to an arena-owned directory their target must treat as home, and
#: that is exactly the kind of name a target's spawn must keep.
IDENTITY_BOUND: frozenset[str] = frozenset({
    "HOME", "USER", "LOGNAME", "USERNAME", "SHELL", "MAIL",
    "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
})


def forwardable(env) -> dict[str, str]:
    """The names in `env` a whole re-invoked driver may carry across the switch.

    Everything the run itself needs stays — `PATH`, and any variable the
    operator exported for the target to see (`Server` merges `os.environ`
    into the target's environment, so an export in the invoking shell reaches
    the target exactly as it did before the switch). Only `IDENTITY_BOUND`
    goes; see its comment.
    """
    return {name: value for name, value in dict(env).items() if name not in IDENTITY_BOUND}


def inherited(account: str) -> Posture:
    """The posture of a process the outer driver has already placed under `account`.

    Handed to a `--drive` process via `--spawned-under` (`run.py`), never
    resolved by probing: inside the enclosing switch — and inside the tracer
    and mechanism around it — `_works`'s `sudo` probe is refused for the module
    docstring's reasons, so probing there would turn every isolated run into a
    guaranteed `not-run`. The claim is made by the harness about its own child,
    on an argv the harness built one process up.

    What the process CAN see is `USER`. `forwardable()` strips every
    `IDENTITY_BOUND` name from what the re-invocation carries across, so `sudo`
    writes the account's own value there and a switch that genuinely happened
    reads `untrusted-runner`; an operator hand-typing `--spawned-under` reads their own
    name instead, and that is the case this refuses. No uid check: `getuid()`
    is the read that does not survive the namespace — but this checks `USER`,
    not uid, and `USER` does. Measured live on this project's own reference
    machine (ticket 0638): `podman unshare unshare -n -- env` still reports
    `USER=untrusted-runner` under the rootless user namespace that makes `getuid()` read
    0 there. `unshare`/`podman unshare` remap the process's uid, mount, and
    network namespaces; they never touch `envp` — environment survives plain
    `execve` inheritance, orthogonal to namespacing. So this check applies
    unconditionally, under every `Mechanism` `sandbox.py` knows about today:
    the module's "verify, don't trust" discipline (`_works`) applied to the
    one case it previously exempted itself from without measuring it.

    Refused, not raised, and that is the shape `resolve()` uses for the same
    reason: this runs at argparse time, before `record()` — the one place in
    the driver that turns a raise into a verdict — so raising here would exit
    the `--drive` child with a traceback and land as a red the artifact cannot
    explain. A refused posture instead reaches the spawn, where `wrap` raises
    inside `record` and the artifact says `not-run` carrying the sentence
    naming both the claimed account and what `USER` actually read. Fail-closed
    either way: `wrap` tests `refused` before every other branch, so nothing
    spawns unwrapped on this path.
    """
    actual = os.environ.get("USER")
    if actual != account:
        return Posture(ACCOUNT_POSTURE, account=account, inherited=True, refused=(
            f"--spawned-under claims this process runs as {account!r}, but USER reads "
            f"{actual!r}; the account switch this claim describes did not happen here"
        ))
    return Posture(ACCOUNT_POSTURE, account=account, inherited=True)


def _account_exists(account: str) -> bool:
    try:
        pwd.getpwnam(account)
    except KeyError:
        return False
    return True


#: Named on the `_works` probe's `--preserve-env` so the probe exercises the
#: SAME sudoers permission a real spawn needs, not merely `sudo -n -u account`.
#: `wrap()` builds `--preserve-env=<names>` only when `env` is non-empty, so a
#: probe called with `{}` (a bare account switch) would never touch the
#: `SETENV` tag at all and would read a sudoers rule with NOPASSWD but no
#: SETENV as working -- a real adapter's first genuine spawn, whose `env` is
#: never empty, would then be the first place that misconfiguration surfaces.
_PROBE_ENV_NAME = "_ACCEPTANCE_POSTURE_PROBE"


def _works(account: str) -> bool:
    """Run a trivial command as the account and see whether it actually ran.

    Not a PATH-style lookup and not a passwd-database lookup either, for the
    reason the module docstring gives: an account that exists but has no
    working sudoers rule must read as unavailable, not as available with a
    surprise later. The probe carries one synthetic environment name so it
    exercises `--preserve-env`'s `SETENV` requirement too (see
    `_PROBE_ENV_NAME`) -- `sudo` refuses the whole invocation, not merely the
    unlisted names, when the invoking user lacks permission to preserve what
    was named, so a missing `SETENV` grant shows up here as a failed probe
    rather than as a silently narrower environment reaching a real target.
    """
    probe = Posture(ACCOUNT_POSTURE, account)
    probe_env = {**os.environ, _PROBE_ENV_NAME: "1"}
    try:
        done = subprocess.run(
            probe.wrap(["true"], {_PROBE_ENV_NAME: "1"}),
            capture_output=True, timeout=30, env=probe_env,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def resolve(posture_name: str, account: str = ACCOUNT) -> Posture:
    """The posture a run has, or a `Posture` whose `wrap` refuses and says why.

    Called once per process that has a boundary to establish: the outer driver,
    and a `--drive` subprocess under `already-isolated`. A `--drive` subprocess
    the outer driver has placed under the account holds `inherited()` instead
    and never probes — from inside the switch the probe cannot succeed (module
    docstring, ticket 0637). Never falls back: on any refusal the returned `Posture` still
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
