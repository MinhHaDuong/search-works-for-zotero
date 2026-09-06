#!/usr/bin/env python3
"""Write one question per sampled paragraph, on a local model, in a declared lane.

    python3 -m bench.generator.questions --work-dir /path/private \\
        --writer tjs --transformers-path <dir> --model <hub id of an instruct model, ONNX weights> \\
        --cache-dir ~/data/cache/transformersjs --other-language-share 0.33 --seed 1

**Lanes.** A lane is the pair (question language, answer-paragraph language),
ruling 2 of 2026-09-06. Every question is written in the paragraph's own
language except a declared share, drawn by the seed, written in another of R7's
default-path languages (English, French, Vietnamese), cycling through the
alternatives so the cross-lingual pairs are spread rather than piled on one.

**Writers.** `tjs` drives `tjs_generate.mjs`, a small instruct model through
transformers.js on CPU: local, free, and the runtime the target already
carries. `template` is the deterministic fallback, a fixed sentence per language
around the paragraph's most distinctive words, used when no model runtime is
usable and for every row a model left blank; the artifact says which writer
wrote each question so a run on the fallback is never read as a run on a model.

**What this measures.** A question written from the paragraph it must retrieve
is a self-consistency probe: it asks whether the engine can find a paragraph
from a paraphrase of that paragraph, which is closer to recall than to a user's
need. The report says so; need-driven questions are the Menagerie's.
"""

import argparse
import json
import logging
import random
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from bench.generator.text import STOPWORDS

#: R7's default-path languages, the ones a cross-lingual lane may be written in.
DEFAULT_PATH_LANGUAGES = ("en", "fr", "vi")

TEMPLATES = {
    "en": "What does the text say about {a}, {b} and {c}?",
    "fr": "Que dit le texte sur {a}, {b} et {c} ?",
    "vi": "Văn bản nói gì về {a}, {b} và {c}?",
    "de": "Was sagt der Text über {a}, {b} und {c}?",
    "es": "¿Qué dice el texto sobre {a}, {b} y {c}?",
}

ALL_STOPWORDS = set().union(*STOPWORDS.values())


def assign_lanes(rows: list[dict], share: float, seed: int) -> list[str]:
    """The question language of each row: its own, or another default-path
    language for `share` of the rows, chosen by the seed and cycled."""
    rng = random.Random(seed)
    out = []
    cycle = 0
    for row in rows:
        own = row["language"]
        if rng.random() < share:
            others = [lang for lang in DEFAULT_PATH_LANGUAGES if lang != own]
            out.append(others[cycle % len(others)])
            cycle += 1
        else:
            out.append(own if own in TEMPLATES or own in DEFAULT_PATH_LANGUAGES else "en")
    return out


def distinctive_words(paragraph: str, k: int = 3) -> list[str]:
    """The k longest distinct alphabetic words of at least six letters that are
    not function words, in order of first appearance among the longest."""
    words = re.findall(r"[^\W\d_]{6,}", paragraph)
    seen: dict[str, int] = {}
    for w in words:
        lw = w.lower()
        if lw in ALL_STOPWORDS or lw in seen:
            continue
        seen[lw] = len(seen)
    ranked = sorted(seen, key=lambda w: (-len(w), seen[w]))[:k]
    return sorted(ranked, key=lambda w: seen[w])


def template_question(paragraph: str, language: str) -> str:
    words = distinctive_words(paragraph)
    while len(words) < 3:
        words.append(words[-1] if words else "…")
    return TEMPLATES.get(language, TEMPLATES["en"]).format(a=words[0], b=words[1], c=words[2])


def clean_question(raw: str) -> str:
    """The first non-empty line, unquoted, bounded — a model's answer trimmed to
    what a search box takes."""
    for line in raw.splitlines():
        line = line.strip().strip('"«»“”\'').strip()
        line = re.sub(r"^(question|q)\s*[:：]\s*", "", line, flags=re.I).strip()
        if line:
            return line[:300]
    return ""


def acceptable(question: str, paragraph: str) -> bool:
    """A blank, a one-word reply or a copied sentence is not a question."""
    if len(question.split()) < 3:
        return False
    return question.lower() not in paragraph.lower()


class TemplateWriter:
    name = "template"
    model = "deterministic template"

    def write(self, rows: list[dict]) -> list[dict]:
        return [{"question": template_question(r["paragraph"], r["question_language"]),
                 "writer": self.name, "elapsed_ms": 0} for r in rows]


