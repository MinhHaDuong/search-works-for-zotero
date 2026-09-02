"""The instrument R10's egress clause needs: a run with no route out, and a tracer.

`SPEC.md` §3, R10 is the clause; `SPEC.md` §5.2.8 owns the harness. This module
is apparatus and asserts nothing. It holds no target's name: it runs an argv.

**Why a tracer and not just a namespace.** Running inside a namespace with no
route proves nothing *left*. It does not prove nothing was *attempted*, and the
clause is about the attempt: "the run completes and no connection to a
destination off this machine is attempted" (ticket 0578, Action 3). A target
that reaches out and swallows the error is indistinguishable, by outcome alone,
from one that never reached. So the namespace supplies the guarantee and the
tracer supplies the observation, and they are different jobs.

**Two detectors, because one has a hole that reads as green.** Measured on this
machine, 2026-09-02, and confirmed independently the same evening:

- A run that reaches for a literal off-machine address inside the namespace
  leaves `connect(..., AF_INET, ... "1.1.1.1") = -1 ENETUNREACH` in the trace.
  The attempt is visible even though nothing left. Detector `off_machine`
  catches it.
- A run that reaches for a *hostname* inside the namespace dies at name
  resolution first, and every `connect` it leaves behind goes to the stub
  resolver on loopback — port 53 at `127.0.0.53`. The off-machine connect it
  wanted **never appears**. A detector that flags only non-loopback addresses
  therefore reports zero attempts for a target that was actively trying to
  phone home. That is a false green, and it is exactly the failure class this
  harness exists to catch.

So `dns` is a second detector, and it counts a name lookup as an egress attempt
even though the packet goes to loopback. The justification is not that loopback
is remote; it is that a resolver is a forwarder, and a target with no business
off this machine has no business resolving a name. If a target turns out to
resolve names at startup for a benign reason, that is a finding to surface,
not an exemption to add here quietly.

The trap inside the trap, recorded so nobody repairs it the wrong way: if the
fail-control stub is written against a hostname, the `off_machine` detector will
not fire, and the tempting fix is to rewrite the control against a literal IP.
That makes the control pass while leaving the assertion blind to every
hostname-based egress in a real target. Both controls are kept, and each must
drive its own detector red.

Both counts are recorded on every run, including green ones, so a reader can
tell a zero that was measured from a zero that was never looked for.

**The isolation mechanism is pluggable and probed, not pinned.** `SPEC.md`
§5.2.8 says "a network namespace with no route out (or the platform's
equivalent)", and the equivalent is not decoration: one of the two machines this
harness must run on has `bwrap` installed but unusable rootless — not setuid,
and unprivileged user namespaces restricted by policy — so a pinned `bwrap`
would make R10 permanently `not-run` there. Each mechanism supplies an isolated
wrapper and a shared-network control wrapper; the assertion probes for one that
works, uses it, and records which one ran. Where none works, the verdict is
`not-run`, never green.

A mechanism's availability is decided by *running* it, not by looking for its
binary on PATH. That distinction is the whole reason this is a probe: on the
machine above, `shutil.which` finds `bwrap` and `bwrap ... true` then exits 1.

**Why the tracer wraps the sandbox and not the other way round.** `--ro-bind / /`
makes the filesystem read-only inside, so a tracer started inside cannot open
its own log (`strace: Can't fopen ...: Read-only file system`). `strace -f`
outside follows the sandbox's children, which is what a target's own forks need,
and it has been confirmed to see through both mechanisms.

**Why the writable set is the caller's to name.** Under `bwrap`'s read-only bind
the target cannot write anywhere, so a run that needs to create derived state
fails for a reason that has nothing to do with egress — a false red of the
environmental kind. Each path in `writable` is re-bound read-write. The caller
passes the adapter's declared derived-state roots, which makes the writable set
a cross-check on the declaration: if the target needs a path its adapter did not
declare, the run fails inside the sandbox, and what that failure reports is an
incomplete declaration.

**That cross-check is not universal, and the difference is recorded rather than
glossed.** It exists only where a mechanism confines writes at all. A mechanism
that leaves the host filesystem mounted — the platform equivalent below does,
which is the whole reason it needs no image — cannot enforce `writable`, so on
that arm the set is a hint and the declaration is checked by the residue sweep
alone. Each mechanism carries `writable_enforced` and the egress assertion
records it beside the mechanism's name, because a guarantee that silently
applies on one machine and not another is worse than one that never applied.

This module never learns which target it is running, and it never learns about
an adapter. It takes an argv and a list of paths.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

STRACE = "strace"

#: Ports at which a name lookup leaves. 53 is DNS, 853 is DNS-over-TLS, 5353 is
#: multicast DNS. Loopback is deliberately NOT excused at these ports; the module
#: docstring argues why.
RESOLVER_PORTS = frozenset({53, 853, 5353})

#: The syscalls through which a destination is named. `connect` covers TCP and a
#: connected UDP socket; `sendto` and `sendmsg` cover the unconnected ones, which
#: is how a resolver query usually goes out.
_SYSCALLS = ("connect", "sendto", "sendmsg")

_LINE = re.compile(r"\b(?P<call>" + "|".join(_SYSCALLS) + r")\((?P<body>.*)")
_V4 = re.compile(
    r"sa_family=AF_INET\b.*?sin_port=htons\((?P<port>\d+)\).*?"
    r'sin_addr=inet_addr\("(?P<addr>[^"]+)"\)'
)
_V6 = re.compile(
    r"sa_family=AF_INET6\b.*?sin6_port=htons\((?P<port>\d+)\).*?"
    r'inet_pton\(AF_INET6, "(?P<addr>[^"]+)"'
)


# --------------------------------------------------------------------------
# Isolation mechanisms.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Mechanism:
    """One way to run an argv with no route out, and its matching control.

    `isolated` and `shared` must differ in exactly one thing: the network
    namespace. Anything else that differs between them turns the control arm
    from a discriminator into decoration.

    `writable_enforced` says whether this mechanism actually confines writes to
    the paths it is handed. It is not a detail. Where it is false, the
    declaration cross-check the module docstring describes does not happen, and
    two artifacts from two machines are not comparable on that axis. A mechanism
    that quietly ignored `writable` while the prose promised otherwise would be
    a guarantee nobody could see was missing, so the flag rides in the artifact
    beside the mechanism's name.
    """

    name: str
    note: str
    writable_enforced: bool = True

    def isolated(self, argv: list[str], writable: tuple[Path, ...]) -> list[str]:
        raise NotImplementedError

    def shared(self, argv: list[str], writable: tuple[Path, ...]) -> list[str]:
        raise NotImplementedError


@dataclass(frozen=True)
class Bubblewrap(Mechanism):
    """Verified working on the machine this was written on (2026-09-02).

    The read-only bind of `/` is what makes `writable` load-bearing; see the
    module docstring.
    """

    name: str = "bwrap"
    note: str = (
        "bubblewrap: the host tree read-only, the declared derived-state roots re-bound "
        "read-write, and --unshare-net for the isolated arm"
    )

    def _base(self, writable: tuple[Path, ...]) -> list[str]:
        binds: list[str] = []
        for path in writable:
            if path.exists():
                binds += ["--bind", str(path), str(path)]
        return ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", *binds]

    def isolated(self, argv: list[str], writable: tuple[Path, ...]) -> list[str]:
        return [*self._base(writable), "--unshare-net", *argv]

    def shared(self, argv: list[str], writable: tuple[Path, ...]) -> list[str]:
        return [*self._base(writable), *argv]


@dataclass(frozen=True)
class PodmanUnshare(Mechanism):
    """The platform equivalent for a host where rootless bubblewrap is refused.

    VERIFIED END TO END on that second machine (2026-09-02), after being written
    blind here from a measurement taken there. `choose()` selects it over
    `bwrap`, which is present but refused rootless (not setuid, unprivileged
    user namespaces restricted by policy); both arms behave as specified — the
    isolated arm takes a different network-namespace inode with zero routes, the
    control keeps the host's — the tracer sees through it, and both detectors
    were driven red separately by the deterministic stubs while the quiet stub
    still came back green.

    `podman unshare` enters the rootless user namespace, where the caller holds
    the capability that the bare `unshare -n` on the host lacks; the isolated arm
    then takes a fresh, empty network namespace inside it. The host filesystem
    stays mounted, which is why no image and no bind list are needed — the
    target's build and its data directory are simply there.

    The price of that convenience is exact and is declared rather than hidden:
    because nothing is bound read-only, `writable` cannot be enforced here, so
    `writable_enforced` is False. Reachability is unaffected — the isolation
    this class exists for is of the network and not of the filesystem — but the
    module docstring's declaration cross-check holds only on the bubblewrap arm.
    Measured on the second machine: with `writable=()` a write outside every
    declared root still succeeded inside the isolated arm.

    The control arm is `podman unshare` *without* the inner `unshare -n`: same
    user namespace, same filesystem, network namespace untouched. That is the
    one-difference rule the base class states.

    Two traps recorded rather than engineered around, neither of them measured
    here. First, `/sys/class/net` inside the isolated arm still lists the host's
    interfaces, because sysfs is not remounted — interface listing is therefore
    not evidence of anything, and the honest observables are the namespace inode
    and the route count. Second, inside `podman unshare` the invoking user maps
    to uid 0 and host uids are shifted, so files the target writes may land with
    surprising ownership on the host; nothing here assumes stable ownership.
    """

    name: str = "podman-unshare"
    note: str = (
        "podman unshare: the rootless user namespace, with a fresh empty network "
        "namespace inside it for the isolated arm. The host filesystem stays mounted, "
        "so the writable set is not enforced on this arm"
    )
    writable_enforced: bool = False

    def isolated(self, argv: list[str], writable: tuple[Path, ...]) -> list[str]:
        return ["podman", "unshare", "unshare", "-n", *argv]

    def shared(self, argv: list[str], writable: tuple[Path, ...]) -> list[str]:
        return ["podman", "unshare", *argv]


#: In probe order. Bubblewrap first because it is the cheaper and the verified
#: one; the platform equivalent is tried when it does not work here.
MECHANISMS: tuple[Mechanism, ...] = (Bubblewrap(), PodmanUnshare())


def _works(mechanism: Mechanism) -> bool:
    """Run the mechanism on a trivial command and see whether it succeeds.

    Deliberately not a PATH lookup. On one of the two machines this harness must
    run on, the binary is present and the invocation is refused — a mechanism
    that is installed and unusable is exactly the case a `which` check calls
    available.
    """
    try:
        done = subprocess.run(
            mechanism.isolated(["true"], ()), capture_output=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def _tracer_works() -> bool:
    try:
        done = subprocess.run([STRACE, "-V"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def choose() -> tuple[Mechanism | None, str | None]:
    """The first mechanism that actually runs here, or why none does.

    The caller turns a reason into `not-run`. An assertion that silently skipped
    its sandbox would report the same green as one that ran.
    """
    if not _tracer_works():
        return None, (
            f"the egress instrument needs {STRACE} and it did not run here; without a "
            "tracer an attempt that fails is indistinguishable from one never made, so "
            "this clause is not decided"
        )
    tried = []
    for mechanism in MECHANISMS:
        if _works(mechanism):
            return mechanism, None
        tried.append(mechanism.name)
    return None, (
        f"no isolation mechanism ran here (tried: {', '.join(tried)}). A network "
        "namespace with no route out, or the platform's equivalent, is what makes this "
        "clause decidable, so it is not decided"
    )


# --------------------------------------------------------------------------
# The detectors.
# --------------------------------------------------------------------------


def is_loopback(address: str) -> bool:
    """127.0.0.0/8 and ::1. Deliberately textual: the trace gives us text."""
    return address == "::1" or address.startswith("127.")


@dataclass
class Attempt:
    """One syscall that named a destination, and which detector it tripped."""

    call: str
    address: str
    port: int
    detector: str
    line: str

    def as_json(self) -> dict:
        return {"call": self.call, "address": self.address,
                "port": self.port, "detector": self.detector}


def attempts_in(trace: str) -> list[Attempt]:
    """Every destination-naming syscall in a trace, classified by detector.

    An attempt can trip both detectors (a literal off-machine resolver, say);
    `off_machine` is reported then, because it is the stronger observation.
    """
    found: list[Attempt] = []
    for line in trace.splitlines():
        head = _LINE.search(line)
        if not head:
            continue
        match = _V4.search(head.group("body")) or _V6.search(head.group("body"))
        if not match:
            continue  # AF_UNIX and AF_NETLINK chatter: no destination off this machine.
        address, port = match.group("addr"), int(match.group("port"))
        if not is_loopback(address):
            detector = "off_machine"
        elif port in RESOLVER_PORTS:
            detector = "dns"
        else:
            continue  # loopback, not a resolver: the target talking to itself.
        found.append(Attempt(head.group("call"), address, port, detector, line.strip()))
    return found


@dataclass
class TraceResult:
    """What one traced, optionally isolated, run observed."""

    argv: list[str]
    mechanism: str
    network_shared: bool
    returncode: int
    stdout: str
    stderr: str
    attempts: list[Attempt] = field(default_factory=list)

    def by_detector(self, detector: str) -> list[Attempt]:
        return [a for a in self.attempts if a.detector == detector]

    def counts(self) -> dict[str, int]:
        """Both counts, always — including the zeros. A zero that was measured
        and a zero that was never looked for are different facts."""
        return {"off_machine": len(self.by_detector("off_machine")),
                "dns": len(self.by_detector("dns"))}

    def as_json(self) -> dict:
        return {
            "mechanism": self.mechanism,
            "network_shared": self.network_shared,
            "returncode": self.returncode,
            "attempt_counts": self.counts(),
            "attempts": [a.as_json() for a in self.attempts],
            "stdout_tail": self.stdout[-2000:],
            "stderr_tail": self.stderr[-2000:],
        }


def run_traced(
    argv: list[str],
    *,
    mechanism: Mechanism,
    network_shared: bool,
    log_dir: Path,
    tag: str,
    writable: tuple[Path, ...] = (),
    timeout: float = 900,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> TraceResult:
    """Run `argv` under the tracer, inside the mechanism, and classify what it named.

    `network_shared=True` is the control arm: same mechanism, same tracer, route
    intact. It is what distinguishes "nothing tried to leave" from "the sandbox
    or the tracer was not working", which is the whole reason it exists.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{tag}.strace"
    wrap = mechanism.shared if network_shared else mechanism.isolated
    command = [STRACE, "-f", "-e", "trace=network", "-o", str(log),
               *wrap(list(argv), tuple(writable))]
    done = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env
    )
    trace = log.read_text(errors="replace") if log.exists() else ""
    return TraceResult(
        argv=list(argv),
        mechanism=mechanism.name,
        network_shared=network_shared,
        returncode=done.returncode,
        stdout=done.stdout,
        stderr=done.stderr,
        attempts=attempts_in(trace),
    )
