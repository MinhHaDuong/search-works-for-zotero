# RUNBOOK — the workstation session that closes the current train segment

*Written 2026-08-27 at session close-out; trimmed 2026-08-28 after events
overtook it. Self-sunsetting: execute, hand the JSONs to the next session,
then DELETE this file — its durable state lives in tickets 0014/0016/0024/0025
and SYNC.md, per the one-statement-per-fact rule. Already executed and
removed from this file: step 1 (PR B became upstream #25, hardened in
review, merged 2026-08-28, shipped in v1.9.0 — ticket 0015 closed) and
I-1's filing (upstream #26, with X6's direction offered as a verification
protocol — step 3's measurement now feeds that thread instead of gating the
filing), and the X1 recall half, which was measured 2026-08-29 on the real
vectors and answered a stronger question than the step asked: 1-bit binary
codes plus an exact rerank, which subsume int8 (artifacts
`bench/results/0025-x1-recall/`, verdict and pool multiple on ticket 0025 and
in `spec/DECISIONS.md`). The remaining stopwords branch is on the fork at
`309204b`-base, validated green on upstream's own gates; the tickets carry the
full record.*

*A step here can rot in two ways, and both bit on 2026-08-29. It can be
**overtaken** — step 6 was already measured, under a better framing. Or its
premise can **move underneath it** while the command still runs: step 4 named
trunk as v1.9.0 after `UPSTREAM` had advanced to v1.10.0, and step 7's X4
command would have executed cleanly and returned a wrong number. Before running
any step, check its version claims against `UPSTREAM` and its artifact
directory against `bench/results/`.*

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
  `/home/haduong/data/projets/zoteus-bench/x2-rebuild`, which clears the
  *schema* obstacle in front of step 7's X4 arm without paying for it again.
  That step is still blocked, on the probe vocabulary rather than the schema —
  see step 7.
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

All on `upstream-main` (his code, not the fork), embeddings off.

**Re-read the baseline before running this.** When this step was written trunk
was v1.9.0 (`bb414df`) and the results dir it names, `trunk-1.9.0/`, was
current. `UPSTREAM` now records **v1.10.0 (`b132f2d`)**, whose search layer is
not a near-copy of v1.8.0 — it carries the two-stage ANN scan that ticket 0025
measured at 49,3x on the median. Measuring "trunk" into a directory named for
the version it is no longer is how a figure outlives its subject. Take the
version from `UPSTREAM` at run time and name the directory for it.

```bash
cd $FORK && git checkout upstream-main && npm ci && npm run build
# Name the results dir for the version actually under test, read from UPSTREAM.
TRUNK=$FTS5/bench/results/trunk-$(sed -n 's/^UPSTREAM_REVIEWED_VERSION=v//p' $FTS5/UPSTREAM)
mkdir -p "$TRUNK"
# 4a. build wall-time + peak RSS, both backends, real library:
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend sqlite --build > "$TRUNK/build-sqlite.json"
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend memory --build > "$TRUNK/build-memory.json"
# 4b. the wall, on trunk: uncapped fulltext build on the memory backend
python3 $FTS5/bench/run_build.py --server dist/index.js --data-dir $(mktemp -d) \
  --backend memory --build --max-items 1000000 --max-chars 0 \
  > "$TRUNK/build-memory-uncapped.json"
# 4c. warm query + resident memory: run_serve.py against each dir
```

→ Hand me the JSONs: I re-draft I-2 with trunk numbers only (his backend, his
tree), and the fork-prototype figures drop out of the text entirely.

## 5. X3a — monster RSS baseline on stock upstream (~15 min) → rss-gate fixture

Stock upstream, the uncapped 44,9 MB document's library, `run_serve`/`run_build`
with `--max-chars 0`; record VmHWM (reproduces 0011's 2 084,9 MiB class on
trunk). → feeds 0026's rss-gate fixture spec; commit JSON to
`bench/results/0025-x3a-monster-rss/`.

## 7. X4 confirmation on the real index — NOT RUNNABLE AS THIS STEP DESCRIBED IT

