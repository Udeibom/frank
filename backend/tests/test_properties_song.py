"""
Property-based tests for the Song Record (song-record spec 01).
Pure logic only (versions.py and brief.py); database writes are verified live.
"""
from __future__ import annotations

import copy

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from app.models.song import FACETS, USER_AUTHOR, Decision, FacetVersion, SongRecord
from app.services.song import versions as rules
from app.services.song.brief import MAX_DECISIONS, _required_header, build_brief

PROJECTS = ["p1", "p2"]
NON_INTENT = [f for f in FACETS if f != "intent"]
AUTHORS = [USER_AUTHOR, "frank", "producer", "mix_engineer"]

contents = st.dictionaries(
    st.text(alphabet="abcdefgh", min_size=1, max_size=4),
    st.one_of(st.integers(-5, 5), st.text(alphabet="abcxyz ", max_size=8)),
    max_size=3,
)

# A step either writes (choosing an existing parent index, or "newest") or restores.
steps = st.lists(
    st.tuples(
        st.sampled_from(["write", "restore", "branch"]),
        st.sampled_from(PROJECTS),
        st.sampled_from(NON_INTENT),
        contents,
        st.integers(0, 50),
        st.sampled_from(AUTHORS),
    ),
    max_size=25,
)


def run_steps(step_list, snapshots: list | None = None) -> list[FacetVersion]:
    """
    Apply a random sequence of writes/restores/branches using the pure rules.
    If `snapshots` is given, a deep copy of every stored row is appended after each step.
    """
    store: list[FacetVersion] = []
    _record = lambda: snapshots.append([v.model_dump() for v in store]) if snapshots is not None else None  # noqa: E731
    for kind, project, facet, content, pick, author in step_list:
        lane = [v for v in store if v.project_id == project and v.facet == facet]
        if kind == "restore" and lane:
            target = lane[pick % len(lane)]
            store.append(
                rules.restore(store, project_id=project, facet=facet, version_id=target.id, author=author)
            )
            _record()
            continue
        if not lane:
            parent = None
        elif kind == "branch":
            parent = lane[pick % len(lane)].id
        else:
            parent = lane[-1].id
        store.append(
            rules.new_version(
                store,
                project_id=project,
                facet=facet,
                content=content,
                parent_id=parent,
                operation="test",
                author=author,
            )
        )
        _record()
    return store


# ─── Version rules ───────────────────────────

@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(steps)
def test_stored_versions_are_never_changed_by_later_writes(step_list):
    # Requirement 3.2: append-only. Every earlier state must still match the final rows.
    snapshots: list = []
    final = run_steps(step_list, snapshots)
    for i, snap in enumerate(snapshots):
        assert snap == [v.model_dump() for v in final[: len(snap)]]


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(steps)
def test_every_lineage_is_acyclic_and_stays_in_its_project_and_facet(step_list):
    store = run_steps(step_list)
    for v in store:
        chain = rules.lineage(store, v.id)
        assert chain[0].parent_id is None
        assert chain[-1].id == v.id
        assert len({c.id for c in chain}) == len(chain)
        assert all(c.project_id == v.project_id and c.facet == v.facet for c in chain)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(steps)
