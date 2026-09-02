"""The Zotero core #6012 adapter's declaration is honest, and one layer clause is not.

Ticket 0583. This target is the reference manager itself — the platform-native
seat — so the defect classes differ from both the external-server adapters and
the plugin ones. Six, and the sixth is not about this adapter at all:

1. **A pin nothing enforces.** #6012 force-pushed off its previous head on
   2026-09-02, so a ref names whatever the branch holds today. The build stamps
   the pinned short hash into `application.ini`, which makes the pin checkable —
   and a check that is documented rather than run lets an artifact record a
   revision that never executed, with no reader able to tell.
2. **A declaration and a method that disagree.** Five verbs are absent here. Let
   the declaration and the `raise`s drift and a verb the adapter refuses is
   scored as a failure of the target.
3. **A harness preference that is really a target option.** The harness writes
   three preferences into the profile. One of them landing on the feature under
   test would be a non-default option — which the ratified contract forbids —
   and it would look exactly like setup.
4. **An exemption list that swallows the sweep.** The desktop's shared cache and
   configuration roots are exempted, so the sweep must still be able to go red:
   a file appearing anywhere else in the arena is residue, and if it is not,
   the check is not a check.
5. **A refusal in the wrong place.** Refusing a missing build at construction
   would make the declaration unreadable on a machine where nothing is built,
   which is the one property a contract check depends on.
6. **`check_local_by_default` reds a target that has no embedder.** This is a
   finding about the assertion layer, reported rather than repaired: the layer's
   own status contract declares `locality: "local" | "remote" | "none"` and the
   assertion scores everything but `"local"` as `fail`. It is driven here
   against a local fake, with the `"local"` control beside it, so the report
   rests on an execution.

Every test here runs offline, spawns nothing, and writes only under `tmp_path`.
"""

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

from acceptance import adapters  # noqa: E402
from acceptance.adapters import zotero_core_6012 as adapter  # noqa: E402
from acceptance.assertions import (  # noqa: E402
    check_local_by_default,
    check_residue_inventory,
    check_uninstall_removes_declared_state,
)
from acceptance.interface import (  # noqa: E402
    FAIL,
    NOT_OFFERED,
    PASS,
    VERBS,
    Declaration,
    UnsupportedVerb,
)

APPLICATION_INI = (
    "[App]\nVendor=Zotero\nName=Zotero\n"
    "Version={version}\nBuildID={build}\nID=zotero@zotero.org\n"
)


def a_build(tmp_path: Path, *, version: str = adapter.VERSION) -> Path:
    """A launcher with an `application.ini` beside it, as `dir_build` lays one out."""
    root = tmp_path / "staging"
    (root / "app").mkdir(parents=True, exist_ok=True)
    launcher = root / "zotero"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    (root / "app" / "application.ini").write_text(
        APPLICATION_INI.format(version=version, build=adapter.BUILD_ID)
    )
    return launcher


def an_adapter(tmp_path: Path, *, application: Path | None = None):
    """An adapter on an arena, with a build that need not exist."""
    return adapter.ZoteroCore6012(
        tmp_path / "arena",
        application=application if application is not None else tmp_path / "nowhere" / "z",
    )


# --- 1. the declaration reads, and the pin is enforced ----------------------


def test_the_declaration_reads_with_nothing_built(tmp_path):
    """The cheapest contract check must not need a built Zotero on the machine."""
    declared = adapter.declaration(tmp_path / "arena")
    assert isinstance(declared, Declaration)
    assert declared.name == "zotero/zotero#6012"
    assert declared.derived_state_roots, "a target that writes nothing is a claim"


def test_the_revision_pins_a_full_commit_and_the_build_stamp(tmp_path):
    """A ref is not a pin here: #6012 force-pushed off 77e2c4b on 2026-09-02."""
    assert len(adapter.COMMIT) == 40
    assert all(c in "0123456789abcdef" for c in adapter.COMMIT)
    assert adapter.COMMIT[:9] in adapter.VERSION, (
        "the build stamp must carry the pinned short hash, or the pin is not checkable"
    )
    revision = adapter.declaration(tmp_path / "arena").revision
    assert adapter.COMMIT in revision
    assert adapter.VERSION in revision


