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
* **Comments, only as far as a scanner can tell.** ``strip_comments`` reads
  JavaScript with a character scanner rather than a parser: it knows quotes,
  template literals, regular expressions and both comment forms, and it does
  not evaluate ``${}`` holes, so a comment written inside one survives and a URL
  inside one is reported. Every construct it misreads costs a false RED. The one
  direction that would cost a silent pass is blanking live code, and only
  comments are blanked — so a comment opener is believed only when TWO readings
  of the source agree it is one, one reading treating an ambiguous ``/`` as a
  regular expression and the other knowing no regex syntax at all. Where they
  disagree the text is left alone. ``REGEX_HAZARDS`` pins that against the six
  shapes two rounds of review found, three of which each single reading gets
  right and the other gets wrong.
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

#: Whole-line comments, stripped before the scan. `strip_comments` below already
#: removes every comment the language actually delimits; this catches the shape
#: it cannot — a bare continuation line (` * still about Fluent`) whose opening
#: `/*` is not in the text being scanned, which is how a fixture or an excerpt
#: writes one. Cheap, and it fails toward a false red.
LINE_COMMENT = re.compile(r"^\s*(//|\*|/\*)")

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


def end_of_quoted(source: str, start: int, quote: str) -> int:
    """One past a `'` or `"` literal — which JavaScript does not let cross a line.

    Stopping at the newline is a safety property rather than a nicety. An
    apostrophe the scanner met in prose it misread as code would otherwise open
    a literal that ran to the next apostrophe anywhere in the file, blanking
    real call sites in between. Bounded to the line, that mistake costs at most
    the rest of one line, and costs it in the direction of a false red.
    """
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1
        if char == "\n":
            return index
        index += 1
    return len(source)


def end_of_template(source: str, start: int) -> int:
    """One past a backtick literal, which may span lines.

    `${}` holes are read as part of the literal rather than as the code they
    are. A comment inside a hole therefore survives stripping, and a URL inside
    one is reported — both false reds, and the module docstring says so.
    """
    index = start + 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
            continue
        if source[index] == "`":
            return index + 1
        index += 1
    return len(source)


def regex_span(source: str, start: int) -> int | None:
    """One past a regular-expression literal at `start`, or None for a division.

    JavaScript's `/` is ambiguous and only a parser settles it. This does not
    parse, so it asks the one question whose two answers have different costs:
    *could* a literal close here, on this line? Read as a regex, a division is
    merely skipped over, and the worst that follows is a comment left standing —
    a false red. Read as a division, a regex is walked as code, and a `/*` in
    its body then opens a block comment that blanks everything to the next `*/`
    or to the end of the file. That is a call site deleted and a silent pass, so
    the ambiguity resolves toward the regex every time.

    An earlier version decided this from the preceding token instead, against a
    list of characters and keywords a regex may follow. The list could not be
    complete — `)`, `]`, an identifier and a number all precede a regex and a
    division alike — and each omission was a silent pass, reproduced on all of
    them (round 1 of the review on PR #461).

    This reading is deliberately credulous, and on its own it is wrong often: it
    calls `done / total; const sep = 'a/b'` a regular expression, ending inside
    a string that has nothing to do with it. That is why nothing acts on it
    alone. `comment_mask` runs it against a second reading that knows no regex
    syntax at all, and `strip_comments` blanks only where the two agree — so a
    span this misreads is a span that does not get blanked.
    """
    index = start + 1
    in_class = False
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == "\n":
            return None
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            return index + 1
        index += 1
    return None


def comment_mask(source: str, *, regex_aware: bool) -> list[bool]:
    """Which characters one reading of `source` calls comment.

    Two readings exist because JavaScript's `/` cannot be classified without a
    parser, and the two plausible guesses fail on disjoint inputs.

    `regex_aware=True` believes `regex_span`: any `/` that could close on its
    line opens a literal, which is then opaque. It is right about `/[/*]/` and
    wrong about `done / total; const sep = 'a/b'`, where it runs into a string.

    `regex_aware=False` knows no regex syntax at all. It is right about that
    division and wrong about `/[/*]/`, whose `/*` it reads as a block comment.

    Neither is trustworthy. `strip_comments` intersects them.
    """
    mask = [False] * len(source)
    length = len(source)
    index = 0
    while index < length:
        char = source[index]
        if char in "'\"":
            index = end_of_quoted(source, index, char)
            continue
        if char == "`":
            index = end_of_template(source, index)
            continue
        if source.startswith("//", index):
            while index < length and source[index] != "\n":
                mask[index] = True
                index += 1
            continue
        if source.startswith("/*", index):
            close = source.find("*/", index + 2)
            if close == -1:
                # An opener with no closer is not a comment: real source does
                # not end inside one, so this is a scanner that has lost its
                # place. Masking to end of file would let a single misread
                # character delete every call site below it -- and it did, until
                # the six-shape fixture put two hazards in one file.
                index += 1
                continue
            for position in range(index, close + 2):
                if source[position] != "\n":
                    mask[position] = True
            index = close + 2
            continue
        if regex_aware and char == "/":
            span = regex_span(source, index)
            if span is not None:
                index = span
                continue
        index += 1
    return mask


