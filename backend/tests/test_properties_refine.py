"""Refine loop (spec 08, design "Properties" 1-4; tasks 2, 3, 5, 6, 8)."""
from __future__ import annotations

import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from hypothesis import assume, given, settings, strategies as st

from app.services.generation import beat
from app.services.generation import fingerprint as fp_utils
from app.services.generation import ops
from app.services.refine import experiments, propose, resolve
from app.services.refine.models import Direction

FP = fp_utils.normalize({"tempo_bpm": 96, "key": "A minor", "energy_level": 0.6, "density": 0.5, "warmth": 0.6, "brightness": 0.4})
SEED = 1234
MIX = {"vocal_gain_db": 0.0, "beat_gain_db": -6.0, "harmony_gain_db": -4.0, "harmony_enabled": True,
       "vocal_effects": [], "beat_effects": [], "section_gain_db": {}}


def plan(energy: float = 0.6, density: float = 0.5):
    sections, _ = beat.build_beat_plan(fp_utils.normalize({**FP, "energy_level": energy, "density": density}))
    for s in sections:
        s.uid = s.index
    return sections


def finding(fid: str, sections: list[int]) -> dict:
    return {"id": fid, "plain": "Something.", "severity": "worth_a_look", "confidence": 0.7, "evidence": [], "sections": sections, "parts": []}


FINDING_IDS = ["chorus_lift", "copy", "flat", "melody_wanders", "voice_buried", "voice_crowded", "too_quiet", "clipping", "too_loud"]


@st.composite
def situations(draw):
    sections = plan(draw(st.floats(0.2, 0.95)), draw(st.floats(0.2, 0.95)))
    n = len(sections)
    found = [finding(draw(st.sampled_from(FINDING_IDS)), sorted(draw(st.sets(st.integers(0, n - 1), min_size=1, max_size=2))))
             for _ in range(draw(st.integers(0, 3)))]
    has_mix = draw(st.booleans())
    return sections, found, has_mix, draw(st.booleans()), draw(st.sampled_from([None, "the chorus doesn't hit", "my voice", "something's off"]))


# ── property 2: the directions are real, checked and different ───────────

@settings(max_examples=60, deadline=None)
@given(situations())
def test_directions_apply_are_distinct_and_two_or_three(case):
    sections, found, has_mix, hummed, concern = case
    frozen = copy.deepcopy(sections)
    message, dirs, experiment = propose.propose(concern, {"findings": found}, sections, SEED, MIX if has_mix else None, hummed,
                                                use_model=False, fp=FP)
    assert [vars(s) for s in sections] == [vars(s) for s in frozen], "proposing must not touch the plan"
    assert message
    assert 1 <= len(dirs) <= 3
    assert len(dirs) >= 2, f"this plan allows more than one different change: {[d.title for d in dirs]}"
    assert len({d.signature() for d in dirs}) == len(dirs)
    assert experiment == (not found)
    for d in dirs:
        assert d.changes, d
        if d.kind == "beat":
            new, _, _, heard = ops.apply_audible(sections, SEED, d.actions, FP)     # every beat direction is audible
            assert set(d.sections) & set(heard)
            assert d.sections and all(0 <= i < len(new) for i in d.sections) and len(d.sections) <= propose.PREVIEW_MAX_SECTIONS
        else:
            assert has_mix


def test_the_model_cannot_offer_the_same_change_twice_or_a_broken_one(monkeypatch):
    sections = plan()
    found = {"findings": [finding("chorus_lift", [1, 2])]}
    bigger = {"title": "Bigger", "plain": "Bigger chorus.", "kind": "beat", "actions": [{"op": "bigger", "section": 2}]}
    monkeypatch.setattr(propose, "_ask_producer", lambda *a: {"message": "The chorus is as strong as the verse.", "directions": [
        bigger, dict(bigger, title="Same again"), {"title": "Broken", "plain": "x", "kind": "beat", "actions": [{"op": "explode"}]},
        {"title": "Nowhere", "plain": "x", "kind": "beat", "actions": [{"op": "bigger", "section": 99}]}, "nonsense", {"option": 99}]})
    message, dirs, _ = propose.propose("the chorus doesn't hit", found, sections, SEED, None, False)
    assert message.startswith("The chorus")
    assert len({d.signature() for d in dirs}) == len(dirs) >= 2
    assert all(d.title not in ("Broken", "Nowhere", "Same again") for d in dirs)


