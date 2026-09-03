// Ticket 0577: peak RSS of ONE embedding-service process, in four cells.
//
// SPEC.md §5.2.9 says the embedding service has no ceiling at all, and names the
// one term nobody has measured on any machine: "the residency of a live batch —
// every sweep on disk priced batch size in latency, not RSS". A service ceiling
// is made of exactly that term, so it is measured here rather than derived.
//
//   1. one generation resident, at rest
//   2. one generation resident, live batch in flight
//   3. two generations resident, at rest
//   4. two generations resident, live batch in flight
//
// ONE PROCESS PER CELL. VmHWM is a monotone high-water mark, so measuring the
// cells in sequence inside one process would carry cell 2's batch peak into
// cell 3's "at rest" figure and make the 3->4 delta — the live-batch term this
// probe exists to isolate — unreadable. Each cell therefore gets a fresh child,
// and the driver only collects.
//
// Peak from /proc/self/status VmHWM, not from sampling: a sampler misses a spike
// between polls, the kernel high-water mark cannot.
//
//   node bench/service_ceiling_rss.mjs --drive --output <file.json>
//   node bench/service_ceiling_rss.mjs --cell 3 --corpus <file.json>   (child)
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { cpus, loadavg, totalmem } from 'node:os';
import { createHash } from 'node:crypto';
import { openSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
// Models are named by REGISTRY ID and resolved here — repository, pooling and
// normalize together. Pooling and normalize are properties of the model, not of this
// driver, and a literal at the call site is how a run silently measures the wrong
// geometry (tickets 0421 and 0486).
import { resolveModel } from './registry.mjs';

const { values: opt } = parseArgs({
  options: {
    drive: { type: 'boolean', default: false },
    cell: { type: 'string', default: '' },
    output: { type: 'string' },
    corpus: { type: 'string', default: '' },
    'transformers-path': {
      type: 'string',
      default: '/home/haduong/CNRS/projets/actifs/zoteus-fts5/fork/node_modules/@huggingface/transformers',
    },
    'cache-dir': { type: 'string', default: '' },
    // Generation A: the incumbent, exactly as the shipped provider loads it —
    // pipeline('feature-extraction', model) with no dtype, i.e. the package default.
    'model-a': { type: 'string', default: 'all-minilm-l6-v2' },
    'dtype-a': { type: 'string', default: '' },
    // Generation B: the multilingual candidate at its 8-bit rung.
    'model-b': { type: 'string', default: 'multilingual-e5-base' },
    'dtype-b': { type: 'string', default: 'q8' },
    // Batch size for the live-batch cells. Empty derives it from the ratified
    // ~1 s time quantum (DECISIONS.md 2026-09-01) on this machine.
    'batch-a': { type: 'string', default: '' },
    'batch-b': { type: 'string', default: '' },
    'quantum-ms': { type: 'string', default: '1000' },
    // Fresh processes per cell. One is not enough: the ONNX runtime's arena
    // allocation at session init varies by a couple of hundred MB between
    // processes, which on a single run made cell 4's peak read BELOW cell 3's and
    // the live-batch delta come out negative. A delta smaller than the spread is
    // not a delta, so every cell is repeated and reported with its spread.
    reps: { type: 'string', default: '5' },
    // Applied to EVERY cell, after its work and before the reading. Uniform by
    // construction: the first version settled only the at-rest cells, and those read
    // ~160 MB ABOVE the batch cells that had not settled — an idle process keeps
    // growing for a second or two after a model load, so a settle applied to some
    // cells and not others measures the settle instead of the batch.
    'settle-ms': { type: 'string', default: '2000' },
    // Execution provider for BOTH generations. Empty means "as the shipped provider
    // loads it": no device key at all when no dtype is asked for, `device: 'cpu'` beside
    // a dtype. `cuda` is the GPU second configuration of SPEC.md §5.2.8 — reported
    // BESIDE the reference machine and never as a substitute for it. The shipped
    // provider (fork/src/features/search/embeddings.ts) passes no device key at all, so
    // a non-empty value here is by construction NOT the shipped configuration.
    device: { type: 'string', default: '' },
    // Which arm of §5.2.8 this run is, declared by the operator and checkable by the
    // reader against the machine/device block the summary records beside it.
    arm: { type: 'string', default: '' },
    // Sample per-process VRAM through nvidia-smi while a cell runs. Off unless asked
    // for: the sampler is a child process, and spawning one from the measured process
    // is a perturbation of the very high-water mark being measured. It is started ONCE,
    // before any model load, when the process is still ~50 MB.
    'vram-sample': { type: 'boolean', default: false },
    warm: { type: 'boolean', default: false },
    'make-corpus': { type: 'string', default: '' },
    'dist-root': { type: 'string', default: '/home/haduong/CNRS/code/search-works-for-zotero/fork/dist' },
    'api-base': { type: 'string', default: 'http://127.0.0.1:23119/api/users/0' },
  },
});

const TP = `${opt['transformers-path']}/dist/transformers.node.mjs`;

function vmhwmKb() {
  for (const line of readFileSync('/proc/self/status', 'utf8').split('\n')) {
    if (line.startsWith('VmHWM:')) return Number(line.split(/\s+/)[1]);
  }
  throw new Error('/proc/self/status has no VmHWM line — cannot report peak RSS');
}
function vmrssKb() {
  for (const line of readFileSync('/proc/self/status', 'utf8').split('\n')) {
    if (line.startsWith('VmRSS:')) return Number(line.split(/\s+/)[1]);
  }
  throw new Error('/proc/self/status has no VmRSS line');
}
const mb = (kb) => Number((kb / 1024).toFixed(1));

async function loadModel(id, dtype, cacheDir, device = opt.device) {
  const { repo, pooling, normalize } = resolveModel(id);
  if (pooling === null || normalize === null) {
    throw new Error(`[registry] ${id} declares no pooling or no normalize; a run on it would guess the geometry`);
  }
  const transformers = await import(TP);
  const { pipeline, env } = transformers;
  if (cacheDir) env.cacheDir = cacheDir;
  const t0 = process.hrtime.bigint();
  // No dtype key at all when none is asked for: passing `undefined` is not the
  // same as omitting it in transformers.js, and the incumbent is measured exactly
  // as the shipped provider loads it.
  // With --device empty this is byte-for-byte the call the merged reference-machine run
  // made; a non-empty --device names the execution provider explicitly for both
  // generations, which is what a second configuration on a GPU host takes.
  const optsPipe = device ? (dtype ? { dtype, device } : { device }) : dtype ? { dtype, device: 'cpu' } : {};
  const extractor = await pipeline('feature-extraction', repo, optsPipe);
  const load_ms = Number(process.hrtime.bigint() - t0) / 1e6;
  return { extractor, load_ms, repo, pooling, normalize };
}

/** One embed call, the shape the shipped provider makes, at the model's own geometry. */
async function embedBatch(model, texts) {
  const t0 = process.hrtime.bigint();
  const tensor = await model.extractor(texts, { pooling: model.pooling, normalize: model.normalize });
  const wall = Number(process.hrtime.bigint() - t0) / 1e6;
  return { wall_ms: wall, dim: tensor.dims?.at(-1) ?? null };
}

/**
 * Derive the batch size the ratified ~1 s quantum implies on THIS device.
 *
 * DECISIONS.md 2026-09-01 ratifies a time quantum of about 1 s with the size
 * derived from it, so a fixed size taken from anywhere else would be measuring a
 * constant this project deliberately did not ratify. Doubling from 1 until the
 * batch takes at least the quantum, then reporting the size whose duration is
 * closest to it — the same multiplicative move the ruling describes, run open-loop
 * because one measurement is all a ceiling probe needs.
 */
async function deriveBatchSize(model, corpus, quantumMs) {
  const trail = [];
  let size = 1;
  let best = { size: 1, wall_ms: Infinity };
  for (let i = 0; i < 12; i++) {
    const texts = Array.from({ length: size }, (_, k) => corpus[k % corpus.length]);
    const { wall_ms } = await embedBatch(model, texts);
    trail.push({ size, wall_ms: Number(wall_ms.toFixed(1)) });
    if (Math.abs(wall_ms - quantumMs) < Math.abs(best.wall_ms - quantumMs)) best = { size, wall_ms };
    if (wall_ms >= quantumMs) break;
    size *= 2;
  }
  return { size: best.size, wall_ms: Number(best.wall_ms.toFixed(1)), trail };
}

/**
 * Start a per-process VRAM sampler and return its handle.
 *
 * `nvidia-smi --query-compute-apps` reports memory PER PROCESS, so the reading is
 * attributable to this cell and immune to whatever else already holds the card — a
 * whole-device figure would fold in a resident display server and be unreadable.
 */
function spawnDetachedSampler(logPath) {
  const fd = openSync(logPath, 'w');
  const p = spawn(
    'bash',
    ['-c', 'while :; do nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits; sleep 0.2; done'],
    { stdio: ['ignore', fd, 'ignore'], detached: true },
  );
  p.unref();
  return p;
}

/** Peak VRAM this process held, in MB, from the sampler's log. Null if it never appeared. */
function readSelfVramPeakMb(logPath, pid) {
  let peak = null;
  let text = '';
  try {
    text = readFileSync(logPath, 'utf8');
  } catch {
    return null;
  }
  for (const line of text.split('\n')) {
    const [p, m] = line.split(',').map((s) => s.trim());
    if (Number(p) !== pid) continue;
    const v = Number(m);
    if (Number.isFinite(v) && (peak === null || v > peak)) peak = v;
  }
  return peak;
}

// ------------------------------------------------------------------- the child

if (opt.cell) {
  const corpus = JSON.parse(readFileSync(opt.corpus, 'utf8'));
  const cell = opt.cell;
  const cacheDir = opt['cache-dir'] || undefined;
  const out = { cell, rss_baseline_mb: mb(vmrssKb()), device: opt.device || '(shipped default)' };

  // VRAM is a DIFFERENT quantity from RSS, not a second reading of it: under a GPU
  // provider the weights and the activations live in device memory, so the host
  // high-water mark below no longer covers them and the two are not comparable across
  // devices. Sampled here so that a GPU cell can report both, and started once, before
  // any load, so the sampler's own fork does not land in the peak it is watching.
  let vramLog = null;
  let sampler = null;
  if (opt['vram-sample']) {
    vramLog = `/tmp/service-ceiling-vram-${process.pid}.csv`;
    sampler = spawnDetachedSampler(vramLog);
  }
  /** Harvest the VRAM peak into `out` and tear the sampler down. Safe to call when no sampler runs. */
  const closeSampler = () => {
    if (!sampler) return;
    out.vram_peak_mb = readSelfVramPeakMb(vramLog, process.pid);
    out.vram_note =
      out.vram_peak_mb === null
        ? 'this process never appeared in nvidia-smi compute-apps: it held NO device memory, whatever device was requested'
        : 'device memory held by THIS process, peak over the cell; not comparable with the host RSS above, which no longer covers weights that moved to the device';
    try {
      process.kill(-sampler.pid);
    } catch {
      /* the sampler is detached; a failed kill is not a measurement error */
    }
    try {
      rmSync(vramLog);
    } catch {
      /* nothing depends on the log surviving the cell */
    }
    sampler = null;
  };

  const a = await loadModel(opt['model-a'], opt['dtype-a'], cacheDir);
  out.model_a = { repo: a.repo, dtype: opt['dtype-a'] || '(package default)', load_ms: Number(a.load_ms.toFixed(1)) };

  if (cell === 'warm') {
    // The warm pass, run BY the drive rather than trusted to have happened. It loads
    // every generation and throws one batch at each, and reports what that cost. The
    // timings are discarded — they exist to be witnessed, not to be quoted.
    const b0 = await loadModel(opt['model-b'], opt['dtype-b'], cacheDir);
    out.model_b = { repo: b0.repo, dtype: opt['dtype-b'], load_ms: Number(b0.load_ms.toFixed(1)) };
    const texts = Array.from({ length: 4 }, (_, k) => corpus[k % corpus.length]);
    out.discarded_batches = [
      { on: 'a', size: 4, ...(await embedBatch(a, texts)) },
      { on: 'b', size: 4, ...(await embedBatch(b0, texts)) },
    ];
    closeSampler();
    process.stdout.write('CELLJSON ' + JSON.stringify(out) + '\n');
    process.exit(0);
  }

  if (cell === 'derive') {
    // Derivation runs in a process of its own. It sweeps batch sizes upward, so its
    // own high-water mark is higher than the chosen size's — leaving it inside a
    // measured cell would publish the sweep's peak as the cell's.
    const da = await deriveBatchSize(a, corpus, Number(opt['quantum-ms']));
    const bb = await loadModel(opt['model-b'], opt['dtype-b'], cacheDir);
    const db = await deriveBatchSize(bb, corpus, Number(opt['quantum-ms']));
    out.derived = { quantum_ms: Number(opt['quantum-ms']), a: da, b: db };
    closeSampler();
    process.stdout.write('CELLJSON ' + JSON.stringify(out) + '\n');
    process.exit(0);
  }

  let b = null;
  if (cell === '3' || cell === '4' || cell === '4b') {
    b = await loadModel(opt['model-b'], opt['dtype-b'], cacheDir);
    out.model_b = { repo: b.repo, dtype: opt['dtype-b'], load_ms: Number(b.load_ms.toFixed(1)) };
  }

  const SETTLE = Number(opt['settle-ms']);
  if (cell === '1' || cell === '3') {
    // At rest: models loaded, nothing in flight.
    await new Promise((r) => setTimeout(r, SETTLE));
    out.settle_ms = SETTLE;
    out.rss_mb = mb(vmrssKb());
    out.peak_rss_mb = mb(vmhwmKb());
  } else {
    // Sizes are PINNED by the driver from a separate derivation process, so no
    // sweep runs inside a measured cell.
    if (!opt['batch-a']) throw new Error('a batch cell needs --batch-a (derive it first)');
    const sizeA = Number(opt['batch-a']);
    const sizeB = b ? Number(opt['batch-b']) : null;
    if (b && !opt['batch-b']) throw new Error('a two-generation batch cell needs --batch-b');
    const pre_batch_peak = vmhwmKb();
    const rest_peak = pre_batch_peak;
    let runs;
    if (cell === '2') {
      const texts = Array.from({ length: sizeA }, (_, k) => corpus[k % corpus.length]);
      runs = [{ on: 'a', size: sizeA, ...(await embedBatch(a, texts)) }];
    } else if (cell === '4') {
      // Realistic dual-embed window: the NEW generation carries the batch while the
      // old one stays resident to answer queries against the standing index.
      const texts = Array.from({ length: sizeB }, (_, k) => corpus[k % corpus.length]);
      runs = [{ on: 'b', size: sizeB, ...(await embedBatch(b, texts)) }];
    } else {
      // 4b: a batch in flight on EACH at once — the worse case, reported beside 4
      // rather than instead of it.
      const ta = Array.from({ length: sizeA }, (_, k) => corpus[k % corpus.length]);
      const tb = Array.from({ length: sizeB }, (_, k) => corpus[k % corpus.length]);
      const [ra, rb] = await Promise.all([embedBatch(a, ta), embedBatch(b, tb)]);
      runs = [{ on: 'a', size: sizeA, ...ra }, { on: 'b', size: sizeB, ...rb }];
    }
    out.batch = { size_a: sizeA, size_b: sizeB, runs };
    await new Promise((r) => setTimeout(r, SETTLE));
    out.settle_ms = SETTLE;
    out.rss_mb = mb(vmrssKb());
    out.peak_rss_mb = mb(vmhwmKb());
    out.peak_rss_before_batch_mb = mb(pre_batch_peak);
    out.peak_rss_at_rest_before_derivation_mb = mb(rest_peak);
  }
  // The RSS readings above are already taken, and VmHWM is monotone, so tearing the
  // sampler down here cannot move them.
  closeSampler();
  process.stdout.write('CELLJSON ' + JSON.stringify(out) + '\n');
  process.exit(0);
}

// -------------------------------------------------------------- corpus builder
//
// The batch cells must carry REAL passages: a batch of synthetic strings has the
// wrong token length, and token length is what decides the activation memory a
// live batch holds — the very term this probe exists to measure.
if (opt['make-corpus']) {
  const { chunkText } = await import(`${opt['dist-root']}/features/search/chunker.js`);
  const { FULLTEXT_CHUNK_SIZE, FULLTEXT_CHUNK_OVERLAP } = await import(
    `${opt['dist-root']}/features/search/index-manager.js`
  );
  const api = opt['api-base'].replace(/\/$/, '');
  const withText = await (await fetch(`${api}/fulltext?since=0`)).json();
  const keys = Object.keys(withText).sort();
  const want = Number(opt['make-corpus']);
  const passages = [];
  // Stride the key list rather than take its head, so the corpus is not one
  // document's prose repeated.
  const stride = Math.max(1, Math.floor(keys.length / 200));
  for (let i = 0; i < keys.length && passages.length < want; i += stride) {
    let ft;
    try {
      ft = await (await fetch(`${api}/items/${keys[i]}/fulltext`)).json();
    } catch {
      continue;
    }
    const content = typeof ft?.content === 'string' ? ft.content : '';
    if (!content) continue;
    for (const c of chunkText(content, FULLTEXT_CHUNK_SIZE, FULLTEXT_CHUNK_OVERLAP)) {
      passages.push(c.text);
      if (passages.length >= want) break;
    }
  }
  writeFileSync(opt.output, JSON.stringify(passages, null, 1) + '\n');
  const lens = passages.map((p) => p.length).sort((a, b) => a - b);
  console.log(
    `corpus n=${passages.length} chars median=${lens[Math.floor(lens.length / 2)]} min=${lens[0]} max=${lens.at(-1)}`,
  );
  process.exit(0);
}

// ------------------------------------------------------------------ the driver

if (opt.warm) {
  // Pull the weights down once, outside every measured cell, so no cell's peak
  // includes a download buffer.
  for (const [repo, dtype] of [
    [opt['model-a'], opt['dtype-a']],
    [opt['model-b'], opt['dtype-b']],
  ]) {
    const t0 = Date.now();
    await loadModel(repo, dtype, opt['cache-dir'] || undefined);
    console.log(`warmed ${repo} ${dtype || '(default)'} in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  }
  process.exit(0);
}

if (!opt.drive) throw new Error('pass --drive (or --cell N, or --warm)');
if (!opt.output) throw new Error('--output is required');
if (!opt.corpus) throw new Error('--corpus is required');

const self = new URL(import.meta.url).pathname;
const results = {};

/** Spawn one child cell and return its parsed row. */
function runCell(c, extra = []) {
  // `extra` goes LAST, after every driver-level flag, because parseArgs lets the last
  // occurrence win and `extra` is how a caller overrides the run's own settings — the
  // no-settle control arm overrides --settle-ms, the F1 cells override --model-a, and
  // the device controls override --device. Spread earlier, `extra` is silently
  // overridden instead of overriding: the first version of this line put it before the
  // --device push, and the device-control arm then ran on CUDA while reporting itself
  // as the shipped CPU call. It was caught only because a hand-run pair on the same
  // host had already established what the shipped call reports.
  const args = [self, '--cell', c, '--corpus', opt.corpus, '--transformers-path', opt['transformers-path'],
    '--model-a', opt['model-a'], '--model-b', opt['model-b'], '--dtype-b', opt['dtype-b'],
    '--quantum-ms', opt['quantum-ms'], '--settle-ms', opt['settle-ms']];
  if (opt['dtype-a']) args.push('--dtype-a', opt['dtype-a']);
  if (opt['cache-dir']) args.push('--cache-dir', opt['cache-dir']);
  if (opt.device) args.push('--device', opt.device);
  if (opt['vram-sample']) args.push('--vram-sample');
  args.push(...extra);
  const t0 = Date.now();
  const r = spawnSync('node', args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  const line = (r.stdout || '').split('\n').find((l) => l.startsWith('CELLJSON '));
  if (!line) return { cell: c, failed: true, status: r.status, stderr: (r.stderr || '').slice(-2000) };
  const row = JSON.parse(line.slice('CELLJSON '.length));
  row.wall_s = Number(((Date.now() - t0) / 1000).toFixed(1));
  return row;
}

/** Bytes on disk under a directory, or null when there is nothing to look at. */
function treeBytes(dir) {
  if (!dir) return null;
  try {
    return Number(execFileSync('du', ['-sb', dir], { encoding: 'utf8' }).split(/\s+/)[0]);
  } catch {
    return null;
  }
}

// The warm pass, performed HERE and witnessed, rather than asserted.
//
// `warm: true` used to be a literal in the summary below while warming was a separate
// optional flag on a separate invocation — so the artifact claimed a property of a run
// it had no way to observe, and deleting the flag from the command line changed nothing
// it said. That is worse than not knowing, because ticket 0260's whole point is that an
// artifact which cannot say is as bad as one that lies.
//
// So the drive warms, in a process of its own, and records what warming actually did:
// the load it performed, the discarded batches it threw away, and the bytes the model
// cache held before and after. `warm` below is set from whether that child succeeded,
// and a reader can check the claim against the witness instead of taking it.
//
// What the warm pass removes, and what it cannot. It removes the WEIGHT DOWNLOAD, which
// is paid once per machine and would otherwise sit inside whichever cell ran first.
// It does not remove the per-process model load or the first-batch graph initialisation:
// every cell is a fresh process by construction, so those are paid in every cell, and
// they are part of what a resident service costs rather than an artefact of the
// measurement. The peak/steady split and `rss_baseline_mb` are what keep them legible.
const cacheBytesBefore = treeBytes(opt['cache-dir']);
const warmRow = runCell('warm');
if (warmRow.failed) {
  throw new Error(`the warm pass failed, so no cell below could be called warm: ${warmRow.stderr}`);
}
const cacheBytesAfterWarm = treeBytes(opt['cache-dir']);

const derived = opt['batch-a'] && opt['batch-b']
  ? { derived: { quantum_ms: Number(opt['quantum-ms']), a: { size: Number(opt['batch-a']) }, b: { size: Number(opt['batch-b']) }, source: 'pinned on the command line' } }
  : runCell('derive');
if (derived.failed) throw new Error(`batch-size derivation failed: ${derived.stderr}`);
const BA = String(derived.derived.a.size);
const BB = String(derived.derived.b.size);
console.log(`derived batch sizes from the ~${opt['quantum-ms']} ms quantum: a=${BA} b=${BB}`);

const REPS = Number(opt.reps);
const median = (xs) => {
  const v = [...xs].sort((a, b) => a - b);
  return v.length % 2 ? v[(v.length - 1) / 2] : Number(((v[v.length / 2 - 1] + v[v.length / 2]) / 2).toFixed(1));
};
/**
 * Device memory across a cell's reps, or nothing at all when the arm did not sample it.
 *
 * A cell whose reps held no device memory reports 0 rather than null — that is a
 * measurement (the provider ran on the host) and must not read as "not sampled".
 */
const vramOf = (runs) => {
  const seen = runs.filter((r) => 'vram_peak_mb' in r);
  if (!seen.length) return {};
  const v = seen.map((r) => (r.vram_peak_mb === null ? 0 : r.vram_peak_mb));
  return {
    vram_peak_mb: median(v),
    vram_peak_mb_reps: v,
    vram_note: seen[0].vram_note,
  };
};

const cells = ['1', '2', '3', '4', '4b'];
for (const c of cells) {
  const runs = [];
  for (let i = 0; i < REPS; i++) {
    const r = runCell(c, ['--batch-a', BA, '--batch-b', BB]);
    if (r.failed) {
      console.error(`cell ${c} rep ${i} FAILED (status ${r.status})`);
      continue;
    }
    runs.push(r);
  }
  if (runs.length === 0) {
    results[c] = { cell: c, failed: true, reps: REPS };
    continue;
  }
  const peaks = runs.map((r) => r.peak_rss_mb);
  const steady = runs.map((r) => r.rss_mb);
  results[c] = {
    cell: c,
    reps: runs.length,
    peak_rss_mb: median(peaks),
    peak_rss_mb_min: Math.min(...peaks),
    peak_rss_mb_max: Math.max(...peaks),
    peak_rss_mb_spread: Number((Math.max(...peaks) - Math.min(...peaks)).toFixed(1)),
    peak_rss_mb_reps: peaks,
    steady_rss_mb: median(steady),
    steady_rss_mb_reps: steady,
    batch: runs[0].batch ?? null,
    model_a: runs[0].model_a,
    model_b: runs[0].model_b ?? null,
    wall_s: runs[0].wall_s,
    // The FIXED term, reported as its own number rather than folded into the cell: the
    // node process before a single weight is loaded. Everything above it is the model
    // plus, in the batch cells, the batch.
    baseline_rss_mb: median(runs.map((r) => r.rss_baseline_mb)),
    ...vramOf(runs),
  };
  console.log(
    `cell ${c}: peak median ${results[c].peak_rss_mb} MB ` +
      `(spread ${results[c].peak_rss_mb_spread}, n=${runs.length}), steady ${results[c].steady_rss_mb} MB`,
  );
}

// Device controls. Only meaningful when a device was named, and then they are not
// optional: `vram_peak_mb: null` is what this instrument reports both when a process
// held no device memory and when nvidia-smi could not be read, so the GPU cells above
// are worth nothing until the same detector has been shown to answer BOTH ways in the
// same session on the same host. Two arms, run as cell 1:
//   - the SHIPPED call, no device key at all, which is how the extension loads a model;
//   - an explicit `device: 'cpu'`, which is how the shipped provider loads one beside a dtype.
// Either arm coming back with a device-memory figure would mean the GPU cells prove
// nothing about the device; both coming back null while the cells above hold VRAM is
// what makes "the shipped runtime does not touch the GPU" a measurement and not a
// reading of the source.
const deviceControls = {};
if (opt['vram-sample'] && opt.device) {
  for (const [name, extra, what] of [
    ['shipped_call_no_device_key', ['--device', ''], 'the shipped call: pipeline() with no device key, as fork/src/features/search/embeddings.ts makes it'],
    ['explicit_cpu', ['--device', 'cpu'], 'an explicit device: cpu, as the shipped provider passes beside a dtype'],
  ]) {
    const r = runCell('1', ['--batch-a', BA, '--batch-b', BB, ...extra]);
    deviceControls[name] = r.failed
      ? { failed: true, what }
      : { what, peak_rss_mb: r.peak_rss_mb, vram_peak_mb: r.vram_peak_mb ?? null, device: r.device };
    console.log(`device control ${name}: RSS ${deviceControls[name].peak_rss_mb} MB, VRAM ${deviceControls[name].vram_peak_mb}`);
  }
}

// Control arm: the same cells with NO settle. Reported beside the cells rather than
// instead of them, so a reader can see how much of each figure is the settle and how
// much is the work — the question the first, non-uniform version got wrong.
const controls = {};
for (const c of ['1', '2', '3', '4']) {
  const runs = [];
  for (let i = 0; i < Math.min(3, REPS); i++) {
    const r = runCell(c, ['--batch-a', BA, '--batch-b', BB, '--settle-ms', '0']);
    if (!r.failed) runs.push(r);
  }
  if (!runs.length) continue;
  const peaks = runs.map((r) => r.peak_rss_mb);
  controls[c] = { reps: runs.length, peak_rss_mb: median(peaks), peak_rss_mb_reps: peaks };
  console.log(`control cell ${c} (settle 0): peak median ${controls[c].peak_rss_mb} MB`);
}

// F1's re-check needs a cell the four do not contain: the multilingual CANDIDATE
// alone, resident and under a live batch. Cell 2 carries the incumbent, and F1's
// collision was never about the incumbent. Same child, generation A swapped for B.
for (const [name, base] of [['1b', '1'], ['2b', '2']]) {
  const runs = [];
  for (let i = 0; i < REPS; i++) {
    const r = runCell(base, ['--batch-a', BB, '--batch-b', BB, '--model-a', opt['model-b'], '--dtype-a', opt['dtype-b']]);
    if (!r.failed) runs.push(r);
  }
  if (!runs.length) continue;
  const peaks = runs.map((r) => r.peak_rss_mb);
  results[name] = {
    cell: name,
    what: base === '1' ? 'the multilingual candidate alone, at rest' : 'the multilingual candidate alone, live batch in flight',
    reps: runs.length,
    peak_rss_mb: median(peaks),
    peak_rss_mb_min: Math.min(...peaks),
    peak_rss_mb_max: Math.max(...peaks),
    peak_rss_mb_spread: Number((Math.max(...peaks) - Math.min(...peaks)).toFixed(1)),
    peak_rss_mb_reps: peaks,
    batch: runs[0].batch ?? null,
    model_a: runs[0].model_a,
    baseline_rss_mb: median(runs.map((r) => r.rss_baseline_mb)),
    ...vramOf(runs),
  };
  console.log(`cell ${name}: peak median ${results[name].peak_rss_mb} MB (spread ${results[name].peak_rss_mb_spread})`);
}

const peak = (c) => results[c]?.peak_rss_mb ?? null;
const delta = (x, y) => (peak(x) != null && peak(y) != null ? Number((peak(x) - peak(y)).toFixed(1)) : null);

const summary = {
  ticket: '0577',
  // Ticket 0260's flag. The weights are downloaded by a separate `--warm` pass
  // before any measured process starts, so no download sits inside a cell. The
  // model LOAD does sit inside every cell's high-water mark, because residency is
  // the quantity being measured and a service that has not loaded its model is not
  // resident; the peak/steady split below is what lets a reader separate the load
  // transient from the settled figure.
  // Set from the code path that ran, not written as a literal: `warm` is true exactly
  // when this drive's own warm child succeeded, and the witness beside it is what a
  // reader checks the claim against.
  warm: !warmRow.failed && Array.isArray(warmRow.discarded_batches) && warmRow.discarded_batches.length === 2,
  warm_witness: {
    what:
      'the warm pass this drive performed before any measured cell, in a process of its ' +
      'own: both generations loaded and one batch thrown at each. Its timings are ' +
      'DISCARDED and recorded only as evidence that the warming happened.',
    loads: [
      { on: 'a', repo: warmRow.model_a?.repo ?? null, load_ms: warmRow.model_a?.load_ms ?? null },
      { on: 'b', repo: warmRow.model_b?.repo ?? null, load_ms: warmRow.model_b?.load_ms ?? null },
    ],
    discarded_batches: warmRow.discarded_batches ?? null,
    cache_dir: opt['cache-dir'] || null,
    cache_bytes_before: cacheBytesBefore,
    cache_bytes_after_warm: cacheBytesAfterWarm,
    cache_bytes_downloaded_by_warm:
      cacheBytesBefore != null && cacheBytesAfterWarm != null ? cacheBytesAfterWarm - cacheBytesBefore : null,
    cache_bytes_after_cells: treeBytes(opt['cache-dir']),
    removes:
      'the weight download, which is paid once per machine and would otherwise sit inside ' +
      'whichever cell ran first. cache_bytes_after_cells equal to cache_bytes_after_warm is ' +
      'the witness that no cell window held one.',
    does_not_remove:
      'the per-process model load and the first-batch graph initialisation. Every cell is a ' +
      'FRESH process by construction, so both are paid in every cell -- they are part of what ' +
      'a resident service costs, not an artefact of the measurement, and the peak/steady split ' +
      'plus rss_baseline_mb are what keep them legible.',
  },
  what: 'peak RSS of one embedding-service process, four cells, one process per cell',
  date: new Date().toISOString().slice(0, 19) + 'Z',
  machine: {
    host: execFileSync('hostname').toString().trim(),
    cpu: cpus()[0]?.model ?? null,
    cores: cpus().length,
    mem_gb: Number((totalmem() / 2 ** 30).toFixed(1)),
    node: process.version,
    loadavg: loadavg().map((x) => Number(x.toFixed(2))),
    // Declared by the operator, and checkable against the cpu/gpu/device facts recorded
    // beside it. SPEC.md §5.2.8 binds every ceiling to the reference machine and admits a
    // GPU host only as a second configuration reported beside it, never as a substitute.
    arm: opt.arm || 'binding — the reference machine of SPEC.md §5.2.8 (Intel i5-8250U, four cores, no GPU)',
    device_requested: opt.device || '(none — the shipped provider passes no device key)',
    gpu: (() => {
      try {
        return execFileSync('nvidia-smi', ['--query-gpu=index,name,memory.total,driver_version', '--format=csv,noheader'])
          .toString()
          .trim()
          .split('\n')
          .map((s) => s.trim());
      } catch {
        return null;
      }
    })(),
    onnxruntime_node: (() => {
      try {
        const p = `${opt['transformers-path']}/../../onnxruntime-node/package.json`;
        return JSON.parse(readFileSync(p, 'utf8')).version;
      } catch {
        return null;
      }
    })(),
    transformers_js: (() => {
      try {
        return JSON.parse(readFileSync(`${opt['transformers-path']}/package.json`, 'utf8')).version;
      } catch {
        return null;
      }
    })(),
    // What it took to reach the device, recorded because it is the difference between
    // the shipped configuration and this one. onnxruntime-node ships the CUDA provider
    // library but not its cuDNN dependency, so on a host without cuDNN 9 the provider
    // refuses to load and the run is a CPU run wearing a GPU label — ticket 0481's
    // defect exactly. Both are recorded so a reader can tell which happened.
    ld_library_path: process.env.LD_LIBRARY_PATH ?? null,
    cuda_visible_devices: process.env.CUDA_VISIBLE_DEVICES ?? null,
  },
  // The corpus itself is NOT committed: it is 256 passages of the author's own
  // library. Its shape is, because batch residency depends on token length and a
  // reader cannot check the cells against a corpus they cannot see.
  corpus: (() => {
    const c = JSON.parse(readFileSync(opt.corpus, 'utf8'));
    const lens = c.map((x) => x.length).sort((a, b) => a - b);
    return {
      path: opt.corpus,
      sha256: createHash('sha256').update(readFileSync(opt.corpus)).digest('hex'),
      n: c.length,
      chars_min: lens[0],
      chars_median: lens[Math.floor(lens.length / 2)],
      chars_max: lens.at(-1),
      provenance: 'drawn from the live library by this script\'s --make-corpus mode, striding the full-text sequence so it is not one document repeated',
    };
  })(),
  generations: {
    a: {
      repo: resolveModel(opt['model-a']).repo,
      dtype: opt['dtype-a'] || '(package default, as the shipped provider loads it)',
      device: opt.device || '(no device key, as the shipped provider loads it)',
    },
    b: {
      repo: resolveModel(opt['model-b']).repo,
      dtype: opt['dtype-b'],
      device: opt.device || 'cpu (explicit, as the shipped provider does beside a dtype)',
    },
  },
  batch_size_derivation: derived.derived,
  cells: results,
  settle_ms: Number(opt['settle-ms']),
  controls_no_settle: controls,
  device_controls: deviceControls,
  deltas_mb: {
    live_batch_one_generation: delta('2', '1'),
    second_generation_at_rest: delta('3', '1'),
    live_batch_two_generations: delta('4', '3'),
    dual_embed_window_price: delta('4', '2'),
    both_batches_in_flight: delta('4b', '3'),
    live_batch_candidate_alone: delta('2b', '1b'),
  },
  // Fixed against marginal, kept apart on purpose. A peak RSS is not a per-unit rate, so
  // the amortisation error that inflates a rate measured on a small denominator does not
  // reach these figures — but the same discipline does: the terms a cell is MADE of are
  // named here rather than left for a reader to infer from one number.
  terms_mb: {
    fixed_process_baseline: results['1']?.baseline_rss_mb ?? null,
    fixed_one_generation_resident: peak('1'),
    fixed_second_generation_resident: delta('3', '1'),
    marginal_live_batch_one_generation: delta('2', '1'),
    marginal_live_batch_two_generations: delta('4', '3'),
    note:
      'a peak, never a rate: nothing here is an elapsed time divided by a count. The batch ' +
      'terms are marginal at THIS run\'s derived batch size, which is a property of the ' +
      'device and not of the models -- read them beside batch_size_derivation, never alone.',
  },
  ceiling_candidate_mb: peak('4'),
  reps_per_cell: REPS,
  spread_caveat:
    'every delta below must be read against the per-cell spread in the same table: a ' +
    'delta smaller than the spread of the cells it subtracts is not a measured delta. ' +
    'One rep per cell put cell 4 BELOW cell 3 and made the live-batch term negative, ' +
    'which is what the reps are here to prevent.',
  c3_reference_mb: 750,
  why_one_process_per_cell:
    'VmHWM is monotone, so cells measured in sequence in one process would each inherit ' +
    'the previous cell peak and the 3->4 delta would be unreadable.',
};

writeFileSync(opt.output, JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary.deltas_mb));
