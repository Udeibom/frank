"""Taste memory (spec 09, design "Properties" 1-2 plus retirement, self statements and ordering)."""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from app.services.taste import rules
from app.services.taste.rules import Outcome, Signal

TOPICS = [t for t in rules.TOPICS if t != "other"]


@st.composite
def histories(draw):
    topic = draw(st.sampled_from(TOPICS))
    n = draw(st.integers(0, 12))
    return [Signal(topic, draw(st.sampled_from([1, -1])), draw(st.sampled_from(["p1", "p2", "p3", None])), i) for i in range(n)]


@settings(max_examples=500, deadline=None)
@given(histories())
def test_a_preference_needs_three_signals_the_same_way_across_two_songs(sig):
    out = rules.evaluate(sig)
    if out.status == "active":
        same = [s for s in sig if s.direction == out.direction]
        assert len(same) >= rules.PROMOTE_SIGNALS
        assert len({s.project_id for s in same if s.project_id}) >= rules.PROMOTE_SONGS
        assert len(same) > len(sig) - len(same)
        assert out.statement == rules.statement_for(sig[0].topic, out.direction) and out.statement


@settings(max_examples=200, deadline=None)
@given(st.sampled_from(TOPICS), st.integers(1, 20), st.sampled_from([1, -1]))
def test_one_signal_or_one_song_never_makes_a_preference(topic, n, d):
    assert rules.evaluate([Signal(topic, d, "p1", 0)]).status == "none"
    assert rules.evaluate([Signal(topic, d, "p1", i) for i in range(n)]).status == "none"


def test_three_across_two_songs_is_enough_and_other_is_never_promoted():
    sig = [Signal("verse_density", -1, "a", 0), Signal("verse_density", -1, "b", 1), Signal("verse_density", -1, "a", 2)]
    out = rules.evaluate(sig)
    assert out.status == "active" and out.direction == -1 and out.statement == "You usually like the verses stripped back."
    assert rules.evaluate([Signal("other", 1, p, i) for i, p in enumerate("abcabc")]).status == "none"


@settings(max_examples=300, deadline=None)
@given(histories(), st.sampled_from([1, -1]))
def test_two_contradictions_in_a_row_retire_a_preference(sig, d):
    topic = sig[0].topic if sig else "chorus_size"
    current = Outcome("active", d, 1.0, rules.statement_for(topic, d))
    tail = [Signal(topic, -d, "p9", 100), Signal(topic, -d, "p8", 101)]
    assert rules.evaluate(sig + tail, current).status == "retired"


def test_a_single_contradiction_only_weakens():
    topic = "vocal_space"
    sig = [Signal(topic, 1, p, i) for i, p in enumerate(["a", "b", "c"])]
    current = rules.evaluate(sig)
    weaker = rules.evaluate(sig + [Signal(topic, -1, "d", 9)], current)
    assert weaker.status == "active" and weaker.strength < current.strength


def test_what_people_say_about_themselves():
    assert rules.from_self("Honestly I hate autotune on my voice")[:2] == ("autotune_amount", -1)
    topic, d, said = rules.from_self("I really like big echoey vocals!")
    assert (topic, d) == ("vocal_space", 1) and said.startswith("You said:")
    assert rules.from_self("I love the piano in the bridge")[0] == "other"
    assert rules.from_self("make the chorus bigger") is None


def test_known_taste_puts_the_matching_direction_first():
    names = ["intro", "verse", "chorus", "verse", "chorus"]
    thinner = ("beat", [{"op": "smaller", "section": [1, 3]}])
    fuller = ("beat", [{"op": "bigger", "section": [2, 4]}])
    prefs = {"verse_density": -1}
    assert rules.direction_score(*thinner, names, prefs) == 1
    assert rules.direction_score(*fuller, names, prefs) == 0
    assert rules.direction_score("beat", [{"op": "bigger", "section": [1]}], names, prefs) == -1


def test_the_proposer_offers_what_the_artist_likes_first_but_still_offers_the_rest():
    from app.services.generation import beat
    from app.services.generation import fingerprint as fp_utils
    from app.services.refine import propose

    fp = fp_utils.normalize({"tempo_bpm": 96, "key": "A minor", "energy_level": 0.6, "density": 0.5})
    sections, fp = beat.build_beat_plan(fp)
    for s in sections:
        s.uid = s.index
    _, plain, _ = propose.propose(None, {"findings": []}, sections, 1, None, False, use_model=False)
    _, liked, _ = propose.propose(None, {"findings": []}, sections, 1, None, False, use_model=False, prefs={"chorus_size": 1})
    assert plain[0].title != "Fuller choruses" and liked[0].title == "Fuller choruses"
    assert {d.title for d in liked} == {d.title for d in plain}, "taste changes the order, never what is possible"
