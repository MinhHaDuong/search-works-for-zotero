"""The ratified chunk geometry (SPEC.md §5.2.2, ratified 2026-08-29), as code.

One statement per fact: SPEC.md §5.2.2 owns the construction and the ceiling;
this module implements it so the passage census and the regression tests share
one resolution instead of each re-deriving it. Ticket 0140.

The construction, verbatim from §5.2.2:

    budget = min(CEILING, modelMax) − specialTokens − count(passagePrefix)

with two rules around it that are part of the geometry, not commentary:

- `modelMax` is the MINIMUM over every position-limit field the model
  declares. The fields disagree in the wild (one candidate declares four
  spanning a factor of four), so a construction naming no field is
  underspecified.
- The heading path is charged to the budget and DROPPED ENTIRELY, never
  truncated, when it would cost more than a quarter of it.

Ordering matters: min-then-subtract bounds the whole embedded sequence,
prefix included. `min(CEILING, width) − affordances` is not
`min(width − affordances, CEILING)`; the two agree at a 512 window and
diverge at 8 192.
"""

import math

# SPEC.md §5.2.2. The ceiling sits below every window in play (census:
# bench/results/0140-model-windows/candidate-windows.json), so the budget
# resolves identically under every candidate and the chunk key stays stable
# across a model swap.
CEILING = 500

# Structural chunking parameters, §5.2.2: tokens on structural boundaries.
MIN_TOKENS = 120
OVERLAP_TOKENS = 48


def model_window(declared: dict[str, int]) -> int:
    """The model's usable window: the minimum over every declared limit field.

    `declared` maps field name to value, as read from the model's own
    config.json / tokenizer_config.json (see model-window-census.py).
    An empty declaration is an error, not a default: a window must be read,
    never assumed.
    """
    if not declared:
        raise ValueError("no declared position-limit fields; read the model, do not assume")
    return min(declared.values())


def resolve_budget(window: int, special_tokens: int, prefix_tokens: int,
                   ceiling: int = CEILING) -> int:
    """budget = min(ceiling, window) − specialTokens − count(passagePrefix).

    `prefix_tokens` is the MODEL's instruction prefix (the registry's
    input_template passage entry), fixed per model — not the heading path,
    which is per-chunk and handled by effective_prefix().
    """
    budget = min(ceiling, window) - special_tokens - prefix_tokens
    if budget <= 0:
        raise ValueError(
            f"budget {budget} <= 0 (window {window}, specials {special_tokens}, "
            f"prefix {prefix_tokens}): this model cannot serve the geometry")
    return budget


def effective_prefix(prefix_tokens: int, budget: int) -> int:
    """The quarter rule: a heading path costing more than budget/4 is dropped
    entirely, not truncated — a pathological outline path that would eat a
    real share of the window hurts more than it helps."""
    if prefix_tokens > budget / 4:
        return 0
    return prefix_tokens


def split_count(n_tokens: int, budget: int, overlap: int = OVERLAP_TOKENS) -> int:
    """How many pieces one oversized paragraph of n_tokens yields when split
    at `budget` with `overlap` tokens carried between consecutive pieces."""
    if n_tokens <= budget:
        return 1
    return math.ceil((n_tokens - overlap) / (budget - overlap))


def chunk_count(paragraph_tokens: list[int], budget: int,
                minimum: int = MIN_TOKENS, overlap: int = OVERLAP_TOKENS) -> int:
    """Passage count for one entry under the settled geometry.

    Paragraphs accumulate into a chunk until adding the next would exceed the
    budget; a chunk closes only once it holds at least `minimum` tokens. A
    single paragraph larger than the budget is split with overlap — overlap
    exists only inside a split paragraph, never between whole paragraphs
    (§5.2.2). Chunks never cross entries, so the caller calls this per entry.

    This is a counting model of the chunker, for the §5.2.9 census: it decides
    how many passages a text yields, not where their exact boundaries land.
    The minimum shows up in two places: a fill still below it is absorbed into
    an oversized paragraph's split rather than closed as its own runt chunk,
    and an entry shorter than the budget yields one chunk regardless (the max
    rarely binds under structural chunking — ticket 0140). A sub-minimum
    TRAILING fill still counts as a chunk, because the text must be embedded
    somewhere; where the real chunker would merge it backward this census
    overcounts by one, which errs on the conservative side for a budget.
    """
    chunks = 0
    filled = 0
    for n in paragraph_tokens:
        if n <= 0:
            continue
        if n > budget:
            if 0 < filled < minimum:
                chunks += split_count(filled + n, budget, overlap)
            else:
                if filled:
                    chunks += 1
                chunks += split_count(n, budget, overlap)
            filled = 0
            continue
        if filled and filled + n > budget:
            chunks += 1
            filled = 0
        filled += n
    if filled:
        chunks += 1
    return chunks
