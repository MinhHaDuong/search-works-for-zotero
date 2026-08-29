// Does zoteus's embed call silently truncate at 512 tokens?
// The test only works if the tail is SEMANTICALLY DIFFERENT from the head:
// with a repeated word, mean-pooling gives the same vector either way and the
// experiment proves nothing. Head = topic A, tail = topic B.
const MOD = '/home/haduong/CNRS/projets/actifs/zoteus-fts5/fork/node_modules/@huggingface/transformers/dist/transformers.node.mjs';
const t = await import(MOD);
const pipeline = t.pipeline ?? t.default?.pipeline;
const AutoTokenizer = t.AutoTokenizer ?? t.default?.AutoTokenizer;

const tok = await AutoTokenizer.from_pretrained('Xenova/all-MiniLM-L6-v2');
const extractor = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
const ntok = (s) => tok(s).input_ids.dims.at(-1);

const A = 'Carbon pricing policy and emissions trading schemes in European industrial sectors. ';
const B = 'Arctic tern migration routes, breeding colonies, plumage and feeding behaviour at sea. ';

const head = A.repeat(75);           // topic A, comfortably over 512 tokens
const tail = B.repeat(60);           // topic B
const long = head + tail;

async function embed(s) {
  const r = await extractor([s], { pooling: 'mean', normalize: true });
  return Array.from(r.data);
}
const cos = (a, b) => { let d = 0; for (let i = 0; i < a.length; i++) d += a[i] * b[i]; return d; };

console.log('tokens: head', ntok(head), ' tail', ntok(tail), ' long', ntok(long));

const vLong = await embed(long);
const vHead = await embed(head);
const vTail = await embed(tail);

const cLongHead = cos(vLong, vHead);
const cLongTail = cos(vLong, vTail);
const cHeadTail = cos(vHead, vTail);

console.log('cosine(long, head-only) =', cLongHead.toFixed(6));
console.log('cosine(long, tail-only) =', cLongTail.toFixed(6));
console.log('cosine(head,      tail) =', cHeadTail.toFixed(6), ' <- positive control: must be well below 1');

if (cHeadTail > 0.95) {
  console.log('INCONCLUSIVE: head and tail are too similar for this test to discriminate.');
} else if (cLongHead > 0.999) {
  console.log('=> SILENT TRUNCATION at 512: the long text embeds exactly as its head; the tail was discarded.');
} else {
  console.log('=> NOT truncated: the tail measurably influenced the vector.');
}
