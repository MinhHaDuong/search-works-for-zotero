# RUNBOOK — the workstation session that closes the current train segment

*Written 2026-08-27 at session close-out; trimmed 2026-08-28 after events
overtook it. Self-sunsetting: execute, hand the JSONs to the next session,
then DELETE this file — its durable state lives in tickets 0014/0016/0024/0025
and SYNC.md, per the one-statement-per-fact rule. Already executed and
removed from this file: step 1 (PR B became upstream #25, hardened in
review, merged 2026-08-28, shipped in v1.9.0 — ticket 0015 closed) and
I-1's filing (upstream #26, with X6's direction offered as a verification
protocol — step 3's measurement now feeds that thread instead of gating the
filing). The remaining stopwords branch is on the fork at `309204b`-base,
validated green on upstream's own gates; the tickets carry the full record.*

Placeholders: `$FTS5` = your zoteus-fts5 checkout, `$FORK` = your MinhHaDuong/zoteus
checkout, `$DATA650` = the data dir holding the big index — misnamed, it holds 477k
passages, not 650k, and as of 2026-08-29 nothing on disk under that name is
readable by v1.9.0 (step 2); the rebuilt one is
`/home/haduong/data/projets/zoteus-bench/x2-rebuild`,
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

## 2. X2 — DONE 2026-08-29, and it FAILED. PR A does not open.

Measured on the real 477 512-passage index with a stock-upstream control arm:
warm p95 1 773,0 ms stopword-less against 392,3 ms on stock, so the deletion
costs 4,5× on p95 and 5,7× on the median, and the ~500 ms rule fires the other
way. Artifacts and the full reasoning are in
`bench/results/0025-x2-stopwordless/x2-verdict.json`; the decision and the two
further blockers are logged on tickets 0025 and 0014. **Do not open PR A from
the pre-filled form below** — it now needs df-pruning in the diff and a reworded
defect section.

Four things this step got wrong, recorded because they cost the session an hour
and any of them would bite a re-run:

- **`bench/query.py` could not time a query.** It recorded hits and peak RSS and
  nothing else, so the step would have completed, written a JSON, and left the
  p95 to be invented. Fixed: `--repeat` and a cold/warm/all latency block.
- **`$DATA650` is unreadable by v1.9.0**, and so is every other index under
  `/home/haduong/data/projets/zoteus-bench/`. They are pre-rename schema, where
  `passages` is itself the FTS5 virtual table; current code expects a plain
  `passages` with `passages_fts` beside it and dies on open with `virtual tables
  may not be indexed`. Rebuild first — 263,7 s and 1 755,6 MiB on doudou,
  reproducing the geometry exactly. The rebuilt index is at
  `/home/haduong/data/projets/zoteus-bench/x2-rebuild`, which also unblocks
  step 7's X4 arm without paying for it again.
- **The seed query list did not exist.** "In the PR handover" pointed at
  nothing. The population now lives in `bench/queries-x2.txt`, committed,
  because a p95 is a claim about a population.
- **`$DATA650` is misnamed**: 477k passages, not 650k. The PR body's `[650k]`
  placeholder wants the real count.

A control arm was not in this step and should have been. Measuring only the
treatment gives a number with nothing to attribute it to; the stock run is what
turned "slow" into "the deletion is why".

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

- **X4 confirmation on the real index** — the driver takes a db path, and it
  queries `passages_fts` by name, so it needs a NEW-schema index. Step 2's
  rebuild is one: `node $FTS5/bench/constrained_match.mjs
  /home/haduong/data/projets/zoteus-bench/x2-rebuild/search-index.sqlite
  > $FTS5/bench/results/0025-x4-constrained-match/real-477k.json`
  The synthetic verdict (ticket 0025) was never-build; this is its formality.
  Budget for it: the synthetic run reached 731 584 ms median at 100k rowids.

## Not in this runbook, deliberately

