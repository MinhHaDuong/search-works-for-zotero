"""Every ``resource://`` the sitter names exists in an installed Zotero.

Three defects in one evening (ticket 0731) shared one shape: the plugin asked
the host for something the host does not have, and every test agreed with it
because every test supplied the thing itself. A mocked ``importESModule``
answered ``resource://gre/modules/Fluent.sys.mjs`` for forty green tests over a
locale layer that threw on every startup it ever had. The only instrument that
could settle it was the author's Browser Console, because nothing in this
repository stated what the host provides and checked it against a host.

So this suite reads no mock. It opens the two archives a real Zotero ships and
asks them.

The mapping, verified on 2026-09-08 against ``/opt/zotero7`` (Zotero 10.0.1) by
listing both jars rather than by reading documentation:

* ``resource://gre/<p>`` -> entry ``<p>`` in ``<install>/omni.ja``. That root is
  built into Gecko and is declared in no manifest line, so it is the one alias
  hard-coded below; ``resource://gre/modules/Timer.sys.mjs`` is
  ``modules/Timer.sys.mjs``.
* every other host is read out of the archives' own ``chrome.manifest`` files,
  whose ``resource <host> <target>`` lines are relative to the *directory of the
  manifest that declares them* — the root ``chrome.manifest`` of the app jar
  maps ``zotero`` to ``resource/``, while ``chrome/chrome.manifest`` of the GRE
  jar maps ``gre-resources`` to ``chrome/toolkit/res/``. Deriving the table
  rather than hard-coding it is what makes the guard survive a Zotero that moves
  its own furniture.

What this guard cannot see, stated here because a guard whose blind spot is
undocumented gets trusted past it:

* **Ambient globals.** ``FluentBundle``, ``Services``, ``ChromeUtils``,
  ``IOUtils``, ``PathUtils`` and ``Zotero`` are handed to the bootstrap scope by
  the host. They are compiled into ``libxul`` or injected by the application and
  are named by no archive entry, so no amount of reading ``omni.ja`` can decide
  whether one of them is present. ``FluentBundle`` was exactly such a global,
  and the console was the only way to settle it. This suite deliberately does
  not pretend otherwise: it makes no claim about them at all.
* **Assembled URLs.** The scan reads string literals, so a spec built by
  concatenation or interpolation — ``'resource://' + host + '/modules/x.mjs'``,
  or a template hole — passes through unseen, this ticket's own namesake string
  included. Every call site today writes the URL whole, and keeping it that way
  is what keeps the guard honest; folding constants would want an AST, not a
  regex.
* **Members.** The guard answers "the file is in the jar", never "the file
  exports the symbol the plugin destructures off it".
* **Delivery.** ``jar:`` URIs built from ``rootURI`` at runtime, the second
  defect of that evening, carry no ``resource://`` literal and are out of range
  here.
* **A URL quoted in a comment that trails code.** ``LINE_COMMENT`` drops
  narration owning a whole line; a comment opened *after* a statement is not
  dropped, and the quote anchor then reads the URL inside it as a call site.
  ``test_a_url_quoted_in_a_trailing_comment_is_a_known_false_red`` pins that
  behaviour rather than asserting it, so the blind spot is demonstrated. The
  cost is a false RED: the guard demands a resource nobody asks for, and the
  reader either rewords the comment or the URL turns out to exist anyway.
  Nothing is lost.

  This is the ticket's own sanctioned outcome (0737 item 1: "anchor the
  extraction on a call shape rather than on a preceding quote, or accept it and
  say so in the blind-spot list"), and it is here because the other branch was
  tried three times and failed three times. Closing it means telling a comment
  from code, which means telling a division from a regular expression, which in
  JavaScript needs parser context a character scanner does not have. Each of the
  three attempts blanked live source somewhere, which is a *silent pass* and the
  one failure this ticket forbids outright; ``REGEX_HAZARDS`` records what each
  one got wrong and stands as the tripwire against a fourth. A parser would
  settle it, and this project depends on none — ``requirements-check.txt`` names
  ``ruff``, ``pytest`` and ``numpy``, and neither ``esprima`` nor
  ``tree_sitter`` is importable here — so one added for an auxiliary guard costs
  more than the false red it buys. See PR #461 before trying again.
* **A line ``LINE_COMMENT`` drops that was not a comment.** Two shapes, both
  silent passes, both accepted for the same reason as the entry above: a line
  beginning ``*`` that is code rather than a JSDoc continuation — a generator
  method ``*steps()``, an exponent or a multiplication continued onto the next
  line — and any line inside a multi-line template literal, where the text is
  data. Separating either from a real comment means deciding whether a line is
  code, which is the parser problem stated above at line granularity instead of
  character granularity. Nothing under ``plugins/`` writes either shape (the
  census is zero lines matching ``^\\s*\\*``), and
  ``test_a_block_comment_that_closes_beside_code_is_not_dropped`` pins both as
  losses, so a future fix cannot land while this list still claims them.

  Three neighbouring shapes that WERE silent passes are fixed rather than
  accepted, because each had a rule that needed no judgement about what the
  source means: a block comment closing beside code and one opening and closing
  on the same line (round 4 of the review on PR #461), and a line cut where
  Python breaks lines but JavaScript does not — ``str.splitlines`` also splits
  on ``\\v``, ``\\f``, ``\\x1c``-``\\x1e``, ``\\x85``, ``\\u2028`` and
  ``\\u2029``, the last two legal raw inside a JavaScript string since ES2019
  (round 5).
* **A directory it cannot enter.** ``Path.rglob`` drops an unreadable directory
  silently — no entry, no error, no warning — so a subtree under ``plugins/``
  with the wrong mode is not scanned and nothing says so. An unreadable *file*
  is warned about; an unreadable *directory* is not. Pre-existing, and the
  quietest failure in this file: unlike everything else here it is not even a
  false red. Nothing under ``plugins/`` has ever carried such a mode, and a
  reader who changes that should expect no help from this suite.

Two over-reaches this file keeps on purpose, written down so the next reader
meets them as decisions rather than as surprises (ticket 0737, 2026-09-08):

* **The file-type tripwire fires on assets too.**
  ``test_no_plugin_file_type_escapes_the_scan`` reddens on any suffix under
  ``plugins/`` that neither ``SOURCE_SUFFIXES`` nor ``ASSET_SUFFIXES`` names — an
  icon or a font as readily as an ``.xhtml`` dialog that really could carry a
  literal. Two reviewers raised the trade independently and it is kept: no rule
  separates the two cases, so the classification is a person's to make once, and
  a line added to a list is cheaper than a scannable format arriving unnoticed.
  A PR that only adds an asset pays one line for that.
* **Duplicate ``resource`` host declarations still resolve last-wins**, silently
  — see ``resource_roots``, which states the limit. Left as it is pending the
  author's ruling on whether the derivation engine survives at all; a table
  would delete the code the fix would live in.

The install is found at ``$ZOTERO_INSTALL_DIR`` when set, else at the first of
``CANDIDATE_INSTALLS`` that carries both jars. With none, the archive-reading
tests SKIP with a stated reason and warn, rather than passing: a guard that goes
green on a machine without the application is the failure this ticket is about,
one level up. Failure messages carry the install's version, read off
``app/application.ini``, so a verdict from one machine is attributable on
another.
"""
import itertools
import os
import re
import warnings
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"

