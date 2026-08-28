# RUNBOOK — the workstation session that closes the current train segment

*Written 2026-08-27 at session close-out; trimmed 2026-08-28 after events
overtook it. Self-sunsetting: execute, hand the JSONs to the next session,
then DELETE this file — its durable state lives in tickets 0014/0024/0025
and SYNC.md, per the one-statement-per-fact rule. Already executed and
removed from this file: step 1 (PR B became upstream #25, hardened in
review, merged 2026-08-28, shipped in v1.9.0 — ticket 0015 closed) and
I-1's filing (upstream #26, with X6's direction offered as a verification
protocol — step 3's measurement now feeds that thread instead of gating the
filing). The remaining stopwords branch is on the fork at `309204b`-base,
validated green on upstream's own gates; the tickets carry the full record.*

Placeholders: `$FTS5` = your zoteus-fts5 checkout, `$FORK` = your MinhHaDuong/zoteus
checkout, `$DATA650` = the data dir holding the big (477k-passage) index,
`$DATAREAL` = your normal Zoteus data dir. Every step ends with a JSON you either
commit to `bench/results/` or hand to me — I do the guard declarations, ticket
updates, and text injection.

## 0. Setup (once, ~5 min)

```bash
cd $FTS5 && git pull                                  # renamed drivers (0030) + new X drivers
cd $FORK && git fetch origin                          # fork main is at v1.9.0 (bb414df)
git fetch https://github.com/oscardvs/zoteus main:upstream-main   # trunk v1.9.0
```

---

## 2. X2 — stopword-less OR p95 (~10 min) → opens PR A

```bash
cd $FORK && git checkout stopwords-follow-up && npm ci && npm run build
# ~20 natural queries carrying function words (seed list in the PR handover; pad
# with queries typical of your library) into /tmp/x2-queries.txt
python3 $FTS5/bench/query.py --server dist/index.js --data-dir $DATA650 \
  --backend sqlite --queries-file /tmp/x2-queries.txt --limit 20 \
  --out $FTS5/bench/results/0025-x2-stopwordless/queries-650k.json
```

Rule (DESIGN §3): p95 ≤ ~500 ms → the deletion ships alone; above → the PR grows
df-pruning first. → Hand me the JSON: I commit it, anchor the figure, inject the
number into PR A's body, and you open it with the pre-filled URL.

## 3. X6 — does extraction bump anything observable? (~20 min) → feeds #26

On BOTH a synced and a never-synced profile, with Zotero running:

```bash
# before: snapshot both sequences
curl -s "http://127.0.0.1:23119/api/users/0/items?format=versions&limit=1" -i | grep -i last-modified-version
curl -s "http://127.0.0.1:23119/api/users/0/fulltext?since=0" > /tmp/x6-census-before.json
# now force a re-extraction of ONE attachment (e.g. delete its .zotero-ft-cache
# in the storage folder, or Reindex Item from the Zotero UI), wait for it, then:
curl -s "http://127.0.0.1:23119/api/users/0/items?format=versions&limit=1" -i | grep -i last-modified-version
curl -s "http://127.0.0.1:23119/api/users/0/fulltext?since=0" > /tmp/x6-census-after.json
# and the item's own version before/after:
curl -s "http://127.0.0.1:23119/api/users/0/items/<ITEMKEY>" | python3 -c "import json,sys; print(json.load(sys.stdin)['version'])"
```

Record: did the library version move? the item version? the census entry for that
attachment? → Hand me the two censuses + the three observations: I write the X6
artifact, evaluate the DESIGN §3 rule (re-stamps-0 → bounded re-verify sweep;
bumps-something → md5 signal suffices), and post the measured answer on the
#26 thread, where the filing offered it as the verification protocol.

## 4. Trunk re-measurement (~30-45 min) → unblocks I-2

All on `upstream-main` (his code, not the fork), embeddings off. Trunk is now
v1.9.0 (`bb414df`); its search layer differs from v1.8.0 only by #25's own
fix, so measure there and name the results dir `trunk-1.9.0/`:

```bash
cd $FORK && git checkout upstream-main && npm ci && npm run build
# 4a. build wall-time + peak RSS, both backends, real library:
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend sqlite --build > $FTS5/bench/results/trunk-1.9.0/build-sqlite.json
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend memory --build > $FTS5/bench/results/trunk-1.9.0/build-memory.json
# 4b. the wall, on trunk: uncapped fulltext build on the memory backend
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend memory --build --max-items 1000000 --max-chars 0 \
  > $FTS5/bench/results/trunk-1.9.0/build-memory-uncapped.json
# 4c. warm query + resident memory: run_serve.py against each dir
```

→ Hand me the JSONs: I re-draft I-2 with trunk numbers only (his backend, his
tree), and the fork-prototype figures drop out of the text entirely.

## 5. X3a — monster RSS baseline on stock upstream (~15 min) → rss-gate fixture

Stock upstream, the uncapped 44,9 MB document's library, `run_serve`/`run_build`
with `--max-chars 0`; record VmHWM (reproduces 0011's 2 084,9 MiB class on
trunk). → feeds 0026's rss-gate fixture spec; commit JSON to
`bench/results/0025-x3a-monster-rss/`.

