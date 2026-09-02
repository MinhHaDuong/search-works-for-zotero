"""The adapter for `jlegewie/beaver-zotero`, the acceptance layer's third target.

Ticket 0586. The contract is `interface.py`, owned by `SPEC.md` §5.2.8 and the
`DECISIONS.md` entry ratified 2026-09-02; neither is restated here. What this
module holds is a declaration and the minimal transport needed to invoke the
surfaces it declares — no patch or workaround, no non-default option, no access
unavailable to the target's own users, and no scoring of a result.

This is the roster's first **in-process plugin**: it runs inside the host
application rather than as a server beside it. Almost everything below that is
not about Beaver is about that difference.

**The pin.** Release `v0.23.3`, annotated tag object
`5047008d810abbd93579a6fa2c6877a51791e90c`, commit
`bec71e141413a1a6d6ab80697e398feed8d45f4d`. The artifact installed is the
release's `beaver.xpi`, 7 107 803 bytes, sha256
`e4846067f1d1d400d19893a9fb821aa6ea41999e072e822f951125ce2974915d` — the file
the add-on's own `update.json` names in `update_link`, i.e. the documented user
install path rather than a build of our own. The adapter refuses an artifact
whose digest does not match, because a pin nobody checks is a sentence in a
docstring. Unlike the second target, one string very nearly does pin this one:
the plugin vendors what it needs (MuPDF WASM ships inside the XPI, 10 MB) and
downloads no model, so there is no resolved dependency closure to record beside
it. What the string does *not* pin is the hosted backend the shipped build is
compiled against — see `default_configuration`.

**R10 is expected to fail here, and this adapter is written so that the failure
is Beaver's rather than the harness's.** `DECISIONS.md` adopts this target as a
real product whose free tier states that some processing occurs on its servers,
and instructs that it be run in its normal configuration with R10 expected to
fail where that configuration attempts egress. Nothing here is shaped to avoid
that and nothing is shaped to produce it: the configuration is the one the
shipped `prefs.js` establishes, unmodified.

**We have no account, and that is a measurement condition rather than a gap.**
Every backend call routes through one gate: `getAuthHeaders` calls
`supabase.auth.getSession()` and throws `SessionExpiredError('User not
authenticated')` (`packages/agent-core/src/transport/apiService.ts:281-290`), so
with `extensions.zotero.beaver.userId` empty no call reaches `fetch`
(`apiService.ts:214`). Read the consequence carefully in both directions: it is
why several clauses below are recorded as unreachable rather than failed, and it
is also why an R10 green here would say nothing about the configured product.

**What this adapter found about the interface** — the lane's actual product,
recorded here because the next adapter's author reads this file and not the
report. Findings 1 to 4 are new; 5 and 6 corroborate the second adapter's.

1. **`derived_state_roots` cannot express state written into a file the host
   owns.** The target's preferences are `extensions.zotero.beaver.*` keys
   written through `Zotero.Prefs` (`src/utils/prefs.ts:39-44`) into the host
   application's own `prefs.js`. Measured on a single launch with no account:
   `installedVersion`, `onboardingWelcomeShown`, `onboardingWelcomeShownAt` and
   `deletionJobs` appear there. That is target-created derived state by any
   reading of R15, and it cannot be declared: naming the file as a root claims
   the host's preferences are the target's and makes R15's uninstall clause
   demand their deletion, while leaving it out under-declares. The interface's
   unit is a path; this state is a set of keys inside somebody else's file. It
   is recorded in `not_derived_state`, whose contract says an entry that is
   neither user data nor external configuration is an admission needing an
   argument. This is that admission.

2. **The residue sweep loses most of its discriminating power on an in-process
   plugin, and the declaration cannot buy it back.** The target's state is
   interleaved with its host's inside two directories the host created:
   `beaver.sqlite` sits beside `zotero.sqlite` in one directory, and
   `<profile>/beaver/` beside `cookies.sqlite` in the other. `residue()`
   exempts by path prefix, so the only way to stop the host's several hundred
   files being reported as the target's strays is to exempt the host's two
   directories whole — which also exempts anywhere inside them the target could
   have strayed. There is no third option in the interface: it has no per-file
   ownership notion, and a hand-listed exemption of the host's filenames is the
   gate-scope trap this project has already recorded once. So the exemption is
   taken, and what it costs is written into each entry's reason rather than
   left for a reader to infer from a green. The control arm in
   `tests/test_acceptance_adapter_beaver.py` drives the sweep red by dropping
   one exemption, which is what shows the sweep is looking at all.

3. **A sidecar database is a file family, not a directory.** `residue()` uses
   `Path.relative_to`, so a declared root that is a *file* covers exactly that
   file: `beaver.sqlite` does not cover `beaver.sqlite-wal`. Measured after one
   launch: `beaver.sqlite`, `-wal` and `-shm` all exist. The journal siblings
   are the host's SQLite layer's business, not the target's, and their names
   depend on a journal mode the target does not choose — so they are enumerated
   here by hand and the declaration silently under-declares if that mode ever
   changes. A server target that owns a directory never meets this.

4. **`unsupported` is per verb, so an adapter cannot say a control covers one
   of two background workers.** This target runs two: a background document
   extractor started unconditionally (`src/hooks.ts:259-261`), and embedding
   indexing. The extractor has a real durable pause — the hidden preference
   `extensions.zotero.beaver.backgroundExtractorEnabled`, read per tick
   (`src/services/backgroundExtractor.ts:401`), re-armed by a preference
   observer (`:216`), with in-flight jobs released rather than lost (`:250-295`)
   and job state checkpointed in SQLite (`src/services/database.ts:605-629`).
   Embedding indexing has **no pause at all**; it stops only by losing
   authentication (`react/hooks/useEmbeddingIndex.ts:530-532`) and its only user
   control is a rebuild (`react/atoms/embeddingIndex.ts:136-139`). `SPEC.md`
   §5.2.8 defines pause and resume as the two transitions of *one* durable
   background-work control, and this target has no such single control. The
   verb is therefore declared absent, with the reason carrying the split, and
   the rejected alternative is recorded under `unsupported`.

5. **`derived_state_roots` presumes the target owns its state** — the second
   adapter's finding 3, in a sharper form. There the roots were created by
   dependencies inside the target's own process; here two of the four are
   created inside directories that belong to a different application entirely,
   which the target neither created nor can relocate.

6. **`HOME` is not this target's sandbox, and that inverts the second
   adapter's finding 4.** Measured: with `HOME` pointed at a scratch directory,
   the tree that appears under it — `.cache/mozilla`, `.cache/fontconfig`,
   `.cache/nvidia`, `.mozilla/extensions`, `.config/pulse`, `.zotero`,
   `Downloads` — is Gecko's and the host desktop's, and contains nothing of the
   target's. The boundaries that matter here are the host's `-profile` and
   `-datadir` arguments. `HOME` is still set, because leaving it at the
   operator's own would put the host's caches in real state; it is a sandbox for
   the host, not for the target.

**One coupling this lane did not resolve, reported rather than patched.**
`check_no_egress` requires `subject.returncode == 0` for a pass. The host
application is a desktop process with no argument that makes it start, do a
bounded amount of work and exit; the sibling lane's host-only baseline had to
kill it, and every cell there records returncode 124. This adapter avoids that
by stopping the process from inside its own lifecycle, so `--drive` exits 0
normally — but a plugin adapter that did not would be unable to reach PASS on
that assertion for a reason that has nothing to do with egress. Recorded, not
worked around.

**What was measured on the host alone, and why this artifact is unreadable
without it.** The process under trace is the *host application's*, not the
target's, so a virgin profile makes the host do its own first-run update,
blocklist and certificate work and a warmed profile makes it do far less. The
sibling lane measured the host-only arm — the identical launch, same isolation,
same tracer, **no plugin installed** — and this lane cites it rather than
re-deriving it: virgin profile isolated, 0 off-machine and 426 name lookups;
the same profile a second time, 60; route intact, 456 off-machine and 80 name
lookups. That baseline already fails R10 on its own, which means "Beaver fails
R10" is not by itself a finding about Beaver. The finding is the difference, and
this adapter's job is to make the two arms comparable: the artifact records
which arena state was used, and the reader compares. Nothing is subtracted in
code — that would be the layer scoring a result.
"""

