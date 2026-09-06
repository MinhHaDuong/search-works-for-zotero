/* The sitter's Fluent layer, driven rather than read (ticket 0692).
 *
 * The criterion the ticket names is the one a source grep cannot settle: a
 * `.ftl` that is missing an id must fall through to English and raise nothing.
 * A translator ships an incomplete file every time — that is the normal state
 * of a locale between two releases — so the fallback is not an edge case, it is
 * the running condition, and a window that throws out of `render()` over it
 * would stop the whole 100 ms redraw loop.
 *
 * Every arm here carries its own positive control, because the shape of this
 * test is exactly the shape that reads like evidence and is not: "the English
 * text appeared" is satisfied by a locale layer that never loaded at all. So
 * each fallback arm is paired with a complete-file arm proving the same id DOES
 * render in French when French has it.
 *
 * The Fluent implementation is `tests/fluent_stub.mjs` — see its header for why
 * a stub rather than the first npm dependency this repository would have.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

import { FluentModule } from './fluent_stub.mjs';

const SITTER = 'plugins/sdt-sitter';
const ROOT = `${SITTER}/`;
const locale = tag => `${ROOT}locale/${tag}/sdt-pack-sitter.ftl`;

/** A context with bootstrap.js loaded and a host that serves the given `.ftl` texts. */
function host(files) {
  const ui = {};
  vm.runInNewContext(fs.readFileSync(`${SITTER}/bootstrap.js`, 'utf8'), ui);
  // Ambient globals, which is how privileged JS actually gets Fluent: verified
  // live in Zotero 10.0.1, `typeof FluentBundle` and `typeof FluentResource`
  // both answer "function", and every `resource://gre/modules/Fluent*.sys.mjs`
  // fails to load. This file used to serve them through a mocked
  // `ChromeUtils.importESModule`, so it asserted the sitter kept making an
  // import the real host has never answered — green here, and every string in
  // the shipped window rendering as its own id.
  ui.FluentBundle = FluentModule.FluentBundle;
  ui.FluentResource = FluentModule.FluentResource;
  // Delivered as `locales.js` assigns them, not fetched. A `.ftl` inside an
  // installed XPI is unreadable at runtime — `rootURI` is a `jar:` URL and
  // every read API refuses it (ticket 0727) — so a host serving them over
  // `Zotero.File` was modelling a delivery that has never worked. The arms
  // below still name files by URL, because "which locale is present" is what
  // they are about; only the road changed.
  ui.SDT_LOCALE_SOURCES = Object.fromEntries(
    Object.entries(files).map(([url, text]) => [url.split('/').at(-2), text]));
  ui.Zotero = { debug: () => {}, Prefs: { get: () => false } };
  return ui;
}

const english = fs.readFileSync(locale('en'), 'utf8');
const french = fs.readFileSync(locale('fr'), 'utf8');

const results = [];
function test(name, body) { body(); results.push(name); }

/* ---- the chain: a regional tag falls back to its language, then to English ---- */

const complete = host({ [locale('en')]: english, [locale('fr')]: french });
const loaded = await complete.loadSDTLocalization('fr-FR');

test('a regional tag with no file of its own resolves to its language', () => {
  // `fr-FR` is served by nothing here, so a loader that demanded an exact match
  // would have landed on English and every French assertion below would fail
  // for a reason that has nothing to do with the missing-id path.
  assert.equal(loaded.locale, 'fr');
  assert.equal(loaded.bundles, 2, 'the English fallback bundle was not kept behind French');
});

test('a complete French file renders French — the control every arm below needs', () => {
  assert.equal(complete.sdtText('dialog-title'), 'Assistant d’indexation');
  assert.equal(complete.sdtText('active-none'), 'Aucune indexation en cours');
});

/* ---- the criterion: a truncated `fr.ftl` shows English where the id is gone ---- */

/** Drop `id` and everything indented under it, the way a half-translated file arrives. */
function without(source, ids) {
  const lines = source.split('\n');
  const kept = [];
  let dropping = false;
  for (const line of lines) {
    if (/^\s/.test(line) && dropping) continue;
    if (line.trim() && !/^\s/.test(line)) {
      dropping = ids.includes(line.slice(0, line.indexOf('=')).trim());
    }
    if (!dropping) kept.push(line);
  }
  return kept.join('\n');
}

const MISSING = ['dialog-title', 'active-none', 'files-indexed'];
const truncated = without(french, MISSING);

test('the truncation removed messages that were really there', () => {
  // Without this the next test is a null result with no control: a `without()`
  // that matched nothing would leave French complete and every "English
  // appeared" assertion below would be about a file nothing had truncated.
  for (const id of MISSING) {
    assert(french.includes(`\n${id} =`), `${id} is not in fr.ftl at all`);
    assert(!truncated.includes(`\n${id} =`), `${id} survived the truncation`);
  }
  assert(truncated.includes('\nphase-census ='), 'the truncation took the whole file');
});

const partial = host({ [locale('en')]: english, [locale('fr')]: truncated });
await partial.loadSDTLocalization('fr');

test('a missing id falls back to English rather than throwing', () => {
  assert.equal(partial.sdtText('dialog-title'), 'Indexing assistant');
  assert.equal(partial.sdtText('active-none'), 'No indexing under way');
  // And the ids the file still carries stay French: the fallback is per message,
  // not a whole-bundle demotion.
  assert.equal(partial.sdtText('phase-census'), 'Recensement');
});

