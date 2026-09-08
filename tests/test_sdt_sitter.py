"""Exercise the admission loop, the sitter's UI vocabulary, and how it installs.

The vocabulary tests are deliberately *not* a whole-file "SDT does not appear"
grep. Such a grep both false-positives on the internal identifiers that must
survive (``createSDTSitter``, ``Zotero.SDT.ensure``, the cache filenames) and
false-negatives on the defects that carry no literal ``SDT`` at all -- the
toolbar tooltip used to interpolate raw internal phase names, and the active
document row used to print a bare item id. Each test below is anchored to one
template site and asserts both the new wording and the absence of the specific
jargon it replaced.

The installation tests (ticket 0688) ask a different question from all of
those: an add-on that is never persistently installed, or whose manifest names
a host nothing can resolve, disappears from the plugin list without one word of
its vocabulary being wrong and without its scheduler misbehaving once. What
they guard is the part that leaves no trace when it fails -- a profile read
that silently says "absent", a placeholder URL, and a startup that says nothing
about which build was running.

The version-bump guard's own suite is `tests/test_check_sitter_version.py`,
where the repository's guard-completeness convention puts it.

Ticket 0692 moved the wording out to `locale/<tag>/sdt-pack-sitter.ftl`; the
author had the whole multilingual layer removed again on 2026-09-07, so the
strings are back in `bootstrap.js`, in the `SDT_TEXT` table, in English only.
The vocabulary assertions are anchored on that table, one message id at a time.
What stays anchored on the code is the *plumbing*: which composer reads which
id, that no site keeps a second copy of a figure, and that no sentence has
crept back into a call site. The two halves are still checked apart, because a
wording test that read the call sites would go green the day a string moved.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'bench') not in sys.path:
    sys.path.insert(0, str(ROOT / 'bench'))

from sdt_sitter_install import ADDON_ID, install, read_addon_record  # noqa: E402

SITTER = ROOT / 'plugins' / 'sdt-sitter'
BOOTSTRAP = SITTER / 'bootstrap.js'
SCHEDULER = SITTER / 'scheduler.js'

#: The one language there is, kept as a tuple so the loops that iterated the
#: four locales still read as what they check: every language this add-on ships
#: obeys the vocabulary ban, carries no internal build name, and renders both
#: halves of the session clause. That was four files and is now one table
#: (author's instruction, 2026-09-07); the shape of the assertion did not change
#: with the count, and collapsing the loops would only have to be undone if a
#: second language ever returns.
LOCALES = ('en',)

#: The two strings whose meaning is carried by a number. They are the only
#: entries in `SDT_TEXT` that are a [singular, plural] pair rather than a
#: string; everything else is a sentence.
PLURAL_MESSAGES = ('files-indexed', 'files-failed')

#: A second add-on, so "present" can be told from "something is present".
OTHER_ID = 'zotero-better-bibtex@iris-advies.com'

#: A document nested deeply enough that `json` gives up on it. Measured, not
#: guessed: 20 000 parses fine on CPython 3.14, whose stack guard only fires
#: around 200 000, while older interpreters hit the recursion limit far earlier.
#: A depth that only reddens on one interpreter is an arm that proves nothing on
#: the next, so the fixture is sized for the laxest one seen.
TOO_DEEP = '[' * 200_000 + ']' * 200_000


def write_extensions(profile: Path, addons: list[dict]) -> Path:
    profile.mkdir(parents=True, exist_ok=True)
    path = profile / 'extensions.json'
    path.write_text(json.dumps({'schemaVersion': 35, 'addons': addons}), encoding='utf-8')
    return path


def sitter_entry(**overrides) -> dict:
    entry = {'id': ADDON_ID, 'version': '2.5.0', 'active': True,
             'location': 'app-profile', 'type': 'extension'}
    entry.update(overrides)
    return entry


def other_entry() -> dict:
    """Same shape, same location, same version — everything but the id."""
    return {'id': OTHER_ID, 'version': '2.5.0', 'active': True,
            'location': 'app-profile', 'type': 'extension'}

BUTTON_BLOCK = ('for (const button of buttons) {', 'for (const dialog of dialogs) {')

# Every site that produces text a reader sees. The ban below is checked against
# each one, rather than against the whole file, so internal element ids
# ('sdt-document-status') and helper names (formatDocumentDuration) stay legal.
UI_SITES = (
    ('function describeSDTTooltip(state) {', '\n}'),
    ('function describeSDTIndexed(count) {', '\n}'),
    ('function describeSDTFailures(count) {', '\n}'),
    ('function announceSDTSweep(before) {', '\n}'),
    ('function describeSDTScope() {', '\n}'),
    ('function describeSDTCoverage(state) {', '\n}'),
    ('function describeSDTFile(info, fallback) {', '\n}'),
    ('function describeSDTActiveFile(state) {', '\n}'),
    ('var SDT_PHASE_LABELS = {', '};'),
    ('status.textContent = ', ';'),
    ('const activeMessage = ', 'const quietMessage'),
    ('const quietMessage = ', ';'),
    ("getElementById('sdt-failures').textContent", ';'),
    ('doc.title = ', ';'),
    ("section('sdt-global-section'", ']);'),
    ("section('sdt-document-section'", ']);'),
    ('indexSummary.textContent = ', ';'),
    ("getElementById('sdt-fulltext').textContent", ';'),
    ('Services.prompt.confirm(', 'if (token !== generation) return;'),
    ('describeError: (info, error) =>', 'reportError:'),
    # The disclosure layers of ticket 0693. A site added to the dialog and not
    # added here is a site the vocabulary ban stops covering, which is the
    # asymmetry this list fails on: removing a site is loud, arriving is silent.
    # Since ticket 0692 the same list carries the localization rule: a site
    # named here may hold message ids and typography, never prose. Add the site
    # when you add the layer, and the guard arrives with it.
    ('function formatSDTBytes(bytes) {', '\n}'),
    ('function formatSDTAge(ms) {', '\n}'),
    ('function describeSDTEnvironment() {', '\n}'),
    ('function describeSDTAdmission() {', '\n}'),
    ('function describeSDTJournalTail(limit = 50) {', '\n}'),
    ('function composeSDTJournalReport() {', '\n}'),
    ('function buildSDTDiagnostics(doc, element) {', '\n}'),
    ("getElementById('sdt-observations').textContent", ';'),
    # The census account of ticket 0693's second pass. Both halves are sites: the
    # composer that builds the rows, and the label lookup that decides what a
    # status is called -- a raw key falling through the lookup is the defect the
    # ruling repaired, and a literal written here is how it would come back.
    ('function describeSDTStatusLabel(status) {', '\n}'),
    ('function describeSDTCensusAccount(counts) {', '\n}'),
    # The end-of-sweep toast of ticket 0696, and the first site this list
    # acquired after 0692 externalized the wording. It arrived carrying one
    # French literal for its headline, which is what the note above predicts and
    # what adding the site here refuses.
    ('function announceSDTSweep(before) {', '\n}'),
    ('function describeSDTIndexed(count) {', '\n}'),
    ('function describeSDTFailures(count) {', '\n}'),
)

# "document" is the trap: Zotero's own French UI renders *item* as "document",
# so it reads as the reference, which is the opposite of the attachment this
# add-on actually indexes. "élément" and "pièce jointe" are the same confusion
# from the other side.
BANNED_IN_UI = ('document', 'élément', 'pièce jointe', 'item', 'pack')


def _site(start: str, end: str, path: Path | None = None) -> str:
    """Return the source between two anchors, so an assertion is scoped to one
    template site rather than to the whole file."""
    source = (path or BOOTSTRAP).read_text(encoding='utf-8')
    assert start in source, f'anchor absent: {start!r}'
    begin = source.index(start)
    assert end in source[begin:], f'closing anchor absent after {start!r}: {end!r}'
    return source[begin:source.index(end, begin)]


def messages(tag: str = 'en') -> dict[str, str | list[str]]:
    """`id -> text` read out of `bootstrap.js`'s `SDT_TEXT` table.

    Read from the source rather than restated, so a reworded string is argued
    with here rather than silently agreed with. The `tag` argument survives the
    removal of the multilingual layer (2026-09-07) so the call sites did not all
    have to change on the same day; there is one language now and it is ignored.

    Parsed as JSON, which the table is: the generator that inlined it emitted
    `json.dumps` output, and keeping it parseable that way is what lets this
    read the wording without a JavaScript engine.
    """
    source = BOOTSTRAP.read_text(encoding='utf-8')
    start = source.index('var SDT_TEXT = ')
    begin = source.index('{', start)
    depth, index, in_string, escaped = 0, begin, False, False
    while index < len(source):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                break
        index += 1
    return json.loads(source[begin:index + 1])


#: `{ $count ->`, `{ $name }`, `[one]`, `*[other]`, `}` — everything a reader of
#: the rendered string never sees. Stripping them is what lets the vocabulary
#: ban below be about words rather than about variable names.
SELECTOR = re.compile(r'\{\s*\$[A-Za-z][\w-]*\s*->')
PLACEABLE = re.compile(r'\{[^{}]*\}')
VARIANT_KEY = re.compile(r'^\s*\*?\[[^\]]*\]', re.MULTILINE)
#: The ONLY placeable the stub implements, spelt as `tests/fluent_stub.mjs`
#: spells it. `PLACEABLE` above is deliberately looser, because `visible()`
#: wants every construct gone; the subset guard wants the ones outside the
#: subset left standing, so it strips with this instead.
VARIABLE = re.compile(r'\{\s*\$[A-Za-z][A-Za-z0-9_-]*\s*\}')


def visible(pattern: str | list[str]) -> str:
    """The text a reader actually sees, with the `{name}` slots removed.

    A plural entry is a [singular, plural] pair, and both halves are text a
    reader meets, so both are returned for the vocabulary ban to read.
    """
    if isinstance(pattern, list):
        return ' '.join(visible(half) for half in pattern)
    return PLACEABLE.sub(' ', pattern)


#: Comments, which are not user-facing text and are full of apostrophes. The
#: naive string extractor reads "the locale's, not this file's" as a quoted
#: literal `s, not this file`, and the tightened sentence heuristic below then
#: reports it as prose in the source. Prose it is — in a comment, where it
#: belongs.
COMMENT = re.compile(r'/\*.*?\*/|//[^\n]*', re.DOTALL)


def _ui_strings(site: str) -> list[str]:
    """The literal text a reader sees in one site: quoted strings, plus the prose
    between a template literal's interpolations. Identifiers are excluded by
    construction, element ids by their 'sdt-' prefix."""
    text = re.findall(r"'((?:[^'\\]|\\.)*)'", site)
    for chunk in re.findall(r'`((?:[^`\\]|\\.)*)`', site):
        text.extend(re.split(r'\$\{[^}]*\}', chunk))
    return [item for item in text if item.strip() and not item.startswith('sdt-')]


@pytest.mark.integration
def test_sdt_sitter_scheduler():
    subprocess.run(['node', 'tests/sdt_sitter_scheduler.mjs'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=30)


@pytest.mark.integration
def test_sdt_sitter_dialog():
    """The disclosure layers, driven against a stub document rather than read.

    Nesting, closed-by-default, the debug switch's two directions, the ring tail
    with the pref off, and what the copy action may carry are all behaviour; the
    source says nothing about any of them.
    """
    subprocess.run(['node', 'tests/sdt_sitter_dialog.mjs'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=30)


@pytest.mark.integration
@pytest.mark.integration
def test_sdt_sitter_bootstrap():
    """`initialize()`'s own closure, run against a mock Zotero host.

    The scheduler suite above supplies its own `blocked`, `inspect` and cache, so
    it exercises the admission contract and never the implementations bootstrap.js
    passes it: the /proc reads, the pack reader, the cache file as the next
    session finds it, the two windows, the two clocks. Ticket 0695.
    """
    subprocess.run(['node', 'tests/sdt_sitter_bootstrap.mjs'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=60)


@pytest.mark.integration
def test_sdt_sitter_bootstrap_syntax():
    subprocess.run(['node', '--check', 'plugins/sdt-sitter/bootstrap.js'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=30)


@pytest.mark.integration
def test_probe_javascript_parses():
    """The Makefile puts `verification/probes/` in the lint gate on the ground
    that a probe which produced committed evidence is code we depend on. Ruff is
    Python-only, so the JavaScript probes were in scope by intent and covered by
    nothing -- a syntax error in the in-app harness stays invisible until someone
    boots a real Zotero, which is the one run that costs an evening. Discovered
    while adding the layer assertions of ticket 0693 to that harness.
    """
    probes = sorted((ROOT / 'verification' / 'probes').rglob('*.js'))
    assert probes, 'no JavaScript probe found: the glob, not the tree, is what changed'
    for probe in probes:
        subprocess.run(['node', '--check', str(probe)], cwd=ROOT,
                       check=True, capture_output=True, text=True, timeout=30)


def test_read_addon_record_discriminates_present_absent_and_someone_else(tmp_path):
    """Three arms, because two would pass on a check that matches the wrong field.

    A positive and a negative arm alone are satisfied by a reader keyed on
    `location` or `version` — both of which the third arm's entry also carries.
    Only an id-keyed read can tell "our add-on is installed" from "an add-on is
    installed", and that is the sentence the verify target prints.
    """
    installed = tmp_path / "installed"
    entry = sitter_entry()
    write_extensions(installed, [other_entry(), entry])
    record = read_addon_record(installed)
    assert record == {"read": True, "present": True, "version": entry["version"],
                      "active": entry["active"], "location": entry["location"]}

    removed = tmp_path / "removed"
    write_extensions(removed, [other_entry()])
    record = read_addon_record(removed)
    assert record["read"] is True and record["present"] is False
    assert record["ids"] == [OTHER_ID]

    # The third arm and the reason this test exists: a foreign add-on whose
    # every other field matches ours must not read as ours.
    foreign = tmp_path / "foreign"
    write_extensions(foreign, [other_entry()])
    assert read_addon_record(foreign)["present"] is False

    # And an unreadable profile is reported as unread, never coerced to absent:
    # "we looked and it is gone" and "we could not look" are different findings.
    missing = tmp_path / "missing"
    missing.mkdir()
    assert read_addon_record(missing) == {
        "read": False, "why": f"{missing / 'extensions.json'} does not exist"}

    unparseable = tmp_path / "unparseable"
    unparseable.mkdir()
    (unparseable / "extensions.json").write_text("{ truncated", encoding="utf-8")
    record = read_addon_record(unparseable)
    assert record["read"] is False and "present" not in record


def test_a_document_of_the_wrong_shape_is_unread_rather_than_absent(tmp_path):
    """Valid JSON is not a valid record, and the difference is a whole verdict.

    `[]` and `"text"` parse cleanly and then have no `.get`. The first draft
    let that AttributeError out of `main()`, where Python exits 1 — the code
    this tool means by ABSENT. A crash landing on "the plugin is gone" is the
    exact collapse the three-valued read exists to prevent.
    """
    for document in ("[]", '"text"', "3", "null"):
        profile = tmp_path / f"shape-{abs(hash(document))}"
        profile.mkdir()
        (profile / "extensions.json").write_text(document, encoding="utf-8")
        record = read_addon_record(profile)
        assert record["read"] is False, document
        assert "present" not in record, document

    # A document nested past the recursion limit. `json` rejects it by
    # exhausting the stack, and RecursionError is a RuntimeError — outside the
    # families a reader catches by reflex, and so out through main() into the
    # ABSENT code.
    deep = tmp_path / "deep"
    deep.mkdir()
    (deep / "extensions.json").write_text(TOO_DEEP, encoding="utf-8")
    assert read_addon_record(deep)["read"] is False


def test_an_element_of_the_wrong_shape_is_absent_rather_than_a_crash(tmp_path):
    """The third floor of the same trapdoor: document, container, then element.

    An entry whose `id` is a number is valid JSON in a valid object in a valid
    list, and it met `sorted()` over mixed types — where `str < int` raises
    TypeError, out of `main()`, into exit 1, which this tool reads as ABSENT.
    """
    profile = tmp_path / "mixed"
    write_extensions(profile, [
        {"id": 17, "version": "1.0"},
        other_entry(),
        {"id": None},
        {"id": ["a", "list"]},
        "not an object at all",
        {},
    ])
    record = read_addon_record(profile)
    assert record["read"] is True and record["present"] is False
    assert record["ids"] == [OTHER_ID], record["ids"]

    # And the add-on is still found when it sits among that debris.
    write_extensions(profile, [{"id": 17}, sitter_entry(), "junk"])
    assert read_addon_record(profile)["present"] is True


@pytest.fixture
def unsearchable_profile(tmp_path):
    """A profile holding `extensions.json`, then stripped of its search bit.

    Mode 0o600 is readable and not searchable, so `open()` on anything inside
    fails with EACCES — the errno `pathlib` does *not* fold into "not a file".
    The mode is restored in teardown so a failing assertion cannot leave
    `tmp_path` undeletable.
    """
    profile = tmp_path / "locked"
    write_extensions(profile, [sitter_entry()])
    profile.chmod(0o600)
    try:
        yield profile
    finally:
        profile.chmod(0o700)


@pytest.mark.skipif(os.geteuid() == 0,
                    reason="root ignores the search bit, so the arm discriminates nothing")
def test_an_unsearchable_profile_is_unread_rather_than_a_crash(unsearchable_profile):
    """`is_file()` sat outside the `try`, and EACCES is not one of the errnos
    `pathlib` swallows — so a profile directory without its search bit raised
    PermissionError past the guard, out of the reader, into the caller. Exit 1
    is what this tool means by ABSENT, so a profile nobody could read reported
    as a plugin that is gone: the exact collapse the three-valued read exists
    to prevent.
    """
    # Positive control: the setup really is unreadable, so a green below is the
    # reader's doing and not the filesystem's indulgence.
    with pytest.raises(PermissionError):
        (unsearchable_profile / "extensions.json").read_text(encoding="utf-8")

    record = read_addon_record(unsearchable_profile)
    assert record["read"] is False
    assert "present" not in record
    # Named as a permission, so the arm cannot be satisfied by a reader that
    # reports the file missing.
    assert "PermissionError" in record["why"], record["why"]


@pytest.mark.integration
@pytest.mark.skipif(os.geteuid() == 0,
                    reason="root ignores the search bit, so the arm discriminates nothing")
def test_verify_on_an_unsearchable_profile_exits_could_not_read(unsearchable_profile):
    """The contract a Make target sees: 3, not the traceback-and-1 of a crash."""
    result = cli("verify", "--profile", str(unsearchable_profile))
    assert result.returncode == 3, result.stderr
    assert "Traceback" not in result.stderr
    assert json.loads(result.stdout)["read"] is False


def test_install_refuses_an_addon_id_that_is_not_one_path_component(tmp_path):
    """The id becomes a filename; a separator in it writes outside the profile."""
    profile = tmp_path / "profile"
    (profile / "extensions").mkdir(parents=True)
    xpi = tmp_path / "built.xpi"
    xpi.write_bytes(b"PK\x03\x04")
    for hostile in ("../../evil", "a/b", "..", ".", ""):
        with pytest.raises(ValueError):
            install(profile, xpi, hostile)
    assert list((profile / "extensions").iterdir()) == []


# ---- the exit codes, which are the contract a Make target and a shell see ----

def cli(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "bench" / "sdt_sitter_install.py"),
                           *arguments], capture_output=True, text=True, timeout=60)


@pytest.mark.integration
def test_verify_exit_codes_separate_present_absent_and_unread(tmp_path):
    """Driven through the CLI, because nothing outside Python sees the dict.

    The shape bug above shipped precisely because the dict was tested and the
    exit code was not: `read_addon_record` was returning nothing wrong, it was
    raising, and the raise only becomes a wrong ANSWER at the process boundary.
    """
    present = tmp_path / "present"
    write_extensions(present, [other_entry(), sitter_entry()])
    assert cli("verify", "--profile", str(present)).returncode == 0

    absent = tmp_path / "absent"
    write_extensions(absent, [other_entry()])
    result = cli("verify", "--profile", str(absent))
    assert result.returncode == 1
    assert OTHER_ID in result.stdout + result.stderr

    never_opened = tmp_path / "never-opened"
    never_opened.mkdir()
    assert cli("verify", "--profile", str(never_opened)).returncode == 3

    for document in ("[]", '"text"', "{ truncated", TOO_DEEP):
        wrong = tmp_path / f"wrong-{abs(hash(document))}"
        wrong.mkdir()
        (wrong / "extensions.json").write_text(document, encoding="utf-8")
        result = cli("verify", "--profile", str(wrong))
        assert result.returncode == 3, f"{document[:40]}: {result.stdout}{result.stderr}"

    # An element of the wrong shape is a real ABSENT, not a crash wearing its
    # exit code: the process must reach report() and print a record.
    mixed = tmp_path / "mixed"
    write_extensions(mixed, [{"id": 17}, other_entry()])
    result = cli("verify", "--profile", str(mixed))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert json.loads(result.stdout)["present"] is False

    # An id nobody installed is absent, and the message must name the id that
    # was looked for rather than the module's default.
    result = cli("--addon-id", "nobody@example.org", "verify", "--profile", str(present))
    assert result.returncode == 1
    assert "nobody@example.org" in result.stdout + result.stderr


@pytest.mark.integration
def test_install_exit_codes_refuse_rather_than_guess(tmp_path):
    xpi = tmp_path / "built.xpi"
    xpi.write_bytes(b"PK\x03\x04")
    profile = tmp_path / "profile"
    profile.mkdir()
    assert cli("install", "--profile", str(profile), "--xpi", str(xpi)).returncode == 0
    assert cli("install", "--profile", str(tmp_path / "nope"), "--xpi", str(xpi)).returncode == 2
    assert cli("install", "--profile", str(profile),
               "--xpi", str(tmp_path / "nope.xpi")).returncode == 2
    assert cli("--addon-id", "../escape", "install", "--profile", str(profile),
               "--xpi", str(xpi)).returncode == 2
    # A missing --profile is argparse's refusal, not a default.
    assert cli("verify").returncode != 0


def test_install_writes_the_xpi_where_the_host_looks_for_it(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    xpi = tmp_path / "built.xpi"
    xpi.write_bytes(b"PK\x03\x04 not really a zip, but the bytes must survive")
    destination = install(profile, xpi)
    assert destination == profile / "extensions" / f"{ADDON_ID}.xpi"
    assert destination.read_bytes() == xpi.read_bytes()


def test_install_refuses_a_profile_that_does_not_exist(tmp_path):
    """Never create the directory: a guessed profile installs into nothing."""
    xpi = tmp_path / "built.xpi"
    xpi.write_bytes(b"PK\x03\x04")
    with pytest.raises(FileNotFoundError):
        install(tmp_path / "no-such-profile", xpi)


def test_the_addon_id_is_the_one_the_manifest_declares():
    """The second copy is the one that goes stale, and this one fails silently.

    `install` names the file `<ADDON_ID>.xpi` and `verify` looks the same string
    up in `extensions.json`. Let it drift from the manifest and the install
    lands under a filename the host attributes to nothing, while verify reports
    ABSENT — indistinguishable from the disappearance this ticket is about.
    """
    manifest = json.loads((SITTER / "manifest.json").read_text(encoding="utf-8"))
    assert ADDON_ID == manifest["applications"]["zotero"]["id"]
    update = json.loads((SITTER / "update.json").read_text(encoding="utf-8"))
    assert ADDON_ID in update["addons"]


def test_manifest_names_no_unresolvable_host():
    """RFC 2606 reserves `.invalid` so that it never resolves. An id is not a URL.

    The id stays as it is — Zotero never dereferences it — but every field whose
    value IS fetched has to name a host that exists, or the plugin's update check
    fails against a name guaranteed to fail.
    """
    manifest = json.loads((SITTER / "manifest.json").read_text(encoding="utf-8"))
    zotero = manifest["applications"]["zotero"]
    update_url = zotero.get("update_url")
    assert update_url is None or (
        "example.invalid" not in update_url and ".invalid/" not in update_url), update_url
    if update_url is not None:
        update = json.loads((SITTER / "update.json").read_text(encoding="utf-8"))
        assert update_url.endswith("/plugins/sdt-sitter/update.json"), update_url
        assert list(update["addons"]) == [zotero["id"]]


def test_update_json_advertises_the_version_the_manifest_ships():
    """Two files state the shipped version, so they can disagree. Ticket 0727.

    `update.json` used to list this add-on with an EMPTY updates array, on the
    reading that empty means "no update available". Measured against Zotero
    10.0.1 that is the suspected cause of the plugin uninstalling itself: an
    add-on the host is told has zero versions has none the host can find
    compatible, and it was seen disabled and then deleted mid-session. The list
    now carries the shipped version — which makes the manifest's `version` and
    the advertised one one fact in two files, and the second is the one that
    goes stale, silently, in the direction that reintroduces the defect.

    An entry OLDER than what is installed is the same finding as an empty list
    for the reader this exists to protect, so equality is what is asserted, not
    presence.
    """
    manifest = json.loads((SITTER / "manifest.json").read_text(encoding="utf-8"))
    update = json.loads((SITTER / "update.json").read_text(encoding="utf-8"))
    entries = update["addons"][manifest["applications"]["zotero"]["id"]]["updates"]
    assert entries, (
        "update.json lists this add-on with no versions at all, which is the "
        "shape ticket 0727 is about")
    assert [entry["version"] for entry in entries] == [manifest["version"]], (
        f'update.json advertises {[e["version"] for e in entries]}, '
        f'manifest.json ships {manifest["version"]}')
    # The bounds travel with it: an entry compatible with nothing is a version
    # the host still cannot accept.
    zotero = manifest["applications"]["zotero"]
    advertised = entries[0]["applications"]["zotero"]
    assert advertised["strict_min_version"] == zotero["strict_min_version"]
    assert advertised["strict_max_version"] == zotero["strict_max_version"]


@pytest.mark.integration
def test_startup_self_check_is_emitted_before_anything_else_can_fail():
    """Driven, not read. A log line asserted by inspection is a log line nobody ran."""
    subprocess.run(['node', 'tests/sdt_sitter_startup.mjs'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=30)


def test_toolbar_button_label_reads_index():
    """The word and the figure come from one composer, so the button cannot show
    a label the tooltip's own coverage segment disagrees with. Before ticket 0692
    the word was concatenated at this site and the figure came from the composer;
    a locale that translates "Index" would have moved only half of it."""
    block = _site(*BUTTON_BLOCK)
    assert "describeSDTCoverage(s) || sdtText('index')" in block, \
        'the button composes its own label instead of reading the coverage composer'
    assert "setAttribute('label', spinning" in block and 'coverageLabel' in block
    assert 'SDT' not in ''.join(_ui_strings(block)), 'the internal name reached the toolbar'
    assert messages()['index'] == 'Index'


def test_toolbar_tooltip_counts_files_not_packs():
    assert 'files indexed' in messages()['files-indexed'][1]
    assert 'packs créés' not in BOOTSTRAP.read_text(encoding='utf-8')
    # 0696's structure and 0692's wording, asserted apart: the tooltip reads the
    # one composer, and the composer reads the one message. Either half alone
    # would go green while the other rotted.
    assert 'describeSDTIndexed(' in _site('function describeSDTTooltip(state) {', '\n}')
    assert "sdtText('files-indexed'" in _site('function describeSDTIndexed(count) {', '\n}')


def test_no_user_facing_string_says_document():
    """The unit of work is one attachment, and every count must name it, in every
    language. Comments are out of scope by construction -- this is a rule about
    what a reader is shown, and the locale files' own headers have to be able to
    state the rule they are subject to."""
    for tag in LOCALES:
        for name, pattern in messages(tag).items():
            text = visible(pattern).lower()
            for word in BANNED_IN_UI:
                assert word not in text, f'{word!r} in {tag}.ftl message {name!r}: {pattern!r}'


def phase_names() -> set[str]:
    """The internal phase names, which are keys of `SDT_PHASE_LABELS` and one of
    which reads like a sentence: `'launch-declined; disable/re-enable to
    launch'`. Read from the source rather than listed, so a phase renamed in
    `bootstrap.js` does not leave an exemption behind that covers nothing."""
    table = _site('var SDT_PHASE_LABELS = {', '};')
    return {match for match in re.findall(r"^\s*'([^']+)':", table, re.MULTILINE)}


def looks_like_a_sentence(text: str) -> bool:
    """Prose a reader would be shown, as opposed to an identifier or punctuation.

    Two words that carry letters, which rules out `' — '` and `', '` — those are
    typography and stay in the source. The first draft additionally required a
    capital or an accent, and a red-team probe walked straight through it with a
    lowercase ASCII fallback (`'unknown size'`), full suite green. The capital
    was standing in for one thing only: the internal phase key that reads like a
    sentence. So the exemption is now that key by name, and the heuristic no
    longer has to guess at case.
    """
    if text in phase_names():
        return False
    words = [word for word in text.split() if any(character.isalpha() for character in word)]
    return len(words) >= 2


def test_no_ui_site_keeps_a_sentence_of_its_own():
    """The forward rule, and the half that catches the NEXT ticket rather than
    this one.

    Ticket 0692 moved the wording out; nothing stops 0693, 0696, 0699 or
    whatever follows from writing a new string straight into a `.textContent`.
    Two directions, because a new literal and a stale one look different: no
    message of any locale may appear verbatim in the source (that is what a
    literal looks like once somebody translates around it), and no site may
    hold prose that is in no locale at all (that is what a brand-new one looks
    like). Adding a string means adding it to `SDT_TEXT` and reading it with
    `sdtText`.

    The first half reads the source with the TABLE CUT OUT of it. Until
    2026-09-07 the wording lived in four `.ftl` files, so "appears in
    bootstrap.js at all" was the duplication; now the table is in bootstrap.js,
    and that test would fail against its own single source of truth. The
    invariant did not change — one home per string — only where the home is.
    """
    source = BOOTSTRAP.read_text(encoding='utf-8')
    begin = source.index('var SDT_TEXT = ')
    outside = source[:begin] + source[source.index('\n};', begin):]
    for tag in LOCALES:
        for name, pattern in messages(tag).items():
            text = visible(pattern).strip()
            # Single words ("Index", "Error") are legitimate elsewhere in the
            # file; a phrase is not, and a phrase is what a second copy loses.
            if len(text.split()) < 3:
                continue
            assert text not in outside, f'message {name!r} is also hardcoded at a call site'
    for start, end in UI_SITES:
        for text in _ui_strings(COMMENT.sub(' ', _site(start, end))):
            assert not looks_like_a_sentence(text), \
                f'{text!r} is prose in the source, not a message id — site anchored at {start!r}'


def test_toolbar_tooltip_never_interpolates_a_raw_phase():
    """The internal phase names ('native-worker-busy', 'low-memory',
    'launch-declined; disable/re-enable to launch') are translated through
    SDT_PHASE_LABELS, never interpolated. The wording of each translation, and
    the guarantee that a blocked sitter stays distinguishable from a healthy
    idle one, are exercised with real state in tests/sdt_sitter_scheduler.mjs."""
    assert '${state.phase}' not in _site('function describeSDTTooltip(state) {', '\n}')
    assert 's.phase}' not in _site(*BUTTON_BLOCK)


def test_toolbar_tooltip_scopes_the_coverage_to_the_libraries_it_covers():
    """Ticket 0710. The button sits in the items toolbar, whose scope is one
    library and one collection; the coverage figure beside it is the whole
    census. The tooltip is the surface that carries the scope, so the figure and
    the libraries it is measured over reach the reader together rather than the
    reader assuming the collection in view."""
    site = _site('function describeSDTTooltip(state) {', '\n}')
    assert 'describeSDTScope(' in site, 'the tooltip states no library scope'
    assert 'describeSDTCoverage(' in site, \
        'the tooltip carries no coverage figure for the scope to qualify'


def test_the_library_scope_is_read_from_zoteros_own_records():
    """A prefix that hardcoded "Ma bibliothèque" would pass any wording grep and
    still lie to every reader of a group library, so the assertion is on the
    provenance of the name, not on its text: the composer reads Zotero's library
    records and holds no library name of its own."""
    site = _site('function describeSDTScope() {', '\n}')
    assert 'Zotero.Libraries' in site, 'the scope is not read from Zotero'
    assert '.name' in site, 'no library record is asked for its name'
    for literal in ('Ma bibliothèque', 'My Library'):
        assert literal not in site, f'{literal!r} is hardcoded rather than read'


def test_one_composer_owns_the_coverage_figure():
    """The toolbar label and the tooltip both show the coverage percentage.
    Composing it twice is how two sites end up rounding or spacing it
    differently; the same lesson describeSDTFile carries for the file name."""
    for start, end in (BUTTON_BLOCK,
                       ('function describeSDTTooltip(state) {', '\n}')):
        assert 'describeSDTCoverage(' in _site(start, end), \
            f'{start!r} composes its own coverage figure'
    percent = _site('function describeSDTCoverage(state) {', '\n}')
    assert "sdtText('index-coverage'" in percent, 'the composer reads no coverage message'
    for tag in LOCALES:
        assert '%' in messages(tag)['index-coverage'], f'{tag}.ftl drops the percent sign'


def test_dialog_title_is_the_index_assistant():
    assert messages()['dialog-title'] == 'Indexing assistant'
    assert 'SDT Pack Sitter' not in _site('doc.title = ', ';')
    for tag in LOCALES:
        assert 'SDT' not in messages(tag)['dialog-title'], f'{tag}.ftl names the internal build'


def test_launch_prompt_title_is_the_index_assistant():
    assert messages()['launch-title'] == 'Indexing assistant — experimental'
    for tag in LOCALES:
        assert 'SDT Pack Sitter' not in messages(tag)['launch-title']


def test_launch_prompt_body_speaks_of_indexing_not_packs():
    english = messages()
    assert 'Index the whole library' in english['launch-question']
    assert 'full-text search index' in english['launch-conditions'], \
        "Zotero's own index must be named apart from the sitter's"
    assert 'packs SDT' not in ' '.join(visible(v) for v in english.values())
    # The four paragraphs are read at the call site in order, so the prompt keeps
    # the shape it had when they were one concatenated literal.
    site = _site('Services.prompt.confirm(', 'if (token !== generation) return;')
    for name in ('launch-question', 'launch-conditions', 'launch-worker', 'launch-disable'):
        assert f"'{name}'" in site, f'{name} is no longer part of the launch prompt'


def test_global_status_line_names_the_unit_it_counts():
    assert messages()['files-indexed-of'].startswith('Files indexed: ')
    assert messages()['files-indexed-count'].startswith('Files indexed: ')
    assert 'Packs' not in ' '.join(visible(v) for v in messages().values())
    site = _site('status.textContent = ', ';')
    assert "sdtText('files-indexed-of'" in site and "sdtText('files-indexed-count'" in site


def test_active_row_leads_with_the_reference_not_the_attachment():
    """Zotero auto-names attachments, so 'Full Text PDF' alone identifies
    nothing. Branch coverage lives in tests/sdt_sitter_scheduler.mjs."""
    site = _site('const activeMessage = ', 'const quietMessage')
    assert "sdtText('active-file'" in site and 'describeSDTActiveFile(' in site
    assert messages()['active-file'].startswith('Indexing: ')
    assert 'Document ${s.active}' not in site
    composer = _site('function describeSDTFile(info, fallback) {', '\n}')
    assert 'parentTitle' in composer, 'the composer still never reads a reference title'


def test_progress_and_error_lines_name_a_file_the_same_way():
    """Two sites name the file being worked on. Composing them separately is how
    the progress line ended up leading with the reference and the error line
    with Zotero's auto-generated attachment title."""
    for start, end in (('function describeSDTActiveFile(state) {', '\n}'),
                       ('describeError: (info, error) =>', 'reportError:')):
        assert 'describeSDTFile(' in _site(start, end), f'{start!r} composes its own label'


