#!/usr/bin/env bash
# How many PDF attachments carry a native SDT pack, counted on the filesystem.
#
# Ticket 0728 recorded "9 108 PDF attachments, 5 255 carrying a
# `.zotero-sdt-cache`, 3 853 without" on 2026-09-06, and ticket 0606's decision
# — whether to produce packs ourselves — rests on what that residue is. A
# number that decides something has to be re-runnable, so it lives here rather
# than in a scratchpad.
#
# WHY CO-LOCATION AND NOT TWO GLOBAL COUNTS. A pack is a sibling of the file it
# describes, so the question is per storage directory. Counting the two
# populations separately and dividing mixes denominators and yields nonsense:
# on 2026-09-08 this library held 13 699 packs against 9 290 PDFs, because
# packs also sit beside epub and snapshot attachments. The ratio is only
# meaningful over directories that actually hold a PDF.
#
# READ-ONLY. It stats and lists; it writes nothing, and it must stay that way —
# it is pointed at the author's live Zotero storage.
set -uo pipefail

storage="${1:-$HOME/data/Zotero/storage}"

if [ ! -d "$storage" ]; then
  echo "no storage directory at $storage" >&2
  echo "pass one as the first argument" >&2
  exit 2
fi

pdf_dirs=0
pdf_dirs_with_pack=0
other_dirs_with_pack=0

for d in "$storage"/*/; do
  has_pdf=0
  # -maxdepth 1: the pack is a sibling of the file, never in a subdirectory.
  if find "$d" -maxdepth 1 -iname '*.pdf' -type f -print -quit 2>/dev/null | grep -q .; then
    has_pdf=1
  fi
  if [ "$has_pdf" -eq 1 ]; then
    pdf_dirs=$((pdf_dirs + 1))
    [ -e "$d/.zotero-sdt-cache" ] && pdf_dirs_with_pack=$((pdf_dirs_with_pack + 1))
  elif [ -e "$d/.zotero-sdt-cache" ]; then
    other_dirs_with_pack=$((other_dirs_with_pack + 1))
  fi
done

echo "directories holding a PDF        : $pdf_dirs"
echo "  with a .zotero-sdt-cache       : $pdf_dirs_with_pack"
echo "  WITHOUT a pack                 : $((pdf_dirs - pdf_dirs_with_pack))"
echo "packs beside a non-PDF           : $other_dirs_with_pack"
echo

# A zero denominator reports that it could not measure, rather than dividing.
awk -v a="$pdf_dirs_with_pack" -v b="$pdf_dirs" \
  'BEGIN {
     if (b > 0) printf "PDF coverage : %.1f %%\n", 100*a/b;
     else print "PDF coverage : NOT MEASURED — no directory here holds a PDF";
   }'
date -Iseconds
