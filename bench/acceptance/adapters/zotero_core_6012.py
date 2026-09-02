"""The adapter for Zotero core PR #6012, the layer's platform-native target.

Ticket 0583. The contract is `interface.py`, owned by `SPEC.md` §5.2.8 and the
`DECISIONS.md` entry ratified 2026-09-02; neither is restated here. What this
module holds is a declaration and the minimal transport needed to invoke the
surfaces it declares — no patch or workaround, no non-default option, no access
unavailable to the target's own users, and no scoring of a result.

**No line of this target's code is reproduced here.** Every claim below is
either a `path:line` citation into the pinned source tree or a measurement taken
on padme, 2026-09-03, and named as such.

**What makes this seat different from the other four.** The other adapters drive
a process the harness starts (zoteus, zotero-mcp) or a plugin loaded by a host
the harness starts (ZotSeek, Beaver). Here the target IS the reference manager.
There is no host to separate it from, no plugin to install, and no wire between
the two. Every consequence below follows from that one fact, and they run in
both directions: two of the plugin lane's hardest problems vanish, and two new
ones appear that no other seat has.

---

## What the interface could not express

**1. `check_local_by_default` reds a target that has no embedder, and the layer's
own vocabulary already has the word for that case.** This is the sharpest
finding of the seat and the only one that is a defect rather than a limit.

`assertions.py` declares the normalized status shape as
`locality: "local" | "remote" | "none"` — three values, and `"none"` is there
because a target may have no embedder in effect. `check_local_by_default` then
computes `PASS if locality == "local" and active is True else FAIL`. So a target
honestly reporting `"none"` is scored `fail` against a clause that reads "the
embedder is local in the target's default configuration". It is not failing to
be local. There is nothing there to be local or remote, and the verdict a reader
needs is the fourth state, not the second.

In the default configuration this target is exactly that case:
`build/defaults/preferences/zotero.js:121` declares
`extensions.zotero.embeddings.model` as `""` with the comment
`disabled when ""`, and `embeddings.js:171-173, 179-181` turns an unknown model
name into `isEnabled() === false`. The feature under test is off, and turning it
on is a non-default option the ratified contract forbids in as many words.

This adapter does not reach that assertion at all — `status` is absent for the
independent reason in finding 2 — so nothing here is shaped to dodge it. The
defect is reported rather than worked around, and `tests/` drives it red against
a local fake so the report rests on an execution and not on a reading.

**2. The target has the roster's most complete status object, and no transport
carries it.** `Zotero.Embeddings.Indexing.getStatus()`
(`chrome/content/zotero/xpcom/embeddings.js:2872-2889`) returns `enabled`,
`model`, `indexing`, `stopping`, `paused`, `phase`, per-library
`indexed`/`eligible` and `indexedAttachments`/`eligibleAttachments` counts,
download and extraction progress and the last error. That is a closer fit to
this layer's normalized status — and to the coverage sentence of `SPEC.md`
§5.2.8 — than anything the other four targets publish. Its own doc comment says
what it is for: "for the preferences UI".

Nothing exposes it. Re-derived at this head, with the positive control the
`BRIDGE-0496` note used at `77e2c4b`: enumerating every
`Zotero.Server.Endpoints[...]` registration in `xpcom/server/` returns the
connector set, the integration set and the local-API set, and not one of them
reaches `Zotero.Embeddings` or `Zotero.ML`. So the field the interface wants is
computed, complete, and unreachable. `query_transport` and the status contract
both presume a wire; here the wire is the missing half.

**3. `query_transport` has to describe something that is not a transport.** The
lane's instruction was to say what it actually is, and the answer is: the
target's query surface is its own user interface. A search runs inside the
application's window, against its own data layer, in the process that owns the
library. There is no protocol, no port and no client — not because the target
hides one, but because a reference manager searching its own library has nothing
to send anything to. zoteus's index build reads Zotero over the local HTTP API
and both plugin targets read the host's data layer in-process; this target *is*
the data layer. The field can say that only in prose.

**4. R10's attribution wall, in its purest form: the target IS the process.**
The ZotSeek and Beaver lanes each found independently that every name lookup
issues from one pid — the host's main process — so a process tracer cannot
separate a plugin's egress from its host's. Here that is not a limitation of the
instrument at all: the process under trace is the target, wholly, and there is
no second party to attribute anything to. What the plugin lanes had to report as
unattributable, this seat can report as simply the target's.

The price is the other half. There is no host-only control arm, because
subtracting the host would be subtracting the target. The three cells recorded
under `process` are this build's own baseline, taken with the same driver the
lane lead used for Zotero 10.0.1 so the two are comparable; nothing is
subtracted anywhere, in code or by hand.

**5. Two plugin-lane problems disappear, and it is worth recording which.**
ZotSeek's finding 6 — the readiness signal has to watch the plugin's own file,
because the host coming up says nothing about whether the target loaded — has no
analogue here: the host's database IS the target's database, so
`data/zotero.sqlite` is the readiness signal with no ambiguity to resolve. And
ZotSeek's finding 1 — `not_derived_state` has to carry the host application
itself — mostly dissolves: the data directory and the profile are the target's
own, wholesale, and `derived_state_roots` can say so. This is the first seat on
the roster where that field means what it was written to mean.

**6. What does not dissolve: state the target causes inside a third
application.** The application registers its word-processor integration on first
run, and the office suite's own installer writes `~/.config/libreoffice/`
(measured; the run's log carries `unopkg`'s output). `derived_state_roots` is a
tuple of paths and cannot express "the part of another program's configuration
store that I caused". It is exempted below with exactly that argument, which is
an admission and not a resolution — the same shape as ZotSeek's preference-key
finding, in a different object class.

**7. The target names all three of R33's modes in one preference, and the
harness cannot reach any of them.** `build/defaults/preferences/zotero.js:110-113`
declares `extensions.zotero.search.bestMatchEngine`, default `"hybrid"`, with
the comment "Temporary, for testing: which engine best-match search runs --
'lexical', 'semantic', or 'hybrid' (both, fused)". Read at
`xpcom/bestMatch.js:815-830`. That is `exact` / `meaning` / `combined` under the
target's own names, in a single selector — the only such selector on the roster,
where zotero-mcp has two disjoint tools and no fusion at all. `MODES` could
express it and `query` is absent, so no assertion ever asks. Recorded because
the next lane to reach a query surface on this target will want it.

---

## The pin, and the one thing that makes it checkable

#6012 force-pushed off `77e2c4b` at 2026-09-02T19:23:11Z, so a ref is not a pin:
`refs/pull/6012/head` names whatever the branch holds today. The commit is the
pin, and the build carries it. `app/scripts/dir_build` stamps the short hash
into `application.ini`'s `Version`, so a built tree says which revision it came
from — `Version=11.0.SOURCE.19e79625b` — and this adapter refuses a build whose
stamp is not the pinned one rather than documenting the requirement. A
declaration that pins a revision while a different build runs is a lie the
artifact cannot detect.

## The build recipe, because "reproducible target setup" is exit criterion one

Recorded here rather than in a note nobody reads, and the dead ends are recorded
with it because each one costs an hour to rediscover.

1. `zotero/zotero-standalone-build` is LEGACY. Its `fetch_xulrunner` is now
   `fetch_xulrunner.sh`, and its `dir_build` calls `build_xpi`, which wants an
   `install.rdf` this tree has not carried since Zotero 4.
2. The packaging scripts are vendored into the client tree at `app/scripts/`.
3. The route is `app/scripts/fetch_xulrunner -p l` then
   `app/scripts/dir_build -p l`, from a checkout detached at the pinned commit
   with `npm ci` done.
4. `dir_build` stops on `app/linux/updater.tar.xz not checked out`. That file is
   a Git LFS object; install git-lfs, then `git lfs install --local` and
   `git lfs pull`. A stub was rejected deliberately: a build shaped by the
   harness is not the platform-native thing under test, and this seat exists to
   measure the platform-native thing.

The product is `app/staging/Zotero_linux-x86_64/zotero`, a shell launcher, with
`app/application.ini` beside it. `--adapter-option application=<that launcher>`
is what this adapter needs; it is not defaulted, for the reason ZotSeek's
launcher is not defaulted.
"""