def test_failure_summary_line_is_rendered_outside_the_diagnostics():
    source = BOOTSTRAP.read_text(encoding='utf-8')
    assert "'sdt-failures'" in source, 'no failure-summary element is created'
    site = _site("getElementById('sdt-failures').textContent", ';')
    assert 's.failed' in site
    assert 'describeSDTFailures(' in site, 'the banner composes its own plural'
    assert 'files could not be indexed' in messages()['files-failed'][1]


def test_one_composer_owns_each_running_total():
    """Ticket 0696. The two counts a reader is shown now reach three surfaces —
    the tooltip, the dialog's failure banner and the end-of-sweep toast, three
    sites that can only agree by coincidence. Both earlier composers in this file
    were written for the same reason: describeSDTFile after the progress and
    error lines came to name one file two different ways (ticket 0691, round 3),
    describeSDTCoverage before the toolbar strip and the tooltip could round one
    percentage two ways (ticket 0710). Here the shared quantity is a count and
    its plural agreement.

    Ticket 0692 then moved the wording itself into the `.ftl` files, and the two
    requirements are orthogonal: the composer is what stops three SITES drifting,
    the selector is what stops one site being wrong in three LANGUAGES. So each
    composer must own the message id — a `count > 1` here would be a French rule
    in JavaScript, and a literal at a call site would defeat 0696."""
    toast = _site('function announceSDTSweep(before) {', '\n}')
    for composer in ('describeSDTIndexed(', 'describeSDTFailures('):
        assert composer in toast, f'the toast composes its own {composer}'
    # Each composer owns one message id, and the singular lives in the locale.
    for start, message in (('function describeSDTIndexed(count) {', 'files-indexed'),
                           ('function describeSDTFailures(count) {', 'files-failed')):
        site = _site(start, '\n}')
        assert f"sdtText('{message}'" in site, f'{start!r} does not read {message}'
        assert 'count > 1' not in site, f'{start!r} decides plural in JavaScript'
        assert 'file' in visible(messages()[message]), f'{message} lost its singular'
    # An empty failure line at zero: a library with nothing wrong says nothing
    # about failures rather than printing "0 fichier". That stays in JavaScript —
    # it is a decision about showing a line, not about wording one.
    assert "return ''" in _site('function describeSDTFailures(count) {', '\n}')