def test_a_build_of_another_revision_is_refused(tmp_path):
    """The pin is checked, not documented — the fixture is a build that is not it.

    Without this the declaration would name a commit while the run launched
    whatever was handed over. The failure is silent by construction: another
    build of Zotero starts perfectly well, creates the same database, and reads
    the same preferences.
    """
    wrong = a_build(tmp_path, version="11.0.SOURCE.deadbeef1")
    with pytest.raises(ValueError, match="not a build of the pinned revision"):
        an_adapter(tmp_path, application=wrong)


def test_the_matching_build_constructs_and_is_read_back(tmp_path):
    """The control for the refusal above: it must be able to come out the other way."""
    target = an_adapter(tmp_path, application=a_build(tmp_path))
    assert target.build["Version"] == adapter.VERSION
    assert target.build["BuildID"] == adapter.BUILD_ID
    assert target.install()["pin_checked"] is True


def test_the_build_id_is_recorded_and_not_enforced(tmp_path):
    """A faithful rebuild of the same commit produces a different BuildID.

    Enforcing it would refuse a correctly reproduced target, which is the
    opposite of what exit criterion one asks for.
    """
    rebuilt = a_build(tmp_path)
    (rebuilt.parent / "app" / "application.ini").write_text(
        APPLICATION_INI.format(version=adapter.VERSION, build="20260904999999")
    )
    target = an_adapter(tmp_path, application=rebuilt)
    assert target.build["BuildID"] == "20260904999999"


# --- 2. refusals land where they cost nothing -------------------------------


def test_the_operators_home_is_refused(tmp_path):
    """The arena holds a sandbox HOME, a profile and a data directory.

    Without one, a run starts a reference manager against the operator's real
    library and the residue sweep reads the result.
    """
    with pytest.raises(ValueError, match="operator's own HOME"):
        adapter.ZoteroCore6012(Path.home(), application=tmp_path / "z")


def test_a_missing_build_is_refused_at_start_and_not_at_construction(tmp_path):
    """Where the refusal belongs, and why it is not at construction.

    Refusing at construction would make the declaration unreadable on a machine
    with nothing built — the property the first test in this file pins. So it
    lands where a run would otherwise report a missing binary as a target defect.
    """
    target = an_adapter(tmp_path)  # constructs cleanly with no build on disk
    with pytest.raises(RuntimeError, match="no build at"):
        with target.running():  # pragma: no cover - the body never runs
            pass


# --- 3. the declaration and the methods agree -------------------------------


@pytest.mark.parametrize("verb", sorted(adapter.declaration(Path("/x")).unsupported))
def test_every_absent_verb_raises_rather_than_returning(tmp_path, verb):
    """A verb the adapter refuses must raise, or it is scored as a target failure."""
    target = an_adapter(tmp_path, application=a_build(tmp_path))
    with pytest.raises(UnsupportedVerb):
        getattr(target, verb)() if verb != "query" else target.query("q", "meaning", 5)


def test_every_offered_verb_answers_without_a_process(tmp_path):
    """`install` and `configure` are the two offered verbs, and both are reports.

    They must not need the target running: the residue sweep calls `install`
    inside `running()`, but a contract check reads them without one.
    """
    target = an_adapter(tmp_path, application=a_build(tmp_path))
    offered = [v for v in VERBS if target.declaration.offers(v)]
    assert offered == ["install", "configure"]
    assert target.install()["commit"] == adapter.COMMIT
    assert target.configure()["target_preferences_set_by_the_harness"] == {}


def test_each_absent_verb_gives_its_own_reason(tmp_path):
    """Five absences, five reasons, and the reasons are what the lane produces.

    A shared or blank reason would put "this target hides a control it has" and
    "this target has no such work at all" back in one cell, which is the defect
    ticket 0597 closed.
    """
    unsupported = adapter.declaration(tmp_path / "arena").unsupported
    assert set(unsupported) == {"uninstall", "query", "status", "pause", "resume"}
    reasons = list(unsupported.values())
    assert all(len(r.strip()) > 120 for r in reasons)
    assert len(set(reasons)) == len(reasons), "two verbs sharing one reason"


def test_the_status_reason_records_that_the_object_exists(tmp_path):
    """This seat's finding: the status is computed, complete, and has no transport.

    Asserted rather than trusted to prose review, because "absent" and "present
    but unreachable" are opposite findings and the reason field is the only
    place they can be told apart.
    """
    why = adapter.declaration(tmp_path / "arena").unsupported["status"]
    assert "embeddings.js:2872-2889" in why
    assert "preferences UI" in why