import os
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from ..interface import Declaration, UnsupportedVerb

#: The head `gh api repos/zotero/zotero/pulls/6012` returned on 2026-09-03. The
#: pull request force-pushed off `77e2c4b` at 2026-09-02T19:23:11Z, so the ref
#: is not a pin and the commit is. If a refetch cannot find this object, that is
#: a finding to report, not a licence to take the newer head.
COMMIT = "19e79625b1c6fbbdd75367aa85b62d5a7080d7f6"

#: What `app/scripts/dir_build` stamps into `application.ini`'s `Version`: the
#: literal string a built tree carries, and the only machine-checkable link
#: between this declaration and the binary that runs.
VERSION = "11.0.SOURCE.19e79625b"

#: The build measured here. Recorded rather than enforced: a rebuild of the same
#: commit produces a different BuildID, and refusing that would refuse a
#: correctly reproduced target.
BUILD_ID = "20260903011524"

#: The three preference keys the pull request declares for the feature under
#: test, with their shipped defaults, read from
#: `build/defaults/preferences/zotero.js:120-125` in the built tree at COMMIT.
#: `embeddings.model` is the switch: `""` means disabled, and
#: `xpcom/embeddings.js:179-181` makes an unknown name mean not enabled.
DECLARED_EMBEDDING_PREFS = {
    "extensions.zotero.embeddings.model": '""  (the comment reads: disabled when "")',
    "extensions.zotero.embeddings.indexingPaused": "false",
    "extensions.zotero.embeddings.indexFulltext": "false",
}

#: Preference prefixes whose keys this adapter reads back out of the profile for
#: `configure()`. The target's own branch for the feature under test, plus the
#: one selector that names R33's three modes.
TARGET_PREF_PREFIXES = (
    "extensions.zotero.embeddings.",
    "extensions.zotero.search.bestMatch",
)

