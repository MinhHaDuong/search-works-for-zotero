/* Experimental native SDT warmer. No endpoints, private ledger, or worker patch. */
var createSDTSitter;
var estimateSDTDuration;
var createSDTCache;
var createSDTJournal;
var createSDTSourceHashes;
// The census's status classification, which the coverage line below reads. Same
// provenance as the four above — scheduler.js is loaded into this global before
// anything renders — and declared here for the same reason: the forward
// declarations are where a reader finds out what this file expects to be given.
var SDT_STATUS_CLASSES;
// `var`, not `let`: the journal and the sitter are the state the scheduler test
// drives this file's emit/heartbeat/shutdown against, and only `var` reaches the
// script global a sandboxed load exposes.
var sitter, journal, alive = false, sealed = false;
// Same reason: the render guard's test drives a torn-down dialog through this
// set and resets the latch between cases, and neither a `const` nor a `let` at
// script top level reaches the sandbox global — the assignment silently lands on
// an unrelated property instead, and the reset reads as though it worked.
var buttons = new Set(), dialogs = new Set(), renderFailing = false;
// The two readings the diagnostics layer shows and nothing else needs.
// `environment` identifies the running build to a bug report; `admission` is the
// last set of resource numbers the gate actually read, as opposed to the verdict
// it reached. Both are `var` for the reason just above: tests/sdt_sitter_dialog.mjs
// drives the layer against them without standing up the whole of initialize().
var environment = {}, admission = null;
// `var` for the same sandbox reason as everything above: shutdown()'s teardown is
// driven directly by tests/sdt_sitter_scheduler.mjs, and the assertion that it
// cleared the three handles and burned the generation token can only be written
// against bindings a sandboxed load exposes. As `let` they were invisible, so the
// half of shutdown() that stops the sitter from rescheduling itself was checked by
// nothing (ticket 0695).
//
// Two tickets arrived at this line independently, which is worth recording rather
// than collapsing: 0696 needed `timers` for the other half of the same loop. The
// sweep reschedules through this handle, so a test that cannot install a clock
// cannot run the loop at all — and a loop nothing runs is where 0696's
// cross-generation defect hid from two suites at once, past a green mutation.
var timer, pulse, heartbeat, timers, notifierID;
// `var`, not `const`: ticket 0730 found that loading this file twice into one
// scope throws `Identifier '...' has already been declared` on the first
// `const`/`let` binding it reaches — a redeclaration `var` tolerates. Whether
// Zotero ever re-runs bootstrap.js into a scope it has already used is
// recorded in that ticket's log; every top-level binding in this file is
// `var` unconditionally so the question never matters again.
var closeJournalled = new WeakSet();
var BUTTON = 'sdt-pack-sitter-button';
// The overall-progress section, named once. `section()` builds its legend as
// `${id}-title`, and `renderState` recomposes that legend on every tick to carry
// the library scope (ticket 0717): two literals a rename could separate, where a
// missed one leaves `getElementById` returning null forever and the scope
// silently absent from a window that still renders. One binding, so the rename
// cannot be half-done.
var GLOBAL_SECTION = 'sdt-global-section';
var SWEEP_INTERVAL_MS = 30000;
var IDLE_SWEEP_INTERVAL_MS = 10 * 60 * 1000;
var RECONCILIATION_INTERVAL_MS = 60 * 60 * 1000;
// How long the end-of-sweep toast stays up. Presentation, like the 1400 ms
// completion blink and the 100 ms redraw beside it, so it lives here rather than
// in SPEC.md, which owns gates, decision rules and budgets. Long enough to read
// two short lines without looking up quickly, and comfortably shorter than the
// 30 s floor above, so two toasts can never be on screen at once.
var SWEEP_TOAST_MS = 8000;
var DEBUG_PREF = 'extensions.sdt-pack-sitter.debug';
/* R22's one obvious way, ratified 2026-09-08 (ticket 0742). Tri-state: unset
   means the question has never been answered, and is the ONLY state in which
   the launch prompt is shown. `true` and `false` are the user's own answer,
   and both hold across a restart and across a disable/re-enable, which is what
   R22 requires and what the old session-only decline never gave.

   Same mechanism and same naming as DEBUG_PREF above (ticket 0693), so a
   reader who found one in the Config Editor finds the other beside it. */
var ENABLED_PREF = 'extensions.sdt-pack-sitter.enabled';
// The generation token the armed loop belongs to. The dialog's switch can arm a
// sweep long after initialize() returned, and a sweep armed against a stale
// token is the cross-generation defect ticket 0696 shipped.
var activeToken = 0;
/* The sweep loop's own generation, burned every time the switch goes off. It is
   NOT `generation`: that one is the plugin's activation, and burning it here
   would stand down the cache writer and every other closure that reads it, for
   a switch flip that tears nothing down. See createSDTSweepLoop. */
var sweepGeneration = 0;
// SPEC.md owns these two numbers; this file needs them to compare against, and
// the diagnostics layer needs to print them. One statement each, so a threshold
// moved in the gate cannot leave a stale figure on screen beside the reading.
var MIN_FREE_MEMORY = 4 * 1024 ** 3, MIN_FREE_DISK = 8 * 1024 ** 3;
// Bootstrap reason constants are numeric here and named elsewhere; accept both.
var SHUTDOWN_REASONS = { 2: 'app-shutdown', 3: 'enable', 4: 'disable',
  5: 'install', 6: 'uninstall', 7: 'upgrade', 8: 'downgrade' };
// Also `var`, and 0696 needs it writable rather than merely readable: the
// disable/re-enable race IS a generation change, so a test that cannot move this
// number cannot stage the defect, and the guard against it would be asserted by
// reading the source — which is how the defect got in.
var generation = 0;
var lastCompleted = 0;
var completionBlinkUntil = 0;

/* What the first bytes of a source file prove about it, and which processor —
   if any — handles that format.

   `inspect()` classifies by the host's three `is*Attachment()` predicates, and
   every one of them reads `attachmentContentType`, a label recorded when the
   file was saved rather than a reading of the file. On the author's library
   eleven page scans are stored as `text/html` over JPEG bytes: they satisfy
   `isSnapshotAttachment()`, are admitted as snapshots, and native SDT finds no
   text in a photograph, persists no pack, and returns in 50–90 ms — every
   session, forever (ticket 0740). The author's rule: « ne pas croire
   l'étiquette, le B A BA du consommateur averti ».

   `processor: null` means no processor handles this format at all. A format
   whose bytes name a processor OTHER than the declared one is the same
   mismatch, so both cases are read the same way at the call site.

   The table is deliberately short of what a full sniffer would carry. HTML has
   no signature — a snapshot may open on a BOM, a comment, whitespace or a
   doctype — so this can only ever rule a document OUT, never in, and an
   unrecognised head means the label stands. Under-reaching here costs one
   failed extraction; over-reaching would stop admitting documents that extract
   perfectly well, which is the failure a fixture of failures alone cannot see.
   BMP ('BM') is left out for that reason: two bytes are not a proof. */
var SDT_SOURCE_MAGIC = [
  { format: 'jpeg', processor: null, prefix: [0xFF, 0xD8, 0xFF] },
  { format: 'png', processor: null, prefix: [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A] },
  { format: 'gif', processor: null, prefix: [0x47, 0x49, 0x46, 0x38] },
  { format: 'tiff', processor: null, prefix: [0x49, 0x49, 0x2A, 0x00] },
  { format: 'tiff', processor: null, prefix: [0x4D, 0x4D, 0x00, 0x2A] },
  { format: 'pdf', processor: 'pdf', prefix: [0x25, 0x50, 0x44, 0x46] },
  // EPUB is a zip, and so are a dozen other things; what this entry says is
  // narrower than "this is an EPUB" and is all the call site needs — a zip
  // container is not a snapshot and is not a PDF.
  { format: 'zip', processor: 'epub', prefix: [0x50, 0x4B, 0x03, 0x04] },
];
/* Derived from the table, never written down beside it. A constant would be
   right today by coincidence — PNG's eight bytes are the longest — and a
   signature added later that outran it would simply stop matching, silently and
   with nothing to catch it: `prefix.length <= head.length` is false, the entry
   is skipped, the label stands, and the document is submitted exactly as it was
   before the entry was added. */
var SDT_MAGIC_BYTES = SDT_SOURCE_MAGIC.reduce((n, entry) => Math.max(n, entry.prefix.length), 0);

/* The longest prefix above, read once. A read that fails answers `null`, which
   is the same answer as an unrecognised head: this function's job is to catch a
   label that is provably wrong, and a file it cannot read proves nothing. The
   file's absence is already `missing-source` two branches earlier. */
async function sniffSDTSource(path) {
  let head;
  try { head = await IOUtils.read(path, { offset: 0, maxBytes: SDT_MAGIC_BYTES }); }
  catch (_error) { return null; }
  return SDT_SOURCE_MAGIC.find(entry => entry.prefix.length <= head.length &&
    entry.prefix.every((byte, index) => head[index] === byte)) || null;
}

function compareSDTVersion(left, right) {
  const parse = value => String(value).split('.').map(part => /^\d+$/.test(part) ? Number(part) : NaN);
  const a = parse(left), b = parse(right);
  if (!a.length || !b.length || a.some(value => !Number.isSafeInteger(value)) || b.some(value => !Number.isSafeInteger(value))) return null;
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index++) {
    const delta = (a[index] ?? 0) - (b[index] ?? 0);
    if (delta) return Math.sign(delta);
  }
  return 0;
}

/* ---- the user-facing text, and the only place any of it lives ----

   ENGLISH ONLY, by the author's instruction of 2026-09-07: "REMOVE ALL THE
   MULTILINGUISM CODE. Revert to English." What was here was a Fluent layer
   with four locales, a fallback chain and a runtime file read (ticket 0692).
   It never once worked in a real Zotero: the module it imported does not
   exist in this host, and the `.ftl` files it fetched are unreadable inside a
   packed XPI, whose `rootURI` is a `jar:` URL no read API this plugin can
   reach will parse. Every string in the shipped window rendered as its own
   message id. Ticket 0727 has the measurements.

   So this is a table and a two-line formatter. `{name}` is substituted from
   the args object; an id the table does not carry returns as itself, which is
   Fluent's own convention and worth keeping -- it is visible in the window and
   it names exactly what is missing, where a throw here would go on throwing
   ten times a second under `render()`'s pulse.

   ADDING A STRING: put it in the table and read it with `sdtText`. Never a
   literal at the call site -- not for translation any more, but because the
   tooltip, the dialog and the toast must not word one count three ways, which
   is how the progress and error lines drifted apart before ticket 0691.
   `test_no_ui_site_keeps_a_sentence_of_its_own` still reddens on prose here.

   The two plural-sensitive entries are `[singular, plural]`, chosen by
   `count === 1`. That is an English rule in JavaScript, which is exactly what
   the Fluent selector existed to prevent -- correctly, while there were four
   languages, and pointlessly now that there is one.

   NO COMMENTS INSIDE THE TABLE. `tests/test_sdt_sitter.py` reads the wording by
   parsing this literal as JSON, which is what lets it argue with a rewording
   without a JavaScript engine; a `//` line in there fails fifteen tests at once
   with a decoder error that names nothing. Wording notes go here instead.

   Three of them, from ticket 0742:

   * "Waiting", never "Paused", for the phases the sitter gates itself on. The
     switch below owns "on" and "off", and a reader who met "Paused: processor
     busy" beside a switch he never touched would go looking for how to unpause
     something he never paused.
   * `launch-question` says neither "tonight" nor "whole library". The sweep
     reschedules for as long as Zotero is open, so nothing ends at dawn, and the
     census walks every attachment Zotero holds, which is not the library in
     view. What is left is the question actually being asked.
   * `launch-details` is the pointer that replaces two paragraphs of consent
     box. `launch-worker` and `launch-disable` are still here, and are now read
     in the window's Details layer, at any time, rather than once inside a modal
     that is the format least likely to be read at all.

   A fourth, from live testing of v0.3.18: the switch line and the raw
   "State: {phase}" line merged into one. The raw phase name in its own line
   said less than the window already knew, and read as a second,
   disconnected status next to the one the reader came to check. `switch-on-*`
   supplies the second half of a sentence whose first half is always
   `switch-on-prefix`; the full explanation of what "off" does and does not do
   still lives in the About disclosure, so `switch-off` only has to say what a
   glance needs. */
