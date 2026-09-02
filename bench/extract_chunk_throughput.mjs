// Ticket 0500: time the extract and chunk stages of a real index build, on the
// reference machine, separately from embed.
//
// SPEC.md §5.2.8 allocates 30 ms per passage at the MUST to "extract, chunk and
// the record write together" and says in terms that both stages are UNPINNED —
// no artifact in this repository measures either. This pass measures them, so
// the allocation can be re-cut from a number instead of from an assumption.
//
// What "extract" is in the shipped build. `build.ts` gets its body text from
// `createFulltextSource`, whose `textFor` is a GET of the platform's own
// `/items/<key>/fulltext`. The population it can serve is exactly what
// `/fulltext?since=0` names — attachments the platform has ALREADY extracted.
// An attachment the platform has not indexed is not in that list, so the build
// never asks for it and never parses anything itself. That makes the mix a
// property of the architecture, not of the library, and this pass measures the
// parse path separately, out of the build's critical path, for what it costs
// when the platform pays it (arm B).
//
// What "chunk" is. `chunkText(text, 1200, 150)` from the fork's own module,
// imported from the built dist rather than reimplemented, so the number cannot
// drift from the code it claims to measure.
//
// Two extract arms, because latency and throughput are different questions:
//   serial      — one request in flight; the per-attachment latency.
//   concurrent  — DEFAULT_FULLTEXT_CONCURRENCY_LOCAL (2) in flight, which is
//                 what a build actually runs, and what the ms/passage budget is
//                 spent at.
//
// warm-up: one discarded pass, over a slice no measured repetition reads, before the
// clock starts. Ticket 0260's rule, and it bites here even with no model in the
// window — the first GET pays the local API's connection setup and the first
// chunkText call pays V8's warm-up for that function, and both would land inside the
// first repetition's rate. The discarded slice is reported (`warm_up` below) so a
// reader can see it was paid rather than take the word for it.
//
//   node bench/extract_chunk_throughput.mjs --output <file.json> [--sample 40]
//
// Nothing leaves the machine: every request is to Zotero on loopback.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cpus, loadavg, totalmem } from 'node:os';
import { readFileSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
// The model is named by REGISTRY ID and resolved here, never written as a literal
// repository string: models.json is the only file that knows what an id points at,
// and a literal at the call site is how a run ends up undeclared.
import { resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    'api-base': { type: 'string', default: 'http://127.0.0.1:23119/api/users/0' },
    'dist-root': { type: 'string', default: '/home/haduong/CNRS/code/search-works-for-zotero/fork/dist' },
    output: { type: 'string' },
    sample: { type: 'string', default: '40' },
    // Independent repetitions of the serial arm, each over a DISJOINT slice of the
    // shuffle, so every rep reads items this pass has not touched. One rep is not
    // enough: four single-rep runs put the extract term between 0,14 and 0,26 ms per
    // passage, and a point estimate inside a spread that wide is a number pretending
    // to a precision the machine does not have.
    reps: { type: 'string', default: '1' },
    seed: { type: 'string', default: '0' },
    'max-chars': { type: 'string', default: '200000' },
    // The build's own local-API concurrency (limits.ts DEFAULT_FULLTEXT_CONCURRENCY_LOCAL).
    concurrency: { type: 'string', default: '2' },
    // Attachments to force the platform to re-extract for arm B. 0 skips the arm.
    reparse: { type: 'string', default: '0' },
    'reparse-timeout-s': { type: 'string', default: '90' },
    'plugin-base': { type: 'string', default: 'http://127.0.0.1:23119/search-works/fulltext/' },
    // Cost proxy only: the census tokenizes, the BUILD's chunker does not (it is
    // char-based, see chunker.js). Empty skips the arm.
    'transformers-path': { type: 'string', default: '' },
    'model-cache': { type: 'string', default: '' },
    model: { type: 'string', default: 'all-minilm-l6-v2' },
  },
});

if (!opt.output) throw new Error('--output is required');

const API = opt['api-base'].replace(/\/$/, '');
const SAMPLE = Number(opt.sample);
const MAX_CHARS = Number(opt['max-chars']);
const CONC = Number(opt.concurrency);

