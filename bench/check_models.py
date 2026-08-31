"""The sixth guard. One model name, one place: `bench/models.json`.

The candidate field for the embedder study was discovered one repository at a time,
and the discoveries did not survive: a mirror ruled out on an unauthenticated 401
turned out to publish the full dtype set, and a repo id that no search can resolve
was recorded as gated. The registry exists so that each of those facts is written
down once, with the state it was observed in, and read by every child of the study.
That only holds if nothing else in `bench/` names a model — a driver with its own
default is a second copy of the field, and the second copy is the one that goes
stale.

Two checks, failing in opposite directions.

**The registry is well formed.** Every record carries every key, the availability
state is one of exactly three, a candidate is loadable, and a model that fails R7 is
recorded as rejected rather than benchmarked.

**No model id appears in `bench/` outside it.** Both the ids the registry declares
and ones it has never heard of: a guard built from the registry's own vocabulary
catches a model being removed and misses one being added, which is the direction
that matters.

R7's language list is read from `spec/REQUIREMENTS.md`, not restated here. Editing
R7 moves this guard with it, and a sheet this script cannot parse is an error rather
than a pass.

    python3 bench/check_models.py [repo-root]
"""

import argparse
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("check_models")

#: The registry. Every other file in `bench/` reads a model through it.
REGISTRY = "bench/models.json"

#: R7's owner. The five languages are its sentence's, not this file's.
R7_SOURCE = "spec/REQUIREMENTS.md"

#: Scanned in full, minus the exemptions and the data directory below.
SCANNED_ROOT = "bench"

#: Data, not code. A result record names the model it measured and must: a cell
#: whose provenance is anonymous cannot be read a month later. Skipping the
#: directory is the one place this guard trades coverage for meaning, and it is
#: bounded — nothing under it is executable. The trailing slash is load-bearing:
#: without it a sibling named `results_backup` or `results-2026` would inherit the
#: exemption by prefix, and an exemption nobody granted is the one nobody audits.
#: `__pycache__` joins it for a different reason: the bytecode is generated from
#: source this guard already scans, so reading it buys nothing, and it is binary —
#: which, now that an undecodable file is a failure rather than a silent skip, would
#: turn every `make check` after a test run red. Generated-and-binary is exempt;
#: authored-and-undecodable is a finding.
SKIPPED = ("bench/results/", "bench/__pycache__/")

#: Exempt, each for its own reason, and there are only two. The registry is the
#: owner. This file holds the vocabulary by construction — the owner names below
#: are what it greps for.
EXEMPT = {REGISTRY, "bench/check_models.py"}

#: Read by `verification/probes/probe_onnx_dtypes.py` and by every child of the
#: study. `available` means the file listing was read and at least one dtype is
#: addressable; `confirmed_absent` means it was read and none is; `could_not_look`
#: means it was not read. The third is not a kind of absence, and collapsing it into
#: one is the mistake this study is correcting.
STATES = {
    "available": "listing read; at least one addressable ONNX file",
    "confirmed_absent": "listing read; no addressable ONNX file",
    "could_not_look": "listing not read (401, gated, 404, network)",
}

REQUIRED_KEYS = {
    "id",
    "hf_repo",
    "upstream_repo",
    "params",
    "dim",
    "max_seq",
    "max_seq_source",
    "languages",
    "licence",
    "mrl",
    "input_template",
    "availability",
    "status",
    "notes",
}

STATUSES = ("candidate", "rejected")

#: The pooling modes a driver can actually pass to transformers.js, read from the
#: `switch` in `src/pipelines/feature-extraction.js` rather than assumed: `mean`,
#: `first_token`/`cls`, `last_token`/`eos`, with `default:` throwing. A candidate
#: whose card names anything else is a finding about that candidate — it is not
#: coerced into one of these, because the coercion would be invisible in the results.
#:
#: Measured 2026-08-29: four of the six candidates pool with `cls` while every driver
#: hardcoded `mean`, so the hardcoded default was wrong for the majority of the field,
#: including both Granite models.
POOLINGS = {"mean", "cls", "last_token"}

#: A rejection names which filter caught it. `r7` is the language list, `licence`
#: the terms, `size` the parameter count, `token-ceiling` the sequence length the
#: model truncates to, `no-onnx` a repo publishing none, `unsweepable-dtypes` a repo
#: publishing ONNX under names the dtype knob cannot address, `unresolved-id` a repo
#: id nothing resolves.
REJECTION_CRITERIA = (
    "r7",
    "licence",
    "size",
    "token-ceiling",
    "no-onnx",
    "unsweepable-dtypes",
    "unresolved-id",
)

