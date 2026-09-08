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
    """
    ini = install / "app" / "application.ini"
    if not ini.is_file():
        return "version unknown (no app/application.ini)"
    for line in ini.read_text(encoding="utf-8", errors="replace").splitlines():
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
    """Every `resource://` string literal in the tree, mapped to where it is written."""
    sites: dict[str, list[str]] = {}
    for path in sorted(tree.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
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

    `bootstrap.js` still narrates the Fluent episode. The extraction is anchored
    on an opening quote so those sentences stay out of the checked set — asserted
    here against a fixture that writes the historical string both ways, rather
    than against today's comment wording, which would make the test pass by
    accident of how the narration happens to be phrased.
    """
    source = tmp_path / "bootstrap.js"
    source.write_text(
        f"// The import of {HISTORICAL_ABSENT} threw on every startup.\n"
        f"ChromeUtils.importESModule('{HISTORICAL_ABSENT}');\n",
        encoding="utf-8",
    )

    sites = named_resource_urls(tmp_path)

    assert sites == {HISTORICAL_ABSENT: ["bootstrap.js:2"]}, sites
    assert HISTORICAL_ABSENT not in named_resource_urls(PLUGINS), (
        "the historical defect is back in the plugin source"
    )


def test_no_plugin_file_type_escapes_the_scan():
    """`SOURCE_SUFFIXES` covers every file the plugin tree actually ships.

    The same hand-listed-scope shape as the directory comment above, one axis
    over: an `.xhtml` dialog or a `.ftl` bundle arriving under `plugins/` would
    carry `resource://` literals that this suite never reads, and nothing would
    say so. Adding a suffix here is cheap; noticing its absence later is not.
    """
    shipped = {path.suffix for path in PLUGINS.rglob("*") if path.is_file()}
    unscanned = shipped - set(SOURCE_SUFFIXES)
    assert not unscanned, (
        f"file types under {PLUGINS} that the resource:// scan never reads: "
        f"{sorted(unscanned)} — extend SOURCE_SUFFIXES or say why they are exempt"
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