def test_only_the_first_version_of_a_facet_has_no_parent_unless_branched_from_a_root(step_list):
    store = run_steps(step_list)
    for project in PROJECTS:
        for facet in NON_INTENT:
            lane = [v for v in store if v.project_id == project and v.facet == facet]
            roots = [v for v in lane if v.parent_id is None]
            assert len(roots) <= 1
            if lane:
                assert lane[0].parent_id is None


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(steps, st.integers(0, 50), st.sampled_from(PROJECTS), st.sampled_from(NON_INTENT))
def test_restore_adds_a_version_with_the_old_content_and_the_old_version_as_parent(
    step_list, pick, project, facet
):
    store = run_steps(step_list)
    lane = [v for v in store if v.project_id == project and v.facet == facet]
    if not lane:
        return
    target = lane[pick % len(lane)]
    before = len(store)
    restored = rules.restore(
        store, project_id=project, facet=facet, version_id=target.id, author=USER_AUTHOR
    )
    assert restored.content == target.content
    assert restored.parent_id == target.id
    assert restored.id != target.id
    assert restored.operation == "restore"
    assert len(store) == before  # restore() only builds; the caller stores it


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(contents, st.sampled_from([a for a in AUTHORS if a != USER_AUTHOR]))
def test_only_the_user_can_write_the_intent(content, author):
    with pytest.raises(rules.VersionError):
        rules.new_version(
            [], project_id="p1", facet="intent", content=content,
            parent_id=None, operation="x", author=author,
        )
    ok = rules.new_version(
        [], project_id="p1", facet="intent", content=content,
        parent_id=None, operation="x", author=USER_AUTHOR,
    )
    assert ok.content == content


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(steps, st.sampled_from(NON_INTENT), contents)
def test_a_parent_from_another_project_or_facet_is_rejected(step_list, facet, content):
    store = run_steps(step_list)
    foreign = [v for v in store if v.project_id != "p1" or v.facet != facet]
    if not foreign:
        return
    with pytest.raises(rules.VersionError):
        rules.new_version(
            store, project_id="p1", facet=facet, content=content,
            parent_id=foreign[0].id, operation="x", author=USER_AUTHOR,
        )


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(steps)
def test_a_missing_parent_is_rejected_once_a_facet_has_versions(step_list):
    store = run_steps(step_list)
    for v in store:
        with pytest.raises(rules.VersionError):
            rules.new_version(
                store, project_id=v.project_id, facet=v.facet, content={},
                parent_id=None, operation="x", author=USER_AUTHOR,
            )
        break


# ─── Brief ───────────────────────────────────

words = st.text(alphabet="abcdefghij klm", min_size=1, max_size=30)


@st.composite
def records(draw) -> SongRecord:
    intent = draw(st.one_of(st.none(), words))
    n_decisions = draw(st.integers(0, MAX_DECISIONS + 4))
    decisions = [
        Decision(
            id=str(i),
            project_id="p1",
            summary=f"DECISION_{i:02d}_" + draw(words),
            proposed_by="frank",
            user_reaction=draw(st.sampled_from([None, "liked it", "rejected it"])),
        )
        for i in range(n_decisions)  # index 0 is the newest
    ]
    facets = {f: None for f in FACETS}
    if intent:
        facets["intent"] = {"text": intent}
    facets["feeling"] = draw(st.one_of(st.none(), st.just({"summary": draw(words)})))
    return SongRecord(
        project_id="p1",
        phase=draw(st.sampled_from(["creating", "refining"])),
        facets=facets,
        lyrics=draw(st.one_of(st.none(), st.text(alphabet="abc def\n", max_size=800))),
        fingerprint=draw(st.one_of(st.none(), st.just({"energy_level": 0.5}))),
        beat=draw(st.one_of(st.none(), st.just({"label": "Beat v1", "sections": []}))),
        vocal=draw(st.one_of(st.none(), st.just({"takes_recorded": 2}))),
        mix=draw(st.one_of(st.none(), st.just({"label": "Mix v1", "params": {}}))),
        decisions=decisions,
    )


budgets = st.integers(50, 8000)
roles = st.one_of(st.none(), st.sampled_from(["mix_engineer", "vocal_producer", "beat_maker", "producer"]))


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(records(), roles, budgets)
def test_the_same_record_gives_the_same_brief(record, role, budget):
    assert build_brief(record, role, budget) == build_brief(copy.deepcopy(record), role, budget)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(records(), roles, budgets)
def test_brief_always_keeps_the_intent_and_phase(record, role, budget):
    brief = build_brief(record, role, budget)
    assert f"Phase: {record.phase}" in brief
    intent = (record.facets.get("intent") or {}).get("text")
    assert (intent in brief) if intent else ("not said yet" in brief)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(records(), roles, budgets)