#: Hub owners that publish text embedders. Membership makes `owner/name` a model id
#: whatever the name looks like.
KNOWN_OWNERS = {
    "alibaba-nlp",
    "baai",
    "cohere",
    "google",
    "ibm-granite",
    "intfloat",
    "jinaai",
    "mixedbread-ai",
    "nomic-ai",
    "onnx-community",
    "openai",
    "qwen",
    "sentence-transformers",
    "snowflake",
    "thenlper",
    "xenova",
}

#: Model-family words. These make `owner/name` a model id whatever the owner is,
#: which is how a publisher nobody has heard of yet still gets caught.
#:
#: The boundary is real and it is declared rather than papered over: an id from an
#: unlisted publisher whose name carries none of these words escapes — a Russian or a
#: fashion-retrieval model would. Widening the pattern until nothing escapes turns
#: every `owner/name` string in a comment into a failure, and a guard that cries wolf
#: gets exempted rather than fixed. `test_the_heuristic_boundary_is_declared` pins
#: what escapes today, so the hole is a known size instead of an assumption.
FAMILY = re.compile(
    r"embed|e5|bge|gte|minilm|mpnet|distiluse|arctic|granite|nomic|jina|labse|"
    r"gemma|qwen|multilingual|paraphrase|instructor|stella",
    re.IGNORECASE,
)

#: `owner/name`, both segments free of slashes and of surrounding path characters.
TOKEN = re.compile(r"(?<![\w./-])([A-Za-z0-9][\w.-]{0,40})/([A-Za-z0-9][\w.-]{0,60})(?![\w./-])")

#: A path segment, not a repo name. `erg` joined 2026-08-30, from two sessions
#: independently: a ticket path (`tickets/0266-…-multilingual.erg`,
#: `tickets/0140-…-embedder-….erg`) is a path like any other, and the first
#: ticket filenames to also contain a FAMILY word showed the extension list
#: had never had to cover it. `tickets` joined PATH_OWNERS the same day.
EXTENSION = re.compile(r"\.(onnx|json|mjs|js|ts|py|md|txt|sh|jsonl|f32|log|csv|html|erg)$", re.I)

#: Directory names that open a path, not an owner.
PATH_OWNERS = {
    "bench",
    "spec",
    "tests",
    "tickets",
    "verification",
    "results",
    "onnx",
    "src",
    "node_modules",
    "tmp",
    "http",
    "https",
    "fork",
    "and",
    "km",
    "s",
}

#: English names to ISO 639-1, for reading R7's sentence. The mapping is the
#: standard's, not a fact this repository owns.
ISO_639_1 = {
    "arabic": "ar",
    "chinese": "zh",
    "dutch": "nl",
    "english": "en",
    "french": "fr",
    "german": "de",
    "greek": "el",
    "hebrew": "he",
    "hindi": "hi",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "portuguese": "pt",
    "russian": "ru",
    "spanish": "es",
    "vietnamese": "vi",
}

#: R7's two operative sentences, since the two tiers were ruled on 2026-08-31.
#: The MUST tier is a filter — a candidate that does not declare it is not a
#: candidate. The SHOULD tier is a preference that may be set aside for a stated
#: reason, so a gap there is reported and not failed; failing it would quietly
#: promote SHOULD to MUST, which is the one thing RFC 2119 asks a reader not to
#: do. Both are read from the sheet rather than restated here.
R7_MUST = re.compile(
    r"\*\*R7[^*]*\*\*(?P<body>.{0,400}?)with no configuration", re.DOTALL | re.IGNORECASE
)
R7_SHOULD = re.compile(
    r"SHOULD work, with no configuration, for(?P<body>.{0,200}?)[.;]", re.DOTALL
)


def _codes(body: str, sheet: Path, which: str) -> set[str]:
    codes = {code for name, code in ISO_639_1.items() if re.search(rf"\b{name}\b", body.lower())}
    if len(codes) < 2:
        raise ValueError(f"R7's {which} sentence in {sheet} names no language list")
    return codes


