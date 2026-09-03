"""The adapter for `introfini/ZotSeek`, the layer's in-process-plugin target.

Ticket 0584. The contract is `interface.py`, owned by `SPEC.md` §5.2.8 and the
`DECISIONS.md` entry ratified 2026-09-02; neither is restated here. What this
module holds is a declaration and the minimal transport needed to invoke the
surfaces it declares — no patch or workaround, no non-default option, no access
unavailable to the target's own users, and no scoring of a result.

**No line of this target's code is reproduced here.** Its licence is declared
only as `"license": "MIT"` in `package.json`, with no LICENSE file in the tree,
so ticket 0584 permits running and inspecting it and forbids copying it.
Everything this module asserts about the target's behaviour is cited as
`path:line` into the pinned source tree or is a measurement taken on padme,
2026-09-03, and named as such.

**Why this target and not another external server.** The other two adapters
drive a process the harness starts and owns. This one is a plugin loaded by a
third-party desktop application: the harness starts *the host*, the host loads
the target, and every verb reaches the target through the host. That is the
architecture class this seat exists to stress, and it is where the interface
bends. The findings below are the lane's actual product.

---

## What the interface could not express

**1. The residue sweep's unit is a path, and on this target the paths belong to
the host.** ZotSeek's whole measured footprint in the default configuration is
two files and one empty directory — `<data dir>/zotseek.sqlite`, the profile's
`zotseek-models/`, and sixteen preference keys. Every directory containing them
is Zotero's. So `not_derived_state` has to carry the host application itself,
and it is documented for user data and externally supplied configuration, which
is neither.

**2. Worse, the host's own writes are NONDETERMINISTIC IN PATH, so a host-only
baseline cannot be subtracted even by hand.** Measured here: two launches of the
same application on the same machine, one with the plugin and one without, both
into a scratch HOME. The host opens its first-run start page in the desktop
browser and registers its word-processor integration, both of which inherit the
sandbox HOME; the browser profile directory and the office suite's staging
directories are named with a fresh random string on every run. 311 files existed
only in the host-only arm and 317 only in the with-plugin arm, and the whole of
that difference is the host's churn except four paths. A differential residue
sweep is therefore not available at path granularity on this architecture, which
is why the exemptions below are directory-wide for `home/` and `profile/` and
name-by-name only inside the data directory, where Zotero's own filenames are
stable.

**3. A preference key is derived state that no path can name.** The target
writes sixteen `zotseek.*` keys into the host's `profile/prefs.js` (measured;
`hostonly` writes none). `derived_state_roots` is a tuple of paths. Declaring
`prefs.js` a derived-state root would claim the host's entire preference store
for the target; omitting it hides state the target creates. It is listed under
`not_derived_state` with exactly that argument, which is an admission and not a
resolution.

**4. R10's subject is the HOST's process — literally the same process — and the
interface gives an adapter no way to say so.** Two things were measured here and
the second is the sharper.

The host alone falsifies the clause. A host-only control arm — Zotero 10.0.1, no
plugin, same isolation, same tracer — attempts zero off-machine connections and
426 name lookups on a virgin profile, 60 on a warmed one (the lane lead's
measurement, `bench/results/r10-host-baseline/hostbase.json`). A matched pair run
for this adapter, differing in NOTHING but the presence of the XPI — same
launcher, same profile shape, same five harness preferences, same mechanism, same
tracer, a fixed 120 s dwell in both so that the arms are the same length — reads
0 off-machine / 56 name lookups without the plugin and 0 / 60 with it, each
reproduced to the digit across two independent replicates, against 47 / 5 with
the route intact (driver `bench/r10_plugin_pair.py`, artifact
`bench/results/0584-zotseek/r10-plugin-pair.json`; committed rather than left in
prose, because a number that lives only in a merge request is a number nobody can
re-derive once the branch is gone). So the target adds four name lookups and no connection attempt
at all, and the clause reds on the host's fifty-six.

And the trace cannot attribute even those four. Every lookup in both arms issues
from a **single pid**, which is the host's main process — the process in which
this target's JavaScript runs, by construction. An in-process plugin has no
process of its own for a process tracer to separate, so on this architecture
class the instrument's resolution is the host, full stop. What makes those four
lookups is therefore not established here, and naming a cause would be a verdict
dressed as a finding; the experiment that would settle it needs an attribution
channel finer than a process, which this harness does not have.

The adapter cannot qualify the verdict either: `unsupported` maps only to
`not-offered`, and the four verbs the clause drives are not absent. The red this
target's artifact carries is a fact about Zotero. It is recorded in `process`, so
that it reaches the artifact through the declaration; nothing is subtracted in
code, because that would be the layer scoring a result.

**5. `check_no_egress` requires the subject's return code to be zero**, so a
target whose process does not exit on its own can never reach `pass` there. The
lane lead hit it with `timeout`-killed cells. This adapter escapes it only
because the drive subprocess owns the host process and terminates it in
`running()`'s finally block; an adapter that ran its target in the foreground
would be structurally unable to pass. Recorded rather than worked around.

**6. The lifecycle assumes that starting the target starts the target.** Here
`running()` starts a desktop application which then loads the plugin, so a
failure to come up is ambiguous between the two. The readiness signal has to be
a file the *plugin itself* writes — `zotseek.sqlite` — because the host coming
up proves nothing about the target. A timeout waiting on the host's own
`zotero.sqlite` would be a false red against the target.

**7. `query_transport` presumes a wire, and this target has none.** The field
asks how the query surface is reached, and the other two adapters answer with a
protocol. This target reads the library through the host's own in-process data
layer — `Zotero.Items.getAsync`, `Zotero.Search`, `Zotero.Libraries`,
`Zotero.Fulltext.getPages`, `attachment.attachmentText`
(src/utils/zotero-api.ts:203-241, 376-421, 474; src/core/hybrid-search.ts:344,
385-386) — and it ATTACHes its own sidecar to the host's LIVE SQLite connection
(src/core/vector-store-sqlite.ts:267-293). It never reads the library over the
local HTTP API. The port occurs three times in the source and none of them is an
outbound call: a comment showing a user how to point an MCP client at it
(src/server/mcp-endpoint.ts:10), a fallback default when the plugin builds a URL
to its OWN endpoint (src/server/http-tools.ts:164), and a comparison plus a
display string in the preference pane's setup instructions
(src/ui/preferences.ts:1133, 1136). So the assumption that a target reaches
Zotero over a wire — which is what an adapter's `query_transport` is shaped to
describe — is false for this architecture class, and the field can say so only in
prose. Verified at the lane lead's request, 2026-09-03; the enumeration above is
a review correction, the first wording having claimed the port occurred only in
prose.

**8. Three distinct kinds of absence now sit under `not-offered`, and only the
reason field separates them.** That field landed in ticket 0597 and this target
is where it earns its place: zoteus reports "there is no such surface", zotero-mcp
reports "there is no such work to control", and ZotSeek reports a third thing —
"the surface exists, does real work, and has no trigger a machine can reach in
the default configuration". Without the reason those three are one cell. This is
the one place the interface came out ahead.

---

## The trap that would have made this declaration wrong

**The preference file shipped inside the XPI is not the effective default
configuration.** `prefs.js` in the artifact declares `maxTokens` 800 and
`indexingMode` "abstract"; a first run writes 2000 and "full" into the profile,
along with four keys the shipped file does not contain at all. An adapter that
read the shipped defaults to describe "the configuration an ordinary user gets"
would have described a configuration nobody runs. The effective set is read from
the profile after a run, and it is reported in `default_configuration` as
measured.
"""

