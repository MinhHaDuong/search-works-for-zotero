# SDT Pack Sitter

A Zotero 10 add-on that prepares structured-text packs in the background, ahead
of demand, and shows you how much of your library is covered.

**Experimental.** [Download and release
notes](https://github.com/MinhHaDuong/search-works-for-zotero/releases/latest) —
read the known bugs before installing.

## What is here

| File | |
|---|---|
| [`RELEASE-NOTES.md`](RELEASE-NOTES.md) | What it does, what it does not, and what is broken. Start here. |
| [`DESIGN-NOTES.md`](DESIGN-NOTES.md) | Why it is built this way, for a Zotero developer rather than a user. |
| `bootstrap.js` | The add-on: lifecycle, the window, the toolbar control, the resource guards. |
| `scheduler.js` | The sweep, the cache and the duration estimates. |
| `manifest.json`, `update.json` | Declared version and supported Zotero range. The two must always agree. |

Built with `python3 bench/build_sdt_sitter.py` from the repository root.

Licence: AGPL-3.0, the same as Zotero's, so that anything worth taking can go
upstream without a licence conversation. That is the point rather than a
formality — this is a prototype, and if the ideas are any good they belong in
Zotero rather than in an add-on everybody has to find and install.
