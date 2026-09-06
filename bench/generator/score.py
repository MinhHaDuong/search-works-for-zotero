"""The ladder: win, near-win, miss, on rank and citation-chain completeness.

Rulings 5 and 7 of 2026-09-06 (`DECISIONS.md`, second round) define the score
and this module is their executable form. An answer is a paragraph in a page in
a file attached to a Zotero entry. A reply is read hit by hit, in rank order:

- a hit is the **answer row** when it names the answer's item and its snippet
  overlaps the answer paragraph;
- a hit is the **same work** when it names the answer's item without touching
  the paragraph, or another item carrying the same title or identifier — the
  other rendering or the other language of ruling 5;
- anything else is noise.

**win**: the answer row is within the first ten and the reply carries every
element of the chain — title, creators, date, identifier, section heading and
printed page label — measured. **near-win**: the answer row is within the first
ten with an incomplete chain, or only the same work is. **miss**: neither.

Two reciprocal ranks are kept because they answer different questions: the
row's, which is the score ruling 5 names, and the work's, which is what a user
who opens the item gets. A miss contributes zero to both; nothing is dropped
from a denominator.

The chain elements a reply carries are read from the hit as the target returns
it, under the field names listed in `CHAIN_FIELDS`; a target that returns only a
title cannot score a win here, and the report says so rather than relaxing the
ladder to fit the reply.
"""

import re
from collections import Counter, defaultdict

#: Field names, per chain element, under which a hit may carry that element.
CHAIN_FIELDS: dict[str, tuple[str, ...]] = {
    "title": ("title",),
    "creators": ("creators", "authors", "author", "creator"),
    "date": ("date", "year"),
    "identifier": ("DOI", "doi", "ISBN", "isbn", "url", "identifier"),
    "section": ("section", "heading", "sectionHeading"),
    "page_label": ("pageLabel", "page_label", "page", "printedPage"),
}

WIN, NEAR, MISS = "win", "near-win", "miss"
SHINGLE = 5


def _norm(s: str) -> str:
    return re.sub(r"[^\w\s]", " ", s.lower()).split()


def overlaps(snippet: str, paragraph: str) -> bool:
    """Whether a snippet was cut from the paragraph: a five-word shingle in common,
    after case and punctuation are dropped. Zoteus centres a 240-character snippet
    on the query terms, so a shorter shingle would match ordinary phrases and a
    longer one would miss a snippet whose two ends both fall outside the paragraph."""
    a, b = _norm(snippet), _norm(paragraph)
    if len(a) < SHINGLE or len(b) < SHINGLE:
        return bool(a) and " ".join(a) in " ".join(b)
    grams = {" ".join(b[i:i + SHINGLE]) for i in range(len(b) - SHINGLE + 1)}
    return any(" ".join(a[i:i + SHINGLE]) in grams for i in range(len(a) - SHINGLE + 1))


def _same_work(hit: dict, answer: dict) -> bool:
    if hit.get("itemKey") == answer["item_key"]:
        return True
    title = (answer["chain"]["title"]["value"] or "").strip().lower()
    if title and (hit.get("title") or "").strip().lower() == title:
        return True
    ident = answer["chain"]["identifier"]["value"]
    if ident:
        for field in CHAIN_FIELDS["identifier"]:
            if str(hit.get(field) or "").strip().lower() == ident.strip().lower():
                return True
    return False


def chain_in_reply(hit: dict) -> dict[str, bool]:
    """Which chain elements this hit carries, by the field names it uses."""
    return {element: any(hit.get(f) not in (None, "", [], {}) for f in fields)
            for element, fields in CHAIN_FIELDS.items()}


def classify(hits: list[dict], answer: dict, top_k: int = 10) -> dict:
    """One reply against one answer. Pure."""
    row_rank = work_rank = None
    row_hit = None
    for i, hit in enumerate(hits[:top_k], start=1):
        if row_rank is None and hit.get("itemKey") == answer["item_key"] and overlaps(hit.get("snippet") or "", answer["paragraph"]):
            row_rank, row_hit = i, hit
        if work_rank is None and _same_work(hit, answer):
            work_rank = i
        if row_rank is not None and work_rank is not None:
            break
    chain = chain_in_reply(row_hit) if row_hit is not None else {e: False for e in CHAIN_FIELDS}
    complete = all(chain.values())
    if row_rank is not None and complete:
        verdict = WIN
    elif row_rank is not None or work_rank is not None:
        verdict = NEAR
    else:
        verdict = MISS
    return {
        "verdict": verdict,
        "row_rank": row_rank,
        "work_rank": work_rank,
        "row_rr": 1 / row_rank if row_rank else 0.0,
        "work_rr": 1 / work_rank if work_rank else 0.0,
        "chain_in_reply": chain,
        "hits": len(hits),
    }


def aggregate(readings: list[dict], key) -> dict:
    """Counts beside rates, per group of `key(reading)`, plus the whole."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in readings:
        groups[str(key(r))].append(r)
    groups["all"] = list(readings)

    def cell(rs: list[dict]) -> dict:
        n = len(rs)
        c = Counter(r["score"]["verdict"] for r in rs)
        return {
            "n": n,
            "win": c[WIN], "near_win": c[NEAR], "miss": c[MISS],
            "win_rate": round(c[WIN] / n, 3) if n else None,
            "near_win_rate": round(c[NEAR] / n, 3) if n else None,
            "miss_rate": round(c[MISS] / n, 3) if n else None,
            "row_mrr": round(sum(r["score"]["row_rr"] for r in rs) / n, 3) if n else None,
            "work_mrr": round(sum(r["score"]["work_rr"] for r in rs) / n, 3) if n else None,
            "row_in_top10": sum(1 for r in rs if r["score"]["row_rank"]),
            "work_in_top10": sum(1 for r in rs if r["score"]["work_rank"]),
        }

    return {g: cell(rs) for g, rs in sorted(groups.items(), key=lambda kv: (kv[0] != "all", kv[0]))}


def chain_tally(readings: list[dict]) -> dict:
    """How often each chain element was carried by the reply's answer row, over
    the readings whose answer row was found."""
    found = [r for r in readings if r["score"]["row_rank"]]
    return {
        "answer_rows_found": len(found),
        "carried": {e: sum(1 for r in found if r["score"]["chain_in_reply"][e]) for e in CHAIN_FIELDS},
    }
