#!/bin/bash
# usage: rung.sh <label> <max_items> <max_chars>
set -u
LBL=$1; ITEMS=$2; CHARS=$3
OUT=/home/haduong/.claude/jobs/a481da3c/tmp/jsonbaseline
DD=/home/haduong/.zoteus-json-baseline/$LBL
BENCH=/home/haduong/CNRS/projets/actifs/zoteus-fts5/bench
SERVER=/home/haduong/CNRS/projets/actifs/zoteus-fts5/fork/dist/index.js
NOPT=--max-old-space-size=12288
mkdir -p "$DD"
cd "$BENCH"
echo "=== BUILD $LBL items=$ITEMS chars=$CHARS $(date -Is) ==="
python3 -u run_build.py --server "$SERVER" --data-dir "$DD" --backend json --build \
  --max-items "$ITEMS" --max-chars "$CHARS" --node-options=$NOPT --poll 15 --max-wait 7200 \
  > "$OUT/build-$LBL.log" 2>&1
BRC=$?
echo "build exit $BRC $(date -Is)"
ls -la "$DD"
echo "=== ATREST $LBL $(date -Is) ==="
python3 -u query.py --server "$SERVER" --data-dir "$DD" --backend json \
  --queries-file queries.txt --node-options=$NOPT \
  --out "$OUT/atrest-$LBL.raw.json" > "$OUT/atrest-$LBL.log" 2>&1
ARC=$?
echo "atrest exit $ARC $(date -Is)"
python3 "$OUT/emit.py" --rung "$LBL" --data-dir "$DD" --max-items "$ITEMS" --max-chars "$CHARS" \
  --node-options=$NOPT --build-log "$OUT/build-$LBL.log" \
  --atrest-json "$OUT/atrest-$LBL.raw.json" --out "$OUT/rung-$LBL.json" \
  --note "build exit $BRC, atrest exit $ARC"
echo "=== DONE $LBL $(date -Is) ==="
