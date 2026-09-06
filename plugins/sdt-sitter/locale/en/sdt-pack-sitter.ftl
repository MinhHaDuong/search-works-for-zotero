# The sitter's user-facing text. English is the source of truth: every id must
# exist here, and a locale missing one falls back to this file (ticket 0692).
#
# Two rules a translator has to know, both enforced by tests/test_sdt_sitter.py:
#
#   * The unit of work is one ATTACHMENT. Zotero's own French UI renders *item*
#     as "document", which reads as the reference rather than the file, so no
#     string here may say document, item, or attachment in any language. Say
#     file. "Pack" is the internal name of the artifact and never reaches a
#     reader either.
#   * Keep to the Fluent subset the files already use: one message per line,
#     `{ $variable }` placeables, and a select expression only for the two
#     genuinely plural-sensitive messages below. No terms, no attributes, no
#     message references, no functions.

## The toolbar button, and the tooltip it carries

index = Index
index-coverage = Index { $percent } %
scope-one = Library: { $names }
scope-few = Libraries: { $names }
scope-many = All libraries ({ $count })

# Plural-sensitive: the count is the whole of this string.
files-indexed = { $count ->
        [one] { $count } file indexed
       *[other] { $count } files indexed
    }

## Every phase a reader can meet on hover, in the user's vocabulary

phase-census = Census
phase-extracting = Indexing under way
phase-error = Error
phase-disabled = Turned off
phase-native-worker-busy = Waiting: native indexing under way
phase-cpu-busy = Paused: processor busy
phase-low-memory = Paused: not enough memory
phase-low-disk = Paused: not enough disk space
phase-storage-unavailable = Paused: storage unavailable
phase-resources-unavailable = Paused: system resources unreadable
phase-launch-declined = Not started: turn the add-on off, then on again

## The status window's frame

dialog-title = Indexing assistant
section-global = Overall progress — library
section-active = Indexing under way
details-title = Details
fulltext-title = Full-text search index
fulltext-body = Zotero’s own full-text search index (distinct from the index the assistant prepares):
fulltext-unavailable = Statistics unavailable: { $error }
tech-title = Technical diagnostics

## Layer 1: progress, what is being worked on, and when it should end

files-indexed-of = Files indexed: { $current } / { $total }
files-indexed-count = Files indexed: { $current }
global-estimate = Estimated finish around { $median } (between { $low } and { $high })
active-none = No indexing under way
active-file = Indexing: { $file } — { $progress } % — { $elapsed } elapsed
active-finalising = Finishing…
active-references = Reading the references…
active-estimate = Estimated duration: { $median } (between { $low } and { $high })

# Plural-sensitive, the second and last one.
files-failed = { $count ->
        [one] { $count } file could not be indexed
       *[other] { $count } files could not be indexed
    }

## Layer 2: the counts, and the fit the estimates rest on

observations-waiting = Observed durations: { $count } (3 needed before any estimate)
observations = Observed durations: { $count }
observations-basis = Observed durations: { $count } — basis: { $basis }
basis-pages = per page
basis-bytes = per byte
diagnostics-phase = State: { $phase }
diagnostics-census = Census: { $scanned } / { $total }
diagnostics-count = { $status }: { $count }
diagnostics-completed = Created this session: { $count }
diagnostics-failed = Could not be indexed (last census): { $count }
diagnostics-error = Error: { $error }
cache-not-saved = Cache not saved: { $error }

## Layer 3: what a bug report asks for and a reader never does

debug-label = Log every step to Zotero’s debug output
journal-copy = Copy the log
journal-copied = Log copied to the clipboard.
journal-copy-failed = Copy failed: clipboard unavailable.
journal-unreadable = Log unreadable: { $error }
environment-version = Add-on version: { $version }
environment-zotero = Zotero: { $version } (declared compatibility { $min } – { $max })
environment-native = Native format: version { $format }, schema { $schema }
environment-extractors = Native extractors: { $extractors }
environment-root = Installed in: { $root }
admission-none = No resource reading since startup.
admission-age = Last reading { $age } ago — one reading per admission, none while the library is up to date
admission-memory = Memory available: { $available } (threshold { $threshold })
admission-load = Processor load: { $load } on { $cpus } cores
admission-disk = Disk space: { $available } (threshold { $threshold })

## Quantities, and how a file is named

gibibytes = { $value } GiB
unknown-value = ?
unit-seconds = { $count } s
unit-minutes = { $count } min
unit-hours-minutes = { $hours } h { $minutes } min
unit-minutes-seconds = { $minutes } min { $seconds } s
file-unknown = unknown file
file-number = file no. { $id }
settle-failed = “{ $file }” failed: { $error }
resources-read = Reading resources: { $error }

## The launch prompt, whose body is these four messages, in order

launch-title = Indexing assistant — experimental
launch-question = Index the whole library tonight?
launch-conditions = One file at a time, with at least 4 GiB of memory available and 8 GiB of free disk. PDFs and the full-text search index settings are left untouched.
launch-worker = The shared worker cannot be interrupted, nor given a system priority of its own. A large file can delay native work that arrived after it. The thresholds do not cap what it consumes.
launch-disable = Turning the add-on off stops new admissions; the file under way finishes. Errors stay confined to the session. A disposable local cache keeps the freshness checks and the durations; it holds no text and no running job.
