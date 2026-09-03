"""The first adapter: declarations, and the minimal transport to reach them.

`SPEC.md` §5.2.8 names this target; `SPEC.md` §5.2.7's "R15's uninstall clause"
paragraph is the authority for what this adapter reports for `uninstall`. Both
are cited, neither restated.

**What is declared and what is merely reached.** Everything a reader needs to
audit a verdict is in `Declaration`: where derived state lands, how the query
surface is reached, how the process starts and stops, what the default
configuration is, and which verbs are absent. The rest of this file is the
JSON-RPC plumbing that invokes those surfaces, reusing `bench/mcp_drive.py`
rather than reinventing a transport. There is no patch, no workaround, no
non-default option, and no scoring of a result.

**`uninstall` is declared absent, and nothing is substituted for it.** This
target has no uninstall surface today. `SPEC.md` §5.2.7 says in as many words
that `purge` is maintenance rather than a stand-in the harness may call to
manufacture a clean result, so the verb is listed unsupported and R15's
uninstall clause reports `not-offered`. That is the honest answer in both
directions: it is not scored as a failure at a surface the target does not
claim to have, and it is not scored as a pass either.

**`resume` is declared absent, and this is the judgement call worth arguing.**
The ratified interface defines pause and resume as the two transitions of one
durable background-work control, with resume idempotent and never forcing a
rebuild, refresh, repair or sync.

The background-work surface here is five actions — build, refresh, update,
status, stop — and `pause` maps cleanly onto `stop`: it cancels a running job,
the partial data stays searchable, and the interrupted work leaves a checkpoint
on disk. That checkpoint is what makes the pause durable in the sense R22 cares
about: the progress survives a restart, and nothing auto-resumes behind the
user's back.

Nothing maps onto `resume`. The only action that continues an interrupted build
is `build`, and `build` is three things at once by its own documentation: it
resumes from the checkpoint, it rebuilds the whole index, and it is *also* the
repair — when the index cannot be read, `build` deletes the unreadable file
before rebuilding. Mapping `resume` onto it would smuggle a destructive rebuild
into the one verb the ruling says never rebuilds, and it would do so invisibly,
because on a healthy checkpointed index `build` really does just resume. The
over-claim would only show itself on the damaged index, which is exactly the
case a green must not cover. So `resume` is declared absent.

**The question that leaves open, which is raised here and not settled.** The
ruling calls pause and resume "the two transitions of one durable
background-work control". This adapter declares one transition present and the
other absent, which the interface permits mechanically — `unsupported` is
per-verb — but which sits awkwardly with a control described as a single thing.
Either the two verbs are independently declarable, or a target missing one of
them has no such control at all and both should be absent. That is a question
about the ratified interface rather than about this target, and it is the more
interesting for surfacing on the target the interface was drawn from. It is
flagged rather than decided.

**Goal 2 needs an index, and an empty data directory cannot express its clauses.**
R3, R13 and R23 are all about a library already in service — what staying current
costs, what a second process does to a settled index, what happens when a stamp
changes under one. Against a data directory this run has just created, R13 is
two processes agreeing that nothing matches and R23 has no baseline to lose. So
this adapter accepts a prebuilt index to start from (`seed_index`), copied in
before the process starts and recorded in the declaration so the artifact says
which index it measured. It is not a non-default option in the sense the
contract forbids: no flag is passed to the target, no behaviour is changed, and
the state it produces — a data directory that already holds an index — is the
ordinary one for every user after their first day.

**Two of the four perturbations are declined, and the reasons differ.** The
restamps are done here, in sqlite, exactly as `bench/smoke_upstream.py`'s
`_restamp_and_open` does them, because the stamp is this target's own storage
and only this adapter may know where it lives. Editing one item and resyncing
identical bytes are declined: both are writes to the user's Zotero library,
which this target is configured read-only against and which R15 excludes from
derived state — and the clauses they serve read work counters this target does
not report, so driving them would produce an undecidable run rather than a
verdict.

**The model runtime path is a declared, overridable input, and it is the sharpest
environmental trap here.** The built checkout does not vendor the on-device model
runtime. Without being pointed at one the target falls back to keyword-only,
silently — and R10's local-by-default clause then fails for a reason that has
nothing to do with the target's behaviour and everything to do with this
machine. That false red looks exactly like a true one. So the path is a
constructor argument, surfaced as a CLI flag and an environment variable, with
no default baked in: a wrong or absent value produces a verdict about the
environment, and the artifact records what was passed so a reader can tell which
they are looking at.
"""

