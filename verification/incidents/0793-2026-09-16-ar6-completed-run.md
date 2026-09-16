# 0793 — AR6 reaches 100 %: the plateau is SLOW, not wedged

**Date:** 2026-09-16 · **Host:** padme · **Sitter:** 0.4.26 · **Zotero:** 10.0.2
**Document:** AR6 / *Climate Change 2021*, journal id 11940
**Artifacts:** [`0793-2026-09-16-ar6-journal.json`](0793-2026-09-16-ar6-journal.json),
[`0793-2026-09-16-cpu-probe.json`](0793-2026-09-16-cpu-probe.json)

## Verdict

**SLOW.** The run the author started reached `settle ok` after 469 472 ms. The
90 % plateau that had looked like a wedge on every previous sighting resolved on
its own. No upstream wedge report is owed on this reading.

## The tail, measured

| Boundary | Journal `at` | Local | Δ |
|---|---|---|---|
| `progress 89` | 1789555012700 | 12:36:52 | — |
| `progress 90` | 1789555014377 | 12:36:54 | 1.7 s after 89 |
| `progress 95` | 1789555262807 | 12:41:02 | **248.4 s at 90** |
| `progress 100` | 1789555272919 | 12:41:12 | 10.1 s |
| `settle ok` | 1789555273011 | 12:41:13 | 0.09 s |

Four heartbeats fell inside the plateau, and their `sinceProgressMS` climbs
monotonically — 9 442, 69 442, 129 505, 189 506 — against a `pending` frozen at
10 494 throughout. The extension was alive and ticking the whole time; only the
document was quiet.

This matches Zotero's own worker source exactly, which is what stops it being a
surprise. In `resource/document-worker/worker.js`, `reportPageProgress` clamps
`progress = 90`: 90 is the **ceiling of the page phase**, not a fraction of the
whole job. The 95 comes from a later stage, a single `onProgress(95)`. So the
plateau is not a stall in the page loop — it is the page loop being *finished*,
with a second, unreported stage running behind a number that cannot move.

After the settle the sitter went straight back to work: drain 281 → 276, admitted
11941 (590 kB) and settled it in 168 ms.

## What the CPU probe did and did not see

`bench/sdt_stall_probe.py` ran against PID 3859611 and collected 33 intervals of
5 s — a 165.2 s window, 12:41:23 → 12:44:08. It stopped early, well short of its
requested 2400 s, for the documented reason: the sampler breaks when the process
dies, and Zotero exited at 12:44:08.

**The window has zero overlap with the plateau.** Sampling began roughly twenty
seconds *after* `settle ok`. On the question the probe was launched to answer —
what the CPU is doing while progress sits at 90 — this run returns a null, and a
null is not a finding. The plateau was settled by the journal, not by the probe.

What the probe did deliver, by accident and worth keeping, is a two-arm
separation of its own bands measured on this host rather than on a fixture:

| Arm | Intervals | `processPercent` | Top thread | RSS | `rchar` |
|---|---|---|---|---|---|
| working | 1–17 | 125.5 – 150.1 | 87–99 % | 1.52 – 4.80 GB, churning | up to 31 MB/interval |
| taper | 18–21 | 1.60, 48.15, 4.99, 4.00 | — | — | — |
| idle | 22–33 | **0.0 ×12** | 0.0 | flat, 1.2806 GB | 0 – 17 bytes |

Overall 71.07 %, max 150.06, min 0.0, `intervalsAboveSlow` 18 of 33, three
threads exited in the window. Between the working arm and the idle arm nothing
sits between 4.99 % and 48.15 %: the ≥10 % "slow tail" and ≤2 % "wedged" bands
are separated by a wide empty region in real data, at both ends. That validates
the instrument's discrimination between *working* and *not working*. It says
nothing about which side a plateau falls on, because no sample was taken during
one.

## This was already on file — and it names a suspect

