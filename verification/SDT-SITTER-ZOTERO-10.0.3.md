# SDT Pack Sitter on Zotero 10.0.3

Run 2026-09-22 against the official Zotero 10.0.3 Linux x86-64 tarball
(build `20260917164854`) and this tree's sitter 0.4.26. The installed Zotero
remained at 10.0.2; the new build ran from a separate directory.

**Verdict: the live smoke test passed.** `bench/sitter_smoke_test.py` built the
XPI, installed it in a fresh profile, observed the sitter arm in a real window,
confirmed Zotero opened the requested throwaway data directory, imported the
Menagerie fixture, and verified the cache records and SDT packs on disk against
the source files. The raw run log is
[`bench/results/sdt-sitter-zotero-10.0.3/smoke-log.txt`](../bench/results/sdt-sitter-zotero-10.0.3/smoke-log.txt).

The tarball's `app/omni.ja` carries the same `resource/document-worker/metadata.json`
constants as the previously tested 10.0.2 build: pack 1, schema 1.2.0,
and processor versions pdf 14 / epub 2 / snapshot 1. This update did not
change the native pack version signals the sitter reads.

Command (with `DISPLAY=:1`):

```sh
python3 bench/sitter_smoke_test.py \
  --zotero-bin /tmp/zotero-10.0.3-test/Zotero_linux-x86_64/zotero \
  --work-dir /tmp/sdt-sitter-10.0.3-live --keep --port 6214
```

This is a fresh-profile installation and preparation check. It does not
exercise an existing library through an in-place Zotero update, the sitter's
pause control, or an uninstall cycle. The separate 10.0.2 acceptance result is
in [`verification/acceptance/0.4.26-2026-09-17.json`](acceptance/0.4.26-2026-09-17.json).