def test_the_sweep_toast_is_gated_on_work_the_sweep_actually_did():
    """Ticket 0696, and the regression it was rewritten to avoid. The loop
    reschedules on a fixed timer for the life of the plugin, so a toast fired on
    the call rather than on a completed/failed delta would repeat every thirty
    seconds forever once the library is caught up.

    Ordering only, and deliberately so: two review seats showed that a
    source-ordering assertion is blind to what the ordered lines mean — a
    snapshot bound to `sitter.state` by reference satisfies every index
    comparison here and welds the gate shut. The loop was hoisted out of
    initialize() for that reason and is driven whole, against real sweeps and a
    real generation change, in tests/sdt_sitter_scheduler.mjs.
    """
    site = _site('function createSDTSweepLoop(token) {', '\n}')
    snapshot = site.index('sitter.state.completed')
    swept = site.index('await sitter.sweep()')
    announced = site.index('announceSDTSweep(before)')
    assert snapshot < swept, 'the counts are snapshotted after the sweep changed them'
    assert swept < announced, 'the toast is composed before the sweep it reports'
    assert 'sitter.state.failed' in site
    gate = _site('function announceSDTSweep(before) {', '\n}')
    for read in ('before.completed', 'before.failed'):
        assert read in gate, f'the gate never compares {read}'
    assert 'return false' in gate, 'the gate has no silent path'


