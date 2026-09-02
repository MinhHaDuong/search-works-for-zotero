"""The adapter for `54yyyu/zotero-mcp`, the acceptance layer's second target.

Ticket 0585. The contract is `interface.py`, owned by `SPEC.md` §5.2.8 and the
`DECISIONS.md` entry ratified 2026-09-02; neither is restated here. What this
module holds is a declaration and the minimal transport needed to invoke the
surfaces it declares — no patch or workaround, no non-default option, no access
unavailable to the target's own users, and no scoring of a result.

**The pin, and why one string cannot carry it.** The distribution is
`zotero-mcp-server`, which is not the repository's name; `pip install
zotero-mcp` installs somebody else's package. Version 0.11.0 is git tag
`v0.11.0`, commit `3cb3e2e34fab1fab7dc252102b03cdeec9915b78`, which was also
`origin/main` when the tree was cloned on 2026-09-02. The `server.json` committed
in that tree still says 0.9.1 and is not the version. But the behaviour this
declaration describes is not this package's alone: two of its three default
egress calls and three of its five derived-state roots are made by `fastmcp`,
`chromadb` and `onnxruntime` rather than by any line of zotero-mcp. A revision
string cannot pin those, so the resolved closure that produced these
measurements is recorded beside this file in `zotero-mcp-0.11.0-core.lock` and
`revision` points at it.

**Why HOME is the sandbox, and why that belongs under `process`.** There is no
target option that relocates this target's state. `--config-path` moves part of
one root: `chroma_client.get_chroma_client` constructs `ChromaClient` with no
`persist_directory`, so `ChromaClient.__init__` falls back to
`Path.home() / ".config" / "zotero-mcp"` and creates it (read from source,
`chroma_client.py`), and `semantic_search.update_database` hardcodes
`Path.home()` for its `update.lock` (read from source, `semantic_search.py`).
Setting `HOME` is therefore the only sandbox this target has, and it is a
property of the process the harness starts, not a configuration the target
offers. Saying so explicitly is load-bearing: the alternative reading — that the
residue sweep runs against the operator's own `$HOME` — is destructive, and
`__init__` refuses that construction rather than trusting the reader.

**The ambient environment is part of the default configuration, so it is
scrubbed.** The target reads 28 environment variables, among them
`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ZOTERO_API_KEY` and `ZOTERO_LOCAL`
(enumerated by grepping `os.getenv`/`os.environ.get` over `src/`), and upstream
carries a comment about a `GOOGLE_API_KEY` "leaked from another tool" silently
changing the embedding configuration. An operator who has any of these exported
would otherwise measure a configuration no ordinary user gets. Blanking them is
not a non-default option; it is what makes "default configuration" true.

**What this adapter found about the interface** — ticket 0585's fourth action,
recorded here because the next adapter's author reads this file and not the
report:

1. `Declaration.unsupported` is a set of VERBS, so it has no way to say that a
   MODE is absent. `MODES` treats exact / meaning / combined as symmetric. On
   this target, in its default install, `combined` does not exist anywhere —
   grepping `src/` for `rrf`, `reciprocal.rank` and `bm25` returns nothing and
   every hit for `combined` is English prose about mutually exclusive arguments
   — and `meaning` needs an optional extra that the documented install command
   does not pull. So `query` is offered while two of its three modes are not,
   and the declaration can say that only in prose. `query()` therefore returns
   `mode_served` and a `why`, and never a verdict.
2. R33's clause is "the mode selected MUST be the mode served", and this target
   can be measured against it, in the falsifiable direction. `zotero_search_items`
   runs a four-strategy cascade when its first attempt returns nothing:
   simplified query, author-only, `qmode="everything"` (Zotero-side full text),
   then semantic search if a config file exists. Nothing turns it off — the one
   documented bypass, `collection_key`, is itself a non-default option that
   narrows the search. Correcting the reconnaissance note this adapter was
   handed: the escalation is **not silent**. The reply carries a prose `*Note:
   Original search for '<q>' returned no results …*` line naming the strategy
   that answered (read from source, and the four strings are in
   `_ESCALATION_NOTES`). The disclosure is human-readable only — there is no
   machine field — which is why `query()` parses the note it is given rather
   than inferring anything.
3. `derived_state_roots` is documented as where the target creates derived
   state, and three of this target's five roots are created by dependencies at
   paths zotero-mcp's own source never names: a 167 MB ONNX model cache under
   `~/.cache/chroma`, a `fastmcp` version cache, and an `onnxruntime` device-id
   store under a `~/.cache/Microsoft` path. They are declared as roots here,
   because the question the field asks is where state appears when this target
   runs, and authorship inside the process tree does not change that. But the
   field cannot record the distinction, and `not_derived_state` is the wrong
   home for it — its documented purpose is user data and external configuration,
   and a dependency's model cache is neither. zoteus does not have this problem
   because it vendors its embedder under its own data directory; this is where
   the interface most visibly assumes zoteus's architecture.
4. An unsupported verb records no REASON — **fixed, ticket 0597.** `pause` and
   `resume` are absent here, and the reason is a finding rather than a gap: in
   the default configuration this target does no unattended indexing at all, so
   there is no background work to pause. That is architecturally the opposite of
   a target which has background work and exposes no control over it, and
   `unsupported` used to put both in the same cell. It now carries the reason,
   mirroring `not_derived_state`'s `(value, why)` shape as this note proposed,
   and the reason reaches the artifact on every `not-offered` verdict.

**Two states measured here that a short run does not show.** `status`, not
`install`, is what first creates derived state on a virgin HOME: `db-status`
writes `~/.config/zotero-mcp/chroma_db/chroma.sqlite3` before anything has been
indexed. And the lifespan's schema refresh is a fire-and-forget task, so
`~/.cache/zotero-mcp/schema.json` appears seconds after `initialize` returns —
measured here, a serve session terminated straight after `tools/list` left only
the `fastmcp` cache behind, while the same session with a 25-second dwell left
the schema cache too. A residue sweep that stops the process the moment its
calls are done will not see root 2.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from ..interface import Declaration, UnsupportedVerb

#: The distribution name on PyPI, which is NOT the repository's name.
DISTRIBUTION = "zotero-mcp-server"
VERSION = "0.11.0"

#: Tag `v0.11.0` in `54yyyu/zotero-mcp`; `origin/main` at clone time, 2026-09-02.
COMMIT = "3cb3e2e34fab1fab7dc252102b03cdeec9915b78"

#: The resolved closure the measurements ran against, recorded because the
#: revision above pins only one of the packages whose behaviour is observed.
LOCK = Path(__file__).with_name(f"zotero-mcp-{VERSION}-core.lock")

#: `bench/mcp_drive.py`, the repository's stdio JSON-RPC driver. It drives this
#: target unchanged — measured 2026-09-02: clean `initialize`, 38 tools listed.
#: It is loaded by path rather than imported, because `bench/` is not a package
#: and because a declaration must stay readable on a machine where nothing is
#: installed: nothing above this line imports it.
MCP_DRIVE = Path(__file__).resolve().parents[2] / "mcp_drive.py"

#: Every environment variable the target reads, blanked before the process
#: starts so that an operator's exported key cannot silently reconfigure it.
#: Enumerated by grepping `os.getenv` and `os.environ.get` over the target's
#: `src/` at the pinned commit. Empty rather than deleted because every read
#: site treats the empty string as absent (read from source: the `ZOTERO_LOCAL`
#: membership test, `schema._cache_path`'s `or` fallback, `_lock_timeout`'s
#: `.strip()` guard, `_app`'s `getattr(logging, "", WARNING)`), and because
#: `mcp_drive.Server` merges over `os.environ` and offers no delete.
TARGET_ENVIRONMENT = (
    "APPDATA", "GEMINI_API_KEY", "GEMINI_BASE_URL", "GOOGLE_API_KEY",
    "LOCALAPPDATA", "OLLAMA_BASE_URL", "OPENAI_API_KEY", "OPENAI_BASE_URL",
    "USERNAME", "XDG_CACHE_HOME", "ZOTERO_API_KEY", "ZOTERO_CLI_DEBUG",
    "ZOTERO_DB_PATH", "ZOTERO_EMBEDDING_MODEL", "ZOTERO_LIBRARY_ID",
    "ZOTERO_LIBRARY_TYPE", "ZOTERO_LOCAL", "ZOTERO_LOCAL_PORT",
    "ZOTERO_MCP_CONTACT_EMAIL", "ZOTERO_MCP_FORCE_UPDATE",
    "ZOTERO_MCP_LOCK_TIMEOUT", "ZOTERO_MCP_LOG_LEVEL",
    "ZOTERO_MCP_SCHEMA_CACHE", "ZOTERO_MCP_SCHEMA_REFRESH",
    "ZOTERO_NO_CLAUDE", "ZOTERO_PDF_MAXPAGES", "ZOTERO_SEARCH_BACKEND",
    "ZOTERO_TOKENS_PER_MINUTE",
    # Not read by the target, but they decide which interpreter and which
    # site-packages the console script ends up running under.
    "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV",
)

#: The four strategies `zotero_search_items` escalates through, keyed by the
#: substring its own disclosure note carries, and the mode each one serves. Read
#: from source at the pinned commit; the note is prose, so this is the only
#: reading available and it is deliberately a lookup rather than an inference.
_ESCALATION_NOTES = (
    ("semantically related papers found via AI-powered search", "meaning"),
    ("via full-text search", "exact"),
    ("via simplified to", "exact"),
    ("via author only", "exact"),
)

#: The tool each reachable mode is served by. `combined` has no entry because
#: this target has no fusion of any kind — see the module docstring, finding 1.
_MODE_TOOL = {"exact": "zotero_search_items", "meaning": "zotero_semantic_search"}

#: The configuration `zotero-mcp setup` writes when every prompt is left at its
#: first option: the bundled embedder, no automatic update. Written to the file
#: the README documents users editing by hand, which is the access an ordinary
#: user has. The interactive wizard itself is a stdin dialogue and is
#: deliberately not driven — scripting a prompt loop would be a workaround.
DEFAULT_CONFIG = {
    "semantic_search": {
        "embedding_model": "default",
        "update_config": {"auto_update": False, "update_frequency": "manual"},
    }
}


class TransportTimeout(RuntimeError):
    """A JSON-RPC call did not answer inside the adapter's budget.

    `mcp_drive.Server.call` stores a `timeout` and never reads it: it loops on
    `stdout.readline()`, which blocks forever. Two of this target's own paths
    can sit there — a cold semantic query downloads a 79 MB ONNX model, and a
    contended Zotero local API holds an in-process lock for 45 seconds — and a
    harness that hangs reports nothing at all, where the honest answer is
    `not-run`. So every call this adapter makes is bounded, and the bound is the
    adapter's, not the driver's.
    """


def _load_mcp_drive():
    """The repository's stdio driver, loaded by path and only when a verb needs it.

    Import-time cost is the point: `interface.Declaration` must be readable on a
    machine with no target installed, and that question should not depend on
    whether a sibling harness file happens to be importable.
    """
    spec = importlib.util.spec_from_file_location("mcp_drive", MCP_DRIVE)
    if spec is None or spec.loader is None:  # pragma: no cover - path is fixed
        raise RuntimeError(f"cannot load the stdio driver at {MCP_DRIVE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declaration(home: Path) -> Declaration:
    """The declaration for a target sandboxed at `home`.

    A free function because the declaration is the readable half of this module:
    a contract check should be able to obtain it without constructing transport,
    starting a process, or having the target installed anywhere.
    """
    home = Path(home)
    return Declaration(
        name="54yyyu/zotero-mcp",
        revision=(
            f"{DISTRIBUTION}=={VERSION} (repository 54yyyu/zotero-mcp, tag v{VERSION}, "
            f"commit {COMMIT}). One string does not pin what was measured: two of the "
            f"three default egress calls and three of the five derived-state roots "
            f"below come from fastmcp, chromadb and onnxruntime rather than from this "
            f"package. The resolved closure is recorded in {LOCK.name}, beside this "
            f"adapter. The repository's server.json is stale at 0.9.1 and is not the "
            f"version; the PyPI distribution is not named after the repository."
        ),
        derived_state_roots=(
            # 1. The target's own directory: config.json, chroma_db/,
            #    fulltext_cache/, openai_batches/, gemini_batches/, update.lock.
            #    `status` rather than `install` is what first creates it —
            #    `db-status` on a virgin HOME writes chroma_db/chroma.sqlite3.
            home / ".config" / "zotero-mcp",
            # 2. The Zotero schema cache (+ .last-attempt). Honours
            #    XDG_CACHE_HOME, which is blanked here so it lands under HOME.
            #    Written by a fire-and-forget task seconds after `initialize`
            #    returns, not before — measured 2026-09-02.
            home / ".cache" / "zotero-mcp",
            # 3. 167 MB of ONNX model, created by chromadb on the first embed.
            #    Not named anywhere in the target's source.
            home / ".cache" / "chroma",
            # 4. fastmcp's own version cache. Created on every serve, including
            #    one that answers a single tools/list and stops.
            home / ".local" / "share" / "fastmcp",
            # 5. onnxruntime's device id — a stable UUID at mode 0600 — and a
            #    sqlite database beside it. Whether the id is ever transmitted
            #    was NOT measured; it is recorded here as a file that appears,
            #    which is the only claim this adapter can support.
            home / ".cache" / "Microsoft" / "DeveloperTools",
        ),
        query_transport=(
            "stdio JSON-RPC to `<venv>/bin/zotero-mcp serve --transport stdio` "
            "(stdio is the default transport), driven by bench/mcp_drive.py "
            "unchanged. `initialize` is clean and 38 tools are listed with Zotero "
            "entirely absent — measured 2026-09-02. Two properties of that "
            "transport the caller must know: fastmcp prints an ANSI banner and a "
            "PyPI update notice on stderr before `initialize` returns, and "
            "`Server.call` has no timeout of its own, so this adapter bounds every "
            "call and raises TransportTimeout rather than hanging. Retrieval is "
            "two tools and no fusion: `zotero_search_items` (substring over title, "
            "creators and year; qmode='everything' widens to Zotero's own "
            "server-side full text) serves `exact`, `zotero_semantic_search` serves "
            "`meaning` where the [semantic] extra is installed, and `combined` has "
            "no implementation at all — no BM25, no reciprocal-rank fusion, nothing "
            "that merges two lists (grepped `src/` for rrf, reciprocal.rank and "
            "bm25 at the pinned commit: zero hits). `exact` is advisory rather than "
            "binding: on an empty result set the tool escalates through a "
            "four-strategy cascade ending in semantic search, no option disables "
            "it, and the escalation is disclosed as a prose note in the reply and "
            "in no machine-readable field."
        ),
        default_configuration=(
            f"`pip install {DISTRIBUTION}` — the README's own command — with none of "
            f"the [semantic], [pdf], [scite] or [all] extras, at the closure recorded "
            f"in {LOCK.name}. Consequences that decide what this target can be asked: "
            f"semantic search is absent from the default install, so `meaning` is "
            f"unreachable until an extra the documented command does not pull is added; "
            f"no configuration file exists, so the server's startup auto-update path "
            f"returns before importing ChromaDB and no unattended indexing runs; and "
            f"ZOTERO_LOCAL is unset, so the client addresses the Zotero Web API rather "
            f"than 127.0.0.1:23119. `configure()` writes "
            f"~/.config/zotero-mcp/config.json, the file the README documents users "
            f"editing by hand, with the values `zotero-mcp setup` produces when every "
            f"prompt is left at its first option. Three default egress calls: "
            f"https://api.zotero.org/schema on every start behind a 7-day TTL "
            f"(bodyless GET, carrying no library and no query text); fastmcp's own "
            f"PyPI update check to https://pypi.org/pypi/fastmcp/json behind a 12-hour "
            f"TTL, which zotero-mcp documents nowhere; and, once the semantic extra is "
            f"present, a 79.3 MB model download from chroma-onnx-models.s3.amazonaws.com "
            f"on the first embed — R10's named exception, and named by this target in "
            f"no place a user would find it. Every hosted embedding path (OpenAI, "
            f"Gemini, their batch APIs, Ollama, HuggingFace) is off by default."
        ),
        process=(
            "HOME is the sandbox, and it is the only one this target has: "
            "`get_chroma_client` builds its ChromaClient with no persist_directory "
            "so the store falls back to Path.home()/.config/zotero-mcp, and "
            "`update_database` hardcodes Path.home() for its lock, which is why "
            "--config-path relocates part of one root and nothing else. HOME is a "
            "property of the process the harness starts, not an option the target "
            "offers, which is why it is declared here. The adapter refuses to be "
            "constructed on the operator's own HOME: with no sandbox, the residue "
            "sweep this declaration exists to serve would run against the operator's "
            f"real state. Start: `<venv>/bin/zotero-mcp serve --transport stdio` with "
            f"HOME set and the {len(TARGET_ENVIRONMENT)} variables the target reads "
            "blanked, so an ambient OPENAI_API_KEY or ZOTERO_LOCAL cannot make the "
            "measured configuration something other than the default. Stop: "
            "terminate, then kill on a 10-second grace. The lifespan's schema refresh "
            "is a background task, so a session stopped immediately after its last "
            "call leaves less residue than the same session held a few seconds "
            "longer — measured 2026-09-02, and a residue sweep has to allow for it."
        ),
        unsupported={
            "uninstall": (
                "no uninstall surface: the documented removal is uninstalling the "
                "package, which is not a verb this target offers and which the harness "
                "will not stand in for"
            ),
            "pause": (
                "there is no background work to pause. In the default configuration "
                "this target does no unattended indexing at all — all three background "
                "paths are gated on configuration that is off by default, and indexing "
                "is a foreground command a user runs. That is the architectural "
                "opposite of a target with background work and no control over it"
            ),
            "resume": "absent for pause's reason: there is nothing to resume",
        },
    )


class ZoteroMCP:
    """Transport for the declaration above, and nothing else.

    Constructed on a sandbox HOME and a virtualenv prefix. Neither is a target
    option: the first is the only sandbox mechanism this target has, the second
    is where `install` put it.
    """

    def __init__(self, home: Path, venv: Path, timeout: float = 180.0,
                 config: dict | None = None) -> None:
        home = Path(home).resolve()
        if home == Path.home().resolve():
            raise ValueError(
                "refusing to run 54yyyu/zotero-mcp against the operator's own HOME. "
                "HOME is this target's only sandbox (see the declaration's `process`), "
                "so a run without one writes five derived-state roots into the "
                "operator's real state and the residue sweep would then delete from it."
            )
        self.home = home
        self.venv = Path(venv).resolve()
        self.timeout = float(timeout)
        self.config = DEFAULT_CONFIG if config is None else config
        self.declaration = declaration(home)
        self._server = None

    # ---- transport -------------------------------------------------------

    @property
    def executable(self) -> Path:
        return self.venv / "bin" / "zotero-mcp"

    @property
    def python(self) -> Path:
        return self.venv / "bin" / "python"

    def environment(self) -> dict[str, str]:
        """HOME plus a blank for every variable the target reads.

        `mcp_drive.Server` merges this over `os.environ` and has no way to delete
        a name, so "absent" is spelled as the empty string. Each read site in the
        target treats that as absent; the docstring on TARGET_ENVIRONMENT names
        the four that were read to check it.
        """
        env = {name: "" for name in TARGET_ENVIRONMENT}
        env["HOME"] = str(self.home)
        return env

    def semantic_installed(self) -> bool:
        """Whether the optional [semantic] extra is present in this venv.

        Asked of the venv rather than of the target, because the target answers
        it only at call time and only in prose. `chromadb` is the extra's first
        dependency and the one every semantic path imports.
        """
        return bool(list(self.venv.glob("lib/python*/site-packages/chromadb")))

    @contextmanager
    def running(self):
        """Start the server, yield, stop it. Harness setup, not an interface verb."""
        drive = _load_mcp_drive()
        cmd = [str(self.executable), "serve", "--transport", "stdio"]
        self.home.mkdir(parents=True, exist_ok=True)
        server = drive.Server(cmd, self.environment(), self.timeout)
        self._server = server
        try:
            self._bounded(server, "initialize", handshake=True)
            yield
        finally:
            self._server = None
            server.p.terminate()
            try:
                server.p.wait(10)
            except subprocess.TimeoutExpired:  # pragma: no cover - grace path
                server.p.kill()

    def _bounded(self, server, method: str, params: dict | None = None,
                 handshake: bool = False):
        """One JSON-RPC call under this adapter's own timeout.

        The driver's `call` blocks on `readline()` forever; a worker thread with
        a join is the smallest bound that does not modify shared harness code.
        The thread is a daemon: on a timeout the process is about to be
        terminated anyway, and a non-daemon reader would outlive it.
        """
        box: dict = {}

        def run():
            try:
                box["ok"] = server.handshake() if handshake else server.call(method, params)
            except Exception as exc:  # noqa: BLE001 - reported, never swallowed
                box["err"] = f"{type(exc).__name__}: {exc}"

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(self.timeout)
        if worker.is_alive():
            raise TransportTimeout(
                f"{method} did not answer in {self.timeout:g}s against "
                f"{self.declaration.name}"
            )
        if "err" in box:
            raise RuntimeError(f"{method} failed: {box['err']}")
        return box["ok"]

    def _tool(self, name: str, arguments: dict) -> dict:
        """Call one MCP tool, inside a session if the caller opened one."""
        if self._server is not None:
            return self._bounded(self._server, "tools/call",
                                 {"name": name, "arguments": arguments})
        with self.running():
            return self._bounded(self._server, "tools/call",
                                 {"name": name, "arguments": arguments})

    @staticmethod
    def _text(reply: dict) -> str:
        """The text of a tools/call reply, unscored and unparsed beyond joining.

        The target answers every tool in this adapter's reach with prose, so this
        is where an assertion's evidence comes from. Nothing here judges it.
        """
        content = (reply.get("result") or {}).get("content") or []
        return "\n".join(part.get("text", "") for part in content
                         if isinstance(part, dict))

    # ---- the seven verbs -------------------------------------------------

    def install(self) -> dict:
        """`pip install zotero-mcp-server==0.11.0` into this adapter's venv.

        The README's own command, at the pinned version, with no extra. `uv` is
        used when it is on PATH because it resolves the same closure faster; the
        stdlib `venv` plus the venv's own `pip` is the fallback, and the returned
        record says which ran. A non-zero return code is reported, not raised:
        the caller's assertion decides what a failed install means, and an
        exception escaping here would be scored as a crash of the harness.
        """
        self.home.mkdir(parents=True, exist_ok=True)
        uv = shutil.which("uv")
        spec = f"{DISTRIBUTION}=={VERSION}"
        if uv:
            steps = [[uv, "venv", str(self.venv)],
                     [uv, "pip", "install", "--python", str(self.python), spec]]
        else:
            steps = [[sys.executable, "-m", "venv", str(self.venv)],
                     [str(self.venv / "bin" / "pip"), "install", spec]]
        env = {**os.environ, **self.environment()}
        ran = []
        for step in steps:
            done = subprocess.run(step, capture_output=True, text=True, env=env,
                                  check=False)
            ran.append({"argv": step, "returncode": done.returncode,
                        "stderr": done.stderr[-2000:]})
            if done.returncode != 0:
                break
        return {
            "verb": "install",
            "installer": "uv" if uv else "venv+pip",
            "distribution": DISTRIBUTION,
            "version": VERSION,
            "commit": COMMIT,
            "lock": str(LOCK),
            "venv": str(self.venv),
            "home": str(self.home),
            "steps": ran,
            "executable_present": self.executable.exists(),
        }

    def uninstall(self) -> dict:
        """Absent. `pip uninstall` removes the package and leaves every root.

        Grepping `README.md`, `src/` and `docs/` at the pinned commit for
        `uninstall`, case-insensitively, returns zero hits, and the CLI's
        fourteen subcommands (`serve setup update-db batch-status
        openai-batch-status batch-import openai-batch-import db-status db-inspect
        update version setup-info schema-refresh install-skill` — read off
        `--help` here) contain no removal verb. The harness does not delete the
        five roots on the target's behalf: manufacturing a clean result by doing
        a target's work for it is what R15's uninstall clause forbids.
        """
        raise UnsupportedVerb(self.declaration.name, "uninstall")

    def configure(self) -> dict:
        """Write `~/.config/zotero-mcp/config.json` under the sandbox HOME.

        Three configuration channels exist and they are read at different times:
        environment variables at process start, this file on each call, and an
        interactive stdin wizard (`zotero-mcp setup`). The wizard is not driven —
        scripting a prompt dialogue is a workaround, and the README documents
        this file as something users edit by hand, so writing it is access an
        ordinary user has. The content defaults to what the wizard produces when
        every prompt is left at its first option.
        """
        path = self.home / ".config" / "zotero-mcp" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        return {"verb": "configure", "path": str(path), "config": self.config,
                "channel": "config.json (per call); the stdin wizard is not driven"}

    def query(self, q: str, mode: str, limit: int) -> dict:
        """One retrieval call, reporting which mode actually answered.

        `mode_served` is the load-bearing field and the reason this returns a
        dict rather than a list of hits: on this target the selected mode is not
        necessarily the served one. `exact` escalates through a cascade ending in
        semantic search whenever its first attempt is empty, and the only record
        of that is a prose note in the reply, which `_ESCALATION_NOTES` reads. A
        mode with no surface returns `served=False` and a reason; it does not
        raise `UnsupportedVerb`, because `query` IS offered and the declaration
        has no way to mark a mode absent (module docstring, finding 1).
        """
        if mode not in _MODE_TOOL:
            return {"verb": "query", "mode_requested": mode, "mode_served": None,
                    "served": False, "hits": None, "raw": None,
                    "why": ("this target implements no fusion of any kind: no BM25, no "
                            "reciprocal-rank fusion, nothing that merges two ranked "
                            "lists. Grepped `src/` at the pinned commit for rrf, "
                            "reciprocal.rank and bm25 — zero hits; every match for "
                            "'combined' is prose about mutually exclusive arguments.")}
        if mode == "meaning" and not self.semantic_installed():
            return {"verb": "query", "mode_requested": mode, "mode_served": None,
                    "served": False, "hits": None, "raw": None,
                    "why": ("the [semantic] extra is not installed in this venv, and "
                            "the README's documented install command does not pull it. "
                            "The tool is still listed by tools/list and answers with an "
                            "install hint, which is a surface without a capability.")}
        tool = _MODE_TOOL[mode]
        reply = self._tool(tool, {"query": q, "limit": limit})
        raw = self._text(reply)
        served, escalation = mode, None
        for marker, becomes in _ESCALATION_NOTES:
            if marker in raw:
                served, escalation = becomes, marker
                break
        return {"verb": "query", "mode_requested": mode, "mode_served": served,
                "served": True, "tool": tool, "escalation": escalation,
                "escalation_disclosure": "prose note in the reply; no machine field",
                "raw": raw}

    def status(self) -> dict:
        """`zotero_get_search_database_status`, verbatim plus its own field split.

        Offered and thin. The tool is in the `search-admin` toolset, which is in
        `DEFAULT_ON`, and `zotero-mcp db-status` is the same read from the CLI.
        What it answers is a markdown block: collection name, document count,
        embedding model, database path, and four update-configuration lines. What
        it does not answer — read from source at the pinned commit — is a
        denominator, a per-stage split, a record-versus-body coverage split, or a
        pause line. Where the [semantic] extra is absent it returns an install
        hint instead of any of it. `fields` is a mechanical parse of the target's
        own `**Key:** value` lines; the raw block is carried beside it so an
        assertion never has to trust the parse.
        """
        reply = self._tool("zotero_get_search_database_status", {})
        raw = self._text(reply)
        fields = {}
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("**") and ":**" in line:
                key, _, value = line.partition(":**")
                fields[key.lstrip("*").strip()] = value.strip()
        return {"verb": "status", "tool": "zotero_get_search_database_status",
                "semantic_extra_installed": self.semantic_installed(),
                "fields": fields, "raw": raw}

    def pause(self) -> dict:
        """Absent, and the reason is a finding rather than a gap.

        In the default configuration this target does no unattended indexing, so
        there is no background work to pause. All three background paths are
        gated on configuration that is off by default: the server lifespan's
        auto-update returns before importing ChromaDB when no config.json exists,
        the search tool's semantic fallback needs one too, and the CLI's update
        loop is user-invoked. Indexing here is a foreground command a user runs.
        That is architecturally the opposite of a target with background work and
        no control over it, and `Declaration.unsupported` puts both in one cell.
        """
        raise UnsupportedVerb(self.declaration.name, "pause")

    def resume(self) -> dict:
        """Absent, for `pause`'s reason: there is nothing to resume."""
        raise UnsupportedVerb(self.declaration.name, "resume")


