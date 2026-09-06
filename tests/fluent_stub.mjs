/* A hand-written stand-in for `resource://gre/modules/Fluent.sys.mjs`, so the
   sitter's own localization code can be driven under plain Node.

   WHY THIS EXISTS AT ALL. Gecko's Fluent modules are not importable outside a
   Firefox/Zotero runtime, and this repository has no npm dependency of any kind
   — adding `@fluent/bundle` for a test would make it the first. Ticket 0692's
   Imagine note settled the trade explicitly: a minimal stub, or route the one
   fallback criterion through the real-Zotero smoke probe. The stub wins because
   it also lets every OTHER string assertion in tests/sdt_sitter_dialog.mjs and
   tests/sdt_sitter_scheduler.mjs go on being driven rather than grepped.

   WHAT IT IS NOT. It is not a Fluent implementation. It parses the subset the
   sitter's own `.ftl` files use and nothing more, and `tests/test_sdt_sitter.py`
   asserts those files stay inside that subset — so the stub cannot silently
   drift into accepting something the real parser would reject. The subset:

     * `#` comment lines and blank lines;
     * `identifier = pattern` on one line;
     * a select expression, which Fluent requires to span lines:
           id = { $count ->
                   [one] one thing
                  *[other] { $count } things
               }
     * placeables of the single form `{ $variable }`.

   Terms (`-term`), attributes (`.attr`), message references (`{ other }`),
   functions (`{ NUMBER($n) }`), block text and escapes are all outside it and
   are refused loudly here rather than mis-parsed quietly.

   The two behaviours it must share with the real bundle, because the sitter
   depends on both: `useIsolating: false` suppresses the FSI/PDI marks Fluent
   otherwise wraps every placeable in (they would land in every assertion and in
   every tooltip), and a numeric argument is formatted with `Intl.NumberFormat`
   for the bundle's own locale — which is why a French "1,5" needs no
   hand-rolled comma anywhere in bootstrap.js. */

import fs from 'node:fs';

const IDENTIFIER = /^[A-Za-z][A-Za-z0-9_-]*$/;
const PLACEABLE = /\{\s*\$([A-Za-z][A-Za-z0-9_-]*)\s*\}/g;

class Unsupported extends Error {}

/** `[one] text` or `*[other] text` — the default variant carries the star. */
function parseVariant(line) {
  const match = /^(\*?)\[\s*([^\]]+?)\s*\]\s*(.*)$/.exec(line);
  if (!match) throw new Unsupported(`not a Fluent variant: ${line}`);
  return { default: match[1] === '*', key: match[2], text: match[3] };
}

/** One message value: either plain text with placeables, or one select. */
function parseValue(text) {
  const select = /^\{\s*\$([A-Za-z][A-Za-z0-9_-]*)\s*->\s*\n([\s\S]*)\}\s*$/.exec(text);
  if (!select) {
    if (text.includes('{')) {
      // Every brace the subset allows is a `{ $var }`; anything else left over
      // is a construct this stub would format wrongly rather than refuse.
      const residue = text.replace(PLACEABLE, '');
      if (residue.includes('{') || residue.includes('}')) {
        throw new Unsupported(`unsupported Fluent expression in: ${text}`);
      }
    }
    return { kind: 'text', text };
  }
  const variants = select[2].split('\n').map(line => line.trim()).filter(Boolean)
    .map(parseVariant);
  if (!variants.some(variant => variant.default)) {
    throw new Unsupported(`select expression with no default variant: ${text}`);
  }
  return { kind: 'select', variable: select[1], variants };
}