def test_a_model_failure_still_gives_directions(monkeypatch):
    def boom(*a):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(propose, "_ask_producer", boom)
    message, dirs, _ = propose.propose("boring", {"findings": [finding("flat", [])]}, plan(), SEED, MIX, False)
    assert len(dirs) >= 2 and "listened" in message.lower()


# ── property 3: an experiment changes exactly one thing ──────────────────

def _changed_things(before, after) -> set[str]:
    out: set[str] = set()
    by = {s.uid: s for s in before}
    for s in after:
        b = by[s.uid]
        if (b.energy, b.density) != (s.energy, s.density):
            out.add("size")
        if b.layers != s.layers:
            out.add("parts playing")
        for part in set(b.parts) | set(s.parts):
            for k in set(b.parts.get(part, {})) | set(s.parts.get(part, {})):
                if b.parts.get(part, {}).get(k) != s.parts.get(part, {}).get(k):
                    out.add(f"{part}.{k}")
    return out


@settings(max_examples=40, deadline=None)
@given(st.floats(0.2, 0.95), st.floats(0.2, 0.95), st.booleans(), st.booleans(), st.sampled_from([None, "the verse", "the chorus", "my voice"]))
def test_each_experiment_differs_in_exactly_one_thing(energy, density, hummed, has_mix, concern):
    sections = plan(energy, density)
    menu = [v for v in (propose.validate(d, sections, SEED, MIX if has_mix else None)
                        for d in experiments.experiment_menu(sections, hummed, has_mix, concern)) if v]
    assert len(menu) >= 2
    for d in menu:
        assert len(d.actions) == 1
        if d.kind == "beat":
            new, seed, _ = ops.apply_operations(sections, SEED, d.actions)
            assert seed == SEED
            assert len(_changed_things(sections, new)) == 1, (d.title, _changed_things(sections, new))
        else:
            assert d.actions[0]["type"] == "apply_effect"
        if hummed:
            assert not any(a.get("part") == "melody" for a in d.actions), "a hummed tune is never rewritten"
    _, dirs, experiment = propose.propose(concern, {"findings": []}, sections, SEED, MIX if has_mix else None, hummed, use_model=False)
    assert experiment and all(len(d.actions) == 1 for d in dirs)


def test_the_model_cannot_widen_an_experiment(monkeypatch):
    two = {"title": "Two things", "plain": "x", "kind": "beat", "actions": [{"op": "bigger", "section": 2}, {"op": "smaller", "section": 1}]}
    monkeypatch.setattr(propose, "_ask_producer", lambda *a: {"message": "I can't tell yet.", "directions": [two]})
    _, dirs, experiment = propose.propose("off", {"findings": []}, plan(), SEED, None, False)
    assert experiment and dirs and all(len(d.actions) == 1 for d in dirs)


def test_the_menu_puts_the_part_the_person_named_first():
    assert experiments.experiment_menu(plan(), False, True, "my voice feels wrong")[0].kind == "mix"
    assert experiments.experiment_menu(plan(), False, False, "the chorus")[0].title == "Fuller choruses"


# ── preview scope ────────────────────────────────────────────────────────

def test_changed_sections_follow_identity_not_position():
    before = plan()
    after, seed, _ = ops.apply_operations(before, SEED, [{"op": "bigger", "section": 2}])
    assert propose.changed_sections(before, after, SEED, seed) == [2]
    assert propose.preview_sections([2], len(after)) == [2]
    assert propose.preview_sections([0], 5, [4, 8, 8, 8, 4]) == [0, 1]          # 12 bars together: heard in context
    assert propose.preview_sections([1], 5, [4, 8, 8, 8, 4]) == [1]             # 16 bars would be over the wait
    moved, seed, _ = ops.apply_operations(before, SEED, [{"op": "move", "section": 1, "to": 3}])
    assert propose.changed_sections(before, moved, SEED, seed)        # sections that moved are what changed
    _, seed2, _ = ops.apply_operations(before, SEED, [{"op": "another_song"}])
    assert propose.changed_sections(before, before, SEED, seed2) == [s.index for s in before]


# ── property 1: a preview never writes a version or an active pointer ────

