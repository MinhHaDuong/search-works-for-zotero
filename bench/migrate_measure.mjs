// Isolated JSON -> SQLite migration, with the environment recorded in the artifact.
// Written because PR #2's review found the original figures (peak RSS, wall clock,
// database size) existed only in an agent's uncaptured stdout. Everything this
// prints lands in a committed JSON file.
// The fork is a separate, git-ignored checkout; ZOTEUS_FORK overrides its location.
const FORK = process.env.ZOTEUS_FORK ?? new URL('../fork/', import.meta.url).pathname;
const { migrateJsonIndexToSqlite } = await import(`${FORK}dist/features/search/migrate-json.js`);
import { statSync, readFileSync, existsSync, unlinkSync } from 'node:fs';

const [jsonPath, dbPath] = process.argv.slice(2);
for (const f of [dbPath, dbPath + '-wal', dbPath + '-shm']) if (existsSync(f)) unlinkSync(f);
const jsonBytes = statSync(jsonPath).size;
const t0 = Date.now();
const r = await migrateJsonIndexToSqlite({ jsonPath, dbPath });
const wall_ms = Date.now() - t0;
// VmHWM is the kernel high-water mark: it cannot miss a peak between samples.
const status = readFileSync('/proc/self/status', 'utf8');
const kb = (k) => Number(new RegExp(`^${k}:\\s+(\\d+)`, 'm').exec(status)?.[1] ?? 0);
const sidecars = ['-wal', '-shm'].filter((s) => existsSync(dbPath + s));
console.log(JSON.stringify({
  node_options: process.env.NODE_OPTIONS ?? '', node_version: process.version,
  jsonPath, json_bytes: jsonBytes, db_bytes: statSync(dbPath).size,
  ratio_db_over_json: +(statSync(dbPath).size / jsonBytes).toFixed(4),
  wall_ms, peak_rss_kB_VmHWM: kb('VmHWM'), final_rss_kB_VmRSS: kb('VmRSS'),
  sidecars_left: sidecars, result: r,
}, null, 1));
