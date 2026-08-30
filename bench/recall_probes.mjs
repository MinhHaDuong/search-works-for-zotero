// The same-item probe draw, factored out so the keyword arm and the fusion driver draw
// EXACTLY the probes bench/vec_task_recall.mjs would draw given the same items/ords/seed —
// the three arms (keyword, vector, fused) are only comparable if they answer the same
// questions.
//
// This is a deliberate COPY of vec_task_recall.mjs's eligibility + draw logic, not an
// import from it: that driver's CLI/output/tests are ticket 0262's, in production use, and
// this ticket does not want to refactor a working driver to extract a dependency. Copied
// verbatim instead, byte-for-byte the same algorithm, so a probe index computed here and one
// computed by vec_task_recall.mjs agree given the same inputs -- tests/test_recall_probes.py
// (well, the .mjs sibling) asserts exactly that against a small fixture, guarding against the
// two copies drifting apart.
import { readFileSync } from 'node:fs';

export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function loadItemsOrds(itemsPath, ordsPath) {
  const items = readFileSync(itemsPath, 'utf8').split('\n').filter(Boolean);
  const ords = readFileSync(ordsPath, 'utf8').split('\n').filter(Boolean).map(Number);
  if (items.length !== ords.length) {
    throw new Error(`items (${items.length}) and ords (${ords.length}) disagree`);
  }
  return { items, ords };
}

export function groupByItem(items) {
  const byItem = new Map();
  for (let i = 0; i < items.length; i++) {
    if (!byItem.has(items[i])) byItem.set(items[i], []);
    byItem.get(items[i]).push(i);
  }
  return byItem;
}

/** Relevant set for probe p: same item, at least `gap` chunks away, self excluded. */
export function relevantSet(byItem, items, ords, p, gap) {
  const sibs = byItem.get(items[p]);
  return new Set(sibs.filter((j) => j !== p && Math.abs(ords[j] - ords[p]) >= gap));
}

/**
 * Probes that CAN be answered (an item has a sibling >= gap away), drawn once with a
 * seeded PRNG so every arm scores the identical probe set.
 */
export function drawProbes({ items, ords, gap, probes, seed }) {
  const byItem = groupByItem(items);
  const eligible = [];
  for (let i = 0; i < items.length; i++) {
    const sibs = byItem.get(items[i]);
    if (sibs.some((j) => j !== i && Math.abs(ords[j] - ords[i]) >= gap)) eligible.push(i);
  }
  const rnd = mulberry32(Number(seed));
  const probeIdx = [];
  const seen = new Set();
  while (probeIdx.length < Math.min(probes, eligible.length)) {
    const p = eligible[Math.floor(rnd() * eligible.length)];
    if (!seen.has(p)) {
      seen.add(p);
      probeIdx.push(p);
    }
  }
  return { byItem, eligible, probeIdx };
}
