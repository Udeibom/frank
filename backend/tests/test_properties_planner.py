"""Planner: the song's shape from the words, and the energy curve (song-engine tasks 3.1, 3.2)."""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from app.services.generation import beat
from app.services.song.sections import generation_for_stated_structure, parse_section_order, structure_from_order

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
    assert parse_section_order("Take note of the way the song is structured into sections: Verse 1 Your floor on which I built my love Pre-chorus Tell me why Chorus Villains are made by love Bridge Hear me Lord Chorus Villains are made by love Outro Maybe I will be redeemed") == order
    assert [s["name"] for s in structure_from_order(order)["sections"]] == order
    assert parse_section_order("Just make the drums busier") == []


def test_a_stated_order_rebuilds_the_beat_from_that_facet():
    action = generation_for_stated_structure("structure-7")
    assert action["type"] == "generate_full_beat"
    assert action["params"]["structure_context"] == {
        "facet": "structure",
        "facet_version_id": "structure-7",
        "source": "user_message",
    }


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


def test_an_approved_direction_starts_the_beat_and_the_rest_continues_from_it():
    from app.services.generation import texture

    seed = texture.texture_seed({**FP, "texture_palette": 5, "energy_level": 0.3, "density": 0.8})
    fp = {**FP, "approved_start": {"kind": "direction", "source_id": "tex-1", "direction": seed}}
    sections, _ = beat.build_beat_plan(fp)
    first = sections[0]
    assert first.parts["harmony"]["progression"] == seed["harmony"]
    assert first.layers == seed["layers"]
    assert first.energy == seed["fingerprint"]["energy_level"]
    assert first.density == seed["fingerprint"]["density"]
    assert len(sections) > 1


def test_an_approved_hum_plays_from_the_start_and_still_returns_for_the_chorus():
    from app.services.generation import lead as lead_mod

    tune = lead_mod.Lead(notes=((60, 0, 1), (62, 1, 1), (64, 2, 1)), bars=4, key="C minor", source="melody-1")
    fp = {**FP, "approved_start": {"kind": "hum", "source_id": "melody-1"}}
    sections, planned_fp = beat.build_beat_plan(fp, lead=tune)
    _, contexts, _ = beat.plan_contexts(sections, planned_fp, 7, tune)
    assert sections[0].bars >= tune.bars
    assert contexts[0].lead is tune
    assert contexts[1].lead is None
    assert 0 in beat.lead_info(sections, tune, fp)["sections"]


def test_a_request_to_start_from_the_kept_feeling_is_recognised():
    assert beat.wants_approved_start("Start from the feeling I kept and build the rest from it")
    assert beat.wants_approved_start("Begin with my hum")
    assert not beat.wants_approved_start("Make the chorus bigger")