def r7_language_codes(sheet: Path) -> tuple[set[str], set[str]]:
    """R7's `(must, should)` ISO codes. Raises when either sentence cannot be read."""
    text = sheet.read_text(encoding="utf-8") if sheet.is_file() else ""
    must, should = R7_MUST.search(text), R7_SHOULD.search(text)
    if not must:
        raise ValueError(f"could not read R7's MUST language sentence in {sheet}")
    if not should:
        raise ValueError(f"could not read R7's SHOULD language sentence in {sheet}")
    return _codes(must.group("body"), sheet, "MUST"), _codes(should.group("body"), sheet, "SHOULD")


def load_registry(root: Path) -> dict:
    return json.loads((root / REGISTRY).read_text(encoding="utf-8"))


def scanned_files(root: Path) -> list[Path]:
    """Every file under `bench/`, minus the data directory and the two exemptions."""
    files = []
    for path in sorted((root / SCANNED_ROOT).rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in EXEMPT or rel.startswith(SKIPPED):
            continue
        files.append(path)
    return files


def model_ids_in(text: str) -> set[str]:
    """Tokens shaped like a hub repo id and reading like a model."""
    found = set()
    for match in TOKEN.finditer(text):
        owner, name = match.group(1), match.group(2)
        if owner.lower() in PATH_OWNERS or EXTENSION.search(name):
            continue
        if owner.lower() in KNOWN_OWNERS or FAMILY.search(name):
            found.add(f"{owner}/{name}")
    return found


def check_registry(root: Path, failures: list[str]) -> None:
    """Well-formedness, and the two invariants a record can violate on its own."""
    try:
        registry = load_registry(root)
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f"{REGISTRY} does not parse: {error}")
        return
    try:
        r7, r7_should = r7_language_codes(root / R7_SOURCE)
    except (OSError, ValueError) as error:
        failures.append(str(error))
        return

    models = registry.get("models")
    if not isinstance(models, list) or not models:
        # An all-clear here would be indistinguishable from "I could not look":
        # a bad merge or a half-written regeneration leaves the payload empty,
        # and every record-level check below then passes vacuously.
        failures.append(
            f"{REGISTRY}: no 'models' list to check "
            f"(got {type(models).__name__}). A registry with no records is a "
            f"failure to read it, not a clean sheet."
        )
        return

    for record in models:
        name = record.get("id", "<no id>")
        missing = sorted(REQUIRED_KEYS - set(record))
        if missing:
            failures.append(f"{name}: missing {', '.join(missing)}")
            continue
        state = record["availability"].get("state")
        if state not in STATES:
            failures.append(f"{name}: availability state {state!r} is not one of {sorted(STATES)}")
        if record["status"] not in STATUSES:
            failures.append(f"{name}: status {record['status']!r} is not one of {STATUSES}")
        if record["status"] == "candidate":
            if state != "available" or not record["availability"].get("dtypes"):
                failures.append(f"{name}: a candidate must have an addressable dtype")
            codes = set((record["languages"] or {}).get("codes") or [])
            if not r7 <= codes:
                failures.append(
                    f"{name}: candidate does not declare R7's MUST languages "
                    f"(missing {sorted(r7 - codes)})"
                )
            elif not r7_should <= codes:
                # Not a failure: a SHOULD set aside is allowed and has to be
                # stated, so this prints where the statement would have to go.
                logger.info(
                    "NOTE %s: declares R7's MUST tier and not all of its SHOULD tier "
                    "(missing %s); setting one aside is allowed and must be said",
                    name,
                    sorted(r7_should - codes),
                )
            # Required on candidates only, and required in a pair. Pooling is the
            # input_template trap one axis over: a wrong value degrades retrieval
            # silently, so it reads as the model being worse rather than as a bug,
            # and a sweep can reject a good candidate on it. The `_source` half is
            # what stops the value from being a plausible guess — it names the file
            # it was read from.
            if record.get("pooling") not in POOLINGS:
                failures.append(
                    f"{name}: candidate pooling is {record.get('pooling')!r}, "
                    f"not one of {sorted(POOLINGS)}. Read it from the model's own "
                    f"1_Pooling/config.json; do not infer it from a sibling model."
                )
            if not (record.get("pooling_source") or "").strip():
                failures.append(
                    f"{name}: pooling carries no pooling_source. A value with no "
                    f"provenance cannot be told from a guess."
                )
            # normalize: whether the pipeline L2-normalizes the pooled vector, read
            # from the model's own modules.json (a declared Normalize module), same
            # provenance discipline as pooling. Unlike pooling, "the value could not
            # be determined" is itself a legitimate recorded state here — ticket
            # 0262 requires it be written as the literal string "unknown" rather
            # than defaulted to true or false, so it is a required field with three
            # allowed values rather than a required determination.
            if record.get("normalize") not in (True, False, "unknown"):
                failures.append(
                    f"{name}: candidate normalize is {record.get('normalize')!r}, "
                    f"not True, False, or 'unknown'. Read it from the model's own "
                    f"modules.json; record 'unknown' rather than guessing."
                )
            if not (record.get("normalize_source") or "").strip():
                failures.append(
                    f"{name}: normalize carries no normalize_source. A value with "
                    f"no provenance cannot be told from a guess."
                )
            # hf_revision: the commit sha the availability probe read on hf_repo,
            # so a sweep result can later be checked against the registry state
            # that produced it (ticket 0262).
            if not (record.get("hf_revision") or "").strip():
                failures.append(
                    f"{name}: candidate hf_revision is missing. Record the repo "
                    f"commit sha the availability probe read "
                    f"(HF API GET /api/models/{{repo}} returns 'sha')."
                )
        else:
            criteria = record.get("rejection", {}).get("criteria") or []
            if not criteria:
                failures.append(f"{name}: rejected with no criterion")
            unknown = sorted(set(criteria) - set(REJECTION_CRITERIA))
            if unknown:
                failures.append(f"{name}: unknown rejection criteria {unknown}")


