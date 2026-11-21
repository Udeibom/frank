"""
Property tests for the pure mappings of frankenstein spec 14 (design.md, "Testing"). Each organ that touches the
song through a rule (not a model) has its rule checked here for any input.
"""
from __future__ import annotations

import random

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services import provenance, region
from app.services.generation import composer, grooves
from app.services.generation.styles import default_choice
from app.services.intake import moment, picture
from app.services.llm import gemini_media
from app.services.reference import analyse as ref
from app.services.team.plain import find_jargon
from app.services.words import timing

STYLES = ["soul", "gospel", "pop", "lofi", "rock", "folk", "hiphop", "electronic", "ambient", "_default"]


# ── drums: real drummers' feel ────────────────────────────────────────────────────────────────────────

@settings(max_examples=60, deadline=None)
@given(st.sampled_from(STYLES), st.sampled_from(["kick", "snare", "hat", "open", "ghost"]), st.integers(0, 15),
       st.sampled_from([-1, 0, 1]), st.integers(0, 10_000), st.booleans())
def test_feel_never_moves_a_hit_more_than_a_third_of_a_step_and_keeps_velocity_sane(style, lane, step, feel, seed, swung):
    shift, accent = grooves.shape(grooves.for_style(style), lane, step, feel, random.Random(seed), swung)
    assert abs(shift) <= grooves.MAX_OFFSET_STEPS * 0.25 + 1e-9
    assert 0.2 < accent < 2.5


@settings(max_examples=40, deadline=None)
@given(st.sampled_from(STYLES), st.integers(0, 15), st.integers(0, 10_000))
def test_tighter_is_never_looser_than_natural(style, step, seed):
    g = grooves.for_style(style)
    tight = abs(grooves.shape(g, "hat", step, -1, random.Random(seed), False)[0])
    loose = abs(grooves.shape(g, "hat", step, 1, random.Random(seed), False)[0])
    assert tight <= loose + 1e-9


@settings(max_examples=25, deadline=None)
@given(st.integers(1, 8), st.floats(0.05, 1.0), st.floats(0.05, 1.0), st.integers(0, 1000), st.sampled_from([-1, 0, 1]))
def test_drums_stay_inside_their_bars_and_in_midi_range(bars, energy, density, seed, feel):
    ctx = composer.SectionContext(seed=seed, style=default_choice(), parts={"drums": {"feel": feel}})
    part = composer.compose_drums(bars, energy, density, ctx)
    assert part.events
    for e in part.events:
        assert 0.0 <= e.start < bars * 4.0 + 0.1
        assert 1 <= e.velocity <= 127


def test_a_tapped_rhythm_is_played_exactly_as_tapped():
    from dataclasses import replace

    ctx = composer.SectionContext(seed=3, style=replace(default_choice(), own_groove=True))
    part = composer.compose_drums(2, 0.6, 0.5, ctx)
    kicks = [e.start for e in part.events if e.note == composer.KICK]
    assert all(abs(k * 4 - round(k * 4)) < 0.02 for k in kicks)     # on the sixteenth grid


# ── rules about where Gemini may be used ─────────────────────────────────────────────────────────────

@given(st.text(max_size=4))
def test_gemini_is_blocked_unless_the_country_is_known_and_outside_eea_ch_uk(code):
    r = region.normalise(code)
    allowed = region.gemini_allowed(code, explicit=True)
    assert allowed == (r is not None and r not in region.GEMINI_BLOCKED)


def test_every_eea_country_switzerland_and_the_uk_are_blocked():
    for c in ["DE", "FR", "IT", "NO", "IS", "LI", "CH", "GB", "UK", "ie"]:
        assert not region.gemini_allowed(c, explicit=True)
    assert region.gemini_allowed("NG", explicit=True) and region.gemini_allowed("US", explicit=True)
    assert not region.gemini_allowed(None, explicit=True)


@settings(max_examples=50)
@given(st.lists(st.fixed_dictionaries({"tag": st.text(max_size=12), "plain": st.text(max_size=60),
                                       "confidence": st.one_of(st.floats(allow_nan=True), st.text(max_size=3))}), max_size=8))
