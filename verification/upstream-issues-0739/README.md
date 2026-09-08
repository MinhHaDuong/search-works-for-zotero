# Upstream issue drafts for `oscardvs/zoteus` — ticket 0739

Five drafts, not filed. Written from the seat reports in `../qa-v1.16.0/` and the
triage in `../REVIEW-v1.16.0-QA.md`, with every `file:line` re-verified against a
read-only clone at `910310b3979aaad9d314087ffd043eaf59eb023a` (the v1.16.0 release
commit). `main` at `4467663` is one README-only commit later, so the line numbers hold.

Nothing was executed: no `node_modules`, no test run, no live Zotero. Each draft says
so in its own first paragraph and names what it could not check, because that is the
part a maintainer who reproduces what he is told needs in order to know where to spend
his time.

| # | File | Title | Severity | What it asks for |
|---|---|---|---|---|
| 1 | `1-fulltext-catchup.md` | A transient attachment read during `action:"update"` drops an item's body passages, then advances the stamp (#63's full-text sibling) | high | Apply the #63 treatment to the full-text lane: distinguish "could not read" from "no text", keep the body rows, withhold the stamp. The signal is already wired in and unread. |
| 2 | `2-two-process-stamp.md` | Quitting Claude Desktop after a headless build zeroes the index stamp, and the next `action:"update"` rebuilds from scratch | high | Make the meta write ownership-aware, so an idle second handle commits nothing on exit. |
| 3 | `3-pdfjs-node-floor.md` | `pdfjs-dist` is frozen on the last release that runs on Node 20.19, so the PDF parser is on a branch that can no longer be patched | medium | Decide the Node floor: raise `engines.node` to `>=22.13` and take pdfjs 6.x, or pin 5.6.205 exactly and record the freeze. |
| 4 | `4-citeproc-attribution.md` | The `.mcpb` bundles and the container redistribute `citeproc`, which is CPAL/AGPL and asks for an attribution notice Zoteus does not ship | medium | Add `THIRD_PARTY_NOTICES.md` with the three Exhibit B lines, ship it inside the artefacts, print the attribution phrase once per session. |
| 5 | `5-untrusted-library-content.md` | A Zotero library is not trusted input: library text reaches the calling model unframed, and most destructive writes have no confirmation gate | design | Write the threat model down, mark provenance on library-derived text, extend the `confirm` policy past permanent delete. Offers to draft the document. |

## Re-verification against `910310b`

All five hold. No finding was retracted.

Corrections made to the seat reports' line references, all cosmetic in the sense that the
mechanism was in every case where the seat said it was:

| Seat cited | Correct at `910310b` | Note |
|---|---|---|
| `sqlite-index.ts:1325-1335` (deleteItem's DELETE) | `deleteItem` is `:1312-1335`; `deletePassages.run` is `:1331` | prepared statement is at `:1009`, not `:1041` |
| `fulltext-source.ts:167-195` | `:167-194` | |
| `index-manager.ts:1656-1686` (own-words read-back) | `:1669-1672` (the `kept` binding) and `:1694-1698` (the re-insert) | one contiguous range in the seat, two blocks in the source |
| `index-manager.ts:2102-2131` (`fulltextForPage`) | function is `:2102-2125`; the catch that swallows the failure is `:2116-2121` | `:2127-2131` is the next function's doc comment |
| `sqlite-index.ts:2067-2072` (`save`) | `:2068-2073` | |
| `sqlite-index.ts:2074-2090` (`close`) | `:2075-2092` | |
| `index-manager.ts:2707-2726` (JSON `save`) | `:2707-2725` | JSON `close()` at `:2728-2732` does not re-save; the overwrite comes from `save()` |
| `index-manager.ts:1534-1541` (`updateBlocker`'s no-stamp branch) | `updateBlocker` is `:1522-1550`; the no-stamp branch is `:1528-1536` | |
| `docs/semantic-search.md:459-471` | `:457-475` | |
| `sqlite-index.ts:236-241` (busy-timeout comment) | `:233-241` | |
| `manage-tags.ts:24` (`destructiveHint`) | `:25` | |
| `trash-items.ts:28-52` (annotations) | annotations at `:27`; handler `:28-` | |
| `pdf-pages.ts:32-37` | `:32-38` (`getTextContent` at `:37`, the push at `:38`) | |
| redteam's `get_fulltext.ts` | `src/tools/get-fulltext.ts` (`zotero_get_fulltext`); `src/tools/fulltext.ts` is the separate `zotero_fulltext` tool | two distinct tools, easy to conflate |

One factual correction, not a line number. The dependencies seat wrote that grepping for
`citationstyles.org` returns nothing. It does not: `README.md:49` and `:115` both link it.
Draft 4 says so, and narrows the claim to what is actually absent — a copyright notice, a
statement of which licence option is taken, and any notices file inside the redistributed
artefacts.

Facts re-derived independently rather than relayed:

- `pdfjs-dist` engine floors per version, from `npm view` on 2026-09-08. 5.6.205 is
  `>=20.19.0 || >=22.13.0 || >=24`; 5.7.284, 6.0.227, 6.1.200, 6.2.108 and 6.3.289 are all
  `>=22.13.0 || >=24`. The seat's reading holds exactly.
- GHSA-hq66-cqwq-w95j, fetched from the advisory page: CVE-2026-16633, affected
  `>=5.6.83 <6.2.108`, patched 6.2.108, and the description does turn on the viewer's
  `enableScripting` default. Draft 3 states the non-reachability plainly for that reason.
- citeproc's `LICENSE` (from the published 2.4.63 tarball) and Exhibit B (from the
  citeproc-js repository), quoted rather than paraphrased.
- The `confirm` gate really is unique to `delete-items.ts`: a grep over `src/tools/*.ts`
  finds it nowhere else outside a tool description.

One thing the safety seat asserted that it could not have observed, per the coordinator's
brief: it wrote positive-control vitest sketches with `FAILS today` annotations. No test was
run in that session. The drafts carry those as acceptance criteria to be written, never as
results.

## Before filing

- Draft 5 is public by choice. `SECURITY.md` asks that vulnerabilities go through private
  reporting, and the draft says in its opening paragraph that it will move to a private
  advisory on request. Worth a moment's thought before posting, since it is the one of the
  five that touches the hosted instance's posture.
- Drafts 1 and 2 both name behaviour that one live check would settle. Neither claims to
  have run it.
- Consider spacing the filings. Five at once from the same account, on the day after five
  others closed, is a lot of queue for one maintainer.
