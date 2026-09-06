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
    return subprocess.run([sys.executable, str(REPO / "bench" / "sdt_sitter_install.py"),
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

    for document in ("[]", '"text"', "{ truncated"):
        wrong = tmp_path / f"wrong-{abs(hash(document))}"
        wrong.mkdir()
        (wrong / "extensions.json").write_text(document, encoding="utf-8")
        result = cli("verify", "--profile", str(wrong))
        assert result.returncode == 3, f"{document}: {result.stdout}{result.stderr}"

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
    subprocess.run(['node', 'tests/sdt_sitter_startup.mjs'], cwd=REPO,
                   check=True, capture_output=True, text=True, timeout=30)
