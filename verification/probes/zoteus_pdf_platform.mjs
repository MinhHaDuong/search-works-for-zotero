// Run from a Zoteus checkout with npm dependencies installed:
// node /path/to/this/probe.mjs [linux|win32|darwin]
// Non-host platforms are loader simulations, NOT native smoke tests.
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const require = createRequire(pathToFileURL(process.cwd() + '/package.json'));
const host = process.platform;
const target = process.argv[2] || host;
Object.defineProperty(process, 'platform', {value: target});
const result = {host, target, arch: process.arch, simulated: target !== host};
try {
  const pdfjs = await import(pathToFileURL(require.resolve('pdfjs-dist/legacy/build/pdf.mjs')).href);
  const bytes = new TextEncoder().encode(`%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 41 >> stream
BT /F1 24 Tf 20 100 Td (Hello PDF) Tj ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
trailer << /Root 1 0 R >>
%%EOF`);
  const task = pdfjs.getDocument({data: bytes, useSystemFonts: true, isEvalSupported: false});
  try {
    const doc = await task.promise;
    const page = await doc.getPage(1);
    const text = await page.getTextContent();
    result.text = text.items.map(it => it.str).join(' ');
  } finally {await task.destroy();}
} catch (e) {result.error = String(e);}
console.log(JSON.stringify(result));