- **X5 / seg-1**: blocked on 0028 (segmenter unbuilt) and the zotero#6012 check.
- **I-2 filing**: happens after step 4, with trunk numbers per your ruling.
  I-1 is filed ([#26](https://github.com/oscardvs/zoteus/issues/26)); step 3's
  measured answer goes on its thread.

## The pre-filled PR forms

PR B is complete — press the green button as-is, once a slot is free. PR A is
HELD: X2 failed on 2026-08-29 and its body now carries a false claim as well as
an unfillable number (see step 2 and the PR A section).

**Neither can open today.** Both ratified in-flight slots are spent, on #27 and
#28, filed 2026-08-28. SYNC.md's status table has this; STATE.md's bullet saying
the slots are free predates those filings.

## PR B — cross-library wipe guard (ready NOW; no measurements pending)

Ticket 0016 (PR-3). Branch `cross-library-guard` (`61a0e38`, one commit atop
`bb414df`) is on the fork, validated on his gates: typecheck, lint, build
clean; 754 passed / 7 skipped (his 745 + 9 new). The repro on stock v1.9.0:
a group build silently replaces the personal index and reports done. Body
frames the guard as enforcing his own `startIndexBuild` doc-comment.

https://github.com/oscardvs/zoteus/compare/main...MinhHaDuong:zoteus:cross-library-guard?quick_pull=1&title=Refuse%20to%20build%20one%20library%27s%20index%20over%20another%27s&body=%23%23%20The%20defect%0A%0AThe%20index%20file%20is%20keyed%20by%20the%20data%20dir%2C%20never%20by%20the%20library%20%E2%80%94%20which%20is%20right%2C%20and%0Adocumented%20on%20%60startIndexBuild%60%20%E2%80%94%20but%20the%20build%20path%20clears%20the%20store%20before%20crawling%0A%28%60reset%28%29%60%20%E2%86%92%20%60clearStore%28%29%60%29%2C%20and%20nothing%20records%20which%20library%20the%20rows%20belong%20to.%20So%0A%60zotero_index%60%20pointed%20at%20a%20group%20library%20silently%20replaces%20the%20personal%20library%27s%20index%0A%28or%20any%20group%27s%29%2C%20reports%20%60done%60%2C%20and%20says%20nothing.%20Reproduced%20on%20v1.9.0%3A%20build%20the%0Apersonal%20library%2C%20then%20%60zotero_index%60%20with%20a%20group%27s%20%60library_id%60%20%E2%80%94%20the%20index%20now%20holds%0Athe%20group%27s%20items%2C%20the%20personal%20rows%20are%20gone%2C%20and%20no%20notice%20was%20ever%20shown.%0A%0A%23%23%20The%20fix%0A%0AThe%20guard%20on%20the%20documented%20single-library%20assumption%20%E2%80%94%20not%20a%20multi-library%20feature.%0A%0A-%20The%20index%20stamps%20the%20canonical%20identity%20of%20the%20library%20it%20holds%20%28%60user%60%2C%20or%0A%20%20%60group%3A%3Cid%3E%60%29%20with%20the%20first%20rows%20written%2C%20riding%20the%20existing%20seams%3A%20the%20%60meta%60%20table%0A%20%20on%20SQLite%2C%20the%20JSON%20snapshot%20on%20memory%2C%20%60library%60%20in%20status%20output.%0A-%20A%20build%20or%20update%20for%20a%20different%20library%20than%20stamped%20refuses%20up%20front%2C%20naming%20both%0A%20%20and%20the%20way%20forward%20%28a%20separate%20%60ZOTEUS_DATA_DIR%60%20per%20library%2C%20or%20delete%20the%20index%20file%0A%20%20to%20hand%20the%20data%20dir%20over%29%2C%20instead%20of%20reaching%20%60clearStore%28%29%60.%20The%20refusal%20is%20asserted%0A%20%20synchronously%20in%20%60startIndexBuild%60%2F%60startIndexUpdate%60%20%E2%80%94%20the%20job%20is%20fire-and-forget%2C%20so%0A%20%20a%20rejection%20inside%20it%20only%20reaches%20the%20log%20%E2%80%94%20and%20the%20engine%20asserts%20again%20before%0A%20%20anything%20is%20cleared.%0A-%20The%20personal%20library%20is%20one%20token%20with%20no%20id%3A%20the%20desktop%20app%20serves%20it%20as%20%60users%2F0%60%0A%20%20while%20the%20cloud%20names%20the%20real%20user%20id%2C%20and%20the%20%60startIndexBuild%60%20doc-comment%20promises%0A%20%20that%20seam%20never%20splits%20the%20index%20%E2%80%94%20so%20it%20must%20never%20split%20the%20stamp%20either.%20A%20rebuild%0A%20%20of%20the%20personal%20library%20across%20the%20local%2Fcloud%20seam%20is%20tested%20to%20never%20refuse.%0A-%20An%20index%20persisted%20before%20the%20stamp%20existed%20refuses%20nothing%3A%20there%20is%20no%20way%20to%20know%0A%20%20whose%20rows%20it%20holds%2C%20and%20refusing%20would%20strand%20every%20existing%20index%20behind%20an%20error%20no%0A%20%20rebuild%20could%20clear.%20Its%20first%20stamped%20build%20%28or%20completed%20update%29%20adopts%20it.%0A%0A%23%23%20Testing%0A%0ANine%20new%20cases%20in%20%60tests%2Ffeatures%2Fsearch-library-guard.test.ts%60%3A%20token%20normalization%0A%28both%20%60users%2F0%60%20and%20cloud-id%20addressing%20of%20the%20personal%20library%29%2C%20the%20engine%20guard%20on%0Abuild%20and%20update%2C%20stamp%20persistence%20across%20a%20JSON%20save%2Fload%20and%20an%20SQLite%20close%2Freopen%2C%0Athe%20synchronous%20tool-path%20refusal%20with%20the%20index%20left%20intact%2C%20and%20the%20local%2Fcloud%20seam%0Athat%20must%20never%20refuse.%20Run%20without%20the%20fix%2C%20the%20repro%20shows%20the%20silent%20erase.%20Full%20suite%0Aon%20this%20branch%3A%20754%20passed%20%2F%207%20skipped%3B%20typecheck%2C%20lint%20and%20build%20clean.

## PR A — stopwords follow-up: HELD, do not open (X2 failed, 2026-08-29)

The form below is kept only so the next revision can be written against it. As it
stands it makes two claims the measurement contradicts. The cost section asks for a
number that would read "1 773,0 ms" against a ~500 ms allowance the same sentence
cites. And the defect section's centerpiece — that `to be or not to be` tokenizes to
nothing at all — is false: `not` was never on the 29-word list, so stock returns
`["not"]` and answers the query as a one-term search, 20 unrelated hits in ~290 ms.
The real defect is worse than the claimed one and needs saying accurately, because
this is the sentence the maintainer will check first.


https://github.com/oscardvs/zoteus/compare/main...MinhHaDuong:zoteus:stopwords-follow-up?quick_pull=1&title=Delete%20the%20stoplist%3A%20no%20language%20loses%20its%20function%20words&body=%23%23%20The%20defect%0A%0AThe%20tokenizer%20carries%20a%2029-word%20English%20stoplist%2C%20which%20penalizes%20exactly%20one%0Alanguage%3A%20%22the%22%20is%20dropped%20while%20%22le%22%2C%20%22der%22%20and%20%22v%C3%A0%22%20pass.%20It%20is%20also%0Aasymmetric%20by%20construction%20%E2%80%94%20the%20FTS5%20document%20side%20%28%60unicode61%60%29%20has%20no%0Astoplist%2C%20so%20the%20index%20holds%20the%20very%20tokens%20the%20query%20side%20throws%20away.%20And%20it%0Aproduces%20queries%20that%20cannot%20say%20what%20they%20mean%3A%20%60to%20be%20or%20not%20to%20be%60%0Atokenizes%20to%20nothing%20at%20all%2C%20on%20both%20backends.%20bm25%20already%20down-weights%0Aubiquitous%20terms%2C%20which%20is%20the%20honest%20version%20of%20what%20a%20stoplist%20approximates.%0A%0A%23%23%20The%20fix%0A%0ADelete%20the%20list.%20%60tokenize%28%29%60%20keeps%20its%20Unicode%20token%20class%20and%20the%20one-char%0Adrop%2C%20nothing%20else.%20Existing%20indexes%20need%20no%20rebuild%3A%20terms%20are%20OR-ed%2C%20so%0Aevery%20query%20keeps%20matching%20through%20its%20content%20words%3B%20the%20SQLite%20index%20always%0Acontained%20the%20function%20words%20%28unicode61%20indexed%20them%20from%20day%20one%29%3B%20the%20JSON%0Abackend%20re-derives%20its%20postings%20from%20raw%20passage%20text%20on%20every%20load.%0A%0A%23%23%20The%20cost%2C%20measured%0A%0AThe%20OR-cost%20of%20high-frequency%20terms%20is%20the%20one%20thing%20to%20check%20before%20deleting%0Aa%20stoplist.%20Measured%20on%20a%20real%20%5B650k%5D-passage%20index%3A%20stopword-less%20OR-query%0Akeyword%20p95%20%3D%20%5BX%20ms%5D%20over%2020%20natural-language%20queries%20carrying%20function%20words.%0A%5BREPLACE%3A%20one%20sentence%20%E2%80%94%20comfortably%20under%20/%20near%20the%20~500%20ms%20where%0Acorpus-driven%20pruning%20of%20%3E50%25-document-frequency%20terms%20would%20be%20the%20follow-up.%5D%0A%0A%23%23%20Testing%0A%0A-%20%60tokenize%60%20cases%20updated%20to%20pin%20the%20new%20contract%20%28function%20words%20kept%20in%0A%20%20every%20language%2C%20one-char%20tokens%20still%20dropped%2C%20%22to%20be%20or%20not%20to%20be%22%20is%20a%0A%20%20searchable%20query%29%3B%20backend-parity%20case%20now%20asserts%20both%20backends%20answer%0A%20%20function-word%20queries%20identically.%0A-%20Full%20suite%3A%20727%20passed%20/%207%20skipped%3B%20typecheck%20and%20lint%20clean.

## Order if time is short

Step 2 is done and PR A is held, so the queue is: 4 (trunk numbers, the I-2
gate) → 3 (X6, for the #26 thread) → 6 → 5 → 7. PR B waits on a free slot
rather than on a measurement. Both slots are currently spent on #27 and #28 —
that is the ratified cap, working as intended.

Every remaining step that reads an existing index pays step 2's rebuild first;
every step that builds its own does not.
