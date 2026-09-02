"""The Beaver adapter's declaration is honest about what it can and cannot do.

Ticket 0586. This target is the roster's first in-process plugin, and the defect
classes below are the ones that difference creates. Each turns one of the four
states into a lie, and none of them needs the target, the host application or a
display:

1. **A sweep that cannot see a file.** A declared derived-state root here is
   partly a set of FILES — a sidecar database beside the host's own — because
   the target owns no directory in the host's data directory. `os.walk` yields
   nothing for a regular file, so before the fix this suite pins, the uninstall
   survivor check reported zero survivors while three files sat on disk. A
   green produced by a sweep that never looked is the failure this whole layer
   exists to catch, so it is pinned here with a fixture rather than trusted.
2. **A declaration and a method that disagree.** Four verbs are declared absent
   and four must raise. Let them drift and a verb the adapter refuses is scored
   as a failure of the target, or a verb declared absent quietly answers.
3. **A reason that collapses two findings into one cell.** `unsupported` now
   carries a reason, and the reason is the lane's product: this target's `pause`
   is absent because it has background work with no single control, which is the
   architectural OPPOSITE of the second target's, absent because it has no
   background work at all. A reason that stopped saying which would be invisible.
4. **A harness preference that becomes a target option.** Five preferences are
   written into the host's profile so a sideloaded artifact loads without a GUI
   click and two instances can coexist. One target preference added to that list
   would silently make every verdict a verdict about a configuration no ordinary
   user runs, and nothing else would notice.
5. **A pin that pins nothing.** The adapter names a release and a digest; if it
   then ran whatever file it was handed, the revision in the artifact would be
   decoration.
6. **A sandbox that is not one.** The residue sweep reads this declaration and
   the uninstall verb deletes the artifact the adapter installed. Both are safe
   only while every path is inside a harness-owned arena.

Every test here runs offline, starts no process and writes only under tmp_path.
"""

import importlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

interface = importlib.import_module("bench.acceptance.interface")
assertions = importlib.import_module("bench.acceptance.assertions")
adapter = importlib.import_module("bench.acceptance.adapters.beaver")


