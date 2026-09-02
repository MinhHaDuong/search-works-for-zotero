#!/usr/bin/env python3
"""Census of language signals in a Zotero library, read-only.

Reports: top-level item count, how many carry the `language` field and with
which spellings, item relations by predicate, items with two or more PDF
attachments, and among those how many pairs read as different languages by a
stopword-and-diacritic heuristic over the flat full-text cache. The heuristic
is labelled as such: it separates EN, FR and VI and calls everything else
"other"; it is a census instrument, not a language identifier for the index.

Nothing here writes. The database is opened read-only through a URI, which
works while Zotero runs (journal_mode is `delete`, no exclusive lock held;
see SPEC.md C2's fulltext.sqlite notes for the same observation).

Usage:
    python3 verification/probes/lang_census.py                 # author's defaults
    python3 verification/probes/lang_census.py --data-dir ~/Zotero
"""
import argparse
import collections
import logging
import re
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("census")

VI = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]")
FR = {"le", "la", "les", "des", "et", "une", "est", "pour", "dans", "que", "qui", "sur"}
EN = {"the", "and", "of", "to", "in", "is", "that", "for", "with", "as", "by", "on"}


def guess(storage: Path, key: str) -> str | None:
    """EN / FR / VI / other, or None when there is no text to judge."""
    p = storage / key / ".zotero-ft-cache"
    if not p.exists():
        return None
    t = p.read_text(errors="replace")[:60000].lower()
    if len(t) < 500:
        return None
    if len(VI.findall(t)) / len(t) > 0.01:
        return "vi"
    words = re.findall(r"[a-zàâçéèêîôûù]+", t)
    if not words:
        return None
    fr = sum(w in FR for w in words) / len(words)
    en = sum(w in EN for w in words) / len(words)
    if max(fr, en) < 0.03:
        return "other"
    return "fr" if fr > en else "en"


def census(data_dir: Path) -> None:
    db = sqlite3.connect(f"file:{data_dir / 'zotero.sqlite'}?mode=ro", uri=True)
    storage = data_dir / "storage"

    def q(sql: str) -> list:
        return db.execute(sql).fetchall()

    top = q(
        "select count(*) from items i where i.itemTypeID not in (select itemTypeID "
        "from itemTypes where typeName in ('attachment','note','annotation')) and "
        "i.itemID not in (select itemID from deletedItems)"
    )[0][0]
    spellings = q(
        "select v.value, count(*) from itemData d join fields f on f.fieldID=d.fieldID "
        "join itemDataValues v on v.valueID=d.valueID where f.fieldName='language' "
        "group by v.value order by 2 desc limit 12"
    )
    with_language = q(
        "select count(distinct d.itemID) from itemData d join fields f on "
        "f.fieldID=d.fieldID where f.fieldName='language'"
    )[0][0]
    log.info("top-level items %s | with a language field %s", top, with_language)
    log.info("language spellings, top 12: %s", spellings)
    log.info(
        "item relations by predicate: %s",
        q(
            "select p.predicate, count(*) from itemRelations r join relationPredicates p "
            "on p.predicateID=r.predicateID group by 1"
        ),
    )
    twins = q(
        "select a.parentItemID, group_concat(i.key) from itemAttachments a join items i "
        "on i.itemID=a.itemID where a.contentType='application/pdf' and a.parentItemID "
        "is not null and i.itemID not in (select itemID from deletedItems) "
        "group by a.parentItemID having count(*)>=2"
    )
    log.info("items with two or more PDF attachments: %s", len(twins))
    mixed = same = undecidable = 0
    combos: collections.Counter[str] = collections.Counter()
    for _pid, keys in twins:
        guesses = [g for g in (guess(storage, k) for k in keys.split(",")) if g]
        if len(guesses) < 2:
            undecidable += 1
        elif len(set(guesses)) > 1:
            mixed += 1
            combos["+".join(sorted(set(guesses)))] += 1
        else:
            same += 1
    log.info(
        "of those: same language %s | different languages %s | undecidable %s",
        same, mixed, undecidable,
    )
    log.info("language pairs among the mixed: %s", dict(combos))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--data-dir", type=Path, default=Path.home() / "data" / "Zotero",
        help="Zotero data directory holding zotero.sqlite and storage/",
    )
    args = ap.parse_args()
    census(args.data_dir)


if __name__ == "__main__":
    main()