var SDT_TEXT = {
    "index": "Index",
    "index-coverage": "Index {percent} %",
    "scope-one": "Library: {names}",
    "scope-few": "Libraries: {names}",
    "scope-many": "All libraries ({count})",
    "files-indexed": [
      "{count} file indexed",
      "{count} files indexed"
    ],
    "phase-census": "Census",
    "phase-extracting": "Indexing under way",
    "phase-error": "Error",
    "phase-disabled": "Turned off",
    "phase-native-worker-busy": "Waiting: native indexing under way",
    "phase-cpu-busy": "Waiting: processor busy",
    "phase-low-memory": "Waiting: not enough memory",
    "phase-low-disk": "Waiting: not enough disk space",
    "phase-storage-unavailable": "Waiting: storage unavailable",
    "phase-resources-unavailable": "Waiting: system resources unreadable",
    "phase-off": "Indexing off",
    "dialog-title": "Indexing assistant",
    "switch-on-prefix": "Indexing is on.",
    "switch-off": "Indexing is off. Zotero will still index PDFs as you view them.",
    "switch-on-idle": "Nothing to index right now.",
    "switch-on-census": "Scanning the library for new or modified attachments.",
    "switch-on-extracting": "Extracting structured text from attachments.",
    "switch-on-error": "An unexpected problem stopped the last scan — see Technical diagnostics.",
    "diagnostics-internal-phase": "Internal phase: {phase}",
    "diagnostics-denominator-live": "The totals above track the library as it changes, not only a completed scan; a count can move without meaning anything is wrong.",
    "diagnostics-denominator-churn": " It moved by {delta} since you last opened this panel.",
    "switch-turn-on": "Turn indexing on",
    "switch-turn-off": "Turn indexing off",
    "section-global": "Overall progress",
    "section-active": "Indexing under way",
    "details-title": "Details",
    "not-indexed-title": "Not indexed",
    "not-indexed-title-count": "Not indexed ({count})",
    "not-indexed-none": "No observed obstacles to indexing.",
    "not-indexed-group-count": "{label} ({count})",
    "not-indexed-no-text": "No extracted text",
    "not-indexed-no-text-detail": "The stored index contains no text. OCR may help if the file consists of scanned images.",
    "not-indexed-session": "Extraction not completed this session",
    "not-indexed-session-detail": "The attachment becomes eligible for another attempt in a later session, subject to normal admission checks.",
    "not-indexed-examined": "Could not be examined",
    "not-indexed-examined-detail": "Inspection returned {class}.",
    "not-indexed-older-format": "Stored index uses an older format",
    "not-indexed-older-format-detail": "Whether Zotero can regenerate this format has not been established here.",
    "not-indexed-newer-format": "Stored index uses a newer format",
    "not-indexed-newer-format-detail": "A compatible Zotero version may be able to read this format.",
    "not-indexed-unordered-format": "Stored index format cannot be compared",
    "not-indexed-unordered-format-detail": "The stored index format cannot be ordered against this Zotero version.",
    "not-indexed-stored-file": "Stored file unavailable",
    "not-indexed-stored-file-detail": "The file is not available on this device. Zotero file sync may retrieve it if a remote copy is available and file sync is enabled.",
    "not-indexed-linked-file": "Linked file unavailable",
    "not-indexed-linked-file-detail": "The linked file is not available at its recorded location. Restoring the file or updating its link may make it accessible.",
    "not-indexed-no-extractor": "No extractor for this format",
    "not-indexed-no-extractor-detail": "The sitter has no extractor for this format. An alternative supported file may provide text.",
    "not-indexed-mismatched-type": "Recorded format differs",
    "not-indexed-mismatched-type-detail": "The file contents differ from the recorded format. A matching format record may allow extraction; image-only content may require OCR.",
    "not-indexed-no-attachment": "Entries without any attached file",
    "not-indexed-no-attachment-detail": "No file attachment is recorded. A file may be available from the publisher or another source.",
    "not-indexed-show": "Show in Zotero",
    "not-indexed-export": "Export list to clipboard",
    "not-indexed-show-tip": "Select every listed record in Zotero. This does not change the library.",
    "not-indexed-export-tip": "Copy every listed record to the clipboard. This does not change the library.",
    "not-indexed-selected": "Listed records selected in Zotero.",
    "not-indexed-selected-omitted": "Listed records selected; {count} were no longer available.",
    "not-indexed-select-unavailable": "The listed records could not be selected in Zotero.",
    "not-indexed-copied": "Listed records copied to the clipboard.",
    "not-indexed-copy-failed": "The list could not be copied to the clipboard.",
    "not-indexed-show-all": "Show all ({count} more)",
    "not-indexed-library": "Library: {library}",
    "not-indexed-library-count": "Library: {library} ({count})",
    "not-indexed-library-unavailable": "Library unavailable",
    "about-title": "About and limitations",
    "about-intro": "Zotero reads a PDF attachment's structured text — a pack, produced by its own native extractor and stored as .zotero-sdt-cache beside the attachment, in its own storage folder — the first time a feature needs it, which for most attachments is the first time you open them yourself. This assistant builds that pack ahead of time, one attachment at a time, across the whole library, instead of waiting for that moment.",
    "fulltext-title": "Full-text search index",
    "fulltext-body": "Zotero’s own full-text search index (distinct from the index the assistant prepares):",
    "fulltext-unavailable": "Statistics unavailable: {error}",
    "tech-title": "Technical diagnostics",
    "files-indexed-of": "Files indexed: {current} / {total}",
    "files-indexed-count": "Files indexed: {current}",
    "global-estimate": "Estimated finish around {median} (between {low} and {high})",
    "active-none": "No indexing under way",
    "active-preparing": "Preparing the next attachment…",
    "active-file": "Indexing: {file} — {progress} % — {elapsed} elapsed",
    "active-finalising": "Finishing…",
    "active-references": "Reading the references…",
    "active-estimate": "Estimated duration: {median} (between {low} and {high})",
    "files-failed": [
      "{count} file could not be indexed",
      "{count} files could not be indexed"
    ],
    "observations-waiting": "Observed durations: {count} (3 needed before any estimate)",
    "observations": "Observed durations: {count}",
    "observations-basis": "Observed durations: {count} — basis: {basis}",
    "basis-pages": "per page",
    "basis-bytes": "per byte",
    "reconciliation-never": "Coverage is last observed; a full reconciliation has not completed yet.",
    "reconciliation-age": "Coverage is last observed. Last full reconciliation: {age} ago.",
    "diagnostics-census": "{total} attachments in the library.",
    "diagnostics-completed": "Attachments indexed this session: {count}",
    "census-total-label": "Attachments counted in all",
    "status-current": "Indexed and up to date",
    "status-empty-pack": "No extracted text",
    "status-missing-pack": "Waiting to be indexed",
    "status-stale-source": "Changed since it was indexed",
    "status-stale-processor": "Indexed by an older extractor",
    "status-invalid-pack": "Stored index unreadable",
    "status-failed-session": "Extraction failed this session",
    "status-inspection-error": "Could not be examined",
    "status-unsupported-pack": "Stored index format requires review",
    "status-missing-source": "Stored or linked file unavailable",
    "status-excluded": "Trashed, or not an attachment",
    "status-unsupported": "No extractor or format mismatch",
    "diagnostics-error": "Last extraction problem: {error}",
    "cache-not-saved": "Cache not saved: {error}",
    "debug-label": "Log every step to Zotero’s debug output",
    "journal-copy": "Copy the log",
    "journal-copied": "Log copied to the clipboard.",
    "journal-copy-failed": "Copy failed: clipboard unavailable.",
    "journal-unreadable": "Log unreadable: {error}",
    "environment-version": "Add-on version: {version}",
    "environment-zotero": "Zotero: {version} (declared compatibility {min} – {max})",
    "environment-native": "Native format: version {format}, schema {schema}",
    "environment-extractors": "Native extractors: {extractors}",
    "environment-root": "Installed in: {root}",
    "admission-none": "No resource reading since startup.",
    "admission-age": "Last reading {age} ago — one reading per admission, none while the library is up to date",
    "admission-memory": "Memory available: {available} (threshold {threshold})",
    "admission-load": "Processor load: {load} on {cpus} cores",
    "admission-disk": "Disk space: {available} (threshold {threshold})",
    "gibibytes": "{value} GiB",
    "unknown-value": "?",
    "unit-seconds": "{count} s",
    "unit-minutes": "{count} min",
    "unit-hours-minutes": "{hours} h {minutes} min",
    "unit-minutes-seconds": "{minutes} min {seconds} s",
    "file-unknown": "unknown file",
    "file-number": "file no. {id}",
    "settle-failed": "“{file}” failed: {error}",
    "resources-read": "Reading resources: {error}",
    "launch-title": "Indexing assistant — experimental",
    "launch-question": "Index attachments in the background, from now on?",
    "launch-conditions": "One file at a time, with at least 4 GiB of memory available and 8 GiB of free disk. PDFs and the full-text search index settings are left untouched.",
    "launch-details": "This answer is remembered. The assistant's window carries what it does not control, and the switch that turns it off again.",
    "launch-yes": "Start indexing",
    "launch-no": "Not now",
    "launch-worker": "Extraction runs on a background process Zotero itself also uses, and it cannot be paused once a file has started: a large file can delay a smaller one that arrived just after it. The assistant starts a new file only when the current free memory and disk space meet its admission thresholds; those checks do not limit a file already being processed.",
    "launch-disable": "Turning indexing off stops the assistant from picking up new attachments; one already being processed still finishes. A failed extraction is only remembered for this session and is tried again the next time Zotero starts. A small file on disk remembers which attachments are already up to date and how long extraction usually takes — never their text, and never an unfinished job.",
    "about-updates": "After the first library pass, the assistant listens to Zotero attachment and file-download changes and rechecks only the affected records. It also reconciles the whole library every hour, so changes outside Zotero are eventually noticed."
  };

/* Every string a reader sees passes through here. */
function sdtText(id, args) {
  let pattern = SDT_TEXT[id];
  if (pattern === undefined) return id;
  if (Array.isArray(pattern)) pattern = Number(args && args.count) === 1 ? pattern[0] : pattern[1];
  return pattern.replace(/\{(\w+)\}/g, (whole, name) =>
    (args && name in args ? String(args[name]) : whole));
}

/* Numbers, in English. What used to sit at these call sites was a hardcoded
   French locale tag and a `.replace` of the point by a comma, which decided the
   decimal mark and the thousands separator for every reader in the world; that
   is still not something to write by hand, so the formatter stays. */
function sdtNumber(value, options) {
  try { return new Intl.NumberFormat('en', options).format(value); }
  catch (_error) { return String(value); }
}

/* The clock every DURATION in this file is measured on.

   `Date.now()` reads the calendar, and the calendar moves: NTP steps it, a
   laptop resuming from suspend steps it, and the author setting his own clock
   steps it by hours. A span computed across such a step is not merely imprecise,
   it changes sign — an elapsed line reading "-42 min", an empirical upper bound
   no document can exceed because the subtraction went negative, a heartbeat
   whose age is in the future. Nothing downstream re-checks the sign, because
   until now nothing could produce a negative one.

   Wall-clock time keeps the two uses that are honestly about the calendar: a
   journal record's `at`, and the projected finish time the dialog prints.
   Everything else — elapsed, silence, service time, the duration samples the
   estimator is fitted on, the age of a resource reading, the memoized-hash
   window — is a span, and reads this.

   Gecko's `ChromeUtils.now()` IS `TimeStamp::Now`, the process-monotonic clock
   the platform measures itself with; `performance.now()` is that same clock
   through the web API. Read at each call rather than resolved once into a
   `const`: this file is evaluated before `startup()` runs, and `ChromeUtils` is
   a global the host installs into the scope, so a load-time binding would
   capture nothing. Both reads are guarded for the reason `classifyError`
   carries — a diagnostic must never be the thing that stops the sitter.

   The last resort is the wall clock ratcheted to its own high-water mark. It
   cannot say how long a backwards step lasted, and no source without a
   monotonic clock can; what it can do is refuse to answer a negative duration,
   which is the failure this exists to end. */
var monotonicFloor = 0;
function monotonic() {
  try {
    if (typeof ChromeUtils === 'object' && typeof ChromeUtils.now === 'function') {
      const reading = ChromeUtils.now();
      if (Number.isFinite(reading)) return reading;
    }
  } catch (_error) { /* Fall through to the next source. */ }
  try {
    if (typeof performance === 'object' && typeof performance.now === 'function') {
      const reading = performance.now();
      if (Number.isFinite(reading)) return reading;
    }
  } catch (_error) { /* Fall through to the wall clock. */ }
  monotonicFloor = Math.max(monotonicFloor, Date.now());
  return monotonicFloor;
}

/* The sitter's whole diagnostic channel. Until the seal, the ring takes
   everything; Zotero.debug() takes everything but trace, which waits on the
   pref. The whole body is guarded: the invariant is that no diagnostic ever
   throws into the sitter loop, and a `detail` the ring rejects must not
   either. */
function emit(kind, detail, level = 'state') {
  // Sealed at shutdown, so nothing can land behind the shutdown record — an
  // invariant of the channel rather than a guard each call site has to remember.
  // Anything that resumes after an await outlives disable: the cache write, the
  // native promise, a dialog's unload.
  if (sealed) return;
  try {
    journal?.push({ at: Date.now(), kind, level, ...detail });
    // Fully qualified pref name: `true` stops Zotero prepending `extensions.zotero.`.
    if (level === 'trace' && !Zotero.Prefs.get(DEBUG_PREF, true)) return;
    Zotero.debug(`SDT sitter ${kind} ${JSON.stringify(detail ?? {})}`);
  } catch (_error) { /* Diagnostics must never throw into the sitter loop. */ }
}

/* The error's class reaches the journal; its message never does. Message text is
   free prose written by the platform, and it carries whatever it happens to name:
   a Gecko IO failure carries the file's full path, a parse failure carries the
   attachment's title. Zotero's debug output is submittable to Zotero's servers,
   so this is not session-confined. Three successive attempts to scrub that prose
   token by token each leaked — a stored filename is "Author - Year - Title.pdf",
   several whitespace-separated words of which a pattern anchored on runs of
   non-whitespace can only ever redact the one touching the extension. Prose and
   filenames are not separable by pattern, so the message is not carried at all.
   describeError still shows the author everything, on screen, locally, where it
   is his own library he is reading. The name is validated rather than trusted:
   a name with a space or a separator in it is a message wearing a name's clothes,
   and the whole body is guarded because a torn-down compartment can throw from
   a getter — this runs outside emit()'s guard, as its argument. */
function classifyError(error) {
  try {
    const name = error && error.name;
    return typeof name === 'string' && /^[\w.$-]{1,64}$/.test(name) ? name : 'Error';
  } catch (_error) {
    return '<unreadable error>';
  }
}

/* A beat for every phase the sitter can hang in, not only the one with a document
   under the worker. Ticket 0703: the census, host.list() and the whole blocked()
   admission check all run with `active` null, so the previous `active === null`
   gate was silent for precisely the phases whose hang left no trace after
   `cache-load`. `busy` is the scheduler's own outer-finally flag, so it goes
   false the instant sweep() exits — including the abort path, where `phase`
   stays stale at 'extracting'. The two ages are null-guarded because they are
   the age of a document, and during census there is none. */
function heartbeatTick() {
  if (!alive || !sitter) return;
  const s = sitter.state;
  if (!s.busy && s.active === null) return;
  const age = since => (since == null ? null : monotonic() - since);
  emit('heartbeat', { id: s.active, phase: s.phase, progress: s.progress,
    elapsedMS: age(s.startedAt), sinceProgressMS: age(s.lastProgressAt),
    pending: s.pending.length }, 'trace');
}

/* Queue retries do no discovery. Quiet libraries wait for reconciliation;
   notifications can wake the pump earlier. SPEC.md §5.2.7 owns the cadence. */
var SDT_BLOCKED_PHASES = ['cpu-busy', 'low-memory', 'low-disk', 'storage-unavailable', 'resources-unavailable'];
function nextSweepDelayMS(state) {
  if (state.busy) return SWEEP_INTERVAL_MS;
  const untilReconciliation = state.nextReconciliationAt == null ? SWEEP_INTERVAL_MS
    : Math.max(0, state.nextReconciliationAt - monotonic());
  const retry = SDT_BLOCKED_PHASES.includes(state.phase) ? IDLE_SWEEP_INTERVAL_MS
    : state.pending?.length || state.phase === 'error' || state.busy ? SWEEP_INTERVAL_MS : Infinity;
  return Math.min(untilReconciliation, retry);
}

function wakeSDTSitter() {
  if (!alive || !sitter?.state.enabled || sitter.state.busy) return;
  timers.clearTimeout(timer);
  timer = timers.setTimeout(createSDTSweepLoop(activeToken, sweepGeneration), 0);
}

/* Ticket 0696. One toast when a sweep actually did something, and nothing at all
   otherwise.

   THE GATE IS A DIFF, NOT A CALL. `nextSweepDelayMS` above reschedules for the
   life of the plugin, so a toast fired on every sweep would arrive every thirty
   seconds forever once the library is caught up — strictly worse than the
   per-file storm this exists to replace. `before` is the wrapper's own snapshot,
   taken ahead of the await: a sweep that admitted nothing, that the resource gate
   refused, or that returned early because one was already running leaves both
   counts equal and this says nothing.

   `failed` belongs in the gate beside `completed` because of how scheduler.js
   derives it — off the census, and only once the scan is whole — so it holds
   still across an idle sweep and moves only when the library did. An accumulated
   tally would drift by one sweep's failures every pass and toast on every one.

   There is no start toast. A sweep touches zero, one or many files, so there is
   no single title to name at its start, and the toolbar already spins on the
   active file and pulses through the census.

   Guarded whole, for the reason render() is. This runs on the sweep loop's own
   path, and an unguarded throw would be caught by the loop's `catch` and
   journalled as a sweep error — a record naming the wrong thing entirely.

   It sits here, beside the delay it shares a loop with, rather than beside the
   two composers it borrows from the UI vocabulary section below: what it is
   about is the sweep, and the wording it shows is not its own. */
function announceSDTSweep(before) {
  if (!alive || !sitter) return false;
  const s = sitter.state;
  if (s.completed === before.completed && s.failed === before.failed) return false;
  try {
    const toast = new Zotero.ProgressWindow();
    // The same message the status window's own title reads (ticket 0692). The
    // toast and the window are the same thing announcing itself, so naming it
    // twice would be two places for one name to drift.
    toast.changeHeadline(sdtText('dialog-title'));
    // One line each, rather than one string with a newline in it: the two counts
    // have different spans (the session's, and the last census's) and a reader
    // meets them as two statements on the tooltip and in the dialog too.
    for (const line of [describeSDTIndexed(s.completed), describeSDTFailures(s.failed)]) {
      if (line) toast.addDescription(line);
    }
    toast.show();
    toast.startCloseTimer(SWEEP_TOAST_MS);
    emit('toast', { completed: s.completed, failed: s.failed });
    return true;
  } catch (error) {
    emit('toast-error', { error: classifyError(error) }, 'error');
    return false;
  }
}

/* The sweep loop: one call, then the reschedule that keeps the sitter alive.

   Hoisted out of initialize() rather than left as a closure inside it, and the
   reason is a defect, not tidiness. Both suites could reach the toast and
   neither could reach the loop, so the two lines that MAKE the toast correct —
   where the snapshot is taken, and against which generation it is spent — were
   verified by reading source text and by nothing else. A mutation that welded
   the gate shut left all forty driven arms green. What is not runnable is not
   tested, and this file already learned that about the startup self-check
   (ticket 0688) and about render() (ticket 0702).

   `token !== generation` before the announcement, matching every other deferred
   callback in this file, and load-bearing rather than symmetric. `sitter` is a
   module-level binding that initialize() reassigns wholesale and shutdown()
   never clears, so `alive` and `sitter` can both be truthy and still belong to a
   DIFFERENT sitter than the one that filled `before`. The plugin's own launch
   prompt advertises the flow that gets there: disabling stops admissions but the
   file in flight finishes, so a disable during an uninterruptible ensure()
   followed by a re-enable leaves this closure suspended while initialize()
   installs a second sitter and sets `alive` back to true — and initialize() does
   both BEFORE its modal confirm, so no click is needed to open the window. The
   resumed closure would then diff one sitter's snapshot against another's
   counters and toast whatever the subtraction happened to say.

   TWO tokens, not one, and the second is ticket 0742's (found by review, not by
   the tests written for it). `generation` changes only when the plugin is torn
   down and stood back up; the user's own switch changes neither it nor `alive`,
   so a sweep suspended inside `ensure()` when the switch went off would run this
   `finally` with both checks satisfied and reschedule itself. Turning the switch
   back on then armed a SECOND loop beside the zombie, and the session ran two
   sweeps per interval for the rest of its life — the exact defect the comment on
   `armSDTSitter`'s `pulse` guard names, reached by a path that guard cannot see.
   `sweepGeneration` is burned by `disarmSDTSitter()` for the same reason
   `generation` is burned by `shutdown()`, and both are read here through
   `current()` so the announcement and the reschedule cannot drift apart.

   The reschedule below already carried the same check, for the neighbouring
   reason: a stale loop that rescheduled would run two sweeps per interval. It is
   in a `finally` because it is the single point whose loss stops the sitter for
   the session, so it must not depend on the sweep having returned normally — nor
   on this file being the only place a throw can come from. That is defence in
   depth behind render()'s own guard (ticket 0702), not a substitute for it.

   The snapshot is a copy of the two numbers, taken outside the try. A reference
   to `sitter.state` would read the same object twice and compare it with itself,
   which is a gate that never opens — the mutation above. Outside the try because
   there is nothing to catch: this reads two integers off a live binding, and if
   that binding is gone the loop has no sweep to run either. */
