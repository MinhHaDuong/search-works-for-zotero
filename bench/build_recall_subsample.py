"""Build ONE seeded, documented subsample of the real 93 022-passage corpus for ticket 0265.

Why a subsample at all. Embedding the full corpus per (candidate, rung) at CPU speeds
costs ~10 h per cell (0263's tracker) and this campaign has 18 surviving cells (6
candidates x fp32/q8/uint8). Measured directly from 0263's own committed fidelity
timings (ms_per_passage, summed across the 18 surviving cells): 7 980,1 ms of embedding
per passage. A subsample of N passages costs N x 7 980,1 ms of total campaign wall time,
not per cell -- so this script's ONE choice of N is the whole campaign's compute budget.

Why items, not passages, are what gets sampled. The same-item recall task's relevant
set for a probe is "other passages of the same item, at least --gap chunks away"
(bench/vec_task_recall.mjs). A passage-level random subsample would shatter most items
into fragments too short to have an eligible sibling, collapsing the probe pool toward
empty relevant sets. So this script shuffles ITEMS with a seeded RNG and keeps each
selected item WHOLE -- every one of its passages, in original order -- until the
passage budget is reached. The item that crosses the budget is kept in full rather than
truncated, so no item in the subsample loses siblings the full corpus would have given it.

Contiguity precondition, verified before this script existed: passages.items has zero
non-contiguous item reappearances over the full 93 022 lines -- every item's passages
already sit in one unbroken run, in file order. That is what lets "ord" be reconstructed
as the passage's 0-indexed position within its item's run, with no separate ords file
ever having existed for the full corpus.

Output, deterministic given (source corpus, source items, seed, target):
  <out-prefix>-passages.txt   one passage per line, item blocks in original file order
  <out-prefix>-items.txt      one item id per line, same length and order
  <out-prefix>-ords.txt       one integer per line: position within the item's own run
  <out-prefix>-meta.json      seed, method, counts, sha256 of the passages file

Usage:
  python3 bench/build_recall_subsample.py \
    --passages /home/haduong/data/projets/zoteus-bench/vec-real/passages.txt \
    --items /home/haduong/data/projets/zoteus-bench/vec-real/passages.items \
    --seed 20260830 --target 1500 \
    --out-prefix /home/haduong/data/projets/zoteus-bench/0265/subsample
"""

import argparse
import hashlib
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger("build_recall_subsample")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--passages", type=Path, required=True)
    p.add_argument("--items", type=Path, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--target", type=int, required=True, help="minimum passage count")
    p.add_argument("--out-prefix", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    passages = args.passages.read_text(encoding="utf-8").split("\n")
    if passages and passages[-1] == "":
        passages.pop()
    item_ids = args.items.read_text(encoding="utf-8").split("\n")
    if item_ids and item_ids[-1] == "":
        item_ids.pop()
    if len(passages) != len(item_ids):
        raise SystemExit(f"passages ({len(passages)}) and items ({len(item_ids)}) disagree")

    # Group into contiguous runs, verifying the contiguity precondition rather than
    # assuming it -- a corpus regenerated upstream could break it silently.
    runs = []  # (item_id, start, end) end exclusive
    start = 0
    seen = set()
    for i in range(1, len(item_ids) + 1):
        if i == len(item_ids) or item_ids[i] != item_ids[start]:
            runs.append((item_ids[start], start, i))
            if i < len(item_ids):
                if item_ids[i] in seen:
                    raise SystemExit(
                        f"item {item_ids[i]!r} reappears non-contiguously at line {i}; "
                        "the ord-reconstruction precondition no longer holds"
                    )
                seen.add(item_ids[i])
            start = i
    logger.info("%d items, %d passages, contiguity precondition holds", len(runs), len(passages))

    rng = random.Random(args.seed)
    order = list(range(len(runs)))
    rng.shuffle(order)

    selected = []
    total = 0
    for idx in order:
        selected.append(idx)
        total += runs[idx][2] - runs[idx][1]
        if total >= args.target:
            break
    # Emit in ORIGINAL file order, not shuffle order -- readable, and matches the
    # repo-wide convention that a passages file is item-blocked in source order.
    selected.sort(key=lambda idx: runs[idx][1])

    out_passages, out_items, out_ords = [], [], []
    for idx in selected:
        item_id, s, e = runs[idx]
        for ord_ in range(e - s):
            out_passages.append(passages[s + ord_])
            out_items.append(item_id)
            out_ords.append(ord_)

    prefix = args.out_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    passages_path = Path(f"{prefix}-passages.txt")
    passages_path.write_text("\n".join(out_passages) + "\n", encoding="utf-8")
    Path(f"{prefix}-items.txt").write_text("\n".join(out_items) + "\n", encoding="utf-8")
    Path(f"{prefix}-ords.txt").write_text("\n".join(str(o) for o in out_ords) + "\n", encoding="utf-8")

    digest = hashlib.sha256(passages_path.read_bytes()).hexdigest()
    meta = {
        "what": "ticket 0265's recall/fusion subsample: whole items, seeded shuffle, budget-capped",
        "source_passages": str(args.passages),
        "source_items": str(args.items),
        "source_passages_total": len(passages),
        "source_items_total": len(runs),
        "seed": args.seed,
        "method": "random.Random(seed).shuffle(item_index); accumulate whole items in "
        "shuffled order until passage count >= target; the crossing item is kept "
        "whole, not truncated; output re-sorted to original file order",
        "target_passages": args.target,
        "items_selected": len(selected),
        "passages_selected": len(out_passages),
        "passages_sha256": digest,
    }
    Path(f"{prefix}-meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(
        "selected %d items, %d passages (target %d); sha256 %s",
        len(selected), len(out_passages), args.target, digest[:16],
    )


if __name__ == "__main__":
    main()