#: Files that can carry a `resource://` literal. The scan covers the whole
#: plugin tree rather than `bootstrap.js` alone: a hand-listed scope guards a
#: file leaving it, never a literal arriving in a sibling — moving the
#: `win.require` call into `scheduler.js` would otherwise retire the guard
#: silently. `test_no_plugin_file_type_escapes_the_scan` guards the other axis.
SOURCE_SUFFIXES = (".js", ".mjs", ".json")

#: Formats that cannot carry a readable `resource://` literal, exempted by name
#: rather than by silence. The scan cannot tell an icon from an `.xhtml` dialog,
#: so a file type arriving under `plugins/` has to be classified by a person;
#: this list is where that decision is recorded.
ASSET_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2")

#: Whole-line comments, dropped before the scan. The quote anchor below rules
#: out unquoted prose; this rules out the quoted kind, which `bootstrap.js`
#: writes when it names the historical spec inside its own narration. A URL
#: quoted in a comment *trailing* a line of code still reads as a call site —
#: the residue is a false red, argued at length in the module docstring.
#:
#: This is a line-shape test, not a parse, and that is the whole of its safety:
#: it can only ever drop a line, never open a state that swallows the lines
#: below it. But dropping a line is still deleting text, so each alternative has
#: to be a shape whose ENTIRE line is comment. Round 4 of the review on PR #461
#: found that `^\s*(//|\*|/\*)` was not:
#:
#: * `\*` also matched `*/`, so an ordinary block-comment close with code
#:   trailing it — `*/ win.require('resource://…')` — was dropped whole, and the
#:   call site went unchecked with nothing said.
#: * `/\*` matched an opener whose comment CLOSES on the same line, so
#:   `/* aside */ win.require('resource://…')` went the same way. The lookahead
#:   drops the opener only when no `*/` follows it on the line, which is the case
#:   where the rest of the line really is comment.
#:
#: Both were silent passes, present since the guard's first commit and caught by
#: no fixture. `test_a_block_comment_that_closes_beside_code_is_not_dropped`
#: pins them.
#:
#: `\*(?!/)` is still wider than "comment", and round 5 said where: a line may
#: legitimately begin with `*` and be code — a generator method (`*entries()`),
#: an exponent continued onto the next line (`** 2`), a multiplication (`* h`).
#: All are dropped. That is a silent pass, and it is ACCEPTED rather than fixed,
#: for the reason the module docstring gives at length: separating those from a
#: JSDoc continuation means deciding whether a line is code, which is the parser
#: problem this file stopped trying to solve after three rounds of heuristics
#: each shipped a worse defect than the gap. A fourth narrowing here would be the
#: same mistake at line granularity.
#:
#: So the residues are listed instead, each a silent pass, none able to spread
#: past its own line:
#:
#: * a line beginning `*` that is code, not a JSDoc continuation;
#: * inside a multi-line template literal, a line beginning `//` or `*`, where
#:   the text is data rather than comment.
#:
#: `test_a_block_comment_that_closes_beside_code_is_not_dropped` pins both as
#: losses, so a future fix cannot land while this list still claims them. The
#: census over `plugins/` is zero lines matching `^\s*\*` at all, which is why
#: the exposure today is nil and the entry is a warning rather than a bug report.
LINE_COMMENT = re.compile(r"^\s*(?://|\*(?!/)|/\*(?!.*\*/))")

#: Anchored on the opening quote, so the match is a string literal rather than
#: prose: `bootstrap.js` still discusses the Fluent episode in several comments,
#: and a scan that read those would report a path no code ever asks for. The
#: right-hand end stops at a quote, whitespace, or a closing bracket, so it reads
#: the URL out of `require('resource://…')` and out of a template string alike.
#: Group 1 is the whole URL, group 2 the host, group 3 the path.
RESOURCE_URL = re.compile(r"""['"`](resource://([A-Za-z0-9._-]+)/([^'"`\s)]*))""")