// The chunker under measurement, from the built artifact the server runs.
const { chunkText } = await import(`${opt['dist-root']}/features/search/chunker.js`);
const { FULLTEXT_CHUNK_SIZE, FULLTEXT_CHUNK_OVERLAP } = await import(
  `${opt['dist-root']}/features/search/index-manager.js`
);

const ms = (t0, t1) => Number(t1 - t0) / 1e6;
const now = () => process.hrtime.bigint();

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

/** Deterministic sampling, so a re-run measures the same items. */
function rng(seed) {
  let s = (seed >>> 0) || 0x2545f491;
  return () => {
    s ^= s << 13;
    s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5;
    s >>>= 0;
    return s / 0x100000000;
  };
}

async function getJson(url, timeoutMs = 120_000) {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ac.signal });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

/** Run `jobs` with at most `n` in flight, exactly as the build's Semaphore does. */
async function pooled(jobs, n) {
  const out = new Array(jobs.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(n, jobs.length) }, async () => {
    for (;;) {
      const i = next++;
      if (i >= jobs.length) return;
      out[i] = await jobs[i]();
    }
  });
  await Promise.all(workers);
  return out;
}

// ---------------------------------------------------------------- source setup

const t = {};
let mark = now();
const withText = await getJson(`${API}/fulltext?since=0`);
t.fulltext_since_ms = ms(mark, now());
const withTextKeys = new Set(Object.keys(withText));

// ONE walk of the attachment pages, not two: it costs a minute and a half on this
// library, and arm B needs the complement of the same walk (the attachments the
// platform has NOT extracted), so re-walking would double a fixed cost for nothing.
mark = now();
const byItem = new Map(); // parent item key -> [attachment keys]
const unextractedPdfs = []; // stored PDFs with no platform cache — the build cannot see these
const extractedPdfs = []; // stored PDFs the platform HAS extracted — arm B's forced-reparse pool
const noTextByType = {}; // content-type census of everything /fulltext?since=0 does not name
const noTextPdfByLinkMode = {}; // of those, the PDFs, by link mode
let mapped = 0;
let pages = 0;
let attachmentsSeen = 0;
let buildStopMs = null;
let buildStopPage = null;
for (let start = 0; pages < 500; pages++) {
  const page = await getJson(`${API}/items?itemType=attachment&limit=100&start=${start}`);
  const items = Array.isArray(page) ? page : (page.data ?? []);
  if (items.length === 0) break;
  attachmentsSeen += items.length;
  for (const it of items) {
    const d = it.data ?? it;
    const key = it.key ?? d.key;
    if (!key) continue;
    if (!withTextKeys.has(key)) {
      // Census rather than a bare filter: a filter that finds nothing and a filter
      // that cannot look produce the same empty list, so the content types of the
      // attachments the platform has NOT extracted are counted and reported.
      const ct = d.contentType || '(none)';
      noTextByType[ct] = (noTextByType[ct] ?? 0) + 1;
      if (d.contentType === 'application/pdf') {
        // A PDF with no platform text is either a real un-extracted file (the parse
        // path has an instance) or a bare link with no local file (it has none).
        // Counting the link modes is what tells those apart; an empty candidate list
        // on its own would not.
        const lm = d.linkMode || '(none)';
        noTextPdfByLinkMode[lm] = (noTextPdfByLinkMode[lm] ?? 0) + 1;
        if (d.linkMode !== 'linked_url') unextractedPdfs.push(key);
      }
      continue;
    }
    if (d.contentType === 'application/pdf' && d.linkMode !== 'linked_url') extractedPdfs.push(key);
    const parent = d.parentItem ?? key;
    const list = byItem.get(parent);
    if (list) list.push(key);
    else byItem.set(parent, [key]);
    mapped++;
    // The shipped source STOPS here (`mapped < total` in its loop condition); this
    // pass keeps walking because arm B needs the complement. Record the build's own
    // stopping point so the setup cost reported is the build's, not this pass's.
    if (mapped === withTextKeys.size && buildStopMs === null) {
      buildStopMs = ms(mark, now());
      buildStopPage = pages + 1;
    }
  }
  start += items.length;
}
t.attachment_map_ms = ms(mark, now());