import hashlib
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from ..interface import Declaration, UnsupportedVerb

#: The plugin's add-on id, from `manifest.json` at the pinned commit. It is the
#: filename a sideloaded XPI must take in the profile's `extensions/` directory.
ADDON_ID = "zotseek@zotero.org"

VERSION = "1.21.2"

#: `origin/main` and the tag-level head of `introfini/ZotSeek` on 2026-09-03.
#: The repository carries one tag, `v1.0.0`, which is nine major versions behind
#: the manifest, so the commit is the only pin available.
COMMIT = "f442f8258d48e3e73458d74f428ded7086c740f5"

#: The release artifact reached through `update.json`'s `update_link` — the
#: documented user install path — and its digest. The digest is checked at
#: construction rather than trusted: a declaration that pins a revision while
#: running a different file is a lie the artifact cannot detect.
ARTIFACT = f"zotseek-{VERSION}.xpi"
ARTIFACT_SHA256 = "7daaf964b1f11da274f201a1671dc82560add264f4b56f0b602c31b067ce2e69"
ARTIFACT_BYTES = 103_284_735

#: The preferences the harness writes into the profile before the host starts.
#: Every one of them is harness setup and is declared under `process`; none is a
#: target option, and none touches the target's own preference branch.
#:
#: `autoDisableScopes` and `enabledScopes` are what make a sideloaded XPI active
#: without a GUI click — the state an ordinary user reaches through the host's
#: Add-ons manager. The HTTP server port exists only so this instance can coexist
#: with the operator's own, and it must be declared because on a plugin target it
#: also relocates any endpoint the plugin registers.
HARNESS_PREFS = (
    ("extensions.autoDisableScopes", "0"),
    ("extensions.enabledScopes", "15"),
    ("extensions.zotero.httpServer.enabled", "true"),
    ("app.update.enabled", "false"),
)

#: The host application's own entries in its data directory, measured in a
#: host-only control arm on padme 2026-09-03: an identical launch, same profile
#: shape, no plugin installed. They are exempted by name rather than by
#: exempting the directory, so that the sweep stays able to see a file the target
#: strays into the one directory it actually writes to. A host entry not in this
#: list reddens the sweep, which is the safe direction: a red is read by a person
#: and a silent exemption is not.
HOST_DATA_ENTRIES = (
    "zotero.sqlite",
    "zotero.sqlite-wal",
    "zotero.sqlite-shm",
    "zotero.sqlite-journal",
    "zotero.sqlite.bak",
    "zotero.sqlite.tmp-wal",
    "fulltext.sqlite",
    "translators",
    "styles",
    "locate",
    "storage",
    "cache",
    "logs",
    "pipes",
    "tmp",
)

