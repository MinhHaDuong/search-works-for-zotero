"""How many ticket logs run backwards, and where does each first break?

Ticket 0571's reconnaissance, kept because it is the measurement the ruling
turned AGAINST. Log entries are append-only (`tickets/AGENTS.md`), so a naive
reading says the stamps should not decrease. They did, in 41 of 131 logs — and
the ruling of 2026-09-01 (`DECISIONS.md`) is that this is the wrong question:
this repository runs parallel sessions, so a log is a merge of several append
streams, and a note written on one branch and merged later honestly lands below
entries stamped after it.

What is a defect is a stamp naming a time that has not happened, which is a
different set: 14 logs still read backwards after the sweep and carry no such
stamp, while logs that read forwards carried plenty. That rule has a standing
guard — `bench/check_ticket_logs.py`, in `make check`. This script has none of
that authority. It reports a shape, not a verdict, and is useful for one thing:
seeing what the merge of parallel streams actually looks like.

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