function createSDTSweepLoop(token, sweepToken) {
  const current = () => alive && token === generation && sweepToken === sweepGeneration;
  const owner = sitter;
  const sweep = async () => {
    if (!current()) return;
    const before = { completed: sitter.state.completed, failed: sitter.state.failed };
    try {
      await owner.pump();
      if (current()) announceSDTSweep(before);
    } catch (error) {
      emit('sweep-error', { error: classifyError(error) }, 'error');
    } finally {
      if (current()) {
        timers.clearTimeout(timer);
        timer = timers.setTimeout(sweep, nextSweepDelayMS(owner.state));
      }
    }
  };
  return sweep;
}

/* The failure half of settle. It goes to the session ring and Zotero.debug(),
   never to a file, for the reason createSDTJournal carries. The identity is the
   opaque cache key, never the attachment's title. */
function reportSettleFailure(info, error) {
  emit('settle', { id: info.cacheKey ?? null, ok: false, error: classifyError(error) }, 'error');
}

function noteDialogClose(dialog) {
  // `close()` may dispatch unload after shutdown has run; record it once, in order.
  if (closeJournalled.has(dialog)) return;
  closeJournalled.add(dialog);
  emit('dialog-close', {});
}

/* The denominator reads the same classification the scheduler admits from, so a
   status added to one class cannot leave the coverage line counting it under
   another (ticket 0699). During a census it reads the last complete snapshot,
   never the live `counts` being rebuilt from empty; current, failed, queued and
   out-of-scope therefore all name one generation (ticket 0718).

   `counts` is defaulted rather than dereferenced: the scheduler always
   initialises it, but before the scope prefix landed the tooltip never read
   coverage at all, so this function's required state shape widened onto the
   render path — where a throw has no guard above it — without the caller's
   shape being re-checked. The classification is defaulted for exactly that
   reason and not a different one: reading it widened the shape a second time,
   onto the same unguarded path, and it arrives with `scheduler.js`, which
   `initialize()` loads later than this file. Absent, the figure is unsayable
   rather than zero — `known: false` and an empty denominator, so the label
   composes to nothing. Rendering "0 %" there would be a wrong claim where the
   caller wants no claim. */
function getSDTCoverage(state) {
  // The one question that decides everything below: is `state.counts` right
  // now a COMPLETE classification, or a half-rebuilt one? Not "which phase
  // are we in" — `state.phase` becomes 'switched-off' the instant the switch
  // is thrown, whatever was under it, so it cannot tell a completed
  // classification from one caught and aborted mid-rebuild.
  // `scanned === total` can, but the two counters are set by two different
  // writers with two different meanings (ticket 0759): a full reconciliation
  // walk sets `total` once, up front, to the count it is about to reclassify,
  // then increments `scanned` one at a time — genuinely mid-rebuild while
  // `scanned < total`. Every ORDINARY per-item event (scheduler.js's
  // `record()`) instead sets `total = scanned = observed.size` together, in
  // one assignment, so it reads "complete" immediately, every time — which
  // is what makes this denominator live: the author ruled 2026-09-09 (ticket
  // 0759, ticket 0752's own event-driven library-state philosophy) that Y
  // should track real attachment churn as it happens rather than hold still
  // between reconciliations. A `2 -> 3 -> 2` sequence across two ordinary
  // events, with no reconciliation between them, is that ruling working as
  // intended, not a bug — each of the three counts is genuinely complete for
  // the library state at the instant it was read.
  //
  // Switching off used to freeze whatever `state.counts` held at that
  // instant unconditionally (ticket 0747) — right if the last walk had
  // finished, wrong if the sitter happened to be mid-way through a
  // reconciliation walk when the click landed: the reader froze on a
  // half-rebuilt classification, a different, plausible-looking wrong number
  // on every such off depending on exactly how far that walk had got when it
  // was cut off (found live, testing v0.3.20). `held` now stands in for the
  // live counts specifically when they are mid-rebuild, falling back to the
  // last walk that DID finish rather than to whichever fragment survives.
  const complete = state.scanned === state.total;
  const held = complete ? null : state.censusSnapshot;
  const counts = held ? held.counts : (state.counts || {});
  const censusTotal = held ? held.total : state.total;
  const classes = SDT_STATUS_CLASSES;
  const tally = keys => keys.reduce((n, key) => n + (counts[key] || 0), 0);
  const current = classes ? tally(classes.indexed) : 0;
  const unindexed = classes ? tally(classes.unindexed) : 0;
  const failed = classes ? tally(classes.failed) : 0;
  const queued = classes ? tally(classes.queued) : 0;
  const outOfScope = classes ? tally(classes.outOfScope) : 0;
  // `ready` is excluded even though 0 === 0 satisfies `complete` trivially:
  // a freshly booted sitter has finished no walk at all, and a lone "0
  // attachments" there would be a measurement where there is none.
  return { known: !!classes && (held ? true : complete && state.phase !== 'ready'),
    current, unindexed, failed, queued, outOfScope,
    total: classes ? Math.max(0, censusTotal - outOfScope) : 0 };
}

/* Every phase a reader can meet on hover, in the user's vocabulary. A blocked or
   failed sitter must be distinguishable from a healthy idle one at zero clicks,
   so each blocking reason gets its own plain sentence; the raw internal name
   stays in the diagnostics disclosure. `null` is the deliberate no-label case:
   the two healthy idle phases, where the count already says everything. An
   unlisted phase falls back to the scoped count rather than leaking its name.

   The values are message ids, not sentences: this table's job is the mapping
   from an internal phase to a decided label, and which language that label is
   written in is the `.ftl` files' job. Keeping the table means `phase in
   SDT_PHASE_LABELS` still answers "has this phase been decided about", which
   is what tests/sdt_sitter_scheduler.mjs asks of every phase it can enumerate. */
var SDT_PHASE_LABELS = {
  ready: null,
  waiting: null,
  census: 'phase-census',
  extracting: 'phase-extracting',
  error: 'phase-error',
  disabled: 'phase-disabled',
  'native-worker-busy': 'phase-native-worker-busy',
  'cpu-busy': 'phase-cpu-busy',
  'low-memory': 'phase-low-memory',
  'low-disk': 'phase-low-disk',
  'storage-unavailable': 'phase-storage-unavailable',
  'resources-unavailable': 'phase-resources-unavailable',
  // The user's own switch, off. Distinct from `disabled`, which is what the
  // scheduler reports when the whole plugin is being torn down: this one is a
  // state the plugin is running in, with a window and a control that leaves it.
  'switched-off': 'phase-off',
};

/* ---- the switch: R22's one obvious way (ticket 0742) ----

   Three functions and one pref. What they replace was two half-controls that
   between them satisfied neither clause of R22: add-on disable held across
   restarts but lived four clicks away in Tools -> Add-ons and removed the very
   window that would have shown the sitter stopped; declining the launch prompt
   was one click away and was forgotten by the next Zotero start, so the prompt
   came back every session and the answer meant nothing. */

/* `null` for "never answered", which is what makes the prompt a once-only
   event rather than a startup ritual. An unreadable pref reads as unanswered
   deliberately: asking a question that was already answered is a nuisance,
   where silently indexing on a machine whose answer could not be read is the
   thing the question exists to prevent. */
function readSDTSwitch() {
  try {
    const value = Zotero.Prefs.get(ENABLED_PREF, true);
    return typeof value === 'boolean' ? value : null;
  } catch (_error) { return null; }
}

/* Guarded like the debug pref's own write. A pref that will not persist leaves
   the session running on the answer just given — the wrong failure would be
   refusing to act on an answer the user did give. */
function writeSDTSwitch(enabled) {
  try { Zotero.Prefs.set(ENABLED_PREF, !!enabled, true); }
  catch (_error) { /* The next read falls back to asking again. */ }
  emit('switch', { enabled: !!enabled });
}

/* Labelled buttons, because OK/Cancel do not answer the question asked: a
   reader meeting `launch-question` over OK/Cancel has to work out which of the
   two means yes. `confirmEx` returns the index of the button pressed, and
   button 0 is the affirmative one.

   Three of the four paragraphs are gone: the worker limitation and the disable
   semantics moved into the dialog's Details layer, where they can be read at
   any time rather than once, inside the modal least likely to be read at all.

   The scope paragraph stays (ticket 0717), and stays SECOND, right under the
   question it qualifies. It is the same composer the tooltip and the dialog
   heading read, so a reader cannot be given three different answers to what the
   sitter covers, and it is dropped when nothing can be read — a prompt naming
   no scope is degraded, one naming a wrong scope is worse. That is also why the
   question itself no longer says "every library": the scope is a reading taken
   from Zotero's own records, not a claim this string can make. */
function askSDTLaunch(win) {
  const buttons = Services.prompt.BUTTON_POS_0 * Services.prompt.BUTTON_TITLE_IS_STRING +
    Services.prompt.BUTTON_POS_1 * Services.prompt.BUTTON_TITLE_IS_STRING;
  const body = [sdtText('launch-question'), describeSDTScope(),
    ...['launch-conditions', 'launch-details'].map(id => sdtText(id))]
    .filter(Boolean).join('\n\n');
  return Services.prompt.confirmEx(win, sdtText('launch-title'), body,
    buttons, sdtText('launch-yes'), sdtText('launch-no'), null, null, {}) === 0;
}

/* Arming and disarming, as the two halves of one switch rather than as
   initialize()'s tail and shutdown()'s teardown. The dialog can reach both, so
   both have to be reachable from outside initialize()'s closure — which is why
   the sweep loop was hoisted (see createSDTSweepLoop) and why `activeToken`
   exists at all.

   `pulse` is the idempotence guard: a second arm while the loop is running
   would leave two sweeps per interval and two render intervals, which is the
   defect a toggle clicked twice would otherwise produce for free. */
function armSDTSitter() {
  if (!alive || !sitter || pulse) return;
  sitter.start();
  pulse = timers.setInterval(render, 100);
  heartbeat = timers.setInterval(heartbeatTick, 60000);
  timer = timers.setTimeout(createSDTSweepLoop(activeToken, sweepGeneration), 0);
  render();
}

/* The graceful half, and deliberately the same semantics the 2026-09-05 ruling
   gave add-on disable: `stop()` ends admissions and breaks the census out of
   its loop, and an `ensure()` already handed to the native worker settles on
   its own. Nothing is cancelled; the sitter simply stops asking.

   `alive` stays true, which is the whole difference from shutdown(): the
   button and the window remain, so "off" is a state the user can see and
   leave, not the silence a removed UI leaves behind. */
function disarmSDTSitter() {
  // Burned FIRST, before anything can await: a sweep suspended inside `ensure()`
  // resumes into its `finally` with this already moved, so it declines to
  // reschedule instead of leaving a zombie chain the next arm would double.
  ++sweepGeneration;
  if (timers) { timers.clearTimeout(timer); timers.clearInterval(pulse); timers.clearInterval(heartbeat); }
  timer = pulse = heartbeat = undefined;
  sitter?.stop();
  if (sitter) sitter.state.phase = 'switched-off';
  render();
}

/* The dialog's control. It writes the pref FIRST, so a toggle that is followed
   by a crash still holds across the restart — the persistence is the
   requirement, the arming is the effect. */
function toggleSDTSwitch() {
  const turningOn = !!sitter && sitter.state.phase === 'switched-off';
  writeSDTSwitch(turningOn);
  if (turningOn) armSDTSitter(); else disarmSDTSitter();
}

/* One composer for the coverage percentage, so the toolbar strip and the tooltip
   cannot round or space it two different ways — the lesson describeSDTFile
   already carries for the file name. */
function describeSDTCoverage(state) {
  const coverage = getSDTCoverage(state);
  return coverage.total > 0
    ? sdtText('index-coverage',
      { percent: Math.floor((coverage.current / coverage.total) * 100) }) : '';
}

/* What the coverage figure is measured over. The button lives in the items
   toolbar, whose scope is one library and one collection, while the census reads
   every attachment in the database (see `list` below), so a reader is invited to
   take the figure for the collection in view. Naming a single library would
   replace one false scope with another; the honest prefix is the set the census
   actually covers, read from Zotero's own records — "Ma bibliothèque" is the
   user library's name, not a literal to hardcode, and a group library must read
   as itself. Each record is asked for its name separately because a group
   library is loaded lazily and can throw from its getter after a restart (the
   defect bench/zotero-fulltext-plugin/bootstrap.js records). Past three names the
   enumeration stops informing and the count does. Returns null when nothing can
   be read: an unscoped tooltip is degraded, a thrown one would kill the render
   loop.

   Feeds are dropped, and that exclusion is the same requirement as the rest of
   this function rather than a refinement of it. `Zotero.Libraries.getAll()`
   enumerates the whole library cache, which `init` fills with feeds alongside
   groups; a feed item carries no attachment, so no feed is in the set the census
   measures. Listing "Nature News" beside the user library, or counting it into
   "Toutes les bibliothèques (7)", would state a scope the figure was never
   measured over — the very failure the prefix exists to end.

   The whole body is inside the guard, not just the `getAll()` call: `render` and
   the pulse timer carry no `try` of their own, so anything escaping here escapes
   into a callback that fires ten times a second and would go on throwing for as
   long as the sitter is alive. A first version guarded only the call, which left
   the iteration itself — a `getAll()` returning something truthy and not
   iterable — outside the guard it was written for. */
function describeSDTScope() {
  try {
    const names = [];
    for (const library of Zotero.Libraries.getAll() || []) {
      let name;
      try {
        if (!library || library.libraryType === 'feed') continue;
        name = library.name;
      } catch (_error) { continue; }
      if (typeof name === 'string' && name.trim()) names.push(name.trim());
    }
    if (names.length === 0) return null;
    if (names.length === 1) return sdtText('scope-one', { names: names[0] });
    if (names.length <= 3) return sdtText('scope-few', { names: names.join(', ') });
    return sdtText('scope-many', { count: names.length });
  } catch (_error) { return null; }
}

/* The two running totals a reader is shown, each composed once. Both now reach
   three surfaces — the tooltip, the dialog, and the end-of-sweep toast — and
   three sites agreeing by coincidence is not agreement. The two composers above
   were each written after their sites had already drifted: describeSDTFile after
   the progress line and the error line came to name one file two different ways
   (ticket 0691, round 3), describeSDTCoverage before the toolbar strip and the
   tooltip could round one percentage two ways (ticket 0710). Here the shared
   quantity is a count and its plural agreement.

   The failure line is empty at zero rather than "0 file": a library with
   nothing wrong has nothing to say about failures, and the dialog's banner has
   read that way since ticket 0699. The indexed line is not, because it is the
   count itself and reads as a measurement even at zero. That emptiness stays
   here in JavaScript, because it is a decision about whether to show a line
   at all rather than about how to word one.

   The plural agreement itself does NOT stay here (ticket 0692). `count > 1` is
   a French rule written in JavaScript: French calls zero singular, English does
   not, and Vietnamese has one form for every count — no source language can
   hold that rule for the target one. So each composer keeps 0696's guarantee
   that the three surfaces cannot drift, and delegates the agreement to the
   locale's own plural rules through a Fluent `$count` selector. The two
   requirements are orthogonal and this is what satisfying both looks like. */
function describeSDTIndexed(count) {
  return sdtText('files-indexed', { count });
}

function describeSDTFailures(count) {
  if (!count) return '';
  return sdtText('files-failed', { count });
}

/* The order the account is read in, which is not the order a JavaScript object
   hands its keys over. It runs from what is done, through what is owed, to what
   failed, to what this add-on cannot index, to what was never its business — so
   a reader who stops after two rows has stopped at the two that answer "is it
   working".

   `excluded` is last, after `unsupported`, and that is the one position here
   chosen for a NEIGHBOURING list rather than for this one: "Not indexed" below
   ends on the same two obstacles this account does, and it can only do that if
   the row naming what is not an attachment at all sits past them. Trashed items
   and non-attachments are also the one row no obstacle group mirrors, so nothing
   is owed a place above them.

   A list, and not `Object.keys(SDT_STATUS_CLASSES).flat()`, because the classes
   partition by MEANING and this orders by READING; `queued` before `failed` is a
   choice about the reader, not a fact about the classification. The classes stay
   the single owner of which statuses exist — `tests/test_sdt_sitter.py` reads
   them and fails here for any status this list or the label table forgets. */