#: Where this adapter captures the host application's own output. It is the
#: harness's instrument rather than the target's state, and it is declared under
#: `not_derived_state` for that reason: the arena is harness-owned, but the
#: residue sweep counts every file in it as the target's.
HOST_LOG = "host.log"

#: `user_pref("<name>", <value>);` as the host writes it. Used to read the
#: effective configuration back out of the profile, which is the access an
#: ordinary user has through the preference editor.
_USER_PREF = re.compile(r'^user_pref\("([^"]+)",\s*(.*)\);\s*$')

#: The prefix of every preference the target owns, as the host actually spells
#: it in the profile. Measured: sixteen keys under this prefix after a first run,
#: and none in the host-only arm.
TARGET_PREF_PREFIX = "zotseek."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def declaration(arena: Path, *, port: int = 23219) -> Declaration:
    """The declaration for a target sandboxed in `arena`.

    A free function for the reason `zotero_mcp.declaration` is one: the
    declaration is the readable half of an adapter, and a contract check must be
    able to obtain it on a machine where neither the host application nor the
    artifact exists.
    """
    arena = Path(arena)
    home, profile, data = arena / "home", arena / "profile", arena / "data"
    sidecar = data / "zotseek.sqlite"
    return Declaration(
        name="introfini/ZotSeek",
        revision=(
            f"ZotSeek {VERSION}, commit {COMMIT} (origin/main and tag-level head on "
            f"2026-09-03; the repository's only tag, v1.0.0, is nine major versions "
            f"behind the manifest, so the commit is the pin). The artifact under test "
            f"is {ARTIFACT}, {ARTIFACT_BYTES} bytes, sha256 {ARTIFACT_SHA256}, fetched "
            f"through update.json's update_link — the documented user install path. The "
            f"digest is verified at construction, not assumed. Licence: package.json "
            f"declares \"MIT\" and the tree carries no LICENSE file, which is why this "
            f"adapter cites source addresses and reproduces no code."
        ),
        derived_state_roots=(
            # 1. The sidecar database, created on the plugin's first startup and
            #    ATTACHed to the host's own SQLite connection
            #    (src/core/vector-store-sqlite.ts:112-113, 155, 259). Measured:
            #    557 056 bytes, schema_version 9, every table empty, on a run that
            #    indexed nothing.
            sidecar,
            # 2-4. Its journal siblings. Separate paths, not children of the file
            #      above, so each is declared: the sweep compares paths.
            data / "zotseek.sqlite-wal",
            data / "zotseek.sqlite-shm",
            data / "zotseek.sqlite-journal",
            # 5-6. Pre-migration backups, written before the v8 and v9 schema
            #      migrations (src/core/vector-store-sqlite.ts:876, 1281). Not
            #      created on a fresh install; declared because a run against an
            #      older sidecar creates them and an undeclared one is residue.
            data / "zotseek.sqlite.v7.bak",
            data / "zotseek.sqlite.v8.bak",
            # 7. Where non-bundled model weights land — the host's PROFILE
            #    directory, not its data directory, deliberately
            #    (src/core/model-download.ts:34-36, and :44-46 for the legacy
            #    location it still reads and no longer writes). Measured: the
            #    directory is created even in the default configuration, where
            #    nothing is downloaded, and stays empty.
            profile / "zotseek-models",
        ),
        query_transport=(
            "none in the default configuration, and that is a measurement rather "
            "than an omission. This target's query surfaces are dialogs inside the "
            "host application's window (content/searchDialog.xhtml, "
            "content/similarDocumentsDialog.xhtml) and a set of REST/MCP endpoints "
            "on the host's own HTTP server. The endpoints are registered only when "
            "`zotseek.mcpServer.enabled` is true, and the shipped preference file "
            "sets it false with the comment \"Opt-in\" "
            "(src/server/server-manager.ts:23, 30-40, 71-75). Measured on the "
            f"running instance at 127.0.0.1:{port}: POST to /zotseek/search, "
            "/zotseek/stats, /zotseek/mcp and /zotseek/similar all answer 404, in the "
            "with-plugin arm and in the host-only arm alike. Turning the preference on "
            "is a non-default option, which the ratified contract forbids in as many "
            "words, and it would also change R10's subject by opening a listening "
            "socket the default configuration does not open.\n\n"
            "What this field cannot say, and it is the sharper half: there is no wire "
            "here at all. This target reaches the library through the host's own "
            "in-process data layer — Zotero.Items.getAsync, Zotero.Search, "
            "Zotero.Libraries, Zotero.Fulltext.getPages, attachment.attachmentText "
            "(src/utils/zotero-api.ts:203-241, 376-421, 474; "
            "src/core/hybrid-search.ts:344, 385-386) — and ATTACHes its own sidecar "
            "database to the host's live SQLite connection "
            "(src/core/vector-store-sqlite.ts:267-293). It never reads the library over "
            "the local HTTP API. That port occurs three times in its source and none "
            "of them is an outbound call: a comment showing a user how to point an MCP "
            "client at it (src/server/mcp-endpoint.ts:10), a fallback default when the "
            "plugin builds a URL to its OWN endpoint (src/server/http-tools.ts:164), "
            "and a comparison plus a display string in the preference pane's setup "
            "instructions (src/ui/preferences.ts:1133, 1136). An external server has a "
            "transport to declare; a plugin has the host's data layer in hand, and the "
            "field is shaped for the first."
        ),
        default_configuration=(
            f"the release artifact {ARTIFACT} sideloaded into the profile's "
            "extensions/ directory — the file-level form of the host's own "
            "Tools > Add-ons > Install from file — with no preference of the target's "
            "own set by the harness, against an empty library. What that resolves to "
            "was READ BACK from the profile after a run rather than transcribed from "
            "the shipped defaults, and the two differ: the XPI's prefs.js declares "
            "maxTokens 800 and indexingMode \"abstract\", while the effective set "
            "carries 2000 and \"full\", plus autoCompact, excludeTag, serverModels and "
            "webgpu.enabled, which the shipped file does not contain at all. Sixteen "
            "keys under the target's prefix are present after a first run and none in "
            "the host-only arm. The ones that decide what this target can be asked: "
            "autoIndex false, so no unattended indexing runs; mcpServer.enabled false, "
            "so no machine-reachable endpoint exists; embeddingModel "
            "nomic-embed-text-v1.5, which is the one model bundled inside the XPI "
            "(content/models/Xenova/nomic-embed-text-v1.5/onnx/model_quantized.onnx, "
            "137,3 MB, beside 32,7 MB of onnxruntime wasm), so in the default "
            "configuration NOTHING IS DOWNLOADED and R15's model-cache clause has no "
            "download to be about. Where a model is not bundled the target fetches it "
            "from huggingface.co (src/core/model-download.ts:20, 231) into the profile "
            "path declared above. The one remote-processing path the target offers is "
            "a local inference server, and its URL is gated to 127.0.0.1, localhost "
            "and [::1] at request time with no override preference "
            "(src/core/loopback-url.ts:9, 17-37) — an observation about the target's "
            "own design, not a verdict, since this adapter measures no egress of its "
            "own."
        ),
        process=(
            "the harness starts the HOST APPLICATION and the host loads the target; "
            "this is the whole of what makes this seat different from the other two "
            "adapters. Start: the host's launcher with -profile, -datadir and "
            "-no-remote, under HOME set to a scratch directory inside the arena and "
            f"DISPLAY pointed at an existing X server, with the profile carrying "
            f"{len(HARNESS_PREFS) + 1} harness preferences and the pinned XPI in its "
            "extensions/ directory. Readiness is the appearance of the target's own "
            "sidecar database, never the host's: the host coming up says nothing about "
            "whether the plugin loaded. Stop: signal the whole process GROUP, twice on "
            "SIGTERM and then on SIGKILL — the launcher is a shell script, and the "
            "application starts the desktop browser and the office suite's registration "
            "helper, so signalling the direct child alone leaves those reparented and "
            "alive, and the egress tracer follows descendants and waits for them.\n\n"
            "HOME is the sandbox and it is the only one, as on the other adapters — "
            "but here most of what appears under it is not the target's. Measured, "
            "padme 2026-09-03: a run creates .zotero/, .cache/{zotero,mozilla,"
            "fontconfig,nvidia}/, .mozilla/extensions/, .config/{pulse,libreoffice,"
            "mozilla}/ and Downloads/ under it, and the host additionally opens its "
            "first-run start page in the DESKTOP BROWSER and stages its word-processor "
            "integration, both of which inherit this HOME and both of which name their "
            "directories with a fresh random string every run. That is why the "
            "exemptions below are directory-wide for home/ and profile/.\n\n"
            "R10's subject on this architecture is the host's process tree, and on an "
            "in-process plugin it is literally the host's process. Two control "
            "measurements are recorded here so a reader can price the verdict, and "
            "neither is subtracted in code.\n\n"
            "(a) The host alone, no plugin, same isolation, same tracer: ZERO "
            "off-machine connection attempts and 426 name lookups on a virgin profile, "
            "60 on that profile's second run, against 456 and 80 with the route intact "
            "— the lane lead's measurement on padme, 2026-09-03, driver "
            "bench/r10_host_baseline.py, artifact "
            "bench/results/r10-host-baseline/hostbase.json.\n\n"
            "(b) A matched pair run for this adapter, differing in NOTHING but whether "
            "the XPI is in the profile — same launcher, same profile shape, the same "
            "five harness preferences, the same mechanism and tracer, and a FIXED 120 s "
            "dwell in both arms, because a readiness-driven dwell is not the same "
            "length in the two and a control that differs in duration is not a control. "
            "Without the plugin: 0 off-machine, 56 lookups. With it: 0 off-machine, 60 "
            "lookups. Each reproduced to the digit across two independent replicates, "
            "against 47 off-machine and 5 lookups with the route intact, which is what "
            "says the instrument works here. Measured on padme, 2026-09-03; driver "
            "bench/r10_plugin_pair.py, artifact "
            "bench/results/0584-zotseek/r10-plugin-pair.json, which also records for "
            "each arm whether the plugin's own sidecar appeared — so a reader can tell "
            "the with-plugin arms really loaded the plugin rather than merely carrying "
            "the file.\n\n"
            "The arena state moves the host's own figure sevenfold, so it is stated "
            "plainly: this adapter runs against a VIRGIN profile and data directory, "
            "created fresh inside the arena on every construction, never seeded and "
            "never cleared afterwards. And the trace cannot attribute the four-lookup "
            "difference: every lookup in both arms issues from a single pid, the host's "
            "main process, which is where this target's JavaScript runs. A process "
            "tracer has no finer resolution than a process, and an in-process plugin "
            "has no process of its own — so what makes those four is not established, "
            "and this declaration does not guess."
        ),
        unsupported={
            "uninstall": (
                "the surface exists, does real work, and has no trigger a machine can "
                "reach — which is a third kind of absence, distinct from both other "
                "adapters'. bootstrap.js:90-141 implements a true-uninstall cleanup: it "
                "deletes the sidecar database and its journal, wal and shm siblings and "
                "deleteBranch()es the whole of the target's preference branch, and it "
                "does so only for reason 6, ADDON_UNINSTALL. The only thing that "
                "produces that reason in the default configuration is the host's "
                "Add-ons manager Remove button, a GUI control. MEASURED, padme "
                "2026-09-03, with a control arm: deleting the sideloaded XPI from the "
                "profile while the application was stopped and restarting it does NOT "
                "fire the hook — the plugin's own bootstrap lines still appear in the "
                "restarted session's debug output, the sidecar database survives, all "
                "sixteen preference keys survive, and the string 'uninstall' does not "
                "occur once in 1 691 lines of that output. The control arm, an "
                "identical restart with the XPI left in place, is indistinguishable. "
                "The harness will not delete the declared state on the target's behalf: "
                "R15's uninstall clause forbids manufacturing a clean result that way"
            ),
            "query": (
                "the target HAS the surface and does not expose it to a machine by "
                "default, which is the opposite finding from an adapter that reports no "
                "such work. Its query paths are GUI dialogs inside the host's window, "
                "plus REST and MCP endpoints registered only when "
                "`zotseek.mcpServer.enabled` is true; the shipped preference file sets "
                "it false and comments it \"Opt-in\" (src/server/server-manager.ts:23, "
                "30-40, 71-75). Measured: those endpoints answer 404 on the running "
                "default instance. Enabling the preference is a non-default option, "
                "which the contract forbids, and it would change R10's subject by "
                "opening a listening socket the default configuration does not open. "
                "The developer self-test harness behind `zotseek.devMode` is out of "
                "bounds for the same reason twice over: a non-default option and a "
                "workaround"
            ),
            "status": (
                "for query's reason, and it was measured rather than assumed. The "
                "machine-readable status is the /zotseek/stats endpoint, behind the "
                "same opt-in preference; the other report is a GUI dialog. The sidecar "
                "database is readable without any opt-in and does NOT carry one: its "
                "metadata table holds a single row, schema_version, and the model in "
                "effect is not in the database at all but in a host preference read at "
                "pipeline init (src/core/model-registry.ts:103-115). Reading a "
                "preference file would answer from configuration, and this clause is "
                "about a running process — a target that defaults to local and a "
                "process that fell back to something else are the same file and "
                "different facts. Constructing a status the target does not publish is "
                "a workaround, so nothing is constructed"
            ),
            "pause": (
                "a third distinct reason again, and both halves of it are findings. "
                "This target HAS unattended background machinery — an auto-index "
                "manager on the host's notifier (src/core/auto-index-manager.ts:22-45) "
                "— and it is off by default: autoIndex is false in the shipped "
                "preferences and false in the effective set measured after a run. So in "
                "the default configuration there is no background work to pause. It "
                "also HAS a real pause control, and that control is a button in a "
                "progress window (src/utils/stable-progress.ts:602-615, read by "
                "src/index.ts:1433 waitIfPaused()), over a run the user starts from the "
                "GUI. Neither the work nor the control is reachable by a machine here. "
                "That is not zotero-mcp's 'there is no such work at all', and it is not "
                "zoteus's 'the only action that would serve it also rebuilds'"
            ),
            "resume": (
                "absent for pause's reason and by the same control: resume is the other "
                "state of the one progress-window button "
                "(src/utils/stable-progress.ts:608-615), so it is exactly as "
                "unreachable and exactly as real"
            ),
        },
        not_derived_state=(
            (
                home,
                "the sandbox HOME, and the whole of it is the host application's and "
                "the desktop's. Measured against a host-only control arm — the "
                "identical launch with no plugin installed — 311 files existed only in "
                "that arm and 317 only in the with-plugin arm, and every one of those "
                "differences is the host's own churn: it opens its first-run start page "
                "in the desktop browser and stages its word-processor integration, both "
                "inheriting this HOME, both naming their directories with a fresh "
                "random string per run. Nothing the target creates was observed here. "
                "The exemption is directory-wide because at path granularity the host's "
                "baseline is not subtractable, which is finding 2 in this module's "
                "docstring and not a convenience",
            ),
            (
                profile,
                "the host application's profile directory: its preference store, its "
                "add-on registry, its startup cache, its certificate and cookie stores. "
                "R15 excludes externally supplied configuration from derived state and "
                "this is the host's, not the target's. The one thing inside it that IS "
                "the target's — zotseek-models/ — is declared a derived-state root "
                "above, so it is accounted for by declaration rather than by exemption. "
                "Read the exemption for exactly what it says, and the statement is "
                "narrower than a reader might assume: a green residue verdict on this "
                "target means nothing appeared in the data directory OUTSIDE the host's "
                "own named entries. It says nothing about the profile, nothing about the "
                "sandbox HOME, and nothing about the interiors of the host's own "
                "data-directory subdirectories, five of which are exempted with their "
                "whole contents (see the entries below). A file strayed into any of "
                "those is invisible to this sweep",
            ),
            (
                profile / "prefs.js",
                "listed a second time, and separately, because the first exemption "
                "would otherwise bury a finding. This file carries state the TARGET "
                "creates: sixteen keys under its own preference prefix after a first "
                "run, none of them present in the host-only arm. derived_state_roots is "
                "a tuple of paths, so the interface cannot express it — the unit here "
                "would have to be a key inside a file the host owns and rewrites. "
                "Declaring the file a root would claim the host's entire preference "
                "store for the target; omitting it would hide state the target creates. "
                "This entry is the admission, not the resolution",
            ),
            (
                arena / HOST_LOG,
                "the HARNESS's own instrument, not the target's state, and it is listed "
                "here because the first real run of this adapter reported it as residue "
                "— the only residue in 931 created files. The arena is documented as "
                "harness-owned, but the sweep counts every file in it as the target's, "
                "so an adapter cannot instrument inside its own arena without declaring "
                "the instrument. It is not avoidable by piping instead: this target's "
                "host is a desktop application whose stdout is the only diagnostic when "
                "it fails to come up, and an in-memory capture would be gone by the time "
                "anyone read the verdict. Neither other adapter meets this, because "
                "neither has a process whose output has to survive the run",
            ),
        ) + tuple(
            (
                data / entry,
                "the host application's own file in its data directory, measured in a "
                "host-only control arm (identical launch, no plugin installed) on "
                "padme, 2026-09-03. Exempted entry by entry rather than by exempting "
                "the data directory, so that the sweep stays able to see a file the "
                "target strays into the one directory it does write to. Where the entry "
                "is itself a directory — translators, styles, locate, storage, cache, "
                "logs, pipes, tmp — the whole of its contents is exempted with it, and "
                "the sweep is blind inside them. That is a real limit and not a "
                "formality: storage/ is the attachment store, so derived state written "
                "there would not be seen",
            )
            for entry in HOST_DATA_ENTRIES
        ),
    )