#: Prose that must name the model it describes, marked line by line.
#:
#: The guard's remedy — "declare it in the registry and resolve it by id" — is
#: available to code and impossible in prose. A docstring explaining what was
#: measured, or a result's own `what:` provenance label, has to carry the literal
#: name: a cell whose provenance is anonymous cannot be read a month later, which
#: is the same argument that exempts `bench/results/` wholesale. Exempting the
#: file would be the cheap version and would hide a real wiring bug in the next
#: driver that grows a comment. So the exemption is per line, carries its reason
#: on the line, and greps out in one command.
EXEMPT_MARKER = "model-id-literal:"


#: `pooling: 'mean'` or `pooling="cls"` — the mode as a literal at a call site.
#:
#: Model identity had a mechanical guard from the start; pooling did not, and the
#: review of 0421 proved the difference by reverting one driver to a hardcoded
#: `'mean'` and watching the whole gate pass. The literal is the whole defect: the
#: value must come from the registry, because the model it is right for is a
#: property of the model, not of the driver.
#:
#: The optional quotes around the key are load-bearing. The first version required a
#: bare `pooling`, so `{ "pooling": "mean" }` — a shape that already exists in
#: `registry.py` — evaded it completely. `record["pooling"] = ...` still passes,
#: because the `[` is consumed by the lookbehind's word/dot exclusion only when the
#: key is followed by `]` rather than by a colon or equals.
#:
#: Still deliberately narrow, and the residue is documented rather than denied: a
#: literal assembled by concatenation, held in a variable, or split across a
#: continuation line evades any per-line literal scan. So does anything a
#: sufficiently determined author writes. This catches the shape a tired author
#: actually writes, which is the one that regressed.
#: Why `input_template` DOES get the same guard, decided under ticket 0422 after a
#: first pass here retracted it.
#:
#: The retraction argued the template literals are ordinary words already present in
#: benign code. The count was right — `query: ` and `passage: ` occur five times
#: under `bench/` — and the conclusion was wrong, because it priced a bare substring
#: scan rather than the quote-requiring shape the pooling scan already uses. Under
#: that shape four of the five are not literals at all (`{ query: q }`, a prose
#: sentence, and `ms_per_passage:` twice, where `passage` is preceded by a word
#: character), leaving one real site: `registry.mjs`'s own empty-template default, in
#: the file that owns the value. One exemption in the owning file is the same trade
#: already made for `REGISTRY` itself.
#:
#: Retracting a guard because the *cheap* version of it would be noisy is the mistake
#: this note now records. What follows is the superseded reasoning, kept because the
#: shape of the error is worth more than the conclusion was:
#:
#: 0421 framed pooling as "the input_template trap one axis over", which implied a
#: parity of protection. That claim is retracted here rather than made true, and the
#: reason is structural rather than effort. A pooling mode is a keyword argument
#: drawn from a closed enum, so `pooling: 'mean'` is syntactically distinctive and a
#: scan for it is quiet on a clean tree. A template is a free-form prefix
#: concatenated into text, and its literals are ordinary words: `query: ` and
#: `passage: ` already occur five times under `bench/` in `{ query: q }`, in
#: `ms_per_passage:`, and inside a sentence about a semantic query. A substring scan
#: for them is red on arrival, and a guard that cries wolf gets exempted rather than
#: fixed — which would cost more than the hole.
#:
#: What protects the templates instead is weaker and should be read as weaker: the
#: drivers destructure `template` from `resolveModel`, and nothing mechanical stops
#: one from inlining a prefix. If that becomes a real defect rather than a
#: hypothetical one, the tractable half is the two distinctive nomic prefixes
#: (`search_document: `, `search_query: `), which collide with nothing.