#: The preferences the harness writes into the profile before the target starts.
#: Every one is harness setup, declared under `process`, and none touches the
#: feature under test.
#:
#: The port move exists only so this instance can coexist with the operator's
#: own and with the other lanes' — and on this target it must be declared for a
#: second reason: it relocates the target's own HTTP server, which is the
#: surface `query` and `status` were assessed against. `httpServer.enabled` is
#: written at its shipped default (`true`, same file:171) so the profile says
#: what was measured rather than leaving it implicit; `app.update.enabled` is
#: false because an update that replaced the binary mid-run would silence the
#: pin check.
HARNESS_PREFS = (
    ("extensions.zotero.httpServer.enabled", "true"),
    ("app.update.enabled", "false"),
)

#: Where this adapter captures the target's own output. Harness instrument, not
#: target state — declared under `not_derived_state` for ZotSeek's reason: the
#: arena is harness-owned but the sweep counts every file in it.
HOST_LOG = "host.log"

#: `user_pref("<name>", <value>);` as the target writes it.
_USER_PREF = re.compile(r'^user_pref\("([^"]+)",\s*(.*)\);\s*$')


def read_application_ini(application: Path) -> dict[str, str]:
    """`Name`, `Version` and `BuildID` from the build beside a launcher.

    A free function because the pin check and the artifact both want it, and
    because a caller with no launcher must still be able to read the
    declaration.
    """
    for candidate in (application.parent / "application.ini",
                      application.parent / "app" / "application.ini"):
        if not candidate.is_file():
            continue
        fields: dict[str, str] = {}
        for line in candidate.read_text(errors="replace").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in ("Name", "Version", "BuildID"):
                fields[key.strip()] = value.strip()
        if fields:
            fields["_path"] = str(candidate)
            return fields
    return {}