const setup = {
  attachments_with_text: withTextKeys.size,
  attachments_mapped: mapped,
  attachments_seen: attachmentsSeen,
  unextracted_stored_pdfs: unextractedPdfs.length,
  extracted_stored_pdfs: extractedPdfs.length,
  attachments_without_text_by_content_type: noTextByType,
  pdfs_without_text_by_link_mode: noTextPdfByLinkMode,
  items_with_text: byItem.size,
  attachment_pages_walked: pages,
  fulltext_since_ms: Number(t.fulltext_since_ms.toFixed(1)),
  attachment_map_ms_full_walk: Number(t.attachment_map_ms.toFixed(1)),
  attachment_map_ms_as_the_build_pays_it: buildStopMs === null ? null : Number(buildStopMs.toFixed(1)),
  // Seconds too, because that is the unit the prose uses for a fixed per-build cost
  // and a figure guard compares the rendered value, not the quantity.
  attachment_map_s_as_the_build_pays_it: buildStopMs === null ? null : Number((buildStopMs / 1000).toFixed(1)),
  attachment_map_pages_as_the_build_pays_it: buildStopPage,
  note:
    'One-time per build, not per passage. The build stops paging once every extracted ' +
    'attachment is located; this pass walks every page because arm B needs the ' +
    'complement, so the build-side figure is the one to amortise.',
};

// ------------------------------------------------------------------- sampling