var SDT_STATUS_ORDER = ['current', 'empty-pack', 'missing-pack', 'stale-source', 'stale-processor',
  'invalid-pack', 'failed-session', 'inspection-error', 'unsupported-pack',
  'missing-source', 'unsupported', 'excluded'];

/* A status nobody has named renders as its own key rather than as the message id
   `sdtText` would otherwise hand back. Both are ugly; only one is greppable back
   to the scheduler that emitted it. */
function describeSDTStatusLabel(status) {
  const id = `status-${status}`;
  return id in SDT_TEXT ? sdtText(id) : status;
}

/* The census, as an account. Author's ruling of 2026-09-08, taken while he read
   this block on his own library.

   What it replaces printed the internal key as the label — `unsupported: 2600 /
   missing-source: 367 / failed-session: 39` — and then, below, a separate
   `Could not be indexed (last census): 406` that added 367 files merely absent
   from this disk to 39 real extraction failures. Two unrelated facts under one
   label, and this session's own analysis went wrong on that figure twice before
   the breakdown was read. The classes summed exactly, so the arithmetic was
   honest and only the presentation was not, which is the cheapest kind to
   repair: name every category in words, and put the total at the bottom, under
   the rows that make it up.

   The aggregate is not reworded, it is gone: each of its constituents now holds
   a row of its own, so the account carries strictly more than the line it
   replaced. The failure total a reader still meets is the layer-1 banner, whose
   span the account's own rows now explain. Why those files fail is ticket 0740;
   this owns only how they are shown.

   The total is summed from the rows PRINTED, never read off `state.total`: an
   account whose bottom line does not equal the column above it is worse than no
   bottom line, and the two diverge for real during a census, where `counts` is
   being rebuilt from empty while `total` still holds the last generation's.
   Zero rows are dropped — an account lists what is there — so the sum is over
   what a reader can actually add up. */
/* A real `<table>`, not padded text: a `<pre>` reflows to the dialog's own UI
   font (`font: inherit`, proportional), where no two space-padded columns of
   digits line up under each other — a right-aligned cell does, in any font
   (found live, testing v0.3.17, after the padded-text version had already
   shipped and still didn't align). Rebuilt whole on every call rather than
   diffed; the row count changes across a census and this runs far below
   10 Hz. */
function fillSDTTable(doc, tbody, entries, { totalRow = false } = {}) {
  const XHTML = 'http://www.w3.org/1999/xhtml';
  tbody.replaceChildren(...entries.map(([label, value], index) => {
    const row = doc.createElementNS(XHTML, 'tr');
    const labelCell = doc.createElementNS(XHTML, 'td');
    labelCell.textContent = label;
    const valueCell = doc.createElementNS(XHTML, 'td');
    valueCell.textContent = value;
    valueCell.style.cssText = 'text-align: right; padding-left: 1em; white-space: nowrap;';
    // A rule above the total, the way a reader expects a sum to be set off
    // from what it adds up (found live, testing v0.3.18) -- only when there
    // is more than one row, so a lone total is not drawn under a rule that
    // separates it from nothing.
    if (totalRow && index === entries.length - 1 && entries.length > 1) {
      labelCell.style.cssText = 'border-top: 1px solid GrayText; padding-top: 4px;';
      valueCell.style.cssText += 'border-top: 1px solid GrayText; padding-top: 4px;';
    }
    row.append(labelCell, valueCell);
    return row;
  }));
}

/* A key from Zotero's own statistics object, read as a label rather than a
   property name: camelCase and snake_case both split into words, and the
   first word capitalizes. Zotero's exact fields are unverified on this host
   (ticket 0746's own caveat), so this reads whatever the object holds rather
   than naming fields in advance. */
function humanizeSDTKey(key) {
  return String(key)
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .replace(/^./, c => c.toUpperCase());
}

function describeSDTCensusAccount(counts) {
  const tallied = counts || {};
  const extra = Object.keys(tallied).filter(status => !SDT_STATUS_ORDER.includes(status));
  const entries = [];
  let total = 0;
  for (const status of [...SDT_STATUS_ORDER, ...extra]) {
    const count = tallied[status] || 0;
    if (!count) continue;
    total += count;
    entries.push([describeSDTStatusLabel(status), sdtNumber(count)]);
  }
  // Before the first census `counts` is empty, and a lone "Attachments counted
  // in all: 0" there is a measurement where there is none — the same wrong claim
  // `getSDTCoverage` refuses when it makes the percentage unsayable rather than
  // zero. An account with no rows is not an account, so it is not printed; the
  // scan line above already says 0 / 0.
  if (!entries.length) return [];
  entries.push([sdtText('census-total-label'), sdtNumber(total)]);
  return entries;
}

/* Declaration order IS display order. It used to be neither: `collectSDTNotIndexed`
   filled a `Map` and handed back its insertion order, so the groups came out in
   the order the census walk happened to meet them — a list whose sequence
   changed with the library rather than with anything a reader could learn.

   The sequence follows the Details account above (`SDT_STATUS_ORDER`), because
   the two lists describe one library and a reader moving between them should not
   have to re-learn where to look. Where one status splits into two groups the
   split's own order is taken from the account row that owns it: "Stored or
   linked file unavailable" gives stored before linked, "No extractor or format
   mismatch" gives extractor before mismatch. `test_sdt_sitter.py` holds both
   halves — the projection onto the account order, and this sub-order.

   `no-attachment` is the exception and sits last on purpose. It has no census
   status at all (it comes off `unattached`, bibliographic records rather than
   attachments), so the account order cannot place it, and it is the one group
   that is not an obstacle to extraction: there is nothing to extract. */
/* The library subsections of one group, in reading order: the personal library
   first, then groups by name, then whatever could not be named.

   This is the same defect the group order above was fixed for, one level down
   and found by sweeping for it: the subsections came out of a `Map` filled by
   the census walk, so a reader with a group library met his own library first
   in one group and second in the next, and the sequence moved whenever the
   library did. Ruled by the author, 2026-09-10, and it is Zotero's own order in
   the items pane — the panel should not teach a second one.

   `libraryType === 'user'` is the discriminator rather than an id compared
   against 1: `describeSDTScope` above already reads that field, a library id is
   a local number this file has no business predicting, and the same read tells
   a group from a feed.

   Every read is inside the guard, for the reason `describeSDTScope` carries in
   full: a group library is loaded lazily and its getter can throw after a
   restart, and this runs on the render path. A library that throws keeps its
   subsection and loses its name, which is what the unavailable heading is for.

   The collation is pinned to 'en' for the reason `sdtNumber` is: the host's
   locale is not this file's to guess, and an unpinned comparator sorts
   differently on two machines reading one library. Names are compared, so the
   last tie-break is the id — two libraries that cannot be named are otherwise
   indistinguishable to the sort and would fall back to the walk order this
   function exists to leave behind. */
function orderSDTLibraries(libraries) {
  const rank = [];
  for (const [libraryID, members] of libraries) {
    let libraryName = null;
    let personal = false;
    try {
      const library = libraryID == null ? null : Zotero.Libraries.get(libraryID);
      const name = library?.name;
      if (typeof name === 'string' && name.trim()) libraryName = name;
      personal = library?.libraryType === 'user';
    } catch (_error) { /* The displayed generation remains usable without a name. */ }
    rank.push({ libraryID, libraryName, personal, members });
  }
  return rank.sort((a, b) =>
    (Number(b.personal) - Number(a.personal))
    || (Number(a.libraryName == null) - Number(b.libraryName == null))
    || (a.libraryName == null ? 0 : a.libraryName.localeCompare(b.libraryName, 'en'))
    || String(a.libraryID).localeCompare(String(b.libraryID), 'en'));
}

var SDT_NOT_INDEXED_GROUPS = {
  'empty-pack': { title: 'not-indexed-no-text', detail: 'not-indexed-no-text-detail' },
  'failed-session': { title: 'not-indexed-session', detail: 'not-indexed-session-detail' },
  'inspection-error': { title: 'not-indexed-examined', detail: 'not-indexed-examined-detail' },
  'older-format': { title: 'not-indexed-older-format', detail: 'not-indexed-older-format-detail' },
  'newer-format': { title: 'not-indexed-newer-format', detail: 'not-indexed-newer-format-detail' },
  'unordered-format': { title: 'not-indexed-unordered-format', detail: 'not-indexed-unordered-format-detail' },
  'missing-source-stored': { title: 'not-indexed-stored-file', detail: 'not-indexed-stored-file-detail' },
  'missing-source-linked': { title: 'not-indexed-linked-file', detail: 'not-indexed-linked-file-detail' },
  'no-extractor': { title: 'not-indexed-no-extractor', detail: 'not-indexed-no-extractor-detail' },
  'mismatched-type': { title: 'not-indexed-mismatched-type', detail: 'not-indexed-mismatched-type-detail' },
  'no-attachment': { title: 'not-indexed-no-attachment', detail: 'not-indexed-no-attachment-detail' },
};

function collectSDTNotIndexed(state) {
  const members = state.censusSnapshot?.members || [];
  const grouped = new Map();
  const add = (groupID, member) => {
    if (!(groupID in SDT_NOT_INDEXED_GROUPS)) return;
    if (!grouped.has(groupID)) grouped.set(groupID, []);
    grouped.get(groupID).push(member);
  };
  for (const member of state.censusSnapshot?.unattached || []) add('no-attachment', member);
  for (const member of members) {
    const groupID = member.status === 'missing-source'
      ? (member.linked ? 'missing-source-linked' : 'missing-source-stored')
      : member.status === 'unsupported'
        ? (member.reason === 'mismatched-type' ? 'mismatched-type' : 'no-extractor')
        : member.status === 'unsupported-pack'
          ? (member.reason || 'unordered-format') : member.status;
    add(groupID, member);
  }
  // Declaration order, not the `Map`'s insertion order: see SDT_NOT_INDEXED_GROUPS.
  // `add` already refuses an id the table does not name, so nothing is dropped here.
  return Object.keys(SDT_NOT_INDEXED_GROUPS)
    .filter(id => grouped.has(id))
    .map(id => ({ id, members: grouped.get(id) }));
}

function fillSDTNotIndexed(doc, container, state) {
  const groups = collectSDTNotIndexed(state);
  const total = groups.reduce((count, group) => count + group.members.length, 0);
  const section = container.parentNode;
  const sectionSummary = section.querySelector?.('summary') || section.childNodes?.[0];
  if (sectionSummary) sectionSummary.textContent = sdtText('not-indexed-title-count', { count: sdtNumber(total) });
  const signature = JSON.stringify(groups.map(group => [group.id, group.members.map(member =>
    [member.itemID ?? member.id, member.libraryID ?? null, member.title ?? null, member.parentTitle ?? null,
      member.key ?? null, member.errorClass ?? null]) ]));
  if (container._sdtSignature === signature) return;
  container._sdtSignature = signature;
  container.replaceChildren();
  if (!groups.length) {
    section.hidden = false;
    const empty = doc.createElementNS('http://www.w3.org/1999/xhtml', 'p');
    empty.textContent = sdtText('not-indexed-none'); container.append(empty);
    return;
  }
  section.hidden = false;
  const make = tag => doc.createElementNS('http://www.w3.org/1999/xhtml', tag);
  const line = member => {
    const label = member.parentTitle ? `${member.parentTitle} — ${member.title || sdtText('file-number', { id: member.itemID ?? member.id })}`
      : member.title || sdtText('file-number', { id: member.itemID ?? member.id });
    return String(label).replace(/[\r\n]+/g, ' ');
  };
  for (const group of groups) {
    const definition = SDT_NOT_INDEXED_GROUPS[group.id];
    const details = make('details');
    details.style.setProperty('margin-top', '8px'); details.style.setProperty('margin-left', '18px');
    const summary = make('summary'); summary.textContent = sdtText('not-indexed-group-count', {
      label: sdtText(definition.title), count: sdtNumber(group.members.length) });
    summary.style.setProperty('font-size', '1em'); summary.style.setProperty('font-weight', '600');
    summary.style.setProperty('margin-top', '4px'); summary.style.setProperty('margin-bottom', '4px');
    const explanation = make('p');
    explanation.textContent = group.id === 'inspection-error'
      ? sdtText(definition.detail, { class: group.members[0].errorClass || 'Error' }) : sdtText(definition.detail);
    details.append(summary, explanation);
    const libraries = new Map();
    for (const member of group.members) {
      const key = member.libraryID ?? null;
      if (!libraries.has(key)) libraries.set(key, []);
      libraries.get(key).push(member);
    }
    for (const { libraryID, libraryName, members } of orderSDTLibraries(libraries)) {
      const libraryHeading = make('h4');
      libraryHeading.textContent = libraryName ? sdtText('not-indexed-library-count', {
        library: libraryName, count: sdtNumber(members.length) })
        : `${sdtText('not-indexed-library-unavailable')} (${sdtNumber(members.length)})`;
      libraryHeading.style.setProperty('font-size', '0.95em'); libraryHeading.style.setProperty('font-weight', '600');
      libraryHeading.style.setProperty('margin-top', '10px'); libraryHeading.style.setProperty('margin-bottom', '2px');
      libraryHeading.style.setProperty('margin-left', '18px');
      const list = make('ul');
      const appendTitle = member => { const item = make('li'); item.textContent = line(member); list.append(item); };
      // The controls capture every displayed member below. Only title rendering
      // is deferred, keeping an initially opened group responsive.
      const preview = members.slice(0, 1);
      for (const member of preview) appendTitle(member);
      const controls = make('div');
      // Align actions with list text rather than the enclosing disclosure, and
      // leave the larger gap below to close this library subsection before the
      // next one begins.
      controls.style.setProperty('margin-left', '40px');
      controls.style.setProperty('margin-top', '4px');
      controls.style.setProperty('margin-bottom', '18px');
      const feedback = make('span'); feedback.setAttribute('aria-live', 'polite');
      const ids = members.map(member => member.itemID ?? member.id).filter(Number.isInteger);
      const exported = members.map(member => `${line(member)}\t${member.libraryID ?? '?'}:${member.key ?? member.itemID ?? member.id}`)
        .join('\n');
      const select = make('button'); select.setAttribute('type', 'button');
      select.textContent = sdtText('not-indexed-show'); select.setAttribute('title', sdtText('not-indexed-show-tip'));
      select.addEventListener('click', async () => {
        try {
          const pane = Zotero.getMainWindow?.()?.ZoteroPane;
          if (!pane || !ids.length || typeof pane.selectItems !== 'function') throw new Error('unavailable');
          const records = await Promise.all(ids.map(id => Zotero.Items.getAsync(id)));
          const surviving = records.filter(record => record && !record.deleted && record.libraryID === libraryID)
            .map(record => record.id);
          if (!surviving.length) throw new Error('unavailable');
          await pane.selectItems(surviving);
          feedback.textContent = surviving.length === ids.length ? sdtText('not-indexed-selected')
            : sdtText('not-indexed-selected-omitted', { count: ids.length - surviving.length });
        } catch (_error) { feedback.textContent = sdtText('not-indexed-select-unavailable'); }
      });
      const copy = make('button'); copy.setAttribute('type', 'button');
      copy.textContent = sdtText('not-indexed-export'); copy.setAttribute('title', sdtText('not-indexed-export-tip'));
      copy.addEventListener('click', () => { feedback.textContent = copySDTText(exported)
        ? sdtText('not-indexed-copied') : sdtText('not-indexed-copy-failed'); });
      controls.append(select, copy, feedback);
      if (preview.length < members.length) {
        const showAllItem = make('li');
        const showAll = make('button'); showAll.setAttribute('type', 'button');
        showAll.textContent = sdtText('not-indexed-show-all', { count: sdtNumber(members.length - preview.length) });
        showAll.addEventListener('click', () => {
          let next = preview.length;
          showAllItem.remove();
          const appendNext = () => {
            if (next >= members.length) return;
            appendTitle(members[next++]); timers.setTimeout(appendNext, 0);
          };
          appendNext();
        });
        showAllItem.append(showAll); list.append(showAllItem);
      }
      details.append(libraryHeading, list, controls);
    }
    container.append(details);
  }
}

/* The switch line and the phase both answered in one sentence (found live,
   testing v0.3.18) rather than the on/off half beside an unrelated raw phase
   name shown in a different part of the window. "On" carries a
   phase-specific second half; a resource-blocked phase reuses the label the
   toolbar tooltip already shows, so the two never say the same fact two
   different ways. */
function describeSDTSwitchLine(state) {
  if (state.phase === 'switched-off') return sdtText('switch-off');
  const detail = state.phase === 'census' ? sdtText('switch-on-census')
    : state.phase === 'extracting' ? sdtText('switch-on-extracting')
    : state.phase === 'error' ? sdtText('switch-on-error')
    : SDT_PHASE_LABELS[state.phase] ? sdtText(SDT_PHASE_LABELS[state.phase])
    : sdtText('switch-on-idle');
  return `${sdtText('switch-on-prefix')} ${detail}`;
}

