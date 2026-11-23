#!/usr/bin/env python3
"""Re-class the 0825 probe population under ticket 0827's byte test.

Ticket 0827 exit criterion: the 0825 probe population re-classed — the 14
truncated files are Damaged PDF, the 4 malformed-xref files are not. The
probe of 2026-09-24 recorded, for each failing attachment, exactly the inputs
the byte test reads (`tailHasEOF`, `linearizedDeclaredLength`, `size`), so the
re-classification here runs the same rule the plugin runs, over the recorded
measurements:

  damaged  <=>  no `%%EOF` in the last kilobyte (`tailHasEOF` false)
            OR a declared linearized length beyond the file's real size

Everything else is unchanged: the 4 malformed-xref files carry `%%EOF` and no
declared length, which is precisely why the byte test cannot see them and they
stay in "Extraction not completed this session"; the web pages and empty
files keep the reasons 0825 already gave them.

Reads  verification/clone/0825-ensure-probe-2026-09-24.json
Writes verification/clone/0827-damaged-pdf-reclass-<date>.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "verification" / "clone" / "0825-ensure-probe-2026-09-24.json"


def byte_test_verdict(attachment: dict) -> str | None:
    """'damaged-pdf' when the byte test fires, else None (admitted as far as
    this test is concerned). Mirrors readsAsSDTDamagedPdf in bootstrap.js."""
    size = attachment["size"]
    if size == 0:
        return None  # empty files are 0825's 'empty-file', not this test's
    if attachment["tailHasEOF"] is False:
        return "damaged-pdf"
    declared = attachment["linearizedDeclaredLength"]
    if declared is not None and declared > size:
        return "damaged-pdf"
    return None


def main() -> int:
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    rows = []
    for attachment in probe["attachments"]:
        verdict = byte_test_verdict(attachment)
        rows.append({
            "attachment": attachment["attachment"],
            "probeClass": attachment["class"],
            "size": attachment["size"],
            "tailHasEOF": attachment["tailHasEOF"],
            "linearizedDeclaredLength": attachment["linearizedDeclaredLength"],
            "byteTest": verdict or "admit",
            "groupUnder0827": verdict or attachment["class"],
        })
    damaged = [r for r in rows if r["byteTest"] == "damaged-pdf"]
    out = {
        "ticket": "0827",
        "date": "2026-11-23",
        "source": str(PROBE.relative_to(ROOT)),
        "rule": "no %%EOF in the last kilobyte, or a declared linearized "
                "length beyond the file size (readsAsSDTDamagedPdf)",
        "summary": {
            "probeAttachments": len(rows),
            "damagedPdf": len(damaged),
            "unchanged": len(rows) - len(damaged),
        },
        "attachments": rows,
    }
    dest = ROOT / "verification" / "clone" / "0827-damaged-pdf-reclass-2026-11-23.json"
    dest.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=1))
    print("wrote", dest.relative_to(ROOT))
    # The exit criterion, as a non-zero exit if it does not hold: exactly the
    # 14 truncated files come out damaged, none of the 4 xref files does.
    truncated = [r for r in rows if r["probeClass"] == "truncated-file"]
    xref = [r for r in rows if r["probeClass"] == "complete-file-malformed-xref"]
    if not (len(damaged) == 14 and all(r["byteTest"] == "damaged-pdf" for r in truncated)
            and all(r["byteTest"] == "admit" for r in xref)):
        print("FAIL: the re-classification does not match the ticket's criterion", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
