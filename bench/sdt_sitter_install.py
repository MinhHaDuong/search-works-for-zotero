#!/usr/bin/env python3
"""Install the sitter into a Zotero profile, and read back what the host recorded.

Ticket 0688. The author reports the plugin "tends to disappear on its own from
the installed-plugins list", and ticket 0680 shipped the XPI to his home
directory with no profile installation at all. A session sideload — the
harness's own `bench/acceptance/adapters/beaver.py` does one — is not an
install: it is how the acceptance layer gets a plugin in front of a throwaway
profile for one run. Copied into `<profile>/extensions/<id>.xpi`, the host
registers the add-on in its own `extensions.json` and it survives a restart.

Two subcommands, and they answer different questions:

    install   put the built artifact where the host looks for it
    verify    read what the host actually recorded about it

`verify` is the half worth having. It reads the host's record rather than
inferring one from the file on disk, because the file being there proves the
copy happened and nothing else: whether the application *accepted* it — and
whether it later disabled it for an incompatible `strict_max_version`, which
is the second mechanism 0688 names — is only in `extensions.json`. That read
is deliberately three-valued. A missing or unparseable file reports that it
could not be read, never `present: False`: "we looked and the plugin is gone"
and "we could not look" are different findings, and collapsing them turns the
plugin's disappearance into a silent green.

Neither subcommand defaults the profile. A guessed profile path installs into
somewhere nobody chose and verifies a profile nobody ran, and both failures
look exactly like success.

Exit codes for `verify`: 0 present, 1 absent, 3 could not be read.
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

# Both spellings are live, so both are tried: the suite reaches this file with
# the repo root on sys.path, while `python3 bench/sdt_sitter_install.py` puts
# bench/ itself there and no `bench` package exists to qualify.
try:
    from bench.host_addon_record import host_addon_record
except ImportError:  # run as a script, with bench/ itself on sys.path
    from host_addon_record import host_addon_record

#: `applications.zotero.id` in `plugins/sdt-sitter/manifest.json`. RFC 2606
#: reserves `.invalid` so that nothing resolves it — which is correct for an
#: id, since Zotero never dereferences one, and was a defect for the
#: `update_url` beside it, which Zotero does fetch.
ADDON_ID = "sdt-pack-sitter@search-works-for-zotero.invalid"

log = logging.getLogger("sdt_sitter_install")


def read_addon_record(profile: Path, addon_id: str = ADDON_ID) -> dict:
    """What the host's own extensions record says about this add-on.

    The read itself is `bench/host_addon_record.py`, shared with
    `bench/acceptance/adapters/beaver.py`, which asks the same question of a
    throwaway acceptance profile. This wrapper adds only the default: the
    shared function is plugin-neutral and takes the id, while this tool has
    exactly one plugin to ask after (ticket 0713).
    """
    return host_addon_record(profile, addon_id)


def install(profile: Path, xpi: Path, addon_id: str = ADDON_ID) -> Path:
    """Copy the artifact to `<profile>/extensions/<addon_id>.xpi`; return the path.

    The profile itself is never created. `extensions/` under an existing profile
    is, because a profile that has never had a plugin has none — but a profile
    directory that does not exist is a path the operator got wrong, and creating
    it would install into a profile no Zotero will ever open.
    """
    profile, xpi = Path(profile), Path(xpi)
    # The id becomes a filename, so it must be one path component. `--addon-id`
    # is an operator's argument rather than an attacker's, but a value carrying
    # a separator writes outside the directory the caller named, and refusing it
    # costs one line.
    if "/" in addon_id or "\\" in addon_id or addon_id in (".", "..", ""):
        raise ValueError(f"addon id {addon_id!r} is not a single path component")
    if not profile.is_dir():
        raise FileNotFoundError(
            f"{profile} is not a directory. Pass the Zotero PROFILE directory "
            "(the one holding prefs.js), not the data directory.")
    if not xpi.is_file():
        raise FileNotFoundError(f"{xpi} is not a file. Build it with bench/build_sdt_sitter.py.")
    destination = profile / "extensions" / f"{addon_id}.xpi"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(xpi, destination)
    return destination


def report(record: dict, addon_id: str = ADDON_ID) -> int:
    """The three-valued read as three exit codes. This is the observed contract.

    Nothing outside a Python import sees the dict; a Make target and a shell see
    only the code, and the codes are what the acceptance line is written against.
    """
    print(json.dumps(record, indent=2))
    if not record["read"]:
        log.error("NOT-RUN: %s. Nothing here says whether the plugin is installed; "
                  "start Zotero on this profile once, then ask again.", record["why"])
        return 3
    if record["present"]:
        log.info("OK: present, version %s, active %s, location %s",
                 record["version"], record["active"], record["location"])
        return 0
    log.error("ABSENT: the host records %d add-on(s), none of them %s",
              len(record["ids"]), addon_id)
    return 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--addon-id", default=ADDON_ID,
                        help="manifest id to install under and look for (default: the sitter's)")
    subcommands = parser.add_subparsers(dest="command", required=True)

    installer = subcommands.add_parser("install", help="copy the XPI into a profile")
    installer.add_argument("--profile", type=Path, required=True,
                           help="the Zotero profile directory (holds prefs.js). Never defaulted.")
    installer.add_argument("--xpi", type=Path, required=True,
                           help="the artifact built by bench/build_sdt_sitter.py")

    verifier = subcommands.add_parser("verify", help="read the host's own extensions record")
    verifier.add_argument("--profile", type=Path, required=True,
                          help="the Zotero profile directory. Never defaulted.")

    args = parser.parse_args()
    if args.command == "install":
        try:
            destination = install(args.profile, args.xpi, args.addon_id)
        except (FileNotFoundError, OSError, ValueError) as exc:
            log.error("FAIL: %s", exc)
            return 2
        log.info("installed %s", destination)
        log.info("Restart Zotero, then: python3 bench/sdt_sitter_install.py verify --profile %s",
                 args.profile)
        return 0
    return report(read_addon_record(args.profile, args.addon_id), args.addon_id)


if __name__ == "__main__":
    sys.exit(main())