def test_every_deferred_callback_checks_the_generation_it_was_armed_in():
    """Ticket 0696, review round 1. `sitter` is a module-level binding that
    initialize() reassigns and shutdown() never clears, so `alive` and `sitter`
    can both be truthy and still name a different sitter than the one whose
    counters a suspended sweep snapshotted. The plugin's own launch prompt
    advertises the flow — disable stops admissions, the file in flight finishes —
    and initialize() restores `alive` before its modal confirm, so no click is
    needed. The race itself is staged and driven in
    tests/sdt_sitter_bootstrap.mjs, over a real startup/disable/re-enable, and
    the gate alone in tests/sdt_sitter_scheduler.mjs; what is asserted here is
    the file-wide convention it broke, since a second deferred callback added
    without the check would reintroduce the same class in a new place."""
    loop = _site('function createSDTSweepLoop(token) {', '\n}')
    assert 'if (token === generation) announceSDTSweep(before)' in loop, \
        'the announcement is spent against whatever generation happens to be current'
    assert 'if (alive && token === generation)' in loop, \
        'a stale loop reschedules itself, running two sweeps per interval'
    # The bindings the race walks through must reach a sandbox load, or the
    # regression test cannot stage it and this convention goes back to being
    # asserted by reading. `let` at script top level does not.
    source = BOOTSTRAP.read_text(encoding='utf-8')
    for binding in ('var generation = 0;', 'var timer, pulse, heartbeat, timers;'):
        assert binding in source, f'{binding!r} is out of reach of a driven test'


