# Public upstream findings — 2026-09-07

Ticket 0736 owns the filing and follow-through. This note records only the
functional probes and the neutral reporting-channel request. It changes no
requirement or design decision.

## Revalidation

The source checkout was upstream `main` at
`5a81cee88be6d979e9ca1e99e897b6b6df25beef`. The repository catch-up command
reported QUIET at that base. The filing procedure checks the live main SHA
and the complete issue/PR list again immediately before each submission;
movement stops filing for another source or duplicate review.

The executable evidence is
[`probes/zoteus_public_findings.test.ts`](probes/zoteus_public_findings.test.ts).
Its assertions deliberately describe the observed defects, rather than the
behavior a fix should implement. It uses upstream's real tool handlers,
router, Web API client, build/update entry points and index implementations,
with deterministic API fixtures and an artificial embedder. It writes no live
Zotero library and contacts no cloud embedding service.

| Finding | Evidence and limit |
| --- | --- |
| Effective library for writes and annotations | A configured group default resolves correctly for reads but a create goes to the cloud user's personal library. Explicit group annotation lookup also uses the personal default before the write. API transport is stubbed. |
| PDF bundle platform support | The published release archive lacks the Windows/macOS native canvas packages. Linux extraction succeeds; Windows/macOS loader simulations fail at PDF module import. Native Windows/macOS execution remains unverified. |
| Own-words retry | After a one-shot child-version census failure, the shared cursor advances. A subsequent successful update still misses the edited and newly added note and retains the old text. Reproduced with memory and SQLite. |
| Local bibliography | Both item-key handlers make a cloud users/0 request despite a locally served default library. The transport records the actual client URL and supplies the failure response; direct CSL-JSON formatting is outside this failure path. |
| Distinct search items | A concentrated annotation fixture exhausts the semantic passage pool before item deduplication. A wider request on the same index recovers the other papers, confirming they were indexed. Reproduced with memory and SQLite; keyword/hybrid behavior is requested as acceptance coverage, not claimed as measured. |

Raw output, release archive identity, and loader results live
in [`../bench/results/upstream-public-review-2026-09-07/`](../bench/results/upstream-public-review-2026-09-07/).
Public issue text is preserved in [`upstream-issues-0736/`](upstream-issues-0736/);
the JSON filing receipts identify each issue and its verified creation state. Filed URLs and feedback belong to
the ticket log, avoiding a second live status board here.

## Reproducing the probes

In a disposable checkout of the source SHA above, with its npm dependencies
installed, copy the test into its expected upstream test location:

```sh
cp /path/to/search-works-for-zotero/verification/probes/zoteus_public_findings.test.ts tests/features/public-findings.test.ts
npm test -- tests/features/public-findings.test.ts --maxWorkers=1 --minWorkers=1
```

For packaging, download the release asset identified in `bundle.json`, inspect
its ZIP members, and unpack it into a fresh directory. From the unpacked bundle
root, run each command in a new Node process:

```sh
node /path/to/search-works-for-zotero/verification/probes/zoteus_pdf_platform.mjs linux
node /path/to/search-works-for-zotero/verification/probes/zoteus_pdf_platform.mjs win32
node /path/to/search-works-for-zotero/verification/probes/zoteus_pdf_platform.mjs darwin
```

The non-host runs change only `process.platform` inside the probe process to
exercise dependency-loader selection; they do not emulate another operating
system. The shipped dependency tree is used directly, without an npm install
that might silently repair the package. These results must not be described
as native Windows/macOS smoke tests.

## Duplicate review and existing feedback

The complete upstream issue/PR history was read before filing. The closest
items were #53 (library selection), #29 (attachment extraction), #38
(transformer installation instructions), #33/#36 (own-words indexing), #26
(full-text freshness), and #58 (citation styles). Their scope differs from the
current reproductions.

In particular, the maintainer's [reply on #58](https://github.com/oscardvs/zoteus/issues/58#issuecomment-5559939505)
already invites a separate local-bibliography issue or PR. The filing follows
that invitation and includes the item-key CSL export path, while leaving the
fixed style forwarding and alias behavior alone. The ticket log records this
feedback and the smallest response plan.

The neutral reporting-channel request contains no vulnerability evidence.
Further substantive comments must be read from the public pages and recorded
with `erg log`, with a response or patch plan. Silence is not approval.

## Probe state lifecycle

This run used disposable state under `/tmp/zoteus-t0736` and
`/tmp/t0736-release`. It holds only a source checkout, test fixtures and the
public release artifact; it can be removed after the committed evidence and
filing receipts are retained. No ad-hoc state was allocated under `~/data`.
