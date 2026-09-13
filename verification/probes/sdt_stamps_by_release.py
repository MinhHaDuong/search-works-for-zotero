#!/usr/bin/env python3
"""Read the SDT drift constants out of one or more Zotero *releases*, not one build.

SYNC.md's drift watch and `sdt_schema_census.py` both read
`resource/document-worker/metadata.json` from whichever build happens to be
installed. Two such readings, taken months apart on different machines, bound a
delta but cannot place it: the 2026-09-11 reading bounded
`SDT_SCHEMA_VERSION` 1.1.0 -> 1.2.0 and pdf 3 -> 14 between 10.0 and 10.0.2 and
recorded the interval as "three point releases", while RELEASE-NOTES.md wrote
that "whether that delta was one jump or several is not knowable from here".

It is knowable, and cheaply. The constants are a static JSON file inside each
release's `app/omni.ja` (a zip). Reading them needs no install, no profile, no
data directory and no running Zotero -- only the tarball. This probe fetches
the releases named on the command line, reads the file out of each, and prints
one row per release, so the interval between two bumps is measured rather than
bounded.

Zotero's first 10.x release is versioned `10.0`, not `10.0.0`; `10.0.0` is not a
release and the download endpoint answers 403 for it. That 403 is the probe's
own positive control: a version that exists answers 206 for the same request.

Nothing here writes to a Zotero directory, and nothing here starts Zotero.

Usage:
    python3 verification/probes/sdt_stamps_by_release.py 10.0 10.0.1 10.0.2
    python3 verification/probes/sdt_stamps_by_release.py --installed ~/.local/Zotero_linux-x86_64
    python3 verification/probes/sdt_stamps_by_release.py 10.0 10.0.2 --json
"""
import argparse
import configparser
import json
import logging
import pathlib
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

DL = ("https://www.zotero.org/download/client/dl"
      "?channel={channel}&platform={platform}&version={version}")
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
METADATA = "resource/document-worker/metadata.json"


def read_app_dir(app: pathlib.Path) -> dict:
    """Read version, build id and the three SDT constants from a Zotero app/ directory."""
    ini = configparser.ConfigParser(strict=False)
    ini.read(app / "application.ini")
    with zipfile.ZipFile(app / "omni.ja") as z:
        meta = json.loads(z.read(METADATA))
    processors = meta["SDT_PROCESSOR_VERSIONS"]
    return {
        "version": ini.get("App", "Version", fallback="?"),
        "build_id": ini.get("App", "BuildID", fallback="?"),
        "schema": meta["SDT_SCHEMA_VERSION"],
        "pack": meta["SDT_PACK_VERSION"],
        **{f"proc_{k}": v for k, v in sorted(processors.items())},
    }


def fetch_release(version: str, channel: str, platform: str, workdir: pathlib.Path) -> dict:
    """Download one release tarball and read its app/ directory out of it."""
    tarball = workdir / f"zotero-{version}.tar.xz"
    if not tarball.exists():
        url = DL.format(channel=channel, platform=platform, version=version)
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=600) as response:
            tarball.write_bytes(response.read())
    app = workdir / f"x-{version}"
    app.mkdir(exist_ok=True)
    # Only the two files we read, so an unpack stays seconds rather than a full tree.
    subprocess.run(
        ["tar", "-xJf", str(tarball), "-C", str(app), "--strip-components=1", "--wildcards",
         "*/app/omni.ja", "*/app/application.ini"],
        check=True, capture_output=True,
    )
    row = read_app_dir(app / "app")
    row["asked"] = version
    return row


def render(rows: list[dict]) -> str:
    columns = ["asked", "version", "build_id", "schema", "pack"]
    columns += [k for k in rows[0] if k.startswith("proc_")]
    widths = [max(len(str(r.get(c, ""))) for r in rows + [{c: c for c in columns}])
              for c in columns]
    out = [" | ".join(c.ljust(widths[i]) for i, c in enumerate(columns)),
           "-+-".join("-" * w for w in widths)]
    out += [" | ".join(str(r.get(c, "")).ljust(widths[i]) for i, c in enumerate(columns))
            for r in rows]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versions", nargs="*", help="release versions, e.g. 10.0 10.0.1 10.0.2")
    parser.add_argument("--installed", action="append", default=[], metavar="DIR",
                        help="a Zotero install directory to read in place (repeatable)")
    parser.add_argument("--channel", default="release")
    parser.add_argument("--platform", default="linux-x86_64")
    parser.add_argument("--keep", metavar="DIR",
                        help="reuse DIR for downloads instead of a temporary directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s")

    if not args.versions and not args.installed:
        parser.error("name at least one release version or --installed directory")

    rows = []
    for directory in args.installed:
        row = read_app_dir(pathlib.Path(directory).expanduser() / "app")
        row["asked"] = str(directory)
        rows.append(row)

    if args.versions:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = pathlib.Path(args.keep).expanduser() if args.keep else pathlib.Path(tmp)
            workdir.mkdir(parents=True, exist_ok=True)
            for version in args.versions:
                try:
                    rows.append(fetch_release(version, args.channel, args.platform, workdir))
                except Exception as exc:  # noqa: BLE001 -- a missing release is a result, not a crash
                    logging.warning("%s: not readable (%s)", version, exc)

    if not rows:
        return 1
    print(json.dumps(rows, indent=2) if args.json else render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