@pytest.fixture
def artifact(tmp_path, monkeypatch):
    """A stand-in for the pinned release artifact, with the pin pointed at it.

    The real artifact is 6.8 MB and is not committed; what these tests need is a
    file whose digest matches whatever the module says it expects. Patching the
    two constants rather than skipping the check keeps the digest guard itself
    exercised — `test_an_artifact_that_is_not_the_pinned_one_is_refused` uses
    the same fixture and hands the constructor a different file.
    """
    import hashlib

    path = tmp_path / "artifact.xpi"
    payload = b"not the real add-on, only a file with a known digest\n"
    path.write_bytes(payload)
    monkeypatch.setattr(adapter, "ARTIFACT_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(adapter, "ARTIFACT_BYTES", len(payload))
    return path


def build(tmp_path, artifact, **kw):
    """An adapter on a harness-owned arena and a host binary that need not exist."""
    return adapter.Beaver(
        tmp_path / "arena", zotero=tmp_path / "nonexistent-host-binary",
        xpi=artifact, dwell=0.0, startup_timeout=0.2, **kw,
    )


# --- 1. the declaration reads with nothing installed ------------------------


def test_the_declaration_reads_without_the_target_the_host_or_a_display(tmp_path):
    """The cheapest contract check must not need a desktop application present.

    `declaration()` is a free function for this reason. This target's transport
    starts a graphical host process; if obtaining the declaration ever reached
    for it, a contract check on a headless machine would fail for a reason that
    has nothing to do with the contract.
    """
    declared = adapter.declaration(tmp_path / "profile", tmp_path / "data",
                                   tmp_path / "home")
    assert isinstance(declared, interface.Declaration)
    assert declared.name == "jlegewie/beaver-zotero"
    assert declared.derived_state_roots, "a target that writes nothing is a claim"


def test_the_revision_pins_the_commit_the_tag_and_the_artifact_digest(tmp_path):
    """A release name alone is not a pin: releases are re-cut and tags move.

    The artifact is what is actually installed, so its digest belongs in the
    revision string beside the commit — the second target needed a whole lock
    file for the same reason, and this one does not only because it vendors its
    runtime and downloads no model.
    """
    assert len(adapter.COMMIT) == 40 and all(c in "0123456789abcdef" for c in adapter.COMMIT)
    assert len(adapter.ARTIFACT_SHA256) == 64
    revision = adapter.declaration(tmp_path / "p", tmp_path / "d", tmp_path / "h").revision
    for pin in (adapter.COMMIT, adapter.TAG, adapter.ARTIFACT_SHA256, str(adapter.ARTIFACT_BYTES)):
        assert pin in revision, f"{pin} is not in the revision string"


def test_the_revision_names_the_backend_the_shipped_build_talks_to(tmp_path):
    """R10's verdict is unreadable without knowing what the build was aimed at.

    The endpoints are compiled into the artifact, so no configuration file in
    the repository records them and a reader of the artifact cannot recover
    them. They are read out of the shipped bundle and carried in the
    declaration.
    """
    declared = adapter.declaration(tmp_path / "p", tmp_path / "d", tmp_path / "h")
    for host in adapter.BACKEND_HOSTS:
        assert host in declared.revision or host in declared.default_configuration


# --- 2. the sandbox ---------------------------------------------------------


def test_every_derived_state_root_is_inside_the_arena(tmp_path):
    """A root outside the arena aims the residue sweep at real state.

    Two of the seven roots live in the host's data directory and one in its
    profile directory. Either written with a real path instead of the arena's
    would still look right in a review, and the sweep would then be reading a
    library.
    """
    arena = tmp_path / "arena"
    declared = adapter.declaration(arena / "profile", arena / "data", arena / "home")
    for root in declared.derived_state_roots:
        assert arena in root.parents, f"{root} escapes the arena"
    for path, _why in declared.not_derived_state:
        assert path == arena / path.name or arena in path.parents, f"{path} escapes"


def test_construction_on_the_operators_own_home_is_refused(tmp_path, artifact):
    """The destructive reading, blocked rather than documented.

    With the operator's home as the arena, the sandbox profile and data
    directory are the operator's own, the sweep reads them, and the uninstall
    verb deletes inside them.
    """
    with pytest.raises(ValueError, match="HOME"):
        adapter.Beaver(Path.home(), zotero=Path("/nonexistent"), xpi=artifact)


def test_construction_on_the_hosts_own_data_directory_is_refused(tmp_path, artifact,
                                                                 monkeypatch):
    """The second destructive reading: a real library as the arena's data dir.

    Refusing only the home directory would leave the commoner mistake open —
    pointing the arena at the place the host actually keeps its library.
    """
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    with pytest.raises(ValueError, match="data directory"):
        adapter.Beaver(tmp_path, zotero=Path("/nonexistent"), xpi=artifact)


def test_an_artifact_that_is_not_the_pinned_one_is_refused(tmp_path, artifact):
    """The pin is checked, not merely stated.

    An adapter that names a release in its declaration and runs whatever file
    the caller passed has pinned a sentence. The refusal names both digests so
    the operator can see which build they had.
    """
    other = tmp_path / "other.xpi"
    other.write_bytes(b"a different file entirely\n")
    with pytest.raises(SystemExit, match="not the pinned one"):
        adapter.Beaver(tmp_path / "arena", zotero=Path("/nonexistent"), xpi=other)


def test_the_build_factory_refuses_to_default_the_host_or_the_artifact(tmp_path):
    """A guessed host binary measures whichever build the machine happens to have.

    This target is a plugin, so the host application is half of what is under
    test. Neither input is defaulted, and the messages say why.
    """
    with pytest.raises(SystemExit, match="host application's binary"):
        adapter.build("beaver", tmp_path, xpi="/x")
    with pytest.raises(SystemExit, match="pinned artifact"):
        adapter.build("beaver", tmp_path, zotero="/x")


# --- 3. the declaration and the methods agree -------------------------------


def test_the_four_absent_verbs_raise_rather_than_return(tmp_path, artifact):
    """A declared-absent verb that returns a value is a `not-offered` nobody sees."""
    target = build(tmp_path, artifact)
    assert set(target.declaration.unsupported) == {"query", "status", "pause", "resume"}
    for verb in sorted(target.declaration.unsupported):
        with pytest.raises(interface.UnsupportedVerb):
            (target.query("q", "meaning", 5) if verb == "query"
             else getattr(target, verb)())


def test_every_offered_verb_exists_and_no_offered_verb_declares_itself_absent(
        tmp_path, artifact):
    """The other half of the drift: an offered verb must be callable."""
    target = build(tmp_path, artifact)
    absent = {"query", "status", "pause", "resume"}
    for verb in interface.VERBS:
        assert callable(getattr(target, verb)), f"{verb} is not implemented"
        assert target.declaration.offers(verb) is (verb not in absent)


def test_the_adapter_satisfies_the_contracts_own_protocol(tmp_path, artifact):
    """`running` is the lifecycle the contract makes a context manager, not a verb."""
    assert isinstance(build(tmp_path, artifact), interface.Target)


# --- 4. the reasons carry the findings, not just the absence ----------------


def test_pause_is_absent_for_the_opposite_reason_to_the_second_targets(tmp_path):
    """The reason field's whole purpose, on the case that motivated it.

    The second target's `pause` is absent because it has no background work.
    This one's is absent because it has TWO background workers and no single
    durable control over them. A reason that stopped distinguishing those would
    put opposite findings back in one cell, and nothing downstream could tell.
    """
    declared = adapter.declaration(tmp_path / "p", tmp_path / "d", tmp_path / "h")
    why = declared.unsupported["pause"]
    assert "backgroundExtractorEnabled" in why, "the control that DOES exist is unnamed"
    assert "no pause at all" in why, "the worker with no control is unnamed"
    assert "Rejected alternative" in why, "the alternative that was weighed is unrecorded"
    assert "background work here to resume" in declared.unsupported["resume"]


def test_query_is_absent_for_three_stated_reasons_and_names_what_was_rejected(tmp_path):
    """Three surfaces, three different closures, and an opt-in that was refused.

    Collapsing this to "no query surface" would read like the second target's
    case, where none exists. Here they exist: one is behind a preference, one is
    compiled out of the shipped build, and one carries no query. The rejected
    alternative — turning the preference on — is the one a reader will think of,
    so it is answered in the declaration rather than in a report.
    """
    declared = adapter.declaration(tmp_path / "p", tmp_path / "d", tmp_path / "h")
    why = declared.unsupported["query"]
    assert "Rejected alternative" in why
    assert "non-default option" in why
    for surface in ("mcp", "production", "protocol handler"):
        assert surface in (why + declared.query_transport).lower(), surface


def test_status_records_the_internal_read_it_refused(tmp_path):
    """Reading the target's private schema is the tempting workaround here.

    Any user can open the file, which is what makes the refusal worth writing
    down: the objection is not access, it is that a private schema is not a
    surface the target offers and the model name in it is a client-side label
    for vectors computed elsewhere.
    """
    why = adapter.declaration(tmp_path / "p", tmp_path / "d", tmp_path / "h")\
        .unsupported["status"]
    assert "Rejected alternative" in why
    assert "workaround" in why
    assert "client-side label" in why


def test_every_absent_verb_carries_a_reason_long_enough_to_be_one(tmp_path):
    """`Declaration` refuses a blank reason; a two-word one would pass it.

    The field replaced an undifferentiated cell, and a reason nobody could act
    on rebuilds that cell with a longer type.
    """
    declared = adapter.declaration(tmp_path / "p", tmp_path / "d", tmp_path / "h")
    for verb, why in declared.unsupported.items():
        assert len(why.split()) >= 12, f"{verb}'s reason is too short to be one"


# --- 5. the harness's own configuration stays the harness's -----------------


def test_no_harness_preference_is_a_target_preference(tmp_path, artifact):
    """The line between harness setup and a non-default option, made mechanical.

    Every preference this adapter writes is one of the host's. A preference
    under the target's own prefix appearing here would change the configuration
    under test without changing anything a reader looks at.
    """
    target = build(tmp_path, artifact)
    written = target._write_harness_prefs()
    assert len(written) == len(adapter.HARNESS_PREFS)
    for line in written:
        assert ".beaver." not in line, f"a target preference in harness setup: {line}"
    assert any(f", {target.port})" in line for line in written), (
        "the port move must reach the profile; it is declared because on a plugin "
        "target it also relocates any endpoint the plugin registers"
    )


def test_configure_applies_nothing(tmp_path, artifact):
    """The configuration under test is the artifact's own shipped defaults.

    A `configure` that wrote a preference would be the adapter choosing the
    configuration, which is the one thing the ruling forbids in as many words.
    """
    target = build(tmp_path, artifact)
    answer = target.configure()
    assert answer["applied"] is None
    assert not (tmp_path / "arena" / "profile" / "prefs.js").exists(), (
        "configure wrote to the profile; it is a report, not an action"
    )


# --- 6. what the declaration admits it cannot express -----------------------


def test_the_hosts_own_directories_are_exempted_with_the_cost_stated(tmp_path):
    """The exemption is what stops the host's files being scored as the target's.

    It also swallows most of the sweep's power on this target class, and that is
    a fact a reader must be able to see from the artifact rather than work out.
    So each entry states what it costs, and this asserts the statement is there.
    """
    arena = tmp_path / "arena"
    declared = adapter.declaration(arena / "profile", arena / "data", arena / "home")
    exempt = {path: why for path, why in declared.not_derived_state}
    for path in (arena / "data", arena / "profile", arena / "home"):
        assert path in exempt, f"{path} is the host's and must be argued, not omitted"
    assert "cost" in exempt[arena / "data"]
    assert "stray" in exempt[arena / "data"]


def test_the_preferences_file_is_recorded_as_an_admission(tmp_path):
    """The sharpest thing this interface cannot say, said in the only field that can.

    The target writes its own preferences into a file the host owns. It is
    derived state and it has no declarable path: naming the file as a root
    claims the host's preferences are the target's. `not_derived_state`'s
    contract calls an entry that is neither user data nor external configuration
    an admission needing an argument, and this is that entry.
    """
    arena = tmp_path / "arena"
    declared = adapter.declaration(arena / "profile", arena / "data", arena / "home")
    exempt = {path: why for path, why in declared.not_derived_state}
    why = exempt[arena / "profile" / "prefs.js"]
    assert "CANNOT express" in why
    assert "extensions.zotero.beaver" in why


def test_the_sidecar_database_declares_its_journal_siblings(tmp_path):
    """A file root covers exactly one file, so the family must be enumerated.

    `residue()` matches by path prefix and a file is a prefix of nothing.
    Measured after one launch: the database, its write-ahead log and its shared
    memory file all exist. Declaring only the first under-declares by two.
    """
    arena = tmp_path / "arena"
    roots = {str(p) for p in adapter.declaration(
        arena / "profile", arena / "data", arena / "home").derived_state_roots}
    base = str(arena / "data" / adapter.PLUGIN_DATABASE)
    for suffix in ("", "-wal", "-shm", "-journal"):
        assert base + suffix in roots, f"{base + suffix} is undeclared"


# --- 7. the survivor sweep can see a file root ------------------------------


def test_the_survivor_sweep_sees_a_root_that_is_a_file(tmp_path):
    """The false green this lane found, pinned so it cannot come back.

    `Snapshot.of` was `os.walk` alone, which yields nothing for a regular file.
    Every declared root of the first two targets was a directory, so nothing
    noticed; this target declares four files, and the uninstall survivor check
    reported `pass` with three of them on disk. The fixture below is the red:
    delete the file-root branch in `assertions.Snapshot.of` and this fails while
    the directory case keeps passing, which is exactly how the defect hid.
    """
    sidecar = tmp_path / "sidecar.sqlite"
    sidecar.write_bytes(b"x")
    assert assertions.Snapshot.of(sidecar).files == frozenset({sidecar})

    directory = tmp_path / "dir"
    (directory / "inner").mkdir(parents=True)
    (directory / "inner" / "f").write_bytes(b"y")
    assert assertions.Snapshot.of(directory).files == frozenset(
        {directory / "inner" / "f"})

    absent = tmp_path / "never-created"
    assert assertions.Snapshot.of(absent).files == frozenset(), (
        "a root that does not exist must sweep as empty, not raise"
    )


def test_a_file_root_is_not_reported_as_residue_against_itself(tmp_path):
    """The other half: a declared file root must exempt the file it names.

    `_under` uses `relative_to`, which succeeds for a path against itself. If it
    did not, every sidecar file the target legitimately creates would be
    reported as a stray and the residue sweep would be red for all of them.
    """
    arena = tmp_path / "arena"
    declared = adapter.declaration(arena / "profile", arena / "data", arena / "home")

    class _Target:
        declaration = declared

    sidecar = arena / "data" / adapter.PLUGIN_DATABASE
    stray = arena / "somewhere-else" / "f"
    found = assertions.residue(frozenset({sidecar, stray}), _Target())
    assert sidecar not in found
    assert stray in found, "the sweep must still report a real stray"


# --- 8. the lifecycle's own honesty -----------------------------------------


def test_a_host_that_never_starts_raises_rather_than_returning_a_verdict(
        tmp_path, artifact):
    """An empty arena sweeps green, so a dead host must not look like a clean run.

    The alternative — recording it and carrying on — makes every assertion below
    it a verdict about a target that never ran, and the residue sweep in
    particular would report `pass`.
    """
    target = build(tmp_path, artifact)
    target.data.mkdir(parents=True)
    with pytest.raises(adapter.HostDidNotStart):
        target._wait()


def test_the_plugin_signal_is_the_targets_own_file_not_the_hosts(tmp_path, artifact):
    """Readiness must discriminate, and only one of the two databases does.

    The host writes its own database with or without any add-on installed, so
    waiting on it would report a loaded plugin for a launch that loaded none.
    Measured both ways on the real host; asserted here on the signal itself.
    """
    target = build(tmp_path, artifact)
    target.data.mkdir(parents=True)
    (target.data / adapter.HOST_DATABASE).write_bytes(b"")
    assert target._wait()["plugin_loaded"] is False
    (target.data / adapter.PLUGIN_DATABASE).write_bytes(b"")
    assert target._wait()["plugin_loaded"] is True


def test_uninstall_removes_the_installed_artifact_and_no_derived_state(
        tmp_path, artifact):
    """R15's clause forbids the harness deleting state on the target's behalf.

    So the verb removes exactly what `install` put there, and anything under a
    declared root is left for the sweep that follows to find. A planted file
    stands in for the sidecar database.
    """
    target = build(tmp_path, artifact)
    (target.profile / "extensions").mkdir(parents=True)
    target.installed_artifact.write_bytes(b"artifact")
    target.data.mkdir(parents=True)
    survivor = target.data / adapter.PLUGIN_DATABASE
    survivor.write_bytes(b"derived state")

    answer = target.uninstall()
    assert answer["artifact_was_present"] is True
    assert not target.installed_artifact.exists()
    assert survivor.exists(), "the harness deleted derived state on the target's behalf"
    assert answer["host_activated"]["read"] is False, (
        "an unreadable host record must be reported as unread, never as a False"
    )