def test_brief_fits_the_budget_unless_only_the_always_kept_part_remains(record, role, budget):
    brief = build_brief(record, role, budget)
    assert len(brief) <= budget or brief == _required_header(record)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(records(), roles, st.integers(50, 8000), st.integers(50, 8000))
def test_a_smaller_budget_drops_older_decisions_first(record, role, a, b):
    big, small = max(a, b), min(a, b)

    def kept(text: str) -> list[int]:
        return [i for i in range(len(record.decisions)) if f"DECISION_{i:02d}_" in text]

    kept_big = kept(build_brief(record, role, big))
    kept_small = kept(build_brief(record, role, small))
    assert set(kept_small) <= set(kept_big)
    # What stays is always the newest ones: a prefix 0..n-1 of the newest-first list.
    assert kept_small == list(range(len(kept_small)))
    assert kept_big == list(range(len(kept_big)))


@settings(suppress_health_check=[HealthCheck.too_slow])
@given(records())
def test_rejected_options_are_listed_so_they_are_not_offered_again(record):
    brief = build_brief(record, None, 100_000)
    shown = record.decisions[:MAX_DECISIONS]
    if any((d.user_reaction or "").startswith("reject") for d in shown):
        assert "Already rejected" in brief
    else:
        assert "Already rejected" not in brief


# ─── The brief speaks plainly (Plain Language Auditor, Nov 12) ─

def test_the_brief_describes_a_hummed_tune_in_words_not_note_numbers():
    record = SongRecord(
        project_id="p1",
        facets={
            "intent": {"text": "a song for my grandmother"},
            "melody": {
                "notes": [{"pitch_midi": 61, "start_beat": 0.0, "dur_beats": 0.5}],
                "performed_notes": [{"pitch_midi": 61, "start_beat": 0.0, "dur_beats": 0.5}] * 12,
                "tempo_bpm": 89.0, "key": "F# major", "mode": "major", "tempo_confidence": 0.7,
                "key_confidence": 0.9, "source_audio": "https://example.test/storage/hums/abc.wav", "confirmed": True,
            },
        },
    )
    brief = build_brief(record, "producer", 6000)
    assert "a tune the person hummed, 12 notes long, confirmed by the person" in brief
    for leak in ("pitch_midi", "tempo_bpm", "F#", "89", "example.test", "key_confidence"):
        assert leak not in brief


def test_the_brief_describes_direction_beat_vocal_and_mix_in_words():
    """Frankenstein task 57: the fingerprint and the beat, vocal and mix records are no longer dumped raw."""
    record = SongRecord(
        project_id="p1",
        fingerprint={"tempo_bpm": 72, "key": "C minor", "mode": "minor", "energy_level": 0.2, "warmth": 0.8,
                     "reference_texture_id": "tex-123", "instrumentation_hints": ["piano"]},
        beat={"label": "Beat v2", "sections": [{"index": 1, "name": "verse", "bars": 8, "layers": ["drums", "keys"]}],
              "lead": {"used": True, "sections": [3], "cut": False, "key": "C minor"}},
        vocal={"takes_recorded": 2, "active": "a recorded take", "tuned": True,
               "active_take": {"kind": "take", "on_the_notes": 0.93, "sits_behind_beat_ms": 40}},
        mix={"label": "Mix v1", "params": {"vocal_gain_db": 0, "beat_gain_db": -6, "vocal_effects": ["warm", "reverb"],
                                           "beat_effects": [], "harmony_enabled": True, "section_gain_db": {}}},
    )
    brief = build_brief(record, None, 100_000)
    assert "unhurried" in brief and "darker, more wistful notes" in brief and "instruments: piano" in brief
    assert "section 1 verse (medium length, drums, keys)" in brief
    assert "their hummed tune plays in section 3" in brief
    assert "sings a little behind the beat" in brief and "voice well above the music" in brief
    for leak in ("tempo_bpm", "C minor", "72", "tex-123", "gain_db", "reverb", " ms", "0.93", "{"):
        assert leak not in brief, leak