import hashlib
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from ..interface import Declaration, UnsupportedVerb

#: The release under test and the artifact that carries it. `TAG_OBJECT` is the
#: annotated tag; `COMMIT` is what it dereferences to. Both are recorded because
#: a tag can be moved and a commit cannot.
VERSION = "0.23.3"
TAG = f"v{VERSION}"
TAG_OBJECT = "5047008d810abbd93579a6fa2c6877a51791e90c"
COMMIT = "bec71e141413a1a6d6ab80697e398feed8d45f4d"

#: The add-on id, which is also the filename the host reads a sideloaded
#: artifact under. From the artifact's own `manifest.json`.
ADDON_ID = "beaver@jlegewie.com"

#: The artifact `update.json`'s `update_link` names for this version — the
#: documented user install path. Size and digest are checked at construction:
#: an adapter that names a revision and then runs whatever file it was handed
#: has not pinned anything.
ARTIFACT = "beaver.xpi"
ARTIFACT_BYTES = 7107803
ARTIFACT_SHA256 = "e4846067f1d1d400d19893a9fb821aa6ea41999e072e822f951125ce2974915d"

#: The hosts the shipped build is compiled against, read out of the artifact's
#: own `content/reactBundle.js` rather than from the repository's `.env` files,
#: which carry localhost values for development. They are recorded so that a
#: reader of an R10 verdict knows what the configuration under test was pointed
#: at, and they are never contacted by this adapter.
BACKEND_HOSTS = ("api.beaverapp.ai", "xxvxklysvpobontwhwoz.supabase.co")

#: The preferences the harness writes into the host's profile before the first
#: launch, and nothing else. None of them is a target preference: the first two
#: are what make a sideloaded artifact active without a GUI click — the state an
#: ordinary user reaches through the add-on manager's "Install from file" — the
#: next two exist only so two harness instances can coexist on one machine, and
#: the last stops the host updating itself mid-measurement. They are declared
#: under `process` because they are harness setup, and the port move is declared
#: because on a plugin target it also relocates any endpoint the plugin
#: registers.
HARNESS_PREFS = (
    ('extensions.autoDisableScopes', 0),
    ('extensions.enabledScopes', 15),
    ('extensions.zotero.httpServer.enabled', True),
    ('extensions.zotero.httpServer.port', None),  # filled in with the port
    ('app.update.enabled', False),
)

