"""Instrumentation refuses changed installed-source anchors instead of guessing."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'verification/probes'))

from sdt_phase_probe import instrument  # noqa: E402


def anchors():
    path = Path(__file__).resolve().parents[1] / 'bench/results/sdt-palgrave-phases-2026-09-05/pages-256.json'
    return json.loads(path.read_text())['provenance']['anchors']


def test_missing_source_anchor_is_rejected():
    with pytest.raises(ValueError, match='not unique'):
        instrument('')


def test_duplicate_source_anchor_is_rejected():
    original = '\n'.join(anchors())
    with pytest.raises(ValueError, match='not unique'):
        instrument(original + '\n' + anchors()[0])


def test_phase_markers_preserve_original_statements():
    original = '\n'.join(anchors())
    patched, used = instrument(original)
    assert used == anchors()
    assert "__sdtProbe('citations:start')" in patched
    assert "__sdtProbe('citations:end')" in patched
    assert "__sdtProbe('pack:start'" in patched
    assert "__sdtProbe('pack:end'" in patched
    for statement in ('getCitationRefs(structure, referenceIndex, annotLinkRefs, structureIndex)',
                      'packStructuredDocumentText(structure, {'):
        assert patched.count(statement) == original.count(statement)
