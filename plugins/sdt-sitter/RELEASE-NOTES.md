# SDT pack sitter initial release notes

Minh.Ha-Duong@cnrs.fr, 2026-09-14

This developer plugin eagerly runs Zotero 10's structured text extraction on your local and group library's attached files.

**Requires Zotero 10.** Earlier versions do not have structured text extraction at all.

## Why ?

a. If you never refresh the index, you get stuck with old versions for years.
b. Lists your unindexed items, so that you know which missing/broken PDFs to fetch.
c. A prototype. Indexing should be automatic, complete, robust, up to date, a safe background process.
d. Fulltext search tools can use the extracted structured text for better replies. And will, someday.
e. The whole indexing may take hours. So if you don't index in advance, the reply to your first request will arrive tomorrow.

Points a, b and c are current limits of Zotero. Points d and e are the frontier.

## What it does, after you click "Start indexing"

1. Delay on startup to let Zotero settle
2. Status check: Scans all attachments in your local and group libraries for existing SDT packs
3. Indexing: For each attachment, ask Zotero to extract the .SDT
4. Listen to changes and update accordingly
5. Every hour, rescan all attachments in case something escaped us.

## What it shows

- The plugin interface is an "Index" button near the search box. It pulses when the plugin is scanning, displays % indexed, and has a spinner when actively indexing
- The Index button is clickable to open an information window with progress bars and details on what is indexed, what is not, and why.

## What it does not

- The plugin does not interfere with Zotero's own "Index on PDF open" behavior.
- The plugin does not reimplement any extraction mechanism, its job is only to babysit a long-running job.
- The plugin does not leave anything behind on uninstall. Exceptions: state is preserved on disable and upgrade in place. And if debug mode is on, a `sdt-sitter-last-shutdown.json` is left in the Zotero data directory for postmortem.
- Sync between machines. The extracted structured text is a local cache file, it does not travel.
- Does not expose an external access point to the SDT. Yet?
- Does not manage chunking and embedding. See PR #6012 for that.
- Does not phone home or send your data anywhere. Exception: Zotero can automatically check online for plugin updates everyday. Disallowable in the Extensions "gear" menu.

## Known bugs and limitations

- When you uninstall a plugin, Zotero hides it from the list and schedules actual removal for later. So if you immediately reinstall, the new copy will get erased. Workaround: always restart Zotero after uninstalling a plugin. Bug report filed upstream.
- The mechanism to throttle down indexing in case of memory / disk / CPU pressure works only on Linux.
- I did my best effort to ensure keyboard navigability and text-to-speech readability, but could not find a way for a plugin to insert its button into Zotero's Tab navigation order. Workaround: none found, you have to click it. Bug report filed upstream.
- The SDT format can evolve with automatic Zotero minor updates, triggering a full reindex. Wait, that's a feature not a bug !
- This does not replace the "Rebuild Index" button that disappeared. Because that button addressed the "full text" index, not the "structured text" index. See next point why.

## Zotero text extraction remarks

- The old "Rebuild Index" and "Clear Index" buttons were removed in Zotero 10
  ([02fb0e92e](https://github.com/zotero/zotero/commit/02fb0e92e)). Rebuild Index marked all content unsynced and re-uploaded it, triggering a server reindex and a re-download on every other device — so it was never a local operation. SDT caches are genuinely local and never travel, which is why a plugin can index all without that blast radius.
- Zotero phones home daily to fetch this repository's update manifest from raw.githubusercontent.com — one fixed URL, nothing about your library, recorded
  in [SPEC.md](../../SPEC.md#surfaces). Sorry, not my fault. The plugin makes no
  request of its own.
- Did not test the quality and accuracy of Zotero's extractor against Grobid, commercial API or others. Probably better than PyMuPDF and pdfplumber, but not as strong as docling, Nougat, Marker. Zotero has no GPU access.
- If you already have a PDF and a carefully extracted TEI on the side, note these are not the same object: TEI gives you the bibliographic structure, SDT gives you text with reading order and page positions. You cannot substitute one for the other, and Zotero will not accept yours.
- No OCR. This plugin, and Zotero, only read text that is already in the file. A scanned PDF that has never been through OCR has no text layer, so there is nothing to extract — it will be reported as having no text rather than as failing. Run OCR on it first (ocrmypdf, Acrobat, or whatever you use) and Zotero will index it fine afterwards.

---

This plugin is a deliverable of my search-works-for-zotero project.
https://github.com/MinhHaDuong/search-works-for-zotero
License: AGPL-3.0 
