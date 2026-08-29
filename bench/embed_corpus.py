"""Embed a passage corpus with a Matryoshka-trained model, resumably, to a flat float32 file.

Ticket 0008 measured the precision axis of the vector-size trade on the shipped 384-dim
on-device model. The dimension axis needs a model whose prefixes are themselves valid
embeddings — Matryoshka Representation Learning — and none of zoteus's own defaults is
one: `all-MiniLM-L6-v2` (384) and Gemini's `text-embedding-004` (768) are fixed-width,
and only the OpenAI models reachable through `ZOTEUS_EMBEDDING_MODEL` are MRL. So the
vectors this driver needs cannot come out of the existing index; they have to be made.

The output is a flat `float32` file of N x dim, row-aligned with the input lines, which is
what `bench/vec_mrl_recall.mjs --f32` reads. Row alignment with the input is the whole
contract: the recall driver pairs these vectors with `passages.items` by position, so a
dropped or reordered line silently scores every probe against the wrong neighbours.

**Resumable, deliberately.** A long GPU run that dies at 80% and has to start from zero is
the exact defect upstream issue #24 reports against zoteus's own build path, and it is not
more acceptable in a bench driver. Progress is the size of the output file — derived from
the artifact itself rather than from a sidecar that can disagree with it — so an interrupted
run resumes at the first row it has not written, and a completed run is a no-op.
"""

import argparse
import json
import logging
import os
from pathlib import Path

from registry import resolve_model

logger = logging.getLogger("embed_corpus")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", type=Path, required=True, help="one passage per line")
    p.add_argument("--output", type=Path, required=True, help="flat float32, N x dim")
    p.add_argument(
        "--model",
        default="qwen3-embedding-06b",
        help=(
            "a registry id from bench/models.json, resolved to its upstream repository "
            "because this driver loads through sentence-transformers rather than ONNX. "
            "A literal owner/name still works and warns."
        ),
    )
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--device", default=None, help="cuda / cpu; default: auto")
    p.add_argument(
        "--dtype",
        default="float16",
        choices=("float16", "bfloat16", "float32"),
        help="compute dtype on GPU; sentence-transformers defaults to float32, which "
        "doubles the memory and roughly halves the throughput for no gain here — the "
        "embeddings are written as float32 either way",
    )
    p.add_argument("--limit", type=int, default=0, help="embed only the first N lines (0 = all)")
    p.add_argument("--max-seq-length", type=int, default=0, help="override the model's own")
    return p.parse_args()


def rows_done(output: Path, row_bytes: int) -> int:
    """How many complete rows the artifact already holds.

    Derived from the file rather than from a progress sidecar: a sidecar is a second
    source of truth that can disagree with the artifact, and the disagreement is silent.
    A trailing partial row (a process killed mid-write) is truncated rather than trusted.
    """
    if not output.exists():
        return 0
    size = output.stat().st_size
    complete = size // row_bytes
    if size % row_bytes:
        logger.warning("truncating a partial trailing row (%d stray bytes)", size % row_bytes)
        os.truncate(output, complete * row_bytes)
    return complete


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    # float16 is a GPU economy; on CPU it is emulated and slower than float32, so the
    # request is honoured only where it pays.
    dtype = getattr(torch, args.dtype) if device.startswith("cuda") else torch.float32
    repo = resolve_model(args.model, kind="upstream")["repo"]
    logger.info("loading %s on %s (%s)", repo, device, dtype)
    model = SentenceTransformer(
        repo,
        device=device,
        trust_remote_code=True,
        model_kwargs={"torch_dtype": dtype},
    )
    if args.max_seq_length:
        model.max_seq_length = args.max_seq_length
    dim = model.get_sentence_embedding_dimension()
    logger.info("dim %d, max_seq_length %s", dim, model.max_seq_length)

    lines = args.input.read_text(encoding="utf-8").splitlines()
    if args.limit:
        lines = lines[: args.limit]
    row_bytes = dim * 4

    start = rows_done(args.output, row_bytes)
    if start >= len(lines):
        logger.info("%s already holds all %d rows; nothing to do", args.output, len(lines))
        return
    if start:
        logger.info("resuming at row %d of %d", start, len(lines))

    meta = {
        "model": repo,
        "model_id": args.model,
        "dim": dim,
        "rows": len(lines),
        "input": str(args.input),
        "max_seq_length": model.max_seq_length,
        "normalized": False,
        "note": "raw embeddings; the recall driver computes its own norms",
    }
    args.output.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    # Append mode, flushed per batch: the file IS the progress record, so a batch that
    # reaches disk is a batch that never runs again.
    with args.output.open("ab") as fh:
        for lo in range(start, len(lines), args.batch):
            chunk = lines[lo : lo + args.batch]
            vecs = model.encode(
                chunk,
                batch_size=len(chunk),
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            ).astype(np.float32)
            if vecs.shape != (len(chunk), dim):
                raise SystemExit(f"expected {(len(chunk), dim)} from encode, got {vecs.shape}")
            fh.write(vecs.tobytes())
            fh.flush()
            done = lo + len(chunk)
            if (lo // args.batch) % 20 == 0 or done == len(lines):
                logger.info("%d / %d rows (%.1f%%)", done, len(lines), 100 * done / len(lines))

    final = args.output.stat().st_size // row_bytes
    if final != len(lines):
        raise SystemExit(f"wrote {final} rows, expected {len(lines)}")
    logger.info("done: %d rows x %d dims -> %s", final, dim, args.output)


if __name__ == "__main__":
    main()
