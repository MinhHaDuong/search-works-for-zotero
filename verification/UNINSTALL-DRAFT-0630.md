# Uninstall draft — ticket 0630, the R15 removal procedure

Drafted 2026-09-03 from `src/lib/paths.ts`, `src/features/search/embeddings.ts`,
`src/tools/whoami.ts`, `src/lib/update-check.ts` and `docs/configuration.md`.
Placement and format reconsidered 2026-09-04 — see below — from a single
root-level `UNINSTALL.md` to a two-piece hand-off: a short section in
`README.md` and the full procedure in `docs/uninstall.md`. The end-to-end run
this reconsideration accompanies is
`bench/results/0630-gap-b/README.md`.

**Read at v1.12.0 (`b05ed69`), re-verified at the reviewed baseline.** The
`fork/` checkout on this machine sits at `b05ed69`, one release behind the
`b0e0bc8` (v1.13.0) that `UPSTREAM` names — a stale-checkout finding in its own
right, reported to the wave. Review round 1 re-read every claim below against
`b0e0bc8` itself: the substance held, and the line-number citations recorded in
this ticket's log were corrected there. Nothing in the content depends on a
line number.

**Not sent.** This is a staged artifact in the same form as
`verification/ISSUE-DRAFT-0530.md` and
`verification/UPSTREAM-PR-POOLING-0612.md`: everything from the first
`## Content —` heading down is what would go upstream, split across the two
destinations each heading names; this preamble would not. The hand-off is
`GOVERNANCE.md`'s lane, not this ticket's — contained-PR form, a docs change
of the shape that merged verbatim twice (#27, #28), against a volume cap this
ticket does not spend.

**Why a document and not a verb.** `R15-uninstall-removes-declared-state` is
`not-offered` for this target. The 2026-09-03 ruling (tracker 0613's log)
retired the earlier reading that zoteus must grow a callable uninstall verb:
an external MCP server has no host uninstall lifecycle to hook, so the
ratified surface for this architecture class is a **published removal
procedure** the harness executes verbatim and then sweeps for residue.

**What the procedure has to match.** `bench/acceptance/adapters/zoteus.py`'s
`Declaration` declares exactly one derived-state root, and `_env()` hands that
root to the target as `ZOTEUS_DATA_DIR`. The document below therefore names
that variable and its OS defaults — never the harness's arena path, which is a
test fixture no user ever sees. `tests/test_uninstall_doc.py` asserts that
correspondence through the shared symbol.

**One precondition still open.** The arena does not yet redirect `TMPDIR` or
the XDG variables. Measured for this ticket: `zoteus.py`'s `_env()` sets only
`ZOTEUS_*` variables and merges them onto the operator's full `os.environ`
(line 372) — it redirects nothing else, not even `HOME`, which four sibling
adapters do redirect. `TMPDIR` is redirected nowhere under `bench/acceptance/`;
`XDG_CACHE_HOME` is touched only in `zotero_mcp.py`. The other precondition,
a dedicated account owning the arena, is closed (ticket 0625). The document's
correctness does not depend on either, but R15 cannot be graded green for
zoteus until the redirection gap closes.

**Location and format, reconsidered 2026-09-04.** The original plan (0613's
log, 2026-09-03T13:43Z) named a single new root file, `UNINSTALL.md`, on the
strength of `CHANGELOG.md`/`CONTRIBUTING.md`/`PRIVACY.md` sitting at the
fork's root. Reread against `fork/README.md` itself, that precedent argues
less than it first looks like it does, and a stronger one was sitting beside
it unused.

*Format.* Checked for an agent-facing consumption format before assuming
prose was the only option: `fork/` ships no `llms.txt` and no agent-facing
doc index of any kind (`find`, empty). The one machine-readable manifest that
exists, `mcpb/manifest.json`, is Claude Desktop's own install-time
configuration schema — third party, not ours to extend, and its only present
consumer is Claude Desktop's own extension manager, which already knows how
to remove the `.mcpb` bundle it installed, through its own UI, independent of
anything this repository publishes. What that manager does *not* know about
is exactly `ZOTEUS_DATA_DIR` — state living outside the bundle, which is the
whole reason a removal procedure needs to exist at all. No consumer for a
machine-readable manifest was found, so there is nothing a manifest format
would win here that prose does not already provide; every doc in `fork/` is
`.md`, and this one stays `.md` by consistency and by fit, not by default.

*Location.* `fork/README.md` already carries a `## Install` section — client
commands, a table, a cloud-key note — and there is no `INSTALL.md` at root:
this project's own precedent for an *operational lifecycle step* is a README
section, not a spun-off file. `CHANGELOG.md`/`CONTRIBUTING.md`/`PRIVACY.md`
are a different class: `CONTRIBUTING.md` is a filename GitHub itself
recognises and surfaces (a PR/issue banner), and the other two are
freestanding history/policy documents with no README counterpart to pair
against. Uninstall has one: it is Install's closing half, and README already
has a working pattern for "the short answer here, the full one linked" — the
"Vector ranking is opt-in" and "Embedding through an API" callouts in `##
How it works`, each a paragraph pointing at `docs/semantic-search.md`. A
fifth unlinked root file is one click further from a person skimming GitHub
than a paragraph under the section they are already reading, and no closer
for an agent that only reads what a tool call surfaces — a `docs/` path
linked from README is exactly as reachable as a root file, and more likely to
actually be linked from the place a reader looks. So: a short `## Uninstall`
section in `README.md`, immediately after `## Install`, plus the full
procedure at `docs/uninstall.md` — not a new root file. The content below is
unchanged in substance; only its two destinations and the split between them
are new.

---

## Content — addition to `README.md`

*(Insert as a new `## Uninstall` section immediately after the existing `##
Install` section, in the same short-answer-plus-link shape as the "Vector
ranking is opt-in" callout under `## How it works`. Also add one entry,
`[Uninstall](./docs/uninstall.md)`, to the `## Documentation` link list.)*

## Uninstall

Zoteus writes everything it derives — the search index, the on-device model
weights, the update-check cache — into one directory: `ZOTEUS_DATA_DIR` if
you set it, otherwise your OS's default application-data path. Stop the
server, remove it from your MCP client's configuration, then delete that
directory; your Zotero library lives elsewhere and nothing here touches it.
Full steps, platform paths, and the pre-v1.10.0 case (model weights that used
to land outside this directory): [`docs/uninstall.md`](./docs/uninstall.md).

## Content — `docs/uninstall.md`

# Uninstalling Zoteus

**Zoteus writes everything it derives into one directory.** Removing that
directory removes the search index, the on-device model weights, and the
update-check cache — every file the server has ever written for itself. Your
Zotero library is somewhere else entirely, and nothing below goes near it.

## Where that directory is

`ZOTEUS_DATA_DIR`, if you set it. Otherwise the OS default:

| Platform | Default |
|---|---|
| macOS | `~/Library/Application Support/zoteus` |
| Windows | `%APPDATA%\zoteus` |
| Linux, BSD, everything else | `${XDG_DATA_HOME:-~/.local/share}/zoteus` |

The table above is the whole rule: no tool reports the resolved path, so if
you set `ZOTEUS_DATA_DIR` yourself, read it back from wherever you set it.

## The steps

1. **Stop the server.** Quit whatever holds the stdio connection — Claude
   Desktop, your editor, or the `node` process, if you started it yourself.
   A running server holds the index's
   SQLite file open and will rewrite its `-wal` sidecar underneath you.

2. **Remove the registration.** Delete Zoteus's entry from your MCP client's
   configuration, or uninstall the desktop extension bundle through the
   client that installed it. Nothing else in this list depends on the order,
   but doing this second means the client will not relaunch the server while
   you are deleting its files.

3. **Delete the data directory.** The one from the table above — and only
   that one. It is not your Zotero library, which lives elsewhere and is not
   part of this procedure; check the path you are about to remove against the
   table before you run anything.

   ```sh
   # Linux/BSD, default location
   rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/zoteus"
   # macOS, default location
   rm -rf ~/Library/Application\ Support/zoteus
   # Windows, PowerShell, default location
   Remove-Item -Recurse -Force "$env:APPDATA\zoteus"
   # any platform, if you set the variable yourself
   rm -rf "$ZOTEUS_DATA_DIR"
   ```

   That is the whole removal. The index (`search-index.sqlite` and its
   `-wal`/`-shm` sidecars, or the older `search-index.json`), the downloaded
   model weights under `<ZOTEUS_DATA_DIR>/models`, and `update-check.json`
   all live inside it.

4. **Remove the embedding runtime, if you installed one by hand.** Semantic
   search needs `@huggingface/transformers`, which Zoteus does not vendor. If
   you installed it yourself and pointed `ZOTEUS_TRANSFORMERS_PATH` at it,
   that directory is yours and outlives every step above — delete it if
   nothing else uses it. An install that never enabled semantic search has
   nothing to do here.

## What is deliberately left alone

**Your Zotero library.** Zoteus reads the desktop app's data directory
(`~/Zotero` by default, `ZOTERO_DATA_DIR` if you moved it) to open attachment
files, and writes no file into it. That is a claim about the directory, not
about your library: unless you ran with `ZOTEUS_READ_ONLY=true`, Zoteus could
add and edit items through the API like any other client, and removing it
leaves those items where they are. Do not delete the directory as part of
removing Zoteus.

**Your API keys.** They live wherever you put them — a shell profile, your
MCP client's configuration, a secret manager. Zoteus keeps no copy of its own,
so nothing in this list reaches them. Revoke them yourself if you want them
gone.

## If you installed before v1.10.0

**Earlier versions left the model weights outside the data directory**, and
deleting the data directory alone was an incomplete uninstall for those
installs. `@huggingface/transformers` caches downloaded weights inside its own
package directory by default; Zoteus did not override that until the fix that
pins the cache to `<ZOTEUS_DATA_DIR>/models` before the pipeline is built.
Under `ZOTEUS_TRANSFORMERS_PATH` pointing at a global `node_modules`, those
weights outlived even uninstalling the desktop extension — and they are the
largest artifact of the lot, tens of megabytes for the default model and
gigabytes for a larger one.

If your install predates that fix and you never removed the package, look for
a `.cache` or `models` directory inside the `@huggingface/transformers`
install you pointed at and delete it. A fresh install writes nothing there.

## Checking

Nothing should remain:

```sh
ls "${ZOTEUS_DATA_DIR:-$HOME/.local/share/zoteus}"    # no such file or directory
```

Reinstalling later rebuilds the index from your library. Nothing removed here
is unrecoverable, and nothing removed here was yours.
