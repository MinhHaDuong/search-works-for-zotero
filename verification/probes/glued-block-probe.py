"""Are 350+ word blocks real paragraphs or extraction artifacts? Look at them."""
import pathlib
import random
import re

random.seed(1)
roots = list(pathlib.Path("/home/haduong/data/Zotero/storage").glob("*/.zotero-ft-cache"))
sample = random.sample(roots, 400)

def is_pdf(cache):
    d = cache.parent
    return any(p.suffix.lower() == ".pdf" for p in d.iterdir() if p.is_file())

big = []
for f in sample:
    if not is_pdf(f):
        continue
    try:
        t = f.read_text(errors="replace")
    except OSError:
        continue
    for p in re.split(r"\n\s*\n", t):
        w = len(p.split())
        if w >= 350:
            big.append((w, p, f.parent.name))

print(f"{len(big)} blocks of 350+ words in {sum(1 for f in sample if is_pdf(f))} sampled PDFs")

# Diagnostics per big block: how many internal sentence-end + newline + capital
# seams does it contain (candidate lost paragraph breaks), and line shape.
def seams(p):
    return len(re.findall(r"[.!?]\n[A-ZÀ-Ü]", p))

seamy = sum(1 for w, p, _ in big if seams(p) >= 2)
print(f"{seamy} of {len(big)} big blocks contain 2+ 'sentence-end\\nCapital' seams (glued-paragraph signature)")

for w, p, key in random.sample(big, min(3, len(big))):
    lines = p.splitlines()
    print(f"\n=== {key}  {w} words, {len(lines)} lines, {seams(p)} seams ===")
    print("\n".join(lines[:6]))
    print("   [...]")
