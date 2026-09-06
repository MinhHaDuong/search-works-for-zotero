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
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'bench') not in sys.path:
    sys.path.insert(0, str(ROOT / 'bench'))

from sdt_sitter_install import ADDON_ID, install, read_addon_record  # noqa: E402

SITTER = ROOT / 'bench' / 'sdt-sitter'
BOOTSTRAP = SITTER / 'bootstrap.js'
SCHEDULER = SITTER / 'scheduler.js'

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
    ('function formatSDTBytes(bytes) {', '\n}'),
    ('function formatSDTAge(ms) {', '\n}'),
    ('function describeSDTEnvironment() {', '\n}'),
    ('function describeSDTAdmission() {', '\n}'),
    ('function describeSDTJournalTail(limit = 50) {', '\n}'),
    ('function composeSDTJournalReport() {', '\n}'),
    ('function buildSDTDiagnostics(doc, element) {', '\n}'),
    ("getElementById('sdt-observations').textContent", ';'),
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
def test_sdt_sitter_bootstrap_syntax():
    subprocess.run(['node', '--check', 'bench/sdt-sitter/bootstrap.js'], cwd=ROOT,
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
        assert update_url.endswith("/bench/sdt-sitter/update.json"), update_url
        assert list(update["addons"]) == [zotero["id"]]


@pytest.mark.integration
def test_startup_self_check_is_emitted_before_anything_else_can_fail():
    """Driven, not read. A log line asserted by inspection is a log line nobody ran."""
    subprocess.run(['node', 'tests/sdt_sitter_startup.mjs'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=30)


def test_toolbar_button_label_reads_index():
    block = _site(*BUTTON_BLOCK)
    assert 'Index${coverageLabel}' in block
    assert 'SDT${coverageLabel}' not in block


def test_toolbar_tooltip_counts_files_not_packs():
    assert 'describeSDTIndexed(' in _site('function describeSDTTooltip(state) {', '\n}')
    assert 'fichiers indexés' in _site('function describeSDTIndexed(count) {', '\n}')
    assert 'packs créés' not in BOOTSTRAP.read_text(encoding='utf-8')


def test_no_user_facing_string_says_document():
    """The unit of work is one attachment, and every count must name it. A whole-
    file grep cannot express this: 'document' is legitimate in element ids and
    helper names, and illegitimate only in the text a reader is shown."""
    for start, end in UI_SITES:
        for text in _ui_strings(_site(start, end)):
            for word in BANNED_IN_UI:
                assert word not in text.lower(), \
                    f'{word!r} in {text!r} — site anchored at {start!r}'


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
    assert '%' in percent, 'the composer does not produce a percentage'


def test_dialog_title_is_the_index_assistant():
    site = _site('doc.title = ', ';')
    assert 'Assistant d’indexation' in site
    assert 'SDT Pack Sitter' not in site


def test_launch_prompt_title_is_the_index_assistant():
    site = _site('Services.prompt.confirm(', '\n')
    assert 'Assistant d’indexation — expérimental' in site
    assert 'SDT Pack Sitter' not in site


def test_launch_prompt_body_speaks_of_indexing_not_packs():
    site = _site('Services.prompt.confirm(', 'if (token !== generation) return;')
    assert 'Indexer toute la bibliothèque' in site
    assert 'packs SDT' not in site
    assert 'index de recherche textuelle' in site, \
        "Zotero's own index must be named apart from the sitter's"


def test_global_status_line_names_the_unit_it_counts():
    site = _site('status.textContent = ', ';')
    assert 'Fichiers indexés : ' in site
    assert 'Packs à jour' not in site


def test_active_row_leads_with_the_reference_not_the_attachment():
    """Zotero auto-names attachments, so 'Full Text PDF' alone identifies
    nothing. Branch coverage lives in tests/sdt_sitter_scheduler.mjs."""
    site = _site('const activeMessage = ', 'const quietMessage')
    assert 'Indexation : ' in site
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
    assert 'fichiers n’ont pas pu être indexés' in \
        _site('function describeSDTFailures(count) {', '\n}')


def test_one_composer_owns_each_running_total():
    """Ticket 0696. The two counts a reader is shown now reach three surfaces —
    the tooltip, the dialog's failure banner and the end-of-sweep toast. Three
    compositions of one plural is how the progress and error lines drifted apart
    in ticket 0691 round 3, and how describeSDTCoverage came to exist."""
    toast = _site('function announceSDTSweep(before) {', '\n}')
    for composer in ('describeSDTIndexed(', 'describeSDTFailures('):
        assert composer in toast, f'the toast composes its own {composer}'
    # And the composers hold the wording, so a rename cannot leave a literal
    # behind at one of the call sites.
    for start, wording in (('function describeSDTIndexed(count) {', 'fichier indexé'),
                           ('function describeSDTFailures(count) {',
                            'fichier n’a pas pu être indexé')):
        assert wording in _site(start, '\n}'), f'{start!r} lost its singular'
    # An empty failure line at zero: a library with nothing wrong says nothing
    # about failures rather than printing "0 fichier".
    assert "return ''" in _site('function describeSDTFailures(count) {', '\n}')


def test_the_sweep_toast_is_gated_on_work_the_sweep_actually_did():
    """Ticket 0696, and the regression it was rewritten to avoid. The wrapper
    reschedules on a fixed timer for the life of the plugin, so a toast fired on
    the call rather than on a completed/failed delta would repeat every thirty
    seconds forever once the library is caught up.

    Read here rather than driven: the wrapper closes over `initialize`'s
    generation token and its timer handles, so reaching it would mean standing up
    the whole of initialize() and testing the stub. What the gate then does with
    the snapshot is driven, with real sweeps, in tests/sdt_sitter_scheduler.mjs.
    """
    site = _site('const sweep = async () => {', 'pulse = timers.setInterval')
    snapshot = site.index('sitter.state.completed')
    swept = site.index('await sitter.sweep()')
    announced = site.index('announceSDTSweep(before)')
    assert snapshot < swept, 'the counts are snapshotted after the sweep changed them'
    assert swept < announced, 'the toast is composed before the sweep it reports'
    gate = _site('function announceSDTSweep(before) {', '\n}')
    for read in ('before.completed', 'before.failed'):
        assert read in gate, f'the gate never compares {read}'
    assert 'return false' in gate, 'the gate has no silent path'
    assert 'sitter.state.failed' in site


def test_the_toast_adds_no_dependency_and_uses_zoteros_own_primitive():
    """Acceptance line 1. This plugin has no build tooling — bootstrap.js and
    scheduler.js load raw through Services.scriptloader — so pulling in
    zotero-plugin-toolkit for a toast would mean introducing a bundler for the
    first time to get the thing Zotero already ships."""
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
    summary = _site('indexSummary.textContent = ', ';')
    assert 'Index de recherche textuelle' in summary
    assert 'Index texte natif' not in summary
    body = _site("getElementById('sdt-fulltext').textContent", ';')
    assert 'Index de recherche textuelle' in body
    assert 'Index texte natif' not in body
    assert 'packs SDT' not in body


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
    census and includes attachments this session never touched. One 'cette
    session' governing both halves would call the second something it is not."""
    lines = [line for line in BOOTSTRAP.read_text(encoding='utf-8').splitlines()
             if 'cette session' in line]
    assert lines, "the diagnostics no longer name the session's own counter"
    for line in lines:
        assert 's.failed' not in line, \
            'a census-derived total is rendered under a "cette session" clause'
