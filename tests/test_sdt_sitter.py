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
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / 'bench' / 'sdt-sitter' / 'bootstrap.js'
SCHEDULER = ROOT / 'bench' / 'sdt-sitter' / 'scheduler.js'

BUTTON_BLOCK = ('for (const button of buttons) {', 'for (const dialog of dialogs) {')


def _site(start: str, end: str, path: Path | None = None) -> str:
    """Return the source between two anchors, so an assertion is scoped to one
    template site rather than to the whole file."""
    source = (path or BOOTSTRAP).read_text(encoding='utf-8')
    assert start in source, f'anchor absent: {start!r}'
    begin = source.index(start)
    assert end in source[begin:], f'closing anchor absent after {start!r}: {end!r}'
    return source[begin:source.index(end, begin)]


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


def test_toolbar_tooltip_counts_documents_not_packs():
    block = _site(*BUTTON_BLOCK)
    assert 'documents indexés' in block
    assert 'packs créés' not in block


def test_toolbar_tooltip_never_interpolates_a_raw_phase():
    """The phase vocabulary ('native-worker-busy', 'low-memory',
    'launch-declined; disable/re-enable to launch') has no approved
    translation; it belongs to the diagnostics disclosure only."""
    tooltip = _site("button.setAttribute('tooltiptext'", ');')
    assert 's.phase}' not in tooltip, 'a raw internal phase name still reaches the tooltip'


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


def test_global_status_line_counts_indexes():
    site = _site('status.textContent = ', ';')
    assert 'Index à jour : ' in site
    assert 'Packs à jour' not in site


def test_active_document_row_shows_the_document_title():
    source = BOOTSTRAP.read_text(encoding='utf-8')
    site = _site('const documentMessage = ', 'const quietMessage')
    assert 'Indexation : ' in site
    assert 'Document ${s.active}' not in site
    assert 'activeInfo?.title' in source, 'the active row still never reads a title'


def test_failure_summary_line_is_rendered_outside_the_diagnostics():
    source = BOOTSTRAP.read_text(encoding='utf-8')
    assert "'sdt-failures'" in source, 'no failure-summary element is created'
    site = _site("getElementById('sdt-failures').textContent", ';')
    assert 's.failed' in site
    assert 'n’ont pas pu être indexés' in site


def test_native_fulltext_panel_is_the_text_search_index():
    summary = _site('indexSummary.textContent = ', ';')
    assert 'Index de recherche textuelle' in summary
    assert 'Index texte natif' not in summary
    body = _site("getElementById('sdt-fulltext').textContent", ';')
    assert 'Index de recherche textuelle' in body
    assert 'Index texte natif' not in body
    assert 'packs SDT' not in body


def test_scheduler_threads_the_document_title_to_the_ui():
    pending = _site('state.pending = candidates.map', ';', SCHEDULER)
    assert 'title' in pending
    active = _site('state.activeInfo = ', ';', SCHEDULER)
    assert 'title' in active
