// Read the model registry. The drivers name models by registry id; `models.json`
// is the only file in bench/ that knows what a registry id points at.
//
// Three per-model axes travel with the repository, and every one of them has been
// silently dropped by a wrapper at least once: `pooling` (hardcoded 'mean' against four
// cls candidates, ticket 0421), the device flag (ticket 0481), and `normalize` (declared
// by ticket 0262 and read by nobody until ticket 0486). Destructure them from
// resolveModel; a literal at the call site is the defect, not a shortcut.
//
// Two repositories per record, and the difference matters. `hf_repo` is what the
// ONNX runtime loads — usually a mirror, because the mirror is what publishes the
// filenames the dtype knob can address. `upstream_repo` is the author's own
// repository, which is what a PyTorch/sentence-transformers loader wants and where
// the card, the licence and the language list live.
//
//   import { resolveModel } from './registry.mjs';
//   const { repo, template, pooling, normalize } = resolveModel('multilingual-e5-small');

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const REGISTRY_PATH = fileURLToPath(new URL('./models.json', import.meta.url));

export function loadRegistry(path = REGISTRY_PATH) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

/**
 * Resolve one token to a repository and its input template.
 *
 * A registry id resolves to the declared repository. Anything containing a slash is
 * taken as a literal repository id and passed through, so an ad-hoc run is still
 * possible — with a warning, because a result from an undeclared model has no record
 * saying what it is.
 *
 * @param {string} token registry id, or a literal `owner/name`
 * @param {{registry?: object, kind?: 'onnx'|'upstream'}} [options]
 */
export function resolveModel(token, options = {}) {
  const registry = options.registry ?? loadRegistry();
  const kind = options.kind ?? 'onnx';
  const record = registry.models.find((entry) => entry.id === token);
  if (record) {
    const repo = kind === 'upstream' ? record.upstream_repo : record.hf_repo;
    return {
      id: record.id,
      repo,
      template: record.input_template,
      pooling: record.pooling ?? null,
      // `unknown` travels as null, exactly like an absent pooling. The registry uses
      // that string for "the model card could not be read", which is a different fact
      // from `false` and must never collapse into it — a driver handed null stops,
      // a driver handed false quietly measures the wrong geometry. Ticket 0486.
      normalize: typeof record.normalize === 'boolean' ? record.normalize : null,
      record,
    };
  }
  if (token.includes('/')) {
    console.warn(
      `[registry] ${token} is not declared in models.json; the run is undeclared. ` +
        'Add a record rather than passing a repository id.',
    );
    // `pooling: null` is deliberate and is not a default. An undeclared model's
    // pooling is unknown, and the wrong value degrades retrieval silently — so the
    // caller is handed the absence to deal with, not a plausible guess.
    return {
      id: token,
      repo: token,
      template: { query: '', passage: '' },
      pooling: null,
      normalize: null,
      record: null,
    };
  }
  const known = registry.models.map((entry) => entry.id).join(', ');
  throw new Error(`[registry] unknown model ${token}. Declared ids: ${known}`);
}

/** Every registry id whose record is a live candidate. */
export function candidateIds(registry = loadRegistry()) {
  return registry.models.filter((entry) => entry.status === 'candidate').map((entry) => entry.id);
}