import os
import shutil
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

from ..durability import (
    EDIT_ONE_ITEM,
    RESET_TO_SEEDED_INDEX,
    RESTAMP_NEWER,
    RESTAMP_OLDER,
    RESYNC_IDENTICAL_BYTES,
)
from ..interface import Declaration, UnsupportedVerb
from ..posture import Posture

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mcp_drive import Server  # noqa: E402

NAMES = ("zoteus",)

#: R33's three retrieval modes in the layer's vocabulary, mapped onto the names
#: this target uses for them. The layer never sees the right-hand side.
MODES = {"exact": "keyword", "meaning": "semantic", "combined": "auto"}

#: The verbs this target does not offer, each with the reason it is absent. The
#: docstring argues both at length; these are the one-line forms that reach the
#: artifact, and they are different reasons — one surface does not exist, the
#: other exists and would over-claim if it were mapped.
UNSUPPORTED = {
    "uninstall": (
        "this target has no uninstall surface. SPEC.md §5.2.7 says in as many words "
        "that its maintenance purge is not a stand-in the harness may call to "
        "manufacture a clean result, so nothing is substituted for it"
    ),
    "resume": (
        "nothing maps onto it. The only action that continues an interrupted build is "
        "also the full rebuild and the repair — on a damaged index it deletes the "
        "unreadable file first — so mapping resume onto it would smuggle a destructive "
        "rebuild into the one verb the ruling says never rebuilds, invisibly, because "
        "on a healthy checkpointed index it really does just resume"
    ),
}

#: The two foreign schema stamps, and they are this target's numbers rather than
#: this harness's: `bench/smoke_upstream.py`'s `_restamp_and_open` has been
#: writing exactly these since the damage-prevention half was first asserted, and
#: a second pair would test a different thing while claiming to test the same one.
#: Older is the one that matters — it is what every user holds the day the build's
#: schema version is incremented.
FOREIGN_STAMPS = {RESTAMP_OLDER: "0", RESTAMP_NEWER: "9999"}

#: The key this target keeps its index schema version under, in the index's own
#: `meta` table. Target knowledge, which is why it is here and not in the layer.
STAMP_KEY = "schemaVersion"


def _payload(response: dict) -> dict:
    """The structured body of a tool reply, whichever way this transport carries it."""
    import json

    result = response.get("result", response)
    if "structuredContent" in result:
        return result["structuredContent"]
    for block in result.get("content", []):
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return {"text": block["text"][:4000]}
    return result


