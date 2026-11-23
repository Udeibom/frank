"""
Core path (spec 15): the founder's run of 22 Nov, turned into properties.
Pure logic only; the live run is scripts/ops/e2e_core.py.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from app.services.generation import ops
from app.services.intake import pace

bpms = st.floats(min_value=40, max_value=200, allow_nan=False)
targets = st.floats(min_value=60, max_value=140, allow_nan=False)
notes = st.lists(st.fixed_dictionaries({"pitch_midi": st.integers(40, 80),
                                         "start_beat": st.floats(0, 64, allow_nan=False),
                                         "dur_beats": st.floats(0.1, 8, allow_nan=False)}), min_size=1, max_size=30)


# ─── Requirement 2.1: the hum's speed is counted to fit the song ─

def test_the_founders_worship_hum_is_counted_at_a_gentle_speed():
    lyrics = "Worthy of every breath we could ever breathe\nOpen up my eyes in wonder"
    assert pace.choose_factor(138, pace.centre(lyrics)) == 0.5          # 69, not 138


@settings(deadline=None)
@given(bpms, notes, st.sampled_from([0.5, 1.0, 2.0]))
def test_recounting_a_tune_never_changes_how_it_sounds(bpm, ns, factor):
    content = {"tempo_bpm": bpm, "notes": ns, "performed_notes": ns, "grid": 0.25}
    out = pace.recount(content, factor)
    for before, after in zip(ns, out["notes"]):
        seconds_before = before["start_beat"] * 60 / bpm
        seconds_after = after["start_beat"] * 60 / out["tempo_bpm"]
        assert seconds_after == pytest.approx(seconds_before, rel=1e-3, abs=1e-3)
        assert after["dur_beats"] * 60 / out["tempo_bpm"] == pytest.approx(before["dur_beats"] * 60 / bpm, rel=1e-3, abs=1e-3)
        assert after["pitch_midi"] == before["pitch_midi"]


@settings(deadline=None)
@given(bpms, targets)
def test_the_chosen_count_is_the_closest_playable_one(bpm, target):
    import math

    f = pace.choose_factor(bpm, target)
    playable = [g for g in (0.5, 1.0, 2.0) if pace.LOW <= bpm * g <= pace.HIGH]
    if playable:
        assert f in playable
        best = min(abs(math.log2(bpm * g / target)) for g in playable)
        assert abs(math.log2(bpm * f / target)) == pytest.approx(best)


# ─── Requirement 2.2: slower and faster really change the speed ─

@settings(deadline=None)
@given(st.integers(56, 164), st.sampled_from(["slower", "faster"]), st.sampled_from(["a_little", "a_lot"]))
def test_slower_and_faster_change_the_speed_the_way_they_say(bpm, op, amount):
    fp = {"tempo_bpm": bpm}
    try:
        out, rest, changes = ops.apply_speed(fp, [{"op": op, "amount": amount}])
    except ops.OpError:
        # only allowed at the edge: already as slow or fast as Frank plays
        assert (op == "slower" and bpm <= ops.SPEED_MIN + 2) or (op == "faster" and bpm >= ops.SPEED_MAX - 2)
        return
    assert rest == [] and len(changes) == 1
    assert ops.SPEED_MIN <= out["tempo_bpm"] <= ops.SPEED_MAX
    assert (out["tempo_bpm"] < bpm) if op == "slower" else (out["tempo_bpm"] > bpm)
    assert fp == {"tempo_bpm": bpm}                                    # the input is never changed


def test_other_operations_pass_through_untouched():
    raw = [{"op": "looser", "section": None}, {"op": "slower"}]
    out, rest, changes = ops.apply_speed({"tempo_bpm": 138}, raw)
    assert rest == [{"op": "looser", "section": None}]
    assert out["tempo_bpm"] < 138 and "slower" in changes[0]


# ─── Requirement 2.3: Frank never claims a speed change it didn't make ─

from app.services.team import claims  # noqa: E402


@pytest.mark.parametrize("said", ["It is too fast and random.", "It's a worship song and the beat is too fast for it.",
                                  "Those things you did does not reduce the speed of the beat"])
def test_the_founders_speed_requests_become_a_real_slower_change(said):
    reply, ops_out = claims.fix_speed(said, "I slowed the groove by relaxing the drums.", [{"op": "looser", "section": None}])
    assert any(o["op"] == "slower" for o in ops_out)
    assert {"op": "looser", "section": None} in ops_out


@settings(deadline=None)
@given(st.sampled_from(["I slowed it down.", "Now it moves at a calmer pace.", "The speed feels better now."]),
       st.lists(st.sampled_from([{"op": "looser", "section": None}, {"op": "sparser", "part": "arp", "section": None}]), max_size=2))
def test_a_reply_never_claims_speed_when_nothing_changes_speed(reply, ops_in):
    out, ops_out = claims.fix_speed("make the chorus bigger", reply, ops_in)
    if not any(o.get("op") in ("slower", "faster") for o in ops_out):
        assert "the speed is still the same" in out.lower() or "haven't changed the speed" in out.lower()


# ─── Requirement 3: the music lasts as long as the singing ─

from app.services.generation import beat as beat_engine  # noqa: E402


def _capacity(bpm: float) -> float:
    """The longest song Frank will make: 16 sections, the last at 32 bars."""
    return beat_engine.seconds_of_bars(15 * 8 + beat_engine.MAX_SECTION_BARS, bpm)


@settings(deadline=None, max_examples=200)
@given(st.integers(55, 165), st.floats(0, 600, allow_nan=False))
def test_a_new_beat_is_at_least_as_long_as_the_singing(bpm, voice_s):
    arr = beat_engine.fit_arrangement(beat_engine.DEFAULT_ARRANGEMENT, bpm, voice_s)
    seconds = beat_engine.seconds_of_bars(sum(e[1] for e in arr), bpm)
    if voice_s + beat_engine.LENGTH_MARGIN_S <= _capacity(bpm) * 0.9:
        assert seconds >= voice_s
    assert arr[0][0] == "intro" and arr[-1][0] == "outro"           # it still starts and ends like a song
    assert len(arr) <= beat_engine.MAX_SECTIONS_FOR_LENGTH


def test_the_founders_four_minutes_at_138_gets_music_to_the_end():
    plan, _ = beat_engine.build_beat_plan({"tempo_bpm": 138, "energy_level": 0.5}, min_seconds=240)
    assert beat_engine.seconds_of_bars(sum(s.bars for s in plan), 138) >= 240


@settings(deadline=None, max_examples=100)
@given(st.integers(55, 165), st.floats(0, 400, allow_nan=False))
def test_lengthening_a_beat_keeps_every_section_it_had(bpm, voice_s):
    plan, _ = beat_engine.build_beat_plan({"tempo_bpm": bpm, "energy_level": 0.5})
    for s in plan:
        s.uid = s.index
    out, changed = beat_engine.extend_sections(plan, bpm, voice_s)
    before = [s.uid for s in plan]
    kept = [s.uid for s in out if s.uid in before]
    assert kept == before                                             # same sections, same order, same notes
    assert len({s.uid for s in out}) == len(out)                      # every copy has its own identity
    if changed:
        assert beat_engine.seconds_of_bars(sum(s.bars for s in out), bpm) > beat_engine.seconds_of_bars(sum(s.bars for s in plan), bpm)


# ─── Requirement 4: "Try something different" is different ─

from app.services.generation import texture  # noqa: E402
from app.services.generation import fingerprint as fp_utils  # noqa: E402

fingerprints = st.fixed_dictionaries({
    "energy_level": st.floats(0, 1), "tempo_feel": st.sampled_from(["floating", "steady", "building", "driving"]),
    "instrumentation_hints": st.lists(st.sampled_from(["piano", "organ", "guitar", "strings", "synth"]), max_size=2),
})


@settings(deadline=None)
@given(fingerprints)
def test_a_different_direction_changes_sound_energy_and_movement_and_is_never_the_stored_copy(fp):
    nxt = {**fp, **texture.contrast(fp)}
    assert texture.palette_for(nxt) != texture.palette_for(fp)
    assert abs(nxt["energy_level"] - fp_utils.normalize(fp)["energy_level"]) >= 0.2 or nxt["energy_level"] in (0.1, 0.9)
    assert nxt["tempo_feel"] != fp["tempo_feel"]
    assert fp_utils.texture_cache_key(nxt) != fp_utils.texture_cache_key(fp)


@settings(deadline=None)
@given(fingerprints)
def test_asking_for_different_again_and_again_goes_through_every_sound_before_repeating(fp):
    seen, cur = [], dict(fp)
    for _ in range(len(texture.PALETTES)):
        seen.append(texture.palette_for(cur))
        cur = {**cur, **texture.contrast(cur)}
    assert sorted(seen) == list(range(len(texture.PALETTES)))


@pytest.mark.parametrize("said", ["Try something quite different.", "That one isn't quite it.", "try again", "something else"])
def test_the_founders_reactions_ask_for_a_different_direction(said):
    assert texture.wants_different(said)
