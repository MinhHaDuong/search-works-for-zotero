"""Exercise the admission loop and the user-facing vocabulary of the sitter UI.

The vocabulary tests are deliberately *not* a whole-file "SDT does not appear"
grep. Such a grep both false-positives on the internal identifiers that must
survive (``createSDTSitter``, ``Zotero.SDT.ensure``, the cache filenames) and
false-negatives on the defects that carry no literal ``SDT`` at all -- the
toolbar tooltip used to interpolate raw internal phase names, and the active
document row used to print a bare item id. Each test below is anchored to one
template site and asserts both the new wording and the absence of the specific
jargon it replaced.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / 'bench' / 'sdt-sitter' / 'bootstrap.js'
SCHEDULER = ROOT / 'bench' / 'sdt-sitter' / 'scheduler.js'

BUTTON_BLOCK = ('for (const button of buttons) {', 'for (const dialog of dialogs) {')

# Every site that produces text a reader sees. The ban below is checked against
# each one, rather than against the whole file, so internal element ids
# ('sdt-document-status') and helper names (formatDocumentDuration) stay legal.
UI_SITES = (
    ('function describeSDTTooltip(state) {', '\n}'),
    ('function describeSDTActiveFile(state) {', '\n}'),
    ('var SDT_PHASE_LABELS = {', '};'),
    ('status.textContent = ', ';'),
    ('const activeMessage = ', 'const quietMessage'),
    ("getElementById('sdt-failures').textContent", ';'),
    ('doc.title = ', ';'),
    ("section('sdt-global-section'", ']);'),
    ("section('sdt-document-section'", ']);'),
    ('indexSummary.textContent = ', ';'),
    ("getElementById('sdt-fulltext').textContent", ';'),
    ('Services.prompt.confirm(', 'if (token !== generation) return;'),
    ('describeError: (info, error) => {', '},'),
)

# "document" is the trap: Zotero's own French UI renders *item* as "document",
# so it reads as the reference, which is the opposite of the attachment this
# add-on actually indexes. "élément" and "pièce jointe" are the same confusion
# from the other side.
BANNED_IN_UI = ('document', 'élément', 'pièce jointe', 'pack')


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


def test_sdt_sitter_scheduler():
    subprocess.run(['node', 'tests/sdt_sitter_scheduler.mjs'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=30)


def test_sdt_sitter_bootstrap_syntax():
    subprocess.run(['node', '--check', 'bench/sdt-sitter/bootstrap.js'], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=30)


def test_toolbar_button_label_reads_index():
    block = _site(*BUTTON_BLOCK)
    assert 'Index${coverageLabel}' in block
    assert 'SDT${coverageLabel}' not in block


def test_toolbar_tooltip_counts_files_not_packs():
    site = _site('function describeSDTTooltip(state) {', '\n}')
    assert 'fichiers indexés' in site
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
    composer = _site('function describeSDTActiveFile(state) {', '\n}')
    assert 'parentTitle' in composer, 'the active row still never reads a reference title'


def test_failure_summary_line_is_rendered_outside_the_diagnostics():
    source = BOOTSTRAP.read_text(encoding='utf-8')
    assert "'sdt-failures'" in source, 'no failure-summary element is created'
    site = _site("getElementById('sdt-failures').textContent", ';')
    assert 's.failed' in site
    assert 'fichiers n’ont pas pu être indexés' in site


def test_native_fulltext_panel_is_the_text_search_index():
    summary = _site('indexSummary.textContent = ', ';')
    assert 'Index de recherche textuelle' in summary
    assert 'Index texte natif' not in summary
    body = _site("getElementById('sdt-fulltext').textContent", ';')
    assert 'Index de recherche textuelle' in body
    assert 'Index texte natif' not in body
    assert 'packs SDT' not in body


def test_scheduler_threads_both_titles_to_the_ui():
    for anchor in ('state.pending = candidates.map', 'state.activeInfo = '):
        site = _site(anchor, ';', SCHEDULER)
        assert 'title:' in site
        assert 'parentTitle:' in site
