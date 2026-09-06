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

#: `applications.zotero.id` in `bench/sdt-sitter/manifest.json`. RFC 2606
#: reserves `.invalid` so that nothing resolves it — which is correct for an
#: id, since Zotero never dereferences one, and was a defect for the
#: `update_url` beside it, which Zotero does fetch.
ADDON_ID = "sdt-pack-sitter@search-works-for-zotero.invalid"

log = logging.getLogger("sdt_sitter_install")


def read_addon_record(profile: Path, addon_id: str = ADDON_ID) -> dict:
    """What the host's own extensions record says about this add-on.

    Modelled on `bench/acceptance/adapters/beaver.py`'s `_host_addon_record`,
    which asks the same question of a throwaway acceptance profile. Read rather
    than inferred, and never coerced to a bare False.
    """
    path = Path(profile) / "extensions.json"
    if not path.is_file():
        return {"read": False, "why": f"{path} does not exist"}
    try:
        addons = json.loads(path.read_text(encoding="utf-8")).get("addons", [])
    except (ValueError, OSError) as exc:
        return {"read": False, "why": f"{type(exc).__name__}: {exc}"}
    if not isinstance(addons, list):
        return {"read": False,
                "why": f'{path}: "addons" is {type(addons).__name__}, not a list'}
    for addon in addons:
        if isinstance(addon, dict) and addon.get("id") == addon_id:
            return {"read": True, "present": True,
                    "version": addon.get("version"),
                    "active": addon.get("active"),
                    "location": addon.get("location")}
    return {"read": True, "present": False,
            "ids": sorted(a.get("id") for a in addons
                          if isinstance(a, dict) and a.get("id"))}


def install(profile: Path, xpi: Path, addon_id: str = ADDON_ID) -> Path:
    """Copy the artifact to `<profile>/extensions/<addon_id>.xpi`; return the path.

    The profile itself is never created. `extensions/` under an existing profile
    is, because a profile that has never had a plugin has none — but a profile
    directory that does not exist is a path the operator got wrong, and creating
    it would install into a profile no Zotero will ever open.
    """
    profile, xpi = Path(profile), Path(xpi)
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


def report(record: dict) -> int:
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
              len(record["ids"]), ADDON_ID)
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
        except (FileNotFoundError, OSError) as exc:
            log.error("FAIL: %s", exc)
            return 2
        log.info("installed %s", destination)
        log.info("Restart Zotero, then: python3 bench/sdt_sitter_install.py verify --profile %s",
                 args.profile)
        return 0
    return report(read_addon_record(args.profile, args.addon_id))


if __name__ == "__main__":
    sys.exit(main())