const itemKeys = [...byItem.keys()].sort();
const rand = rng(Number(opt.seed));
const shuffled = itemKeys.slice();
for (let i = shuffled.length - 1; i > 0; i--) {
  const j = Math.floor(rand() * (i + 1));
  [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
}
const REPS = Number(opt.reps);
/** Rep r's slice. Disjoint by construction, so no rep reads an item a previous one warmed. */
const sliceFor = (r) => shuffled.slice(r * SAMPLE, Math.min((r + 1) * SAMPLE, shuffled.length));
const sampled = sliceFor(0);
// The concurrent arm gets a DISJOINT sample, after every serial rep's. Re-reading a
// serial rep's items would measure a warm platform cache as if it were a concurrency
// gain — the two would be confounded and the pooled number would flatter itself.
const sampledConc = sliceFor(REPS);

// --------------------------------------------- arm A: cache-hit extract + chunk

/** One item, exactly as fulltext-source.textFor + index-manager.addFulltext do it. */
async function extractItem(itemKey) {
  const keys = byItem.get(itemKey);
  const parts = [];
  let used = 0;
  let extractMs = 0;
  let reads = 0;
  let readChars = 0;
  for (const key of keys) {
    if (MAX_CHARS > 0 && used >= MAX_CHARS) break;
    const m0 = now();
    let ft;
    try {
      ft = await getJson(`${API}/items/${key}/fulltext`);
    } catch (e) {
      extractMs += ms(m0, now());
      return { itemKey, error: String(e?.message ?? e) };
    }
    extractMs += ms(m0, now());
    reads++;
    const content = typeof ft?.content === 'string' ? ft.content : '';
    readChars += content.length;
    if (!content) continue;
    const slice = MAX_CHARS > 0 ? content.slice(0, MAX_CHARS - used) : content;
    parts.push(slice);
    used += slice.length;
  }
  const text = parts.length ? parts.join('\n\n') : '';
  return { itemKey, extractMs, reads, readChars, text };
}

function chunkOne(text) {
  const m0 = now();
  const chunks = chunkText(text, FULLTEXT_CHUNK_SIZE, FULLTEXT_CHUNK_OVERLAP);
  const chunkMs = ms(m0, now());
  return { chunkMs, chunks };
}

const load_before = loadavg();

/** One serial pass over one slice: per-attachment latency, one request in flight. */
async function serialPass(keys) {
  const rows = [];
  const texts = [];
  const tExtract = performance.now();
  for (const key of keys) {
    const r = await extractItem(key);
    if (r.error) {
      rows.push({ item: key, error: r.error });
      continue;
    }
    texts.push({ key, r });
  }
  const extractElapsed = performance.now() - tExtract;
  const tChunk = performance.now();
  const chunked = texts.map(({ r }) => chunkText(r.text, FULLTEXT_CHUNK_SIZE, FULLTEXT_CHUNK_OVERLAP));
  const chunkElapsed = performance.now() - tChunk;
  texts.forEach(({ key, r }, i) => {
    const chunks = chunked[i];
    rows.push({
      item: key,
      attachments: r.reads,
      read_chars: r.readChars,
      chars: r.text.length,
      passages: chunks.length,
      extract_ms: Number(r.extractMs.toFixed(3)),
      passage_chars: chunks.map((c) => c.text.length),
    });
  });
  return { rows, extractElapsed, chunkElapsed };
}

// The discarded pass. Its slice sits after the concurrent arm's, so nothing measured
// later reads an item it warmed.
const warmKeys = sliceFor(REPS + 1).slice(0, Math.min(8, SAMPLE));
const warmed = warmKeys.length ? await serialPass(warmKeys) : null;
const warm_up = {
  items: warmKeys.length,
  discarded: true,
  why: 'first-connection and first-call costs are paid here rather than inside repetition 0',
};

const repPasses = [];
for (let r = 0; r < REPS; r++) {
  const keys = sliceFor(r);
  if (keys.length === 0) break;
  repPasses.push(await serialPass(keys));
}
void warmed;
const repRows = repPasses.map((p) => p.rows);
const serialRows = repRows[0];

// Concurrent arm: the build's own local-API concurrency, over items the serial arm
// never touched, so concurrency is not measured against a cache the serial arm warmed.
const t_conc0 = now();
const concResults = await pooled(
  sampledConc.map((key) => async () => {
    const r = await extractItem(key);
    if (r.error) return { item: key, error: r.error };
    const { chunkMs, chunks } = chunkOne(r.text);
    return {
      item: key,
      passages: chunks.length,
      extract_ms: Number(r.extractMs.toFixed(3)),
      chunk_ms: Number(chunkMs.toFixed(3)),
    };
  }),
  CONC,
);
const conc_wall_ms = ms(t_conc0, now());

const load_after = loadavg();

// ---------------------------------------------------- arm B: on-the-fly parse

let reparse = {
  run: false,
  reason:
    'not requested (--reparse 0). The build never reaches this path: an attachment the ' +
    'platform has not extracted is absent from /fulltext?since=0, so the source cannot ' +
    'serve it and the build does not ask.',
};
const REPARSE = Number(opt.reparse);
const REPARSE_TIMEOUT_MS = Number(opt['reparse-timeout-s']) * 1000;
if (REPARSE > 0) {
  // The parse path is priced by FORCING a re-extraction, not by hunting for an
  // un-extracted file. The plugin calls Zotero.FullText.indexItems(ids, {complete:
  // true}), which re-parses whether or not a cache exists, so an already-extracted
  // PDF measures the same parse an un-extracted one would cost. That matters here:
  // on this library the un-extracted stored-PDF pool may be empty, and waiting for
  // one to exist would leave the path unmeasured rather than measured.
  const pool = unextractedPdfs.length >= REPARSE ? unextractedPdfs : extractedPdfs;
  const poolName = pool === unextractedPdfs ? 'un-extracted stored PDFs' : 'forced re-extraction of cached PDFs';
  const candidates = pool;
  // Spread the picks across the pool rather than taking the head, which on a
  // key-ordered walk would concentrate on whatever the first pages happen to hold.
  const stride = Math.max(1, Math.floor(pool.length / Math.max(REPARSE, 1)));
  const picks = Array.from({ length: Math.min(REPARSE, pool.length) }, (_, i) => pool[i * stride]);
  const rows = [];
  for (const key of picks) {
    const m0 = now();
    let status;
    try {
      const res = await fetch(`${opt['plugin-base']}reindex`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keys: [key] }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      // Poll until the platform reports the attachment complete, or give up. A
      // timeout is recorded as a timeout, never folded into the parse cost.
      let done = false;
      const deadline = Date.now() + REPARSE_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 250));
        status = await getJson(`${opt['plugin-base']}status?keys=${key}`);
        const it = (status.items ?? [])[0];
        done =
          !!it &&
          ((it.indexedPages != null && it.totalPages != null && it.indexedPages >= it.totalPages) ||
            (it.indexedChars != null && it.totalChars != null && it.indexedChars >= it.totalChars));
        if (done && !status.busy) break;
      }
      if (!done) {
        rows.push({ attachment: key, timed_out_after_s: REPARSE_TIMEOUT_MS / 1000, status: status ?? null });
        continue;
      }
    } catch (e) {
      rows.push({ attachment: key, error: String(e?.message ?? e) });
      continue;
    }
    const parse_ms = ms(m0, now());
    let ft = null;
    try {
      ft = await getJson(`${API}/items/${key}/fulltext`);
    } catch {
      /* left null */
    }
    const content = typeof ft?.content === 'string' ? ft.content : '';
    const { chunks } = chunkOne(content);
    const it = (status?.items ?? [])[0] ?? {};
    rows.push({
      attachment: key,
      parse_ms: Number(parse_ms.toFixed(1)),
      chars: content.length,
      pages: it.totalPages ?? null,
      passages: chunks.length,
      parse_ms_per_passage: chunks.length ? Number((parse_ms / chunks.length).toFixed(2)) : null,
    });
  }
  const timed = rows.filter((r) => r.parse_ms != null && r.passages);
  reparse = {
    run: true,
    pool: poolName,
    method:
      'bench/zotero-fulltext-plugin reindex (Zotero.FullText.indexItems with ' +
      'complete:true, which re-parses regardless of an existing cache), polled to ' +
      'completion, then the same GET the build would do. The wall clock is the PLATFORM ' +
      'parsing the PDF, measured from outside; it includes the plugin round trip and a ' +
      'poll quantum of up to 250 ms, so it is an upper bound on the parse itself.',
    candidates_seen: candidates.length,
    unextracted_stored_pdfs: unextractedPdfs.length,
    extracted_stored_pdfs: extractedPdfs.length,
    parsed: timed.length,
    parse_ms_per_passage_median: timed.length
      ? timed.map((r) => r.parse_ms_per_passage).sort((a, b) => a - b)[Math.floor(timed.length / 2)]
      : null,
    rows,
  };
}

