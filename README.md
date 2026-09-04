# Search Works for Zotero

*An independent open workshop for advancing semantic retrieval in Zotero.*

Search should work across a whole scholarly library: records, notes,
annotations, articles, books, and very large reference works. It should find
meaning rather than merely matching strings, while remaining inspectable,
resource-bounded, current, and honest about what has and has not been indexed.

This repository is a public statement of that direction and a place to do the
work. It develops requirements, constraints, designs, executable experiments,
acceptance tests, and upstream contributions. It is not the home of a single
product and it does not assume that one implementation should win.

Files directory and instructions: see [`AGENTS.md`](AGENTS.md)

## The theory of change

This workshops aims to define what professional-grade semantic retrieval is, and influence the Zotero ecosystem in that direction.
The definition of success is not in the code we ship, it is the availability of semantic search in Zotero that works "Really Well".
That can be implemented in more than one way. Three work surfaces therefore have equal standing:

1. **Zotero itself.** [zotero/zotero#6012](https://github.com/zotero/zotero/pull/6012)
   and its successors are first-class design and influence points. Their result
   locations, saved-search representation, lifecycle, local-API surface, and
   retrieval semantics may decide which machinery outside Zotero remains
   necessary.
2. **Independent implementations.** [zoteus](https://github.com/oscardvs/zoteus)
   is the current working vehicle and upstream contribution target, not the
   project identity. Other servers, plugins, and future adapters are legitimate
   implementations of the same contract.
3. **The implementation-neutral workshop.** Requirements, measurements,
   fixtures, gates, and decision records live here so that claims can survive a
   change of implementation.

In the near term, I aim to deliver:
- A more or less formal vision for what I regard as professional-grade.
- [The multilingual menagerie](https://www.zotero.org/groups/6659303/semantic_search_challenge_fixture), which is a Zotero collection designed as a fixture to test retrieval engines on. Menagerie means there are interesting beasts in it. It comes with a set of questions those answers can be found in the documents (but sometimes inside a table on page 240).
- An test suite to verify and score implementations wrt the requirements.

## Key design constraints for professional-grade Zotero semantic search

- Zotero is open source research infrastructure. It has a healthy development pace. Privacy, running locally, running free matter.
- The community is global, collections are multilingual. Queries, documents, replies, it impacts the whole processing chain.
- Collections accrete thousands of entries. Missing/malformed files, legacy formats, misclassifications, duplicates... expect pathologies to be present.
- One bibliographic entry (a Zotero item) may contain many article-sized documents. A book has many chapters, a proceedings many talks, a dictionary many entries. It is wrong to assume that all items are less than 40 pages.
- In good prose, one paragraph is one idea. Chunking is paragraph-sized, we retrieve ideas not data snippets.
- While OCR would be good to have, it is out for now.

As with all programs, the system that work well must converge without manual rebuilds, expose
honest coverage, avoid recomputing unchanged content, filter before truncating
answers, survive very large documents, and operate within explicit CPU and
memory budgets.

Document [`SPEC.md`](SPEC.md) details the vision. It is organized in RFC section order
(Introduction, Terminology, Requirements, Constraints, Design, Security
Considerations).  It translates the vision into testable requirements.

Contents below the bar is generated to track implementation progress.

---


## Deliverables

<!-- generated status; sources are the linked owning documents and tickets -->

| deliverable | status | authority |
|---|---|---|
| Formal specification | **Complete** | [SPEC.md](SPEC.md): 24 ratified requirements, including R36 free operation |
| [Multilingual Menagerie](https://www.zotero.org/groups/6659303/semantic_search_challenge_fixture) | **In progress** | ticket 0029 |
| Verification and scoring bench | **In progress** | [bench/](bench/) and ticket 0026 |

Numbers in the **work owner** columns are local issues tracked in
[`tickets/`](tickets/) with [git-erg](https://github.com/MinhHaDuong/git-erg).

### Multilingual Menagerie

| object | state | work owner |
|---|---|---|
| Zotero fixture collection and reproducible injection | Live subset exercised; group attachment storage unresolved | 0632 |
| Corpus recipe, attachment state and drift | In progress | 0627, 0641 |
| Pinned questions and known-correct answers | In progress | 0029 |
| Multilingual and pathological-document coverage | In progress | 0029, 0632 |

### Verification and scoring bench

| object | state | work owner |
|---|---|---|
| Fixture runner, scoring and fail-controls | In progress | 0602, 0604, 0658 |
| Schema migration and proportional maintenance | In progress | 0623, 0649 |
| Privacy and free-default operation | In progress | 0660–0664, 0671 (R36) |
| Deletion, residue and uninstall | In progress | 0654–0657 |
| Concurrent serving and bounded duplicate work | In progress | 0650–0652 |
| Durable pause | In progress | 0643, 0665; upstream #56 / PR #57 |

Current focus and handoff: [STATE.md](STATE.md). Upstream movement and
contributions: [SYNC.md](SYNC.md). Evidence: [verification/](verification/).

This is an independent project and is not affiliated with or endorsed by the
Zotero project.
