"""Read creation dates and processor identities from existing SDT packs."""

import argparse
import hashlib
import json
from pathlib import Path

from sdt_read import read_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packs", nargs="+", type=Path)
    args = parser.parse_args()
    rows = []
    for path in args.packs:
        pack = read_pack(path)
        metadata = pack["metadata"]
        rows.append(
            {
                "key": path.parent.name,
                "dateCreated": metadata.get("dateCreated"),
                "processor": metadata.get("processor"),
                "source_hash": metadata.get("source", {}).get("hash"),
                "mtime_ns": path.stat().st_mtime_ns,
                "pages": len(pack["catalog"].get("pages", [])),
                "pack_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