#: The same shape without the quote anchor, for matching a bare URL handed in as
#: a string rather than found in source.
BARE_RESOURCE_URL = re.compile(r"""resource://([A-Za-z0-9._-]+)/([^'"`\s)]*)""")

#: The historical defect, kept verbatim because an invented absent path would
#: only prove the checker can say no to something nobody ever wrote. This exact
#: string cost an evening and forty green tests.
HISTORICAL_ABSENT = "resource://gre/modules/Fluent.sys.mjs"

#: `resource://gre/` is Gecko's built-in alias for the runtime root, declared in
#: no `chrome.manifest`; the GRE `omni.ja` *is* that root. Every other alias is
#: derived from the archives.
GRE_HOST = "gre"

ZOTERO_INSTALL_ENV = "ZOTERO_INSTALL_DIR"

#: Ordered; the first that carries both jars wins. `$ZOTERO_INSTALL_DIR`
#: overrides the list entirely, which is how a machine with Zotero somewhere
#: else runs this suite instead of skipping it.
CANDIDATE_INSTALLS = (
    Path("/opt/zotero7"),
    Path("/opt/zotero"),
    Path("/usr/lib/zotero"),
    Path("/usr/lib/zotero7"),
    Path.home() / "Zotero_linux-x86_64",
)


def jars(install: Path) -> dict[str, Path]:
    """The two archives an install answers from, by role."""
    return {"gre": install / "omni.ja", "app": install / "app" / "omni.ja"}


def is_install(path: Path) -> bool:
    """A directory carrying both `omni.ja` archives."""
    return all(jar.is_file() for jar in jars(path).values())


def zotero_install() -> Path | None:
    """The installed Zotero to read, or None when the host has none."""
    override = os.environ.get(ZOTERO_INSTALL_ENV)
    if override:
        candidate = Path(override)
        return candidate if is_install(candidate) else None
    return next((path for path in CANDIDATE_INSTALLS if is_install(path)), None)


def installed_version(install: Path) -> str:
    """The install's advertised version, so a verdict travels between machines.

    A pass here is a statement about one build of one application. Without the
    version in the message, a failure reported from another machine cannot be
    told from a failure on this one, and the first question after any red run —
    which Zotero was it — has no answer in the artifact.

    Every way of failing to read it degrades to a stated `version unknown`,
    including an unreadable one. This runs while the caller is composing a
    failure message about a real defect, so a raise here would replace the
    assertion that names it with a traceback about a `.ini` file.

    The `is_file()` probe is inside the guarded block, not in front of it.
    `Path.is_file` swallows only the errors `pathlib._IGNORED_ERRNOS` lists —
    ENOENT, ENOTDIR, EBADF, ELOOP — and EACCES is not among them, so an
    unreadable `app/` directory raises there rather than answering False. Put in
    front, the guard covered every way of failing to read the file except the
    one it was added for (round 1 of the review on PR #461).
    """
    ini = install / "app" / "application.ini"
    try:
        if not ini.is_file():
            return "version unknown (no app/application.ini)"
        text = ini.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"version unknown (app/application.ini unreadable: {error})"
    for line in text.splitlines():
        if line.startswith("Version="):
            return line.split("=", 1)[1].strip()
    return "version unknown (application.ini names none)"


def describe(install: Path) -> str:
    """The install as it should appear in any message this suite prints."""
    return f"{install} (Zotero {installed_version(install)})"


def skip_reason() -> str:
    """Why the guard could not look, naming only the places it actually tried.

    Kept apart from `require_install` so it can be asserted on directly: a test
    that provoked the skip in order to read its wording would itself be reported
    as skipped, since pytest's `Skipped` is a `BaseException`.
    """
    override = os.environ.get(ZOTERO_INSTALL_ENV)
    looked = (
        f"${ZOTERO_INSTALL_ENV}={override} carries no omni.ja and app/omni.ja, so "
        f"nothing else was looked at"
        if override
        else f'looked at {", ".join(str(path) for path in CANDIDATE_INSTALLS)}'
    )
    return (
        f"no installed Zotero found — {looked}. The host APIs the sitter names went "
        f"UNCHECKED; this is not a pass. Point ${ZOTERO_INSTALL_ENV} at a directory "
        f"holding omni.ja and app/omni.ja."
    )


def require_install() -> Path:
    """The install, or a loud skip naming why the guard could not look.

    The warning is the loud half: `make check` runs pytest under `-q`, where a
    skip is one grey `s` and a warning still prints its own summary section. A
    silent skip here reads exactly like a pass.
    """
    install = zotero_install()
    if install is None:
        reason = skip_reason()
        warnings.warn(reason, stacklevel=2)
        pytest.skip(reason)
    return install


def resource_roots(install: Path) -> dict[str, tuple[str, str]]:
    """Every `resource://` host the install declares, as (jar role, prefix).

    Read out of the archives' own `chrome.manifest` files. A manifest's targets
    are relative to the directory holding it, which is why the prefix is joined
    onto the manifest's parent rather than onto the jar root.

    An alias whose target is itself a `resource://` URL is chased to a fixpoint
    rather than in one pass: the manifests are read in archive order, so a
    single pass would resolve or drop such a line depending on where it happens
    to sit relative to the alias it names. Nothing shipped today needs more than
    one round, which is exactly why the ordering dependency would go unnoticed.

    One limit, recorded rather than engineered around: a host declared twice
    with different targets resolves last-wins, silently. Zotero 10.0.1 declares
    none twice, and the two hosts the sitter actually uses are each declared
    once, so reporting the ambiguity would add engine for a case no install
    presents. A URL that resolved through the losing declaration would fail as
    "absent from the archive", which points at the right file and the wrong
    reason.
    """
    roots: dict[str, tuple[str, str]] = {GRE_HOST: ("gre", "")}
    aliases: dict[str, str] = {}
    for role, jar in jars(install).items():
        with zipfile.ZipFile(jar) as archive:
            for name in archive.namelist():
                if Path(name).name != "chrome.manifest":
                    continue
                base = name[: -len("chrome.manifest")]
                text = archive.read(name).decode("utf-8", "replace")
                for line in text.splitlines():
                    fields = line.split()
                    if len(fields) < 3 or fields[0] != "resource":
                        continue
                    host, target = fields[1], fields[2]
                    if target.startswith("resource://"):
                        aliases[host] = target
                    else:
                        roots[host] = (role, base + target.rstrip("/") + "/")
    while aliases:
        resolved_now = {
            host: resolve_in(target, roots)
            for host, target in aliases.items()
            if resolve_in(target, roots) is not None
        }
        if not resolved_now:
            break
        for host, resolved in resolved_now.items():
            role, entry = resolved
            roots[host] = (role, entry.rstrip("/") + "/")
            del aliases[host]
    return roots