#: The file the target's own startup creates in the host's data directory. Its
#: appearance is this adapter's readiness signal and its evidence that the
#: plugin loaded: the host creates its own database whether or not any add-on is
#: present, so only this one discriminates. Measured both ways — with the
#: artifact installed it appears; with the identical launch and no artifact it
#: does not.
PLUGIN_DATABASE = "beaver.sqlite"

#: The host's own database. Its absence means the host application never
#: started, which is an environment failure and not a finding about the target.
HOST_DATABASE = "zotero.sqlite"


class HostDidNotStart(RuntimeError):
    """The host application left no database, so nothing was measured.

    Raised rather than recorded because every assertion below it would otherwise
    return a verdict about a target that never ran — a residue sweep over an
    empty arena is green, and a green that means "the application did not start"
    is the failure this harness exists to catch. The alternative, a `not-run`
    state, is not the adapter's to return: the contract gives an adapter verbs
    and a declaration, and `not-run` is a verdict the layer reaches.
    """


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def declaration(profile: Path, data: Path, home: Path) -> Declaration:
    """The declaration for a target sandboxed at these three directories.

    A free function for the reason the second adapter's is: the declaration is
    the readable half of this module, and a contract check should be able to
    obtain it without an artifact on disk, a host application installed, or a
    display to start one on.
    """
    profile, data, home = Path(profile), Path(data), Path(home)
    return Declaration(
        name="jlegewie/beaver-zotero",
        revision=(
            f"beaver-zotero {VERSION} (repository jlegewie/beaver-zotero, tag {TAG}, "
            f"annotated tag object {TAG_OBJECT}, commit {COMMIT}), installed from the "
            f"release artifact {ARTIFACT}, {ARTIFACT_BYTES} bytes, sha256 "
            f"{ARTIFACT_SHA256} — the file this add-on's own update.json names in "
            f"update_link, which is the documented user install path rather than a "
            f"build of the harness's own. The plugin vendors its PDF runtime inside "
            f"the artifact and downloads no model, so unlike the second target there "
            f"is no resolved dependency closure to pin beside this string. What the "
            f"string does not pin is the hosted backend the shipped build is compiled "
            f"against: {', '.join(BACKEND_HOSTS)}, read out of the artifact's own "
            f"content/reactBundle.js."
        ),
        derived_state_roots=(
            # 1-4. The sidecar database and its journal siblings, in the HOST's
            #      data directory beside the host's own database. Four paths
            #      rather than one because `residue()` matches by path prefix
            #      and a file is a prefix of nothing: -wal and -shm were both
            #      measured present after a single launch. -journal is listed
            #      because the journal mode is the host SQLite layer's choice
            #      and not the target's.
            data / PLUGIN_DATABASE,
            data / f"{PLUGIN_DATABASE}-wal",
            data / f"{PLUGIN_DATABASE}-shm",
            data / f"{PLUGIN_DATABASE}-journal",
            # 5. The target's directory inside the host's data directory. Holds
            #    external-files (src/services/externalFiles.ts:118). Created
            #    lazily: it did NOT appear on a no-account launch.
            data / "beaver",
            # 6. The stdio bridge the target writes when its machine-reachable
            #    surface is switched on (react/hooks/useMcpServer.ts:148,156).
            #    Unreachable in the default configuration, where that preference
            #    is false, and declared anyway: the field asks where this target
            #    creates state, and an undeclared path that appears the moment a
            #    user opts in is a declaration that is true only by luck.
            data / "beaver-mcp-stdio.mjs",
            # 7. The target's directory inside the HOST's profile directory:
            #    secure-storage (src/services/EncryptedStorage.ts:112-131) and
            #    document-cache (src/services/documentCache.ts:140-155). Both
            #    measured present after a no-account launch, both empty — the
            #    first is reached by the auth layer's storage adapter even when
            #    there is no session to read.
            profile / "beaver",
        ),
        query_transport=(
            "none in the configuration under test, and the reason is a finding rather "
            "than an omission. Three surfaces exist and all three are shut. (a) A "
            "JSON-RPC MCP endpoint the plugin registers on the host's own HTTP server "
            "at /beaver/mcp (src/services/mcpService.ts:121, registered from "
            "react/hooks/useMcpServer.ts:1511) is never mounted, because registration "
            "returns early on a preference whose shipped default is false "
            "(useMcpServer.ts:1478). MEASURED on a running instance: /connector/ping "
            "answers 200 while /beaver, /beaver/mcp, /beaver/search, /beaver/status "
            "and /mcp all answer 404 to GET and POST — the 200 is what makes the 404s "
            "readable rather than a probe that could not look. (b) Roughly 120 "
            "/beaver/* HTTP endpoints exist in source but are compiled out of the "
            "shipped build (react/hooks/useHttpEndpoints.ts:1325); the string 'Not "
            "registering endpoints in production' is present in the artifact's own "
            "bundle and no /beaver/test path is. (c) The zotero://beaver protocol "
            "handler (src/services/protocolHandler.ts:126-140) is UI navigation only: "
            "it accepts thread, preferences and sidebar routes, dispatches a DOM event "
            "and returns noContent, carrying no query text and returning no answer. "
            "Beyond transport, retrieval itself is unavailable without an account: the "
            "query embedding is fetched from the backend "
            "(src/services/semanticSearchService.ts:71) and the local metadata search "
            "is fail-closed on an empty library scope until an authenticated profile "
            "loads (react/atoms/profile.ts:96-101, 116-119)."
        ),
        default_configuration=(
            f"the shipped artifact's own prefs.js, unmodified. The values that decide "
            f"what can be asked of this target: userId is empty and there is no stored "
            f"session, so every backend call throws at "
            f"packages/agent-core/src/transport/apiService.ts:290 before reaching "
            f"fetch; mcpServerEnabled is false, so the machine-reachable query surface "
            f"is never mounted; backgroundExtractorEnabled is true, so a background "
            f"worker starts unconditionally (src/hooks.ts:259-261) though its queue "
            f"stays empty without an account; dataProviderEnabled is false; "
            f"accessRemoteFiles is true; authMethod is otp. The build under test is "
            f"compiled against {BACKEND_HOSTS[0]} and {BACKEND_HOSTS[1]}. The product "
            f"discloses remote processing in its own onboarding UI — 'Some metadata "
            f"and chat content are processed on our servers to power Beaver features' "
            f"(react/components/pages/FreeOnboardingPage.tsx:137-138) — which is the "
            f"disclosed remote processing DECISIONS.md expects R10 to fail against. "
            f"Installing the plugin also causes the HOST to poll the add-on's "
            f"update_url at github.com on its own schedule (manifest.json update_url); "
            f"that egress is performed by the host application, not by plugin code, "
            f"and the host-only baseline this artifact cites is what separates them. "
            f"No preference is changed by this adapter: the five it writes are harness "
            f"setup and are listed under `process`."
        ),
        process=(
            "the target is an in-process plugin, so the process the harness starts is "
            "the HOST application's and the target has no process of its own. Start: "
            "the artifact is copied to <profile>/extensions/" + ADDON_ID + ".xpi — the "
            "sideload path an ordinary user reaches through the add-on manager's "
            "Install from file — then the host binary is run with -profile, -datadir "
            "and -no-remote, with HOME and DISPLAY set. Five preferences are written "
            "into the profile beforehand and none of them is a target preference: "
            "extensions.autoDisableScopes=0 and extensions.enabledScopes=15 are what "
            "make a sideloaded artifact active without a GUI click, the httpServer "
            "port and enabled pair exists only so two harness instances can coexist on "
            "one machine (and is declared because on a plugin target it also relocates "
            "any endpoint the plugin registers), and app.update.enabled=false stops "
            "the host updating itself mid-measurement. Readiness: the harness waits "
            "for the TARGET's own " + PLUGIN_DATABASE + " to appear in the data "
            "directory, which is the only signal that discriminates — the host creates "
            "its own database with or without any add-on, and this file was measured "
            "to appear with the artifact installed and not to appear on the identical "
            "launch without it. A readiness probe over the network would not do: "
            "inside a network namespace with no route, loopback is down too. Dwell: "
            "the harness then holds the process for a declared number of seconds "
            "before the verbs run, because this target's startup work is asynchronous "
            "and a session stopped the moment its calls return leaves less state and "
            "makes fewer attempts than one held a few seconds longer. Stop: terminate "
            "then kill, addressed to the host's PROCESS GROUP rather than to what was "
            "spawned — measured here, the host's launcher is a shell script that runs "
            "the real application as a child rather than exec'ing it, so signalling "
            "the process kills the script and orphans the application, and two "
            "instances survived their lifecycle on the first run. The lifecycle "
            "stopping the process itself is also why this adapter's traced run can "
            "exit 0, where a probe that has to kill the host cannot. HOME is set but "
            "is NOT this target's boundary: "
            "measured, everything that appears under it is the host's and the "
            "desktop's. The adapter refuses the operator's own HOME, profile or data "
            "directory, because the residue sweep reads this declaration and a run "
            "without a sandbox would point it at real state."
        ),
        unsupported={
            "query": (
                "there is no query surface in the configuration under test, and the "
                "three that exist are shut in three different ways — a preference "
                "default, a production build flag, and a route that carries no query. "
                "See `query_transport` for the addresses and the measurement. Two "
                "distinctions matter and must not be collapsed: this is NOT the second "
                "target's case, where a verb is absent because the target has no such "
                "work; and it is NOT quite the sibling plugin's either, where an "
                "opt-in preference alone hides an otherwise complete surface. Here the "
                "preference hides one surface, a build flag removes a second, and even "
                "with both open the query would still fail, because the query "
                "embedding is computed by the hosted backend and the local search "
                "scope is fail-closed until an authenticated profile loads. So this is "
                "additionally a clause that no credentialled run of ours could decide "
                "either: with an account it would become answerable, and we have none. "
                "Rejected alternative: set mcpServerEnabled true and call the result "
                "the normal configuration. It is a non-default option, which the "
                "ratified contract forbids in as many words; it writes a file into the "
                "data directory; it opens a listening socket the default configuration "
                "does not open, changing R10's subject; and it would still refuse "
                "every tools/call with 'User is not logged into Beaver' "
                "(src/services/mcpService.ts:243-251), so it buys a surface and no "
                "capability."
            ),
            "status": (
                "no machine-readable status surface. What exists is either in-process "
                "or internal: getStatus() and getStats() are methods on the plugin's "
                "own objects (src/services/backgroundExtractor.ts:150-152, "
                "src/services/documentCache.ts:968-974) reachable only from privileged "
                "JavaScript inside the host process, the indexing progress a user sees "
                "is an in-memory atom that is never persisted "
                "(react/atoms/embeddingIndex.ts:18-43), and the plugin's public API "
                "object is empty (src/addon.ts:47). This is the opposite of the second "
                "target, which offers a status tool and answers it thinly. Rejected "
                "alternative: read the counters out of the target's own sidecar "
                "database, where embedding_index_state and background_jobs do carry "
                "them (src/services/database.ts:387-394, 605-629). Any user can open "
                "that file, but it is not a surface the target offers — reading a "
                "private schema is a workaround for a missing surface, which the "
                "contract forbids, and the model_id it would yield is a client-side "
                "label written beside vectors the backend computed "
                "(src/services/embeddingIndexer.ts:195), so reporting it as the "
                "embedder in effect would be the adapter scoring a result. Without an "
                "account those tables are empty in any case, so the alternative would "
                "have decided nothing."
            ),
            "pause": (
                "this target has two background workers and no single control over "
                "them, so the verb SPEC.md §5.2.8 defines as the two transitions of one "
                "durable background-work control has no referent here. The document "
                "extractor, started unconditionally at src/hooks.ts:259-261, does have "
                "a real durable pause: the hidden preference "
                "backgroundExtractorEnabled, read per tick "
                "(src/services/backgroundExtractor.ts:401), re-armed by a preference "
                "observer (:216), releasing in-flight work rather than losing it "
                "(:250-295) against job state checkpointed in SQLite "
                "(src/services/database.ts:605-629). Embedding indexing has no pause "
                "at all: it stops only by losing authentication "
                "(react/hooks/useEmbeddingIndex.ts:530-532) and its only user control "
                "is a rebuild (react/atoms/embeddingIndex.ts:136-139), which is the "
                "destructive action the ruling says resume must never be. Rejected "
                "alternative: map pause onto the extractor's preference and report a "
                "durable background-work control. That would be true of one worker and "
                "false of the other, and `unsupported` is per verb, so the declaration "
                "has no way to say which — the finding is in the module docstring."
            ),
            "resume": (
                "absent for pause's reason, and not for the second target's: there IS "
                "background work here to resume — one worker's is checkpointed and "
                "would resume, the other's has no control at all — so this is a "
                "missing control over real work, which is the architectural opposite "
                "of a target that has no such work"
            ),
        },
        not_derived_state=(
            (
                profile / "prefs.js",
                "target-created derived state that this declaration CANNOT express, "
                "recorded here as the admission the field's contract asks for rather "
                "than passed over. The target writes its preferences as "
                "extensions.zotero.beaver.* keys into the host application's own "
                "preferences file (src/utils/prefs.ts:39-44); measured after one "
                "launch with no account, installedVersion, onboardingWelcomeShown, "
                "onboardingWelcomeShownAt and deletionJobs are in it. Declaring the "
                "file as a derived-state root would claim the host's preferences are "
                "the target's and would make R15's uninstall clause demand their "
                "deletion; omitting it entirely would under-declare. The interface's "
                "unit is a path and this state is a set of keys inside somebody else's "
                "file, so neither field fits and the honest move is to say so.",
            ),
            (
                data,
                "the host application's data directory, which is also the user's "
                "library — zotero.sqlite, fulltext.sqlite, storage/, translators/, "
                "styles/, locate/ and the host's own temp directory. R15 excludes the "
                "user's own library from derived state, and everything else here is "
                "created by the host with or without this target installed. The cost "
                "of exempting it whole is exact and is finding 2 in the module "
                "docstring: the target's sidecar sits INSIDE this directory, so a "
                "prefix exemption cannot distinguish the host's files from a stray of "
                "the target's, and a stray written here would not be reported. The "
                "declared roots above are what a reader checks instead, and the "
                "adapter reports which of them materialised.",
            ),
            (
                profile,
                "the host application's profile directory: its extensions store, "
                "certificate and cookie databases, startup cache, crash reports and "
                "its own preferences file. Created by the host with or without this "
                "target, and externally supplied configuration in R15's sense. The "
                "same cost as the entry above — the target's own directory sits inside "
                "it — and the same compensation: <profile>/beaver is declared as a "
                "root.",
            ),
            (
                home,
                "the sandbox HOME. Measured on this machine: everything that appears "
                "under it — .cache/mozilla, .cache/fontconfig, .cache/nvidia, "
                ".cache/zotero, .mozilla/extensions, .config/pulse, .config/mozilla, "
                ".zotero and Downloads — is created by Gecko and by the host desktop, "
                "and none of it is the target's. It is set to a scratch directory so "
                "that the host's caches do not land in the operator's real state; it "
                "is a sandbox for the host application, not a boundary for this "
                "target, which is the reverse of the second target's arrangement.",
            ),
        ),
    )


