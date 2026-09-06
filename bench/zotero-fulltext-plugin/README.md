# Full-text control plugin

A measurement aid for the segmenter experiment (X5, ticket 0025): two endpoints
on Zotero's own local server, so a script on the author's machine can ask
Zotero to re-extract named attachments in full and can see when it has
finished. Nothing stock offers either: the local API reads the cache, and
since Zotero 10 the bulk reindex buttons are gone from the settings pane, so a
partially indexed attachment can only be re-extracted one click at a time.

The plugin is not part of zoteus and files nothing upstream. The ask it stands
in for belongs on Zotero's local API and travels, if at all, as a courtesy
filing.

## Install

```bash
bench/zotero-fulltext-plugin/build.sh          # writes ~/fulltext-control.xpi (or the path given)
```

The package lands outside the repository on purpose: the bench guards read every
file under `bench/` as text, and a zip is not text.

Zotero → Tools → Plugins → gear → Install Plugin From File → the `.xpi`.
Installs live, no restart. Remove it from the same pane. Zotero 10 requires
`update_url` in the manifest; it points at `updates.json` here, which lists no
updates, so the periodic check is a no-op.

## Use

```bash
uv run python bench/zotero_fulltext.py status 65F79PTJ TD45RDD6
uv run python bench/zotero_fulltext.py reindex 65F79PTJ TD45RDD6 --wait             # stock limits
uv run python bench/zotero_fulltext.py reindex 65F79PTJ TD45RDD6 --wait --complete  # limits ignored
```

Or by hand:

```bash
curl -s -X POST -H 'Content-Type: application/json' \
  --data '{"keys":["TD45RDD6"], "complete": false}' http://localhost:23119/search-works/fulltext/reindex
curl -s 'http://localhost:23119/search-works/fulltext/status?keys=TD45RDD6'
```

`reindex` answers 202 at once with what it queued and the mode it queued it in.
Extraction runs in Zotero's own queue. The body's `"complete"` (boolean,
default `false`) chooses the mode: `false` is **stock**, the client's own
`fulltext.pdfMaxPages` and `fulltext.textMaxLength` apply exactly as they would
to Zotero's own extraction; `true` is **uncapped**, both limits ignored
(`Zotero.FullText.indexItems(ids, {complete: true})`, which `fulltext.js`
documents as passing no page bound to `indexPDF`). Until version 0.2.0 the
plugin always passed `complete: true`, so an export recording the stock
preferences was not bounded by them (ticket 0632's real run, 2026-09-06);
the default is now the stock arm and the mode is reported, never assumed.

`status` reports, per key, the library, the indexing state (unindexed,
partial, indexed, queued, unavailable), pages and characters indexed against
totals, and the full-text version; plus the library-wide statistics, `busy`
(true while a reindex this plugin queued is still running), `version` (the
plugin's own), `lastReindexMode` (`stock`, `uncapped`, or `null` before any
reindex since startup), and `prefs` — `pdfMaxPages` and `textMaxLength` read
live from `Zotero.Prefs` on every call, so an export can record the values the
extraction actually ran under instead of typing them.

`import` (version 0.3.0) imports one bibliographic file — RIS, BibTeX, Zotero
RDF — through Zotero's own import translators into the **user library of the
running profile**, never a group, with file attachments linked rather than
copied, so the relative `L1` paths of the Menagerie's RIS package resolve
beside the file. It answers with the translator used and, per imported item,
its type, title and each linked attachment's path and whether the file exists.
A verification aid for ticket 0721's `make menagerie-ris`, meant for a scratch
profile and data directory (`zotero -profile <scratch> -datadir <scratch>`);
it refuses a relative path and a file no translator matches.

```bash
curl -s -X POST -H 'Content-Type: application/json' \
  --data '{"path":"/abs/path/to/menagerie.ris"}' http://localhost:23119/search-works/fulltext/import
```

## What it can reach

Zotero binds the server to the loopback interface, refuses any `Host` header
other than localhost, and refuses browser-shaped requests without the
`Zotero-Allowed-Request` header; all three are Zotero's own server code, and the
plugin adds no permission of its own. Keys are looked up in every library the
profile holds, so group-library attachments work without naming the group.
