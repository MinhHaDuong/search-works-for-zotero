#!/usr/bin/env python3
"""Read what a Zotero profile's own extensions record says about one add-on.

Ticket 0713. This function was written twice — `read_addon_record` in
`bench/sdt_sitter_install.py` (ticket 0688) and `_host_addon_record` in
`bench/acceptance/adapters/beaver.py` (ticket 0712, hand-ported from the
first) — and the same four-defect fix had to be applied to both copies. Two
copies of a fix drift; a third caller would have made three. This module is the
one implementation, plugin-neutral: it takes the profile and the add-on id, and
knows nothing about which plugin is being asked after.

The read is deliberately three-valued, and that is the whole point of it.
`{"read": False, "why": …}` means we could not look; `{"read": True,
"present": False, "ids": […]}` means we looked and the add-on is not recorded.
Collapsing the first into the second turns "the plugin vanished" and "the file
was missing" into one green — and both callers act on the difference, one as an
exit code and one as evidence inside a dictionary its verbs return unguarded.

A record that is present carries what the host wrote about it: `version`,
`active`, `location`. Whether the application *accepted* a sideloaded artifact,
and whether it later disabled it, lives only here — the .xpi being on disk
proves the copy happened and nothing else.

The two merged implementations differed in exactly one respect, and the union
is what this module keeps: the sitter's copy did not catch `MemoryError`. The
narrower tuple's only extra behaviour was to raise, so nothing can depend on it
that was not already a defect.
"""

import json
import stat
from pathlib import Path


def host_addon_record(profile: Path, addon_id: str) -> dict:
    """What the host's own extensions record says about `addon_id`.

    Read rather than inferred, and never coerced to a bare False. Every wrong
    shape a valid JSON document can take is a `read: False`, not a raise: the
    callers read this inside an exit code and inside an evidence dictionary,
    where an exception surfaces far from the profile that caused it.
    """
    path = Path(profile) / "extensions.json"
    try:
        # Do not use Path.is_file() here. Current pathlib folds EACCES into
        # False, which turns an unreadable profile into a false claim that its
        # record is absent. stat() preserves the distinction for the OSError
        # handler below. A dangling link and a link loop are still a visible
        # non-file, as are directories.
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            if path.is_symlink():
                return {"read": False, "why": f"{path} is not a regular file"}
            return {"read": False, "why": f"{path} does not exist"}
        except OSError:
            if path.is_symlink():
                return {"read": False, "why": f"{path} is not a regular file"}
            raise
        if not stat.S_ISREG(mode):
            return {"read": False, "why": f"{path} is not a regular file"}
        document = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, RecursionError, MemoryError) as exc:
        # RecursionError and MemoryError, not only ValueError: json rejects
        # deeply nested input by exhausting the stack and a large enough
        # document by exhausting the heap. Neither descends from ValueError or
        # OSError — RecursionError is a RuntimeError and MemoryError inherits
        # Exception directly — so a tuple naming only the two obvious families
        # lets both straight through the caller. Both were reproduced against
        # this function's ancestor rather than reasoned about: 200k nested
        # arrays for the first, an 81 MB flat document under a 150 MB
        # address-space cap for the second, each with a small-input control
        # under the same conditions returning a record normally.
        return {"read": False, "why": f"{type(exc).__name__}: {exc}"}
    # Shape, separately from syntax. `[]` and `"text"` are valid JSON, so
    # nothing above rejects them, and `.get` on the result raised
    # AttributeError. The document's shape, then the container's, then each
    # element's: three floors of one trapdoor.
    if not isinstance(document, dict):
        return {"read": False,
                "why": f"{path}: the document is {type(document).__name__}, not an object"}
    addons = document.get("addons", [])
    if not isinstance(addons, list):
        return {"read": False,
                "why": f'{path}: "addons" is {type(addons).__name__}, not a list'}
    for addon in addons:
        if isinstance(addon, dict) and addon.get("id") == addon_id:
            return {"read": True, "present": True,
                    "version": addon.get("version"),
                    "active": addon.get("active"),
                    "location": addon.get("location")}
    # `isinstance(..., str)` and not a bare truth test, which is the third
    # floor: the document was checked, then the container, and an ELEMENT whose
    # id is a number still reached `sorted()` over mixed types, where
    # `str < int` raises TypeError. An id that is not a string is not an id
    # anything could have installed under, so it is not one of the ids reported
    # back.
    return {"read": True, "present": False,
            "ids": sorted(a["id"] for a in addons
                          if isinstance(a, dict) and isinstance(a.get("id"), str)
                          and a["id"])}