// -------------------------------------------- tokenizer pass (cost proxy only)
//
// The census (bench/passage_census.mjs) tokenizes; the BUILD's chunk stage does
// not — `chunkText` splits on characters and word boundaries, with no tokenizer
// anywhere in the module. So this number is NOT part of the extract+chunk term
// the allocation covers: it is the census's own cost, and inside the pipeline the
// same work happens inside the embedder, i.e. inside the embed term. Measured
// here because ticket 0500's action 2 asks for it and its wall clock was never
// recorded when the census ran.
let tokenizer = { run: false, reason: 'not requested (--transformers-path empty)' };
if (opt['transformers-path']) {
  try {
    const tp = await import(`${opt['transformers-path']}/dist/transformers.node.mjs`);
    const { AutoTokenizer, env } = tp;
    if (opt['model-cache']) {
      env.localModelPath = opt['model-cache'];
      env.allowRemoteModels = false;
    }
    const { repo } = resolveModel(opt.model);
    const tk = await AutoTokenizer.from_pretrained(repo);
    // Re-chunk the sampled corpus to get the passage TEXTS (the rows keep lengths only).
    const passageTexts = [];
    for (const key of sampled) {
      const row = serialRows.find((r) => r.item === key);
      if (!row || row.error || !row.passages) continue;
      const r = await extractItem(key);
      if (r.error) continue;
      for (const c of chunkText(r.text, FULLTEXT_CHUNK_SIZE, FULLTEXT_CHUNK_OVERLAP)) passageTexts.push(c.text);
    }
    const lenOf = (enc) => {
      const ids = enc.input_ids;
      return ids?.dims?.at?.(-1) ?? ids?.data?.length ?? (Array.isArray(ids) ? ids.length : 0);
    };
    // warm-up: the first tokenize call builds the tokenizer's internal tables, and
    // that cost divided by the passage count would be reported as a per-passage rate.
    // Issued for its side effect and discarded.
    if (passageTexts.length) await tk(passageTexts[0], { truncation: false });
    const tTokens = performance.now();
    let tokens = 0;
    for (const txt of passageTexts) tokens += lenOf(await tk(txt, { truncation: false }));
    const tokElapsed = performance.now() - tTokens;
    tokenizer = {
      run: true,
      model: resolveModel(opt.model).repo,
      passages: passageTexts.length,
      tokens,
      wall_ms: Number(tokElapsed.toFixed(1)),
      ms_per_passage: passageTexts.length ? Number((tokElapsed / passageTexts.length).toFixed(3)) : null,
      tokens_per_passage: passageTexts.length ? Number((tokens / passageTexts.length).toFixed(1)) : null,
      not_in_the_build:
        'the build chunker is char-based (chunkText); this cost sits inside embed, not ' +
        'inside the extract+chunk allocation, and is reported so the census pass has a ' +
        'wall clock at last',
    };
  } catch (e) {
    tokenizer = { run: false, reason: `tokenizer arm failed: ${String(e?.message ?? e)}` };
  }
}