#: The targets this module builds. The registry in `__init__.py` walks the
#: package and reads this rather than holding a written-down list, so declaring
#: it here is what makes the adapter selectable — and what lets the
#: target-neutrality guard learn this target's name without being told it.
NAMES = ("zotero-mcp",)


def build(name: str, arena: Path, *, home: str = "", venv: str = "",
          timeout: str | float = 180.0, **_opts) -> ZoteroMCP:
    """Construct the adapter from the driver's opaque `--adapter-option` pairs.

    Neither `home` nor `venv` is defaulted, and the refusal is the point rather
    than an inconvenience. HOME is this target's ONLY sandbox — the Chroma client
    and the update lock resolve the home directory directly, so the config-path
    option relocates part of one root out of five — which means a guessed HOME is
    not a guessed path but the operator's real state, and the residue sweep would
    then be sweeping it. The constructor refuses the operator's own HOME as a
    second line of defence; this is the first.
    """
    if not home:
        raise SystemExit(
            "this adapter needs a sandbox HOME (--adapter-option home=<dir>). It is not "
            "defaulted: HOME is this target's only derived-state boundary, so a guessed "
            "one puts five roots in the operator's real state."
        )
    if not venv:
        raise SystemExit(
            "this adapter needs the virtualenv `install` put the target in "
            "(--adapter-option venv=<dir>). It is not defaulted: a guessed prefix is how "
            "a run measures an installation nobody chose."
        )
    return ZoteroMCP(home=Path(home), venv=Path(venv), timeout=float(timeout))
