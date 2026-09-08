# A Zotero library is not trusted input: library text reaches the calling model unframed, and most destructive writes have no confirmation gate

Read on `main` at `910310b3979aaad9d314087ffd043eaf59eb023a` (the v1.16.0 release commit). Source reading only. **No exploit was built and none is described here in runnable form.** This is a threat-model proposal rather than a bug report, and it is deliberately public for that reason; `SECURITY.md` asks for private reporting of vulnerabilities, and I am happy to move it to a private advisory if you would rather, but there is nothing here that is not already general knowledge about MCP servers over user corpora.

### The trust boundary that is not drawn

`registry.ts` names the boundaries the code does draw, and draws them well. A stdio caller is the machine owner, so filesystem paths are unconfined; an HTTP caller is not, so `remoteCaller` confines caller paths to `dataDir`; per-tenant contexts carry their own key and their own index file. The conventional adversarial surface is closed with them: parameterised SQL throughout, FTS5 terms quoted from `\p{L}\p{N}` tokens only, a capped EPUB inflate that rejects zip64, a byte cap and `isEvalSupported:false` on the PDF path, PKCE and a timing-safe passcode on the OAuth path.

The boundary that is missing is between text the model has just read and instructions the model follows. A Zotero library is not a trusted corpus. Its contents arrive from PDFs downloaded off the open web, from group libraries synced from collaborators, and from items accepted from other people. Whoever wrote those controls item titles, abstracts, creator names, tags, note HTML, annotation highlight text and comments, and extracted PDF and EPUB body text. They never call a tool. They plant text the model reads later.

That text reaches the model verbatim and unmarked. Every tool returns through `ok(structured, summary)`, which puts the summary in one text block and `JSON.stringify(structured, null, 2)` in a second ([registry.ts:131-139](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/registry/registry.ts#L131-L139); the mirror is deliberate, and the comment above it explains why). `zotero_search_items` projects `title`, `creatorSummary` and `date`, plus `tags`, `DOI` and `url` in detailed mode ([search-items.ts:14-31](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/search-items.ts#L14-L31)). `zotero_get_item` returns the whole item record ([get-item.ts:35-40](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/get-item.ts#L35-L40)). `zotero_get_fulltext` returns extracted body text and passages. `zotero_semantic_search` returns snippets that may come from a note or an annotation. Notes are HTML run through `htmlToText` ([src/lib/html-text.ts](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/lib/html-text.ts)), which is a text extractor and not a sanitiser: it strips markup, and instruction-shaped prose passes through it unchanged, as it should. Nowhere on the return path is library-origin text delimited, escaped, or tagged with provenance.

### The other half: which writes ask before acting

`confirm` appears in exactly one tool in `src/tools/`. `zotero_delete_items` needs both `ZOTEUS_ALLOW_DELETE=true` and `confirm: true` on every call ([delete-items.ts:25-46](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/delete-items.ts#L25-L46)), which is right, and it is correctly the strongest lock in the tree. Everything else runs on the model's decision alone:

| Tool | `destructiveHint` | Gate |
|---|---|---|
| `zotero_delete_items` | true | `ZOTEUS_ALLOW_DELETE` + `confirm` |
| `zotero_trash_items` | false ([:27](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/trash-items.ts#L27)) | none |
| `zotero_update_item` | true ([:42](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/update-item.ts#L42)) | none |
| `zotero_create_items` | true ([:28](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/create-items.ts#L28)) | none |
| `zotero_manage_tags` | true ([:25](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/manage-tags.ts#L25)) | none |
| `zotero_manage_collections` | true ([:29](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/manage-collections.ts#L29)) | none |
| `zotero_saved_searches` | true ([:25](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/saved-searches.ts#L25)) | none |

`zotero_manage_collections action:"delete"` is worth singling out, because it is not the trash: it is the same server-side `DELETE ...?collectionKey=` primitive as the item purge ([manage-collections.ts:79-84](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/tools/manage-collections.ts#L79-L84)), and it is reachable with no `allowDelete` and no `confirm`. Items survive, but a hand-built hierarchy does not, and there is no undo through Zoteus.

The shortest path from planted text to a destructive call is therefore three steps and no gate: a poisoned abstract or note enters the library; a routine question routes through `zotero_search_items` or `zotero_semantic_search` and the text lands in the model's context indistinguishable from a legitimate result; the model calls `zotero_trash_items` with keys from the same result. Trash is reversible, which is why this is a design issue and not an emergency. Mass retagging, wholesale metadata rewrites through `update_item`, and a deleted collection tree are not.

### What I am not claiming

Whether a given client model obeys instruction-shaped text in a tool result is a property of that model, not of this code, and it varies. I built no exploit and ran nothing. What I can say from the source is narrower and, I think, still worth acting on: Zoteus does nothing to make the boundary legible to the model, and the tools that would act on a bad decision mostly do not ask first. Those are two affordances you control, independent of any model's behaviour.

`ZOTEUS_READ_ONLY` already closes the second half for shared deployments, by filtering the tool list to `readOnlyHint === true` plus `zotero_index` ([server.ts:71-72](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/src/server.ts#L71-L72)), and the Dockerfile already recommends it for public connectors ([Dockerfile:30](https://github.com/oscardvs/zoteus/blob/910310b3979aaad9d314087ffd043eaf59eb023a/Dockerfile#L30)). That is the right lever; it is just not documented as the answer to this threat, because the threat is not written down anywhere. Grepping the repository for "prompt injection" or "untrusted" returns nothing.

### Proposal

Three pieces, in the order I would do them.

**Write the threat model down.** A section in `SECURITY.md`, or a `docs/threat-model.md`, stating plainly that library content is untrusted input to the model, naming who can put text in a library (web PDFs, group libraries, collaborators' items), and saying that a write-enabled deployment trusts the calling model with the library. That costs nothing, changes no code, and is the piece a user needs in order to decide how to deploy.

**Mark provenance on library-derived text.** Wrap library-origin strings in the tool output in a machine-readable envelope, so a client or a system prompt can be told to treat them as data: a `source: "library-content"` field alongside the payload, or a sentinel delimiter around the text blocks that carry item titles, abstracts, notes, annotations and body text. This does not stop injection, and should not be sold as if it did. It makes the boundary expressible, which is a precondition for anything downstream doing something about it.

**Extend the gate policy beyond permanent delete.** A `confirm` argument, or a bulk-size threshold above which `confirm` becomes mandatory, on `trash_items`, `manage_tags`, `manage_collections action:"delete"` and `update_item`. The threshold form keeps single-item edits fluent, which is most of the real traffic, and puts a human in the loop exactly where an injected instruction would want scale.

I am happy to write the threat-model document as a PR if that would help; say the word and I will draft it against this tree rather than in the abstract.

### Acceptance criteria

- `SECURITY.md` or a linked document states the trust boundary and names the deployment postures (`ZOTEUS_READ_ONLY`, write-enabled personal stdio, write-enabled shared HTTP).
- Library-derived text in tool output carries a provenance marker, and a test asserts it survives the `ok()` text mirror.
- A destructive tool refuses a bulk operation without `confirm`, with a test for the refusal, mirroring `tests/tools/writes.test.ts:143-156` for `delete_items`.

Related: #54 is the same instinct about telling the user what the server does on their behalf.