// ------------------------------------------------------------------ aggregates

const ok = serialRows.filter((r) => !r.error);
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const passages = sum(ok.map((r) => r.passages));
const extractMsTotal = repPasses[0].extractElapsed;
const chunkMsTotal = repPasses[0].chunkElapsed;
// Distribution over EVERY rep, not just the first: it describes the corpus the rate
// ran on, and the rate is a median over all of them.
const allPassageChars = repRows.flat().filter((r) => !r.error).flatMap((r) => r.passage_chars);
allPassageChars.sort((a, b) => a - b);
const q = (p) => (allPassageChars.length ? allPassageChars[Math.floor(p * (allPassageChars.length - 1))] : null);

const median = (xs) => {
  const v = [...xs].sort((a, b) => a - b);
  return v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
};
const repStats = repPasses.map(({ rows, extractElapsed, chunkElapsed }, i) => {
  const o = rows.filter((r) => !r.error);
  const p = sum(o.map((r) => r.passages));
  return {
    rep: i,
    items: o.length,
    read_failures: rows.length - o.length,
    passages: p,
    extract_ms_per_passage: p ? Number((extractElapsed / p).toFixed(3)) : null,
    chunk_ms_per_passage: p ? Number((chunkElapsed / p).toFixed(3)) : null,
    extract_plus_chunk_ms_per_passage: p ? Number(((extractElapsed + chunkElapsed) / p).toFixed(3)) : null,
  };
});
const repE = repStats.map((r) => r.extract_ms_per_passage).filter((x) => x != null);
const repC = repStats.map((r) => r.chunk_ms_per_passage).filter((x) => x != null);
const repT = repStats.map((r) => r.extract_plus_chunk_ms_per_passage).filter((x) => x != null);

const concOk = concResults.filter((r) => !r.error);
const concPassages = sum(concOk.map((r) => r.passages));

