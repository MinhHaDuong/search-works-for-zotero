#!/usr/bin/env node
/**
 * Serve the committed golden export as the mock Zotero local API, for the query side.
 *
 * `make_index_fixture.mjs --replay-export` starts this same replay for the BUILD and stops
 * it when the build ends. Querying the built index happens in a second server process,
 * which probes the local API at startup like any other, so the replay has to be up again.
 * This entry loads the export with the same validator, starts the same replay, prints one
 * JSON line `{"port": N}` on stdout, and stays up until stdin closes — the driver that
 * spawned it owns its lifetime (ticket 0722, `bench/golden_run.py`).
 *
 * Usage:
 *   node bench/fixtures/golden_replay_serve.mjs --export <snapshot> --recipe <recipe.json>
 */
import { parseArgs } from 'node:util';

import { loadGoldenExport, startGoldenReplay } from './make_index_fixture.mjs';

const { values: opt } = parseArgs({
  options: { export: { type: 'string' }, recipe: { type: 'string' } },
});
if (!opt.export || !opt.recipe) {
  console.error('usage: golden_replay_serve.mjs --export <snapshot> --recipe <recipe.json>');
  process.exit(2);
}
const fixture = loadGoldenExport(opt.export, { recipePath: opt.recipe });
const replay = await startGoldenReplay(fixture);
process.stdout.write(`${JSON.stringify({ port: replay.port, recipe_sha256: fixture.manifest.recipe_sha256 })}\n`);

const stop = async () => {
  await replay.close();
  process.exit(0);
};
process.stdin.on('end', stop);
process.stdin.on('close', stop);
process.on('SIGTERM', stop);
process.stdin.resume();
