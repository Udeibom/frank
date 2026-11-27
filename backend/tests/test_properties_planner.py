"""Planner: the song's shape from the words, and the energy curve (song-engine tasks 3.1, 3.2)."""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from app.services.generation import beat
from app.services.song.sections import parse_section_order, structure_from_order

NAMES = ["intro", "verse", "pre-chorus", "chorus", "bridge", "outro"]
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
    assert [a[0] for a in arr] == [e[0] for e in es]
    for (name, lines, _), (n, bars, _) in zip(es, arr):
        assert n == name
        assert bars % 4 == 0 and 4 <= bars <= 16 and bars >= min(16, lines * beat.LINE_BARS)


def test_no_structure_means_the_style_template():
    for bad in (None, {}, {"sections": []}, {"sections": [{"name": "solo", "first_line": 1, "last_line": 4}]}, "x"):
        assert beat.arrangement_from_structure(bad) is None
    secs, _ = beat.build_beat_plan(FP, beat.arrangement_from_structure(None))
    assert [s.name for s in secs] == [n for n, _ in beat.DEFAULT_ARRANGEMENT]


def test_an_explicit_order_is_kept_exactly():
    order = ["verse", "pre-chorus", "chorus", "bridge", "chorus", "outro"]
    arr = beat.arrangement_from_structure(structure([(name, 4, None) for name in order]))
    assert [a[0] for a in arr] == order


def test_a_stated_order_is_parsed():
    order = ["verse", "pre-chorus", "chorus", "bridge", "chorus", "outro"]
    assert parse_section_order("Verse 1\nPre-chorus\nChorus\nBridge\nChorus\nOutro") == order
    assert parse_section_order("Make it Verse, Pre-chorus, Chorus, Bridge, Chorus, Outro") == order
    assert parse_section_order("Verse -> Pre-chorus -> Chorus -> Bridge -> Chorus -> Outro") == order
    assert [s["name"] for s in structure_from_order(order)["sections"]] == order
    assert parse_section_order("Just make the drums busier") == []


def test_boarding_music_grows_the_sections_without_inventing_any():
    arr = [("verse", 8, None), ("chorus", 8, None)]
    long = beat.fit_arrangement(arr, 90, 120)
    assert [a[0] for a in long] == ["verse", "chorus"]
    assert sum(a[1] for a in long) > sum(a[1] for a in arr)


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
    assert hot[0].energy > calm[0].energy