class TjsWriter:
    """transformers.js through node, one process for the whole batch."""

    name = "tjs"

    def __init__(self, transformers_path: str, model: str, cache_dir: str, dtype: str = "q4",
                 script: Path | None = None, run: Callable = subprocess.run):
        self.transformers_path = transformers_path
        self.model = model
        self.cache_dir = cache_dir
        self.dtype = dtype
        self.script = script or Path(__file__).with_name("tjs_generate.mjs")
        self.run = run

    def write(self, rows: list[dict]) -> list[dict]:
        payload = "".join(json.dumps({"id": i, "paragraph": r["paragraph"], "language": r["question_language"]},
                                     ensure_ascii=False) + "\n" for i, r in enumerate(rows))
        cmd = ["node", str(self.script), "--transformers-path", self.transformers_path,
               "--model", self.model, "--cache-dir", self.cache_dir, "--dtype", self.dtype]
        proc = self.run(cmd, input=payload, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"question writer failed ({proc.returncode}): {proc.stderr[-2000:]}")
        answers: dict[int, dict] = {}
        for line in proc.stdout.splitlines():
            if line.strip():
                d = json.loads(line)
                answers[int(d["id"])] = d
        out = []
        for i, r in enumerate(rows):
            d = answers.get(i, {})
            q = clean_question(d.get("question", ""))
            if acceptable(q, r["paragraph"]):
                out.append({"question": q, "writer": self.name, "elapsed_ms": d.get("elapsed_ms")})
            else:
                out.append({"question": template_question(r["paragraph"], r["question_language"]),
                            "writer": "template-fallback", "elapsed_ms": d.get("elapsed_ms")})
        return out


def write_questions(rows: list[dict], writer, share: float, seed: int) -> list[dict]:
    lanes = assign_lanes(rows, share, seed)
    for row, lang in zip(rows, lanes):
        row["question_language"] = lang
        row["lane"] = f"{lang}->{row['language']}"
        row["cross_lingual"] = lang != row["language"]
    written = writer.write(rows)
    for row, w in zip(rows, written):
        row.update(w)
        row["model"] = writer.model
    return rows


def questions_summary(rows: list[dict], writer, share: float) -> dict:
    from collections import Counter
    return {
        "n": len(rows),
        "writer": writer.name,
        "model": writer.model,
        "other_language_share_declared": share,
        "cross_lingual": sum(1 for r in rows if r["cross_lingual"]),
        "lanes": dict(Counter(r["lane"] for r in rows).most_common()),
        "written_by": dict(Counter(r["writer"] for r in rows)),
        "question_language": dict(Counter(r["question_language"] for r in rows).most_common()),
        "elapsed_ms_total": sum(r.get("elapsed_ms") or 0 for r in rows),
    }


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_writer(args: argparse.Namespace):
    if args.writer == "tjs":
        if not (args.transformers_path and args.model and args.cache_dir):
            raise SystemExit("--writer tjs needs --transformers-path, --model and --cache-dir")
        w = TjsWriter(args.transformers_path, args.model, args.cache_dir, dtype=args.dtype)
        w.model = f"{args.model} ({args.dtype}, transformers.js at {args.transformers_path})"
        return w
    return TemplateWriter()


def add_arguments(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--writer", choices=["tjs", "template"], default="template")
    ap.add_argument("--transformers-path", default="", help="a @huggingface/transformers package directory")
    ap.add_argument("--model", default="", help="model id for the text-generation pipeline")
    ap.add_argument("--cache-dir", default="", help="where transformers.js keeps model files")
    ap.add_argument("--dtype", default="q4")
    ap.add_argument("--other-language-share", type=float, default=1 / 3,
                    help="share of questions written in another default-path language")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(ap)
    ap.add_argument("--work-dir", type=Path, required=True, help="holds sample.jsonl; questions.jsonl is written beside it")
    ap.add_argument("--seed", type=int, default=1)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = load_rows(args.work_dir / "sample.jsonl")
    writer = build_writer(args)
    rows = write_questions(rows, writer, args.other_language_share, args.seed)
    with (args.work_dir / "questions.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = questions_summary(rows, writer, args.other_language_share)
    (args.work_dir / "questions-summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    logging.info("wrote %d questions (%s)", len(rows), summary["written_by"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
