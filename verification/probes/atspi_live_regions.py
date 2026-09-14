"""Is the panel's status region exposed to an AT as a live region? Ticket 0769.

Ticket 0686 item (1) is about `announceSDTTransition` -- the panel announcing a
change of state. Orca speaks a live region only if the accessibility layer says
it is one, so this reads the region's role and its `container-live` /
`live` object attributes from OUTSIDE the process, which is what Orca sees.
"""
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402


def walk(node, depth=0, hits=None):
    if hits is None:
        hits = []
    try:
        name = node.get_name() or ""
        role = node.get_role_name()
        try:
            attrs = node.get_attributes() or {}
        except Exception:  # noqa: BLE001
            attrs = {}
        live = {k: v for k, v in attrs.items()
                if "live" in k.lower() or "atomic" in k.lower() or "relevant" in k.lower()}
        if live or "id" in attrs and str(attrs.get("id", "")).startswith("sdt"):
            hits.append({"depth": depth, "role": role, "name": name[:60],
                         "id": attrs.get("id"), "live": live})
        for i in range(node.get_child_count()):
            child = node.get_child_at_index(i)
            if child:
                walk(child, depth + 1, hits)
    except Exception:  # noqa: BLE001
        pass
    return hits


def main() -> int:
    if Atspi.init() not in (0, 1):
        print("NOT-RUN: no accessibility bus")
        return 3
    time.sleep(0.5)
    desktop = Atspi.get_desktop(0)
    found = False
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if not app or "zotero" not in (app.get_name() or "").lower():
            continue
        found = True
        hits = walk(app)
        if not hits:
            print("no sdt-* ids and no live-region attributes found in Zotero's tree")
        for h in hits:
            print(f"  {h['role']:<18} id={h['id']!r:<26} live={h['live']} name={h['name']!r}")
    if not found:
        print("NOT-RUN: Zotero is not on the bus")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