class Zoteus:
    def __init__(self, arena: Path, *, entrypoint: Path, transformers_path: str = "",
                 zotero_data_dir: str = "", seed_index: str = "", timeout: float = 900,
                 posture: Posture | None = None):
        self.arena = Path(arena)
        self.entrypoint = Path(entrypoint)
        self.data_dir = self.arena / "data"
        self.transformers_path = transformers_path
        self.zotero_data_dir = zotero_data_dir
        self.seed_index = Path(seed_index) if seed_index else None
        self.timeout = timeout
        self.server: Server | None = None
        #: See `beaver.Beaver._posture`: `None` unwraps the spawn (every test
        #: that builds this adapter directly gets that), `run.py` always
        #: resolves a real `Posture` first (ticket 0625).
        self._posture = posture
        self.declaration = Declaration(
            name="zoteus",
            revision=_revision(self.entrypoint),
            derived_state_roots=(self.data_dir,),
            query_transport=(
                "an MCP server over stdio JSON-RPC; the semantic-search tool is called "
                "with the mode the harness asked for, mapped onto this target's mode names"
            ),
            default_configuration=(
                "the local on-device embedder, the SQLite index backend, no automatic "
                "refresh, full text on, read-only against the library. The one input "
                "that is not a default is the path to the on-device model runtime, which "
                "the built checkout does not vendor: it is passed in, and recorded here, "
                f"as {transformers_path or '(not supplied — the target falls back to keyword-only)'}"
            ),
            process=(
                "node runs the built entrypoint as a child process, spoken to over stdio; "
                "it is started before the verbs and terminated after them"
                + (f"; the data directory is seeded from {self.seed_index} before the "
                   "first start, so goal 2's clauses have an index in service to be "
                   "about" if self.seed_index else
                   "; the data directory starts empty, so any clause about an index "
                   "already in service has nothing to read")
            ),
            unsupported=UNSUPPORTED,
            not_derived_state=(
                (Path(zotero_data_dir), "the user's own library, which R15 excludes from "
                                        "derived state") if zotero_data_dir else
                (Path("/nonexistent"), "placeholder: no library directory was supplied"),
            ) if zotero_data_dir else (),
        )

    # -- adapter-declared harness setup, deliberately not an interface verb ----

    def _env(self) -> dict[str, str]:
        env = {
            "ZOTEUS_EMBEDDINGS": "local",
            "ZOTEUS_DATA_DIR": str(self.data_dir),
            "ZOTEUS_INDEX_BACKEND": "sqlite",
            "ZOTEUS_INDEX_AUTO_REFRESH": "false",
            "ZOTEUS_INDEX_FULLTEXT": "1",
            "ZOTEUS_READ_ONLY": "true",
        }
        if self.transformers_path:
            env["ZOTEUS_TRANSFORMERS_PATH"] = self.transformers_path
        if self.zotero_data_dir:
            env["ZOTERO_DATA_DIR"] = self.zotero_data_dir
        return env

    def _seed(self) -> None:
        """Put a prebuilt index in place before the first start, if one was supplied.

        Copied only when the data directory holds no index yet, so a restart —
        which is what R23's clause turns on — reopens the index the previous run
        left, foreign stamp and all, rather than silently getting a fresh one.
        """
        if self.seed_index is None or self._index() is not None:
            return
        shutil.copyfile(self.seed_index, self.data_dir / self.seed_index.name)

    def _index(self) -> Path | None:
        """This target's index file in the data directory, or None if there is none.

        Found by opening each candidate and asking whether it carries the stamp,
        rather than by matching a filename: the name has changed across versions
        of this target and will change again, and a probe that silently finds
        nothing would report "no index" for a build whose file was merely renamed.
        """
        for candidate in sorted(self.data_dir.glob("*.sqlite")):
            try:
                con = sqlite3.connect(f"file:{candidate}?mode=ro", uri=True)
                try:
                    row = con.execute(
                        "SELECT value FROM meta WHERE key=?", (STAMP_KEY,)).fetchone()
                finally:
                    con.close()
            except sqlite3.Error:
                continue
            if row is not None:
                return candidate
        return None

    @contextmanager
    def running(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._seed()
        cmd = ["node", str(self.entrypoint)]
        env = self._env()
        # See `zotero_mcp.ZoteroMCP.running`'s identical comment (same
        # `mcp_drive.Server` transport): only the process spawn crosses the
        # identity boundary (ticket 0625, Action 1); `env` is unchanged by
        # wrapping and still reaches `Server` exactly as before, `wrap` only
        # adds `--preserve-env=<names>` to `cmd`, and a refused posture raises
        # before anything starts rather than falling back to an unwrapped spawn.
        if self._posture is not None:
            cmd = self._posture.wrap(cmd, {**os.environ, **env})
        self.server = Server(cmd, env, timeout=self.timeout)
        self.server.handshake()
        try:
            yield
        finally:
            self.server.p.terminate()
            self.server = None

    def _call(self, tool: str, arguments: dict) -> dict:
        if self.server is None:
            raise RuntimeError("the target's process is not running; use running()")
        return _payload(self.server.call("tools/call", {"name": tool, "arguments": arguments}))

    # -- the seven verbs ------------------------------------------------------

    def install(self) -> dict:
        """This target's install is the pinned build plus a fresh data directory.

        There is no install surface to call: the derived state materializes when
        the process starts against an empty data directory, which `running()`
        has done by the time this is reached. Acquiring the build itself is out
        of scope for an adapter — it is a network operation, and the reviewed
        revision in `UPSTREAM` already satisfies it.
        """
        return {
            "entrypoint": str(self.entrypoint),
            "data_dir": str(self.data_dir),
            "materialized": sorted(p.name for p in self.data_dir.iterdir())
            if self.data_dir.is_dir() else [],
        }

    def uninstall(self) -> dict:
        raise UnsupportedVerb(self.declaration.name, "uninstall")

    def configure(self) -> dict:
        """Report the configuration in effect. It was applied at process start,
        which is where this target takes its configuration, so this changes
        nothing — reporting is the whole of it."""
        return {"applied_at": "process start", "environment_keys": sorted(self._env())}

    def query(self, q: str, mode: str, limit: int) -> dict:
        return self._call("zotero_semantic_search", {
            "q": q, "mode": MODES[mode], "limit": limit, "auto_build": False,
        })

    def status(self) -> dict:
        """The normalized shape the layer reads, plus this target's own report.

        The two calls behind it are this adapter's business: one names the
        embedder the configuration resolved to, the other says whether it is
        actually running. A configuration that says local and a process that
        fell back to keyword-only are the same file and different facts, which
        is why both are read.
        """
        whoami = self._call("zotero_whoami", {})
        index = self._call("zotero_index", {"action": "status"})
        embeddings = whoami.get("embeddings") or {}
        effective = embeddings.get("effective")
        return {
            "embedding": {
                "locality": {"local": "local"}.get(effective, "remote" if effective else "none"),
                "active": index.get("embedderActive") is True,
                "model": index.get("embedderModel"),
            },
            # Explicitly None rather than absent. This target's status carries
            # coverage and phase but no `work.<stage>.<trigger>.<outcome>` counter
            # of any kind — measured on 2026-09-03, all 29 top-level keys read,
            # no `work` or `counters` object anywhere. Saying so here is the
            # difference between an adapter that answered and one that forgot,
            # and it is what makes R3's `not-run` a finding rather than a gap.
            "work": None,
            "reported": {"whoami_embeddings": embeddings, "index_embedder": index.get("embedder")},
        }

    def pause(self) -> dict:
        """Halt background work. Durable in the sense R22 asks for: the cancel
        flag itself is in memory, but the interrupted work leaves a checkpoint on
        disk, the partial data stays searchable, and nothing auto-resumes."""
        return {
            "stopped": self._call("zotero_index", {"action": "stop"}),
            "work_checkpointed": True,
            "auto_resumes": False,
        }

    def resume(self) -> dict:
        raise UnsupportedVerb(self.declaration.name, "resume")

    # -- perturbation: adapter-declared harness setup, not an eighth verb -----

    def perturb(self, what: str) -> dict:
        """Make something happen to this target that no verb can express.

        Called with the process stopped: the restamp writes to the index file,
        and writing to a database another process holds open is a different
        experiment from the one R23 asks for.
        """
        if what in FOREIGN_STAMPS:
            return self._restamp(what)
        if what == RESET_TO_SEEDED_INDEX:
            return self._reset_to_seeded_index()
        if what in (EDIT_ONE_ITEM, RESYNC_IDENTICAL_BYTES):
            raise NotImplementedError(
                "this would write to the user's own Zotero library, which this target is "
                "configured read-only against and which R15 excludes from derived state; "
                "and the clause it serves reads work counters this target does not "
                "report, so driving it would produce an undecidable run rather than a "
                "verdict"
            )
        raise NotImplementedError(f"this adapter has no way to do {what!r}")

    def _stamp(self, index: Path) -> str | None:
        """The schema version this index file currently carries, or None."""
        con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM meta WHERE key=?", (STAMP_KEY,)).fetchone()
        finally:
            con.close()
        return row[0] if row else None

    def _reset_to_seeded_index(self) -> dict:
        """Put the prebuilt index back, so each of R23's two arms starts where the other did.

        `_seed` deliberately copies only into a data directory that holds no index,
        because a restart must reopen the file the previous run left. That is the
        right rule between the halves of one arm and the wrong one between arms:
        the second direction would then be applied to whatever the first arm's
        restart produced. This is the explicit request for the starting state, and
        it is the only thing in this adapter that overwrites derived state.
        """
        if self.seed_index is None:
            raise NotImplementedError(
                "this target was given no prebuilt index to start from, so the harness "
                "cannot put its data directory back into the state R23's clause is about; "
                "pass one with --seed-index"
            )
        existing = self._index()
        was = self._stamp(existing) if existing is not None else None
        destination = self.data_dir / self.seed_index.name
        shutil.copyfile(self.seed_index, destination)
        return {
            "perturbation": RESET_TO_SEEDED_INDEX,
            "index": destination.name,
            "index_found_before_reset": existing.name if existing is not None else None,
            "stamp_before_reset": was,
            "stamp_after_reset": self._stamp(destination),
            "file_deleted_by_hand": False,
        }

    def _restamp(self, direction: str) -> dict:
        """Write a foreign schema version into the index, the way a version change would.

        The same operation `bench/smoke_upstream.py` performs for the
        damage-prevention half, done here on the index in place rather than on a
        copy: what R23's serving clause asks is what this build does with the file
        it finds, and a copy set aside is not the file it finds.
        """
        index = self._index()
        if index is None:
            raise NotImplementedError(
                "no index carrying a schema stamp exists in this data directory, so there "
                "is nothing to restamp; seed the arena with a built index first"
            )
        was = self._stamp(index)
        con = sqlite3.connect(index)
        try:
            con.execute("UPDATE meta SET value=? WHERE key=?",
                        (FOREIGN_STAMPS[direction], STAMP_KEY))
            con.commit()
        finally:
            con.close()
        return {
            "perturbation": direction,
            "index": index.name,
            "was": was,
            "restamped_to": FOREIGN_STAMPS[direction],
            "file_deleted_by_hand": False,
        }


def _revision(entrypoint: Path) -> str:
    """The built revision under test, so an artifact says what it measured."""
    package = entrypoint.resolve().parent.parent / "package.json"
    if package.is_file():
        import json

        try:
            return str(json.loads(package.read_text()).get("version") or "unknown")
        except ValueError:
            return "unknown"
    return "unknown"


def build(name: str, arena: Path, *, entrypoint: str = "", transformers_path: str = "",
          zotero_data_dir: str = "", seed_index: str = "", posture: Posture | None = None,
          **_opts) -> Zoteus:
    if not entrypoint:
        raise SystemExit(
            "this adapter needs the path to the target's built entrypoint (--entrypoint). "
            "It is not defaulted: a guessed path is how a run measures a build nobody chose."
        )
    return Zoteus(
        Path(arena),
        entrypoint=Path(entrypoint),
        transformers_path=transformers_path or os.environ.get("ZOTEUS_TRANSFORMERS_PATH", ""),
        zotero_data_dir=zotero_data_dir,
        seed_index=seed_index,
        posture=posture,
    )
