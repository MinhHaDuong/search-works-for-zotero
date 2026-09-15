#!/usr/bin/env python3
"""Package the sitter; refuse to replace an existing release artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

#: Where the payload's source lives, relative to the repository root, and the
#: only definition of it. Ticket 0697 promoted the sitter out of `bench/`, which
#: is for probes and one-off measurements, to a top-level `plugins/`; the guard
#: in `bench/check_sitter_version.py` reads this rather than restating it, so a
#: further move cannot leave one of the two packaging the old directory.
SOURCE = 'plugins/sdt-sitter'

#: The payload, and the only definition of it. `bench/check_sitter_version.py`
#: reads this rather than keeping a second list: a file added to the XPI and
#: forgotten by the version guard is a payload that can change without a bump,
#: which is the one thing that guard exists to prevent. `update.json` beside
#: these is deliberately absent — it is served over HTTP, never packed.
#:
#: The locale files that briefly sat here are gone with the rest of the
#: multilingual layer (author's instruction, 2026-09-07): the strings live in
#: `bootstrap.js`, so they are payload by being part of it.
DELIVERED = ('manifest.json', 'bootstrap.js', 'scheduler.js')


def default_output(source: Path) -> Path:
    """Beside the payload it packs, named for the version the payload declares.

    `--output` was required and had no default, so the path was whatever the
    caller typed from wherever they stood — which is how four .xpi files came to
    sit at the repository root, a directory that packages nothing and that the
    document map does not claim. Deriving it removes the choice that put them
    there. Both halves of the name come from the manifest rather than from a
    constant here: the id's local part is the add-on's stable machine name, and
    the version is the number Zotero keys its record on, so a bump cannot leave
    this naming the previous build.
    """
    manifest = json.loads((source / 'manifest.json').read_text())
    stem = manifest['applications']['zotero']['id'].split('@')[0]
    return source / f"{stem}-{manifest['version']}.xpi"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=None,
                        help='where to write the package; '
                             'defaults beside the payload, named from its manifest')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent / SOURCE
    if args.output is None:
        args.output = default_output(source)
    names = DELIVERED
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as package:
        for name in names:
            entry = zipfile.ZipInfo(name, (2026, 9, 5, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            package.writestr(entry, (source / name).read_bytes())
    print(json.dumps({'path': str(args.output),
                      'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      'sourceSHA256': {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                                       for name in names}}, indent=2))


if __name__ == '__main__':
    main()