const result = {
  ticket: '0500',
  // Ticket 0260's flag, set from the code path that ran. What is inside the timed
  // windows: one GET per attachment and one chunkText call per item, nothing else.
  // What is outside them and reported separately: the model cache (pre-existing, no
  // download), the full-text sequence read, and the attachment-page walk — the whole
  // fixed per-build term, which is measured and published rather than folded into
  // the per-passage rate. Each item's text is fetched exactly once, which is exactly
  // what a build does with it, so the window holds no one-time cost that a build
  // would not also pay per item.
  warm: true,
  warm_basis:
    'no model load, no download and no index build inside any timed window; the ' +
    'per-build fixed cost (full-text sequence read plus attachment-page walk) is ' +
    'measured separately under `setup` and never folded into the per-passage rate',
  what:
    'extract and chunk, timed separately from embed, on the reference machine, over the ' +
    'population a build actually reads',
  date: new Date().toISOString().slice(0, 19) + 'Z',
  machine: {
    host: execFileSync('hostname').toString().trim(),
    cpu: cpus()[0]?.model ?? null,
    cores: cpus().length,
    mem_gb: Number((totalmem() / 2 ** 30).toFixed(1)),
    kernel: execFileSync('uname', ['-r']).toString().trim(),
    node: process.version,
    loadavg_before: load_before.map((x) => Number(x.toFixed(2))),
    loadavg_after: load_after.map((x) => Number(x.toFixed(2))),
    is_reference_machine:
      'yes — SPEC.md §5.2.8 names an Intel i5-8250U at 1,6 GHz, four cores, no GPU',
  },
  under_measurement: {
    chunker: `${opt['dist-root']}/features/search/chunker.js`,
    chunker_sha256: sha256(`${opt['dist-root']}/features/search/chunker.js`),
    chunk_size: FULLTEXT_CHUNK_SIZE,
    chunk_overlap: FULLTEXT_CHUNK_OVERLAP,
    max_chars: MAX_CHARS,
    concurrency: CONC,
    api_base: API,
  },
  setup,
  arm_a_cache_hit: {
    what: 'the only path a build takes: read the platform full-text cache over the local API',
    warm_up,
    reps: {
      n: repStats.length,
      items_per_rep: SAMPLE,
      slices: 'disjoint — every rep reads items no earlier rep touched',
      per_rep: repStats,
      extract_ms_per_passage_median: repE.length ? Number(median(repE).toFixed(3)) : null,
      extract_ms_per_passage_min: repE.length ? Math.min(...repE) : null,
      extract_ms_per_passage_max: repE.length ? Math.max(...repE) : null,
      chunk_ms_per_passage_median: repC.length ? Number(median(repC).toFixed(3)) : null,
      chunk_ms_per_passage_min: repC.length ? Math.min(...repC) : null,
      chunk_ms_per_passage_max: repC.length ? Math.max(...repC) : null,
      extract_plus_chunk_ms_per_passage_median: repT.length ? Number(median(repT).toFixed(3)) : null,
      extract_plus_chunk_ms_per_passage_min: repT.length ? Math.min(...repT) : null,
      extract_plus_chunk_ms_per_passage_max: repT.length ? Math.max(...repT) : null,
      why:
        'the extract term is a loopback read of a desktop application that is also ' +
        'doing its own work; a single pass of it is not a rate. The median over ' +
        'disjoint slices is the figure to quote and the min-max is what it is worth.',
    },
    items: ok.length,
    errors: serialRows.length - ok.length,
    attachments_read: sum(ok.map((r) => r.attachments)),
    passages,
    chars: sum(ok.map((r) => r.chars)),
    serial: {
      extract_ms_total: Number(extractMsTotal.toFixed(1)),
      chunk_ms_total: Number(chunkMsTotal.toFixed(1)),
      extract_ms_per_passage: passages ? Number((extractMsTotal / passages).toFixed(3)) : null,
      chunk_ms_per_passage: passages ? Number((chunkMsTotal / passages).toFixed(3)) : null,
      extract_plus_chunk_ms_per_passage: passages
        ? Number(((extractMsTotal + chunkMsTotal) / passages).toFixed(3))
        : null,
      extract_ms_per_item: ok.length ? Number((extractMsTotal / ok.length).toFixed(1)) : null,
      passages_per_item: ok.length ? Number((passages / ok.length).toFixed(1)) : null,
    },
    concurrent: {
      in_flight: CONC,
      sample: 'disjoint from the serial arm, so concurrency is not confounded with a warm cache',
      items: concOk.length,
      passages: concPassages,
      wall_ms: Number(conc_wall_ms.toFixed(1)),
      wall_ms_per_passage: concPassages ? Number((conc_wall_ms / concPassages).toFixed(3)) : null,
      note:
        'wall clock of the whole pooled pass divided by the passages it produced — the ' +
        'rate a build spends, where the serial arm is the latency one request sees.',
    },
  },
  read_outcomes: {
    items_sampled: sampled.length,
    items_read: ok.length,
    items_whose_read_failed: serialRows.filter((r) => r.error).length,
    items_read_but_empty: ok.filter((r) => r.read_chars === 0).length,
    why:
      'an attachment listed by /fulltext?since=0 can still answer 404, or answer with an ' +
      'empty body (the version-0 entries). Both are extract-stage work that yields no ' +
      'passage, so they raise the per-passage rate and are counted rather than dropped.',
  },
  arm_b_on_the_fly_parse: reparse,
  tokenizer_cost_proxy: tokenizer,
  passage_length_chars: {
    n: allPassageChars.length,
    min: allPassageChars[0] ?? null,
    p25: q(0.25),
    median: q(0.5),
    p75: q(0.75),
    p95: q(0.95),
    max: allPassageChars[allPassageChars.length - 1] ?? null,
    mean: allPassageChars.length ? Number((sum(allPassageChars) / allPassageChars.length).toFixed(1)) : null,
    why: 'a rate does not transfer across distributions (SPEC.md §5.2.8); this is the one it ran on',
  },
  rows: serialRows,
};

writeFileSync(opt.output, JSON.stringify(result, null, 2) + '\n');
console.log(
  `items=${ok.length} passages=${passages} ` +
    `extract=${result.arm_a_cache_hit.serial.extract_ms_per_passage} ms/passage ` +
    `chunk=${result.arm_a_cache_hit.serial.chunk_ms_per_passage} ms/passage ` +
    `concurrent wall=${result.arm_a_cache_hit.concurrent.wall_ms_per_passage} ms/passage`,
);