def test_a_preview_writes_no_version_and_no_pointer(monkeypatch):
    from app.services.jobs import refine_runner as rr

    sections = plan()
    d = propose.validate(Direction(title="Bigger", plain="Bigger chorus.", kind="beat", actions=[{"op": "bigger", "section": 2}]),
                         sections, SEED, None)
    row = {"id": "p1", "project_id": "proj", "directions": [d.model_dump()], "based_on": {"beat": "b1"}}
    calls: list[str] = []

    def forbidden(name):
        def f(*a, **k):
            calls.append(name)
            raise AssertionError(f"a preview called {name}")
        return f

    for mod, names in ((rr.beat_db, ["create_beat_version_sync", "create_beat_version", "create_stem_sync"]),
                       (rr.mix_db, ["create_mix_version_sync"]),
                       (rr.projects_db, ["update_project_active_state"])):
        for n in names:
            monkeypatch.setattr(mod, n, forbidden(n))
    stored: dict = {}
    monkeypatch.setattr(rr.refine_db, "get_proposal", lambda pid: row)
    monkeypatch.setattr(rr.refine_db, "update_direction", lambda pid, n, f: stored.update(f))

    async def basis(pid):
        return {"beat_id": "b1", "mix_id": None, "sections": sections, "seed": SEED, "fp": FP, "lead": None, "mix_params": None,
                "beat": {"render_url": None, "params": {"song_gain": 1.0}}}
    monkeypatch.setattr(rr, "load_basis", basis)
    heard: dict = {}

    def excerpt(new, idx, fp, seed, lead, song_gain=None):
        heard.update(idx=idx, gain=song_gain, energy=new[2].energy)
        return np.zeros((100, 2), dtype=np.int16)
    monkeypatch.setattr(rr.beat_engine, "render_excerpt", excerpt)
    monkeypatch.setattr(rr, "upload_audio", lambda bucket, data, extension, name_prefix: f"https://x/{name_prefix}.mp3")
    monkeypatch.setattr(rr, "to_mp3_bytes", lambda a: b"mp3")
    done: dict = {}

    async def complete(job, result):
        done.update(result)

    async def nothing(*a, **k):
        return None
    monkeypatch.setattr(rr.jobs_db, "mark_processing", nothing)
    monkeypatch.setattr(rr.jobs_db, "mark_complete", complete)
    monkeypatch.setattr(rr.jobs_db, "mark_failed", forbidden("mark_failed"))
    monkeypatch.setattr(rr, "_progress", nothing)

    asyncio.run(rr.run_preview_job("job", "proj", "p1", 0))
    assert not calls
    assert done["preview_url"].endswith("preview.mp3") and stored["preview_url"] == done["preview_url"]
    assert heard["idx"] == d.sections and 2 in d.sections and heard["gain"] == 1.0 and heard["energy"] > sections[2].energy
    assert sections[2].energy == plan()[2].energy, "the saved plan is untouched"


def test_render_excerpt_plays_only_the_chosen_sections():
    sections = plan()
    spans = beat.section_spans(sections, FP["tempo_bpm"])
    one = beat.render_excerpt(sections, [2], FP, SEED, song_gain=1.0, mix_chain=False)
    expected = spans[2][1] - spans[2][0] + int(beat.TAIL_SECONDS * beat.SAMPLE_RATE)
    assert one.shape == (expected, 2) and one.dtype == np.int16 and np.abs(one).max() > 0
    assert beat.render_excerpt(sections, [], FP, SEED).shape[0] == 0


# ── property 4: the resolver names a version that exists, or asks ───────

T0 = datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)


def versions(n: int, changes: list[list[str]] | None = None) -> list[dict]:
    return [{"id": f"v{i + 1}", "label": f"Beat v{i + 1}", "created_at": (T0 + timedelta(hours=i)).isoformat(),
             "params": {"changes": (changes or [[]] * n)[i]}} for i in range(n)]


@settings(max_examples=150, deadline=None)
@given(st.integers(1, 8), st.text(max_size=60), st.sampled_from(["give me the second version back", "the one before I changed the chorus",
       "go back", "the version from yesterday", "undo that", "the original", "v3", "the one with the strings", "version 12"]))
def test_resolver_returns_a_real_version_or_asks(n, noise, phrase):
    vs = versions(n, [[["I brought in the strings in the chorus."], ["I made it bigger in the chorus."], []][i % 3] for i in range(n)])
    ids = {v["id"] for v in vs}
    for text in (phrase, noise, phrase + " " + noise):
        r = resolve.resolve(text, vs, [], vs[-1]["id"], now=T0 + timedelta(days=1))
        if r.version:
            assert r.version["id"] in ids
        assert all(c["id"] in ids for c in r.candidates) and len(r.candidates) <= 2


