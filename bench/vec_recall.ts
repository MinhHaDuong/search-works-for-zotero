/**
 * Recall of the two-stage vector query against the exact float32 ranking, per pool size.
 *
 * Ticket 0008's acceptance criterion is recall, not latency: a 13x speedup that quietly
 * drops relevant passages is a regression wearing a benchmark's clothes. So this measures
 * the thing that can regress, and it measures it through `Fts5PassageStore.vectorSearch`
 * itself rather than through a re-implementation, because a bench that mirrors the SQL is
 * a bench that can agree with a broken store.
 *
 *   npx tsx bench/vec_recall.ts [--n 100000] [--probes 100] [--dim 384] [--topk 30]
 *
 * Writes and deletes a database under $TMPDIR. Needs Node >= 22.5 and sqlite-vec.
 *
 * Two fixtures, because the answer depends on the geometry and only one of them is honest
 * about the worst case:
 *
 *  - `uniform` — independent random unit vectors. In 384 dimensions these are almost
 *    exactly orthogonal, so the whole corpus sits in a thin shell of cosines around zero
 *    and the true top-30 are separated by hundredths. Resolving that from one sign bit per
 *    dimension is the hardest thing you can ask of a binary code. This is the conservative
 *    number.
 *  - `clustered` — a mixture around random centroids, which is the shape a sentence
 *    embedder actually produces: neighbours are genuinely near and the gap between the
 *    top-k and the rest is real. This is the number the library will see.
 *
 * What neither fixture is: real embeddings of real passages. Running the model over
 * 100 000 passages is a different measurement on a different machine, and the honest
 * summary is that the clustered fixture brackets it from the easy side and the uniform one
 * from the hard side.
 */
import { existsSync, unlinkSync, statSync } from 'node:fs';
import type { DatabaseSync } from 'node:sqlite';
import { Fts5PassageStore, loadSqlite, defaultVecLoader } from '../src/features/search/fts5-store.js';

interface Options {
  n: number;
  probes: number;
  dim: number;
  topK: number;
}

function parseArgs(argv: string[]): Options {
  const opts: Options = { n: 100_000, probes: 100, dim: 384, topK: 30 };
  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    const value = Number(argv[i + 1]);
    if (!Number.isFinite(value)) continue;
    if (flag === '--n') opts.n = value;
    else if (flag === '--probes') opts.probes = value;
    else if (flag === '--dim') opts.dim = value;
    else if (flag === '--topk') opts.topK = value;
  }
  return opts;
}

/** Seeded, so a rerun of a surprising number lands on the same corpus. */
function makeRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff - 0.5;
  };
}

function normalize(v: number[]): number[] {
  let n = 0;
  for (const x of v) n += x * x;
  n = Math.sqrt(n) || 1;
  return v.map((x) => x / n);
}

type Fixture = (i: number) => number[];
type FixtureKind = 'uniform' | 'clustered';

function uniformFixture(dim: number, rnd: () => number): Fixture {
  return () => normalize(Array.from({ length: dim }, rnd));
}

/** Cosine a corpus member keeps with its own centroid. See clusteredFixture. */
const INTRA_CLUSTER_COSINE = 0.8;

/**
 * A mixture of 200 centroids, each member at a stated cosine from its centroid.
 *
 * The noise scale is derived rather than picked, because picking it is how the first
 * version of this bench went wrong: an offset of `0.5 * rnd()` per component has norm
 * `0.5 * sqrt(dim/12)`, which at 384 dimensions is 2,8 against a unit centroid — the noise
 * swamped the structure and the "clustered" fixture measured the same near-orthogonal
 * shell as the uniform one. A vector at cosine c from its centroid needs an orthogonal
 * offset of norm `sqrt(1/c^2 - 1)`, so that is what is solved for here.
 *
 * 0,8 is the shape a sentence embedder produces: a passage's genuine neighbours sit high,
 * the rest of the corpus sits near zero, and the gap between them is large compared with
 * the resolution a binary code can offer.
 */
function clusteredFixture(dim: number, rnd: () => number): Fixture {
  const centroids = Array.from({ length: 200 }, () => normalize(Array.from({ length: dim }, rnd)));
  // rnd() is uniform on [-1/2, 1/2], so a dim-long draw has expected norm sqrt(dim/12).
  const scale = Math.sqrt(1 / INTRA_CLUSTER_COSINE ** 2 - 1) / Math.sqrt(dim / 12);
  return (i: number) => {
    const c = centroids[i % centroids.length]!;
    return normalize(c.map((x) => x + scale * rnd()));
  };
}

/**
 * Build a fixture of the named kind. Called twice per run with different seeds — once for
 * the corpus, once for the probes — so the probes share the corpus's geometry without
 * being members of it.
 */
function fixtureFor(kind: FixtureKind, dim: number, rnd: () => number): Fixture {
  return kind === 'uniform' ? uniformFixture(dim, rnd) : clusteredFixture(dim, rnd);
}

