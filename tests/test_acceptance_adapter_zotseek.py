"""The ZotSeek adapter's declaration is honest about a target it does not own.

Ticket 0584. This target is a plugin inside a third-party desktop application,
so the defect classes are not the ones the other two adapters have. Five, each
of which turns one of the four states into a lie, and none of which needs the
host application, the artifact, or a display:

1. **A pin nothing enforces.** The declaration names a commit and a digest for a
   103 MB file the harness copies into a profile. If the digest is documented
   rather than checked, an artifact records a revision that never ran, and no
   reader can tell.
2. **An exemption list that swallows the sweep.** Most of what appears under this
   target's arena is the host's, so `not_derived_state` has to be large. Large
   enough and the residue sweep is vacuously green: it cannot fail, so it is not
   a check. What must stay true is that a file the target strays into the ONE
   directory it writes to is still residue.
3. **A readiness signal that watches the wrong process.** `running()` starts the
   host, and the host coming up says nothing about whether the plugin loaded. A
   wait on the host's own database returns green for a run in which the target
   never initialised.
4. **A declaration and a method that disagree.** Five verbs are declared absent
   here, more than on either other adapter. Let the declaration and the raises
   drift and a verb the adapter refuses is scored as a failure of the target.
5. **A harness preference that is really a target option.** The harness writes
   preferences into the host's profile to make a sideloaded plugin active. One of
   them landing under the target's own preference branch would be a non-default
   option — which the ratified contract forbids — and it would look exactly like
   setup.

Every test here runs offline, spawns nothing, and writes only under tmp_path.
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
adapter = importlib.import_module("bench.acceptance.adapters.zotseek")


def artifact_at(tmp_path: Path, content: bytes = b"") -> Path:
    """A stand-in for the release artifact. Absent unless a test needs one."""
    path = tmp_path / adapter.ARTIFACT
    if content:
        path.write_bytes(content)
    return path


def build(tmp_path: Path) -> object:
    """An adapter on an arena, a launcher and an artifact that need not exist.

    Construction must work with nothing installed: the declaration is the half of
    an adapter a contract check reads, and it should not depend on a desktop
    application being present on the machine doing the checking.
    """
    return adapter.ZotSeek(
        tmp_path / "arena",
        launcher=tmp_path / "nowhere" / "launcher",
        artifact=artifact_at(tmp_path),
    )


# --- 1. the declaration reads, and the pin is enforced ----------------------


def test_the_declaration_reads_without_the_host_or_the_artifact(tmp_path):
    """The cheapest contract check must not need a desktop application installed."""
    declared = adapter.declaration(tmp_path / "arena")
    assert isinstance(declared, interface.Declaration)
    assert declared.name == "introfini/ZotSeek"
    assert declared.derived_state_roots, "a target that writes nothing is a claim"


def test_the_revision_pins_a_full_commit_and_the_artifact_digest(tmp_path):
    """A tag would be the wrong pin here: the repository's only tag is nine major
    versions behind the manifest, so the commit and the artifact digest are the
    whole of what identifies what ran."""
    assert len(adapter.COMMIT) == 40
    assert all(c in "0123456789abcdef" for c in adapter.COMMIT)
    assert len(adapter.ARTIFACT_SHA256) == 64
    revision = adapter.declaration(tmp_path / "arena").revision
    assert adapter.COMMIT in revision
    assert adapter.ARTIFACT_SHA256 in revision
    assert adapter.VERSION in adapter.ARTIFACT


def test_an_artifact_whose_digest_does_not_match_is_refused(tmp_path):
    """The pin is checked, not documented — the fixture is a file that is not it.

    Without this the declaration would name a digest while the run copied
    whatever was handed over, and the artifact would record a revision nobody
    measured. The failure is silent by construction: a wrong plugin loads
    perfectly well.
    """
    wrong = artifact_at(tmp_path, b"not the pinned release")
    with pytest.raises(ValueError, match="pinned artifact"):
        adapter.ZotSeek(tmp_path / "arena", launcher=tmp_path / "l", artifact=wrong)


def test_a_missing_artifact_is_refused_at_placement_and_not_at_construction(tmp_path):
    """The control for the test above, and it decides where the refusal belongs.

    Refusing a missing artifact at construction would make the declaration
    unreadable on a machine with nothing installed, which is the property the
    first test in this file pins. So the refusal lands where it costs nothing:
    at the point a run would otherwise start a host with no plugin in it and
    measure the host.
    """
    target = build(tmp_path)  # constructs cleanly with no artifact on disk
    target.profile.joinpath("extensions").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="pinned artifact is not at"):
        target._place_artifact()


# --- 2. the sandbox and the exemptions --------------------------------------


def test_every_derived_state_root_is_inside_the_arena(tmp_path):
    """A root outside the arena aims the residue sweep at real state."""
    arena = tmp_path / "arena"
    for root in adapter.declaration(arena).derived_state_roots:
        assert arena in root.parents, f"{root} escapes the arena"


def test_construction_on_the_operators_own_home_is_refused():
    """The destructive reading, blocked rather than documented.

    With no arena this adapter starts a desktop application against the
    operator's real profile and library.
    """
    with pytest.raises(ValueError, match="HOME"):
        adapter.ZotSeek(Path.home(), launcher=Path("/nonexistent"),
                        artifact=Path("/nonexistent"))


def test_a_strayed_file_in_the_data_directory_is_still_residue(tmp_path):
    """The red that keeps the exemption list from being a blanket.

    `not_derived_state` here carries the host application itself, because on a
    plugin target the host owns every directory the plugin writes into. Exempt
    the data directory wholesale and the sweep can never fail — it would report
    green for a target that wrote anything anywhere. So the data directory is
    exempted entry by entry, and this is the fixture that proves a file which is
    neither a declared root nor a measured host entry still comes back as
    residue.
    """
    target = build(tmp_path)
    strayed = target.data / "zotseek-scratch.tmp"
    assert assertions.residue(frozenset({strayed}), target) == [strayed]


def test_the_hosts_own_data_directory_files_are_not_residue(tmp_path):
    """The control for the test above: without it, every run is red for the host.

    A check that fires on everything is as uninformative as one that fires on
    nothing. These names were measured in a host-only control arm — the identical
    launch with no plugin installed — so they are the host's, and R15 does not
    make a target answer for its host.
    """
    target = build(tmp_path)
    for entry in adapter.HOST_DATA_ENTRIES:
        path = target.data / entry / "deep" / "file"
        assert assertions.residue(frozenset({path}), target) == [], entry


def test_the_declared_roots_are_not_residue(tmp_path):
    """The other control: a target's own declared state is accounted for."""
    target = build(tmp_path)
    roots = frozenset(target.declaration.derived_state_roots)
    assert assertions.residue(roots, target) == []


