#!/usr/bin/env python3
"""Package the sitter; refuse to replace an existing release artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / 'sdt-sitter'
    names = ('manifest.json', 'bootstrap.js', 'scheduler.js')
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