def declaration(arena: Path, *, port: int = 23519) -> Declaration:
    """The declaration for a target sandboxed in `arena`.

    A free function for the reason the other adapters' are: the declaration is
    the readable half of an adapter, and a contract check must be able to obtain
    it on a machine where no build exists.
    """
    arena = Path(arena)
    home, profile, data = arena / "home", arena / "profile", arena / "data"
    return Declaration(
        name="zotero/zotero#6012",
        revision=(
            f"Zotero core pull request #6012 at commit {COMMIT}, built from source on "
            f"padme 2026-09-03. The build stamps its own provenance: application.ini "
            f"reads Name=Zotero Version={VERSION} BuildID={BUILD_ID}, and the Version "
            f"string carries the pinned short hash, which is what this adapter checks "
            f"at construction rather than documents. The pull request force-pushed off "
            f"77e2c4b at 2026-09-02T19:23:11Z, so refs/pull/6012/head is not a pin and "
            f"the commit is; the BuildID is recorded and NOT enforced, because a "
            f"faithful rebuild of the same commit produces a different one. No release "
            f"carries this revision — the build recipe is in this module's docstring, "
            f"and it is the whole of what makes the target setup reproducible."
        ),
        derived_state_roots=(
            # 1. The data directory named by -datadir: zotero.sqlite and its
            #    wal, fulltext.sqlite, storage/, styles/, translators/, locate/.
            #    Measured 2026-09-03: 769 files after a first run against an
            #    empty library, reproduced to the file across two runs. On a
            #    plugin target this directory is the host's and has to be
            #    exempted entry by entry; here it is the target's own, which is
            #    the first time on this roster that this field says what it was
            #    written to say.
            data,
            # 2. The profile named by -profile: the preference store, the
            #    add-on registry, the startup cache, the certificate and cookie
            #    stores. Measured: 16 files, and prefs.js carries NONE of the
            #    target's own keys after a run (see `default_configuration`).
            profile,
            # 3-4. The toolkit's caches and profile registry under the sandbox
            #      HOME. Unambiguously this target's: it is the toolkit this
            #      application ships and starts. Declared as roots rather than
            #      swept under the HOME exemption below, so that they are
            #      accounted for by declaration.
            home / ".cache" / "mozilla",
            home / ".config" / "mozilla",
            # 5-6. The application's own cache and configuration roots under
            #      HOME, created even though -profile and -datadir are both
            #      given explicitly. Measured: home/.cache/zotero/zotero and
            #      home/.config/zotero/zotero exist after every run.
            home / ".cache" / "zotero",
            home / ".config" / "zotero",
            # 7. The download directory the toolkit creates on start. Empty in
            #    every run measured here; declared because it appears.
            home / "Downloads",
            # 8. Where the vectors would live if the feature were on: a separate
            #    database ATTACHed to the main one (xpcom/embeddings.js:280,
            #    :304-316, tables created at :403, :422, :432). Declared and
            #    MEASURED ABSENT — no embeddings.sqlite is created in the
            #    default configuration, because nothing calls initDB when
            #    isEnabled() is false. An undeclared path that appears the
            #    moment someone selects a model would be residue.
            data / "embeddings.sqlite",
        ),
        query_transport=(
            "none, and the field is being asked to describe something that is not a "
            "transport. This target is the reference manager itself, so its query "
            "surface is its own user interface: a search runs inside the application's "
            "window, in the process that owns the library, against its own data layer. "
            "zoteus reads Zotero over the local HTTP API and the two plugin targets read "
            "the host's data layer in process; this target IS the data layer, and there "
            "is nothing for it to send anything to.\n\n"
            "What a machine could reach, measured rather than read. The target's HTTP "
            f"server does start in the default configuration — httpServer.enabled is "
            f"true at build/defaults/preferences/zotero.js:171, gated at "
            f"xpcom/zotero.js:715-716 — and it answers on 127.0.0.1:{port}. Measured "
            "2026-09-03: GET /connector/ping returns 200 and the literal body "
            "'<!DOCTYPE html><html><body>Zotero is running</body></html>'. That is a "
            "liveness signal; the POST form returns a fixed connector-preferences "
            "bundle (xpcom/server/server_connector.js, Ping.init) which names nothing "
            "about retrieval or embeddings. Every /api/ route answers 403 'Local API is "
            "not enabled' — measured on /api/, /api/users/0/items?q=test and POST "
            "/api/local/authorize alike — because httpServer.localAPI.enabled is false "
            "at build/defaults/preferences/zotero.js:173 and gated at "
            "xpcom/server/server_localAPI.js:249.\n\n"
            "This resolves an open observation from the lane's build smoke, which "
            "recorded code=000 on that port and left the cause unestablished: the "
            "server does answer, and a short smoke had not yet reached the point where "
            "it listens. Reported because a null that was never explained is how a "
            "false negative survives."
        ),
        default_configuration=(
            "the platform-native build at the pinned commit, launched with -profile, "
            "-datadir and -no-remote against an empty library, with no preference of "
            "the target's own set by the harness.\n\n"
            "THE FEATURE UNDER TEST IS OFF. build/defaults/preferences/zotero.js:120-125 "
            "declares exactly three embedding preferences — embeddings.model \"\", with "
            "the comment 'disabled when \"\"'; embeddings.indexingPaused false; "
            "embeddings.indexFulltext false — and xpcom/embeddings.js:171-173, 179-181 "
            "makes an unknown model name mean isEnabled() is false. Independent "
            "confirmation, from a built tree, of what the BRIDGE-0496 note read from "
            "the pull request's API diff at 77e2c4b. Selecting a model is a non-default "
            "option, which the ratified contract forbids in as many words, so nothing "
            "here turns it on to get a greener run. Consequences that decide what this "
            "target can be asked: no embedder is in effect, so R10's local-by-default "
            "clause has no embedder to be about (see this module's finding 1); nothing "
            "is downloaded, so R15's model-cache clause has no download to be about; and "
            "no embeddings.sqlite is created, measured.\n\n"
            "MEASURED READ-BACK, not transcribed from the shipped defaults, because the "
            "ZotSeek lane found the two can differ: after a full start and a clean "
            "shutdown the profile's prefs.js carries exactly ONE key, the harness's own "
            "httpServer.port. The target writes NONE of its own preference keys — not "
            "one of the three above, not bestMatchEngine — because the toolkit omits a "
            "preference still sitting at its built-in default. So the effective "
            "configuration is the shipped one, and the evidence for that is the absence "
            "rather than a transcription. (Contrast ZotSeek, which writes sixteen keys "
            "and whose effective set differs from its shipped file.)\n\n"
            "Two further facts about the default configuration, both re-derived at this "
            "head. The retrieval-mode selector search.bestMatchEngine defaults to "
            "'hybrid' and is marked 'Temporary, for testing' "
            "(build/defaults/preferences/zotero.js:110-113, read at "
            "xpcom/bestMatch.js:815-830); its three values are R33's three modes under "
            "the target's own names. And the outbound preference embeddings.endpoint, "
            "which routes passage embedding to an external server, is read at "
            "xpcom/embeddings.js:1034 and is declared in no preferences file and named "
            "in no preferences pane — still undeclared at this head, as the BRIDGE-0496 "
            "note found at 77e2c4b. Empty by default, so it changes nothing about what "
            "was measured; recorded because an undeclared preference that decides where "
            "library text goes is R10's business."
        ),
        process=(
            "the harness starts the TARGET, and there is no host to separate it from — "
            "which is the whole of what makes this seat different from the plugin ones. "
            "Start: the build's launcher with -profile, -datadir and -no-remote, under "
            "HOME set to a scratch directory inside the arena and DISPLAY pointed at an "
            "existing X server, with the profile carrying three harness preferences and "
            "nothing else. There is no headless mode.\n\n"
            "Readiness is the appearance of data/zotero.sqlite, measured at 2 s. On a "
            "plugin target that file is the host's and proves nothing about the target, "
            "so ZotSeek has to wait on a file the plugin itself writes; here the two "
            "coincide, and the ambiguity that adapter had to engineer around does not "
            "exist. A settle window follows, because the data directory is still filling "
            "when the database appears.\n\n"
            "Stop: signal the whole process GROUP, on SIGTERM twice and then SIGKILL. "
            "The launcher is a shell script that execs the real binary, and the "
            "application starts the office suite's registration helper (measured: the "
            "run's log carries unopkg's output) — so signalling the direct child leaves "
            "descendants reparented and alive, holding the databases open, and the "
            "egress tracer follows descendants and waits for them. Both plugin lanes hit "
            "this independently. `start_new_session` is what makes the group "
            "addressable without the kill reaching the harness.\n\n"
            "HOME is the sandbox and the adapter refuses the operator's own. What "
            "appears under it, measured 2026-09-03: .cache/{mozilla,zotero,fontconfig,"
            "nvidia}/, .config/{mozilla,zotero,pulse,libreoffice}/ and Downloads/, with "
            "the top-level shape identical across two runs and the file counts NOT — "
            "1742 and 1498 — the difference living inside the font, GL-shader and "
            "office-suite caches. The four that are the target's or its toolkit's are "
            "declared as derived-state roots; the rest are exempted below.\n\n"
            "R10's SUBJECT IS THIS TARGET'S OWN PROCESS, exactly and with nothing else "
            "in it. The plugin lanes each found that a process tracer cannot separate a "
            "plugin from its host, since every name lookup issues from one pid; here "
            "that pid is the target, so this seat reports as the target's what they had "
            "to report as unattributable. The other half of the same fact is that there "
            "is NO host-only control arm available — subtracting the host would be "
            "subtracting the target — and none is attempted.\n\n"
            "THIS BUILD'S OWN BASELINE, three cells, measured on padme 2026-09-03 with "
            "the same driver the lane lead used for Zotero 10.0.1 (bench/r10_host_"
            "baseline.py, PR #234), so the two are comparable; the artifact is "
            "bench/results/0583-zotero-6012/r10-baseline.json and the numbers are "
            "repeated in this adapter's own artifact. THE ARENA STATE IS PART OF THE "
            "MEASUREMENT and is stated plainly: this adapter runs against a VIRGIN "
            "profile and data directory, created fresh inside the arena on every "
            "construction, never seeded and never cleared afterwards — which is the "
            "expensive end of the range, because a first run does the update, blocklist "
            "and first-run work a warmed one does not. Nothing is subtracted anywhere, "
            "in code or by hand: the artifact carries the cells and a reader compares "
            "them."
        ),
        unsupported={
            "uninstall": (
                "there is no removal surface anywhere in this target, and the reason is "
                "the fourth distinct one on this roster. zoteus reports no such surface "
                "yet; zotero-mcp reports that the documented removal is uninstalling a "
                "package; ZotSeek reports a real uninstall hook with no trigger a "
                "machine can reach. This target reports something else again: it is the "
                "application, so its removal is deleting the tree the operator unpacked "
                "— an operation of the file system, not of the target — and the state it "
                "leaves behind is the data directory, which is THE USER'S LIBRARY. A "
                "reference manager that offered to delete its own data directory would "
                "be offering to delete the thing it exists to keep. Grepping the target "
                "for an uninstall surface at the pinned commit returns only the plugin "
                "manager's own machinery for uninstalling OTHER add-ons "
                "(xpcom/plugins.js) and a vendored regular-expression library's "
                "unrelated install/uninstall API. The harness will not delete the "
                "declared roots on the target's behalf: R15's uninstall clause forbids "
                "manufacturing a clean result that way"
            ),
            "query": (
                "the surface is the application's own user interface, and no machine "
                "route to it exists in the default configuration. Measured on the "
                "running build 2026-09-03, not read: every /api/ route answers 403 "
                "'Local API is not enabled' (xpcom/server/server_localAPI.js:249; the "
                "preference is false at build/defaults/preferences/zotero.js:173), and "
                "the endpoints that ARE on by default are the browser connector's — "
                "ping, translator and save routes, none of which searches a library. "
                "Enabling the local API is a non-default option, which the contract "
                "forbids; it would also change R10's subject by opening a namespace the "
                "default configuration does not open. And it would not deliver a query "
                "even then: the one indirect route to inference at this head runs a "
                "saved search carrying a root-level bestMatch condition "
                "(data/searchConditions.js, data/search.js) over the local API, which "
                "returns ITEMS and no vector, embeds one query with no passage or batch "
                "path, and WRITES DURABLE LIBRARY STATE PER QUERY — a side effect "
                "masquerading as a transport (established at source in the BRIDGE-0496 "
                "note, re-derived here at this head). Its write path additionally needs "
                "POST /api/local/authorize, which prompts the user, and which answers "
                "403 here for the same reason. Finally there would be nothing behind it: "
                "with embeddings.model \"\" no embedder is in effect, so the 'meaning' "
                "mode has no engine at all"
            ),
            "status": (
                "this target computes the roster's most complete status object and no "
                "transport carries it, which is a fifth kind of absence and the finding "
                "this seat exists to produce. xpcom/embeddings.js:2872-2889 returns "
                "enabled, model, indexing, stopping, paused, phase, per-library "
                "indexed/eligible and indexedAttachments/eligibleAttachments counts, "
                "download and extraction progress and the last error — a closer fit to "
                "this layer's normalized status than anything else on the roster "
                "publishes — and its own doc comment says it is 'for the preferences "
                "UI'. Nothing exposes it: enumerating every Zotero.Server.Endpoints "
                "registration under xpcom/server/ at this head reaches the connector, "
                "integration and local-API sets and not one of them names "
                "Zotero.Embeddings or Zotero.ML, and the local API is 403 by default in "
                "any case. GET /connector/ping is on by default and is liveness only "
                "('Zotero is running'), which is not a status in this layer's sense — "
                "the harness observes convergence through status, and a liveness byte "
                "cannot carry a coverage sentence. Reading the preference file instead "
                "would answer from configuration where the clause is about a running "
                "process, and constructing a status the target does not publish is a "
                "workaround; neither is done"
            ),
            "pause": (
                "the roster's best-matching pause control, and the harness cannot reach "
                "it. SPEC.md §5.2.8 defines pause and resume as the two transitions of "
                "one durable background-work control, resume idempotent and never "
                "forcing a rebuild. That is exactly what this target implements: "
                "stopIndexing() at xpcom/embeddings.js:3141-3150 clears both queues, "
                "cancels the kick timer and persists embeddings.indexingPaused, and "
                "isPaused() at :1824-1826 reads it back — 'Persisted so a stop survives "
                "a restart', in the target's own comment. Both are called from ONE "
                "place, the preferences pane (preferences/preferences_advanced.js:103, "
                ":107), which is a GUI control; no route reaches them and the preference "
                "is settable only through the configuration editor or by editing the "
                "profile while the application is stopped. Even reached, it would govern "
                "nothing here: with embeddings.model \"\" there is no indexing to stop "
                "(:1809 gates the work on isEnabled()). So the control is real, durable "
                "and correct, the work it governs is off, and neither is machine-"
                "reachable — three separate things, and the reason field is the only "
                "place they can be told apart"
            ),
            "resume": (
                "absent for pause's reason and by the same GUI control. Worth recording "
                "separately because startIndexing() at xpcom/embeddings.js:2965-2971 is "
                "the contract's resume almost verbatim — it clears the paused "
                "preference, is documented as safe to call while the consumer is already "
                "running, and re-enqueues work that is then skipped by source hash "
                "rather than rebuilt — and because its FIRST line returns immediately "
                "when isEnabled() is false, which it is in the default configuration. A "
                "resume that is correct, idempotent, non-rebuilding and a no-op is not a "
                "verb the harness can assert against"
            ),
        },
        not_derived_state=(
            (
                arena / HOST_LOG,
                "the HARNESS's own instrument, not the target's state. The arena is "
                "documented as harness-owned but the residue sweep counts every file in "
                "it, so an adapter cannot capture its target's output inside its own "
                "arena without declaring the capture. Not avoidable by piping: this "
                "target is a desktop application whose stdout is the only diagnostic "
                "when it fails to come up, and an in-memory capture would be gone by the "
                "time anyone read the verdict",
            ),
            (
                home / ".cache",
                "the DESKTOP's shared cache root, and the exemption is deliberately "
                "narrower than it looks: the two subtrees under it that are the "
                "target's — .cache/mozilla and .cache/zotero — are declared as "
                "derived-state ROOTS above, so they are accounted for by declaration "
                "rather than by this exemption. What is exempted is the rest: the font "
                "configuration library's cache, the GL driver's shader cache, and the "
                "sound server's client cache, all written by libraries the toolkit "
                "links rather than by the target's own code, and all shared desktop "
                "state a user already has. Measured: their contents are the whole of the "
                "nondeterminism between two runs of this adapter (1742 files against "
                "1498). Read the limit for what it is — the sweep is blind inside "
                "this directory outside the two declared subtrees",
            ),
            (
                home / ".config",
                "the DESKTOP's shared configuration root, exempted on the same terms "
                "and with the same two-declared-subtrees structure: .config/mozilla and "
                ".config/zotero are declared roots above. What is exempted is the sound "
                "server's configuration and — the entry that is an admission rather than "
                "a formality — the office suite's, at .config/libreoffice/. That "
                "directory exists because the target registers its word-processor "
                "integration on first run and the office suite's own installer writes "
                "it (measured; the run's log carries unopkg's output). It is therefore "
                "state the TARGET CAUSES inside a THIRD program's configuration store, "
                "and derived_state_roots — a tuple of paths — has no way to say that. "
                "Declaring the directory a root would claim another program's "
                "configuration for this target; omitting it silently would hide state "
                "the target causes. This entry is the admission, not the resolution",
            ),
        ),
    )