None of the above is new. The 2026-09-05 Palgrave work (ticket 0676) reached the
same conclusion from the other end, and
[`verification/SDT-PALGRAVE-AUDIT.md`](../SDT-PALGRAVE-AUDIT.md) already maps the
plateau precisely:

> `reportPageProgress` … maps page processing into the interval ending at 90
> percent. … Global transformations after the page loop do not report
> intermediate progress. The caller next reports 95 percent after structure
> creation … **Long silence near the end is compatible with healthy work**; 100
> percent is not persisted completion.

and [`verification/SDT-PALGRAVE-PHASES.md`](../SDT-PALGRAVE-PHASES.md) names what
runs in the gap:

> **Citation resolution was the largest instrumented global stage, followed by
> reference application.** Native progress was silent during those global
> transformations. This demonstrates a **healthy long progress gap, not a hung
> job.**

So the 90 % plateau is the citation + reference-application stage, and this AR6
run is a second, independent confirmation on a far larger document — 248 s where
Palgrave's subsets were shorter.

**The open patch ticket for the suspect inside that stage is
[0679](../../tickets/0679-patch-zotero-sdt-quadratic-reference-blo.erg)**,
"Patch Zotero SDT quadratic reference-block membership scan" (open, filed
2026-09-05, parent analysis 0678, closed). It targets the document-worker
reference index and `isReferenceBlock`: for B eligible blocks and R bibliography
runs the membership query scans the runs before consulting a Set, worst-case
**O(B × R)**, to be replaced by an O(R + B) Set built once.

One caution carries over verbatim and must not be dropped: PHASES.md states the
scan **"is demonstrated, but its share of total citation time is not isolated"**,
and explicitly "does NOT attribute all citation time to the membership scan".
This AR6 reading does not change that. It shows a 248 s citation stage on a
document with an unusually large bibliography — consistent with a B × R term
dominating, and not evidence that it does. Isolating the share is 0679's own
acceptance work ("count operations while independently scaling blocks and
bibliography runs"), not something this run settles.

## Consequence for the wedge predicate

A healthy AR6 finalisation is **248 seconds of zero progress at exactly 90**.
Any trigger keyed on progress silence alone must sit above that figure, or must
special-case the 90 ceiling — a 60 s silence threshold would have declared this
run wedged four heartbeats running, on a document that finished normally. The
90/95 semantics are not a cosmetic detail for the predicate; they are the
difference between a true positive and four false ones.

## The interface already models both milestones — where it is buried

The author's reading was that 90 and 95 are finalisation milestones the UI does
not treat as such. Half of that is already answered in our own code:

```js
const quietMessage = s.active !== null && Number(s.progress) >= 90 && silence >= 60
  ? sdtText(Number(s.progress) >= 95 ? 'active-finalising' : 'active-references') : '';
```

with `"active-references": "Reading the references…"` and
`"active-finalising": "Finishing…"`, and `silence` in seconds. The strings are
ours, not Zotero's — a search of `omni.ja` finds neither.

Against this run's numbers:

- `active-references` became eligible at the second heartbeat (silence 69 s) and
  stayed eligible for ~188 of the plateau's 248 seconds.
- `active-finalising` **never displayed**: 95 → 100 took 10.1 s and silence at 95
  was 1.15 s, far below the 60 s gate.

So the wording exists and the ≥95 switch exists. Three things keep it from
answering the complaint: it lives in the secondary `sdt-document-status` line,
it waits a full minute of silence before appearing at all, and the headline
figure keeps reading **90 %** for four minutes regardless. A user watching the
percentage sees a frozen number; the sentence that explains it is late, quiet,
and elsewhere.

The decision 0793's exit criteria ask for — whether the sitter should *announce*
the slow tail — is therefore not "should we write this", but "should this be
promoted out of the quiet line and off the 60 s gate, given that the plateau's
measured duration is 248 s". That is a UI change, small and well-bounded, and it
is recorded here rather than acted on.