def test_the_home_and_profile_exemptions_are_wide_and_that_is_asserted(tmp_path):
    """The weakness is pinned rather than left to prose.

    The host's own writes are nondeterministic in path — it opens its start page
    in the desktop browser and stages its word-processor integration, both into
    the sandbox HOME, both under a fresh random directory name every run — so a
    differential sweep is not available there and the exemption is directory-wide.
    A green residue verdict on this target therefore means "nothing strayed in the
    data directory", not "nothing strayed anywhere". Asserting it here means a
    future change that narrowed the claim, or widened it, has to say so.
    """
    target = build(tmp_path)
    for path in (target.home / "anything" / "at" / "all",
                 target.profile / "anything" / "at" / "all"):
        assert assertions.residue(frozenset({path}), target) == []


def test_the_hosts_preference_file_is_exempted_with_its_own_argument(tmp_path):
    """The finding must not be buried under the profile-wide exemption.

    The target writes sixteen keys into this file and `derived_state_roots` is a
    tuple of paths, so the interface cannot express it. The entry exists to carry
    that argument where a reader of the artifact will meet it; if it were dropped,
    the profile exemption would still cover the file and the finding would
    silently vanish.
    """
    declared = adapter.declaration(tmp_path / "arena")
    prefs = tmp_path / "arena" / "profile" / "prefs.js"
    reasons = [why for path, why in declared.not_derived_state if path == prefs]
    assert reasons, "prefs.js is listed separately, for the finding it carries"
    assert "cannot express" in reasons[0]


# --- 3. readiness watches the target, not the host --------------------------


def test_readiness_is_the_targets_own_file(tmp_path):
    """A wait on the host's database is green for a run the plugin never joined."""
    target = build(tmp_path)
    assert target.sidecar.parent == target.data
    assert target.sidecar.name.startswith("zotseek")


def test_the_wait_fails_when_the_target_never_initialises(tmp_path):
    """The red: no sidecar, so the wait must raise rather than yield a green run."""
    target = build(tmp_path)
    target.startup_timeout = 0.5
    target.data.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="did not appear"):
        target._await_target(started=__import__("time").monotonic())


def test_the_wait_returns_once_the_targets_file_exists(tmp_path):
    """The control: with the sidecar present the same code path must succeed.

    Without it, a wait that raised unconditionally would pass the test above and
    make every run of this adapter red for a reason that has nothing to do with
    the target.
    """
    target = build(tmp_path)
    target.settle = 0.0
    target.data.mkdir(parents=True)
    target.sidecar.write_bytes(b"")
    target._await_target(started=__import__("time").monotonic())


# --- 4. the declaration and the methods agree -------------------------------


def test_the_five_absent_verbs_raise_rather_than_return(tmp_path):
    """A declared-absent verb that returns a value is a `not-offered` nobody sees."""
    target = build(tmp_path)
    assert set(target.declaration.unsupported) == {
        "uninstall", "query", "status", "pause", "resume"
    }
    for verb in sorted(target.declaration.unsupported):
        with pytest.raises(interface.UnsupportedVerb):
            if verb == "query":
                target.query("q", "meaning", 5)
            else:
                getattr(target, verb)()