*(Step 6, the X1 recall half, is gone — measured 2026-08-29, see the header.
Numbers are not reused here: step 1 left the same gap when it was executed.)*

**Do not run the command that stood here.** It would have produced a wrong
number that no symptom distinguishes from a right one.

The step verified that `constrained_match.mjs` queries `passages_fts` by name,
so it needs a new-schema index, and stopped there. That check was necessary and
not sufficient: the probe-only path also reuses `probeQuery()`, whose terms are
the *synthetic* Zipf vocabulary (`"w5" OR "w1200" OR "w25000"`). Those terms are
not absent from a real library — OCR debris and variable names put a few in — so
nothing errors and no result is empty. The MATCH simply does almost no work.

Measured on the real 477 512-passage index at `x2-rebuild`, 2026-08-29, by
`verification/probes/x4_probe_vocabulary.py` → artifact
`bench/results/0025-x4-constrained-match/real-477k-probe-vocabulary.json`:

| arm | query | best of 3 |
|---|---|---|
| synthetic vocabulary | `"w5" OR "w1200" OR "w25000"` | 1,0 ms |
| real vocabulary (control) | `"of" OR "steam" OR "095"` | 379,3 ms |

The control is the point: it is drawn from the same three df bands the driver's
comment says the cost depends on, and it could have come out fast. It did not —
379x slower on the same index — so the synthetic arm's speed is the absence of
work, not the presence of performance. Since X4's rule is an *upper bound* on
latency, a vacuously fast arm does not merely mislead: it satisfies DESIGN §3's
150 ms allowance and **inverts X4's no-ship verdict**.

A synthetic vocabulary cannot carry a document-frequency spread into a real
corpus, and the spread is the whole cost model. The real index holds 639 888
distinct terms, of which 114 sit at df ≥ 10% (`of` at 84,96%), 8 195 between
0,1% and 1%, and 356 124 below 0,1%.

**Before this step can run**, `constrained_match.mjs` needs a probe-only path
that samples those three bands from `fts5vocab` on the index under test,
leaving the synthetic path byte-identical so `synthetic-477k.json` stays
reproducible. The probe above already does the sampling and can be read for it;
a full `fts5vocab(row)` scan costs 5,4 s warm here, paid once per run. X4-real
is unrun and stays unrun until then; ticket 0025 carries the record.

## Not in this runbook, deliberately