function tempPath(tag: string): string {
  return `${process.env.TMPDIR ?? '/tmp'}/zoteus-recall-${tag}-${process.pid}.sqlite`;
}

function unlinkDb(path: string): void {
  for (const f of [path, `${path}-wal`, `${path}-shm`]) if (existsSync(f)) unlinkSync(f);
}

/** Build the corpus once; every pool size below reads the same file. */
function build(path: string, opts: Options, fixture: Fixture): void {
  unlinkDb(path);
  const store = new Fts5PassageStore(path);
  store.beginBatch();
  for (let i = 0; i < opts.n; i++) {
    const id = `P#${i}`;
    store.add({ id, itemKey: `I${i}`, title: 'passage', text: `synthetic passage ${i}` });
    store.setVector(id, fixture(i));
    if (i % 5000 === 4999) {
      store.commitBatch();
      store.beginBatch();
    }
  }
  store.commitBatch();
  store.close();
}

/** One ranked hit, on the descending-best convention the store uses. */
interface Hit {
  id: string;
  score: number;
}

interface Reference {
  db: DatabaseSync;
  /** The exact float32 ranking: the ground truth every recall figure below is against. */
  exact(probe: Uint8Array, k: number): Hit[];
  /** The binary ranking taken at face value, no rerank — the float32-optional question. */
  binaryOnly(probe: Uint8Array, k: number): string[];
  /** The true cosine of one passage, by id, for scoring a list that arrived without scores. */
  scoreOf(probe: Uint8Array, id: string): number;
}

/**
 * The two reference rankings, on a raw connection.
 *
 * `exact` is the statement this store issued before ticket 0008, verbatim, so "recall
 * against the current exact ranking" means what it says. It has to be run here rather than
 * through the store because the store no longer takes that path once a binary column
 * exists, which is the change under measurement.
 */
function references(path: string): Reference {
  const { DatabaseSync: Ctor } = loadSqlite();
  const db = new Ctor(path, { allowExtension: true });
  db.enableLoadExtension(true);
  defaultVecLoader(db);
  db.enableLoadExtension(false);
  const stmtExact = db.prepare(
    'SELECT m.id AS id, 1.0 - v.distance AS score' +
      ' FROM passage_vectors v JOIN passage_meta m ON m.rowid = v.rowid' +
      ' WHERE v.embedding MATCH ? AND v.k = ? ORDER BY v.distance',
  );
  const stmtBinary = db.prepare(
    'SELECT m.id AS id FROM passage_vectors_bin v JOIN passage_meta m ON m.rowid = v.rowid' +
      ' WHERE v.embedding MATCH vec_quantize_binary(?) AND v.k = ? ORDER BY v.distance',
  );
  const stmtScore = db.prepare(
    'SELECT 1.0 - vec_distance_cosine(v.embedding, ?) AS score FROM passage_vectors v' +
      ' JOIN passage_meta m ON m.rowid = v.rowid WHERE m.id = ?',
  );
  return {
    db,
    exact: (probe, k) => (stmtExact.all(probe, BigInt(k)) as unknown as Hit[]).filter((h) => h.score > 0),
    binaryOnly: (probe, k) =>
      (stmtBinary.all(probe, BigInt(k)) as unknown as Array<{ id: string }>).map((h) => h.id),
    scoreOf: (probe, id) => {
      const row = stmtScore.get(probe, id) as { score: number } | undefined;
      return row?.score ?? 0;
    },
  };
}

function float32Blob(v: number[]): Uint8Array {
  return new Uint8Array(Float32Array.from(v).buffer);
}

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)] ?? 0;
}

function recall(got: Hit[], want: Hit[]): number {
  if (want.length === 0) return 1;
  const truth = new Set(want.map((h) => h.id));
  let hit = 0;
  for (const h of got) if (truth.has(h.id)) hit++;
  return hit / want.length;
}

/**
 * Fraction of the exact top-k's total similarity that the approximate top-k retains.
 *
 * Reported beside recall because recall alone cannot tell a real miss from a tie, and in a
 * near-orthogonal corpus nearly every miss is a tie: the true 30th neighbour and the 34th
 * differ in the third decimal of a cosine, so exchanging them costs a recall point and
 * changes nothing a reader could notice. A run where recall sags while this stays at 1,000
 * is losing ties. A run where both sag is losing passages, and that is the regression this
 * ticket refuses to ship.
 */
function similarityKept(got: Hit[], want: Hit[]): number {
  const total = want.reduce((a, h) => a + h.score, 0);
  if (total <= 0) return 1;
  return got.slice(0, want.length).reduce((a, h) => a + h.score, 0) / total;
}