def strip_comments(source: str) -> str:
    """`source` with every comment blanked, character for character.

    Blanked rather than removed so line numbers and columns survive: the scan
    reports where a URL is written, and a stripper that shifted the text would
    make every site it names wrong.

    Blanking is the only operation here that can delete a call site, and only
    comments are blanked, so the whole design question is when to believe a
    comment opener. Two rounds of review on PR #461 answered it by elimination.
    A single scanner cannot: classifying `/` needs a parser, both available
    guesses are wrong on real code from `bootstrap.js`, and whichever one is
    chosen, the inputs it misreads are the ones where it blanks live code — a
    silent pass, the failure ticket 0737 forbids. Round 1 shipped the
    preceding-token guess and round 2 the credulous-regex guess; each closed the
    other's cases and opened its own.

    So neither is trusted. `comment_mask` produces both readings and this blanks
    only where they AGREE. Disagreement means at least one scanner is confused,
    and the response to confusion is to leave the text alone — which costs an
    unstripped comment reported as a call site, exactly the false red this
    function was written to reduce, never a call site deleted. The two readings
    fail on disjoint inputs by construction, since they differ only in whether a
    `/` is opaque, and that is what makes the intersection safe rather than
    merely quieter.

    `'`/`"` literals additionally stop at the newline, so an apostrophe met in
    prose that one reading misread costs at most the rest of one line. `${}`
    holes in a template literal are not evaluated: a comment inside one survives
    and a URL inside one is reported, both false reds.

    Checked two ways, and neither alone is enough.
    `test_a_regex_literal_does_not_swallow_the_call_site_beside_it` puts every
    hazardous construct on the same line as a call site — that fixture carries
    the guarantee. `test_no_url_the_live_tree_writes_in_code_is_lost_to_comment
    _stripping` watches the tree that actually ships, and only fires when the
    shipped tree happens to contain the shape.
    """
    agreed = zip(
        source,
        comment_mask(source, regex_aware=True),
        comment_mask(source, regex_aware=False),
        strict=True,
    )
    return "".join(
        " " if believed and confirmed else char for char, believed, confirmed in agreed
    )