# --- 4. the harness sets no option of the target's --------------------------


def test_no_harness_preference_touches_the_feature_under_test(tmp_path):
    """A harness preference on the target's own branch would be a non-default option.

    It would also be invisible: it looks exactly like setup, and the run would
    measure a configuration no ordinary user gets.
    """
    target = an_adapter(tmp_path, application=a_build(tmp_path))
    written = dict(target.harness_prefs())
    assert not [k for k in written if k.startswith(adapter.TARGET_PREF_PREFIXES)]
    assert "extensions.zotero.httpServer.port" in written
    assert written["extensions.zotero.httpServer.port"] == str(target.port)


def test_the_declared_defaults_are_the_shipped_ones(tmp_path):
    """`configure` reports the shipped defaults because the profile carries none.

    The empty read is the evidence, not a gap — the toolkit omits a preference
    still at its built-in default — so the adapter has to carry the defaults it
    cites, and they have to be the three the pull request declares.
    """
    target = an_adapter(tmp_path, application=a_build(tmp_path))
    reported = target.configure()
    assert reported["target_preferences_observed"] == {}
    assert set(reported["declared_defaults"]) == {
        "extensions.zotero.embeddings.model",
        "extensions.zotero.embeddings.indexingPaused",
        "extensions.zotero.embeddings.indexFulltext",
    }


def test_target_preferences_are_read_back_when_the_profile_has_any(tmp_path):
    """The control for the empty read: the reader must be able to find a key.

    Without this, "the profile carries none of the target's keys" and "the
    parser never matched anything" are the same output.
    """
    target = an_adapter(tmp_path, application=a_build(tmp_path))
    target.profile.mkdir(parents=True)
    (target.profile / "prefs.js").write_text(
        'user_pref("extensions.zotero.embeddings.model", "a-model");\n'
        'user_pref("extensions.zotero.httpServer.port", 23519);\n'
    )
    found = target.target_preferences()
    assert found == {"extensions.zotero.embeddings.model": '"a-model"'}


# --- 5. the residue sweep can still go red ----------------------------------


class _Fake(adapter.ZoteroCore6012):
    """The real declaration, a lifecycle that starts nothing, an install that writes.

    Subclassed rather than mocked so the sweep runs against THIS adapter's
    declared roots and exemptions. What is replaced is only the part that would
    need a desktop application.
    """

    def __init__(self, arena: Path, writes: tuple[Path, ...]) -> None:
        super().__init__(arena, application=arena / "nowhere" / "z")
        self._writes = writes

    @contextmanager
    def running(self):
        yield

    def install(self) -> dict:
        for path in self._writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x")
        return {"verb": "install", "wrote": [str(p) for p in self._writes]}


def test_the_residue_sweep_goes_red_on_a_stray(tmp_path):
    """The red that says this check is a check.

    A file created by the run outside every declared root and every exemption
    is residue. If this passes, the exemption list has swallowed the sweep and
    a green here means nothing.
    """
    arena = tmp_path / "arena"
    arena.mkdir()
    target = _Fake(arena, (arena / "somewhere" / "strayed.bin",))
    verdict = check_residue_inventory(target, arena=arena)
    assert verdict.result == FAIL
    assert verdict.detail["residue_count"] == 1


def test_the_residue_sweep_is_green_on_the_declared_roots(tmp_path):
    """The control arm: a run that writes only where the declaration says.

    A check that reds on everything is as useless as one that reds on nothing,
    and this is the arm that shows the difference is the declaration.
    """
    arena = tmp_path / "arena"
    arena.mkdir()
    target = _Fake(arena, (
        arena / "data" / "zotero.sqlite",
        arena / "profile" / "prefs.js",
        arena / "home" / ".cache" / "mozilla" / "firefox" / "a",
        arena / "home" / ".config" / "zotero" / "zotero" / "profiles.ini",
        arena / "home" / "Downloads" / "d",
    ))
    verdict = check_residue_inventory(target, arena=arena)
    assert verdict.result == PASS, verdict.detail