export class FluentResource {
  constructor(source) {
    this.messages = new Map();
    const lines = String(source).split('\n');
    let id = null, buffer = [];
    const flush = () => {
      if (id !== null) this.messages.set(id, parseValue(buffer.join('\n').trim()));
      id = null; buffer = [];
    };
    for (const line of lines) {
      if (/^\s*#/.test(line) || (!line.trim() && id === null)) continue;
      // A continuation line is indented; Fluent uses exactly that rule to know
      // a select's variants belong to the message above them.
      if (/^\s/.test(line) && id !== null) { buffer.push(line.trim()); continue; }
      if (!line.trim()) { flush(); continue; }
      flush();
      const split = line.indexOf('=');
      if (split < 0) throw new Unsupported(`not a Fluent message: ${line}`);
      const name = line.slice(0, split).trim();
      if (!IDENTIFIER.test(name)) throw new Unsupported(`unsupported Fluent entry: ${line}`);
      id = name;
      buffer.push(line.slice(split + 1).trim());
    }
    flush();
  }
}

export class FluentBundle {
  constructor(locales, options = {}) {
    this.locales = Array.isArray(locales) ? locales : [locales];
    // The real bundle defaults this ON. The sitter turns it off, and a stub
    // that defaulted it off would hide the day someone forgets to.
    this.useIsolating = options.useIsolating !== false;
    this.messages = new Map();
    this.plurals = new Intl.PluralRules(this.locales[0]);
    this.numbers = new Intl.NumberFormat(this.locales[0]);
  }

  addResource(resource) {
    for (const [id, value] of resource.messages) this.messages.set(id, { value });
    return [];
  }

  hasMessage(id) { return this.messages.has(id); }

  getMessage(id) { return this.messages.get(id); }

  formatPattern(pattern, args = null, errors = null) {
    try {
      return this.#format(pattern, args || {});
    } catch (error) {
      if (errors) { errors.push(error); return '???'; }
      throw error;
    }
  }

  #value(name, args) {
    if (!(name in args)) throw new Error(`unknown variable: $${name}`);
    const value = args[name];
    const text = typeof value === 'number' ? this.numbers.format(value) : String(value);
    return this.useIsolating ? `⁨${text}⁩` : text;
  }

  #text(text, args) {
    return text.replace(PLACEABLE, (_match, name) => this.#value(name, args));
  }

  #format(pattern, args) {
    if (pattern.kind === 'text') return this.#text(pattern.text, args);
    const selector = args[pattern.variable];
    const category = typeof selector === 'number' ? this.plurals.select(selector) : null;
    const chosen = pattern.variants.find(variant => variant.key === String(selector))
      || pattern.variants.find(variant => variant.key === category)
      || pattern.variants.find(variant => variant.default);
    return this.#text(chosen.text, args);
  }
}

/** What `ChromeUtils.importESModule('resource://gre/modules/Fluent.sys.mjs')` hands back. */
export const FluentModule = { FluentBundle, FluentResource };

/* Give a context that has already loaded bootstrap.js the REAL `.ftl` files, by
   running the plugin's own loader against them. Every driven assertion about
   what the window says therefore goes through the same fetch, chain and format
   path the plugin uses at startup — a test that hand-installed bundles would
   leave `loadSDTLocalization` itself unexercised, which is where the fallback
   chain lives.

   `Zotero` is set up here only as far as the loader needs it (a fetch, and the
   two calls `emit` makes); a caller that replaces `ui.Zotero` afterwards, as
   the scheduler test does per library fixture, keeps the bundles either way —
   they are held in the context's own `SDT_BUNDLES`, not on the host. */
export async function loadSitterLocale(ui, requested = 'fr') {
  const previous = ui.Zotero;
  ui.ChromeUtils = { importESModule: () => FluentModule };
  ui.Zotero = { debug: () => {}, Prefs: { get: () => false },
    // The loader builds `<rootURI>locale/<tag>/sdt-pack-sitter.ftl`, which under
    // the repository root is the path on disk. A tag with no file throws here,
    // exactly as an unshipped locale does against a real rootURI.
    File: { getContentsFromURLAsync: async url => fs.readFileSync(url, 'utf8') } };
  const loaded = await ui.loadSDTLocalization('bench/sdt-sitter/', requested);
  if (previous !== undefined) ui.Zotero = previous;
  return loaded;
}
