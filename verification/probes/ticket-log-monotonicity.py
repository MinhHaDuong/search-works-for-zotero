"""How many ticket logs run backwards, and where does each first break?

Ticket 0569. Log entries are append-only (`tickets/AGENTS.md`), so a log's
stamps should not decrease. They do: the stamps are typed by hand as often as
they come from `erg log`, which reads the real clock, and a typed one can name
a time that has not happened — commit 2a5b04f stamped six tickets 2026-09-01
at 16:30Z while the commit itself landed at 11:51Z UTC.

Measured 2026-09-01 over 131 tickets: 41 non-monotone. Six were the 2a5b04f
family (first entry, corrected in this branch); the rest break mid-log, where
the cause is not necessarily a bad stamp — a note appended on a parallel branch
and merged later lands after entries stamped before it.

    python3 verification/probes/ticket-log-monotonicity.py
    python3 verification/probes/ticket-log-monotonicity.py --first-entry-only
"""
import argparse
import pathlib
import re

STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z)\s")


def stamps(path: pathlib.Path) -> list[str]:
    """Every log-section stamp in file order (ISO-8601 Z, so string order is time order)."""
    lines = path.read_text().split("\n")
    if "--- log ---" not in lines:
        return []
    out = []
    for line in lines[lines.index("--- log ---") + 1:]:
        if line.startswith("--- "):
            break
        match = STAMP.match(line)
        if match:
            out.append(match.group(1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickets", type=pathlib.Path, default=pathlib.Path("tickets"))
    parser.add_argument("--first-entry-only", action="store_true",
                        help="report only logs whose FIRST entry is the break "
                             "(the created stamp typed later than the work it precedes)")
    args = parser.parse_args()

    total = broken = 0
    for path in sorted(args.tickets.rglob("*.erg")):
        seen = stamps(path)
        if not seen:
            continue
        total += 1
        breaks = [i for i in range(len(seen) - 1) if seen[i + 1] < seen[i]]
        if not breaks or (args.first_entry_only and breaks != [0]):
            continue
        broken += 1
        where = ", ".join(f"#{i + 1} {seen[i]} > #{i + 2} {seen[i + 1]}" for i in breaks)
        print(f"{path}: {where}")
    print(f"\n{broken} non-monotone of {total} logs")


if __name__ == "__main__":
    main()