def test_the_mock_host_carries_the_toast_primitive():
    """`announceSDTSweep` is guarded, so a host without `Zotero.ProgressWindow`
    does not fail — it journals `toast-error` and returns. The mock in
    tests/sdt_sitter_zotero_mock.mjs must therefore carry the primitive, or every
    scenario driven through it records a swallowed error where a toast belongs
    and the one that checks for silence passes because the constructor threw. A
    control run with the primitive removed reddens
    `a disable, a re-enable, and the suspended sweep announces nothing`."""
    mock = (ROOT / 'tests' / 'sdt_sitter_zotero_mock.mjs').read_text(encoding='utf-8')
    assert 'class ProgressWindow' in mock, 'the mock host cannot show a toast'
    assert 'ProgressWindow,' in mock, 'the class is never published on the Zotero stub'
    assert 'toasts,' in mock, 'the harness exposes no toasts to assert on'


def test_the_toast_adds_no_dependency_and_uses_zoteros_own_primitive():
    """Acceptance line 1. This plugin has no build tooling — Zotero's own
    bootstrapped-extension mechanism loads bootstrap.js and bootstrap.js loads
    scheduler.js raw through Services.scriptloader, with nothing between source
    and runtime — so pulling in zotero-plugin-toolkit for a toast would mean
    introducing a bundler for the first time to get the thing Zotero ships."""
    assert 'Zotero.ProgressWindow' in \
        _site('function announceSDTSweep(before) {', '\n}')
    source = BOOTSTRAP.read_text(encoding='utf-8')
    assert 'zotero-plugin-toolkit' not in source
    assert not (SITTER / 'package.json').exists(), 'the sitter acquired a build step'