# ─── Two writers racing for the first version (Integration Tester, Nov 12) ─

import asyncio  # noqa: E402

from postgrest.exceptions import APIError  # noqa: E402

from app.services.song import store  # noqa: E402


class _FakeSongDb:
    """An in-memory stand-in for db/song.py that can simulate losing a race for the first version."""

    def __init__(self, lose_race_once: bool):
        self.rows: list[FacetVersion] = []
        self.active: dict[str, str] = {}
        self.lose_race_once = lose_race_once
        self.insert_calls = 0

    async def list_versions(self, project_id, facet=None):
        return [v for v in self.rows if v.project_id == project_id and (facet is None or v.facet == facet)]

    async def get_active_map(self, project_id):
        return dict(self.active)

    async def insert_version(self, v: FacetVersion):
        self.insert_calls += 1
        if self.lose_race_once and v.parent_id is None:
            # Another writer got there first with its own first version.
            self.lose_race_once = False
            self.rows.append(
                FacetVersion(id="theirs", project_id=v.project_id, facet=v.facet, content={"n": 0},
                             parent_id=None, operation="other", author="frank")
            )
            self.active[v.facet] = "theirs"
            raise APIError({"message": "duplicate key", "code": "23505", "details": "", "hint": ""})
        if v.parent_id is None and any(r.parent_id is None and r.facet == v.facet and r.project_id == v.project_id for r in self.rows):
            raise APIError({"message": "duplicate key", "code": "23505", "details": "", "hint": ""})
        self.rows.append(v)
        return v

    async def set_active(self, project_id, facet, version_id):
        self.active[facet] = version_id


def _run_with_fake(monkeypatch, fake, coro_factory):
    for name in ("list_versions", "get_active_map", "insert_version", "set_active"):
        monkeypatch.setattr(store.song_db, name, getattr(fake, name))
    return asyncio.run(coro_factory())


def test_a_writer_that_loses_the_race_for_the_first_version_builds_on_the_winner(monkeypatch):
    fake = _FakeSongDb(lose_race_once=True)
    result = _run_with_fake(
        monkeypatch, fake,
        lambda: store.write_facet("p1", "feeling", {"n": 1}, author="frank", operation="t"),
    )
    roots = [v for v in fake.rows if v.parent_id is None]
    assert len(roots) == 1 and roots[0].id == "theirs"
    assert result.parent_id == "theirs"
    assert fake.active["feeling"] == result.id
    assert fake.insert_calls == 2


def test_other_database_errors_are_not_swallowed_by_the_retry(monkeypatch):
    class Broken(_FakeSongDb):
        async def insert_version(self, v):
            raise APIError({"message": "boom", "code": "XX000", "details": "", "hint": ""})

    fake = Broken(lose_race_once=False)
    with pytest.raises(APIError):
        _run_with_fake(monkeypatch, fake, lambda: store.write_facet("p1", "feeling", {}, author="frank", operation="t"))


def test_a_caller_who_names_a_parent_is_not_retried_on_a_conflict(monkeypatch):
    class AlwaysConflict(_FakeSongDb):
        async def insert_version(self, v):
            self.insert_calls += 1
            raise APIError({"message": "duplicate key", "code": "23505", "details": "", "hint": ""})

    fake = AlwaysConflict(lose_race_once=False)
    fake.rows.append(FacetVersion(id="a", project_id="p1", facet="feeling", content={}, parent_id=None, operation="t", author="frank"))
    with pytest.raises(APIError):
        _run_with_fake(
            monkeypatch, fake,
            lambda: store.write_facet("p1", "feeling", {}, author="frank", operation="t", parent_id="a"),
        )
    assert fake.insert_calls == 1
