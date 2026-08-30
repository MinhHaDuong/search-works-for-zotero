#!/usr/bin/env python3
"""Score one cross_lingual_probe.mjs cell: cosine-rank the pool for every query.

Reads the driver's manifest (`<prefix>.json`) plus its two raw float32 vector
files (`<prefix>.pool.f32`, `<prefix>.query.f32`), and the probe definition
(`pool.jsonl`, `queries.jsonl`) that produced them. Computes cosine similarity
of every query against every pool passage, ranks the pool, and reports:

  - per query: rank (1-indexed) of the best relevant pool item, hit@1/5/10
  - per (query_lang, target_lang) pair: mean reciprocal rank, hit@10 rate
  - the monolingual-EN self-check lane (English contrast model's own control)
  - the native-language positive control (same-language query -> its own gold)
  - the negative controls: for each, whether any of the 20 non-English gold
    passages appear in its top-10 (should be none)

A query whose relevant_pool_ids is empty (the negative controls) is scored
only for "did a gold item leak into top-k", never for rank/hit@k.

Usage:
  python3 bench/cross_lingual_score.py --prefix <out-prefix> \
    --pool <pool.jsonl> --queries <queries.jsonl> --output <result.json>
"""
import argparse
import json
import math
from pathlib import Path


def read_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def read_f32(path, n, dim):
    import array

    a = array.array('f')
    with open(path, 'rb') as f:
        a.frombytes(f.read())
    assert len(a) == n * dim, f'{path}: expected {n * dim} floats, got {len(a)}'
    return [a[i * dim : (i + 1) * dim] for i in range(n)]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(sum(x * x for x in a))


def cosine(a, b, na=None, nb=None):
    na = na if na is not None else norm(a)
    nb = nb if nb is not None else norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def score_cell(manifest, pool_meta, query_meta, pool_vecs, query_vecs, topk=10):
    """The scoring logic alone, over already-loaded vectors — no file I/O, so a
    unit test can drive it with a handful of synthetic vectors instead of a
    real ONNX run. `main()` below is the only caller that touches disk.
    """
    assert manifest['pool_ids'] == [p['pool_id'] for p in pool_meta], (
        'pool.jsonl order does not match the vectors — was pool.jsonl rebuilt after embedding?'
    )
    assert manifest['query_ids'] == [q['query_id'] for q in query_meta], (
        'queries.jsonl order does not match the vectors — was queries.jsonl rebuilt after embedding?'
    )

    pool_norms = [norm(v) for v in pool_vecs]

    # Non-English gold: the leakage check for negative controls.
    nonen_gold_pool_ids = {
        p['pool_id'] for p in pool_meta if p['kind'] == 'gold' and p['lang_tag'] != 'en'
    }

    per_query = []
    for qi, q in enumerate(query_meta):
        qvec = query_vecs[qi]
        qnorm = norm(qvec)
        sims = [
            (pool_meta[pi]['pool_id'], cosine(qvec, pool_vecs[pi], qnorm, pool_norms[pi]))
            for pi in range(len(pool_meta))
        ]
        sims.sort(key=lambda x: -x[1])
        ranked_ids = [pid for pid, _ in sims]
        top_k_ids = set(ranked_ids[:topk])

        relevant = set(q['relevant_pool_ids'])
        if relevant:
            best_rank = min(ranked_ids.index(pid) + 1 for pid in relevant if pid in ranked_ids)
            rr = 1.0 / best_rank
            hit1 = best_rank <= 1
            hit5 = best_rank <= 5
            hit10 = best_rank <= 10
            leaked_gold = None
        else:
            # Negative control: no relevant item exists. Report whether any
            # non-English gold item leaked into top-k instead.
            best_rank = None
            rr = None
            hit1 = hit5 = hit10 = None
            leaked_gold = sorted(top_k_ids & nonen_gold_pool_ids)

        per_query.append(dict(
            query_id=q['query_id'],
            topic_id=q['topic_id'],
            query_lang=q['query_lang'],
            target_lang=q['target_lang'],
            best_rank=best_rank,
            reciprocal_rank=rr,
            hit_at_1=hit1,
            hit_at_5=hit5,
            hit_at_10=hit10,
            top1_pool_id=ranked_ids[0],
            top1_sim=round(sims[0][1], 6),
            leaked_nonen_gold=leaked_gold,
        ))

    # Aggregate per (query_lang, target_lang) pair, excluding negative controls.
    pairs = {}
    for r in per_query:
        if r['reciprocal_rank'] is None:
            continue
        key = f"{r['query_lang']}->{r['target_lang']}"
        pairs.setdefault(key, []).append(r)

    pair_summary = {}
    for key, rows in pairs.items():
        n = len(rows)
        pair_summary[key] = dict(
            n=n,
            mrr=round(sum(r['reciprocal_rank'] for r in rows) / n, 4),
            hit_at_1=round(sum(1 for r in rows if r['hit_at_1']) / n, 4),
            hit_at_5=round(sum(1 for r in rows if r['hit_at_5']) / n, 4),
            hit_at_10=round(sum(1 for r in rows if r['hit_at_10']) / n, 4),
        )

    neg_rows = [r for r in per_query if r['leaked_nonen_gold'] is not None]
    negative_control = dict(
        n=len(neg_rows),
        clean=sum(1 for r in neg_rows if not r['leaked_nonen_gold']),
        leaked=[r['query_id'] for r in neg_rows if r['leaked_nonen_gold']],
    )

    return dict(
        model_id=manifest['model_id'],
        model=manifest['model'],
        dtype=manifest['dtype'],
        device=manifest['device'],
        pooling=manifest['pooling'],
        template=manifest['template'],
        topk=topk,
        pool_size=len(pool_meta),
        query_count=len(query_meta),
        pair_summary=pair_summary,
        negative_control=negative_control,
        per_query=per_query,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', required=True, help='out-prefix passed to cross_lingual_probe.mjs')
    ap.add_argument('--pool', required=True)
    ap.add_argument('--queries', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--topk', type=int, default=10)
    args = ap.parse_args()

    manifest = json.loads(Path(f'{args.prefix}.json').read_text(encoding='utf-8'))
    dim = manifest['dim']
    pool_meta = read_jsonl(args.pool)
    query_meta = read_jsonl(args.queries)
    pool_vecs = read_f32(f'{args.prefix}.pool.f32', len(pool_meta), dim)
    query_vecs = read_f32(f'{args.prefix}.query.f32', len(query_meta), dim)

    out = score_cell(manifest, pool_meta, query_meta, pool_vecs, query_vecs, topk=args.topk)
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    nc = out['negative_control']
    print(f"wrote {args.output}: {len(out['pair_summary'])} pairs, negative_control clean={nc['clean']}/{nc['n']}")


if __name__ == '__main__':
    main()