def test_no_toast_announces_the_start_of_a_sweep():
    """A sweep touches zero, one or many files, so there is no single title to
    name at its start, and the toolbar already spins on the active file and
    pulses through the census. The assertion is on the one construction site:
    exactly one toast exists, and it is the one the wrapper fires afterwards."""
    source = BOOTSTRAP.read_text(encoding='utf-8')
    assert source.count('new Zotero.ProgressWindow') == 1
    assert source.count('announceSDTSweep(') == 2, \
        'one definition and one call site — a second call is a second cadence'


def test_native_fulltext_panel_is_the_text_search_index():
    english = messages()
    assert english['fulltext-title'] == 'Full-text search index'
    assert 'full-text search index' in english['fulltext-body']
    assert 'Index texte natif' not in ' '.join(visible(v) for v in english.values())
    assert 'packs SDT' not in english['fulltext-body']
    assert "sdtText('fulltext-title')" in _site('indexSummary.textContent = ', ';')
    assert "sdtText('fulltext-body')" in _site(
        "getElementById('sdt-fulltext').textContent", ';')


def test_admission_readings_are_recorded_where_they_are_read():
    """The diagnostics layer shows the numbers behind the gate's verdict.

    Read here rather than driven: `blocked()` closes over `initialize`'s Zotero
    handles, and standing those up would test the stub. What a reading of the
    source CAN settle is the placement that decides whether the layer is ever
    populated — a reading recorded on the refusing branch alone is blank exactly
    when the sitter is healthy, which is most of the time it is looked at. So
    each assertion pairs the field with the line that must precede its threshold.
    The rendering of these readings is driven, in tests/sdt_sitter_dialog.mjs.
    """
    site = _site('async function blocked(info) {', '\n  }')
    for field, threshold in (('memoryAvailableBytes', "return 'low-memory'"),
                             ('load', "return 'cpu-busy'"),
                             ('cpus', "return 'cpu-busy'"),
                             ('diskAvailableBytes', "return 'low-disk'")):
        assert 'admission' in site and field in site, field
        assert site.index(field) < site.index(threshold), \
            f'{field} is recorded after the refusal it explains'


