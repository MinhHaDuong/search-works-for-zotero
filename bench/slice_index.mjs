// Cut a smaller but REAL index from the 321 MB one: same passages, fewer of them.
// Streaming, because the input is the file JSON.parse cannot comfortably hold.
import { createReadStream, createWriteStream } from 'node:fs';
const [src, dst, wantStr] = process.argv.slice(2);
const want = Number(wantStr);
const out = createWriteStream(dst);
out.write('{"chunks":[');
let buf = '', depth = 0, inStr = false, esc = false, started = false, n = 0, cur = '';
outer: for await (const piece of createReadStream(src, { encoding: 'utf8' })) {
  buf += piece;
  for (let i = 0; i < buf.length; i++) {
    const c = buf[i];
    if (!started) { if (c === '[') started = true; continue; }
    if (depth > 0) cur += c;
    if (esc) { esc = false; continue; }
    if (c === '\\') { esc = true; continue; }
    if (c === '"') { inStr = !inStr; continue; }
    if (inStr) continue;
    if (c === '{') { if (depth === 0) cur = '{'; depth++; }
    else if (c === '}') { depth--; if (depth === 0) { if (n) out.write(','); out.write(cur); if (++n >= want) break outer; } }
  }
  buf = '';
}
out.write('],"vectors":[],"builtFromVersion":200}');
await new Promise(r => out.end(r));
console.log(JSON.stringify({ chunks_written: n }));
