#!/usr/bin/env python3
"""The replace step's red-control payload for rung 3 (ticket 0822).

A build of `plugins/sdt-sitter/` with one change: on every activation,
before anything else, it deletes every `.zotero-sdt-cache` under the data
directory's `storage/`. Installed as the replacement mid-extraction
(`bench/sitter_menagerie_test.py --replace-xpi`), it throws away the work
finished before the replace, and the sitter then extracts it again -- the
regression the replace check exists to catch. The count of packs recovers,
so a count-only check would pass it; the pack identities do not.

Built in a scratch copy with the repository's own builder; the tree is
never written. The anchor must match exactly once, or nothing is built.

    python3 bench/sitter_lifecycle_red_payload.py OUT.xpi
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

ANCHOR = "function startup({ rootURI, version, id }, reason) {\n"
MUTATION = ANCHOR + (
    "  /* RED CONTROL, ticket 0822: finished packs thrown away on activation. */\n"
    "  try {\n"
    "    const entries = Zotero.File.pathToFile(\n"
    "      PathUtils.join(Zotero.DataDirectory.dir, 'storage')).directoryEntries;\n"
    "    let dir;\n"
    "    while ((dir = entries.nextFile)) {\n"
    "      const pack = dir.clone();\n"
    "      pack.append('.zotero-sdt-cache');\n"
    "      if (pack.exists()) pack.remove(false);\n"
    "    }\n"
    "  } catch (_error) { /* A red control must not stop the startup it breaks. */ }\n")


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(args[0]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)
        shutil.copytree(REPO / "plugins" / "sdt-sitter", tree / "plugins" / "sdt-sitter")
        (tree / "bench").mkdir()
        shutil.copy2(REPO / "bench" / "build_sdt_sitter.py", tree / "bench")
        bootstrap = tree / "plugins" / "sdt-sitter" / "bootstrap.js"
        source = bootstrap.read_text(encoding="utf-8")
        if source.count(ANCHOR) != 1:
            print(f"anchor matched {source.count(ANCHOR)} times, expected 1", file=sys.stderr)
            return 1
        bootstrap.write_text(source.replace(ANCHOR, MUTATION), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "bench/build_sdt_sitter.py", "--output", str(out)],
            cwd=tree, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
