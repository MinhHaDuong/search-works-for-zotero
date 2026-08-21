import { migrateJsonIndexToSqlite } from '/home/haduong/CNRS/projets/actifs/zoteus-fts5/fork/dist/features/search/migrate-json.js';

const [jsonPath, dbPath] = process.argv.slice(2);
const t0 = Date.now();
const r = await migrateJsonIndexToSqlite({ jsonPath, dbPath });
console.log(JSON.stringify({ ...r, wall_ms: Date.now() - t0 }));