def test_resolver_cases():
    vs = versions(4, [[], ["I brought in the strings in the chorus."], ["I made it bigger in the chorus."], ["I made the drums simpler everywhere."]])
    now = T0 + timedelta(days=1)
    assert resolve.resolve("give me the second version back", vs, now=now).version["id"] == "v2"
    assert resolve.resolve("go back", vs, active_id="v4", now=now).version["id"] == "v3"
    assert resolve.resolve("undo", vs, active_id="v2", now=now).version["id"] == "v1"
    assert resolve.resolve("the original", vs, now=now).version["id"] == "v1"
    assert resolve.resolve("the one before I changed the drums", vs, now=now).version["id"] == "v3"
    assert resolve.resolve("the version before I changed the chorus", vs, now=now).version["id"] == "v1"
    assert resolve.resolve("the version from yesterday", vs, now=now).candidates      # four that day: play two and ask
    assert resolve.resolve("the one with the strings", vs, now=now).version["id"] == "v2"
    assert resolve.resolve("version 9", vs, now=now).candidates
    assert not resolve.is_about_versions("make the chorus bigger before the bridge")
    assert resolve.is_about_versions("give me the second version back")
    assert resolve.is_about_versions("can you put it back how it was")


# ── mismatch: the person's word, one question ────────────────────────────

def test_disagreeing_asks_one_question_about_the_word():
    from app.routers.refine import meaning_question
    q = meaning_question("No, it needs to be bigger")
    assert q.count("?") == 1 and "louder" in q and "fuller" in q
    assert meaning_question("nah").endswith("?")


def test_frank_speaks_as_one_person_and_names_an_experiment():
    found = {"findings": []}
    said = propose.finish_message("The Listener didn't find a clear cause.", found, True)
    assert "listener" not in said.lower() and "one thing" in said
    assert propose.finish_message("I couldn't pin it down.", found, True).endswith("your ears can decide.")
    assert propose.finish_message("", {"findings": [{"plain": "The chorus is quiet."}]}, False).startswith("I listened.")


def test_not_knowing_what_is_wrong_starts_the_listening():
    for said in ("something feels off with the chorus but I don't know what", "it just doesn't hit", "I can't put my finger on it",
                 "show me a few ideas"):
        assert resolve.wants_refine(said), said
    for said in ("make the chorus bigger", "the bass is too busy in the verse", "I love it"):
        assert not resolve.wants_refine(said), said


def test_the_propose_job_completes_with_the_findings(monkeypatch):
    """Regression (demo 3, Nov 19): the drift check overwrote the Listener's findings and every proposal failed."""
    from app.services.jobs import refine_runner as rr
    from app.services.listener.models import MeasurementReport
    from app.services.team import identity

    sections = plan()
    done: dict = {}

    async def nothing(*a, **k):
        return None

    async def measure(*a, **k):
        return MeasurementReport()

    async def basis(pid):
        return {"beat_id": "b1", "mix_id": None, "sections": sections, "seed": SEED, "fp": FP, "lead": None, "mix_params": None, "beat": {}}

    async def ctx(pid):
        return {}, False

    async def complete(job, result):
        done.update(result)

    async def fail(job, msg):
        raise AssertionError(msg)

    async def say(job, text):
        return None

    async def mention(pid, key, note):
        return note

    monkeypatch.setattr(rr.jobs_db, "mark_processing", nothing)
    monkeypatch.setattr(rr.jobs_db, "mark_complete", complete)
    monkeypatch.setattr(rr.jobs_db, "mark_failed", fail)
    monkeypatch.setattr(rr, "_progress", say)
    monkeypatch.setattr(rr.listen_project, "measure_song", measure)
    monkeypatch.setattr(rr, "load_basis", basis)
    monkeypatch.setattr(rr, "_prefs", lambda pid: nothing())
    monkeypatch.setattr(rr.refine_db, "insert_proposal", lambda row: {"id": "p1", **row})
    monkeypatch.setattr(identity, "context", ctx)
    monkeypatch.setattr(identity, "mention_once", mention)
    monkeypatch.setattr(identity, "drift_notes", lambda *a, **k: ["That would take your own tune out."])
    monkeypatch.setattr(rr.propose_mod, "_ask_producer", lambda *a: {"message": "", "directions": [
        {"title": "Leave the tune out", "plain": "x", "kind": "beat", "actions": [{"op": "remove_part", "part": "melody", "section": [2]}]}]})
    asyncio.run(rr.run_propose_job("job", "proj", "the chorus doesn't hit"))
    assert done["proposal_id"] == "p1" and isinstance(done["findings"], list) and 2 <= len(done["directions"]) <= 3