def resolve_in(url: str, roots: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """A `resource://` URL as (jar role, archive entry), or None if unmapped."""
    match = BARE_RESOURCE_URL.fullmatch(url)
    if match is None:
        return None
    root = roots.get(match.group(1))
    if root is None:
        return None
    role, prefix = root
    return role, prefix + match.group(2)


def named_resource_urls(tree: Path) -> dict[str, list[str]]:
    """Every `resource://` string literal in the tree, mapped to where it is written.

    A file that cannot be read is warned about and skipped rather than allowed
    to abort the walk: one unreadable sibling would otherwise take down the
    scan of every file beside it. The warning is what keeps that honest — a
    quiet skip would turn a file the guard could not read into a file the guard
    approved, the failure `require_install` warns about one level up.

    Nothing here rewrites the source before scanning it, and that is a decision
    rather than an omission: an extraction that deletes text can delete a call
    site, and a deleted call site is a green run over an unchecked URL. Only
    whole lines are dropped, by `LINE_COMMENT`, which is a per-line shape test
    that cannot open a state spanning the lines below it. The residue is a URL
    quoted in a comment trailing code, reported as a call site — a false red,
    argued in the module docstring and pinned by
    `test_a_url_quoted_in_a_trailing_comment_is_a_known_false_red`.

    Lines are cut on `\\n` alone, not by `str.splitlines`. Python's idea of a
    line boundary is wider than JavaScript's: it also breaks on `\\v`, `\\f`,
    `\\x1c`-`\\x1e`, `\\x85`, `\\u2028` and `\\u2029`. The last two are legal raw
    inside a JavaScript string literal and inside JSON, so one of them earlier in
    a line made the tail a "line" of its own — and where that tail began `//`,
    `LINE_COMMENT` ate the call site after it, with no warning. Six separators
    reproduced it (round 5 of the review on PR #461);
    `test_a_javascript_line_is_cut_only_on_a_newline` pins them. Trailing `\\r`
    is stripped so a CRLF file behaves as `splitlines` did.
    """
    sites: dict[str, list[str]] = {}
    for path in sorted(tree.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            warnings.warn(
                f"{path} could not be read ({error}); any resource:// literal it "
                f"names went UNCHECKED, and this is not a pass",
                stacklevel=2,
            )
            continue
        for number, raw in enumerate(text.split("\n"), 1):
            line = raw.rstrip("\r")
            if LINE_COMMENT.match(line):
                continue
            for match in RESOURCE_URL.finditer(line):
                site = f"{path.relative_to(tree).as_posix()}:{number}"
                sites.setdefault(match.group(1), []).append(site)
    return sites


def unanswered(urls: dict[str, list[str]], install: Path) -> list[str]:
    """One line per URL the install does not answer, empty when all resolve.

    Two distinct failures, both reported rather than skipped over: a host the
    install declares nowhere, and a host that resolves to an archive entry that
    is not there.
    """
    roots = resource_roots(install)
    contents = {}
    for role, jar in jars(install).items():
        with zipfile.ZipFile(jar) as archive:
            contents[role] = set(archive.namelist())
    problems = []
    for url, sites in sorted(urls.items()):
        where = ", ".join(sites)
        resolved = resolve_in(url, roots)
        if resolved is None:
            problems.append(
                f"{url} ({where}): no resource host by that name in {describe(install)}"
            )
            continue
        role, entry = resolved
        if entry not in contents[role]:
            problems.append(
                f"{url} ({where}): resolves to {entry!r}, absent from "
                f"{jars(install)[role]} — {describe(install)}"
            )
    return problems


def test_the_plugin_tree_names_resource_urls():
    """The scan finds something to check.

    Without this the suite below is vacuous: an empty URL set makes every
    archive assertion trivially true, and a regex that stopped matching would
    read as a clean bill of health. That is the same all-clear-indistinguishable
    -from-could-not-look shape the whole ticket is about.
    """
    urls = named_resource_urls(PLUGINS)
    assert urls, f"no resource:// literal found under {PLUGINS} — the extraction is broken"


def test_prose_about_an_absent_module_is_not_read_as_a_call_site(tmp_path):
    """A URL discussed in a comment is not a URL the plugin asks for.

    `bootstrap.js` still narrates the Fluent episode. Two filters keep that
    narration out of the checked set, and the fixture writes it four ways to
    exercise both: the quote anchor drops unquoted prose, and the whole-line
    comment filter drops the quoted kind, in `//` and block-comment form alike.
    Asserting against a fixture rather than against today's comment wording is
    the point — the wording will change, and a test that passed by accident of
    it would go on passing after the property was gone.
    """
    source = tmp_path / "bootstrap.js"
    source.write_text(
        f"// The import of {HISTORICAL_ABSENT} threw on every startup.\n"
        f"// It was written '{HISTORICAL_ABSENT}', quoted, right here.\n"
        f" * and again as '{HISTORICAL_ABSENT}' inside a block comment.\n"
        f"ChromeUtils.importESModule('{HISTORICAL_ABSENT}');\n",
        encoding="utf-8",
    )

    sites = named_resource_urls(tmp_path)

    assert sites == {HISTORICAL_ABSENT: ["bootstrap.js:4"]}, sites
    assert HISTORICAL_ABSENT not in named_resource_urls(PLUGINS), (
        "the historical defect is back in the plugin source"
    )


def test_a_url_quoted_in_a_trailing_comment_is_a_known_false_red(tmp_path):
    """The accepted gap of ticket 0737 item 1, pinned so it stays demonstrated.

    `LINE_COMMENT` drops narration owning a whole line. It cannot see a comment
    opened *after* a statement, and the quote anchor then reads the URL inside it
    as a literal. So this asserts the limitation rather than a fix: the URL IS
    reported, and the guard would go on to demand it of the archives.

    That direction is the whole reason the gap is acceptable. A reported comment
    costs a red run and a reworded comment; a comment mistaken for code and
    blanked would cost a call site and a green run, which is the failure ticket
    0737 forbids. Three rounds of review on PR #461 each found a heuristic that
    made exactly that trade (the module docstring names them) and the guard
    now blanks nothing at all.

    The second line is the near-miss, and it is what stops this being a test of
    the obvious: the same trailing comment on a line whose code divides. That is
    where all three heuristics failed — the `/` gave them a regex to misread and
    the comment gave them something to blank — so here the outcome must be the
    false red on the comment AND the real call site still reported beside it.
    Both halves, or the test would pass against a stripper that swallowed the
    line whole.

    The shipped tree's own state is asserted in
    `test_prose_about_an_absent_module_is_not_read_as_a_call_site`, not
    duplicated here.
    """
    source = tmp_path / "bootstrap.js"
    source.write_text(
        "const timers = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');"
        f" // we used to require '{HISTORICAL_ABSENT}' here\n"
        "const pct = coverage.current / coverage.total;"
        " win.require('resource://zotero/document-worker/sdt.js');"
        f" // and once '{HISTORICAL_ABSENT}'\n",
        encoding="utf-8",
    )

    sites = named_resource_urls(tmp_path)

    assert HISTORICAL_ABSENT in sites, (
        "the accepted false red is gone -- if that is deliberate, read the module "
        f"docstring before believing it, and check what was blanked to get it: {sites}"
    )
    assert sites[HISTORICAL_ABSENT] == ["bootstrap.js:1", "bootstrap.js:2"], sites
    assert sites["resource://gre/modules/Timer.sys.mjs"] == ["bootstrap.js:1"], sites
    assert sites["resource://zotero/document-worker/sdt.js"] == ["bootstrap.js:2"], (
        f"the real call site beside a division and a comment must survive: {sites}"
    )


def test_a_block_comment_that_closes_beside_code_is_not_dropped(tmp_path):
    """`LINE_COMMENT` may only drop a line that is comment all the way across.

    Round 4 of the review on PR #461 found two shapes where it did not, both
    silent passes and both present since the guard's first commit:

    * `*/ win.require('resource://…')` — the old `\\*` alternative matched the
      block-comment CLOSE, and the call site trailing it went with the line.
    * `/* aside */ win.require('resource://…')` — the `/\\*` alternative matched
      an opener whose comment ends on the same line.

    Both reddened here before the pattern was narrowed to `\\*(?!/)` and
    `/\\*(?!.*\\*/)`. This is the one test in the file whose subject is the
    *dropping* rather than the extraction, and it is deliberately the
    silent-pass direction: the first two arms assert the URL is FOUND.

    Neither shape appears under `plugins/` today — the census is zero, and an
    earlier draft of this docstring claimed otherwise ("ordinary style in
    `bootstrap.js`"), which a reviewer disproved by grepping every block-comment
    span in the tree. The fix is precautionary, and that is reason enough: it
    costs two lookaheads and removes a way for the guard to go green over an
    unchecked URL. What it is not is a response to a live defect.

    The last two arms are residues, pinned as known LOSSES rather than fixed —
    they assert the URL is absent. A line beginning `*` that is code rather than
    a JSDoc continuation, and any line inside a multi-line template literal, are
    both dropped. Separating either from a real comment means deciding whether a
    line is code, which is the parser problem this file gave up after three
    rounds of heuristics; `LINE_COMMENT`'s own comment argues it. Pinning the
    losses is what keeps the blind-spot list honest: fix one and this test
    reddens, so the list cannot quietly go stale.
    """
    closes_beside_code = tmp_path / "closes"
    closes_beside_code.mkdir()
    (closes_beside_code / "a.js").write_text(
        "/* the episode, at length:\n"
        f"   the spec was {HISTORICAL_ABSENT}, unquoted\n"
        "*/ win.require('resource://zotero/document-worker/sdt.js');\n",
        encoding="utf-8",
    )
    (closes_beside_code / "b.js").write_text(
        "/* an aside */ win.require('resource://zotero/document-worker/metadata.json');\n",
        encoding="utf-8",
    )

    sites = named_resource_urls(closes_beside_code)

    assert sites == {
        "resource://zotero/document-worker/sdt.js": ["a.js:3"],
        "resource://zotero/document-worker/metadata.json": ["b.js:1"],
    }, f"a whole line was dropped for a block comment that ended on it: {sites}"

    narration = tmp_path / "narration"
    narration.mkdir()
    (narration / "c.js").write_text(
        "/* the episode, at length:\n"
        f" * the spec was '{HISTORICAL_ABSENT}'\n"
        " */\n"
        "win.require('resource://zotero/document-worker/sdt.js');\n",
        encoding="utf-8",
    )

    still_dropped = named_resource_urls(narration)

    assert still_dropped == {"resource://zotero/document-worker/sdt.js": ["c.js:4"]}, (
        f"narration owning its whole line must still be dropped: {still_dropped}"
    )

    hole = tmp_path / "hole"
    hole.mkdir()
    (hole / "d.js").write_text(
        "const doc = `\n// ${'resource://zotero/document-worker/hole.js'}\n`;\n",
        encoding="utf-8",
    )

    assert named_resource_urls(hole) == {}, (
        "the template-literal residue is fixed, not merely reported — if that is "
        "deliberate, the LINE_COMMENT comment naming it as a known loss is now stale"
    )

    star_code = tmp_path / "star"
    star_code.mkdir()
    (star_code / "e.js").write_text(
        "class Sitter {\n  *steps() { win.require('resource://zotero/a.js'); }\n}\n",
        encoding="utf-8",
    )
    (star_code / "f.js").write_text(
        "const n = base\n  ** 2; win.require('resource://zotero/b.js');\n",
        encoding="utf-8",
    )

    assert named_resource_urls(star_code) == {}, (
        "a line beginning `*` that is code is no longer dropped — if that is "
        "deliberate, the LINE_COMMENT comment listing it as a known loss, and the "
        "module docstring's blind-spot entry, are now stale and must be updated"
    )


#: Characters `str.splitlines` treats as line boundaries and JavaScript does not.
#: U+2028 and U+2029 are the ones that matter: since ES2019 both are legal raw
#: inside a string literal, and both are legal inside JSON, so a file can carry
#: one without being malformed. The rest are here because the fix is the same for
#: all of them and a fixture that covered only the reachable two would invite the
#: next reader to re-widen the split.
PYTHON_ONLY_LINE_BREAKS = ("\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", " ", " ")


def test_a_javascript_line_is_cut_only_on_a_newline(tmp_path):
    """Python breaks lines where JavaScript does not, and the tail can be eaten.

    `str.splitlines` splits on eight characters beyond `\\n`. Put one earlier in
    a line and the remainder becomes a line of its own; where that remainder
    begins `//`, `LINE_COMMENT` drops it and the call site after it goes with it
    — a silent pass, found in round 5 of the review on PR #461 and reproduced on
    all eight separators.

    The fixture writes the separator inside a string literal, which is where a
    real one would be: U+2028 and U+2029 have been legal raw in a JavaScript
    string since ES2019, and are legal in JSON, so this needs no malformed file.

    Cutting on `\\n` alone fixes it, and unlike everything else in this file the
    fix required no judgement about what the source means — Python's rule was
    simply not JavaScript's. The `\\r` strip keeps a CRLF file reading as it did.
    """
    for number, separator in enumerate(PYTHON_ONLY_LINE_BREAKS):
        url = f"resource://zotero/document-worker/sep-{number}.js"
        source = tmp_path / f"case-{number}.js"
        source.write_text(
            f"const s = 'a{separator}// b'; win.require('{url}');\n", encoding="utf-8"
        )

        sites = named_resource_urls(source.parent)

        assert url in sites, (
            f"{separator!r} inside a string literal cut the line, and the tail "
            f"beginning `//` took the call site with it: {sites}"
        )
        assert sites[url] == [f"{source.name}:1"], (
            f"{separator!r} shifted the reported line number: {sites}"
        )
        source.unlink()

    crlf = tmp_path / "crlf.js"
    crlf.write_text(
        "win.require('resource://zotero/document-worker/crlf.js');\r\n"
        "// a comment\r\n",
        encoding="utf-8",
    )

    assert named_resource_urls(crlf.parent) == {
        "resource://zotero/document-worker/crlf.js": ["crlf.js:1"]
    }, "a CRLF file must read as it did under splitlines"


#: A `/` beside a call site, once per way a scanner has been caught misreading
#: one. Every line here must still yield its URL.
#:
#: The extraction blanks nothing, so no `/` can hide a call site and these pass
#: by construction. That is the point: this fixture is a tripwire against a
#: FOURTH attempt at comment stripping, not a test of one. Three are recorded on
#: PR #461, and each was proven to blank live source somewhere:
#:
#: * Round 1 classified `/` from the preceding token. `)`, `]`, an identifier and
#:   a number precede a regex and a division alike, so a regex read as code let
#:   its `/*` open a block comment over the call site beside it — the first four
#:   entries.
#: * Round 2 read every ambiguous `/` as a regex. A division whose search for a
#:   closing `/` ran into a later string desynchronised the quote state, and the
#:   `//` of a real URL then read as a comment — the fifth entry. Both halves of
#:   that shape are live in the plugin tree: `bootstrap.js` divides
#:   (`coverage.current / coverage.total`) and writes `resource://` URLs. The
#:   entry itself is a fixture, not a quotation. The sixth is a regex closing
#:   immediately before another `/`, presenting a `//` that is not a comment.
#: * Round 3 intersected the two readings on the argument that they fail on
#:   disjoint inputs. A fuzzer disproved it on its second trial: combining
#:   entries onto one line desynchronises them independently and they agree on
#:   the same wrong answer.
#:
#: A stripper reintroduced without solving all three reddens here.
REGEX_HAZARDS = (
    "if (matches(p)) /[/*]/.test(p);",
    "const first = names[0] /[/*]/.exec(p);",
    "const flag = config.enabled /['\"]/.test(p);",
    "const scaled = 42 /['\"]/.source.length;",
    "const pct = done / total; const sep = 'a/b';",
    "const n = /ab//1;",
)


def test_no_ambiguous_slash_can_hide_the_call_site_beside_it(tmp_path):
    """The invariant of ticket 0737, in the one direction that fails silently.

    Reading a comment as code costs a false red, and this file accepts one.
    Reading *code* as a comment deletes a call site and the guard goes green.

    The `/` and the call must share a LINE for this to discriminate, and the
    hazards run in three arrangements because each catches a different round:

    * **alone**, one per file — round 1's four tokens;
    * **stacked**, one per line in one file — a mis-opened block comment nothing
      closes, which used to reach across lines to delete a call site four rows
      down;
    * **paired**, every ordered pair on ONE line — round 3. Round 4 of the review
      found the first two arrangements do not discriminate against round 3's
      intersection at all: it passes both cleanly, so a PR reintroducing it
      verbatim would have got a green light from the very test that says not to.
      Pairing is what breaks it, on 5 of the 30 ordered pairs, because the two
      readings desynchronise independently and converge on the same wrong answer.
      Measured against `61ff1831` before this arm was written.
    """
    urls = [f"resource://zotero/document-worker/case-{n}.js" for n in range(len(REGEX_HAZARDS))]
    lines = [
        f"{hazard} win.require('{url}');\n"
        for hazard, url in zip(REGEX_HAZARDS, urls, strict=True)
    ]

    alone = tmp_path / "alone"
    alone.mkdir()
    for number, line in enumerate(lines):
        (alone / f"case-{number}.js").write_text(line, encoding="utf-8")
    solo = named_resource_urls(alone)
    assert solo == {url: [f"case-{n}.js:1"] for n, url in enumerate(urls)}, (
        "a call site was lost to the `/` on its own line: "
        + ", ".join(f"{REGEX_HAZARDS[urls.index(url)]!r}" for url in sorted(set(urls) - set(solo)))
    )

    together = tmp_path / "together"
    together.mkdir()
    (together / "scheduler.js").write_text("".join(lines), encoding="utf-8")
    sites = named_resource_urls(together)

    assert sites == {url: [f"scheduler.js:{n}"] for n, url in enumerate(urls, 1)}, (
        "a hazard reached across lines to delete another's call site: "
        + ", ".join(f"{REGEX_HAZARDS[urls.index(url)]!r}" for url in sorted(set(urls) - set(sites)))
    )

    paired = tmp_path / "paired"
    paired.mkdir()
    expected = {}
    for left, right in itertools.permutations(range(len(REGEX_HAZARDS)), 2):
        url = f"resource://zotero/document-worker/pair-{left}-{right}.js"
        name = f"pair-{left}-{right}.js"
        (paired / name).write_text(
            f"{REGEX_HAZARDS[left]} {REGEX_HAZARDS[right]} win.require('{url}');\n",
            encoding="utf-8",
        )
        expected[url] = [f"{name}:1"]
    pairs = named_resource_urls(paired)

    assert pairs == expected, (
        "two hazards on one line deleted the call site after them — this is the "
        "arrangement that discriminates against round 3, so a failure here most "
        "likely means a stripper came back: "
        + ", ".join(sorted(set(expected) - set(pairs)))
    )


def test_an_unreadable_application_ini_degrades_rather_than_raising(tmp_path):
    """The version lookup runs while composing a failure message, so it may not throw.

    Missing, empty, binary and a directory in its place all already fall back to
    `version unknown (...)`. An unreadable one raised `PermissionError` instead,
    on the one path where the caller is already reporting a real defect: the
    traceback would replace the assertion naming it.
    """
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file, so the permission error never fires")
    install = tmp_path / "zotero"
    (install / "app").mkdir(parents=True)
    ini = install / "app" / "application.ini"
    ini.write_text("Version=10.0.1\n", encoding="utf-8")
    ini.chmod(0o000)

    version = installed_version(install)

    assert "version unknown" in version, version
    assert "10.0.1" not in version, version
    assert str(install) in describe(install)


def test_an_unreadable_app_directory_degrades_rather_than_raising(tmp_path):
    """The same contract one directory up, where the first fix did not reach.

    `Path.is_file` is not the total predicate it reads as: it swallows only the
    errnos `pathlib._IGNORED_ERRNOS` lists (ENOENT, ENOTDIR, EBADF, ELOOP), and
    EACCES is not among them, so an unreadable `app/` raises out of it. The
    guard was placed after that probe and therefore covered every way of failing
    to read the file except the one it was added for — found in round 1 of the
    review on PR #461, reproduced here.
    """
    if os.geteuid() == 0:
        pytest.skip("root traverses a mode-000 directory, so the error never fires")
    install = tmp_path / "zotero"
    app = install / "app"
    app.mkdir(parents=True)
    (app / "application.ini").write_text("Version=10.0.1\n", encoding="utf-8")
    app.chmod(0o000)
    try:
        version = installed_version(install)
    finally:
        app.chmod(0o755)

    assert "version unknown" in version, version
    assert "10.0.1" not in version, version


def test_an_unreadable_plugin_file_is_reported_rather_than_aborting_the_scan(tmp_path):
    """One unreadable file must not take the whole scan down with it.

    The warning is what keeps the degradation honest: skipping quietly would
    turn a file the guard could not read into a file the guard approved, which
    is the failure `require_install` already warns about one level up.
    """
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file, so the permission error never fires")
    (tmp_path / "bootstrap.js").write_text(
        "win.require('resource://zotero/document-worker/sdt.js');\n", encoding="utf-8"
    )
    blocked = tmp_path / "scheduler.js"
    blocked.write_text(
        "win.require('resource://zotero/document-worker/other.js');\n", encoding="utf-8"
    )
    blocked.chmod(0o000)

    with pytest.warns(UserWarning, match="scheduler.js"):
        sites = named_resource_urls(tmp_path)

    assert sites == {"resource://zotero/document-worker/sdt.js": ["bootstrap.js:1"]}, sites


def test_no_plugin_file_type_escapes_the_scan():
    """`SOURCE_SUFFIXES` covers every file the plugin tree actually ships.

    The same hand-listed-scope shape as the directory comment above, one axis
    over: an `.xhtml` dialog or a `.ftl` bundle arriving under `plugins/` would
    carry `resource://` literals that this suite never reads, and nothing would
    say so.

    It fires on an icon as readily as on a new source format. That is the
    design, not a rough edge, and the trade it makes is argued once — in the
    module docstring, under the over-reaches this file keeps on purpose.
    Re-examined and kept there on 2026-09-08 (ticket 0737 item 5).
    """
    shipped = {path.suffix for path in PLUGINS.rglob("*") if path.is_file()}
    unscanned = shipped - set(SOURCE_SUFFIXES) - set(ASSET_SUFFIXES)
    assert not unscanned, (
        f"file types under {PLUGINS} that the resource:// scan never reads: "
        f"{sorted(unscanned)} — add each to SOURCE_SUFFIXES, or to ASSET_SUFFIXES "
        f"if it cannot carry a readable resource:// literal"
    )


def test_the_skip_reason_names_only_what_was_looked_at(monkeypatch):
    """The one guard whose contract is honesty about what it could not check.

    With `$ZOTERO_INSTALL_DIR` set, the candidate list is never consulted, so
    naming it would claim a search that did not happen — and on this host it
    would name `/opt/zotero7`, where a working install actually sits.
    """
    monkeypatch.setenv(ZOTERO_INSTALL_ENV, "/nonexistent")
    assert zotero_install() is None, "the override must not fall back to the candidates"

    message = skip_reason()

    assert "/nonexistent" in message
    assert "UNCHECKED" in message, "the reason must say the check did not happen"
    assert not any(str(path) in message for path in CANDIDATE_INSTALLS), message

    monkeypatch.delenv(ZOTERO_INSTALL_ENV)
    assert str(CANDIDATE_INSTALLS[0]) in skip_reason(), "unset, it does search the candidates"


@pytest.mark.slow
def test_every_named_resource_exists_in_the_installed_zotero():
    """The whole point: the real archives answer every path the plugin names."""
    install = require_install()
    problems = unanswered(named_resource_urls(PLUGINS), install)
    assert not problems, (
        f"host APIs the sitter names that {describe(install)} does not have:\n"
        + "\n".join(problems)
    )


@pytest.mark.slow
def test_guard_reddens_on_the_historical_absent_module(tmp_path):
    """The control, run in both directions through the whole pipeline.

    Not `unanswered([HISTORICAL_ABSENT])` on its own: that would exercise the
    resolver while leaving the extraction unproven. This writes the defect back
    into a plugin tree of its own, in the call shape it originally had, and
    checks that the guard finds it there and stays quiet about the real paths
    written beside it.

    The real paths come along as the negative half, so the comparison is against
    what the live tree already reports rather than against zero. Otherwise a
    genuine breakage of the shipped plugin would redden this control too, under
    a message about Fluent that names the wrong defect.
    """
    install = require_install()
    real = {
        url: sites
        for url, sites in named_resource_urls(PLUGINS).items()
        if url != HISTORICAL_ABSENT
    }
    assert real, "no real paths to serve as the negative half of the control"
    baseline = unanswered(real, install)
    source = tmp_path / "bootstrap.js"
    source.write_text(
        f"ChromeUtils.importESModule('{HISTORICAL_ABSENT}');\n"
        + "".join(f"win.require('{url}');\n" for url in sorted(real)),
        encoding="utf-8",
    )

    problems = unanswered(named_resource_urls(tmp_path), install)

    named = [problem for problem in problems if HISTORICAL_ABSENT in problem]
    assert len(named) == 1, f"expected the Fluent import to redden once, got: {problems}"
    assert "bootstrap.js:1" in named[0], "the guard names where the defect is written"
    assert len(problems) == len(baseline) + 1, (
        f"the real paths beside it must contribute nothing new; baseline {baseline}, "
        f"fixture {problems}"
    )


@pytest.mark.slow
def test_an_undeclared_host_is_reported_rather_than_ignored(tmp_path):
    """A URL whose host the install never declares fails loudly.

    The second way this guard could go quietly wrong: resolve nothing and call
    it clean. `resource://gre/` is the only alias written into this file, so a
    typo in a host name must not fall through as "nothing to check".
    """
    install = require_install()
    source = tmp_path / "bootstrap.js"
    source.write_text("win.require('resource://no-such-host/x.js');\n", encoding="utf-8")

    problems = unanswered(named_resource_urls(tmp_path), install)

    assert len(problems) == 1 and "no resource host" in problems[0], problems


@pytest.mark.slow
def test_the_zotero_host_is_derived_not_assumed():
    """The `zotero` alias comes out of the archive, not out of this file.

    Only `gre` is hard-coded. If a Zotero release stopped declaring `zotero` in
    its root `chrome.manifest`, the two document-worker paths would go
    unresolvable above — this asserts the derivation is what answers them, so
    that failure would read as "the alias moved" rather than as "the files
    vanished".
    """
    install = require_install()
    roots = resource_roots(install)
    assert "zotero" in roots, f"{describe(install)} declares no resource://zotero/ alias"
    assert roots["zotero"] == ("app", "resource/")
