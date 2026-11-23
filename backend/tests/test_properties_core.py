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