def test_at_most_three_notes_and_other_is_never_confirmed(notes):
    heard = gemini_media.parse_heard({"heard": "x", "notes": notes})
    assert heard is not None and len(heard.notes) <= gemini_media.MAX_NOTES
    for n in heard.notes:
        assert 0.0 <= n["confidence"] <= 1.0 and n["tag"] in gemini_media.TAGS
    for n in gemini_media.confirm(heard, {"chorus_lift", "voice_buried", "too_loud"}):
        if n["tag"] == "other":
            assert not n["confirmed"]


# ── provenance lines are plain ──────────────────────────────────────────────────────────────────────

@given(st.sampled_from(sorted(provenance.ORGANS)), st.one_of(st.none(), st.text(max_size=80)))
def test_every_provenance_line_is_jargon_free(organ, custom):
    line = provenance.line_for(organ, custom)
    assert not find_jargon(line.plain)


# ── words and timing ────────────────────────────────────────────────────────────────────────────────

word = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=9)


@settings(max_examples=40)
@given(st.lists(st.lists(word, min_size=1, max_size=6), min_size=1, max_size=6), st.floats(0.1, 0.6))
def test_line_spans_never_overlap_or_run_backwards(lines, gap):
    words, t = [], 0.0
    for line in lines:
        for w in line:
            words.append({"word": w, "start": round(t, 2), "end": round(t + gap, 2)})
            t += gap
    spans = timing.line_spans(words, [" ".join(l) for l in lines])
    last = -1.0
    for s in spans:
        if s["start"] is not None:
            assert s["end"] > s["start"] >= last - 1e-9
            last = s["end"]


# ── pictures, the moment, references ────────────────────────────────────────────────────────────────

@settings(max_examples=40)
@given(st.lists(st.tuples(st.floats(0, 1), st.floats(0, 1), st.floats(0, 1)), min_size=4, max_size=64))
def test_colours_and_their_hints_stay_in_range(px):
    c = picture.colours(np.array(px, dtype=np.float32))
    for v in (c.brightness, c.warmth, c.energy):
        assert 0.0 <= v <= 1.0
    for v in picture.hints(c).values():
        assert 0.0 <= v <= 1.0


@given(st.integers(0, 23), st.one_of(st.none(), st.integers(0, 99)), st.one_of(st.none(), st.floats(-40, 50)))
def test_the_moment_is_always_plain_words(hour, code, temp):
    text = moment.describe(hour, code, temp, None)
    assert text and not find_jargon(text)
    for v in moment.hints(hour, code).values():
        assert 0.0 <= v <= 1.0


measured = st.fixed_dictionaries({
    "bpm": st.floats(40, 220), "tempo_confidence": st.floats(0, 1), "mode": st.sampled_from(["major", "minor"]),
    "key_confidence": st.floats(0, 1), "brightness_hz": st.floats(100, 9000), "busyness": st.floats(0, 40),
    "loudness": st.floats(-40, -3), "build": st.floats(0, 20), "low_share": st.floats(0, 1)})


@given(measured)
def test_reference_hints_are_in_range_and_speed_is_playable(m):
    h = ref.hints(m)
    if "tempo_bpm" in h:
        assert 60 <= h["tempo_bpm"] <= 150
    for k in ("brightness", "density", "energy_level"):
        if k in h:
            assert 0.0 <= h[k] <= 1.0
    assert not any(find_jargon(w) for w in ref.feeling_words(m))


@given(measured, measured)
def test_at_most_three_plain_differences_from_a_reference(a, b):
    diffs = ref.compare(a, b)
    assert len(diffs) <= 3
    assert not any(find_jargon(d) for d in diffs)


# ── feeling words measured by Song Describer ───────────────────────────────────────────────────────────

from app.services.intake import feeling_table  # noqa: E402


@given(st.lists(st.sampled_from(sorted(feeling_table._table().get("words", {})) or ["calm"]), max_size=6), st.text(max_size=40))
def test_feeling_words_only_nudge_the_direction_within_range_and_never_set_speed(words, extra):
    h = feeling_table.hints(" ".join(words) + " " + extra)
    assert "tempo_bpm" not in h
    for v in h.values():
        assert 0.05 <= v <= 0.95


def test_words_people_tag_differently_are_not_trusted():
    for w, c in feeling_table._table().get("mood_check", {}).items():
        assert feeling_table.trusted(w) == (c["agreement"] >= feeling_table.MIN_AGREEMENT
                                           and feeling_table._table()["words"][w]["recordings"] >= feeling_table.MIN_RECORDINGS)