def named_resource_urls(tree: Path) -> dict[str, list[str]]:
    """Every `resource://` string literal in the tree, mapped to where it is written.

    A file that cannot be read is warned about and skipped rather than allowed
    to abort the walk: one unreadable sibling would otherwise take down the
    scan of every file beside it. The warning is what keeps that honest — a
    quiet skip would turn a file the guard could not read into a file the guard
    approved, the failure `require_install` warns about one level up.
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
        for number, line in enumerate(strip_comments(text).splitlines(), 1):
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


def test_a_url_quoted_in_a_trailing_comment_is_not_a_call_site(tmp_path):
    """A comment that shares its line with code is still a comment.

    `LINE_COMMENT` drops narration owning a whole line; it cannot see a comment
    opened after a statement, and the quote anchor then reads the URL inside it
    as a literal. `bootstrap.js` narrates the Fluent episode in half a dozen
    places, so the guard passes today only because none of that narration
    happens to quote the path on a line that also carries code — a property of
    the prose, not of the checker, and the same accident round 1 fixed one layer
    down.

    The fixture writes the three shapes a stripper has to tell apart: a `//`
    comment after a statement, a `/* */` comment after a statement, and a block
    comment whose continuation line starts with neither a slash nor a star, so
    that only real block-comment state can drop it.
    """
    source = tmp_path / "bootstrap.js"
    source.write_text(
        "const timers = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');"
        f" // we used to require '{HISTORICAL_ABSENT}' here\n"
        "const SDT = win.require('resource://zotero/document-worker/sdt.js');"
        f" /* and once as '{HISTORICAL_ABSENT}' */\n"
        "/* the episode, at length:\n"
        f"   the spec was '{HISTORICAL_ABSENT}', and it threw on every startup\n"
        "*/\n"
        "win.require('resource://zotero/document-worker/metadata.json');\n",
        encoding="utf-8",
    )

    sites = named_resource_urls(tmp_path)

    assert HISTORICAL_ABSENT not in sites, (
        f"narration quoted beside code is still narration: {sites}"
    )
    assert sorted(sites) == [
        "resource://gre/modules/Timer.sys.mjs",
        "resource://zotero/document-worker/metadata.json",
        "resource://zotero/document-worker/sdt.js",
    ], sites


#: A `/` beside a call site, once per way of misreading one. Each line must
#: yield its URL. `strip_comments` deletes a call site only by blanking, and it
#: blanks only comments, so every entry here is a way of tricking a scanner into
#: opening one over live code — the whole silent-pass surface, and the reason
#: `strip_comments` intersects two readings instead of trusting either.
#:
#: The first four are regex literals a preceding-token heuristic cannot classify:
#: `)`, `]`, an identifier and a number precede a regex and a division alike.
#: Walked as code, `/[/*]/` opens a block comment that runs to the next `*/` or
#: to end of file, and `/['"]/` opens a string literal. Round 1 of the review on
#: PR #461 reproduced all four against the token heuristic.
#:
#: The last two are the mirror image, found in round 2 against the credulous
#: reading that replaced it. A division whose search for a closing `/` runs into
#: a later string desynchronises the quote state, and the `//` of a real URL then
#: reads as a comment — both halves of that line exist verbatim in `bootstrap.js`
#: (`:502` and `:512`). A regex closing immediately before another `/` presents a
#: `//` that is not a comment.
REGEX_HAZARDS = (
    "if (matches(p)) /[/*]/.test(p);",
    "const first = names[0] /[/*]/.exec(p);",
    "const flag = config.enabled /['\"]/.test(p);",
    "const scaled = 42 /['\"]/.source.length;",
    "const pct = done / total; const sep = 'a/b';",
    "const n = /ab//1;",
)


def test_a_regex_literal_does_not_swallow_the_call_site_beside_it(tmp_path):
    """The stripper's own control, in the one direction that fails silently.

    Reading a comment as code costs a false red. Reading *code* as a comment
    deletes a call site and the guard goes green — the failure ticket 0737
    forbids outright. A `/` is where that happens: its body, if it has one, can
    carry `/*` or a quote, and both are inert inside a literal and destructive
    outside one. `bootstrap.js` splits a path on `/[\\\\/]/` and divides on
    `:512`, so both shapes are live; the fixture is named for a sibling only to
    stay distinct from the other fixtures here.

    The `/` and the call must share a LINE for this to discriminate. On separate
    lines the damage is stopped by `end_of_quoted`'s newline bound before it
    reaches the call, and the test then passes against a stripper with no regex
    handling at all — which is how the first draft was written, and why the
    shape is now pinned by construction.

    The table this drives is the record of two rounds of review on PR #461, and
    the reason it is a table: round 1 found four cases the preceding-token
    reading missed, round 2 found two more that the credulous reading which
    replaced it missed, and each reading passed the other's cases. A repair that
    closes one group and not the other cannot read as a fix here.

    Each hazard runs alone and then all six run in one file, because the two are
    different questions and only the second caught the last defect. A misread
    `/*` opening a block comment nothing closes used to mask to end of file, so
    one hazard on line 1 deleted another's call site four lines down while every
    hazard passed in isolation.
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
        "a call site was blanked by the `/` on its own line: "
        + ", ".join(f"{REGEX_HAZARDS[urls.index(url)]!r}" for url in sorted(set(urls) - set(solo)))
    )

    together = tmp_path / "together"
    together.mkdir()
    (together / "scheduler.js").write_text("".join(lines), encoding="utf-8")
    sites = named_resource_urls(together)

    assert sites == {url: [f"scheduler.js:{n}"] for n, url in enumerate(urls, 1)}, (
        "a hazard reached across lines to blank another's call site: "
        + ", ".join(f"{REGEX_HAZARDS[urls.index(url)]!r}" for url in sorted(set(urls) - set(sites)))
    )


def test_no_url_the_live_tree_writes_in_code_is_lost_to_comment_stripping():
    """Positive control for the stripper against the tree that actually ships.

    A fixture proves the stripper handles the shapes someone thought to write.
    Only the shipped tree proves it handles the shapes someone did write. So
    every URL the unstripped scan reports under `plugins/` must still be
    reported after stripping — otherwise the guard would go green by having
    blanked the call sites it exists to check, which is this suite's own
    all-clear-indistinguishable-from-could-not-look failure, one layer down.

    Read what this can and cannot witness, because the two are easy to confuse.
    It fires when stripping destroys something the shipped tree writes: deleting
    the string branch of `strip_comments` reddens it, under its own message. It
    stays green against a stripper that removes nothing at all — the identity
    function passes — which is correct, since removing nothing cannot lose a
    call site, and it is also why this is a floor and not a guarantee. Its
    sensitivity is a property of `plugins/`, not of the test: today the three
    real URLs (`bootstrap.js:1095`, `:1172`, `:1174`) share a line with none of
    the tree's regex literals (`:189`, `:284`, `:1279`, `:1331`, `:1413`), so
    the whole hazard class in `REGEX_HAZARDS` is invisible here — which is how
    both rounds of review on PR #461 found silent passes this stayed green over.
    That fixture carries the guarantee. This watches the tree.

    A legitimate divergence is possible: it means someone wrote a `resource://`
    URL inside a comment trailing a line of code, which is exactly what the
    stripper is for. Read the two sets before relaxing this — a URL that
    vanished from a line carrying no comment is the defect.
    """
    unstripped: dict[str, list[str]] = {}
    for path in sorted(PLUGINS.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            if LINE_COMMENT.match(line):
                continue
            for match in RESOURCE_URL.finditer(line):
                site = f"{path.relative_to(PLUGINS).as_posix()}:{number}"
                unstripped.setdefault(match.group(1), []).append(site)

    assert unstripped, "the unstripped control found nothing, so it can witness no loss"
    assert named_resource_urls(PLUGINS) == unstripped, (
        "comment stripping changed what the shipped plugin tree reports"
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