class ZoteroCore6012:
    """Transport for the declaration above, and nothing else.

    Constructed on a harness-owned arena and on the one thing it cannot guess:
    the launcher of a build of the pinned revision.
    """

    def __init__(self, arena: Path, *, application: Path, port: int = 23519,
                 display: str = ":1", startup_timeout: float = 300.0,
                 settle: float = 20.0) -> None:
        arena = Path(arena).resolve()
        if arena == Path.home().resolve():
            raise ValueError(
                "refusing to run zotero/zotero#6012 against the operator's own HOME. "
                "The arena holds this target's sandbox HOME, its profile and its data "
                "directory, so a run without one starts a reference manager against the "
                "operator's real library, and the residue sweep that reads this "
                "declaration then reports on it."
            )
        self.arena = arena
        self.home = arena / "home"
        self.profile = arena / "profile"
        self.data = arena / "data"
        self.application = Path(application)
        self.port = int(port)
        self.display = display
        self.startup_timeout = float(startup_timeout)
        self.settle = float(settle)
        self.build = read_application_ini(self.application)
        if self.build and self.build.get("Version") != VERSION:
            raise ValueError(
                f"{self.application} is not a build of the pinned revision: "
                f"application.ini says Version={self.build.get('Version')!r} against the "
                f"declared {VERSION!r}. #6012 force-pushed off its previous head, so a "
                "ref is not a pin and this stamp is the only machine-checkable link "
                "between the declaration and the binary — a declaration that pins a "
                "revision while a different build runs is a lie the artifact cannot "
                "detect, so this is refused rather than warned about."
            )
        self.declaration = declaration(arena, port=self.port)
        self._process: subprocess.Popen | None = None

    # ---- adapter-declared harness setup, deliberately not an interface verb ----

    @property
    def started_marker(self) -> Path:
        """The file whose appearance says the target started.

        The host's database and the target's database are the same file here,
        which is the ambiguity the plugin adapters have to resolve and this one
        does not.
        """
        return self.data / "zotero.sqlite"

    def harness_prefs(self) -> tuple[tuple[str, str], ...]:
        """Every preference the harness writes, including the one that varies.

        The port is here rather than in the module constant because several
        lanes share one machine, and a declared value that is not the value
        written is worse than no declaration.
        """
        return (("extensions.zotero.httpServer.port", str(self.port)), *HARNESS_PREFS)

    def _write_profile(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.data.mkdir(parents=True, exist_ok=True)
        self.profile.mkdir(parents=True, exist_ok=True)
        lines = [f'user_pref("{name}", {value});' for name, value in self.harness_prefs()]
        (self.profile / "prefs.js").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def environment(self) -> dict[str, str]:
        """HOME and DISPLAY, and nothing that could reconfigure the target.

        HOME is the sandbox. DISPLAY is not optional: there is no headless mode,
        so an adapter that dropped it would report a startup failure as a target
        defect.
        """
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["DISPLAY"] = self.display
        env.pop("XAUTHORITY", None)
        return env

    @contextmanager
    def running(self):
        """Start the target, wait for it, yield, stop it and everything it started."""
        if not self.application.is_file():
            raise RuntimeError(
                f"there is no build at {self.application}. Construction does not refuse "
                "a missing one, deliberately — the declaration must read on a machine "
                "where nothing is built — so the refusal lands here, where a run would "
                "otherwise report a missing binary as a target defect. The build recipe "
                "is in this module's docstring."
            )
        self._write_profile()
        argv = [str(self.application), "-profile", str(self.profile),
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
        """Stop the target and every descendant, by process group.

        The launcher is a shell script that execs the real binary, and the
        application starts the office suite's registration helper. Signalling
        the direct child leaves those reparented and alive, holding the
        databases open — and the egress tracer follows descendants and waits for
        them, so a run that has finished its work hangs until the tracer's own
        timeout. Both plugin lanes hit this independently.
        """
        try:
            group = os.getpgid(process.pid)
        except ProcessLookupError:  # pragma: no cover - already gone
            return
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
            if self.started_marker.exists():
                time.sleep(self.settle)
                return
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(
                    f"the target exited with {self._process.returncode} before "
                    f"{self.started_marker.name} appeared; its output is at "
                    f"{self.arena / HOST_LOG}."
                )
            time.sleep(2)
        raise RuntimeError(
            f"{self.started_marker.name} did not appear in {self.startup_timeout:g}s. "
            f"The target's output is at {self.arena / HOST_LOG}."
        )

    def target_preferences(self) -> dict[str, str]:
        """The target's own keys for the feature under test, as the profile has them.

        Read from the file the target writes and an ordinary user edits. Measured
        empty in the default configuration: the toolkit omits a preference still
        sitting at its built-in default, so the absence IS the evidence that the
        effective configuration is the shipped one.
        """
        found: dict[str, str] = {}
        path = self.profile / "prefs.js"
        if not path.is_file():
            return found
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _USER_PREF.match(line.strip())
            if match and match.group(1).startswith(TARGET_PREF_PREFIXES):
                found[match.group(1)] = match.group(2)
        return found

    # ---- the seven verbs -------------------------------------------------

    def install(self) -> dict:
        """Report the build under test and what it materialised.

        There is no install surface to call. This target arrives as a platform
        build the operator unpacks — here one built from source, because no
        release carries the revision — and it materialises its state on its
        first run against a fresh profile and data directory, which `running()`
        has done by the time this is reached. Building is a network operation
        and is out of an adapter's scope, the same line ZotSeek draws around
        acquiring its artifact; the pin check in the constructor is what makes
        the build that did arrive auditable.
        """
        return {
            "verb": "install",
            "channel": (
                "the platform-native build at the pinned commit, launched against a "
                "fresh profile and data directory. No release carries this revision, so "
                "the build is from source by the tree's own packaging scripts "
                "(app/scripts/fetch_xulrunner then app/scripts/dir_build); the recipe "
                "and its four dead ends are in this adapter's module docstring"
            ),
            "commit": COMMIT,
            "application": str(self.application),
            "application_ini": {k: v for k, v in self.build.items() if k != "_path"},
            "pin_checked": bool(self.build),
            "pin_expected_version": VERSION,
            "materialized": {
                str(root): (
                    root.stat().st_size if root.is_file()
                    else sum(1 for _ in root.rglob("*") if _.is_file()) if root.is_dir()
                    else None
                )
                for root in self.declaration.derived_state_roots
            },
            "target_preference_keys": sorted(self.target_preferences()),
        }

    def uninstall(self) -> dict:
        """Absent: this target is the application, and its state is the user's library."""
        raise UnsupportedVerb(self.declaration.name, "uninstall")

    def configure(self) -> dict:
        """Report the configuration in effect. Nothing of the target's is set.

        The target's configuration channel is its own preference system, reached
        through the preferences pane or the configuration editor. The default
        configuration is what an ordinary user gets, so the harness sets none of
        the target's preferences and this verb reports rather than changes — the
        shape the other declaration-first adapters use, for the same reason.

        `target_preferences_observed` is measured EMPTY here, and that is the
        finding rather than a gap: the toolkit writes no preference still at its
        built-in default, so an empty read is what says the shipped defaults are
        the effective ones. `declared_defaults` carries those, cited.
        """
        observed = self.target_preferences()
        return {
            "verb": "configure",
            "applied_at": "process start",
            "channel": "the target's own preference store, via the profile",
            "harness_preferences": dict(self.harness_prefs()),
            "target_preferences_set_by_the_harness": {},
            "target_preferences_observed": observed,
            "observed_count": len(observed),
            "declared_defaults": dict(DECLARED_EMBEDDING_PREFS),
            "declared_defaults_source": (
                "build/defaults/preferences/zotero.js:120-125 in the built tree at the "
                "pinned commit"
            ),
            "why_observed_is_empty": (
                "the toolkit omits from the profile any preference still sitting at its "
                "built-in default, so an empty read is evidence that the effective "
                "configuration is the shipped one — not evidence that the read failed. "
                "The one key the profile does carry is the harness's own port."
            ),
        }

    def query(self, q: str, mode: str, limit: int) -> dict:
        """Absent: the query surface is the application's own window."""
        raise UnsupportedVerb(self.declaration.name, "query")

    def status(self) -> dict:
        """Absent: the status object is complete, in process, and has no transport."""
        raise UnsupportedVerb(self.declaration.name, "status")

    def pause(self) -> dict:
        """Absent: a real durable control, reachable only from the preferences pane."""
        raise UnsupportedVerb(self.declaration.name, "pause")

    def resume(self) -> dict:
        """Absent for pause's reason, and a no-op besides while the feature is off."""
        raise UnsupportedVerb(self.declaration.name, "resume")


#: The targets this module builds. The registry in `__init__.py` walks the
#: package and reads this rather than holding a written-down list, so declaring
#: it here is what makes the adapter selectable — and what lets the
#: target-neutrality guard learn this target's name without being told it.
NAMES = ("zotero-core-6012",)


def build(name: str, arena: Path, *, application: str = "", port: str | int = 23519,
          display: str = ":1", startup_timeout: str | float = 300.0,
          **_opts) -> ZoteroCore6012:
    """Construct the adapter from the driver's opaque `--adapter-option` pairs.

    The build is not defaulted, and the refusal is the point. This target has no
    release carrying the revision under test, so there is no conventional path
    to guess at; a guessed launcher is how a run measures a Zotero nobody
    pinned, and on this target the process under trace IS the target, so a wrong
    binary silently changes the whole measurement. The constructor's pin check
    is the second line of defence; this is the first.
    """
    if not application:
        raise SystemExit(
            "this adapter needs the launcher of a build of the pinned revision "
            "(--adapter-option application=<path>). It is not defaulted: no release "
            "carries this revision, the process R10 traces IS this target, and a "
            "guessed binary silently changes what was measured. The build recipe is in "
            "bench/acceptance/adapters/zotero_core_6012.py's module docstring."
        )
    return ZoteroCore6012(
        Path(arena),
        application=Path(application),
        port=int(port),
        display=display or os.environ.get("DISPLAY", ":0"),
        startup_timeout=float(startup_timeout),
    )