/**
 * Pool as a multiple of topK, carried past the point where the two-stage query stops being
 * a speedup. A sweep that stops at the pool you already meant to ship cannot tell you the
 * pool was too small, so the last two rows are here to be rejected: vec0's KNN cost grows
 * faster than linearly in k (measured at 100 000 x 384: 7,7 ms at k=30, 18,2 at k=120,
 * 83,6 at k=480, 216,8 at k=960), so a wide pool makes STAGE ONE the expensive half and
 * the whole query costs more than the exact scan it replaces.
 */
const POOL_FACTORS = [1, 2, 4, 8, 16, 32];

const TITLES: Record<FixtureKind, string> = {
  uniform: 'uniform random unit vectors (conservative)',
  clustered: 'clustered, 200 centroids (realistic)',
};

function measure(label: FixtureKind, path: string, opts: Options, corpusSeed: number): void {
  // ONE fixture instance for both the corpus and the queries. The probes are drawn from it
  // after the corpus is built, so they share its centroids without being members of it — a
  // held-out query set. Building a second fixture for the probes is the mistake this
  // replaces: fresh centroids meant every query pointed away from every cluster, and the
  // clustered corpus was measured against queries no user would ever issue. It made the
  // realistic fixture look as hard as the conservative one, which should have been the
  // tell.
  const fixture = fixtureFor(label, opts.dim, makeRandom(corpusSeed));
  build(path, opts, fixture);
  const sizeMb = statSync(path).size / 2 ** 20;

  const probes = Array.from({ length: opts.probes }, (_, i) => fixture(opts.n + i));
  const blobs = probes.map(float32Blob);

  const ref = references(path);
  const truth: Hit[][] = [];
  const exactMs: number[] = [];
  for (const b of blobs.slice(0, 4)) ref.exact(b, opts.topK); // warm the page cache
  for (const b of blobs) {
    const t0 = performance.now();
    truth.push(ref.exact(b, opts.topK));
    exactMs.push(performance.now() - t0);
  }

  console.log(`\n### ${TITLES[label]}  N=${opts.n} dim=${opts.dim} topK=${opts.topK} probes=${opts.probes}`);
  console.log(`database ${sizeMb.toFixed(0)} MB (float32 + binary columns, FTS5 and metadata included)`);
  console.log('pool                      recall@k   sim kept   median query');
  console.log(`exact float32 (before)       1.000      1.000   ${median(exactMs).toFixed(1).padStart(7)} ms`);

  // Binary alone, no rerank: the measurement that decides whether float32 may be dropped.
  const binOnlyRecall: number[] = [];
  const binOnlySim: number[] = [];
  const binOnlyMs: number[] = [];
  for (let i = 0; i < blobs.length; i++) {
    const t0 = performance.now();
    const ids = ref.binaryOnly(blobs[i]!, opts.topK);
    binOnlyMs.push(performance.now() - t0);
    // Scored from the exact table, because a Hamming distance is not a similarity: the
    // question is how good the passages it chose really are, not what it believed of them.
    const got = ids
      .map((id) => ({ id, score: ref.scoreOf(blobs[i]!, id) }))
      .sort((a, b) => b.score - a.score);
    binOnlyRecall.push(recall(got, truth[i]!));
    binOnlySim.push(similarityKept(got, truth[i]!));
  }
  const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
  console.log(
    `binary only, no rerank       ${mean(binOnlyRecall).toFixed(3)}      ` +
      `${mean(binOnlySim).toFixed(3)}   ${median(binOnlyMs).toFixed(1).padStart(7)} ms`,
  );

  for (const factor of POOL_FACTORS) {
    // poolMin: 1 so the sweep measures the ratio and nothing else; the shipped floor is a
    // separate decision about small topK, not about this curve.
    // twoStage on explicitly: the shipped default is off, and this bench exists to
    // measure the path, not the default.
    const store = new Fts5PassageStore(path, { twoStage: true, poolFactor: factor, poolMin: 1 });
    const rs: number[] = [];
    const sims: number[] = [];
    const ms: number[] = [];
    for (let i = 0; i < probes.length; i++) {
      const t0 = performance.now();
      const got = store.vectorSearch(probes[i]!, opts.topK);
      ms.push(performance.now() - t0);
      rs.push(recall(got, truth[i]!));
      sims.push(similarityKept(got, truth[i]!));
    }
    store.close();
    const pool = factor * opts.topK;
    console.log(
      `two-stage, pool=${String(pool).padEnd(6)}(${String(factor).padStart(3)}k)   ` +
        `${mean(rs).toFixed(3)}      ${mean(sims).toFixed(3)}   ${median(ms).toFixed(1).padStart(7)} ms`,
    );
  }
  ref.db.close();
  unlinkDb(path);
}

function main(): void {
  const opts = parseArgs(process.argv.slice(2));
  const path = tempPath('sweep');
  try {
    measure('uniform', path, opts, 999);
    measure('clustered', path, opts, 31337);
  } finally {
    unlinkDb(path);
  }
}

main();