class Beaver:
    """Transport for the declaration above, and nothing else.

    Constructed on a harness-owned arena, the host application's binary and the
    pinned artifact. None of the three is a target option: the arena is where
    the residue sweep looks, the binary is the host this plugin runs inside, and
    the artifact is what `install` puts there.
    """

    def __init__(self, arena: Path, *, zotero: Path, xpi: Path, display: str = ":1",
                 port: int = 23319, dwell: float = 75.0, startup_timeout: float = 180.0,
                 stop_grace: float = 20.0) -> None:
        self.arena = Path(arena).resolve()
        self.zotero = Path(zotero)
        self.xpi = Path(xpi).resolve()
        self.display = display
        self.port = int(port)
        self.dwell = float(dwell)
        self.startup_timeout = float(startup_timeout)
        self.stop_grace = float(stop_grace)

        self.home = self.arena / "home"
        self.profile = self.arena / "profile"
        self.data = self.arena / "data"
        self._refuse_real_state()
        self.artifact_sha256 = self._verify_artifact()
        self.declaration = declaration(self.profile, self.data, self.home)
        self._process: subprocess.Popen | None = None
        self._startup: dict = {}

    # ---- refusals, which are the first line of the sandbox ----------------

    def _refuse_real_state(self) -> None:
        """Refuse to run against the operator's own home, profile or library.

        The residue sweep reads this declaration and the uninstall assertion
        deletes the artifact this adapter installed; both are safe only because
        every path they touch is inside a directory the harness made. A guessed
        or defaulted path here is not a guessed path, it is somebody's library.
        """
        real_home = Path.home().resolve()
        # A scratch arena INSIDE the operator's home is fine — that is where
        # scratch directories live. The home itself is not, because the arena's
        # three subdirectories would then be the operator's own.
        if self.arena == real_home:
            raise ValueError(
                "refusing to run jlegewie/beaver-zotero with the operator's own HOME "
                "as the arena: the residue sweep reads this declaration, and the "
                "sandbox HOME, profile and data directory would all be real state."
            )
        forbidden = {real_home / "Zotero", real_home / ".zotero",
                     real_home / "Zotero" / "profile"}
        for name, path in (("data", self.data), ("profile", self.profile),
                           ("home", self.home)):
            if path in forbidden:
                raise ValueError(
                    f"refusing the operator's own host {name} directory {path}. This "
                    "adapter's uninstall removes the artifact it installed and the "
                    "sweep reads the declaration; both need a harness-owned arena."
                )

    def _verify_artifact(self) -> str:
        """Check the pinned artifact's digest, or refuse.

        An adapter that names a revision in its declaration and then runs
        whatever file it was handed has pinned a sentence, not a build. Size is
        checked too because it is free and because a truncated download has a
        different digest for an uninteresting reason.
        """
        if not self.xpi.is_file():
            raise SystemExit(
                f"the pinned artifact is not at {self.xpi}. This adapter installs "
                f"{ARTIFACT} from release {TAG}, sha256 {ARTIFACT_SHA256}."
            )
        size = self.xpi.stat().st_size
        digest = _digest(self.xpi)
        if digest != ARTIFACT_SHA256 or size != ARTIFACT_BYTES:
            raise SystemExit(
                f"the artifact at {self.xpi} is not the pinned one: {size} bytes / "
                f"sha256 {digest}, expected {ARTIFACT_BYTES} bytes / sha256 "
                f"{ARTIFACT_SHA256} ({ARTIFACT} from release {TAG}). Refusing rather "
                "than measuring a build nobody chose."
            )
        return digest

    # ---- adapter-declared harness setup, deliberately not a verb ----------

    @property
    def installed_artifact(self) -> Path:
        """Where the host reads a sideloaded add-on from."""
        return self.profile / "extensions" / f"{ADDON_ID}.xpi"

    def environment(self) -> dict[str, str]:
        """The environment the host process starts in.

        HOME is redirected so the host's own caches land in the arena rather
        than in real state; DISPLAY is where a desktop application draws. Both
        are properties of the process the harness starts, not options the target
        offers, which is why they are declared under `process`.
        """
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["DISPLAY"] = self.display
        return env

    def _write_harness_prefs(self) -> list[str]:
        """The five preferences named under `process`, and nothing else.

        Written before the first launch. None is a target preference: the target
        keeps its own under a different prefix and this adapter writes none of
        them, because changing one would make the measured configuration
        something other than the default.
        """
        lines = []
        for key, value in HARNESS_PREFS:
            if key.endswith("httpServer.port"):
                value = self.port
            literal = "true" if value is True else "false" if value is False else str(value)
            lines.append(f'user_pref("{key}", {literal});')
        self.profile.mkdir(parents=True, exist_ok=True)
        (self.profile / "prefs.js").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return lines

    def _sideload(self) -> None:
        (self.profile / "extensions").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.xpi, self.installed_artifact)

    def _wait(self) -> dict:
        """Wait for the host to come up and for the target to leave its mark.

        Two signals and they answer different questions. The host's own database
        says the application started; the target's says the plugin loaded. Only
        the second discriminates, which is why the first is not used as
        readiness on its own — and why a missing first is an environment failure
        that raises rather than a finding that is recorded.
        """
        host_db, plugin_db = self.data / HOST_DATABASE, self.data / PLUGIN_DATABASE
        started = time.monotonic()
        host_at = plugin_at = None
        while time.monotonic() - started < self.startup_timeout:
            if host_at is None and host_db.exists():
                host_at = round(time.monotonic() - started, 1)
            if plugin_at is None and plugin_db.exists():
                plugin_at = round(time.monotonic() - started, 1)
            if host_at is not None and plugin_at is not None:
                break
            if self._process is not None and self._process.poll() is not None:
                break
            time.sleep(0.5)
        if host_at is None:
            raise HostDidNotStart(
                f"the host application left no {HOST_DATABASE} in {self.data} within "
                f"{self.startup_timeout:g}s, so nothing about the target was measured. "
                "This is an environment failure — no display, no binary, a stale lock "
                "— and it is raised rather than recorded because every verdict below "
                "it would be a verdict about a target that never ran."
            )
        return {
            "host_database_after_s": host_at,
            "plugin_database_after_s": plugin_at,
            "plugin_loaded": plugin_at is not None,
            "startup_timeout_s": self.startup_timeout,
        }

    @contextmanager
    def running(self):
        """Sideload, start the host, wait, dwell, yield, stop it.

        Harness setup rather than an eighth verb, per the contract. The dwell is
        inside the lifecycle because this target's startup work is asynchronous:
        the process is held for a declared number of seconds before any verb
        runs, so that a residue sweep and an egress trace see the same window
        rather than whatever the verbs happened to take.
        """
        for path in (self.home, self.profile, self.data):
            path.mkdir(parents=True, exist_ok=True)
        prefs = self._write_harness_prefs()
        self._sideload()
        argv = [
            str(self.zotero), "-profile", str(self.profile),
            "-datadir", str(self.data), "-no-remote",
        ]
        # `start_new_session` puts the host in a process group of its own, and
        # stopping it signals that GROUP rather than the process. This is not
        # tidiness: the host's launcher is a shell script that runs the real
        # binary as a CHILD rather than exec'ing it, so terminating what was
        # spawned kills the script and orphans the application. Measured here
        # on the first run — two orphaned instances survived their lifecycle,
        # kept their databases open, and would have made the next arm's
        # "process stopped" a fiction.
        self._process = subprocess.Popen(
            argv, env=self.environment(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, start_new_session=True,
        )
        try:
            self._startup = {"argv": argv, "harness_prefs": prefs, **self._wait()}
            time.sleep(self.dwell)
            yield
        finally:
            process, self._process = self._process, None
            if process is not None:
                self._stop(process)

    def _stop(self, process: subprocess.Popen) -> None:
        """Signal the host's whole process group, then wait for it to be gone.

        Terminate then kill, each addressed to the group. `os.killpg` is used
        rather than `Popen.terminate` for the reason the comment above gives,
        and both calls tolerate the group having already exited: a race between
        the wait and the signal must not raise out of a `finally`.
        """
        import signal

        for sig in (signal.SIGTERM, signal.SIGKILL):
            if process.poll() is not None and not self._group_alive(process.pid):
                return
            try:
                os.killpg(os.getpgid(process.pid), sig)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                process.wait(self.stop_grace)
            except subprocess.TimeoutExpired:  # pragma: no cover - grace path
                pass

    @staticmethod
    def _group_alive(pid: int) -> bool:
        try:
            os.killpg(os.getpgid(pid), 0)
        except (ProcessLookupError, PermissionError, OSError):
            return False
        return True

    # ---- the seven verbs -------------------------------------------------

    def install(self) -> dict:
        """The sideload the lifecycle performed, and what it produced.

        There is no install command to call: this target is a plugin, and its
        installation is a file placed where the host reads add-ons, after which
        the host loads it and the target's state materialises. `running()` has
        done that by the time this is reached, exactly as the first target's
        `install` reports a data directory the process created. What this returns
        is evidence: the artifact's digest, the host's own record of whether it
        activated the add-on, and which declared roots exist.

        Note what is NOT claimed. `plugin_loaded` reads the target's own database
        appearing, which was measured to discriminate — the identical launch
        without the artifact does not produce it — and `host_activated` reads the
        host's extensions record. Neither is scored here; both are reported.
        """
        return {
            "verb": "install",
            "artifact": str(self.xpi),
            "artifact_sha256": self.artifact_sha256,
            "artifact_bytes": self.xpi.stat().st_size,
            "installed_at": str(self.installed_artifact),
            "addon_id": ADDON_ID,
            "version": VERSION,
            "commit": COMMIT,
            "startup": dict(self._startup),
            "host_activated": self._host_addon_record(),
            "declared_roots_present": self._roots_present(),
        }

    def uninstall(self) -> dict:
        """Remove the artifact this adapter installed. Nothing else is touched.

        This is the inverse of `install` and it is deliberately no more than
        that: the sideload path is how an ordinary user installs a plugin the
        host does not fetch itself, and removing that file is what the host's
        add-on manager does on disk when the same user removes it. The harness
        does NOT delete any derived state — that is precisely what R15's
        uninstall clause forbids a harness from doing on a target's behalf, and
        the assertion that follows this call sweeps the declared roots to see
        what survived.

        The rejected alternative, recorded because it is defensible and was
        weighed: declare the verb absent on the ground that the real removal is
        an operation of the HOST's add-on manager, which is a graphical surface,
        and that scripting a graphical surface is the workaround the second
        adapter refused for an interactive wizard. It was rejected for symmetry
        — the same file placement is already how `install` works, sanctioned as
        the state a user reaches through Install from file — and because the
        clause is decidable here on the evidence: the plugin's own bootstrap
        `install()` and `uninstall()` hooks are empty, and its shutdown path
        stops workers and closes the database without deleting anything
        (`bootstrap.js:12,104`; `src/hooks.ts:787-877`), so no removal path this
        target has removes its state. A reader who prefers the other reading has
        the survivors and this note in the artifact.
        """
        existed = self.installed_artifact.is_file()
        if existed:
            self.installed_artifact.unlink()
        return {
            "verb": "uninstall",
            "removed": str(self.installed_artifact),
            "artifact_was_present": existed,
            "what_this_does_not_do": (
                "no derived state is deleted by the harness. The target's own "
                "bootstrap uninstall hook is empty and its shutdown path deletes "
                "nothing, so whatever the sweep now finds under the declared roots "
                "survived a removal this target does not act on"
            ),
            "host_activated": self._host_addon_record(),
        }

    def configure(self) -> dict:
        """Report the configuration in effect. It applies nothing.

        This target's configuration is a preference set the host holds, and the
        configuration under test is the artifact's own shipped defaults. Writing
        any of them would make the measured configuration something other than
        the default, which the contract forbids, so this verb reports and does
        not act — the same shape the first target's takes, for the same reason.
        The five preferences named here are the harness's, listed under
        `process`, and none of them is a target preference.
        """
        return {
            "verb": "configure",
            "applied": None,
            "channel": (
                "the host's preference store; the configuration under test is the "
                "artifact's own shipped prefs.js, unmodified"
            ),
            "harness_prefs": self._startup.get("harness_prefs", [
                key for key, _ in HARNESS_PREFS
            ]),
            "backend_hosts_compiled_in": list(BACKEND_HOSTS),
            "default_configuration": self.declaration.default_configuration,
        }

    def query(self, q: str, mode: str, limit: int) -> dict:
        """Absent. Three surfaces, three different reasons, none of them open."""
        raise UnsupportedVerb(self.declaration.name, "query")

    def status(self) -> dict:
        """Absent. No machine-readable status surface; see the declaration."""
        raise UnsupportedVerb(self.declaration.name, "status")

    def pause(self) -> dict:
        """Absent. Two background workers, no single durable control over them."""
        raise UnsupportedVerb(self.declaration.name, "pause")

    def resume(self) -> dict:
        """Absent for pause's reason, and not for the second target's."""
        raise UnsupportedVerb(self.declaration.name, "resume")

    # ---- evidence the verbs report, none of it scored ---------------------

    def _roots_present(self) -> dict[str, bool]:
        return {str(p): p.exists() for p in self.declaration.derived_state_roots}

    def _host_addon_record(self) -> dict:
        """What the host's own extensions record says about this add-on.

        Read rather than inferred: the host writes it, and it is the only place
        that says whether the application accepted the sideloaded artifact. A
        missing or unreadable file is reported as such, never as a False.
        """
        import json

        path = self.profile / "extensions.json"
        if not path.is_file():
            return {"read": False, "why": f"{path} does not exist"}
        try:
            addons = json.loads(path.read_text(encoding="utf-8")).get("addons", [])
        except (ValueError, OSError) as exc:
            return {"read": False, "why": f"{type(exc).__name__}: {exc}"}
        for addon in addons:
            if addon.get("id") == ADDON_ID:
                return {"read": True, "present": True,
                        "version": addon.get("version"),
                        "active": addon.get("active"),
                        "location": addon.get("location")}
        return {"read": True, "present": False,
                "ids": sorted(a.get("id") for a in addons if a.get("id"))}


#: The targets this module builds. The registry walks the package and reads
#: this, so declaring it is what makes the adapter selectable — and what lets the
#: target-neutrality guard learn this target's name without being told it.
NAMES = ("beaver",)


def build(name: str, arena: Path, *, zotero: str = "", xpi: str = "",
          display: str = ":1", port: str | int = 23319, dwell: str | float = 75.0,
          startup_timeout: str | float = 180.0, **_opts) -> Beaver:
    """Construct the adapter from the driver's opaque `--adapter-option` pairs.

    Neither the host binary nor the artifact is defaulted, and both refusals are
    the point. A guessed binary measures whatever host happens to be installed;
    a guessed artifact measures a build nobody chose, which is the one thing a
    pinned revision exists to prevent.
    """
    if not zotero:
        raise SystemExit(
            "this adapter needs the host application's binary "
            "(--adapter-option zotero=<path>). It is not defaulted: this target is a "
            "plugin, so the host is half of what is under test, and a guessed path "
            "measures whichever build the machine happens to carry."
        )
    if not xpi:
        raise SystemExit(
            f"this adapter needs the pinned artifact (--adapter-option xpi=<path> to "
            f"{ARTIFACT} from release {TAG}, sha256 {ARTIFACT_SHA256}). It is not "
            "defaulted, and its digest is checked: an adapter that names a revision "
            "and runs whatever file it is handed has pinned nothing."
        )
    return Beaver(
        Path(arena), zotero=Path(zotero), xpi=Path(xpi), display=display,
        port=int(port), dwell=float(dwell), startup_timeout=float(startup_timeout),
    )