class ZotSeek:
    """Transport for the declaration above, and nothing else.

    Constructed on an arena the harness owns and on the two things it cannot
    guess: the host application's launcher and the pinned release artifact.
    """

    def __init__(self, arena: Path, *, launcher: Path, artifact: Path,
                 port: int = 23219, display: str = ":1",
                 startup_timeout: float = 300.0, settle: float = 20.0) -> None:
        arena = Path(arena).resolve()
        if arena == Path.home().resolve():
            raise ValueError(
                "refusing to run introfini/ZotSeek against the operator's own HOME. The "
                "arena holds this target's sandbox HOME, the host application's profile "
                "and its data directory, so a run without one starts a desktop "
                "application against the operator's real profile and library, and the "
                "residue sweep that reads this declaration then reports on it."
            )
        self.arena = arena
        self.home = arena / "home"
        self.profile = arena / "profile"
        self.data = arena / "data"
        self.launcher = Path(launcher)
        self.artifact = Path(artifact)
        self.port = int(port)
        self.display = display
        self.startup_timeout = float(startup_timeout)
        self.settle = float(settle)
        self._digest = _sha256(self.artifact) if self.artifact.is_file() else ""
        if self.artifact.is_file() and self._digest != ARTIFACT_SHA256:
            raise ValueError(
                f"{self.artifact} is not the pinned artifact: sha256 {self._digest} "
                f"against the declared {ARTIFACT_SHA256}. A declaration that pins a "
                "revision while a different file runs is a lie the artifact cannot "
                "detect, so this is refused rather than warned about."
            )
        self.declaration = declaration(arena, port=self.port)
        self._process: subprocess.Popen | None = None

    # ---- adapter-declared harness setup, deliberately not an interface verb ----

    @property
    def sidecar(self) -> Path:
        """The file whose appearance says the TARGET started, not the host."""
        return self.data / "zotseek.sqlite"

    @property
    def installed_artifact(self) -> Path:
        return self.profile / "extensions" / f"{ADDON_ID}.xpi"

    def harness_prefs(self) -> tuple[tuple[str, str], ...]:
        """Every preference the harness writes, including the one that varies.

        The port is here rather than in the module constant because two lanes on
        one machine need different ones, and a declared value that is not the
        value written is worse than no declaration.
        """
        return (("extensions.zotero.httpServer.port", str(self.port)), *HARNESS_PREFS)

    def _write_profile(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.data.mkdir(parents=True, exist_ok=True)
        (self.profile / "extensions").mkdir(parents=True, exist_ok=True)
        lines = [f'user_pref("{name}", {value});' for name, value in self.harness_prefs()]
        (self.profile / "prefs.js").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _place_artifact(self) -> None:
        """Sideload the pinned XPI, which is the file-level form of the GUI install.

        `cp --reflink=auto` where it is available: the artifact is 103 MB and the
        arena tree is btrfs on the machine this runs on, so a run that needs five
        arenas should not need half a gigabyte. A plain copy is the fallback and
        the result is the same file either way.
        """
        target = self.installed_artifact
        if target.exists():
            return
        if not self.artifact.is_file():
            raise RuntimeError(
                f"the pinned artifact is not at {self.artifact}. Construction does not "
                "refuse a missing one, deliberately — the declaration must read on a "
                "machine where nothing is installed — so the refusal lands here, where "
                "a run would otherwise start a host with no plugin in it and measure "
                "the host."
            )
        try:
            subprocess.run(["cp", "--reflink=auto", str(self.artifact), str(target)],
                           check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            shutil.copyfile(self.artifact, target)

    def environment(self) -> dict[str, str]:
        """HOME and DISPLAY, and nothing inherited that could reconfigure the host.

        HOME is the sandbox. DISPLAY is not optional: the host is a desktop
        application and there is no headless mode, so an adapter that dropped it
        would report a startup failure as a target defect.
        """
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["DISPLAY"] = self.display
        env.pop("XAUTHORITY", None)
        return env

    @contextmanager
    def running(self):
        """Start the host, wait for the TARGET, yield, stop the host.

        The wait is on the plugin's own sidecar database rather than on the host's
        readiness, for the reason in this module's docstring: a host that came up
        with a plugin that did not load is a green nobody can see.
        """
        self._write_profile()
        self._place_artifact()
        argv = [str(self.launcher), "-profile", str(self.profile),
                "-datadir", str(self.data), "-no-remote"]
        log = self.arena / HOST_LOG
        started = time.monotonic()
        with log.open("wb") as sink:
            self._process = subprocess.Popen(
                argv, stdout=sink, stderr=subprocess.STDOUT, env=self.environment(),
                start_new_session=True,
            )
            try:
                self._await_target(started)
                yield
            finally:
                process, self._process = self._process, None
                self._stop(process)

    def _stop(self, process: subprocess.Popen) -> None:
        """Stop the host and everything it started, by process group.

        The launcher is a shell script that execs the real binary, and the
        application in turn starts the desktop browser and the office suite's
        registration helper. Signalling the direct child alone leaves those
        reparented to init and still running, and the egress tracer follows
        descendants — so it waits for them, and a run that has finished its work
        hangs until the tracer's own timeout. Measured while building this
        adapter: a control arm left a reparented host process alive and its
        traced run never returned. `start_new_session` is what makes the group
        addressable; without it the kill would reach this harness too.
        """
        group = os.getpgid(process.pid)
        for signal_number, grace in ((15, 60), (15, 20), (9, 30)):
            if process.poll() is not None and not self._group_alive(group):
                return
            try:
                os.killpg(group, signal_number)
            except (ProcessLookupError, PermissionError):  # pragma: no cover
                pass
            try:
                process.wait(grace)
            except subprocess.TimeoutExpired:  # pragma: no cover - grace path
                continue

    @staticmethod
    def _group_alive(group: int) -> bool:
        try:
            os.killpg(group, 0)
        except (ProcessLookupError, PermissionError):
            return False
        return True

    def _await_target(self, started: float) -> None:
        while time.monotonic() - started < self.startup_timeout:
            if self.sidecar.exists():
                time.sleep(self.settle)
                return
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(
                    f"the host application exited with {self._process.returncode} before "
                    f"{self.sidecar.name} appeared. The target's own sidecar is the "
                    "readiness signal, so this says the plugin never initialised; the "
                    f"host's output is at {self.arena / 'host.log'}."
                )
            time.sleep(2)
        raise RuntimeError(
            f"{self.sidecar.name} did not appear in {self.startup_timeout:g}s. This is "
            "the target failing to initialise inside a host that may well be running, "
            "which is why the wait is on the target's file and not on the host's."
        )

    def target_preferences(self) -> dict[str, str]:
        """The target's own preference keys as the profile currently carries them.

        Read from the file the host writes and an ordinary user edits. The host
        flushes it asynchronously and on shutdown, so a call during a first run
        sees fewer keys than a later one; the measured full set is in the
        declaration's `default_configuration`, and this is what is true right now.
        """
        found: dict[str, str] = {}
        path = self.profile / "prefs.js"
        if not path.is_file():
            return found
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _USER_PREF.match(line.strip())
            if match and match.group(1).startswith(TARGET_PREF_PREFIX):
                found[match.group(1)] = match.group(2)
        return found

    # ---- the seven verbs -------------------------------------------------

    def install(self) -> dict:
        """Report the sideload and what it materialised. It has already happened.

        There is no install surface to call: this target materialises when the
        host starts with the XPI in its profile, which `running()` has done by the
        time this is reached. Acquiring the artifact is out of scope for an
        adapter — it is a network operation, and the pinned digest above is what
        makes the acquired file auditable.
        """
        return {
            "verb": "install",
            "channel": (
                "the pinned XPI placed in the profile's extensions/ directory, which is "
                "the file-level form of the host's Add-ons > Install from file; made "
                "active without a GUI click by the two scope preferences declared under "
                "`process`"
            ),
            "artifact": ARTIFACT,
            "artifact_sha256": self._digest,
            "artifact_bytes": self.artifact.stat().st_size if self.artifact.is_file() else None,
            "addon_id": ADDON_ID,
            "installed_at": str(self.installed_artifact),
            "version": VERSION,
            "commit": COMMIT,
            "materialized": {
                str(root): (root.stat().st_size if root.is_file() else
                            "directory" if root.is_dir() else None)
                for root in self.declaration.derived_state_roots
            },
            "target_preference_keys": sorted(self.target_preferences()),
        }

    def uninstall(self) -> dict:
        """Absent. The hook is real; nothing a machine can do fires it.

        `bootstrap.js:90-141` deletes the sidecar database, its journal siblings
        and the whole preference branch — for reason 6 only. Measured with a
        control arm on padme 2026-09-03: removing the sideloaded XPI while the
        host is stopped and restarting does not fire it, and the plugin loads
        anyway. The declaration carries the measurement; the harness does not
        delete the declared state itself, because that is the clean result R15's
        uninstall clause forbids manufacturing.
        """
        raise UnsupportedVerb(self.declaration.name, "uninstall")

    def configure(self) -> dict:
        """Report the configuration in effect. Nothing of the target's is set.

        The target's configuration channel is the host's preference system, read
        through its own preference pane. The default configuration is what an
        ordinary user gets, so the harness sets none of the target's preferences
        and this verb reports rather than changes — the same shape the first
        adapter uses, for the same reason.
        """
        observed = self.target_preferences()
        return {
            "verb": "configure",
            "applied_at": "process start",
            "channel": "the host application's preference store, via the profile",
            "harness_preferences": dict(self.harness_prefs()),
            "target_preferences_set_by_the_harness": {},
            "target_preferences_observed": observed,
            "observed_count": len(observed),
            "caveat": (
                "the host flushes its preference file asynchronously and on shutdown, "
                "so a call made early in a first run sees fewer keys than the same call "
                "later. The measured full set is recorded in the declaration's "
                "default_configuration; this field is what the profile carries at the "
                "moment of the call, and the two are allowed to differ."
            ),
        }

    def query(self, q: str, mode: str, limit: int) -> dict:
        """Absent: GUI dialogs, plus endpoints behind an opt-in preference."""
        raise UnsupportedVerb(self.declaration.name, "query")

    def status(self) -> dict:
        """Absent: a GUI dialog, plus an endpoint behind the same opt-in preference.

        Measured rather than assumed, per the lane's instruction: the sidecar
        database is readable with no opt-in and carries no status — one metadata
        row, `schema_version`, and the model in effect lives in a host preference
        instead (src/core/model-registry.ts:103-115).
        """
        raise UnsupportedVerb(self.declaration.name, "status")

    def pause(self) -> dict:
        """Absent: the background work is off by default and the control is a button."""
        raise UnsupportedVerb(self.declaration.name, "pause")

    def resume(self) -> dict:
        """Absent, for pause's reason and by the same progress-window button."""
        raise UnsupportedVerb(self.declaration.name, "resume")


#: The targets this module builds. The registry in `__init__.py` walks the
#: package and reads this rather than holding a written-down list, so declaring
#: it here is what makes the adapter selectable — and what lets the
#: target-neutrality guard learn this target's name without being told it.
NAMES = ("zotseek",)


def build(name: str, arena: Path, *, launcher: str = "", artifact: str = "",
          port: str | int = 23219, display: str = ":1",
          startup_timeout: str | float = 300.0, **_opts) -> ZotSeek:
    """Construct the adapter from the driver's opaque `--adapter-option` pairs.

    Neither the launcher nor the artifact is defaulted, and both refusals are the
    point. A guessed launcher is how a run measures a host application nobody
    chose — and on this target the host is half the measurement, since R10's
    subject is its process tree. A guessed artifact is how a run measures a
    revision nobody pinned; the digest check in the constructor is the second
    line, this is the first.
    """
    if not launcher:
        raise SystemExit(
            "this adapter needs the host application's launcher "
            "(--adapter-option launcher=<path>). It is not defaulted: this target is a "
            "plugin, the host is what the harness starts, and R10's subject is the "
            "host's process tree — so a guessed host silently changes what was measured."
        )
    if not artifact:
        raise SystemExit(
            "this adapter needs the pinned release artifact "
            f"(--adapter-option artifact=<path to {ARTIFACT}>). It is not defaulted: "
            "the declaration pins a commit and a digest, and a guessed file is how an "
            "artifact comes to describe a revision that never ran."
        )
    return ZotSeek(
        Path(arena),
        launcher=Path(launcher),
        artifact=Path(artifact),
        port=int(port),
        display=display or os.environ.get("DISPLAY", ":0"),
        startup_timeout=float(startup_timeout),
    )