## 6. X1 recall half — int8 on the 93,022 real vectors (~15 min)

```bash
node $FTS5/bench/vec_real_measure.mjs --db <path-to-real-vector-search-index.sqlite> \
  --output $FTS5/bench/results/0025-x1-recall/real-93022-int8.json
```

Rule: int8 ships only if recall@30 ≥ 0,98 at pool ≤ 32×topK (the timing clause
already passed in-container — ticket 0025). → JSON to
`bench/results/0025-x1-recall/`.

## 7. Optional same-visit extra

- **X4 confirmation on the real index** — the driver takes a db path:
  `node $FTS5/bench/constrained_match.mjs /path/to/real/search-index.sqlite \
    > $FTS5/bench/results/0025-x4-constrained-match/real-477k.json`
  The synthetic verdict (ticket 0025) was never-build; this is its formality.

## Not in this runbook, deliberately

- **X5 / seg-1**: blocked on 0028 (segmenter unbuilt) and the zotero#6012 check.
- **I-2 filing**: happens after step 4, with trunk numbers per your ruling.
  I-1 is filed ([#26](https://github.com/oscardvs/zoteus/issues/26)); step 3's
  measured answer goes on its thread.

## The pre-filled PR form

The form opens with title and body already filled; press the green button
after X2, filling the two REPLACE lines in-form.

## PR A — stopwords follow-up (open AFTER X2; fill the two REPLACE lines in the form)

https://github.com/oscardvs/zoteus/compare/main...MinhHaDuong:zoteus:stopwords-follow-up?quick_pull=1&title=Delete%20the%20stoplist%3A%20no%20language%20loses%20its%20function%20words&body=%23%23%20The%20defect%0A%0AThe%20tokenizer%20carries%20a%2029-word%20English%20stoplist%2C%20which%20penalizes%20exactly%20one%0Alanguage%3A%20%22the%22%20is%20dropped%20while%20%22le%22%2C%20%22der%22%20and%20%22v%C3%A0%22%20pass.%20It%20is%20also%0Aasymmetric%20by%20construction%20%E2%80%94%20the%20FTS5%20document%20side%20%28%60unicode61%60%29%20has%20no%0Astoplist%2C%20so%20the%20index%20holds%20the%20very%20tokens%20the%20query%20side%20throws%20away.%20And%20it%0Aproduces%20queries%20that%20cannot%20say%20what%20they%20mean%3A%20%60to%20be%20or%20not%20to%20be%60%0Atokenizes%20to%20nothing%20at%20all%2C%20on%20both%20backends.%20bm25%20already%20down-weights%0Aubiquitous%20terms%2C%20which%20is%20the%20honest%20version%20of%20what%20a%20stoplist%20approximates.%0A%0A%23%23%20The%20fix%0A%0ADelete%20the%20list.%20%60tokenize%28%29%60%20keeps%20its%20Unicode%20token%20class%20and%20the%20one-char%0Adrop%2C%20nothing%20else.%20Existing%20indexes%20need%20no%20rebuild%3A%20terms%20are%20OR-ed%2C%20so%0Aevery%20query%20keeps%20matching%20through%20its%20content%20words%3B%20the%20SQLite%20index%20always%0Acontained%20the%20function%20words%20%28unicode61%20indexed%20them%20from%20day%20one%29%3B%20the%20JSON%0Abackend%20re-derives%20its%20postings%20from%20raw%20passage%20text%20on%20every%20load.%0A%0A%23%23%20The%20cost%2C%20measured%0A%0AThe%20OR-cost%20of%20high-frequency%20terms%20is%20the%20one%20thing%20to%20check%20before%20deleting%0Aa%20stoplist.%20Measured%20on%20a%20real%20%5B650k%5D-passage%20index%3A%20stopword-less%20OR-query%0Akeyword%20p95%20%3D%20%5BX%20ms%5D%20over%2020%20natural-language%20queries%20carrying%20function%20words.%0A%5BREPLACE%3A%20one%20sentence%20%E2%80%94%20comfortably%20under%20/%20near%20the%20~500%20ms%20where%0Acorpus-driven%20pruning%20of%20%3E50%25-document-frequency%20terms%20would%20be%20the%20follow-up.%5D%0A%0A%23%23%20Testing%0A%0A-%20%60tokenize%60%20cases%20updated%20to%20pin%20the%20new%20contract%20%28function%20words%20kept%20in%0A%20%20every%20language%2C%20one-char%20tokens%20still%20dropped%2C%20%22to%20be%20or%20not%20to%20be%22%20is%20a%0A%20%20searchable%20query%29%3B%20backend-parity%20case%20now%20asserts%20both%20backends%20answer%0A%20%20function-word%20queries%20identically.%0A-%20Full%20suite%3A%20727%20passed%20/%207%20skipped%3B%20typecheck%20and%20lint%20clean.

## Order if time is short

2 (X2 + PR A, 10 min) → 4 (trunk numbers, the I-2 gate) → 3 (X6, for the
#26 thread) → 6 → 5 → 7.