/* Four segments joined by one em dash.

   Before the first census there is no percentage, and the bare word "Index"
   between two em dashes says nothing the rest of the line does not: that
   segment is dropped rather than left dangling. The scope is not — which
   libraries the sitter is about is true before any figure exists. The phase
   label is a segment in its own right for the same reason it used to be
   concatenated with the same em dash: one separator, one place. */
function describeSDTTooltip(state) {
  const label = SDT_PHASE_LABELS[state.phase];
  return [describeSDTScope(), describeSDTCoverage(state), label && sdtText(label),
    describeSDTIndexed(state.completed)].filter(Boolean).join(' — ');
}

/* The unit of work is one attachment, and Zotero names attachments for us
   ('Full Text PDF', 'Snapshot'), so the attachment title alone identifies
   nothing. Lead with the reference that owns it. One composer, so the progress
   line and the error line cannot drift into naming the same file two ways. */
function describeSDTFile(info, fallback) {
  const { parentTitle, title } = info || {};
  if (parentTitle && title) return `${parentTitle} — ${title}`;
  return parentTitle || title || fallback;
}

function describeSDTActiveFile(state) {
  return describeSDTFile(state.activeInfo, sdtText('file-number', { id: state.active }));
}

/* ---- the third layer: what a bug report asks for and a reader never does ---- */

function formatSDTBytes(bytes) {
  // The decimal mark is the locale's, not this file's: `toFixed` produces a
  // point and the old `.replace('.', ',')` produced a comma, and exactly one of
  // those two is right for any given reader.
  return Number.isFinite(bytes)
    ? sdtText('gibibytes', { value: sdtNumber(bytes / 1024 ** 3,
      { minimumFractionDigits: 1, maximumFractionDigits: 1 }) })
    : sdtText('unknown-value');
}

/* Which build is running, and where it was installed from. Ticket 0688 put this
   in the debug log because a plugin that vanishes leaves nothing else behind;
   the same facts belong on screen, because the author reading the window is the
   one who will be asked which version he was running. */
function describeSDTEnvironment() {
  const native = environment.packVersions || {};
  const unknown = sdtText('unknown-value');
  return [
    sdtText('environment-version', { version: environment.version ?? unknown }),
    sdtText('environment-zotero', { version: environment.zoteroVersion ?? unknown,
      min: environment.strictMinVersion ?? unknown,
      max: environment.strictMaxVersion ?? unknown }),
    sdtText('environment-native', { format: native.SDT_PACK_VERSION ?? unknown,
      schema: native.SDT_SCHEMA_VERSION ?? unknown }),
    sdtText('environment-extractors',
      { extractors: JSON.stringify(native.SDT_PROCESSOR_VERSIONS ?? null) }),
    sdtText('environment-root', { root: environment.rootURI ?? unknown }),
  ].join('\n');
}

function formatSDTAge(ms) {
  const seconds = Math.max(0, Math.round(ms / 1000));
  if (seconds < 60) return sdtText('unit-seconds', { count: seconds });
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? sdtText('unit-minutes', { count: minutes })
    : sdtText('unit-hours-minutes',
      { hours: Math.floor(minutes / 60), minutes: minutes % 60 });
}

/* The numbers behind the gate's verdict. A sitter that says "En pause : mémoire
   insuffisante" states a conclusion; only the reading says how far from the
   threshold it was, which is the difference between waiting and closing a
   browser. Absent until the first admission is attempted, and it says so rather
   than printing zeros that would read as measurements.

   The age leads, because these readings go stale silently and there is no
   plausible way to keep them fresh: blocked() is called once per candidate, so
   a caught-up library stops taking readings altogether and the panel would
   otherwise show hours-old numbers indistinguishable from live ones. Saying
   when, and why there may be no newer reading, is the honest fix; polling
   /proc from render() ten times a second to keep a diagnostic warm is not. */
function describeSDTAdmission() {
  if (!admission) return sdtText('admission-none');
  return [
    // `monotonic()`, from ticket 0695: the age of a reading is a SPAN, and the
    // calendar moves under a span. Its wording is this ticket's `.ftl`; its
    // clock is that ticket's, and the merge keeps both.
    sdtText('admission-age', { age: formatSDTAge(monotonic() - admission.at) }),
    sdtText('admission-memory', { available: formatSDTBytes(admission.memoryAvailableBytes),
      threshold: formatSDTBytes(MIN_FREE_MEMORY) }),
    // The load average is a bare number from /proc; passed as a NUMBER so that
    // Fluent's own NumberFormat gives it the same decimal mark as the two byte
    // readings beside it, whatever locale that is.
    admission.load === undefined ? ''
      : sdtText('admission-load', { load: admission.load, cpus: admission.cpus }),
    admission.diskAvailableBytes === undefined ? ''
      : sdtText('admission-disk', { available: formatSDTBytes(admission.diskAvailableBytes),
        threshold: formatSDTBytes(MIN_FREE_DISK) }),
  ].filter(Boolean).join('\n');
}

/* The ring, rendered whole rather than field by field, and unlike the clipboard
   copy below it is NOT scrubbed: this is the author's own screen, reading his
   own machine, and the panel prints the install path two lines above anyway.
   A whitelist here would only hide a record kind added later. Guarded because
   this runs from render(), and a throw there stops the redraw loop. */
function describeSDTJournalTail(limit = 50) {
  try {
    return Array.from(journal ? journal.tail(limit) : [], record => {
      const { at, kind, level, ...rest } = record;
      return `${new Date(at).toLocaleTimeString('en', { hour12: false })} ${level} ${kind} ${JSON.stringify(rest)}`;
    }).join('\n');
  } catch (error) {
    return sdtText('journal-unreadable', { error: classifyError(error) });
  }
}

/* The ring is path-free where the sitter writes it — that is emit()'s and
   classifyError()'s whole job. One record is not, and it is not an accident:
   ticket 0688's `startup` carries the install root deliberately, so a plugin
   that vanishes can be traced back to a build. That decision is about Zotero's
   debug log, which the author opts into knowingly.

   This button is a new door, opened here, and it must not widen what leaves by
   a field nobody asked it to carry. The ring survives a disable/re-enable
   (`journal ??=` in initialize) — which the sitter's own "désactiver puis
   réactiver" wording tells the author to do — so on that second startup the
   record lands in the ring as well, and a verbatim tail would put a home
   directory on the clipboard. Omitting `rootURI` as a top-level field is not
   enough; it has to be dropped from the records too.

   Dropped by name, and that is sound here where 0689's token-wise scrubbing of
   prose was not: this is a structured field with a known key, so the drop is
   total and has no partial case. What it does not cover is a future record kind
   carrying a path under some other key — no pattern can promise that either, so
   the guard is the assertion in tests/sdt_sitter_dialog.mjs that the composed
   text holds no scheme and no home directory, run against a ring the real
   startup path contaminated. */
var CLIPBOARD_OMITTED = ['rootURI'];

function scrubSDTRecord(record) {
  const copy = { ...record };
  for (const field of CLIPBOARD_OMITTED) delete copy[field];
  return copy;
}

/* What the copy action puts on the clipboard, and therefore what may be pasted
   into a bug report. The install path stays on screen, two lines above in the
   same panel, where the author is reading his own machine. The versions travel,
   because a ring with no build attached answers nothing. */
function composeSDTJournalReport() {
  try {
    return JSON.stringify({
      version: environment.version ?? null,
      zoteroVersion: environment.zoteroVersion ?? null,
      nativeVersions: environment.packVersions ?? null,
      records: journal ? Array.from(journal.tail(50), scrubSDTRecord) : [],
    }, null, 2);
  } catch (error) {
    return sdtText('journal-unreadable', { error: classifyError(error) });
  }
}

/* Two clipboards, because the one a chrome about:blank window has is not the one
   Zotero exposes and neither is guaranteed across host versions. The boolean is
   the point: a copy that silently does nothing is worse than one that says so. */
function copySDTText(text) {
  try { Zotero.Utilities.Internal.copyTextToClipboard(text); return true; }
  catch (_error) { /* Fall through to the platform service. */ }
  try {
    Cc['@mozilla.org/widget/clipboardhelper;1'].getService(Ci.nsIClipboardHelper).copyString(text);
    return true;
  } catch (_error) { return false; }
}

/* Layer 3, built once with the dialog. Native controls only — a <details>, a
   checkbox carrying a real <label for>, a <button> — so keyboard reach comes
   from the platform instead of from key handling this file would have to get
   right, which is the half of 0686 a source review cannot certify anyway. */
/* A separate disclosure for what the reader would call "About": the two
   paragraphs ticket 0742 moved out of the launch modal, and the version and
   compatibility lines that used to sit inside the debug/log disclosure
   instead. Found live, testing v0.3.16: both belong together, and neither
   belongs beside a journal tail and a resource reading, which a reader opens
   to debug a problem rather than to learn what the add-on does or does not
   do. Composed once, like the disclosures already were — this text never
   changes across a render. */
function buildSDTAbout(doc, element) {
  const group = element('details', 'sdt-about-details');
  group.style.setProperty('margin-top', '14px'); group.style.setProperty('margin-left', '18px');
  const summary = element('summary', 'sdt-about-title');
  summary.textContent = sdtText('about-title');
  summary.style.setProperty('font-size', '1.1em'); summary.style.setProperty('font-weight', '650');
  summary.style.setProperty('margin-top', '6px'); summary.style.setProperty('margin-bottom', '6px');
  // What the plugin does and why, ahead of its limitations (found live,
  // testing v0.3.19): a reader who opens "About" reasonably expects to be
  // told what the thing is before being told what it cannot do.
  const intro = element('pre', 'sdt-about-intro');
  intro.textContent = sdtText('about-intro');
  const disclosures = element('pre', 'sdt-disclosures');
  disclosures.textContent = ['launch-worker', 'launch-disable', 'about-updates']
    .map(id => sdtText(id)).join('\n\n');
  // Static About facts precede the explanatory paragraphs: a reader sees the
  // installed version and compatibility before the qualifications that follow.
  group.append(summary, intro, element('pre', 'sdt-environment'), disclosures);
  return group;
}

function buildSDTDiagnostics(doc, element) {
  const group = element('details', 'sdt-tech-details');
  group.style.setProperty('margin-top', '14px'); group.style.setProperty('margin-left', '18px');
  const summary = element('summary', 'sdt-tech-title');
  summary.textContent = sdtText('tech-title');
  summary.style.setProperty('font-size', '1.1em'); summary.style.setProperty('font-weight', '650');
  summary.style.setProperty('margin-top', '6px'); summary.style.setProperty('margin-bottom', '6px');
  const row = element('div', 'sdt-debug-row');
  const toggle = element('input', 'sdt-debug');
  toggle.setAttribute('type', 'checkbox');
  const label = element('label', 'sdt-debug-label');
  label.setAttribute('for', toggle.id);
  label.textContent = sdtText('debug-label');
  row.append(toggle, label);
  toggle.addEventListener('change', () => {
    // Fully qualified, like every other read of this pref.
    try { Zotero.Prefs.set(DEBUG_PREF, !!toggle.checked, true); }
    catch (_error) { /* An unwritable pref is reported by the next render's reread. */ }
    emit('debug-pref', { enabled: !!toggle.checked });
  });
  const copy = element('button', 'sdt-journal-copy');
  copy.setAttribute('type', 'button');
  copy.textContent = sdtText('journal-copy');
  copy.addEventListener('click', () => {
    doc.getElementById('sdt-journal-copy-status').textContent =
      sdtText(copySDTText(composeSDTJournalReport()) ? 'journal-copied' : 'journal-copy-failed');
  });
  // Author's ruling of 2026-09-08: "Observed durations" is technical diagnostics
  // and belongs here, not among the primary readings. It leads the layer because
  // it is the one line that explains a number shown above — the estimate rests on
  // this count and this covariate — where everything below is about the add-on
  // rather than about the library.
  group.append(summary, element('pre', 'sdt-observations'), element('pre', 'sdt-internal-phase'),
    element('pre', 'sdt-denominator-note'),
    element('pre', 'sdt-error'), row,
    element('pre', 'sdt-admission'),
    copy, element('pre', 'sdt-journal-copy-status'), element('pre', 'sdt-journal'));
  return group;
}

/* Whether the reader has asked the platform for less motion (ticket 0686).

   Three things move in the toolbar strip — the spinner, the census pulse and
   the completion blink — and none of them carries information the label and the
   tooltip do not already state in words. `prefers-reduced-motion` is a system
   preference rather than a taste, and on the platforms that expose it, it is
   set by people for whom the animation is a symptom, not a nuisance. So all
   three stop together: suppressing one and leaving the others would honour the
   preference on paper and not on screen.

   Read per node, because a media query is answered by the window and the
   plugin puts a button in every main window; read through `ownerDocument`,
   because inside the render loop that node is the only handle on its window
   there is. Guarded and defaulting to motion, because this runs ten times a
   second: a window whose docshell is going away throws from `matchMedia`, and
   an unguarded throw here would take out the render loop rather than one
   frame of an animation — the class the render() wrapper below records. The
   guard is silent, deliberately: it fires during teardown, on every button, at
   10 Hz, and journalling it would evict the ring the wrapper's own record
   lives in. A scenario in tests/sdt_sitter_bootstrap.mjs makes matchMedia
   throw, so this catch has been seen to hold rather than assumed to. */
function prefersSDTReducedMotion(node) {
  try {
    return node?.ownerDocument?.defaultView
      ?.matchMedia('(prefers-reduced-motion: reduce)')?.matches === true;
  } catch (_error) { return false; }
}

/* Ticket 0702. renderState() runs unguarded DOM work over `dialogs`, and it is
   reached from publish(), which the scheduler calls from inside its own finally.
   A throw there — a dead XUL dialog after its window closed, getElementById
   returning null mid-render — rejected sitter.sweep(), so the wrapper that
   reschedules the next sweep never ran and the sitter stopped for the rest of
   the session while `phase` still read 'waiting'. Indistinguishable from working.

   The failure is recorded on its transition, not on its tick: the pulse calls
   this at 10 Hz, and a persistent broken dialog emitting every time would evict
   the whole 2000-record ring in under four minutes — destroying exactly the
   evidence ticket 0703 keeps. The layer above widens what runs under it, which
   is the reason this guard is worth more now than when it was written. */
function render() {
  try {
    renderState();
    renderFailing = false;
  } catch (error) {
    if (renderFailing) return;
    renderFailing = true;
    emit('render-error', { error: classifyError(error) }, 'error');
  }
}

