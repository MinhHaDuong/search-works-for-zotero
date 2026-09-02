#!/usr/bin/env node
/**
 * Run seg/1 over Zotero full-text cache files and report what it cut.
 *
 * The consumer path experiment X5 uses on the author's machine: the cache is
 * streamed in windows the size the extract worker forwards, so the segmenter
 * runs exactly as it would inside the conductor. Nothing here is committed to
 * bench/results by this script; it prints, and `--json` prints machine-readable.
 *
 * Needs the fork built: `cd fork && npm run build`. The fork is a separate,
 * git-ignored checkout; `--fork` points at another one, as in the sibling drivers.
 *
 *   node bench/seg1_run.mjs --key ABCD1234 [--key ...] [--titles 20] [--fork /path/to/fork/]
 *   node bench/seg1_run.mjs --path /path/to/.zotero-ft-cache
 *   node bench/seg1_run.mjs --keys-file keys.txt --json > out.jsonl
 */

import { readFileSync, createReadStream } from 'node:fs';
import { join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { parseArgs } from 'node:util';

const { values } = parseArgs({
  options: {
    key: { type: 'string', multiple: true, default: [] },
    path: { type: 'string', multiple: true, default: [] },
    'keys-file': { type: 'string' },
    storage: { type: 'string', default: join(homedir(), 'data', 'Zotero', 'storage') },
    fork: { type: 'string', default: new URL('../fork/', import.meta.url).pathname },
    titles: { type: 'string', default: '12' },
    json: { type: 'boolean', default: false },
  },
});

const seg1Path = resolve(values.fork, 'dist', 'features', 'search', 'segmenter', 'seg1.js');
const { createSeg1, SEG1_ID } = await import(seg1Path);

// The extract worker's window: WINDOW_CHARS in the fork's conductor/document-stream.ts
// (streamFullText). Restated here because that branch is not in the build this imports
// (ticket 0565's recon); re-read it there if the worker's geometry moves.
const WINDOW_CHARS = 64 * 1024;

const cachePath = (k) => join(values.storage, k, '.zotero-ft-cache');
const targets = [];
for (const k of values.key) targets.push({ key: k, path: cachePath(k) });
for (const p of values.path) targets.push({ key: null, path: p });
if (values['keys-file']) {
  for (const line of readFileSync(values['keys-file'], 'utf8').split('\n')) {
    const k = line.trim().split(/\s+/)[0];
    if (k) targets.push({ key: k, path: cachePath(k) });
  }
}
if (targets.length === 0) {
  console.error('nothing to do: pass --key, --path or --keys-file');
  process.exit(2);
}

/**
 * Stream a file in windows of WINDOW_CHARS characters. A window never ends on a high
 * surrogate, so each pushed string is valid UTF-16 on its own — driver-side hygiene for
 * what gets logged and diffed; seg/1 itself is tested equal across window sizes.
 */
async function segmentFile(path) {
  const seg = createSeg1();
  let offset = 0;
  let pending = '';
  const stream = createReadStream(path, { encoding: 'utf8', highWaterMark: 256 * 1024 });
  for await (const chunk of stream) {
    pending += chunk;
    while (pending.length >= WINDOW_CHARS) {
      let cut = WINDOW_CHARS;
      const code = pending.charCodeAt(cut - 1);
      if (code >= 0xd800 && code <= 0xdbff) cut -= 1;
      seg.push({ text: pending.slice(0, cut), offset });
      offset += cut;
      pending = pending.slice(cut);
    }
  }
  // Flush the tail; an empty document still pushes once so the segmenter sees it.
  if (pending.length > 0 || offset === 0) {
    seg.push({ text: pending, offset });
    offset += pending.length;
  }
  return seg.finish();
}

const maxTitles = Number(values.titles);
for (const t of targets) {
  const label = t.key ?? t.path;
  let result;
  const started = process.hrtime.bigint();
  try {
    result = await segmentFile(t.path);
  } catch (err) {
    const line = { key: t.key, path: t.path, error: String(err?.message ?? err) };
    console.log(values.json ? JSON.stringify(line) : `${label}: ERROR ${line.error}`);
    continue;
  }
  const ms = Number(process.hrtime.bigint() - started) / 1e6;
  const summary = {
    key: t.key,
    segmenter: SEG1_ID,
    chars: result.chars,
    formFeeds: result.formFeeds,
    documentClass: result.documentClass,
    fallback: result.fallback,
    confidence: Number(result.confidence.toFixed(3)),
    entries: result.entries.length,
    ms: Math.round(ms),
    titles: result.entries.slice(0, maxTitles).map((e) => ({
      ordinal: e.ordinal,
      title: e.title,
      charStart: e.charStart,
      chars: e.charEnd - e.charStart,
      page: e.pageStart ?? null,
      sections: e.sections.length,
      tier: e.tier,
    })),
  };
  if (values.json) {
    console.log(JSON.stringify(summary));
    continue;
  }
  console.log(
    `${label}: ${summary.documentClass} fallback=${summary.fallback} confidence=${summary.confidence} ` +
      `entries=${summary.entries} chars=${summary.chars} ff=${summary.formFeeds} ${summary.ms} ms`,
  );
  for (const e of summary.titles) {
    const page = e.page === null ? '' : ` p.${e.page}`;
    console.log(`  #${e.ordinal}${page} @${e.charStart} (${e.chars} chars, ${e.sections} sections) ${e.title ?? '<no title>'}`);
  }
  if (summary.entries > maxTitles) console.log(`  … ${summary.entries - maxTitles} more`);
}
