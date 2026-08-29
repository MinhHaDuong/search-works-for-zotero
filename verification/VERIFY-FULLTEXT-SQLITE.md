# VERIFY — the `fulltext.sqlite` claim

Field verification of `zotero-cli-cc` PR #100 (2026-08-18), which states that
Zotero 10 moved its full-text index out of `zotero.sqlite` into a standalone
contentless FTS5 database, dropping `fulltextWords` / `fulltextItemWords`, and
that its `core/fts.py` ports Zotero's query-side `fulltext.js` including CJK
2-gram routing to `fulltextContentCJK`.

Verified 2026-08-29 against the author's own installation, against the shipped
JavaScript of the exact installed build, and against `zotero/zotero` at commit.

**No write of any kind was made to the author's Zotero data directory.** Every
inspection ran on copies in `/tmp/ztverify/` and on `omni.ja` extracted to
`/tmp/ztapp/`. Zotero was not running (`pgrep -f zotero` matched only this
agent's own shell). The scratch copies of `zotero.sqlite`, its `-wal` and
`-shm` siblings, `fulltext.sqlite` and `zotero.sqlite.bak` were taken with
`cp`; the 882,2 MiB backup copy was deleted after use. The `fts5vocab` tables
used to measure the CJK dictionary were created on the scratch copy, never on
the original.

Verified after the fact: every file's size and mtime is byte-identical to the
reading taken before any inspection, and the data directory's own mtime is
still 2026-08-22 08:53:20 — earlier than this session.

## 1. Verdict per sub-claim

| # | Sub-claim | Verdict | Strongest evidence |
|---|---|---|---|
| 1 | The full-text index lives in a standalone `fulltext.sqlite`, separate from `zotero.sqlite` | **CONFIRMED** | File present on this machine, 281 280 512 bytes; `fulltext.js:115` attaches it as `ftindex` |
| 2 | `fulltextWords` / `fulltextItemWords` were dropped from `zotero.sqlite` | **CONFIRMED** | Absent from the live DB, present with 733 709 / 18 122 750 rows in the pre-migration backup; dropped at `schema.js` userdata step 127 |
| 3 | The FTS5 tables are contentless | **CONFIRMED** | `content=''` in all four DDLs; a text select returns a row whose column is NULL |
| 4 | A `fulltextContentCJK` table exists | **CONFIRMED** | Present, 386 documents, `fts5(text, tokenize='ascii', content='', contentless_delete=1)` |
| 5 | The CJK geometry is 2-gram | **CONFIRMED** | 2 536 distinct terms in the author's CJK index, **every one exactly 2 characters**; `getCJKBigrams()` at `fulltext.js:2144` |
| 6 | Queries are CJK-routed to that table | **CONFIRMED** | `getWordMatchClause()` at `fulltext.js:2361`; routing is **exclusive**, not fused |
| 7 | The change is a Zotero **10** event | **CONFIRMED** | Commit `7c2a1d1`, 2026-06-30; `git tag --contains` returns 10.0.0 and 10.0.1 only |
| 8 | `core/fts.py` faithfully ports the query side | **PARTLY** | Routing, bigrams and clause shapes match; the port **drops upstream's `verify` flag** |
| 9 | The index was FTS5 *before* the move | **REFUTED** (implied, not asserted) | The pre-migration DB has no FTS5 table at all — the predecessor was a hand-rolled inverted index |

Two corrections to how the claim is usually restated, neither fatal:

- Zotero does not open `fulltext.sqlite` standalone; it **attaches** it to the
  main connection as `ftindex`. A third-party reader may of course open it
  standalone, and PR #100 does.
- The move was not "FTS5 relocated". It was a **representation change and a
  relocation in one step**: a hand-rolled `wordID`/`itemID` inverted index
  became four contentless FTS5 tables in a new file.

## 2. Evidence

### 2.1 The installation (direct observation, 2026-08-29)

Data directory resolved from `~/.zotero/zotero/qr3b6poy.default/prefs.js`:

```
user_pref("extensions.zotero.dataDir", "/home/haduong/data/Zotero");
```

Version, from `/opt/zotero7/app/application.ini`:

```
Vendor=Zotero
Name=Zotero
Version=10.0
BuildID=20260817151751
```

`compatibility.ini` records `LastVersion=10.0_20260817151751/20260811190631`.

Directory listing, `/home/haduong/data/Zotero/` (sizes in bytes, mtimes local):

```
fulltext.sqlite        281 280 512   2026-08-22 08:53:20
zotero.sqlite          100 859 904   2026-08-22 09:29:50
zotero.sqlite.bak      925 007 872   2026-08-21 14:26:48
zotero.sqlite.1.bak    925 007 872   2026-08-20 21:44:03
```

`fulltext.sqlite` exists. The main database fell from 882,2 MiB to 96,2 MiB
across the migration, and 268,2 MiB of index moved into the new file.

### 2.2 The schema, as installed

Schema dump of the scratch copy:

```sql
CREATE VIRTUAL TABLE fulltextContent    USING fts5(text, tokenize='unicode61', content='', contentless_delete=1);
CREATE VIRTUAL TABLE fulltextContentCJK USING fts5(text, tokenize='ascii',     content='', contentless_delete=1);
CREATE VIRTUAL TABLE fulltextNotes      USING fts5(text, tokenize='trigram',   content='', contentless_delete=1);
CREATE VIRTUAL TABLE fulltextNotesCJK   USING fts5(text, tokenize='ascii',     content='', contentless_delete=1);
CREATE TABLE fulltextIndexState     (itemID INTEGER PRIMARY KEY, version INT NOT NULL);
CREATE TABLE fulltextNoteIndexState (itemID INTEGER PRIMARY KEY, version INT NOT NULL);
CREATE INDEX fulltextNoteIndexState_stale ON fulltextNoteIndexState(itemID) WHERE version=0;
CREATE TABLE noteText          (itemID INTEGER PRIMARY KEY, text TEXT);
CREATE TABLE fulltextIndexMeta (key TEXT PRIMARY KEY, value NOT NULL);
```

`PRAGMA user_version` = 2. `PRAGMA journal_mode` = delete. Contents:

| Table | Documents |
|---|---|
| `fulltextContent` | 13 090 |
| `fulltextContentCJK` | 386 |
| `fulltextNotes` | 1 200 |
| `fulltextNotesCJK` | 0 |
| `fulltextIndexState` | 14 112, all at version 1 |

`fulltextIndexMeta` holds one row: `localUserKey` = `LGLIg9Zg`. This matters —
see §3.3.

### 2.3 The dropped tables, with a before/after control on this machine

Probe against the live `zotero.sqlite`, asking `sqlite_master` for four names
at once, returns exactly one: `fulltextItems`. That single returned row **is**
the probe's positive control — the query form demonstrably returns names when
names exist. A second control on tables known to exist returned `items` and
`itemAttachments`. A `LIKE 'fulltext%'` sweep over the whole live database
returns only `fulltextItems` and its two indexes.

The stronger control is the pre-migration backup, `zotero.sqlite.bak`, written
2026-08-21 14:26 — the same file, one schema version earlier:

```
fulltextItemWords   18 122 750 rows
fulltextWords          733 709 rows
fulltextItems           12 402 rows
userdata schema 125, compatibility 7
```

versus the live database at userdata 129, compatibility 9. The legacy DDL:

```sql
CREATE TABLE fulltextWords (wordID INTEGER PRIMARY KEY, word TEXT UNIQUE);
CREATE TABLE fulltextItemWords (wordID INT, itemID INT, PRIMARY KEY (wordID, itemID), ...);
```

No FTS5 virtual table appears anywhere in the backup. This is what refutes
sub-claim 9: the predecessor was not FTS5.

The migration step, read from the shipped `schema.js` of this exact build
(`/opt/zotero7/app/omni.ja` → `chrome/content/zotero/xpcom/schema.js:3698`):

```javascript
if (i == 127) {
    await _updateCompatibility(9);
    await Zotero.DB.queryAsync("DROP TABLE IF EXISTS fulltextItemWords");
    await Zotero.DB.queryAsync("DROP TABLE IF EXISTS fulltextWords");
    Zotero.Prefs.clear('vacuum.lastTime');
```

Userdata step **127**, which also bumps the compatibility level to 9 —
matching both observed values.

### 2.4 Contentless, proved

Selecting the indexed column for an existing rowid returns the row with the
column NULL:

```
rowid = 31 | text IS NULL = 1 | quote(text) = NULL
```

Positive control, on the one table in the same file that does store text —
`noteText` returns `text IS NULL = 0` and real content. The FTS5 tables return
NULL for their column; `noteText` does not. Matching in the contentless table
still works: a CJK match returns rowids 3 219, 3 220, 5 624, 6 931 and 16 160.

The comment at `fulltext.js:157` gives Zotero's reason for the split into four
tables: "contentless FTS5 tables can't be filtered by an extra column, so
attachment content and notes couldn't be told apart in one table."

### 2.5 The CJK 2-gram geometry — measured, then read in source

The `ascii` tokenizer cannot segment CJK, so the geometry is decided by the
producer. Measured directly on the author's index, through an `fts5vocab`
table built over the CJK index: **2 536 distinct terms, and the length
histogram has exactly one bucket — length 2, count 2 536.** No other length
occurs.

The top terms make the sliding window visible — a single source string,
bigrammed with overlap:

```
中国  国社  社会  会科  科学  学院  院研  研究  究生  生院  院制  制作
```

each at document frequency 1 in the same item, which is
中国社会科学院研究生院制作 stepped one character at a time. The overlap is
confirmed by an adjacency phrase query on the three leading bigrams, which
matches 1 document: positions are stored, and consecutive bigrams sit
adjacent.

Script coverage, by codepoint class over the same vocabulary: Han 1 720,
Hiragana 467, Hangul 279, Katakana 155, pure-Latin 0.

Now the shipped code of this build, `fulltext.js:2130`:

```javascript
const _cjkCharRE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u;
const _cjkRunRE  = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]+/gu;
```

and the generator, `fulltext.js:2144`:

```javascript
function getCJKBigrams(text) {
  if (!text) { return ''; }
  let bigrams = [];
  for (let match of text.matchAll(_cjkRunRE)) {
    let run = match[0];
    for (let i = 0; i < run.length - 1; i++) {
      bigrams.push(run.substr(i, 2));
    }
  }
  return bigrams.join(' ');
}
```

`substr(i, 2)`, stepping by one: overlapping 2-grams, scoped to CJK runs,
joined by spaces so the `ascii` tokenizer yields one token per bigram. The
same function runs on both sides — index (`fulltext.js:2208`) and query
(`fulltext.js:2370`).

The design rationale is in the table-creation comment, `fulltext.js:146`:

> CJK: overlapping 2-grams of CJK runs only, space-separated, indexed with the
> ascii tokenizer (which leaves multibyte characters intact and splits on the
> spaces). The word tokenizer treats a CJK run as a single token, so the
> 1-2-character queries common in CJK go here instead.

### 2.6 Routing is exclusive, not fused

`getWordMatchClause()`, `fulltext.js:2361`:

```javascript
let hasCJK = _cjkCharRE.test(normalized);
let hasNonCJK = hasNonCJKWordChars(normalized);
// Pure CJK: match the term's 2-grams as a contiguous phrase against the CJK index
if (hasCJK && !hasNonCJK) {
  let bigrams = getCJKBigrams(normalized);
  // A single CJK character has no 2-gram
  if (!bigrams) { return null; }
  return { table: _contentTables.cjk, match: '"' + bigrams + '"', verify: false };
}
if (hasCJK) { return null; }
```

Three states, and the two failure states matter for our own design:

- **pure CJK, ≥ 2 characters** → the CJK table alone, as one contiguous
  bigram phrase, `verify: false`;
- **pure CJK, exactly 1 character** → `null`. The index cannot answer it, and
  the caller falls back to scanning the cached text. The comment at line 149
  advertises "1-2-character queries"; the code answers only the 2-character
  case from the index;
- **mixed script** → `null`, for the reason given at line 2161: "the CJK index
  would drop the non-CJK characters".

The two tables are **twins at index time and disjoint at query time**. All 386
CJK documents are also present in `fulltextContent` (intersection 386,
CJK-only 0) — but `unicode61` indexes a CJK run as one undivided token, which
is why the main table's CJK vocabulary holds entries such as
`切换到简体中文` and `日本語に切り替える` as single terms. Useful for an exact
whole-run match, useless for substring search. Hence the twin.

### 2.7 The two version constants, both matching this machine

`fulltext.js:42`:

```javascript
// Schema version of the attached index database (fulltext.sqlite) ...
const _indexDBVersion = 2;
// Version of the index format. Bump to force a rebuild of the index from the cached text ...
const _contentIndexVersion = 1;
```

Observed: `PRAGMA fulltext.user_version` = 2; all 14 112 rows of
`fulltextIndexState` at version 1. Both agree.

### 2.8 Upstream: the commit, the date, the release

Read on a full clone of `zotero/zotero`, HEAD `bccaf46`, 2026-08-27.

The split landed in **commit `7c2a1d127d73a555ccebbfd7fad0e38e4b348b39`,
authored 2026-06-30 13:40:36 −0400 by Dan Stillman, "Add full-text content
search via FTS5"** — 9 files, +1 488 / −346. From its message:

> Index attachment content into a contentless trigram FTS5 table in a separate,
> attached fulltext.sqlite, normalized so matching is accent- and
> case-insensitive. For content containing CJK characters, a companion
> 'ascii'-tokenized table holds bigrams so 1-2 character CJK queries, which the
> trigram tokenizer can't match, still work. The extracted text still lives in
> the .zotero-ft-cache files, so the index is fully derived and rebuildable.

The same commit removed `fulltextWords` and `fulltextItemWords` from
`resource/schema/userdata.sql`, bumped that file's header 126 → 127, raised
`_maxCompatibility` 8 → 9, and dropped the `fulltextItemWords` integrity-check
rule. `git tag --contains 7c2a1d1` returns **`10.0.0` and `10.0.1` only**; tag
`10.0.0` is dated 2026-08-17, `9.0.6` is 2026-07-07 and contains no reference
to `fulltext.sqlite`. The drop is a Zotero 10 event, not a point release.

There is **no `resource/schema/fulltext.sql`**. The index schema is created
imperatively in `setUpContentDB()`, which is why the file carries a `PRAGMA
user_version` written from `_indexDBVersion` rather than a schema-file header.

Two follow-ups matter more than they look:

- **`0ce289a`, 2026-07-17, "Use a word index for full-text content search"**
  changed the main content table from `trigram` to `unicode61` and bumped
  `_indexDBVersion` 1 → 2, forcing the rebuild. Zotero shipped trigram for
  content, then moved off it within three weeks, keeping trigram for notes
  only. Its message: "Notes keep the trigram index and CJK matching is
  unchanged." That trajectory is independent support for our own trigram kill
  at `DESIGN.md:738`, and it is worth knowing that the platform tried the
  thing we rejected and rejected it too.
- **`bcfa43b`, 2026-07-17, "Fix routing of search terms mixing CJK and
  non-ASCII words"** replaced a naive `/[a-z0-9]/` test with
  `hasNonCJKWordChars()`. The bug: "A term mixing CJK with non-ASCII words
  (e.g., Cyrillic plus Japanese) was routed to the CJK index with only its CJK
  characters, matching every document that contained those." If we build the
  fused third list, this is the exact trap, already found and fixed once
  upstream.

The `getCJKBigrams` geometry itself is **byte-identical to its 2026-06-30
form**. Only the routing predicate and the main tokenizer moved.

**No public release note names the split.** The changelog entry for Zotero
10.0 (2026-08-17) says "Much faster full-text content searches" and
"Accent-insensitive searching"; `fulltext.sqlite`, FTS5 and the separate index
database appear nowhere in it. The change is documented only in the commit
message and the source comments. Anyone tracking this platform from release
notes alone would have missed it entirely — which is the general lesson for
`SYNC.md`; it is more than a detail of this claim.

### 2.9 A defect in the bigram generator, reproduced here

Reported as an observation with a positive control, not as a product failure.

`run.length` and `run.substr(i, 2)` are **UTF-16 code-unit** operations, while
`\p{Script=Han}` under the `u` flag matches astral code points. For CJK
Unified Ideographs Extension B and beyond (U+20000 and up) each character is a
surrogate pair, so the window slides by code unit rather than by character. I
ran the function verbatim under `node`:

```
BMP han     "気候 候変 変動"          <- correct
hangul      "대한 한민 민국"          <- correct
astral han  "𠀀 \udc00\ud840 𠀁 \udc01\ud840 𠀂"
astral: token count = 5 | code-point lengths = 1,2,1,2,1
tokens containing an unpaired surrogate: 2 of 5
```

The two BMP cases are the positive control: the same function, same run,
produces correct bigrams. Three astral characters produce five tokens, of
which three are single characters and two are **reversed broken surrogate
pairs** (a low surrogate followed by a high one).

Scope, honestly. The query side calls the same function, so an astral query is
mangled identically and still matches its own document. The user-visible
symptom would be index bloat and false positives on astral text, not a miss.
And **there is no evidence of it on this machine**: all 2 536 terms in the
author's CJK vocabulary are exactly 2 code points, where an astral character
would appear as a 1-code-point token. Extension-B ideographs are rare in
ordinary bibliography. This is a latent defect in code we may copy, not a
live problem in the author's library — and if we do copy the geometry, iterate
over code points.

### 2.10 PR #100 itself, treated as a lead

Repository `Agents365-ai/zotero-cli-ai` — renamed from `zotero-cli-cc`, which
still redirects. PR #100, "feat(rank): score full text via Zotero 10's FTS5
index (fulltext.sqlite)", opened 2026-08-18T16:42:00Z and **merged 48 seconds
later by its own author**, unreviewed, merge commit `dfb4d0e`.

Its claim, verbatim:

> Zotero 10 dropped `fulltextWords`/`fulltextItemWords` from zotero.sqlite and
> moved the full-text index to a separate `fulltext.sqlite` (contentless FTS5,
> keyed by attachment itemID).

**The PR cites no external evidence.** No Zotero commit SHA, no release note,
no forum thread; its warrants are two self-assertions and a test fixture
constructed from the claim. It is nonetheless **substantially correct** — as
established above by evidence entirely independent of it.

Its port, `src/zotero_cli_cc/core/fts.py`, opens the file read-only
(`file:...?mode=ro`) as a sibling of `zotero.sqlite`, generates overlapping
bigrams query-side, and routes pure CJK to `fulltextContentCJK` as a quoted
phrase — matching upstream. Two divergences worth recording:

- it **drops upstream's `verify` flag**, so it produces upstream's *candidate*
  set rather than its *verified* set, over-matching phrases and
  punctuation-bearing terms such as `c++`;
- it open-codes the Unicode script ranges as explicit codepoint ranges,
  because Python's `re` has no `\p{Script=…}`. A faithful transcription in
  intent; an unaudited one in fact.

## 3. What this means for our documents

### 3.1 `DESIGN.md §2.6` — the CJK paragraph is now understated and misattributed

Current text:

> The scheduled companion is **2-gram twin tables** — #6012's shipped geometry,
> and decisive on its own terms: the modal Chinese word is two characters,
> unrepresentable as an exact trigram — backfilled from slabs for CJK-bearing
> passages only, query-routed, fused as a third list.

Two defects, one of attribution and one of tense.

**Attribution.** "#6012's shipped geometry" credits the wrong artifact. The
2-gram geometry is in **shipped Zotero 10's keyword path**, `fulltext.js`, not
in the draft semantic-search pull request. #6012 is a draft; `getCJKBigrams`
is in the binary on the author's disk. The phrase should name the shipped
source, which is both more accurate and considerably stronger: a design
choice we can point at in a release beats one we point at in a draft.

**Tense.** "scheduled" and "companion" read as future work awaiting a platform
change. The geometry is observable today, on this machine, with a schema we
can read. Our companion table is still ours to build — Zotero's index is keyed
by its own `itemID` and covers attachments, not our entries — but the
*geometry decision* is no longer a bet. It is a copy.

Suggested replacement for the attribution clause: **"Zotero 10's shipped
keyword geometry (`fulltext.js`, `getCJKBigrams`), verified on the author's
own index: 2 536 distinct terms, every one exactly two characters."**

One design divergence to state out loud rather than let a reader infer.
DESIGN says "fused as a third list". Zotero does **not** fuse — it routes
exclusively and returns `null` for mixed-script and single-character terms,
falling back to a scan of cached text. Fusing is a genuine improvement over
the platform, and the sentence should say so deliberately instead of
appearing to describe platform behaviour. The two platform dead ends
(single CJK character, mixed script) are exactly the cases a fused third list
would answer, which is the argument for our variant.

Also worth adding: the rejected-list entry at `DESIGN.md:738` reads "trigram
CJK (the modal Chinese word is two characters)". That kill is now corroborated
by the platform, which reserves `trigram` for **notes** and uses `ascii` +
pre-generated bigrams for CJK. Same conclusion, independent authority.

### 3.2 `CONSTRAINTS.md` C2 — one sentence is now incomplete

C2 currently says:

> zotero/zotero#6012 — the draft pull request in which Zotero is building its
> own semantic search — is active, and exposes nothing over the local API yet.

That remains true of #6012, and nothing here touches it. But C2's framing —
"the ground moves", with the platform's relevant motion located in a draft PR
— is now incomplete. The ground moved in a **shipped release**, between
2026-08-20 and 2026-08-22 on this machine, and it moved under the keyword
path, which is the half of our design C2 does not currently track.

Suggested addition to C2's sharpenings, as one bullet:

> Zotero 10 (userdata step 127, compatibility 9) dropped `fulltextWords` /
> `fulltextItemWords` and moved the keyword index into a separate attached
> database `fulltext.sqlite` — four contentless FTS5 tables (`unicode61` for
> content, `ascii` over pre-generated overlapping 2-grams for CJK, `trigram`
> for notes), `PRAGMA user_version` 2, per-item format version 1 in
> `fulltextIndexState`. Verified on the author's installation 2026-08-29. The
> index is keyed by **local `itemID`** and stamped with `localUserKey` in
> `fulltextIndexMeta`; Zotero itself drops and rebuilds the whole index when
> that key does not match. Any external reader must check it.

C2's chunker sentence also needs a correction, established in §5.2. Current
text:

> Zotero's own chunker splits on structural boundaries, measured in tokens —
> 120 minimum, 768 maximum, 48 overlap — never crosses a section, and embeds
> the heading path with the text.

"Never crosses a section" is false as an absolute. Suggested replacement:

> Zotero's own chunker splits on structural boundaries, measured in tokens —
> 120 minimum, 48 overlap, and a 768 ceiling that never binds because every
> shipped model declares a 512-token limit. It never merges two sections each
> large enough to stand alone, but it **does** merge sections below the
> minimum forward into their neighbour, and exempts auxiliary sections
> (captions, image descriptions) from merging in either direction. It embeds
> the first section's heading path with the text, in a separate `embedText`
> field, paid for out of the token budget and dropped when it would exceed a
> quarter of it.

### 3.3 A new constraint fact C1 should probably absorb

This is the finding with the longest reach, and it is not in the claim.
`fulltext.js:114`:

```javascript
// The index is keyed by local itemID, which is reassigned whenever zotero.sqlite is
// recreated (e.g., deleted and re-synced from the server). An index built against a
// different database instance would map its rows to the wrong items, so it has to be
// discarded and rebuilt rather than reused. Detect that by comparing the localUserKey
// the index was stamped with against the current one.
```

Zotero has independently arrived at C1's derivation-graph discipline and at
C1's `Zotero-Server-ID` partitioning sharpening, for the same reason and with
the same remedy: a stored key, compared on open, with a rebuild on mismatch.
`fulltextIndexMeta.localUserKey` is the platform's `Zotero-Server-ID`. That
is a strong corroboration of C1 and worth one sentence there — and if we ever
read `fulltext.sqlite` directly, it becomes binding rather than decorative.

Second reach: `.zotero-ft-cache` files remain on disk (13 631 of them here),
and `fulltext.js:97` says so explicitly — "the original extracted text still
lives in the `.zotero-ft-cache` files". Zotero's index is rebuildable from
local cache without re-extraction. That is a cheaper local corpus than the one
C1's experiment X6 is being designed around, and it bears on the
extractor-identity question. Not a contradiction; a possible shortcut.

### 3.4 `SYNC.md` — the tracking method has a blind spot this exposes

Worth stating separately because it outlives this claim. A keyword-search
rewrite, a schema split, a new database file and two dropped tables shipped in
Zotero 10.0 on 2026-08-17, and **the public changelog says only "Much faster
full-text content searches"**. No release note names `fulltext.sqlite`, FTS5,
or the split. The change is visible in the commit message, in the source
comments, and on disk — nowhere else.

`SYNC.md` tracks the platform through `#6012`, a draft pull request, which is
where the *announced* work is. The platform's largest recent move in our own
problem area arrived unannounced, in a release, three weeks before we noticed,
and it was found here only because a third party's PR mentioned it in passing.
The cheap remedy: watch `chrome/content/zotero/xpcom/fulltext.js` and
`resource/schema/userdata.sql` on `main` directly, the way `UPSTREAM` already
pins a reviewed SHA for the zoteus fork. A schema-header diff is one line of
`git`, and it would have fired on 2026-06-30 rather than 2026-08-29.

### 3.5 A note on the figure guard

This file is not scanned by `bench/check_figures.py` — its `PROSE` map covers
`STATE.md`, `README.md`, `SYNC.md`, `DESIGN.md` and `REQUIREMENTS.md` only, so
`make check` is unaffected by anything here. But the guard's discipline applies
the moment any of these numbers moves into one of those files. The candidates,
if §3.1's suggested edit is taken, are **2 536** distinct CJK terms and the
**2**-character uniformity. They are measurements of the author's live library,
not artifacts under `bench/results/`, so they have no key path to declare
against. Either the measurement is re-run into a small committed JSON summary
and declared, or the prose cites it as an observation with its date and does
not pretend to be reproducible from the repo. The second is cheaper and
honest; the first is what the repo's convention would prefer. The author
chooses.

## 4. Draft `DECISIONS.md` entry — DRAFT ONLY, not added to the file

> **2026-08-29 — Zotero 10 shipped the CJK 2-gram geometry.** Verified on the
> author's own installation (10.0, build 20260817151751) and in the shipped
> `fulltext.js` of that build: Zotero 10 dropped `fulltextWords` /
> `fulltextItemWords` at userdata step 127 and moved the keyword index into a
> separate attached database `fulltext.sqlite` — four contentless FTS5 tables,
> among them `fulltextContentCJK`, `fts5(text, tokenize='ascii', content='')`,
> fed space-separated overlapping 2-grams generated by `getCJKBigrams()` over
> Han/Hiragana/Katakana/Hangul runs. Measured on the author's index: 2 536
> distinct terms, every one exactly two characters. Consequences: DESIGN.md
> §2.6 stops crediting the 2-gram geometry to the draft #6012 and credits
> shipped Zotero 10 instead; the CJK companion moves from "scheduled, pending
> the platform" to "geometry settled, ours to build"; §2.6 states explicitly
> that our fused-third-list variant **differs** from the platform, which
> routes exclusively and answers neither a single CJK character nor a
> mixed-script term from the index. C2 gains the shipped-schema bullet. C1
> gains the observation that Zotero stamps its index with `localUserKey` and
> rebuilds on mismatch — the platform's own form of the Server-ID partitioning
> C1 already requires. The trigram-CJK kill stands, now corroborated: the
> platform reserves `trigram` for notes. Nothing here changes an upstream
> commitment; the PR budget is untouched.

A second, separable entry for the C2 chunker corrections of §5 — the author
may ratify either without the other:

> **2026-08-29 — of the four #6012 attributions in C2, one is refuted.** Read
> at PR head `77e2c4b`, 2026-08-28. (a) The token geometry 120 / 768 / 48
> holds as constants, but 768 never binds: every shipped embedding model
> declares `maxTokens: 512`, so the effective ceiling is ~510 minus the
> heading prefix. DESIGN.md §2.2's "adopted verbatim" and its ≈ 250–300k
> passage estimate are inconsistent with each other under that reading; the
> author picks which to move. (b) **"Never crosses a section" is refuted as
> stated.** The chunker merges sections below the 120-token minimum forward
> into their neighbour, asserted by #6012's own tests; it never merges two
> sections each able to stand alone, and exempts auxiliary sections.
> CONSTRAINTS.md C2 is corrected accordingly. Our boundary ruling is stricter
> than the platform's, which is now a deliberate divergence rather than an
> alignment. (c) Smallest-first is confirmed and applies to **attachments
> only** — the metadata queries carry no ORDER BY, and metadata is enqueued
> before attachments as a class. DESIGN.md §2.3's scoping was already correct
> and stands. (d) The CJK 2-gram geometry is **not** #6012's: it predates the
> PR on `main` and ships in Zotero 10. #6012 extends it to a new item-metadata
> table and adds a query-side implementation with a **single-character CJK
> fallback** the shipped path lacks — worth adopting, since it answers one of
> the two dead ends our fused third list is meant to cover.

## 5. Secondary — the four C2 attributions to zotero#6012

Reported separately because it is a different question from the primary claim.
Our field review could not re-verify four C2 attributions from publicly
readable PR text and recorded them as "could not look". They are now read at
source.

**Provenance.** `zotero/zotero#6012` "Semantic search", opened 2026-08-05 by
dstillman, **still open and still draft**. Head SHA
`77e2c4b05111077108fe31e879f95b9687643e9a`, committed 2026-08-28T14:30:06-07:00.
56 files, +15 368 / −106. Fetched as `pull/6012/head`; the diff was captured
separately so PR-added lines could be told from pre-existing context — which
turns out to decide question 4.

| # | C2 attribution | Verdict |
|---|---|---|
| 1 | Token chunk geometry 120 / 768 / 48, measured in tokens | **CONFIRMED**, with a caveat that changes what 768 means |
| 2 | Never crosses a section | **REFUTED** as an absolute; PARTLY true as a policy |
| 3 | Smallest-first ordering | **CONFIRMED** for attachments; does not apply to items |
| 4 | CJK 2-gram geometry | **PARTLY** — the geometry is *not* #6012's; it predates it |
| — | *(bonus)* Embeds the heading path with the text | **CONFIRMED** |

### 5.1 The geometry — confirmed, but 768 never binds

`embeddings.js:1512`, `Zotero.Embeddings.Chunking`:

```javascript
const CHUNK_OVERLAP_TOKENS = 48;
const CHUNK_MIN_TOKENS = 120;
const CHUNK_MAX_TOKENS = 768;
```

The unit is unambiguously tokens — counted by the model's own
`PreTrainedTokenizer` (`embeddings.js:1552`). The same three numbers are
mirrored in `utilities_internal.js:3368` (`Zotero.Utilities.Internal.Chunking`)
for consumers with no tokenizer, alongside `CHARS_PER_TOKEN = 4` and
`CJK_CHARS_PER_TOKEN = 1`.

The caveat is material. The effective budget is a `min`, not the constant —
`embeddings.js:1638`:

```javascript
budget: Math.min(CHUNK_MAX_TOKENS, Zotero.Embeddings.getModelMaxTokens())
    - specialTokens - (prefix ? count(prefix) : 0),
```

**Every shipped model in the registry declares `maxTokens: 512`** —
`bge-small-en-v1.5`, `bge-small-zh-v1.5`, `multilingual-e5-small`
(`embeddings.js:69`). Only two entries labelled `test:` carry 8 192. So in any
shipped configuration the real ceiling is roughly 510 tokens minus the heading
prefix, and 768 is a constant that never binds.

That has a downstream consequence in our own numbers. `DESIGN.md:666`
estimates "768-token chunks give ≈ 250–300k passages from the same corpus that
yields …". If we adopt Zotero's geometry verbatim as `DESIGN.md:211` says we
do, we inherit an *effective* ~510, and the passage count rises by roughly half
again. Either the estimate or the "adopted verbatim" needs adjusting; the
choice is the author's.

### 5.2 "Never crosses a section" — refuted as stated

`chunkSections()` deliberately merges sections that are individually below the
120-token minimum. `utilities_internal.js:3718`:

```javascript
// Group sections into chunk-worthy units, combining any too small to
// stand alone with the sections that follow them
...
// A trailing group still under the minimum joins the previous body
// group rather than standing alone as a runt chunk
if (pending) {
    if (lastBodyGroup >= 0) {
        groups[lastBodyGroup].entries.push(...pending.entries);
    }
```

A group of several sections is concatenated and chunked as one, so a chunk can
span two or more sections. The PR's own tests assert both halves:
`embeddingsTest.js:637` "shouldn't put two substantial sections in one chunk",
and `embeddingsTest.js:670` "should combine sections too small to embed on
their own", which asserts a single chunk containing `Title page`, `Copyright
notice` **and** `alpha0`. Line 690 asserts one chunk spanning a `Body` and an
`Appendix` section.

The accurate statement, which C2 should carry instead: **a chunk never merges
two sections each substantial enough to stand alone; sections below the
minimum are merged forward into their neighbour.** A third rule sits on top —
sections flagged `auxiliary` (captions, image descriptions) never merge in
either direction (`utilities_internal.js:3711`).

This is the one place where C2's current sentence would mislead an
implementer. Our boundary ruling (DECISIONS.md 2026-08-26, "chunk boundaries
align to section/entry boundaries where structure is detectable, never
straddling two entries") is cited as aligning with platform prior art. It
aligns with the *substantial-section* half of that prior art and is stricter
than the runt-merging half. Worth saying so, because a runt-merging rule is
one we may actually want: a 40-token section embedded alone is a poor vector.

### 5.3 Smallest-first — confirmed, and correctly scoped in our text already

`embeddings.js:2085`, `_getEligibleItemIDs()`:

```sql
ORDER BY COALESCE(totalChars, totalPages * ?, ?), itemID
```

with `CHARS_PER_PAGE = 3000` and `UNKNOWN_ATTACHMENT_SIZE = 99999999` — so an
attachment of unrecorded size sorts to the **end**, not the front. The comment
gives the motive: "smallest first so that one enormous book doesn't sit at the
head of the queue while the rest of the library waits behind it."

The three sibling queries for regular items, notes and annotations
(`embeddings.js:2048`) carry **no `ORDER BY` at all**. Ordering by size is an
attachment-only rule. What separates metadata from attachments is class, not
size: `_enqueueAllLibraries()` (line 2149) iterates
`for (let kind of ['items', 'attachments'])`, so all metadata across all
libraries is enqueued before any attachment anywhere.

`DESIGN.md:259` already says "#6012 … orders attachments smallest-first" and
rejects it "at item granularity on R2's own text". That scoping is exactly
right and needs no change. Noted here only because the field review flagged it
as unverified; it is now verified, and it was correct.

### 5.4 CJK 2-gram — the attribution is the finding

**The 2-gram geometry is not #6012's.** It is on `main` and ships today — the
same code §2.5 read out of the author's installed build. `fulltext.js` at
`main` already contains the `fulltextContentCJK` creation and `getCJKBigrams`
with the identical `substr(i, 2)` loop and the identical four-script class.
In the #6012 diff, `getCJKBigrams` appears **only as a call site and a comment
reference, never as an added definition.**

What #6012 does add is an extension of the existing scheme:

- a new item-metadata CJK table, `fulltextItemTextCJK`, same `ascii`
  tokenizer, columns `title, abstract, note, annotation`, fed by the
  pre-existing generator;
- a new file `lexical.js` (+1 066 lines, wholly added), which reimplements the
  bigram construction on the **query** side, with a single-character fallback
  the shipped keyword path lacks — a lone CJK character is matched as a prefix
  against every bigram starting with it (`'"' + term.text + '"*'`).

So `DESIGN.md:461`'s "#6012's shipped geometry" is doubly imprecise: it is not
#6012's, and #6012 is not shipped. The correct credit is shipped Zotero 10's
keyword path, per §3.1. #6012 deserves separate credit for something we should
want: **the single-character CJK fallback**, which is exactly one of the two
dead ends §2.6 identifies in the shipped router, and which our fused third
list would otherwise have to invent.

### 5.5 Bonus — the heading path is embedded, and paid for

`utilities_internal.js:3762`:

```javascript
let outlinePath = group.entries[0].section.outlinePath || '';
let prefix = outlinePath ? outlinePath + '\n\n' : '';
let prefixSize = prefix ? count(prefix) : 0;
// A pathological outline path that would eat a real share of the
// window hurts more than it helps
if (prefixSize > budget / 4) { prefix = ''; prefixSize = 0; }
```

Emitted as a second field, leaving the display text plain (line 3808):
`{ text: piece.text, embedText: prefix + piece.text, size: piece.size + prefixSize }`.
The body is chunked against `budget - prefixSize`, so the prefix is paid out
of the window rather than added on top. Two details our design should copy:
the **quarter-of-budget cap** on a pathological outline path, and the
**two-field split** — `text` for display, `embedText` for the vector.

One wrinkle, from the interaction with §5.2: a merged group takes only its
**first** section's outline path, so the tail sections of a merged chunk carry
a heading that is not theirs. If we adopt runt-merging, we inherit that defect
unless we handle it.

## 6. What could not be established

- **Whether any `fulltext.sqlite` existed before the Zotero 7 line.** The probe
  at tag `9.0.6` returns nothing, which is a real negative and enough for "new
  in 10.0". The same probe at `6.0.37` timed out: the clone was made with
  `--filter=blob:none`, so a historical grep refetches blobs one at a time. No
  claim is made about pre-7.x. What would settle it: a full-blob clone.
- **When the `savedSearchConditions` rewrite joined userdata step 127.** It was
  a commented-out `i == 128` in `7c2a1d1` and is live inside step 127 in the
  shipped build. Nothing about the fulltext drops depends on it; noted only so
  the step's content is not mistaken for its original form.
- **Whether the migration on this machine was clean.** The two 882,2 MiB
  backups (2026-08-20 and 2026-08-21) bracket the event, and
  `fulltext.sqlite` is dated 2026-08-22 08:53 against `zotero.sqlite` at
  09:29 the same morning. Consistent with a normal upgrade migration; not
  independently confirmed against the logs, which were not read.
- **Whether PR #100's open-coded Unicode ranges match `\p{Script=…}` exactly.**
  Its port replaces four Unicode script properties with hand-written codepoint
  ranges. The ranges look right and were not diffed against the real script
  tables. What would settle it: enumerate both sets over the BMP plus the CJK
  supplementary planes and compare. Relevant only if we adopt that code, which
  we have no reason to.
- **Whether `fulltext.sqlite` is safely readable while Zotero runs.** PR #100
  asserts it is not held under `locking_mode=EXCLUSIVE`, unlike
  `zotero.sqlite`. Not tested here — Zotero was not running, deliberately.
  What would settle it: open it read-only with the application live, which is
  the author's call to authorize, not mine.