function renderState() {
  if (!alive || !sitter) return;
  const s = sitter.state;
  const coverage = getSDTCoverage(s);
  for (const button of buttons) {
    // Composed here rather than hoisted, so the toolbar strip and the tooltip
    // read as the two call sites of one composer at the sites themselves. The
    // composer now carries the word as well as the figure — before the first
    // census there is no percentage, and the button still has to say what it is.
    // Off reads as off, in plain words, at zero clicks. A coverage percentage
    // beside a sitter that is not indexing states a figure and hides the one
    // fact the reader needs (ticket 0742); the label table owns the wording so
    // the button and the tooltip cannot say it two ways.
    const coverageLabel = s.phase === 'switched-off'
      ? sdtText(SDT_PHASE_LABELS['switched-off'])
      : describeSDTCoverage(s) || sdtText('index');
    const working = s.phase === 'census' || s.active !== null;
    // The blink deadline and the two animation phases are all spans, so they
    // read the monotonic clock: a wall-clock step backwards would otherwise
    // freeze the spinner for as long as the step lasted.
    const now = monotonic();
    if (s.completed > lastCompleted) {
      lastCompleted = s.completed;
      completionBlinkUntil = now + 1400;
    }
    const still = prefersSDTReducedMotion(button);
    const spinning = s.active !== null && !still;
    const blinking = !working && !still && now < completionBlinkUntil;
    button.setAttribute('label', spinning
      ? `${['◐', '◓', '◑', '◒'][Math.floor(now / 140) % 4]} ${coverageLabel}` : coverageLabel);
    // The name a screen reader speaks, pinned to the figure alone. In XUL the
    // `label` IS the accessible name, and the frame advances every 140 ms — so
    // the spinner rewrites that name a little over seven times a second, and a
    // reader following the button learns nothing from any of them. Whether
    // `aria-label` in fact wins the accname computation on a XUL toolbarbutton,
    // and whether Gecko re-announces on an identical-value write at 10 Hz, are
    // readings for the Accessibility Inspector in a live window; neither is
    // established here. `aria-label` overrides that name, and
    // it changes only when the coverage does, which is the one thing here
    // worth announcing (ticket 0686).
    button.setAttribute('aria-label', coverageLabel);
    const opacity = still ? 1
      : s.phase === 'census'
        ? 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(now / 450))
        : blinking ? ((Math.floor(now / 180) % 2) ? 0.2 : 1) : 1;
    button.style.setProperty('opacity', String(opacity), 'important');
    button.setAttribute('tooltiptext', describeSDTTooltip(s));
  }
  for (const dialog of dialogs) {
    if (dialog.closed) { dialogs.delete(dialog); continue; }
    const doc = dialog.document;
    const status = doc.getElementById('sdt-status');
    if (!status) continue;
    // The switch, reread from the sitter's own phase rather than from the pref:
    // the two agree, and the phase is what every other line in this window is
    // drawn from, so a disagreement shows here instead of hiding.
    const off = s.phase === 'switched-off';
    doc.getElementById('sdt-switch-state').textContent = describeSDTSwitchLine(s);
    doc.getElementById('sdt-switch').textContent =
      sdtText(off ? 'switch-turn-on' : 'switch-turn-off');
    const elapsed = s.active === null ? null : Math.round((monotonic() - s.startedAt) / 1000);
    const silence = s.active === null ? null : Math.round((monotonic() - s.lastProgressAt) / 1000);
    const formatDuration = ms => {
      const minutes = Math.max(1, Math.round(ms / 60000));
      return minutes < 60 ? sdtText('unit-minutes', { count: minutes })
        : sdtText('unit-hours-minutes',
          { hours: Math.floor(minutes / 60), minutes: minutes % 60 });
    };
    const formatDocumentDuration = ms => {
      const seconds = Math.max(0, Math.round(ms / 1000));
      if (seconds < 60) return sdtText('unit-seconds', { count: seconds });
      // The seconds are zero-padded, so they are passed as text: a number would
      // go through Fluent's NumberFormat and come back as "7" where the column
      // wants "07".
      return sdtText('unit-minutes-seconds', { minutes: Math.floor(seconds / 60),
        seconds: String(seconds % 60).padStart(2, '0') });
    };
    const activePrediction = s.active === null ? null : estimateSDTDuration(s.fittedSamples, s.activeInfo);
    const total = { low: 0, median: 0, high: 0 };
    const overrun = activePrediction && monotonic() - s.startedAt > activePrediction.high;
    // The one wall-clock reading left in this loop, and it is not a span: a
    // finish time is a point on the author's calendar, which is exactly what a
    // monotonic clock cannot name (ticket 0695). The offset added to it IS a
    // span, so it comes from the totals above. Its LOCALE decides the field
    // order and not merely the separators — 05/09 and 09/05 are the same
    // instant and two different dates to two readers (ticket 0692).
    const finishAt = ms => new Date(Date.now() + ms).toLocaleString('en',
      { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    let unknown = 0;
    for (const item of s.pending) {
      const prediction = estimateSDTDuration(s.fittedSamples, item);
      if (!prediction) { unknown++; continue; }
      const spent = item.id === s.active ? monotonic() - s.startedAt : 0;
      for (const key of ['low', 'median', 'high']) total[key] += Math.max(0, prediction[key] - spent);
    }
    if (unknown && s.fittedSamples.length >= 3) {
      const durations = s.fittedSamples.map(sample => sample.milliseconds).sort((a, b) => a - b);
      const quantile = fraction => durations[Math.min(durations.length - 1,
        Math.floor((durations.length - 1) * fraction))];
      total.low += unknown * quantile(0.05);
      total.median += unknown * quantile(0.5);
      total.high += unknown * quantile(0.95);
    }
    // The scope of the figures under it is stated before the reader can
    // misread them (ticket 0717): the progress bar and the file count below
    // are the whole census, and "Overall progress" alone invites the reader
    // of a dialog opened from one collection's toolbar to read them as that
    // collection's. It moved out of the bold `<legend>` into a plain line of
    // its own (found live, testing v0.3.18): three long library names joined
    // into a heading wrapped five lines on a narrow window, where the same
    // text as an ordinary line wraps like any other sentence in the window.
    // Composed here rather than at populate time, and through the same
    // composer the tooltip uses, because a group library loads lazily — text
    // frozen when the dialog opened would name a set the census no longer
    // covers.
    doc.getElementById('sdt-scope').textContent = [describeSDTScope(),
      s.lastReconciliationAt == null ? sdtText('reconciliation-never')
        : sdtText('reconciliation-age', { age: formatDocumentDuration(monotonic() - s.lastReconciliationAt) })
    ].filter(Boolean).join('\n');
    const globalProgress = doc.getElementById('sdt-global-progress');
    globalProgress.max = Math.max(1, coverage.total);
    if (coverage.known) globalProgress.value = coverage.current;
    else globalProgress.removeAttribute('value');
    status.textContent = coverage.known
      ? sdtText('files-indexed-of', { current: coverage.current, total: coverage.total })
      : sdtText('files-indexed-count', { current: coverage.current });
    // Found live, testing v0.3.19: the box still blinked between documents
    // even with its height reserved, because the text itself flashed to "No
    // indexing under way" for real, however briefly — scheduler.js awaits
    // twice (`host.yield()`, `host.blocked()`) between one document settling
    // and the next being admitted, and `state.active` genuinely reads null
    // for that span. `state.pending` still names what is queued behind it,
    // so a reader is not told nothing is happening when something is about
    // to be.
    const activeMessage = s.active === null
      ? (s.pending && s.pending.length > 0 ? sdtText('active-preparing') : sdtText('active-none'))
      : sdtText('active-file', { file: describeSDTActiveFile(s),
        progress: s.progress ?? sdtText('unknown-value'),
        elapsed: formatDocumentDuration(elapsed * 1000) });
    const quietMessage = s.active !== null && Number(s.progress) >= 90 && silence >= 60
      ? sdtText(Number(s.progress) >= 95 ? 'active-finalising' : 'active-references') : '';
    doc.getElementById('sdt-document-status').textContent = [activeMessage, quietMessage].filter(Boolean).join('\n');
    doc.getElementById('sdt-document-estimate').textContent = activePrediction
      ? sdtText('active-estimate', { median: formatDocumentDuration(activePrediction.median),
        low: formatDocumentDuration(activePrediction.low),
        high: formatDocumentDuration(activePrediction.high) }) : '';
    const globalEstimate = !overrun && s.scanned === s.total && s.fittedSamples.length >= 3
      ? sdtText('global-estimate', { median: finishAt(total.median),
        low: finishAt(total.low), high: finishAt(total.high) }) : '';
    doc.getElementById('sdt-global-estimate').textContent = globalEstimate;
    // Failures were reachable only by opening the diagnostics. Surface the
    // count — through the composer, so this banner and the toast cannot word
    // one number two ways, and its plural comes from the locale.
    doc.getElementById('sdt-failures').textContent = describeSDTFailures(s.failed);
    // Order matters, and it is the ruling's: the scan's own progress, then the
    // session counter — and only then the account (its own table, below this
    // text). The cache warning is an exception rather than a row, and appears
    // only when there is one. The raw phase name moved to Technical
    // diagnostics and the state of the machine into the switch line itself,
    // in words (found live, testing v0.3.18): "State: extracting" said less
    // than the window already knew, next to the line that says the same fact
    // in a sentence. The error moved there too a round earlier (v0.3.17): a
    // single extraction failure is routine and already carries its own row in
    // the account below, and reading it as "Error:" at the top overclaimed
    // what one failed attachment among many means.
    // Before host.list() has ever resolved, `total` still holds its initial
    // 0 -- not a measurement of an empty library, but the absence of one,
    // exactly the distinction `describeSDTCensusAccount` already draws for
    // its own rows. `censusSnapshot` is null in that state and in no other:
    // once a census completes, even on a genuinely empty library, publish()
    // sets a real (if empty) snapshot, so this line becomes true the moment
    // there is anything to be true about (found live, testing v0.3.20).
    const totalKnown = s.total > 0 || s.censusSnapshot !== null;
    doc.getElementById('sdt-diagnostics').textContent = [
      totalKnown ? sdtText('diagnostics-census', { total: s.total }) : '',
      // `completed` accumulates over the whole session and says so; it is not a
      // census class and does not belong among the rows the census total sums.
      sdtText('diagnostics-completed', { count: s.completed }),
      // The cache is derived and disposable, so a failed write changes nothing
      // about what is indexed and belongs in the disclosure rather than beside
      // the totals — but it was set and read nowhere at all, which made an
      // unwritable data directory a silence instead of a line.
      s.cacheWarning || '',
    ].filter(Boolean).join('\n');
    // Rebuilt only when the account itself changed, not on every 100 ms tick:
    // `replaceChildren` tears the table down to rebuild it, and doing that
    // ten times a second whether or not a single number moved is a visible
    // flicker in the very layer a reader has open to watch a census update
    // (found live, testing v0.3.18). The signature lives on the dialog, not
    // in a module-level variable — a second open window's table must still
    // fill on its own first render even if it happens to match what another
    // window already shows.
    const accountEntries = describeSDTCensusAccount(s.counts);
    const accountSignature = JSON.stringify(accountEntries);
    if (dialog._censusSignature !== accountSignature) {
      dialog._censusSignature = accountSignature;
      fillSDTTable(doc, doc.getElementById('sdt-census-body'), accountEntries, { totalRow: true });
    }
    fillSDTNotIndexed(doc, doc.getElementById('sdt-not-indexed-body'), s);
    const progress = doc.getElementById('sdt-progress');
    progress.hidden = s.active === null;
    if (s.active !== null && Number.isFinite(s.progress)) progress.value = s.progress;
    else progress.removeAttribute('value');
    // Layer 3 since the ruling of 2026-09-08. What the estimates above rest on:
    // how many durations were kept, and which covariate carried the fit. An
    // estimate whose basis is unreadable is a number the reader has no way to
    // disbelieve — but it is a reading about the machine, not about the library,
    // which is what put it below rather than beside the numbers it explains.
    // Composed unconditionally, unlike the ring: this is one short line, where
    // rendering the ring whole behind a closed disclosure is the work nobody sees.
    const fit = s.activeInfo ? estimateSDTDuration(s.fittedSamples, s.activeInfo) : null;
    doc.getElementById('sdt-observations').textContent = s.fittedSamples.length < 3
      ? sdtText('observations-waiting', { count: s.fittedSamples.length })
      : fit ? sdtText('observations-basis', { count: s.fittedSamples.length,
        basis: sdtText(fit.basis === 'pages' ? 'basis-pages' : 'basis-bytes') })
        : sdtText('observations', { count: s.fittedSamples.length });
    // Layer 3. The checkbox is reread rather than written once, so a pref changed
    // from Zotero's own advanced settings is not silently contradicted here.
    const technical = doc.getElementById('sdt-tech-details');
    const about = doc.getElementById('sdt-about-details');
    const toggle = doc.getElementById('sdt-debug');
    try {
      const enabled = !!Zotero.Prefs.get(DEBUG_PREF, true);
      if (toggle.checked !== enabled) toggle.checked = enabled;
    } catch (_error) { /* An unreadable pref must not fight the checkbox. */ }
    // Only while each is open. This loop runs ten times a second and the ring
    // is rendered whole; behind a closed disclosure that is work nobody can
    // see. The environment line moved to its own disclosure (About), open and
    // closed independently of the debug/log one beside it.
    if (about.open) doc.getElementById('sdt-environment').textContent = describeSDTEnvironment();
    if (technical.open) {
      doc.getElementById('sdt-internal-phase').textContent =
        sdtText('diagnostics-internal-phase', { phase: s.phase });
      // Ticket 0759: Y is live-tracked by design (the author's ruling, given
      // the churn this note itself explains), not a bug to hide -- so this is
      // disclosure, not damage control, and it only exists on demand behind
      // this closed-by-default panel. The baseline is taken once, at the
      // closed-to-open transition, and held while the panel stays open -- not
      // reread every ~100 ms tick, which would make the delta flash for one
      // frame and vanish the instant it had anything to say. So "since you
      // opened this panel" means exactly that, including a churn that keeps
      // growing while the reader watches.
      if (!dialog._sdtDenominatorOpen) dialog._sdtDenominatorAt = s.total;
      dialog._sdtDenominatorOpen = true;
      const delta = s.total - dialog._sdtDenominatorAt;
      doc.getElementById('sdt-denominator-note').textContent = sdtText('diagnostics-denominator-live') +
        (delta !== 0 ? sdtText('diagnostics-denominator-churn', { delta: delta > 0 ? `+${delta}` : `${delta}` }) : '');
      doc.getElementById('sdt-error').textContent =
        s.error ? sdtText('diagnostics-error', { error: s.error }) : '';
      doc.getElementById('sdt-admission').textContent = describeSDTAdmission();
      doc.getElementById('sdt-journal').textContent = describeSDTJournalTail(50);
    } else {
      // Closing the panel forgets the baseline, so the NEXT open takes a fresh
      // reading rather than comparing against whatever the library looked like
      // several opens ago.
      dialog._sdtDenominatorOpen = false;
    }
  }
}

function openDialog(window) {
  for (const existing of dialogs) {
    if (!existing.closed) {
      existing.focus();
      emit('dialog-open', { reused: true });
      render();
      return existing;
    }
    dialogs.delete(existing);
  }
  const dialog = window.openDialog('about:blank', 'sdt-pack-sitter-status',
    'chrome,dialog=no,resizable,width=700,height=650');
  emit('dialog-open', { reused: false });
  dialog.addEventListener('unload', () => { dialogs.delete(dialog); noteDialogClose(dialog); }, { once: true });
  // A bare `chrome,dialog=no` window carries none of a XUL <dialog>'s built-in
  // key bindings, so Escape does nothing unless asked to (found live, testing
  // v0.3.15). `dialog.close()` is the same call the window's own unload path
  // already goes through, so this adds no second way to tear the window down.
  dialog.addEventListener('keydown', event => { if (event.key === 'Escape') dialog.close(); });
  const populate = async () => {
    if (!alive || dialog.closed) return;
    const doc = dialog.document;
    doc.title = sdtText('dialog-title');
    const body = doc.body || doc.documentElement;
    body.replaceChildren();
    // A bare chrome about:blank window does not inherit Zotero's opaque surface.
    doc.documentElement.style.cssText = 'background: Canvas; color: CanvasText; color-scheme: light dark; min-height: 100%;';
    body.style.cssText = 'background: Canvas; color: CanvasText; margin: 0; padding: 16px; box-sizing: border-box; min-height: 100vh; font: menu;';
    const element = (tag, id) => {
      const node = doc.createElementNS('http://www.w3.org/1999/xhtml', tag);
      node.id = id;
      if (tag === 'progress') { node.max = 100; node.style.width = '100%'; }
      else if (tag === 'table') node.style.cssText = 'border-collapse: collapse; margin: 8px 0;';
      else if (tag === 'tbody') { /* rows carry their own cell styling */ }
      else node.style.cssText = 'white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.5;';
      return node;
    };
    const section = (id, title, children) => {
      const group = element('fieldset', id);
      group.style.cssText = 'border: 1px solid GrayText; border-radius: 6px; padding: 12px; margin: 0 0 16px; min-width: 0;';
      const legend = element('legend', `${id}-title`);
      legend.textContent = title; legend.style.fontWeight = 'bold';
      group.append(legend);
      for (const [tag, childID] of children) {
        const node = element(tag, childID);
        if (tag === 'progress') node.setAttribute('aria-labelledby', legend.id);
        group.append(node);
      }
      body.append(group);
    };
    /* Layer 1's first line, above every reading: the one switch (ticket 0742).
       First because it is the answer to the only question a user opens this
       window in a hurry to ask — how do I stop this — and because R22's "one
       obvious way" is not obvious three sections down. A native <button>, so
       keyboard reach and the accessible name come from the platform, exactly as
       the diagnostics layer's controls do. */
    const control = element('div', 'sdt-switch-row');
    // The salient state leads, in reading order, as everywhere else in this
    // window — but "on" and "off" describe very different lengths of text, and
    // a button placed right after that text moves sideways every time the
    // reader clicks it (found live, testing v0.3.15). `space-between` pins the
    // button to the row's fixed right edge regardless of how long the state
    // text runs, rather than to wherever that text happens to end.
    control.style.cssText = 'display: flex; gap: 12px; align-items: center; ' +
      'justify-content: space-between; margin: 0 0 16px;';
    const state = element('span', 'sdt-switch-state');
    // The state text is prose and may wrap; `min-width: 0` is what lets a flex
    // child actually shrink to make room instead of forcing the row wider.
    state.style.cssText += 'flex: 1 1 auto; min-width: 0;';
    const toggle = element('button', 'sdt-switch');
    toggle.setAttribute('type', 'button');
    // `element()`'s default styling is written for the prose blocks and
    // carries `white-space: pre-wrap`, which let the button's own two words
    // wrap onto two lines and turn it into a square at some widths, a
    // rectangle at others (found live, testing v0.3.17). A button is not
    // prose; it keeps its native single-line sizing.
    toggle.style.cssText = 'white-space: nowrap; flex-shrink: 0;';
    toggle.addEventListener('click', () => toggleSDTSwitch());
    control.append(state, toggle);
    body.append(control);
    // Layer 1, always visible and always first: progress, what is being worked
    // on, how long it has taken and when it should end. Nothing below is needed
    // to read any of it.
    section(GLOBAL_SECTION, sdtText('section-global'), [
      ['pre', 'sdt-scope'],
      ['pre', 'sdt-status'], ['progress', 'sdt-global-progress'], ['pre', 'sdt-global-estimate'],
      ['pre', 'sdt-failures']]);
    section('sdt-document-section', sdtText('section-active'), [
      ['pre', 'sdt-document-status'], ['progress', 'sdt-progress'], ['pre', 'sdt-document-estimate']]);
    // A filename can take three lines, followed by the finalising note. Reserve
    // all four lines rather than the old two-line case so progress updates do
    // not resize the fieldset. The estimate is independently reserved because
    // it appears only after enough observations have accumulated.
    doc.getElementById('sdt-document-status').style.minHeight = '6em';
    doc.getElementById('sdt-document-estimate').style.minHeight = '3em';
    // Layer 2, closed: the census account, and the native index's own statistics
    // below it. 0686 asked for exactly this — technical detail kept, moved below
    // primary progress. The fit behind the estimates used to sit here too and no
    // longer does: the ruling of 2026-09-08 put it a layer further down, with the
    // rest of what is about the machine rather than about the library.
    const details = element('details', 'sdt-details');
    const summary = element('summary', 'sdt-details-title');
    summary.textContent = sdtText('details-title');
    summary.style.setProperty('font-size', '1.35em'); summary.style.setProperty('font-weight', '700');
    summary.style.setProperty('margin-top', '4px'); summary.style.setProperty('margin-bottom', '12px');
    const censusTable = element('table', 'sdt-census-table');
    censusTable.append(element('tbody', 'sdt-census-body'));
    details.append(summary, element('pre', 'sdt-diagnostics'), censusTable);
    const notIndexed = element('details', 'sdt-not-indexed');
    notIndexed.style.setProperty('margin-top', '14px'); notIndexed.style.setProperty('margin-left', '18px');
    const notIndexedSummary = element('summary', 'sdt-not-indexed-title');
    notIndexedSummary.textContent = sdtText('not-indexed-title');
    notIndexedSummary.style.setProperty('font-size', '1.1em'); notIndexedSummary.style.setProperty('font-weight', '650');
    notIndexedSummary.style.setProperty('margin-top', '6px'); notIndexedSummary.style.setProperty('margin-bottom', '6px');
    notIndexed.append(notIndexedSummary, element('div', 'sdt-not-indexed-body'));
    details.append(notIndexed);
    const indexDetails = element('details', 'sdt-index-details');
    indexDetails.style.setProperty('margin-top', '14px'); indexDetails.style.setProperty('margin-left', '18px');
    const indexSummary = element('summary', 'sdt-index-title');
    indexSummary.textContent = sdtText('fulltext-title');
    indexSummary.style.setProperty('font-size', '1.1em'); indexSummary.style.setProperty('font-weight', '650');
    indexSummary.style.setProperty('margin-top', '6px'); indexSummary.style.setProperty('margin-bottom', '6px');
    const fulltextTable = element('table', 'sdt-fulltext-table');
    fulltextTable.append(element('tbody', 'sdt-fulltext-body'));
    indexDetails.append(indexSummary, element('pre', 'sdt-fulltext'), fulltextTable);
    details.append(indexDetails);
    // Layer 3, nested inside layer 2 and closed in its turn, each discoverable
    // without being in the way. About (the two consent-box disclosures ticket
    // 0742 moved out of the launch modal, plus the version/compatibility
    // lines) is its own disclosure, apart from the debug/log one below it —
    // found live, testing v0.3.16: a reader opens one of these to learn what
    // the add-on does or does not do, and the other to chase a problem, and a
    // journal tail buried the former inside the latter.
    details.append(buildSDTAbout(doc, element));
    details.append(buildSDTDiagnostics(doc, element));
    body.append(details);
    dialogs.add(dialog); render();
    try {
      const stats = await Zotero.Fulltext.getIndexStats();
      // A raw JSON dump reads as a debug printout, not as an account (found
      // live, testing v0.3.15) — the same real table the census uses, over
      // whatever fields this Zotero build's own statistics carry.
      const rows = Object.entries(stats || {}).map(([key, value]) =>
        [humanizeSDTKey(key), typeof value === 'number' ? sdtNumber(value) : String(value)]);
      if (alive && !dialog.closed) {
        doc.getElementById('sdt-fulltext').textContent = sdtText('fulltext-body');
        fillSDTTable(doc, doc.getElementById('sdt-fulltext-body'), rows);
      }
    } catch (error) {
      if (alive && !dialog.closed) doc.getElementById('sdt-fulltext').textContent =
        sdtText('fulltext-unavailable', { error: String(error) });
    }
  };
  if (dialog.document.readyState === 'complete') populate();
  else dialog.addEventListener('load', populate, { once: true });
}

function onMainWindowLoad({ window }) {
  if (!alive || window.document.getElementById(BUTTON)) return;
  const toolbar = window.document.getElementById('zotero-items-toolbar');
  if (!toolbar) return;
  const button = window.document.createXULElement('toolbarbutton');
  button.id = BUTTON;
  // Zotero's toolbar styles otherwise constrain this to an icon-sized square.
  button.style.setProperty('min-width', '80px', 'important');
  button.style.setProperty('width', 'auto', 'important');
  button.style.setProperty('max-width', 'none', 'important');
  button.style.setProperty('flex-shrink', '0', 'important');
  button.style.setProperty('padding-inline', '8px', 'important');
  button.addEventListener('command', () => openDialog(window));
  toolbar.append(button); buttons.add(button); render();
}
function onMainWindowUnload({ window }) {
  for (const button of buttons) if (button.ownerDocument === window.document) {
    button.remove(); buttons.delete(button);
  }
}

/* The host HANDS us the version, and that is the only way we can have it.

   `data.version` and `data.id` come from the add-on record Zotero already
   built; nothing is read to obtain them. The self-check below used to parse
   `manifest.json` for the version instead, which cannot work in an installed
   add-on: `rootURI` is `jar:file:///….xpi!/` and `Zotero.File` cannot parse a
   `jar:` URI, so every startup since ticket 0688 recorded
   `version: "unreadable (NS_ERROR_FAILURE)"`. The instrumentation 0688 added
   to say WHICH BUILD was running when the plugin vanished has therefore never
   once said it — the same defect that made every UI string render as its own
   id, in the one place whose whole job was to leave evidence (ticket 0727). */
var installedVersion = null;

function startup({ rootURI, version }) {
  const token = ++generation;
  installedVersion = typeof version === 'string' ? version : null;
  timers = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  // Addon startup is serialized. Never hold it on UI readiness or a modal prompt.
  timer = timers.setTimeout(() => initialize(rootURI, token).catch(error => Zotero.logError(error)), 0);
}
/* Ticket 0688. The plugin "tends to disappear on its own from the installed-plugins
   list" and left nothing behind saying which build was running when it did. Raw
   values, no compatibility-range parsing: `strict_max_version` against
   `Zotero.version` is exactly the comparison the host already made, and a second
   verdict here could only disagree with it.

   Every read is guarded, because this runs as an ARGUMENT to emit() and therefore
   outside emit()'s own guard — the hazard classifyError() above carries for the
   same reason. `JSON.parse` of a document that is not an object is the case the
   first draft missed (`null` and `3` parse, then read wrong or throw), and
   `Zotero.version` is a getter that runs code in a compartment this plugin does
   not own. A diagnosis must never be the thing that stops startup. */
async function sitterStartupSelfCheck(rootURI) {
  let manifest = null;
  try {
    manifest = JSON.parse(await Zotero.File.getContentsFromURLAsync(rootURI + 'manifest.json'));
  } catch (error) { manifest = { version: `unreadable (${classifyError(error)})` }; }
  if (!manifest || typeof manifest !== 'object') manifest = { version: `unreadable (${typeof manifest})` };
  const application = (manifest.applications && manifest.applications.zotero) || {};
  let zoteroVersion = '<unreadable>';
  try { zoteroVersion = Zotero.version; } catch (_error) { /* A getter can throw. */ }
  // The handed version wins over the parsed one. The manifest read is kept
  // because the compatibility bounds are only there, and it degrades to
  // "unreadable" in an installed add-on exactly as it always has -- but the
  // version, which is the one field this record exists to carry, no longer
  // depends on a read that cannot succeed.
  return { version: installedVersion || manifest.version, rootURI, zoteroVersion,
    strictMinVersion: application.strict_min_version,
    strictMaxVersion: application.strict_max_version };
}
async function initialize(rootURI, token) {
  await Zotero.initializationPromise;
  // First thing after the host is up, and before any of the work below can throw:
  // a disappearance that leaves no `startup` record happened earlier than this
  // point. It goes through 0689's channel rather than a Zotero.debug() of its own
  // — one diagnostic channel, already guarded, already sealed at shutdown.
  //
  // On the FIRST startup the ring is not up yet (scheduler.js loads below), so
  // this record reaches the debug log alone. On every later one it does not: the
  // ring survives a disable/re-enable through the `??=` below, and this record
  // then lands in it too, install path and all. That asymmetry is why
  // composeSDTJournalReport drops `rootURI` at the clipboard boundary rather
  // than trusting the ring to be path-free.
  try {
    // Kept, not just logged: the diagnostics layer shows the same record on
    // screen, and a second read of the manifest could disagree with the one the
    // log carries. One read, two readers.
    environment = await sitterStartupSelfCheck(rootURI);
    emit('startup', environment);
  } catch (_error) { /* Diagnostics must never throw into startup. */ }
  await Zotero.uiReadyPromise;
  if (token !== generation) return;
  Services.scriptloader.loadSubScript(rootURI + 'scheduler.js', globalThis);
  // `??=`: a re-initialization within one Zotero session keeps the transitions
  // that led to it. A real plugin unload tears this scope down and takes the ring
  // with it; surviving that needs a durable store, which the ruling forbids.
  journal ??= createSDTJournal();
  // A second handle, under a name shutdown never deletes. The natural recovery
  // from a hang is disable/re-enable, and disable removes Zotero.SDTPackSitter —
  // which was the only way in to the ring, so the recovery action destroyed the
  // evidence of what it was recovering from (ticket 0703). Republished in
  // shutdown()'s finally as well, so the guarantee holds for a session whose
  // initialize() never got this far.
  Zotero.SDTPackSitterJournal = journal;
  sealed = false;
  // Kept although the locale load that used to sit above it is gone: nothing
  // between here and the window read awaits today, so this is redundant TODAY,
  // and re-earning it costs a disable/re-enable race of exactly the kind
  // ticket 0696 shipped. A guard removed because the await it guarded moved is
  // a guard removed for the wrong reason.
  if (token !== generation) return;
  const win = Zotero.getMainWindow();
  if (!win || typeof Zotero.SDT?.ensure !== 'function') throw new Error('Zotero 10 native SDT unavailable');
  const SDT = win.require('resource://zotero/document-worker/structured-document-text.js');
  const pako = win.require('pako');
  let versions = JSON.parse(await Zotero.File.getContentsFromURLAsync('resource://zotero/document-worker/metadata.json'));
  environment = { ...environment, packVersions: versions };
  if (token !== generation) return;
  const cachePath = PathUtils.join(Zotero.DataDirectory.dir, 'sdt-sitter-cache.jsonl');
  await Zotero.SDTPackSitterCacheWrite?.catch(() => {});
  const raw = { format: 1, versions: JSON.stringify(versions), records: Object.create(null) };
  try {
    for (const line of (await IOUtils.readUTF8(cachePath)).split('\n')) {
      try {
        const row = JSON.parse(line);
        if (row.versions !== raw.versions || typeof row.key !== 'string') continue;
        if (row.record) raw.records[row.key] = row.record;
        else delete raw.records[row.key];
      } catch (error) { /* Ignore incomplete/corrupt cache rows. */ }
    }
  } catch (error) { /* Disposable cache. */ }
  let cache = createSDTCache(raw, JSON.stringify(versions));
  // In memory, never on disk: the pack cache above carries claims worth keeping
  // across sessions, and a source hash is reconstructible from the file itself.
  const sourceHashes = createSDTSourceHashes();
  emit('cache-load', { records: Object.keys(raw.records).length });
  let seen = null;
  const children = new Map(), parents = new Map();
  let compact = true;
  // Latched exactly as render()'s guard is, and for the same reason: saveCache
  // runs once at the end of the census and again after every settled duration,
  // so a data directory that is unwritable for the session would emit on each of
  // them and evict the ring that holds the evidence. One record per episode,
  // released by the next write that works — so a second, later episode is still
  // reported (ticket 0695).
  let cacheFailing = false;
  const saveCache = async () => {
    const previous = Zotero.SDTPackSitterCacheWrite || Promise.resolve();
    const write = previous.catch(() => {}).then(async () => {
      if (!alive || token !== generation) return;
      const changes = cache.changes(compact);
      if (!compact && !changes.length) return;
      const bytes = new TextEncoder().encode(changes.map(change => JSON.stringify({ versions: raw.versions, ...change })).join('\n') + '\n');
      try {
        // Compact once per activation; subsequent writes contain changed rows only.
        await IOUtils.write(cachePath, bytes, compact ? { tmpPath: `${cachePath}.tmp` } : { mode: 'append' });
        cache.saved(changes);
        // Cleared here, or a transient failure — a full disk that was emptied, a
        // directory momentarily unwritable — would stay on screen for the session.
        if (alive && sitter) sitter.state.cacheWarning = null;
        // This one resumes after an await, so disable can land under it. The seal
        // in shutdown() is what keeps it off the far side of the shutdown record.
        emit('cache-write', { rows: changes.length, compact });
        cacheFailing = false;
        compact = false;
      }
      catch (error) {
        if (alive && sitter) {
          sitter.state.cacheWarning = sdtText('cache-not-saved', { error: String(error) });
        }
        // Contained is not silent. From the ring alone a cache that has stopped
        // persisting anything looked exactly like one that is working, and the
        // on-screen warning it did set sits three disclosures deep. The error's
        // class travels and its message does not — the throw comes from the
        // platform, and a platform message names the path it failed on.
        if (!cacheFailing) {
          cacheFailing = true;
          emit('cache-error', { error: classifyError(error), compact }, 'error');
        }
      }
    });
    Zotero.SDTPackSitterCacheWrite = write;
    await write;
  };
  if (token !== generation) return;

  const getItemTitle = async item => {
    if (!item) return null;
    try {
      if (typeof item.loadData === 'function') await item.loadData();
      return item.getField('title') || item.getDisplayTitle?.() || null;
    } catch (_error) {
      return null;
    }
  };

  // This is deliberately a bibliographic-item view separate from `list()`:
  // regular records without a file attachment explain a useful absence, but do
  // not belong in attachment coverage. `numFileAttachments()` excludes notes
  // and URL-only attachments by Zotero's own file-attachment predicate.
  const unattached = async () => {
    const result = [];
    try {
      const ids = await Zotero.DB.columnQueryAsync(
        'SELECT itemID FROM items WHERE itemID NOT IN (SELECT itemID FROM deletedItems) ORDER BY itemID');
      for (const id of ids) {
        // This view can walk an entire library before attachment inspection
        // begins. Yield on every record so the first census never makes the
        // Zotero window appear frozen while it discovers bibliography-only
        // records.
        await new Promise(resolve => timers.setTimeout(resolve, 0));
        const item = await Zotero.Items.getAsync(id);
        if (!item || item.deleted || typeof item.isRegularItem !== 'function' || !item.isRegularItem()) continue;
        try {
          if (typeof item.loadData === 'function') await item.loadData(['childItems']);
          if (typeof item.numFileAttachments !== 'function' || item.numFileAttachments() !== 0) continue;
        } catch (_error) { continue; }
        const title = await getItemTitle(item);
        result.push({ itemID: id, libraryID: item.libraryID, key: item.key,
          title: title || sdtText('file-number', { id }), parentTitle: null });
      }
    } catch (error) {
      // This auxiliary view is never allowed to stop attachment indexing. Its
      // next reconciliation retries the read, while the journal retains only a
      // safe error class.
      emit('unattached-read-error', { error: classifyError(error) }, 'error');
    }
    return result;
  };

  const blockHasSDTText = block => {
    if (!block || typeof block !== 'object') return false;
    if (typeof block.text === 'string' && block.text.trim()) return true;
    return Array.isArray(block.content) && block.content.some(blockHasSDTText);
  };
  const packHasSDTText = async reader => {
    if (typeof reader.getTopLevelBlockCount !== 'function' || typeof reader.getBlocks !== 'function') {
      // A reader that cannot inspect all blocks cannot establish an empty pack.
      // Preserve the pre-0760 current classification rather than guessing.
      return true;
    }
    const count = reader.getTopLevelBlockCount();
    if (!Number.isInteger(count) || count < 0) throw new Error('Invalid native block count');
    for (let index = 0; index < count; index++) {
      const blocks = await reader.getBlocks(index, index);
      if (!Array.isArray(blocks)) throw new Error('Invalid native block range');
      if (blocks.some(blockHasSDTText)) return true;
      // One block is bounded by the native reader's chunk format. Yielding between
      // blocks keeps a long, textless document from monopolising Zotero's UI.
      await new Promise(resolve => timers.setTimeout(resolve, 0));
    }
    return false;
  };

  async function inspect(id) {
    const item = await Zotero.Items.getAsync(id);
    const previousParent = parents.get(id);
    if (!item) {
      children.get(previousParent)?.delete(id); parents.delete(id);
      return { status: 'excluded', absent: true };
    }
    if (!item.isAttachment()) return { status: 'excluded' };
    if (previousParent !== item.parentItemID) children.get(previousParent)?.delete(id);
    parents.set(id, item.parentItemID);
    if (item.parentItemID) {
      if (!children.has(item.parentItemID)) children.set(item.parentItemID, new Set());
      children.get(item.parentItemID).add(id);
    }
    if (item.deleted) return { status: 'excluded' };
    const parent = item.parentItemID ? await Zotero.Items.getAsync(item.parentItemID) : null;
    if (parent?.deleted) return { status: 'excluded' };
    const [title, parentTitle] = await Promise.all([getItemTitle(item), getItemTitle(parent)]);
    let filename = null;
    try { filename = item.attachmentFilename || null; } catch (_error) { /* Optional primary data. */ }
    let linked = false;
    try {
      linked = typeof item.isLinkedFileAttachment === 'function' ? item.isLinkedFileAttachment()
        : item.attachmentLinkMode === Zotero.Attachments.LINK_MODE_LINKED_FILE;
    } catch (_error) { /* Treat an unreadable link mode as the storage-neutral case. */ }
    const label = title || filename || sdtText('file-number', { id });
    const descriptor = { itemID: id, libraryID: item.libraryID, key: item.key,
      title: label, parentTitle: parentTitle || null, filename, linked };
    const processor = item.isPDFAttachment() ? 'pdf' : item.isEPUBAttachment() ? 'epub' : item.isSnapshotAttachment() ? 'snapshot' : null;
    if (!processor) return { status: 'unsupported', ...descriptor, reason: 'no-extractor' };
    const cacheKey = `${item.libraryID}/${item.key}`;
    const missingSource = () => { sourceHashes.drop(cacheKey); cache.drop(cacheKey); return {
      status: 'missing-source', ...descriptor }; };
    const sourcePath = await item.getFilePathAsync();
    if (!sourcePath) return missingSource();
    // One stat where there were an exists() and a stat(): it answers both
    // questions at once, and its (size, lastModified) is what lets the MD5 below
    // be skipped on a file nothing has touched since the last census.
    let source;
    try { source = await IOUtils.stat(sourcePath); }
    catch (error) {
      // A missing path is a fact; an access or platform failure is not. Do not
      // turn the latter into a promise that file sync can repair.
      if (error?.name === 'NotFoundError') return missingSource();
      return { status: 'inspection-error', ...descriptor, errorClass: classifyError(error) };
    }
    // The re-verify window is an age, so it is a span like every other: on the
    // wall clock a backwards step shortens it and a forwards one can expire an
    // entry verified a second ago.
    const hash = await sourceHashes.hash(cacheKey, sourcePath, source, monotonic(),
      () => item.attachmentHash);
    const directory = Zotero.Attachments.getStorageDirectory(item).path;
    const path = PathUtils.join(directory, '.zotero-sdt-cache');
    const result = { status: 'missing-pack', directory, ...descriptor,
      title: title || filename || sourcePath.split(/[\\/]/).pop(),
      identity: `${item.libraryID}/${item.key}/${hash}/${JSON.stringify(versions)}` };
    result.cacheKey = cacheKey;
    seen?.add(result.cacheKey);
    result.sourceBytes = source.size;
    result.pages = processor === 'pdf' ? await Zotero.DB.valueQueryAsync(
      'SELECT totalPages FROM fulltextItems WHERE itemID = ?', [id]) : null;
    // The same collapse as the source file above, in the same census walk: this
    // exists() and the stat() that followed it asked one file one question.
    // An absent pack takes the branch it always took. One case does move: a pack
    // present but unstattable (permissions) now reads 'missing-pack' where it
    // read 'invalid-pack'. Both re-extract, so only the diagnostic bucket
    // differs, and 'missing-pack' is the truer of the two for a file the
    // filesystem will not describe.
    //
    // An absent pack falls THROUGH rather than returning, which it did not
    // before ticket 0740: no pack is the commonest state of the documents the
    // label check below exists for — a page scan recorded as `text/html` has
    // never yielded one and never will — so an early return here would skip the
    // check on precisely the population it was written for.
    let stat = null;
    try { stat = await IOUtils.stat(path); }
    catch (_error) { cache.drop(result.cacheKey); }
    if (stat) try {
      const fingerprint = JSON.stringify([stat.size, stat.lastModified]);
      const cached = cache.check(result.cacheKey, result.identity, fingerprint);
      if (cached) return { ...result, status: cached.empty ? 'empty-pack' : 'current', cached: true };
      const reader = await SDT.openStructuredDocumentTextPack({ byteLength: stat.size,
        read: async (offset, length) => {
          const bytes = await IOUtils.read(path, { offset, maxBytes: length });
          return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        },
      }, { inflate: bytes => pako.inflateRaw(bytes) });
      const metadata = await reader.getMetadata();
      const packVersionMismatch = reader.header.packVersion !== versions.SDT_PACK_VERSION ||
        String(reader.header.schemaVersion).split('.')[0] !== versions.SDT_SCHEMA_VERSION.split('.')[0];
      const sourceMismatch = metadata.source?.hash !== hash;
      const processorMismatch = metadata.processor?.type !== processor ||
        metadata.processor?.version !== versions.SDT_PROCESSOR_VERSIONS[processor];
      if (packVersionMismatch) {
        result.status = 'unsupported-pack';
        const packOrder = compareSDTVersion(reader.header.packVersion, versions.SDT_PACK_VERSION);
        const schemaOrder = compareSDTVersion(reader.header.schemaVersion, versions.SDT_SCHEMA_VERSION);
        result.packOrder = packOrder; result.schemaOrder = schemaOrder;
        const directions = [packOrder, schemaOrder].filter(order => order !== 0);
        result.reason = directions.length && directions.every(order => order < 0) ? 'older-format'
          : directions.length && directions.every(order => order > 0) ? 'newer-format'
            : 'unordered-format';
      }
      else if (sourceMismatch) result.status = 'stale-source';
      else if (processorMismatch) result.status = 'stale-processor';
      else result.status = (await packHasSDTText(reader)) ? 'current' : 'empty-pack';
      if (result.status === 'current' || result.status === 'empty-pack') cache.remember(result.cacheKey, result.identity, fingerprint, result);
      else cache.drop(result.cacheKey);
    } catch (error) { result.status = 'invalid-pack'; }
    // The label check, and the last thing before a document becomes a candidate.
    // Placed here rather than beside the `is*Attachment()` predicates on purpose:
    // there it would read eight bytes off every attachment in the library on
    // every 30-second sweep, where here it reads them only for a document that
    // is otherwise about to be handed to the worker — 4 890 snapshots minus the
    // 4 729 that already carry a pack, and nothing at all on a library that is
    // fully indexed.
    //
    // Not once each, and the exception is the population this exists for: only
    // `current` reaches cache.remember(), so a document the sniff rules out has
    // no cache record and is re-read on every sweep. Eight bytes every thirty
    // seconds against 39 documents, replacing a native extraction attempt of
    // 50–90 ms each — cheap enough that memoizing it would buy a second store
    // to keep consistent for no measurable return.
    //
    // A mismatch is `unsupported`, not a failure. The document is fine; our
    // classification of it was wrong, and the file that Zotero labelled
    // `text/html` was never something a text extractor could have read.
    // Read without a guard, unlike the coverage line's `classes ? …`: there an
    // absent classification must make a figure unsayable rather than wrong,
    // here it would silently stop checking labels. scheduler.js is loaded
    // before initialize() builds this closure, so absence is impossible — and
    // if that ever changed, a throw becoming `inspection-error` is the loud
    // failure, which is the one to have.
    if (SDT_STATUS_CLASSES.queued.includes(result.status)) {
      const sniffed = await sniffSDTSource(sourcePath);
      if (sniffed && sniffed.processor !== processor) {
        result.status = 'unsupported'; result.reason = 'mismatched-type';
      }
    }
    return result;
  }

  const workerBusy = () => Zotero.PDFWorker?._processingQueue !== false || Zotero.PDFWorker?._queue?.length !== 0;
  async function blocked(info) {
    if (!alive) return 'disabled';
    if (workerBusy()) return 'native-worker-busy';
    try {
      // procfs reports a zero stat size. Read its tiny generated streams, not
      // IOUtils' regular-file size-based path. No library file uses this sync path.
      const memory = Zotero.File.getContents('/proc/meminfo');
      const available = Number(memory.match(/^MemAvailable:\s+(\d+) kB$/m)?.[1]) * 1024;
      // Recorded where it is read, not where the verdict is returned: the
      // diagnostics layer shows how far from each threshold the gate was, and a
      // reading taken on the refusing branch alone would be blank whenever the
      // sitter is healthy — which is most of the time it is looked at.
      admission = { at: monotonic(), memoryAvailableBytes: available };
      if (!Number.isFinite(available)) return 'resources-unavailable';
      if (available < MIN_FREE_MEMORY) return 'low-memory';
      const load = Number(Zotero.File.getContents('/proc/loadavg').split(' ')[0]);
      const cpus = win.navigator.hardwareConcurrency;
      admission.load = load; admission.cpus = cpus;
      if (!Number.isFinite(load) || !cpus) return 'resources-unavailable';
      if (load >= cpus) return 'cpu-busy';
      let directory = info.directory;
      while (!(await IOUtils.exists(directory))) {
        const parent = PathUtils.parent(directory);
        if (parent === directory) return 'storage-unavailable';
        directory = parent;
      }
      const file = Zotero.File.pathToFile(directory);
      if (!file.isWritable()) return 'storage-unavailable';
      admission.diskAvailableBytes = file.diskSpaceAvailable;
      if (file.diskSpaceAvailable < MIN_FREE_DISK) return 'low-disk';
    } catch (error) {
      if (alive && sitter) sitter.state.error = sdtText('resources-read', { error: String(error) });
      return 'resources-unavailable';
    }
    // Recheck after async resource reads; never deliberately queue behind native work.
    if (!alive) return 'disabled';
    if (workerBusy()) return 'native-worker-busy';
    return null;
  }

  sitter = createSDTSitter({
    reconciliationIntervalMS: RECONCILIATION_INTERVAL_MS,
    list: async () => {
      const latest = JSON.parse(await Zotero.File.getContentsFromURLAsync('resource://zotero/document-worker/metadata.json'));
      if (JSON.stringify(latest) !== JSON.stringify(versions)) {
        versions = latest; raw.versions = JSON.stringify(versions);
        cache = createSDTCache(null, raw.versions); compact = true;
        environment = { ...environment, packVersions: versions };
      }
      seen = new Set();
      return Zotero.DB.columnQueryAsync('SELECT itemID FROM itemAttachments ORDER BY itemID');
    },
    unattached,
    // Parent erasure may report only the parent; retain previously observed
    // child IDs as well as the current DB membership. Never await this inside
    // notify(): item notifications can run within the transaction we query.
    affected: async id => {
      const ids = new Set([...(children.get(id) || [])]);
      const item = await Zotero.Items.getAsync(id);
      if (!item || item.isAttachment()) ids.add(id);
      if (!item || !item.isAttachment()) {
        for (const child of await Zotero.DB.columnQueryAsync(
          'SELECT itemID FROM itemAttachments WHERE parentItemID = ?', [id])) ids.add(child);
      }
      return ids;
    },
    censusComplete: async () => {
      cache.prune(seen); sourceHashes.prune(seen); seen = null;
      await saveCache(); return cache.samples();
    },
    samples: () => cache.samples(),
    observed: async (info, sample) => { cache.observe(info.cacheKey, info.identity, sample); await saveCache(); },
    // Every number the scheduler stamps with this — startedAt, lastProgressAt,
    // serviceMS, and the duration samples the estimator is fitted on — is a span.
    inspect, blocked, now: monotonic, changed: render,
    beforeSubmit: () => workerBusy() ? 'native-worker-busy' : null,
    // 0691's on-screen wording, this ticket's journal: describeError still shows
    // the author the file and the full error text, locally, and the failure that
    // reaches the journal is what replaced the retired on-disk error ledger.
    describeError: (info, error) => sdtText('settle-failed',
      { file: describeSDTFile(info, sdtText('file-unknown')), error: String(error) }),
    reportError: reportSettleFailure,
    emit,
    yield: () => new Promise(resolve => timers.setTimeout(resolve, 0)),
    ensure: (id, onProgress) => Zotero.SDT.ensure(id, { isPriority: false, onProgress }),
  });
  /* Ask BEFORE arming, which is the ordering the modal always deserved and
     never had (ticket 0742). What stood here set `alive = true` and installed
     the toolbar button first, so the button appeared in the window UNDER a
     modal that was still asking whether the sitter should run at all — the same
     class of defect ticket 0696 had to guard against, and a promise made to the
     user before he had answered.

     The prompt is now reached at most once per profile: an answered pref skips
     it entirely, which is what makes disable/re-enable (ticket 0727 arm 4) and
     every later restart silent. */
  let enabled = readSDTSwitch();
  if (enabled === null) {
    enabled = askSDTLaunch(win);
    if (token !== generation) return;
    writeSDTSwitch(enabled);
  }
  alive = true;
  activeToken = token;
  Zotero.SDTPackSitter = { state: sitter.state, inspect, blocked, journal };
  const owner = sitter;
  notifierID = Zotero.Notifier.registerObserver({
    notify(event, type, ids) {
      if (!alive || token !== generation || owner !== sitter || !owner.state.enabled) return;
      if ((type === 'item' && ['add', 'modify', 'trash', 'delete', 'refresh'].includes(event)) ||
          (type === 'file' && event === 'download')) {
        owner.invalidate(Array.isArray(ids) ? ids : [ids]);
        wakeSDTSitter();
      }
    },
  }, ['item', 'file'], 'sdt-pack-sitter');
  // Off is a state the plugin RUNS in: the button and the window are installed
  // either way, and they are what make "off" discoverable and reversible
  // without leaving Zotero's main window.
  if (enabled) armSDTSitter(); else disarmSDTSitter();
  for (const window of Zotero.getMainWindows()) onMainWindowLoad({ window });
}
function shutdown(data, reason) {
  // try/finally, because the teardown between here and the seal calls out to the
  // platform: dialog.close() during app shutdown is a real throw site, and a
  // shutdown that throws halfway would otherwise leave the channel open and write
  // no record — losing the evidence at exactly the moment disable is being used
  // to recover from a hang. The throw still propagates; the record is not lost.
  try {
    ++generation; alive = false; sitter?.stop();
    try { if (notifierID !== undefined) Zotero.Notifier.unregisterObserver(notifierID); }
    catch (error) { Zotero.logError(error); }
    notifierID = undefined;
    if (timers) { timers.clearTimeout(timer); timers.clearInterval(pulse); timers.clearInterval(heartbeat); }
    // Cleared, not merely stopped. `pulse` is armSDTSitter()'s idempotence
    // guard (ticket 0742), and a stale non-null handle left here makes the next
    // activation's arm a silent no-op: the plugin re-enables, builds a second
    // sitter, and never sweeps again. Nothing before this ticket read these
    // three after clearing them, so leaving them set cost nothing then.
    timer = pulse = heartbeat = undefined;
    for (const button of buttons) button.remove();
    buttons.clear();
    for (const dialog of dialogs) if (!dialog.closed) { noteDialogClose(dialog); dialog.close(); }
    dialogs.clear();
    delete Zotero.SDTPackSitter;
  } finally {
    emit('shutdown', { reason: typeof reason === 'number' ? SHUTDOWN_REASONS[reason] || `reason-${reason}`
      : reason ? String(reason).toLowerCase().replace(/^addon[_-]/, '').replace(/_/g, '-') : 'unknown' });
    sealed = true;
    // The shutdown record is the last thing written, and this is what keeps the
    // ring holding it reachable afterwards. Guarded for the same reason emit()
    // is: a teardown already halfway through a throw must not acquire a second.
    try { if (journal) Zotero.SDTPackSitterJournal = journal; } catch (_error) { /* Nothing. */ }
  }
}
function install() {}
function uninstall() {}
