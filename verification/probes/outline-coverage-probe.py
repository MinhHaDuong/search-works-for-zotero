"""Do book-sized PDFs carry a chapter outline the PDF side can segment by?"""
import pathlib
import random
import subprocess

random.seed(3)
pdfs = []
for d in pathlib.Path("/home/haduong/data/Zotero/storage").iterdir():
    if not d.is_dir():
        continue
    for p in d.iterdir():
        if p.suffix.lower() == ".pdf" and p.stat().st_size > 3_000_000:
            pdfs.append(p)
            break
sample = random.sample(pdfs, min(60, len(pdfs)))

with_outline = big = 0
for p in sample:
    try:
        info = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=20)
        pages = 0
        for line in info.stdout.splitlines():
            if line.startswith("Pages:"):
                pages = int(line.split()[-1])
    except Exception:
        continue
    if pages < 100:
        continue
    big += 1
    try:
        out = subprocess.run(["mutool", "show", str(p), "outline"],
                             capture_output=True, text=True, timeout=30)
        if out.stdout.strip():
            with_outline += 1
    except Exception:
        pass

print(f"book-sized PDFs (>3MB file): {len(pdfs)} in library; sampled {len(sample)}")
print(f"of sampled, 100+ pages: {big}; with a machine-readable outline: {with_outline}")
