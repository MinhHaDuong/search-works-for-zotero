# RUNBOOK — the workstation session that closes the current train segment

*Written 2026-08-27 at session close-out. Self-sunsetting: execute, hand the
JSONs to the next session, then DELETE this file — its durable state lives in
tickets 0014/0015/0024/0025 and SYNC.md, per the one-statement-per-fact rule.
Both PR branches are on the fork at `309204b`-base, validated green on
upstream's own gates; the tickets carry the full record.*

Placeholders: `$FTS5` = your zoteus-fts5 checkout, `$FORK` = your MinhHaDuong/zoteus
checkout, `$DATA650` = the data dir holding the big (477k-passage) index,
`$DATAREAL` = your normal Zoteus data dir. Every step ends with a JSON you either
commit to `bench/results/` or hand to me — I do the guard declarations, ticket
updates, and text injection.

## 0. Setup (once, ~5 min)

```bash
cd $FTS5 && git pull                                  # renamed drivers (0030) + new X drivers
cd $FORK && git fetch origin
git fetch https://github.com/oscardvs/zoteus main:upstream-main   # trunk v1.8.0+
```

---

## 1. PR B verification (~2 min) → opens PR B

```bash
cd $FORK && git checkout schema-read-before-write && npm ci && npm run build
D=$(mktemp -d)
cp "$DATAREAL/search-index.sqlite" "$D/"
sqlite3 "$D/search-index.sqlite" "UPDATE meta SET value='99' WHERE key='schemaVersion'"
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir "$D" \
  --backend sqlite > /tmp/verify-0015.json; grep -o 'storageNotice[^,}]*' /tmp/verify-0015.json
ls "$D"; sqlite3 "$D"/search-index.sqlite.incompatible-* \
  "SELECT value FROM meta WHERE key='schemaVersion'"   # must still say 99
```

PASS = server up; `storageNotice` names the sideline; old file intact at 99; fresh
file stamped 1. → Open PR B with the pre-filled URL, pasting your one-line result
into the bracketed verification line. FAIL = stop, tell me what you saw.

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

## 3. X6 — does extraction bump anything observable? (~20 min) → unblocks I-1

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
bumps-something → md5 signal suffices), and re-draft I-1 with the measured answer
in place of the rejected offer.

## 4. Trunk re-measurement at v1.8.0 (~30-45 min) → unblocks I-2

All on `upstream-main` (his code, not the fork), embeddings off:

```bash
cd $FORK && git checkout upstream-main && npm ci && npm run build
# 4a. build wall-time + peak RSS, both backends, real library:
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend sqlite --build > $FTS5/bench/results/trunk-1.8.0/build-sqlite.json
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend memory --build > $FTS5/bench/results/trunk-1.8.0/build-memory.json
# 4b. the wall, on trunk: uncapped fulltext build on the memory backend
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend memory --build --max-items 1000000 --max-chars 0 \
  > $FTS5/bench/results/trunk-1.8.0/build-memory-uncapped.json
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
- **I-1/I-2 filing**: happens after steps 3 and 4 respectively, with re-drafted
  texts — per your ruling: measured, not offered; trunk, not branch.

## The pre-filled PR forms

Each opens GitHub's form with title and body already filled; press the green
button (after the step that gates it, filling the REPLACE line in-form).

## PR B — schema read-before-write (open AFTER your real-index verification; fill the one REPLACE line in the form)

https://github.com/oscardvs/zoteus/compare/main...MinhHaDuong:zoteus:schema-read-before-write?quick_pull=1&title=A%20database%20from%20a%20different%20schema%20version%20is%20moved%20aside%2C%20never%20written%20into&body=%23%23%20The%20defect%0A%0A%60createSchema%60%20stamps%20%60SCHEMA_VERSION%60%20with%20%60INSERT%20OR%20REPLACE%60%20before%20anything%0Areads%20what%20the%20file%20already%20says%20%E2%80%94%20and%20nothing%20anywhere%20reads%20it%20back%3A%20the%20stamp%0Ais%20written%20and%20consulted%20by%20no%20one.%20So%20a%20database%20written%20by%20a%20newer%20build%20%28the%0Aordinary%20result%20of%20a%20downgrade%29%20is%20silently%20re-stamped%20with%20the%20older%20version%0Aand%20then%20misread.%20The%20comment%20on%20%60SCHEMA_VERSION%60%20promises%20%22an%20older%20file%20is%0Arebuilt%2C%20not%20patched%22%3B%20nothing%20enforces%20it.%20The%20failing%20test%20is%20the%0Areproduction%3A%20open%20a%20fixture%20stamped%20%60schemaVersion%3D99%60%20on%20stock%20and%20it%20comes%0Aback%20re-stamped%20to%201%2C%20its%20rows%20read%20as%20if%20they%20were%20this%20build%27s.%0A%0A%23%23%20The%20fix%0A%0A%60open%28%29%60%20now%20reads%20the%20stamp%20of%20an%20existing%20database%20before%20any%20DDL%20or%20write.%0AA%20file%20this%20build%20does%20not%20understand%20%E2%80%94%20a%20different%20version%2C%20an%20unparseable%0Astamp%2C%20or%20tables%20with%20no%20stamp%20at%20all%20%28an%20interrupted%20first%20creation%2C%20or%20not%20a%0AZoteus%20index%29%20%E2%80%94%20is%20moved%20aside%20to%20%60search-index.sqlite.incompatible-%3Ctimestamp%3E%60%2C%0Anever%20deleted%3A%20the%20moved%20file%20remains%20a%20complete%20database%2C%20readable%20by%20whichever%0Abuild%20stamped%20it.%20Its%20write-ahead%20sidecars%20travel%20with%20it%2C%20database%20last%2C%20for%0Athe%20reason%20%60sidecarsOf%60%20already%20states%20%E2%80%94%20a%20fresh%20database%20created%20beside%20an%0Aorphaned%20%60-wal%60%20is%20the%20one%20arrangement%20that%20can%20manufacture%20a%20corruption%20out%20of%0Athis%20protection.%20A%20fresh%20index%20is%20created%20in%20place%20and%20one%20notice%20lands%20on%0A%60storageNotice%60%2C%20the%20channel%20that%20already%20reports%20what%20opening%20the%20store%20did%20or%0Arefused%20to%20do.%0A%0ATwo%20deliberate%20narrownesses.%20A%20zero-byte%20file%20is%20a%20first%20open%2C%20not%20an%0Aincompatibility%3A%20SQLite%20treats%20it%20as%20a%20valid%20empty%20database%2C%20and%20a%20handle%0Aopened%20and%20dropped%20before%20any%20DDL%20leaves%20exactly%20that.%20And%20when%20the%0Aincompatible%20file%20can%20be%20read%20but%20not%20moved%20%E2%80%94%20locked%20by%20another%20process%2C%20or%20the%0Adirectory%20refuses%20the%20rename%20%E2%80%94%20the%20failure%20becomes%20%60SearchIndexCorruptError%60%3A%0Athe%20server%20survives%2C%20search%20refuses%20naming%20the%20file%2C%20and%20an%20explicit%0A%60action%3A%22build%22%60%20may%20clear%20it%2C%20with%20the%20consent%20that%20implies%20%28%2321%29.%0A%0A%23%23%20Testing%0A%0A-%20Seven%20new%20cases%20in%20%60tests/features/search-schema-version.test.ts%60%3A%20sideline%0A%20%20not%20re-stamp%3B%20the%20moved%20file%20stays%20a%20usable%20database%3B%20a%20stale%20log%20cannot%0A%20%20poison%20the%20fresh%20index%3B%20garbled%20and%20missing%20stamps%3B%20current-version%20and%0A%20%20empty%20files%20left%20exactly%20alone.%20Five%20of%20seven%20fail%20on%20stock%20v1.8.0.%0A-%20Full%20suite%3A%20733%20passed%20/%207%20skipped%3B%20%60npm%20run%20typecheck%60%20and%20%60npm%20run%20lint%60%0A%20%20clean.%0A-%20%5BVerified%20against%20a%20real%20library%20index%3A%20stamped%20a%20copy%20at%20version%2099%2C%0A%20%20watched%20the%20server%20start%2C%20sideline%20it%20intact%2C%20and%20open%20a%20fresh%20index%20%E2%80%94%0A%20%20REPLACE%20WITH%20YOUR%20ONE-LINE%20RESULT.%5D
--
## PR A — stopwords follow-up (open AFTER X2; fill the two REPLACE lines in the form)

https://github.com/oscardvs/zoteus/compare/main...MinhHaDuong:zoteus:stopwords-follow-up?quick_pull=1&title=Delete%20the%20stoplist%3A%20no%20language%20loses%20its%20function%20words&body=%23%23%20The%20defect%0A%0AThe%20tokenizer%20carries%20a%2029-word%20English%20stoplist%2C%20which%20penalizes%20exactly%20one%0Alanguage%3A%20%22the%22%20is%20dropped%20while%20%22le%22%2C%20%22der%22%20and%20%22v%C3%A0%22%20pass.%20It%20is%20also%0Aasymmetric%20by%20construction%20%E2%80%94%20the%20FTS5%20document%20side%20%28%60unicode61%60%29%20has%20no%0Astoplist%2C%20so%20the%20index%20holds%20the%20very%20tokens%20the%20query%20side%20throws%20away.%20And%20it%0Aproduces%20queries%20that%20cannot%20say%20what%20they%20mean%3A%20%60to%20be%20or%20not%20to%20be%60%0Atokenizes%20to%20nothing%20at%20all%2C%20on%20both%20backends.%20bm25%20already%20down-weights%0Aubiquitous%20terms%2C%20which%20is%20the%20honest%20version%20of%20what%20a%20stoplist%20approximates.%0A%0A%23%23%20The%20fix%0A%0ADelete%20the%20list.%20%60tokenize%28%29%60%20keeps%20its%20Unicode%20token%20class%20and%20the%20one-char%0Adrop%2C%20nothing%20else.%20Existing%20indexes%20need%20no%20rebuild%3A%20terms%20are%20OR-ed%2C%20so%0Aevery%20query%20keeps%20matching%20through%20its%20content%20words%3B%20the%20SQLite%20index%20always%0Acontained%20the%20function%20words%20%28unicode61%20indexed%20them%20from%20day%20one%29%3B%20the%20JSON%0Abackend%20re-derives%20its%20postings%20from%20raw%20passage%20text%20on%20every%20load.%0A%0A%23%23%20The%20cost%2C%20measured%0A%0AThe%20OR-cost%20of%20high-frequency%20terms%20is%20the%20one%20thing%20to%20check%20before%20deleting%0Aa%20stoplist.%20Measured%20on%20a%20real%20%5B650k%5D-passage%20index%3A%20stopword-less%20OR-query%0Akeyword%20p95%20%3D%20%5BX%20ms%5D%20over%2020%20natural-language%20queries%20carrying%20function%20words.%0A%5BREPLACE%3A%20one%20sentence%20%E2%80%94%20comfortably%20under%20/%20near%20the%20~500%20ms%20where%0Acorpus-driven%20pruning%20of%20%3E50%25-document-frequency%20terms%20would%20be%20the%20follow-up.%5D%0A%0A%23%23%20Testing%0A%0A-%20%60tokenize%60%20cases%20updated%20to%20pin%20the%20new%20contract%20%28function%20words%20kept%20in%0A%20%20every%20language%2C%20one-char%20tokens%20still%20dropped%2C%20%22to%20be%20or%20not%20to%20be%22%20is%20a%0A%20%20searchable%20query%29%3B%20backend-parity%20case%20now%20asserts%20both%20backends%20answer%0A%20%20function-word%20queries%20identically.%0A-%20Full%20suite%3A%20727%20passed%20/%207%20skipped%3B%20typecheck%20and%20lint%20clean.

## Order if time is short

1 (PR B, 2 min) → 2 (X2 + PR A, 10 min) → 4 (trunk numbers, the I-2 gate) →
3 (X6, the I-1 gate) → 6 → 5 → 7.
