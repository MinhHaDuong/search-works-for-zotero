#!/usr/bin/env node
/**
 * Does the droplist actually move snippets off the passage opening, on a real library?
 *
 * Ticket 0091. The snippet claim is the one the PR body makes that
 * `bench/query.py` cannot check — that driver records item keys and scores, never the
 * snippet text — so until this ran it rested on a unit fixture alone. `makeSnippet`
 * centres on the EARLIEST query term it finds, so a term the corpus is saturated with
 * sits at or near character 0 of nearly every passage and every snippet becomes the
 * passage's opening words. That is a claim about a real corpus and it is cheap to test
 * against one.
 *
 * Method: open the same index twice through the shipped code — once with its stored
 * droplist, once with the two meta rows taken out — and compare the snippet each query
 * returns for the SAME passage. `startsAtOpening` is the discriminator: whether the
 * snippet begins at character 0 of the passage (no leading ellipsis), which is exactly
 * what the pruning is supposed to stop.
 *
 * Usage:
 *   node verification/probes/snippet-droplist-probe.mjs \
 *     --dist <fork>/dist --data-dir <dir> --queries bench/queries-x2.txt --out <file.json>
 */
import { parseArgs } from 'node:util';
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const { values } = parseArgs({
  options: {
    dist: { type: 'string' },
    'data-dir': { type: 'string' },
    queries: { type: 'string' },
    out: { type: 'string' },
    limit: { type: 'string', default: '5' },
  },
});
for (const k of ['dist', 'data-dir', 'queries', 'out']) {
  if (!values[k]) {
    console.error(`missing --${k}`);
    process.exit(2);
  }
}

const factory = await import(pathToFileURL(join(values.dist, 'features/search/factory.js')).href);
const { DatabaseSync } = createRequire(import.meta.url)('node:sqlite');
const silent = { debug() {}, info() {}, warn() {}, error() {} };
const jsonPath = join(values['data-dir'], 'search-index.json');
const dbPath = factory.sqliteIndexPath(jsonPath);
const limit = Number(values.limit);

const queries = readFileSync(values.queries, 'utf8')
  .split('\n')
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith('#'));

/** Take the droplist out, or put a saved one back. Same file for both arms. */
function droplist(on, saved) {
  const db = new DatabaseSync(dbPath);
  if (on) {
    for (const [k, v] of Object.entries(saved)) {
      db.prepare('INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)').run(k, v);
    }
  } else {
    db.exec("DELETE FROM meta WHERE key IN ('droplist', 'droplistPassages')");
  }
  db.close();
}

function readDroplist() {
  const db = new DatabaseSync(dbPath);
  const rows = db.prepare("SELECT key, value FROM meta WHERE key LIKE 'droplist%'").all();
  db.close();
  return Object.fromEntries(rows.map((r) => [r.key, r.value]));
}

async function run() {
  const index = await factory.createSearchIndex({
    embedder: null, logger: silent, backend: 'sqlite', jsonPath,
  });
  const out = {};
  for (const q of queries) {
    const hits = await index.query(q, { limit, mode: 'keyword' });
    out[q] = hits.map((h) => ({ itemKey: h.itemKey, snippet: h.snippet }));
  }
  await index.close();
  return out;
}

const saved = readDroplist();
if (!saved.droplist) {
  console.error('this index carries no droplist — derive one first (bench/derive_droplist.mjs)');
  process.exit(2);
}

const withList = await run();
droplist(false);
const without = await run();
droplist(true, saved);

/** A snippet that begins at the passage's first character carries no leading ellipsis. */
const opens = (s) => !s.startsWith('…');

let pairs = 0;
let openedWithout = 0;
let openedWith = 0;
let moved = 0;
const examples = [];
for (const q of queries) {
  const a = new Map(withList[q].map((h) => [h.itemKey, h.snippet]));
  for (const h of without[q]) {
    const other = a.get(h.itemKey);
    if (other === undefined) continue; // different hit; not a snippet comparison
    pairs++;
    if (opens(h.snippet)) openedWithout++;
    if (opens(other)) openedWith++;
    if (opens(h.snippet) && !opens(other)) {
      moved++;
      if (examples.length < 6) {
        examples.push({ query: q, itemKey: h.itemKey, unpruned: h.snippet.slice(0, 110), pruned: other.slice(0, 110) });
      }
    }
  }
}

writeFileSync(values.out, `${JSON.stringify({
  probe: 'ticket 0091 — does the droplist move snippets off the passage opening, on a real library',
  data_dir: values['data-dir'],
  queries: queries.length,
  comparable_pairs: pairs,
  snippets_starting_at_the_passage_opening: { unpruned: openedWithout, pruned: openedWith },
  moved_off_the_opening_by_pruning: moved,
  examples,
  note: 'Only hits returned by BOTH arms are compared, since a snippet comparison needs the same '
      + 'passage on both sides. A snippet that begins at character 0 carries no leading ellipsis, '
      + 'which is what makes the discriminator mechanical rather than a judgement about readability.',
}, null, 2)}\n`);
console.error(`wrote ${values.out}: ${moved} of ${pairs} snippets moved off the opening`);