- **X5 / seg-1**: blocked on 0028 (segmenter unbuilt) and the zotero#6012 check.
- **I-2 filing**: happens after step 4, with trunk numbers per your ruling.
  I-1 is filed ([#26](https://github.com/oscardvs/zoteus/issues/26)); step 3's
  measured answer goes on its thread.

## The pre-filled PR forms

PR B is complete — press the green button as-is, once a slot is free. PR A is
HELD: X2 failed on 2026-08-29 and its body now carries a false claim as well as
an unfillable number (see step 2 and the PR A section).

**Check the slot before opening any of them, and check it in SYNC.md.** The
bound is GOVERNANCE.md's and what is live against it moves week to week; a count
restated here goes stale the day after it is written, which is what the sentence
that used to stand in this spot did — it still named #27 and #28 as the two
in-flight after both had merged. SYNC.md's status table is the live one.

**A form is body text, not a link to click.** The two URL-encoded compare links
below predate that ruling and are kept as they are rather than rewritten. New
forms carry the body in plain markdown with the command that files it: once the
author authorizes a filing, the agent files it, and the round-trip through a
browser paste is what put a stray indent and CRLF into #31's public body.

## PR B — cross-library wipe guard (ready NOW; no measurements pending)

Ticket 0016 (PR-3). Branch `cross-library-guard` (`61a0e38`, one commit atop
`bb414df`) is on the fork, validated on his gates: typecheck, lint, build
clean; 754 passed / 7 skipped (his 745 + 9 new). The repro on stock v1.9.0:
a group build silently replaces the personal index and reports done. Body
frames the guard as enforcing his own `startIndexBuild` doc-comment.

https://github.com/oscardvs/zoteus/compare/main...MinhHaDuong:zoteus:cross-library-guard?quick_pull=1&title=Refuse%20to%20build%20one%20library%27s%20index%20over%20another%27s&body=%23%23%20The%20defect%0A%0AThe%20index%20file%20is%20keyed%20by%20the%20data%20dir%2C%20never%20by%20the%20library%20%E2%80%94%20which%20is%20right%2C%20and%0Adocumented%20on%20%60startIndexBuild%60%20%E2%80%94%20but%20the%20build%20path%20clears%20the%20store%20before%20crawling%0A%28%60reset%28%29%60%20%E2%86%92%20%60clearStore%28%29%60%29%2C%20and%20nothing%20records%20which%20library%20the%20rows%20belong%20to.%20So%0A%60zotero_index%60%20pointed%20at%20a%20group%20library%20silently%20replaces%20the%20personal%20library%27s%20index%0A%28or%20any%20group%27s%29%2C%20reports%20%60done%60%2C%20and%20says%20nothing.%20Reproduced%20on%20v1.9.0%3A%20build%20the%0Apersonal%20library%2C%20then%20%60zotero_index%60%20with%20a%20group%27s%20%60library_id%60%20%E2%80%94%20the%20index%20now%20holds%0Athe%20group%27s%20items%2C%20the%20personal%20rows%20are%20gone%2C%20and%20no%20notice%20was%20ever%20shown.%0A%0A%23%23%20The%20fix%0A%0AThe%20guard%20on%20the%20documented%20single-library%20assumption%20%E2%80%94%20not%20a%20multi-library%20feature.%0A%0A-%20The%20index%20stamps%20the%20canonical%20identity%20of%20the%20library%20it%20holds%20%28%60user%60%2C%20or%0A%20%20%60group%3A%3Cid%3E%60%29%20with%20the%20first%20rows%20written%2C%20riding%20the%20existing%20seams%3A%20the%20%60meta%60%20table%0A%20%20on%20SQLite%2C%20the%20JSON%20snapshot%20on%20memory%2C%20%60library%60%20in%20status%20output.%0A-%20A%20build%20or%20update%20for%20a%20different%20library%20than%20stamped%20refuses%20up%20front%2C%20naming%20both%0A%20%20and%20the%20way%20forward%20%28a%20separate%20%60ZOTEUS_DATA_DIR%60%20per%20library%2C%20or%20delete%20the%20index%20file%0A%20%20to%20hand%20the%20data%20dir%20over%29%2C%20instead%20of%20reaching%20%60clearStore%28%29%60.%20The%20refusal%20is%20asserted%0A%20%20synchronously%20in%20%60startIndexBuild%60%2F%60startIndexUpdate%60%20%E2%80%94%20the%20job%20is%20fire-and-forget%2C%20so%0A%20%20a%20rejection%20inside%20it%20only%20reaches%20the%20log%20%E2%80%94%20and%20the%20engine%20asserts%20again%20before%0A%20%20anything%20is%20cleared.%0A-%20The%20personal%20library%20is%20one%20token%20with%20no%20id%3A%20the%20desktop%20app%20serves%20it%20as%20%60users%2F0%60%0A%20%20while%20the%20cloud%20names%20the%20real%20user%20id%2C%20and%20the%20%60startIndexBuild%60%20doc-comment%20promises%0A%20%20that%20seam%20never%20splits%20the%20index%20%E2%80%94%20so%20it%20must%20never%20split%20the%20stamp%20either.%20A%20rebuild%0A%20%20of%20the%20personal%20library%20across%20the%20local%2Fcloud%20seam%20is%20tested%20to%20never%20refuse.%0A-%20An%20index%20persisted%20before%20the%20stamp%20existed%20refuses%20nothing%3A%20there%20is%20no%20way%20to%20know%0A%20%20whose%20rows%20it%20holds%2C%20and%20refusing%20would%20strand%20every%20existing%20index%20behind%20an%20error%20no%0A%20%20rebuild%20could%20clear.%20Its%20first%20stamped%20build%20%28or%20completed%20update%29%20adopts%20it.%0A%0A%23%23%20Testing%0A%0ANine%20new%20cases%20in%20%60tests%2Ffeatures%2Fsearch-library-guard.test.ts%60%3A%20token%20normalization%0A%28both%20%60users%2F0%60%20and%20cloud-id%20addressing%20of%20the%20personal%20library%29%2C%20the%20engine%20guard%20on%0Abuild%20and%20update%2C%20stamp%20persistence%20across%20a%20JSON%20save%2Fload%20and%20an%20SQLite%20close%2Freopen%2C%0Athe%20synchronous%20tool-path%20refusal%20with%20the%20index%20left%20intact%2C%20and%20the%20local%2Fcloud%20seam%0Athat%20must%20never%20refuse.%20Run%20without%20the%20fix%2C%20the%20repro%20shows%20the%20silent%20erase.%20Full%20suite%0Aon%20this%20branch%3A%20754%20passed%20%2F%207%20skipped%3B%20typecheck%2C%20lint%20and%20build%20clean.

## PR A — stopwords follow-up: HELD, do not open (X2 failed, 2026-08-29)

The form below is kept only so the next revision can be written against it. As it
stands its cost section asks for a number that would read "1 773,0 ms" against the
~500 ms allowance the same sentence cites, which is the whole reason the PR is held.

The defect section's false claim has been CORRECTED, here and on the fork branch
(`ab89bbc`, 2026-08-29). It said `to be or not to be` tokenizes to nothing at all;
`not` was never on the 29-word list, so stock returns `["not"]` and answers the query
as a one-term search — 20 unrelated hits in ~290 ms. The corrected wording is longer
rather than softer: a query returning nothing tells the user something went wrong, and
one returning confident noise does not.


https://github.com/oscardvs/zoteus/compare/main...MinhHaDuong:zoteus:stopwords-follow-up?quick_pull=1&title=Delete%20the%20stoplist%3A%20no%20language%20loses%20its%20function%20words&body=%23%23%20The%20defect%0A%0AThe%20tokenizer%20carries%20a%2029-word%20English%20stoplist%2C%20which%20penalizes%20exactly%20one%0Alanguage%3A%20%22the%22%20is%20dropped%20while%20%22le%22%2C%20%22der%22%20and%20%22v%C3%A0%22%20pass.%20It%20is%20also%0Aasymmetric%20by%20construction%20%E2%80%94%20the%20FTS5%20document%20side%20%28%60unicode61%60%29%20has%20no%0Astoplist%2C%20so%20the%20index%20holds%20the%20very%20tokens%20the%20query%20side%20throws%20away.%20And%20it%0Aproduces%20queries%20that%20cannot%20say%20what%20they%20mean%2C%20in%20the%20way%20that%20is%0Ahardest%20to%20notice%3A%20%60to%20be%20or%20not%20to%20be%60%20comes%20through%20the%20list%20as%20%60not%60%0Aalone%2C%20the%20one%20word%20of%20it%20the%20list%20happens%20to%20omit%2C%20so%20the%20search%20becomes%20a%0Aone-term%20query%20for%20an%20incidental%20function%20word%20and%20answers%20it%20with%20twenty%0Aconfidently%20ranked%20passages%20about%20nothing%20in%20particular.%20bm25%20already%20down-weights%0Aubiquitous%20terms%2C%20which%20is%20the%20honest%20version%20of%20what%20a%20stoplist%20approximates.%0A%0A%23%23%20The%20fix%0A%0ADelete%20the%20list.%20%60tokenize%28%29%60%20keeps%20its%20Unicode%20token%20class%20and%20the%20one-char%0Adrop%2C%20nothing%20else.%20Existing%20indexes%20need%20no%20rebuild%3A%20terms%20are%20OR-ed%2C%20so%0Aevery%20query%20keeps%20matching%20through%20its%20content%20words%3B%20the%20SQLite%20index%20always%0Acontained%20the%20function%20words%20%28unicode61%20indexed%20them%20from%20day%20one%29%3B%20the%20JSON%0Abackend%20re-derives%20its%20postings%20from%20raw%20passage%20text%20on%20every%20load.%0A%0A%23%23%20The%20cost%2C%20measured%0A%0AThe%20OR-cost%20of%20high-frequency%20terms%20is%20the%20one%20thing%20to%20check%20before%20deleting%0Aa%20stoplist.%20Measured%20on%20a%20real%20%5B650k%5D-passage%20index%3A%20stopword-less%20OR-query%0Akeyword%20p95%20%3D%20%5BX%20ms%5D%20over%2020%20natural-language%20queries%20carrying%20function%20words.%0A%5BREPLACE%3A%20one%20sentence%20%E2%80%94%20comfortably%20under%20/%20near%20the%20~500%20ms%20where%0Acorpus-driven%20pruning%20of%20%3E50%25-document-frequency%20terms%20would%20be%20the%20follow-up.%5D%0A%0A%23%23%20Testing%0A%0A-%20%60tokenize%60%20cases%20updated%20to%20pin%20the%20new%20contract%20%28function%20words%20kept%20in%0A%20%20every%20language%2C%20one-char%20tokens%20still%20dropped%2C%20%22to%20be%20or%20not%20to%20be%22%20is%20a%0A%20%20searchable%20query%29%3B%20backend-parity%20case%20now%20asserts%20both%20backends%20answer%0A%20%20function-word%20queries%20identically.%0A-%20Full%20suite%3A%20727%20passed%20/%207%20skipped%3B%20typecheck%20and%20lint%20clean.

## PR C — WITHDRAWN, 2026-08-29. Not a knob; the ask is a registry

Ticket 0220's `ZOTEUS_EMBEDDING_DTYPE` is no longer offered upstream, and the
pre-filled form that stood here is deleted rather than kept, because a form is an
invitation to file and this must not be filed.

Its motivating premise was false. The ticket argued an asymmetry — the model has
a knob, precision does not — and the local path has neither: it hardcodes
`Xenova/all-MiniLM-L6-v2`, and `ZOTEUS_EMBEDDING_MODEL` reaches only the API
providers. Every axis the knob would have needed beside it turned out per-model
too: pooling, where four of six sweep candidates want `cls` against a hardcoded
`mean` (0421); the input template, where e5 without its prefixes measures worse
than an English model; and dtype availability itself, which is a bet on one
repo's filenames that some repos lose outright (0261). A precision knob shipped
alone would be a setting whose likeliest outcome is a wrong conclusion about a
good model, and it would have to be unwound by the registry that follows it.

What survives is evidence, not an offer:

- `verification/DEVICE-AUTO-0220.md` — that `device: 'auto'` fails on an ordinary
  CPU-only Linux desktop whichever way the package was installed. **This is not
  an upstream item and no issue is filed for it.** Nobody passes `auto`: zoteus
  passes no options at all, and transformers.js defaults to `['cpu']` on Node, so
  there is no defect in the maintainer's code and reporting one would be noise.
  Where the defect does live — transformers.js hard-failing instead of falling
  back — it is already reported as huggingface/transformers.js#1642, open since
  2026-04-14 and confirmed here still present at 4.2.0. The finding's value is
  internal: it is why this fork passes no device, and it is a standing risk to
  watch if transformers.js ever changes its Node default away from `['cpu']`.
- The measurements: on the default model, warm, q8 takes the load's resident cost
  from 143,7 MB to 69,1 MB and load time from 415,2 ms to 191,1 ms.
- Fork branch `embedding-dtype` (`0cdfe70`), left in place as a prototype nobody
  is offering. Its integration test — a refused precision must leave the index
  holding zero vectors rather than default-precision vectors under the wrong
  label — is the reusable part, and its lesson is already in 0261's schema: an
  entry's identity derives from its vector-affecting fields, never from its id.

The replacement ask is `tickets/0440`, an issue rather than a pull request, held
until 0262/0263 have a candidate table under it.

## Order if time is short

Step 2 is done, step 6 is done, PR A is held, and step 7 is blocked on a driver
fix rather than on machine time — so the queue is: 4 (trunk numbers, the I-2
gate) → 3 (X6, for the #26 thread) → 5. PR B waits on a free slot rather than on
a measurement. Both slots are currently spent on #27 and #28 — that is the
ratified cap, working as intended.

Every remaining step that reads an existing index pays step 2's rebuild first;
every step that builds its own does not.
