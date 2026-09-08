# SDT sitter: notification scheduling and reconciliation

2026-09-08. Ticket [0752](../tickets/closed/0752-make-sdt-sitter-event-driven-with-reconc.erg).
Implementation base: `606383dcd73326d55e94757ffba9a9c98d7957b7`.

The sitter now keeps observed attachment states and coalesced dirty IDs behind
one serialized pump. Notifications request targeted inspection; queue retries
call the pump without enumerating the library. Explicit `sweep()` remains a
reconciliation entry point for diagnostics and existing probes. Activation,
re-enabling and the deadline in SPEC.md §5.2.7 request full reconciliation.
Missed deadlines coalesce, including when native extraction is unresolved.

## Host contract checked

Read the installed Zotero distribution at
`/tmp/ztmp2/Zotero_linux-x86_64/app/omni.ja`, with application version `10.0.1`
and BuildID `20260824184709`. The relevant source can be reproduced with
`unzip -p <omni.ja> <member>`; members below are relative to the archive root.

- `chrome/content/zotero/xpcom/notifier.js`: `registerObserver` accepts `item`
  and `file`; callbacks receive `(event, type, ids, extraData)`, and the returned
  registration handle is passed to `unregisterObserver`.
- `chrome/content/zotero/xpcom/storage/storageRequest.js`: completed downloads
  trigger `download` on `file` with the attachment's item ID.
- `chrome/content/zotero/xpcom/data/item.js`: item save produces `add`/`modify`,
  trash produces item notifications, and refresh notifications identify items.
  Parent erasure recursively erases child attachments. The sitter also retains
  observed parent/child membership so an already-erased parent's children can
  be invalidated when current database membership has disappeared.

Notifier callbacks perform no awaited database work. Parent expansion and
inspection run later in the pump, avoiding a notifier/transaction dependency.
Shutdown unregisters the observer; captured callbacks also check activation
identity, so a late callback cannot wake a replacement sitter.

## Behavioral evidence

Run from the repository root:

```sh
node tests/sdt_sitter_scheduler.mjs
node tests/sdt_sitter_bootstrap.mjs
python3 verification/probes/sdt_sitter_scheduler_mutants.py
python3 verification/probes/sdt_sitter_bootstrap_mutants.py
make check
```

The scheduler suite drives notifications during inspection, parent expansion
and native extraction; resource waits; late native settlement across off/on;
missed reconciliation deadlines; interrupted censuses; and source identity
changes at admission and during extraction. Completed publications conserve
attachment counts, keep nonnegative buckets and contain unique pending IDs.

The bootstrap suite runs the actual plugin over a mock Zotero/filesystem host.
It changes source files and packs on disk, emits native-shaped download and item
notifications, trashes/restores/erases parent items, changes processor metadata,
and checks observer teardown and visible reconciliation freshness. It counts
full-list queries, targeted inspections, hashes and native admissions, so a
hidden full sweep cannot pass as event handling. Replacement fixtures pin the
old pack hash independently of the new source hash. Targeted invalidation
removes obsolete ETA samples without pruning unrelated cache records.

Missing-source observations discard the source hash memo and obsolete derived
cache hint, preserve the Zotero item and native pack, and remove pending
extraction. Admission rechecks the source after resource reads; a changed source
or storage directory requires another resource check, followed by a final native
worker-idle check. A disappearance during extraction does not suppress the
restored source. A genuine extraction failure while the same source remains
available stays session-suppressed; a verified current pack always takes
precedence over that suppression. A changed source inherits neither a previous
source's failed identity nor its duration observation.

Mutation probes retain the earlier behavioral failure classes and exercise the
new lost-event and final-admission defenses. Previously stale anchors for the
per-item catch, generation-gated toast and held coverage are updated to the
current mechanisms, without treating an unmatched anchor as a passing test.

## Limits

This is source inspection and executable host-mock evidence, not a live-profile
installation or native extraction campaign. Both scheduler and bootstrap tests
use the production plugin files; the native extractor itself remains mocked.
External changes become visible at the next successful observation, subject to
running/disabled state, resource availability and scan duration. The source-hash
memo retains the reuse window in SPEC.md §5.2.7: an in-place byte rewrite that
preserves path, size and modification time is not promised detection at the
next reconciliation. A permanently unresolved native job still blocks further
submissions; the sitter neither cancels nor isolates that shared worker.
