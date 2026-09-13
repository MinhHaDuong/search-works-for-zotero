"""Does Zotero expose the sitter's toolbar control to an assistive technology?

Ticket 0769 half two. Orca reads what AT-SPI exposes, so before asking whether
Orca SPEAKS the right thing, ask whether there is anything there to speak. This
walks the accessible tree from outside the process -- the decorrelated reading
the plugin's own `getAttribute('aria-label')` cannot give, because that asserts
what the markup says, not what the accessibility layer computed from it.
"""
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

TARGET_HINTS = ("Index", "sdt", "SDT")


def walk(node, depth=0, out=None, limit=4000):
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    try:
        name = node.get_name() or ""
        role = node.get_role_name()
        out.append((depth, role, name))
        if any(h in name for h in TARGET_HINTS):
            try:
                states = node.get_state_set()
                flags = [s.value_nick for s in
                         (Atspi.StateType.FOCUSABLE, Atspi.StateType.FOCUSED,
                          Atspi.StateType.ENABLED, Atspi.StateType.SHOWING,
                          Atspi.StateType.VISIBLE)
                         if states.contains(s)]
            except Exception as exc:  # noqa: BLE001
                flags = [f"states unreadable: {exc}"]
            print(f"  HIT depth={depth} role={role!r} name={name!r} states={flags}")
        for i in range(node.get_child_count()):
            child = node.get_child_at_index(i)
            if child:
                walk(child, depth + 1, out, limit)
    except Exception:  # noqa: BLE001 -- a node can vanish mid-walk
        pass
    return out


def main() -> int:
    if Atspi.init() not in (0, 1):
        print("NOT-RUN: Atspi.init() failed; no accessibility bus")
        return 3
    time.sleep(1.0)
    count = Atspi.get_desktop_count()
    print(f"atspi desktops: {count}")
    desktop = Atspi.get_desktop(0)
    apps = desktop.get_child_count()
    print(f"applications on the bus: {apps}")
    names = []
    for i in range(apps):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        nm = app.get_name() or "(unnamed)"
        names.append(nm)
    print("applications:", names)

    zotero = [desktop.get_child_at_index(i) for i in range(apps)
              if (desktop.get_child_at_index(i) or None)
              and "zotero" in (desktop.get_child_at_index(i).get_name() or "").lower()]
    if not zotero:
        print("NOT-RUN: Zotero is not on the accessibility bus "
              "(is it running with GNOME_ACCESSIBILITY=1?)")
        return 3
    for app in zotero:
        nodes = walk(app)
        print(f"walked {len(nodes)} accessible nodes under {app.get_name()!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
