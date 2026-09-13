"""The parts of the real-Zotero smoke test that do not need a Zotero.

Ticket 0784. The smoke test's own value is only provable against a live
process (see the ticket's log for the red/green pair that proves it), which
this suite cannot reproduce in `make check` -- there is no Zotero binary and no
display on the machine that gate has to stay green on. What IS checkable here,
fast and without a Zotero, is the part most likely to silently rot: the fixture
generator (does it still write three valid, linkable attachments), and the
setup helpers that refuse to reuse throwaway state.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

from fixtures.smoke_library import write_smoke_library  # noqa: E402
from sitter_smoke_test import (  # noqa: E402
    NotRunError,
    find_zotero_bin,
    setup_profile,
)


def test_write_smoke_library_writes_three_linkable_items(tmp_path):
    ris_path = write_smoke_library(tmp_path)
    text = ris_path.read_text(encoding="utf-8")
    linked = [line.split("-", 1)[1].strip()
             for line in text.splitlines() if line.startswith("L1  -")]
    assert len(linked) == 3
    for relative in linked:
        attachment = ris_path.parent / relative
        assert attachment.exists(), attachment
        # Genuinely a PDF, not merely named one -- the same discipline
        # `bench/fixtures/make_attachment_fixtures.py`'s own docstring states:
        # a fixture that only looks like its format measures nothing.
        assert attachment.read_bytes().startswith(b"%PDF-")


def test_write_smoke_library_refuses_to_overwrite(tmp_path):
    write_smoke_library(tmp_path)
    with pytest.raises(FileExistsError):
        write_smoke_library(tmp_path)


def test_find_zotero_bin_refuses_a_missing_launcher(tmp_path):
    with pytest.raises(NotRunError):
        find_zotero_bin(tmp_path / "no-such-zotero")


def test_find_zotero_bin_refuses_a_launcher_with_no_binary_beside_it(tmp_path):
    launcher = tmp_path / "zotero"
    launcher.write_text("#!/bin/sh\n")
    with pytest.raises(NotRunError):
        find_zotero_bin(launcher)


def test_setup_profile_pins_the_data_directory_and_its_gating_pref(tmp_path):
    """Ticket 0782's actual mechanism, established while first running this
    script against a real Zotero: `dataDirectory.js` only honours the `dataDir`
    pref when `useDataDir` is ALSO true. `bench/sitter_volume_experiment.py`'s
    `SEED_PREFS`, reused here, sets `dataDir` alone -- so this asserts the
    companion pref this file adds on top is still there, since its absence is
    exactly what let a smoke run open the real default data directory."""
    profile, data_dir = setup_profile(tmp_path, port=6100)
    prefs = (profile / "prefs.js").read_text(encoding="utf-8")
    assert f'"extensions.zotero.dataDir", "{data_dir}"' in prefs
    assert 'user_pref("extensions.zotero.useDataDir", true);' in prefs