def test_scheduler_threads_both_titles_to_the_ui():
    for anchor in ('state.pending = candidates.map', 'state.activeInfo = '):
        site = _site(anchor, ';', SCHEDULER)
        assert 'title:' in site
        assert 'parentTitle:' in site


def test_a_cache_that_cannot_be_written_reaches_a_surface_and_is_cleared():
    """The warning existed as state and was read by nothing.

    `saveCache` set `state.cacheWarning` on a failed write and no render site
    ever mentioned it, so an unwritable data directory was a silence -- the
    data was there, the sentence was not. It belongs in the disclosure rather
    than beside the totals: the cache is derived and disposable, and a failed
    write changes nothing about what is indexed. The clear is the other half; a
    warning that is only ever set survives the condition that raised it and
    ends the session on screen after the disk was emptied.
    """
    site = _site("getElementById('sdt-diagnostics').textContent", '.filter(Boolean)')
    assert 'cacheWarning' in site, 'the cache warning is still rendered nowhere'
    write = _site('await IOUtils.write(cachePath', 'catch (error)')
    assert 'cacheWarning = null' in write, 'a transient cache failure would stick for the session'


def test_the_census_classification_has_exactly_one_owner():
    """Ticket 0699. The four admissible statuses were written out in two files.

    The scheduler's admission whitelist and the dialog's own remaining-work
    tally each carried their own copy of the same four strings, and three other
    statuses (`inspection-error`, `unsupported-pack`, `missing-source`) belonged
    to no list at all -- which is how a library could report zero failures while
    none of those attachments was indexed. `SDT_STATUS_CLASSES` is now the one
    place that decides what each status means; a second copy is what lets a
    status be added to admission and forgotten by the banner.
    """
    scheduler = SCHEDULER.read_text(encoding='utf-8')
    bootstrap = BOOTSTRAP.read_text(encoding='utf-8')
    quartet = "'missing-pack', 'stale-source', 'stale-processor', 'invalid-pack'"
    assert scheduler.count(quartet) == 1, 'the admissible statuses are spelt out twice'
    assert quartet not in bootstrap, 'the dialog keeps a second copy of the whitelist'
    assert 'SDT_STATUS_CLASSES.queued.includes(status)' in scheduler, \
        'admission no longer reads the classification'
    # Every status the classification names, and nothing else, may be produced by
    # the census -- a status the census emits and no class claims is invisible in
    # both user-facing totals, which is the defect this ticket is about.
    classes = _site('var SDT_STATUS_CLASSES = {', '\n};', SCHEDULER)
    classified = set(re.findall(r"'([a-z-]+)'", classes))
    emitted = set(re.findall(r"status: '([a-z-]+)'", scheduler + bootstrap))
    emitted |= set(re.findall(r"result\.status = '([a-z-]+)'", bootstrap))
    emitted |= set(re.findall(r"status = '([a-z-]+)'", scheduler))
    assert emitted, 'the census-status extraction matched nothing'
    assert emitted <= classified, f'unclassified census statuses: {sorted(emitted - classified)}'


