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
import sys
from contextlib import contextmanager
from pathlib import Path

from ..interface import Declaration, UnsupportedVerb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mcp_drive import Server  # noqa: E402

NAMES = ("zoteus",)

#: R33's three retrieval modes in the layer's vocabulary, mapped onto the names
#: this target uses for them. The layer never sees the right-hand side.
MODES = {"exact": "keyword", "meaning": "semantic", "combined": "auto"}

#: The verbs this target does not offer. The docstring argues each one.
UNSUPPORTED = frozenset({"uninstall", "resume"})


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
                 zotero_data_dir: str = "", timeout: float = 900):
        self.arena = Path(arena)
        self.entrypoint = Path(entrypoint)
        self.data_dir = self.arena / "data"
        self.transformers_path = transformers_path
        self.zotero_data_dir = zotero_data_dir
        self.timeout = timeout
        self.server: Server | None = None
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

    @contextmanager
    def running(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.server = Server(["node", str(self.entrypoint)], self._env(), timeout=self.timeout)
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
          zotero_data_dir: str = "", **_opts) -> Zoteus:
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
    )