def test_every_offered_verb_exists_and_no_offered_verb_declares_itself_absent(tmp_path):
    target = build(tmp_path)
    absent = {"uninstall", "query", "status", "pause", "resume"}
    for verb in interface.VERBS:
        assert callable(getattr(target, verb)), f"{verb} is not implemented"
        assert target.declaration.offers(verb) is (verb not in absent)


def test_each_absent_verb_carries_a_reason_that_says_something(tmp_path):
    """Ticket 0597's field is the one this target most needs, so it is asserted.

    Three kinds of absence sit under `not-offered` across the three adapters, and
    only this field separates them. A reason that repeated the verb's name, or
    that were shared across all five, would be the undifferentiated cell the
    field replaced — so the reasons must be distinct and must be long enough to
    carry an argument.
    """
    unsupported = adapter.declaration(tmp_path / "arena").unsupported
    assert len(set(unsupported.values())) == len(unsupported), "reasons are not distinct"
    for verb, why in unsupported.items():
        assert len(why) > 120, f"{verb}'s reason is too short to be one"


def test_the_adapter_satisfies_the_contracts_own_protocol(tmp_path):
    """`Target` is runtime-checkable, so the structural gate costs one call.

    It catches the rename nothing else here would: `running` is the lifecycle the
    contract makes a context manager rather than an eighth verb.
    """
    assert isinstance(build(tmp_path), interface.Target)


# --- 5. harness setup is not a target option --------------------------------


def test_no_harness_preference_touches_the_targets_own_branch(tmp_path):
    """A harness preference under the target's branch is a non-default option.

    It would be indistinguishable from setup in a diff, and the contract forbids
    it in as many words. The list is short enough to read; this makes it checked.
    """
    target = build(tmp_path)
    for name, _value in target.harness_prefs():
        assert adapter.TARGET_PREF_PREFIX not in name, f"{name} configures the target"


def test_the_declared_port_is_the_port_written(tmp_path):
    """A declared value that is not the written value is worse than no declaration.

    Two lanes on one machine need different ports, so the port cannot be a module
    constant; that makes the pairing something to check rather than to read.
    """
    target = adapter.ZotSeek(tmp_path / "arena", launcher=tmp_path / "l",
                             artifact=artifact_at(tmp_path), port=23999)
    written = dict(target.harness_prefs())
    assert written["extensions.zotero.httpServer.port"] == "23999"
    target._write_profile()
    assert "23999" in (target.profile / "prefs.js").read_text(encoding="utf-8")


def test_configure_sets_none_of_the_targets_preferences_and_says_so(tmp_path):
    """The default configuration is the one an ordinary user gets, so nothing is set.

    `configure` reports rather than changes, as on the first adapter. What is
    checked is that the report says the harness set nothing, and that the reported
    observation really comes from the profile rather than from a constant.
    """
    target = build(tmp_path)
    target._write_profile()
    (target.profile / "prefs.js").write_text(
        'user_pref("extensions.zotero.httpServer.port", 23219);\n'
        'user_pref("zotseek.autoIndex", false);\n'
        'user_pref("zotseek.embeddingModel", "nomic-embed-text-v1.5");\n',
        encoding="utf-8",
    )
    answer = target.configure()
    assert answer["target_preferences_set_by_the_harness"] == {}
    assert set(answer["target_preferences_observed"]) == {
        "zotseek.autoIndex", "zotseek.embeddingModel"
    }
    assert answer["observed_count"] == 2


def test_the_preference_read_ignores_the_hosts_own_keys(tmp_path):
    """The control for the read: a profile with no target key must come back empty.

    A parse that matched every `user_pref` line would pass the test above — the
    target's keys are in there — while reporting the host's entire preference
    store as the target's configuration.
    """
    target = build(tmp_path)
    target.profile.mkdir(parents=True)
    (target.profile / "prefs.js").write_text(
        'user_pref("extensions.autoDisableScopes", 0);\n'
        'user_pref("app.update.enabled", false);\n'
        'user_pref("extensions.webextensions.uuids", "{\\"zotseek@zotero.org\\":\\"x\\"}");\n',
        encoding="utf-8",
    )
    assert target.target_preferences() == {}


def test_install_reports_the_pin_and_what_materialised(tmp_path):
    """`install` is a report here, and the artifact is read from it.

    There is no install surface to call: this target materialises when the host
    starts with the XPI in its profile. What the report has to carry is the pin
    and the declared roots' state, because that is a reader's only evidence that
    the thing measured is the thing declared.
    """
    target = build(tmp_path)
    reported = target.install()
    assert reported["commit"] == adapter.COMMIT
    assert reported["addon_id"] == adapter.ADDON_ID
    assert set(reported["materialized"]) == {
        str(p) for p in target.declaration.derived_state_roots
    }
    assert all(v is None for v in reported["materialized"].values()), (
        "nothing has run, so nothing may be reported as materialised"
    )