def test_every_census_status_is_named_in_words_a_reader_can_read():
    """Ticket 0693, the author's ruling of 2026-09-08: every category named in
    three to five words instead of one.

    The third face of `SDT_STATUS_CLASSES`'s single ownership. The two tests
    above force a new status into a class and force the coverage line to agree
    about which; neither forces anybody to say what it MEANS. Without this, a
    status added to the scheduler renders in the account as its own internal
    key -- `failed-session: 39` -- which is exactly the line the author read on
    his own library and objected to.

    The word count is a real bound, not decoration: one word is the defect
    being repaired, and a clause long enough to wrap turns an account into
    prose. Read out of the classification rather than listed here, so a status
    renamed in `scheduler.js` fails here instead of leaving a dead entry
    behind.
    """
    classes = _site('var SDT_STATUS_CLASSES = {', '\n};', SCHEDULER)
    classified = sorted(set(re.findall(r"'([a-z-]+)'", classes)))
    assert classified, 'the census-status extraction matched nothing'
    # The reading order is the other half, and it was unguarded on the first
    # draft: a red-team control dropped two statuses from `SDT_STATUS_ORDER` and
    # the whole suite stayed green, because the composer's `extra` tail still
    # prints an unordered status. Nothing crashes -- the status merely falls out
    # of the curated order into an arbitrary tail, which is the substance of the
    # ruling rather than a detail of it.
    order = _site('var SDT_STATUS_ORDER = [', '];')
    ordered = re.findall(r"'([a-z-]+)'", order)
    assert len(ordered) == len(set(ordered)), f'a status is ordered twice: {ordered}'
    assert set(ordered) == set(classified), \
        f'the account order and the classification disagree: {sorted(set(ordered) ^ set(classified))}'
    catalogue = messages()
    for status in classified:
        key = f'status-{status}'
        assert key in catalogue, f'census status {status!r} has no reader-facing name'
        words = catalogue[key].split()
        assert 3 <= len(words) <= 5, \
            f'{key} is {len(words)} words, not three to five: {catalogue[key]!r}'
        assert words[0][0].isupper(), f'{key} does not open an account row: {catalogue[key]!r}'
    # And the account's own two lines: a row template that is punctuation, and a
    # total whose wording says it is a total.
    assert '{label}' in catalogue['census-row'] and '{count}' in catalogue['census-row']
    assert '{count}' in catalogue['census-total']


def test_the_coverage_denominator_reads_the_classification():
    """The other half of the same fact, and the one a reader sees as a percentage.

    `emitted <= classified` above forces a new status into *some* class; it
    cannot force the coverage line to agree about which. A second copy of the
    out-of-scope pair here is how 'admitted but not counted' would come back at
    reduced scale -- the coverage denominator silently keeping the old meaning
    of a status the scheduler has since reclassified.
    """
    site = _site('function getSDTCoverage', '\n}')
    # Asserted on the two members, not on the literal `SDT_STATUS_CLASSES.x`:
    # binding the object to a local first is a legitimate shape (it is what the
    # merge with the library-scope work produced, so that an absent
    # classification can make the figure unsayable rather than throw), and an
    # anchor on the dotted spelling would have failed that refactor while the
    # fact it guards was intact.
    assert 'SDT_STATUS_CLASSES' in site, \
        'the coverage line no longer reads the census classification at all'
    assert '.outOfScope' in site, \
        'the coverage denominator keeps its own copy of the out-of-scope statuses'
    assert '.indexed' in site, \
        'the coverage numerator keeps its own copy of what "indexed" means'
    for status in ("'excluded'", "'unsupported'", "'current'"):
        assert status not in site, f'{status} is spelt out a second time'


def test_the_session_clause_names_only_session_counters():
    """`completed` accumulates over the session; `failed` is read off the last
    census and includes attachments this session never touched. One "this
    session" governing both halves would call the second something it is not.

    Two messages, and the assertion is that they stay two: the risk a translator
    runs is folding them into one line, which reads better and is false. So the
    session clause must appear in exactly one of the pair, in every locale --
    and both must be rendered somewhere a reader reaches.

    Ticket 0693 moved the census half. `diagnostics-failed` -- "Could not be
    indexed (last census)" -- was the aggregate the author objected to on
    2026-09-08: it added files merely absent from this disk to real extraction
    failures under one label. It is gone from the account, where every one of
    its constituents now holds a named row of its own, and the census-derived
    total a reader still meets is the layer-1 banner `files-failed`. So the
    pair this test guards is `diagnostics-completed` against that banner. The
    invariant did not change -- one "this session", governing only the counter
    that accumulates over one -- only which two lines carry it."""
    for tag in LOCALES:
        catalogue = messages(tag)
        session, census = catalogue['diagnostics-completed'], catalogue['files-failed']
        assert session not in census, f'{tag}.ftl: the two totals share one sentence'
        assert '{count}' in session and all('{count}' in form for form in census)
    english = messages()
    assert 'this session' in english['diagnostics-completed']
    assert not any('session' in form for form in english['files-failed']), \
        'a census-derived total is rendered under a session clause'
    # And the aggregate that conflated two facts is not merely reworded.
    assert 'diagnostics-failed' not in english, \
        'the conflating "could not be indexed (last census)" aggregate is back'
    site = _site("getElementById('sdt-diagnostics').textContent", '.filter(Boolean)')
    assert "sdtText('diagnostics-completed', { count: s.completed })" in site
    assert 'describeSDTCensusAccount(s.counts)' in site, \
        'the census block no longer renders through the account composer'
    assert "sdtText('diagnostics-failed'" not in BOOTSTRAP.read_text(encoding='utf-8')
