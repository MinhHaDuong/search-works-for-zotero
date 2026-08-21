#!/usr/bin/env python3
"""Compare two query-result files produced by query.py (one per backend)."""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="baseline (json backend) results")
    ap.add_argument("--b", required=True, help="candidate (sqlite backend) results")
    a = ap.parse_args()

    A = json.load(open(a.a))
    B = json.load(open(a.b))
    rows = []
    for q in A["queries"]:
        ka = [k for k in A["queries"][q]["keys"] if k]
        kb = [k for k in B["queries"].get(q, {}).get("keys", []) if k]
        sa, sb = set(ka), set(kb)
        inter = sa & sb
        jac = len(inter) / len(sa | sb) if (sa | sb) else 1.0
        same_order = ka == kb
        rows.append({"query": q, "n_json": len(ka), "n_sqlite": len(kb),
                     "overlap": len(inter),
                     "jaccard": round(jac, 3),
                     "identical_ordered": same_order,
                     "json_only": sorted(sa - sb), "sqlite_only": sorted(sb - sa)})
    print(json.dumps({"backend_a": A["backend"], "backend_b": B["backend"],
                      "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