def test_the_desktop_exemptions_are_argued_and_narrow(tmp_path):
    """Each exemption carries a why, and the two target subtrees stay declared.

    The exemptions cover the desktop's shared cache and configuration roots. If
    they also covered the toolkit's own caches, those would be accounted for by
    exemption instead of by declaration — which is the direction that hides
    state rather than the direction that reports it.
    """
    declared = adapter.declaration(tmp_path / "arena")
    exempt = {path for path, _why in declared.not_derived_state}
    assert all(why.strip() for _p, why in declared.not_derived_state)
    home = tmp_path / "arena" / "home"
    assert home / ".cache" in exempt and home / ".config" in exempt
    for root in (home / ".cache" / "mozilla", home / ".config" / "mozilla",
                 home / ".cache" / "zotero", home / ".config" / "zotero"):
        assert root in declared.derived_state_roots


def test_the_harness_log_is_declared_as_the_harness_instrument(tmp_path):
    """The arena is harness-owned but the sweep counts every file in it.

    An adapter that captures its target's output inside its own arena without
    declaring the capture reports its own instrument as the target's residue.
    """
    arena = tmp_path / "arena"
    declared = adapter.declaration(arena)
    exempt = {path for path, _why in declared.not_derived_state}
    assert arena / adapter.HOST_LOG in exempt


# --- 6. the uninstall clause, and the layer finding it does not reach -------


def test_uninstall_reports_not_offered_and_carries_this_adapter_s_reason(tmp_path):
    """R15's uninstall clause on a target whose state is the user's library.

    The reason has to reach the artifact: "there is no removal surface" and
    "removing it would delete the library" are different findings, and only the
    second explains why no surface will ever appear.
    """
    arena = tmp_path / "arena"
    arena.mkdir()
    verdict = check_uninstall_removes_declared_state(_Fake(arena, ()), arena=arena)
    assert verdict.result == NOT_OFFERED
    assert "USER'S LIBRARY" in verdict.detail["why_absent"]


class _ReportsLocality:
    """A minimal target that answers `status` with one locality value.

    Local to this file and not an adapter: it exists to drive one assertion of
    the layer through the three values the layer's own status contract declares.
    """

    def __init__(self, locality: str | None, active: bool = True) -> None:
        self.declaration = Declaration(
            name="a fake that reports one locality",
            revision="none — this is a fixture, not a target",
            derived_state_roots=(),
            query_transport="none",
            default_configuration="none",
            process="none",
            unsupported={"install": "a fixture installs nothing"},
        )
        self._locality, self._active = locality, active

    @contextmanager
    def running(self):
        yield

    def configure(self) -> dict:
        return {"verb": "configure"}

    def status(self) -> dict:
        return {"embedding": {"locality": self._locality, "active": self._active,
                              "model": None}}


def test_a_target_with_no_embedder_is_scored_fail_by_the_local_by_default_clause():
    """The layer finding this seat reports, driven rather than argued.

    `assertions.py` declares the status shape as
    `locality: "local" | "remote" | "none"`, and `check_local_by_default`
    computes `PASS if locality == "local" and active is True else FAIL`. So a
    target honestly reporting `"none"` — no embedder in effect, which is exactly
    Zotero core #6012's default configuration — is scored `fail` against a clause
    reading "the embedder is local in the target's default configuration". It is
    not failing to be local; there is nothing there to be local or remote.

    This adapter does not reach the assertion (its `status` is absent for an
    independent reason), so nothing here is shaped to dodge the case. The verdict
    is recorded, not repaired: the ratified contract is not re-cut from a lane.
    """
    verdict = check_local_by_default(_ReportsLocality("none"))
    assert verdict.result == FAIL, (
        "if this passes, the layer has been changed and this finding is stale"
    )
    assert verdict.detail["locality"] == "none"


def test_the_control_arm_of_that_finding_passes():
    """The discriminating control: the same assertion must be able to come out green.

    Without it, the red above would be consistent with an assertion that reds on
    everything, and would prove nothing about the `"none"` case in particular.
    """
    assert check_local_by_default(_ReportsLocality("local")).result == PASS
    assert check_local_by_default(_ReportsLocality("remote")).result == FAIL


# --- 7. the adapter is reachable through the registry -----------------------


def test_the_registry_finds_this_adapter():
    """`NAMES` is what makes an adapter selectable and what the neutrality guard reads."""
    assert "zotero-core-6012" in adapters.available()
    assert adapter.NAMES == ("zotero-core-6012",)


def test_the_loader_refuses_a_run_with_no_build_named(tmp_path):
    """A guessed launcher is how a run measures a Zotero nobody pinned."""
    with pytest.raises(SystemExit, match="launcher of a build"):
        adapters.load("zotero-core-6012", tmp_path)
