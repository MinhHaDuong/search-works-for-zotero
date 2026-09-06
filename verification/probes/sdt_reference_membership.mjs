// Feed the installed worker bundle on stdin. No PDF or Zotero process is opened.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(0, 'utf8');
const start = source.indexOf('function isReferenceBlock(');
const end = source.indexOf('\nfunction getReferenceForBlock', start);
assert.ok(start >= 0 && end > start, 'Installed function anchors changed');
const context = vm.createContext({
  reference_getBlockRefKey: ref => ref.join(','),
});
vm.runInContext(source.slice(start, end), context);
const cases = [];
for (const [blocks, runs] of [[100, 100], [1000, 100], [1000, 1000]]) {
  let comparisons = 0;
  const index = {
    runs: {
      *[Symbol.iterator]() {
        for (let i = 0; i < runs; i++) {
          comparisons++;
          yield { ref: [blocks + i] };
        }
      },
    },
    referenceBlocks: new Set(),
  };
  for (let i = 0; i < blocks; i++) {
    assert.equal(context.isReferenceBlock(index, [i]), false);
  }
  assert.equal(comparisons, blocks * runs);
  cases.push({ blocks, runs, comparisons });
}
console.log(JSON.stringify({
  workerSha256: createHash('sha256').update(source).digest('hex'),
  scope: 'Exact installed membership function, synthetic nonmatching runs; not an extraction benchmark',
  cases,
}, null, 2));
