# UNINSTALL.md draft — ticket 0630, the R15 removal procedure

Drafted 2026-09-03 against the reviewed baseline `b0e0bc8` (`UPSTREAM`,
v1.13.0), reading `src/lib/paths.ts`, `src/features/search/embeddings.ts`,
`src/lib/update-check.ts` and `docs/configuration.md` in the `fork/` checkout.

**Not sent.** This is a staged artifact in the same form as
`verification/ISSUE-DRAFT-0530.md` and
`verification/UPSTREAM-PR-POOLING-0612.md`: everything from `## Content` down
is what would go upstream, this preamble would not. The hand-off is
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

---

## Content

*(This is the file, `UNINSTALL.md` at the repository root — beside
`CHANGELOG.md`, `CONTRIBUTING.md` and `PRIVACY.md`, not under `docs/`.)*

# Uninstalling Zoteus

**Zoteus writes everything it derives into one directory.** Removing that
directory removes the search index, the on-device model weights, and the
update-check cache — every file the server has ever written for itself. Your
Zotero library is not in it and is never touched.

## Where that directory is

`ZOTEUS_DATA_DIR`, if you set it. Otherwise the OS default:

| Platform | Default |
|---|---|
| macOS | `~/Library/Application Support/zoteus` |
| Windows | `%APPDATA%\zoteus` |
| Linux, BSD, everything else | `${XDG_DATA_HOME:-~/.local/share}/zoteus` |

`zotero_whoami` reports the resolved path if you would rather read it than
derive it.

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

3. **Delete the data directory.** The one from the table above:

   ```sh
   rm -rf "${ZOTEUS_DATA_DIR:-$HOME/.local/share/zoteus}"    # Linux/BSD default
   rm -rf ~/Library/Application\ Support/zoteus              # macOS default
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
files, and never writes to it. Do not delete it as part of removing Zoteus.

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
