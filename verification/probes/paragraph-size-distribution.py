import random
import re
import statistics
import pathlib
random.seed(0)
roots = list(pathlib.Path('/home/haduong/data/Zotero/storage').glob('*/.zotero-ft-cache'))
sample = random.sample(roots, min(1500, len(roots)))

def kind(cache):
    d = cache.parent
    exts = {p.suffix.lower() for p in d.iterdir() if p.is_file() and not p.name.startswith('.')}
    if '.pdf' in exts:
        return 'pdf'
    if exts & {'.html', '.htm', '.mht'}:
        return 'html'
    return 'other'

buckets = {'pdf': [], 'html': [], 'other': []}
counts = {'pdf': 0, 'html': 0, 'other': 0}
for f in sample:
    try:
        k = kind(f)
        t = f.read_text(errors='replace')
    except Exception:
        continue
    counts[k] += 1
    for p in re.split(r'\n\s*\n', t):
        w = len(p.split())
        if w:
            buckets[k].append(w)

print("attachment mix in sample:", counts)
print()
for k in ('pdf', 'html', 'other'):
    a = sorted(buckets[k])
    if not a:
        continue
    total = sum(a)
    print("=== %s  (%d docs, %d blocks, %d words)" % (k.upper(), counts[k], len(a), total))
    print("  median block %.0f w   mean %.0f w   max %d w" % (statistics.median(a), statistics.mean(a), a[-1]))
    print("  share of total WORDS held by blocks of size:")
    bands = [(0, 10), (10, 50), (50, 150), (150, 350), (350, 600), (600, 10**9)]
    for lo, hi in bands:
        m = sum(w for w in a if lo <= w < hi)
        lab = ("%d-%d w" % (lo, hi)) if hi < 10**9 else ("%d+ w" % lo)
        print("    %12s: %5.1f%%" % (lab, m / total * 100))
    print()