test('a plural-selector message falls back with its selector intact', () => {
  // The English fallback must still SELECT, not print the `other` variant blind:
  // 0 is `one` in French and `other` in English, and the fallback is English.
  assert.equal(partial.sdtText('files-indexed', { count: 0 }), '0 files indexed');
  assert.equal(partial.sdtText('files-indexed', { count: 1 }), '1 file indexed');
  assert.equal(partial.sdtText('files-indexed', { count: 4 }), '4 files indexed');
  // The control: with the id present, French selects by French rules, where
  // zero is singular.
  assert.equal(complete.sdtText('files-indexed', { count: 0 }), '0 fichier indexé');
  assert.equal(complete.sdtText('files-indexed', { count: 1 }), '1 fichier indexé');
  assert.equal(complete.sdtText('files-indexed', { count: 4 }), '4 fichiers indexés');
});

test('the failures line selects the same way', () => {
  assert.equal(complete.sdtText('files-failed', { count: 1 }),
    '1 fichier n’a pas pu être indexé');
  assert.equal(complete.sdtText('files-failed', { count: 3 }),
    '3 fichiers n’ont pas pu être indexés');
  assert.equal(partial.sdtText('files-failed', { count: 1 }),
    '1 fichier n’a pas pu être indexé', 'the failures line was not translated');
});

test('an id no locale carries is loud and harmless', () => {
  // Fluent's own convention: the id stands in for the string. It is visible in
  // the window, it names exactly what to add, and it does not throw into a
  // redraw loop that runs ten times a second.
  assert.equal(partial.sdtText('no-such-message-anywhere'), 'no-such-message-anywhere');
  assert.equal(partial.sdtText('no-such-message-anywhere', { count: 2 }),
    'no-such-message-anywhere');
});

test('an argument a message does not expect is not a throw', () => {
  assert.equal(complete.sdtText('active-none', { count: 3 }), 'Aucune indexation en cours');
});

/* ---- a locale file that is not merely incomplete but malformed ---- */

const MALFORMED = [
  ['a message with no equals sign', french.replace('phase-error = Erreur', 'phase-error Erreur')],
  ['a Fluent function the subset forbids',
    french.replace('index-coverage = Index { $percent } %',
      'index-coverage = Index { NUMBER($percent) } %')],
  ['a select with no default variant',
    french.replace('       *[other] { $count } fichiers indexés',
      '        [other] { $count } fichiers indexés')],
  ['a truncated tail', `${french.slice(0, french.indexOf('phase-census'))}dialog-title = {`],
];

for (const [what, source] of MALFORMED) {
  const broken = host({ [locale('en')]: english, [locale('fr')]: source });
  const result = await broken.loadSDTLocalization('fr');
  test(`${what} degrades to English instead of throwing`, () => {
    // The positive control is the mutation itself: each string above differs
    // from the file on disk, and `String.replace` is a no-op on a miss, so the
    // arm would be about an intact file.
    assert.notEqual(source, french, `the ${what} mutation matched nothing`);
    // English survives, which is the property that matters: a reader gets a
    // window in a language rather than a window of message ids.
    assert.equal(broken.sdtText('dialog-title'), 'Indexing assistant');
    assert.equal(broken.sdtText('files-indexed', { count: 2 }), '2 files indexed');
    assert(result.bundles >= 1, 'the English bundle went down with the French one');
  });
}

/* What these arms do NOT establish, recorded rather than glossed: this stub
   discards a whole resource on one bad entry, and Gecko's real Fluent is
   documented as fault-tolerant per entry — it keeps the messages that parsed
   and reports the rest through the errors array `addResource` returns. So
   production is expected to do BETTER than this (some French, not none), and
   nothing here proves it for this add-on, because proving it needs the real
   parser. What is proved is the floor, and the floor is what the sitter's
   guarantee rests on: whatever the parser does with a broken file, the window
   still renders and the redraw loop still runs. */

/* ---- the platform failing entirely ---- */

test('no locale file at all leaves the window naming its ids', () => {
  const bare = host({});
  return Promise.resolve(bare.loadSDTLocalization('fr')).then(result => {
    assert.equal(result.bundles, 0);
    assert.equal(bare.sdtText('dialog-title'), 'dialog-title');
  });
});

const noFluent = host({ [locale('en')]: english });
// A host where the globals are simply not there — an older Gecko, or a scope
// that does not expose them. Deleting them is the whole of the simulation now:
// there is no import left to make throw.
delete noFluent.FluentBundle;
delete noFluent.FluentResource;

test('a host with no Fluent global degrades instead of stopping startup', async () => {
  const result = await noFluent.loadSDTLocalization('en');
  assert.equal(result.bundles, 0);
  assert.equal(noFluent.sdtText('dialog-title'), 'dialog-title');
});

/* ---- the four locales load, and each is complete against English ---- */

// Read off the tree, not listed here: a locale added to `locale/` and to
// nothing else must be exercised by this loop rather than skipped by it.
// `tests/test_sdt_sitter.py` is what holds that directory and the packed set
// together; this loop only has to not be a third place to forget.
for (const tag of fs.readdirSync(`${ROOT}locale`).sort()) {
  const source = fs.readFileSync(locale(tag), 'utf8');
  const one = host({ [locale(tag)]: source });
  await one.loadSDTLocalization(tag);
  test(`${tag} parses and answers with no English behind it`, () => {
    assert.equal(one.sdtText('dialog-title') === 'dialog-title', false,
      `${tag}.ftl carries no dialog-title`);
    // Every plural-sensitive message must select in every locale, including the
    // ones (Vietnamese) whose plural rules have a single category.
    for (const id of ['files-indexed', 'files-failed']) {
      const singular = one.sdtText(id, { count: 1 });
      assert(singular && singular !== id, `${tag}.ftl: ${id} did not format`);
      assert(!singular.includes('$'), `${tag}.ftl: ${id} left a placeable unresolved`);
      assert(singular.includes('1'), `${tag}.ftl: ${id} dropped its count`);
    }
  });
}

console.log(JSON.stringify({ tests: results, result: 'pass' }));
