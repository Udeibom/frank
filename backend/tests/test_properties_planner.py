"""Planner: the song's shape from the words, and the energy curve (song-engine tasks 3.1, 3.2)."""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from app.services.generation import beat

NAMES = ["verse", "chorus", "pre-chorus", "bridge"]
FP = {"tempo_bpm": 90, "key": "C minor", "energy_level": 0.6, "density": 0.5}


def structure(entries):
    line, out = 1, []
    for name, lines, feeling in entries:
        out.append({"name": name, "first_line": line, "last_line": line + lines - 1, "feeling": feeling})
        line += lines
    return {"sections": out}


entries = st.lists(st.tuples(st.sampled_from(NAMES), st.integers(1, 12), st.sampled_from([None, "sorrowful", "angry", "warm", "mixed"])), min_size=1, max_size=8)


@settings(max_examples=80, deadline=None)
@given(entries)
def test_the_words_decide_the_shape(es):
    arr = beat.arrangement_from_structure(structure(es))
    names = [a[0] for a in arr]
    assert names[0] == "intro" and names[-1] == "outro"
    assert names[1:1 + len(es)] == [e[0] for e in es]                  # the person's sections, in their order
    for (name, lines, _), (n, bars, _) in zip(es, arr[1:]):
        assert bars % 4 == 0 and 4 <= bars <= 16 and bars >= min(16, lines * beat.LINE_BARS)
    if "chorus" in names and es[-1][0] != "chorus":
        assert names[-2] == "chorus"                                   # the song ends on its hook


def test_no_structure_means_the_style_template():
    for bad in (None, {}, {"sections": []}, {"sections": [{"name": "verse"}]}, {"sections": [{"name": "solo", "first_line": 1, "last_line": 4}]}, "x"):
        assert beat.arrangement_from_structure(bad) is None
    secs, _ = beat.build_beat_plan(FP, beat.arrangement_from_structure(None))
    assert [s.name for s in secs] == [n for n, _ in beat.DEFAULT_ARRANGEMENT]


@settings(max_examples=40, deadline=None)
@given(st.floats(0.2, 1.0))
def test_each_chorus_is_at_least_as_big_as_the_one_before_and_the_last_is_the_biggest(e):
    secs, _ = beat.build_beat_plan({**FP, "energy_level": e})
    choruses = [s.energy for s in secs if s.name == "chorus"]
    assert choruses == sorted(choruses)
    verses = [s.energy for s in secs if s.name == "verse"]
    assert max(verses) <= max(choruses)


def test_the_words_feeling_moves_the_energy():
    calm = beat.build_beat_plan(FP, beat.arrangement_from_structure(structure([("verse", 4, "sorrowful")])))[0]
    hot = beat.build_beat_plan(FP, beat.arrangement_from_structure(structure([("verse", 4, "angry")])))[0]
    assert hot[1].energy > calm[1].energy