POOLING_LITERAL = re.compile(r"""(?<![\w.])['"]?pooling['"]?\s*[:=]\s*['"]""")


def template_literals(root: Path) -> set[str]:
    """Every non-empty input_template value the registry declares."""
    try:
        registry = load_registry(root)
    except (OSError, json.JSONDecodeError):
        return set()
    models = registry.get("models")
    if not isinstance(models, list):
        # A malformed registry is check_registry's failure to report, not this
        # scan's to crash on. Iterating a dict here yields its keys and calls
        # .get() on a string — which is exactly what the wrong-type test caught.
        return set()
    found = set()
    for record in models:
        if not isinstance(record, dict):
            continue
        for value in (record.get("input_template") or {}).values():
            if isinstance(value, str) and value.strip():
                found.add(value)
    return found


def check_no_hard_coded_templates(root: Path, failures: list[str]) -> None:
    """A registry-declared prefix written as a literal instead of resolved.

    Registry-derived, so it inherits the id scan's known asymmetry: it catches a
    declared prefix being inlined and cannot catch a prefix for a model nobody has
    declared yet. Weaker than the pooling scan, and written down as weaker rather
    than implied to be equal.
    """
    literals = template_literals(root)
    if not literals:
        return
    owners = {REGISTRY, "bench/check_models.py", "bench/registry.mjs", "bench/registry.py"}
    for path in scanned_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in owners:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if EXEMPT_MARKER in line:
                continue
            for literal in sorted(literals):
                if f"'{literal}'" in line or f'"{literal}"' in line:
                    failures.append(
                        f"{rel}:{number}: writes the input template {literal!r} "
                        f"literally. Resolve it from {REGISTRY} — the prefix a model "
                        f"needs is a property of the model, not of the driver."
                    )
                    break


def check_no_hard_coded_pooling(root: Path, failures: list[str]) -> None:
    """A pooling mode written at a call site instead of resolved from the registry."""
    for path in scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Reported already by the id scan, which reads the same file set; a
            # second identical failure per file would be noise, not information.
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if EXEMPT_MARKER in line:
                continue
            if POOLING_LITERAL.search(line):
                failures.append(
                    f"{path.relative_to(root).as_posix()}:{number}: names a pooling "
                    f"mode literally. Resolve it from {REGISTRY} — the right mode is a "
                    f"property of the model, not of the driver."
                )


def check_no_hard_coded_ids(root: Path, failures: list[str]) -> None:
    for path in scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            # Skipping silently would exempt the whole file from the invariant,
            # and a single stray byte is enough to do it. Unreadable is a
            # failure to look, which this guard reports rather than swallows.
            failures.append(
                f"{path.relative_to(root).as_posix()}: cannot be scanned for "
                f"model ids ({error}). Fix the file's encoding; an unreadable "
                f"file is not a clean one."
            )
            continue
        scannable = "\n".join(
            line for line in text.splitlines() if EXEMPT_MARKER not in line
        )
        for model in sorted(model_ids_in(scannable)):
            failures.append(
                f"{path.relative_to(root).as_posix()}: names the model {model!r}. "
                f"Declare it in {REGISTRY} and resolve it by registry id."
            )


def run(root: Path) -> int:
    failures: list[str] = []
    check_registry(root, failures)
    check_no_hard_coded_ids(root, failures)
    check_no_hard_coded_pooling(root, failures)
    check_no_hard_coded_templates(root, failures)
    for failure in failures:
        logger.error("%s", failure)
    if failures:
        logger.error("%d failure(s)", len(failures))
        return 1
    logger.info(
        "OK: the registry is well formed, and nothing else in bench/ names a model, "
        "a pooling mode, or an input template"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to check (default: this file's repository)",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return run(parse_args().root)


if __name__ == "__main__":
    raise SystemExit(main())
