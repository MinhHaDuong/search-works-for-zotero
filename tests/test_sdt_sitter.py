"""Exercise the production admission loop with deterministic asynchronous hosts.

Also the sitter's *installation* discipline (ticket 0688), which is a different
question from whether its scheduler is correct: an add-on that is never
persistently installed, or whose manifest names a host nothing can resolve,
disappears from the plugin list without any of the scheduler's logic being
wrong. The three concerns guarded here are the ones that leave no trace when
they fail — a profile read that silently says "absent", a placeholder URL, and
a startup that leaves no trace of which build was running.

The version-bump guard's own suite is `tests/test_check_sitter_version.py`,
where the repository's guard-completeness convention puts it.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "bench") not in sys.path:
    sys.path.insert(0, str(REPO / "bench"))

from sdt_sitter_install import ADDON_ID, install, read_addon_record  # noqa: E402

SITTER = REPO / "bench" / "sdt-sitter"

#: A second add-on, so "present" can be told from "something is present".
OTHER_ID = "zotero-better-bibtex@iris-advies.com"


def write_extensions(profile: Path, addons: list[dict]) -> Path:
    profile.mkdir(parents=True, exist_ok=True)
    path = profile / "extensions.json"
    path.write_text(json.dumps({"schemaVersion": 35, "addons": addons}), encoding="utf-8")
    return path


def sitter_entry(**overrides) -> dict:
    entry = {"id": ADDON_ID, "version": "2.3.0", "active": True,
             "location": "app-profile", "type": "extension"}
    entry.update(overrides)
    return entry


def other_entry() -> dict:
    """Same shape, same location, same version — everything but the id."""
    return {"id": OTHER_ID, "version": "2.3.0", "active": True,
            "location": "app-profile", "type": "extension"}


@pytest.mark.integration
def test_sdt_sitter_scheduler():
    subprocess.run(['node', 'tests/sdt_sitter_scheduler.mjs'], cwd=REPO,
                   check=True, capture_output=True, text=True, timeout=30)


@pytest.mark.integration
def test_sdt_sitter_bootstrap_syntax():
    subprocess.run(['node', '--check', 'bench/sdt-sitter/bootstrap.js'], cwd=REPO,
                   check=True, capture_output=True, text=True, timeout=30)


def test_read_addon_record_discriminates_present_absent_and_someone_else(tmp_path):
    """Three arms, because two would pass on a check that matches the wrong field.

    A positive and a negative arm alone are satisfied by a reader keyed on
    `location` or `version` — both of which the third arm's entry also carries.
    Only an id-keyed read can tell "our add-on is installed" from "an add-on is
    installed", and that is the sentence the verify target prints.
    """
    installed = tmp_path / "installed"
    write_extensions(installed, [other_entry(), sitter_entry()])
    record = read_addon_record(installed)
    assert record == {"read": True, "present": True, "version": "2.3.0",
                      "active": True, "location": "app-profile"}

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
    subprocess.run(['node', 'tests/sdt_sitter_startup.mjs'], cwd=REPO,
                   check=True, capture_output=True, text=True, timeout=30)
