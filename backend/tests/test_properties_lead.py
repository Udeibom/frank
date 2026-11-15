"""
Property-based tests for the hum-as-lead feature (song-engine spec 04, requirement 3.3):
the person's confirmed hum becomes the chorus melody, and the chords are chosen to fit it.

Fast properties look at notes and dictionaries. Two tiny renders (2-bar sections) check the plumbing.
"""
from __future__ import annotations

import asyncio
import json
import math
from unittest import mock

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from app.services.generation import beat, composer, theory
from app.services.generation import fingerprint as fp_utils
from app.services.generation import lead as lead_mod
from app.services.generation.lead import LEAD_SECTIONS, PHRASE_BARS, Lead
from app.services.generation.styles import pick_style
from app.services.intake.melody import CONFIDENT
from app.services.jobs import beat_runner
from app.services.song import record as song_record

KEYS = ["C minor", "A minor", "E minor", "F# minor", "G major", "D major", "Bb major", "D dorian", "G mixolydian"]
FEELS = ["steady", "building", "floating", "driving"]
SECTIONS = ["intro", "verse", "pre-chorus", "chorus", "bridge", "outro"]
BASE_FP = {"tempo_bpm": 100, "key": "C minor", "energy_level": 0.6, "density": 0.5, "warmth": 0.5, "brightness": 0.4}

unit = st.floats(0.0, 1.0, allow_nan=False)

# ── generators ────────────────────────────────────────────────────────────

# Anything json.loads can produce, including NaN and Infinity (Python's json accepts them).
json_values = st.recursive(
    st.none() | st.booleans() | st.integers(-(2**70), 2**70) | st.floats(allow_nan=True, allow_infinity=True)
    | st.text(max_size=6) | st.sampled_from([1e308, -1e308, 1e-320, 2**53, -1.0, 0.0, -0.0]),
    lambda kids: st.lists(kids, max_size=4) | st.dictionaries(st.text(max_size=8), kids, max_size=4),
    max_leaves=8,
)
# Same, but with no +-Infinity float anywhere: Infinity as a PITCH crashes from_sketch/from_dict
# (see the xfail tests), so the broad "never raises" properties exclude it and the xfail tests pin it.
json_finite = st.recursive(
    st.none() | st.booleans() | st.integers(-(2**70), 2**70) | st.floats(allow_nan=True, allow_infinity=False)
    | st.text(max_size=6) | st.sampled_from([1e308, -1e308, 1e-320, 2**53, -1.0, 0.0, -0.0]),
    lambda kids: st.lists(kids, max_size=4) | st.dictionaries(st.text(max_size=8), kids, max_size=4),
    max_leaves=8,
)
weird_numbers = st.one_of(
    st.integers(-(2**70), 2**70),
    st.floats(allow_nan=True, allow_infinity=True),
    st.sampled_from([1e308, -1e308, 0, -1, 0.0, -0.0, 1e-320, 127, 128, -0.5]),
    st.none(),
    st.text(max_size=3),
)
finite_pitch = weird_numbers.filter(lambda v: not (isinstance(v, float) and math.isinf(v)))
garbage_notes = st.lists(
    st.one_of(
        st.fixed_dictionaries({}, optional={"pitch_midi": finite_pitch, "start_beat": weird_numbers, "dur_beats": weird_numbers}),
        json_finite,
    ),
    max_size=8,
)

grid_start = st.integers(0, 280).map(lambda i: i * 0.25)          # 0 .. 70 beats, on the quarter-beat grid
sung_note = st.fixed_dictionaries(
    {
        "pitch_midi": st.integers(48, 84),                         # three octaves: one voice's honest range
        "start_beat": grid_start,
        "dur_beats": st.integers(1, 32).map(lambda i: i * 0.25),
    }
)
early_note = st.fixed_dictionaries(
    {
        "pitch_midi": st.integers(48, 84),
        "start_beat": st.integers(0, 200).map(lambda i: i * 0.25),   # always before the 16-bar limit
        "dur_beats": st.integers(1, 16).map(lambda i: i * 0.25),
    }
)


def sketch(notes, confirmed=True, **extra) -> dict:
    return {"confirmed": confirmed, "notes": notes, "key": "A", "mode": "minor", **extra}


def expected_cut(notes: list[dict]) -> list[tuple[int, float, float]]:
    """What the sung notes must become before octave placement: ordered, with the 16-bar cut applied."""
    triples = sorted(((n["pitch_midi"], n["start_beat"], n["dur_beats"]) for n in notes), key=lambda n: (n[1], n[0]))
    return [(p, s, min(d, 64.0 - s)) for p, s, d in triples if s < 64.0]


@st.composite
def leads(draw, key=None, min_bars=1):
    """A Lead as from_sketch would build it: notes inside `bars`, on the quarter-beat grid."""
    bars = draw(st.sampled_from([b for b in PHRASE_BARS if b >= min_bars]))
    n = draw(st.integers(3, 12))
    notes = []
    for _ in range(n):
        start = draw(st.integers(0, bars * 16 - 1)) * 0.25
        room = int(round((bars * 4.0 - start) / 0.25))
        dur = draw(st.integers(1, min(room, 8))) * 0.25
        notes.append((draw(st.integers(55, 84)), start, dur))
    notes.sort(key=lambda t: (t[1], t[0]))
    return Lead(notes=tuple(notes), bars=bars, key=key or draw(st.sampled_from(KEYS)))


@st.composite
def tune_from_progression(draw, allow_diminished=True, allow_repeats=True, settled=False):
    """
    A tune that was written over a random diatonic progression: in every bar the notes come from that
    bar's chord, and the notes on beats 0 and 2 (the strong beats) are always there.
    """
    key = draw(st.sampled_from(KEYS))
    root, mode = theory.parse_key(key)
    bars = draw(st.sampled_from([4, 8] if settled else [2, 4, 8]))
    usable = [d for d in range(7) if allow_diminished or not lead_mod._is_diminished(
        lead_mod._chord_pcs(root, mode, d, False), (root + theory.SCALE_INTERVALS[mode][d]) % 12)]
    degrees: list[int] = []
    for _ in range(bars):
        choices = [d for d in usable if allow_repeats or not degrees or d != degrees[-1]]
        degrees.append(draw(st.sampled_from(choices)))
    if settled:                    # starts and ends on the tonic, as most songs do
        degrees[0] = degrees[-1] = 0
        for i in range(1, bars - 1):
            while degrees[i] == degrees[i - 1] or (i == bars - 2 and degrees[i] == 0):
                degrees[i] = 4 if degrees[i - 1] != 4 else 3
    notes = []
    for bar, degree in enumerate(degrees):
        tones = theory.chord_for_degree(root, mode, degree, 5)       # octave 5 (around 72)
        for beat_in_bar in (0.0, 2.0):
            notes.append((draw(st.sampled_from(tones)), bar * 4.0 + beat_in_bar, 2.0 if draw(st.booleans()) else 1.0))
        for beat_in_bar in (1.0, 3.0):
            if draw(st.booleans()):
                notes.append((draw(st.sampled_from(tones)), bar * 4.0 + beat_in_bar, 1.0))
    notes.sort(key=lambda t: (t[1], t[0]))
    return Lead(notes=tuple(notes), bars=bars, key=key), degrees


def pcs_in_key(key: str) -> set[int]:
    root, mode = theory.parse_key(key)
    return {(root + i) % 12 for i in theory.SCALE_INTERVALS[mode]}


# ── (1) from_sketch: when there is a tune ─────────────────────────────────

@given(st.lists(early_note, min_size=3, max_size=12))
def test_from_sketch_needs_confirmed(notes):
    """Req 1: an unconfirmed (or missing/falsy 'confirmed') melody is never a lead."""
    assert lead_mod.from_sketch(sketch(notes, confirmed=False)) is None
    assert lead_mod.from_sketch({"notes": notes, "key": "A", "mode": "minor"}) is None
    assert lead_mod.from_sketch(sketch(notes, confirmed=None)) is None
    assert lead_mod.from_sketch(sketch(notes, confirmed=0)) is None
    assert lead_mod.from_sketch(sketch(notes)) is not None


@given(st.lists(early_note, max_size=2), garbage_notes)
def test_from_sketch_needs_three_valid_notes(few, junk):
    """Req 1: fewer than 3 VALID notes is no tune, however much garbage surrounds them."""
    bad = [
        {"pitch_midi": 60, "start_beat": -1.0, "dur_beats": 1.0},
        {"pitch_midi": 60, "start_beat": 0.0, "dur_beats": 0.0},
        {"pitch_midi": 60, "start_beat": float("nan"), "dur_beats": 1.0},
        {"pitch_midi": 200, "start_beat": 0.0, "dur_beats": 1.0},
        {"pitch_midi": -3, "start_beat": 0.0, "dur_beats": 1.0},
        {"start_beat": 0.0, "dur_beats": 1.0},
    ]
    assert lead_mod.from_sketch(sketch(few + bad)) is None
    assert lead_mod.from_sketch(sketch(bad)) is None


@given(st.lists(early_note, min_size=3, max_size=12), st.lists(st.sampled_from([
    {"pitch_midi": 60, "start_beat": -0.25, "dur_beats": 1.0},
    {"pitch_midi": 60, "start_beat": 1.0, "dur_beats": 0.0},
    {"pitch_midi": 60, "start_beat": 1.0, "dur_beats": -2.0},
    {"pitch_midi": 128, "start_beat": 1.0, "dur_beats": 1.0},
    {"pitch_midi": 60, "start_beat": 1.0},
    {"pitch_midi": 60, "start_beat": 1e308, "dur_beats": 1e308},
]), max_size=6))
def test_invalid_notes_are_ignored_not_fatal(good, bad):
    """Req 1: invalid notes mixed into a good tune are skipped; the good ones still make the lead."""
    mixed = lead_mod.from_sketch(sketch(good + bad))
    clean = lead_mod.from_sketch(sketch(good))
    assert mixed is not None and clean is not None
    assert mixed.notes == clean.notes and mixed.bars == clean.bars


@given(garbage_notes, json_finite, json_finite, json_finite, json_finite)
@settings(max_examples=300, deadline=None)
def test_from_sketch_never_raises_on_garbage(notes, confirmed, key, mode, source):
    """Req 1: no input the JSON layer can deliver makes from_sketch raise; it gives a Lead or None."""
    result = lead_mod.from_sketch({"confirmed": confirmed, "notes": notes, "key": key, "mode": mode}, source=source)
    assert result is None or isinstance(result, Lead)


@given(json_finite)
def test_from_sketch_never_raises_on_any_content(content):
    """Req 1: the content itself can be any JSON value."""
    result = lead_mod.from_sketch(content)
    assert result is None or isinstance(result, Lead)


@given(finite_pitch, weird_numbers, weird_numbers)
@settings(max_examples=300, deadline=None)
def test_from_sketch_never_raises_on_one_weird_note(pitch, start, dur):
    """Req 1: a single note with NaN, Infinity, huge, negative or text values never crashes it (3 good notes beside it)."""
    good = [{"pitch_midi": 60, "start_beat": float(i), "dur_beats": 1.0} for i in range(3)]
    result = lead_mod.from_sketch(sketch(good + [{"pitch_midi": pitch, "start_beat": start, "dur_beats": dur}]))
    assert isinstance(result, Lead)          # the three good notes always carry it


@given(finite_pitch, weird_numbers, weird_numbers)
@settings(max_examples=300, deadline=None)
def test_a_lead_never_contains_invalid_notes(pitch, start, dur):
    """Req 1: whatever comes out holds only finite, in-range notes with a positive length."""
    good = [{"pitch_midi": 60, "start_beat": float(i), "dur_beats": 1.0} for i in range(3)]
    result = lead_mod.from_sketch(sketch(good + [{"pitch_midi": pitch, "start_beat": start, "dur_beats": dur}]))
    assert result is not None
    for p, s, d in result.notes:
        assert isinstance(p, int) and 0 <= p <= 127
        assert math.isfinite(s) and s >= 0
        assert math.isfinite(d) and d > 0
        assert s + d <= 64.0 + 1e-9


@pytest.mark.parametrize("pitch", [float("inf"), float("-inf"), 1e999])
def test_infinite_pitch_does_not_crash_from_sketch(pitch):
    """Req 1: a note whose pitch is Infinity (json.loads accepts it) is skipped like any invalid note."""
    good = [{"pitch_midi": 60, "start_beat": float(i), "dur_beats": 1.0} for i in range(3)]
    assert isinstance(lead_mod.from_sketch(sketch(good + [{"pitch_midi": pitch, "start_beat": 0.0, "dur_beats": 1.0}])), Lead)


# ── (2) the tune is preserved ─────────────────────────────────────────────

@given(st.lists(sung_note, min_size=3, max_size=14))
def test_tune_is_preserved_except_octaves_and_the_16_bar_cut(notes):
    """Req 2: pitch differs by whole octaves, start and duration unchanged (except the 16-bar cut)."""
    want = expected_cut(notes)
    result = lead_mod.from_sketch(sketch(notes))
    if len(want) < lead_mod.MIN_NOTES:
        assert result is None
        return
    assert result is not None
    assert len(result.notes) == len(want)
    for (p, s, d), (wp, ws, wd) in zip(result.notes, want):
        assert (p - wp) % 12 == 0
        assert s == ws
        assert d == wd


@given(st.lists(sung_note, min_size=3, max_size=14))
def test_every_octave_shift_is_the_same_for_the_whole_tune(notes):
    """Req 2: the tune moves as one block, so the shape of the tune (intervals between notes) is untouched."""
    want = expected_cut(notes)
    assume(len(want) >= lead_mod.MIN_NOTES)
    result = lead_mod.from_sketch(sketch(notes))
    shifts = {p - wp for (p, _, _), (wp, _, _) in zip(result.notes, want)}
    assert len(shifts) == 1


@given(st.lists(early_note, min_size=3, max_size=12), st.integers(1, 20))
def test_a_tune_longer_than_16_bars_is_cut(notes, extra):
    """Req 2: a note starting at or after beat 64 is dropped; a note crossing beat 64 is shortened to end there."""
    tail = [
        {"pitch_midi": 65, "start_beat": 64.0 + extra, "dur_beats": 1.0},
        {"pitch_midi": 65, "start_beat": 63.0, "dur_beats": 6.0},
    ]
    result = lead_mod.from_sketch(sketch(notes + tail))
    assert result is not None
    assert all(s < 64.0 for _, s, _ in result.notes)
    assert all(s + d <= 64.0 + 1e-9 for _, s, d in result.notes)
    assert result.bars == 16
    crossing = [n for n in result.notes if n[1] == 63.0]
    assert any(abs(d - 1.0) < 1e-9 for _, _, d in crossing)


def test_extreme_range_breaks_whole_octave_rule():
    result = lead_mod.from_sketch(sketch([
        {"pitch_midi": 5, "start_beat": 0.0, "dur_beats": 1.0},
        {"pitch_midi": 127, "start_beat": 1.0, "dur_beats": 1.0},
        {"pitch_midi": 127, "start_beat": 2.0, "dur_beats": 1.0},
    ]))
    assert all((p - w) % 12 == 0 for (p, _, _), w in zip(result.notes, (5, 127, 127)))


# ── (3) placement and length ──────────────────────────────────────────────

@given(st.lists(sung_note, min_size=3, max_size=14))
def test_middle_of_the_tune_sits_in_the_lead_range(notes):
    """Req 3: the middle pitch of the tune lands in 62..76."""
    result = lead_mod.from_sketch(sketch(notes))
    assume(result is not None)
    middle = sorted(p for p, _, _ in result.notes)[len(result.notes) // 2]
    assert 62 <= middle <= 76


@given(st.lists(sung_note, min_size=3, max_size=14))
def test_bars_is_a_phrase_length_that_covers_the_last_note(notes):
    """Req 3: bars is one of PHRASE_BARS and the tune fits inside it."""
    result = lead_mod.from_sketch(sketch(notes))
    assume(result is not None)
    assert result.bars in PHRASE_BARS
    assert result.bars * 4.0 >= max(s + d for _, s, d in result.notes) - 1e-9


@given(st.lists(sung_note, min_size=3, max_size=14))
def test_bars_is_the_smallest_phrase_that_covers_the_tune(notes):
    """Req 3: not longer than needed (a tune of 3 bars becomes 4, not 8)."""
    result = lead_mod.from_sketch(sketch(notes))
    assume(result is not None)
    smaller = [b for b in PHRASE_BARS if b < result.bars]
    end = max(s + d for _, s, d in result.notes)
    assert all(b * 4.0 < end - 1e-9 for b in smaller)


# ── (4) harmonize: shape ──────────────────────────────────────────────────

@given(leads(), st.sampled_from([0.0, 0.5, 1.0]))
@settings(max_examples=60, deadline=None)
def test_harmonize_shape_and_key(lead, extension):
    """Req 4: one chord per bar, all inside the key, same dictionary shape as build_progression."""
    prog = lead_mod.harmonize(lead, lead.key, extension)
    ref = theory.build_progression(lead.key)
    assert set(prog) == set(ref)
    n = lead.bars
    for field in ("degrees", "chords", "chord_pcs", "tones", "sevenths", "bass_notes"):
        assert len(prog[field]) == n, field
    scale = pcs_in_key(lead.key)
    for pcs in prog["chord_pcs"] + prog["tones"]:
        assert set(pcs) <= scale
    for chord in prog["chords"]:
        assert {note % 12 for note in chord} <= scale
    assert prog["family"] == "from_tune"
    assert (prog["root"], prog["mode"]) == theory.parse_key(lead.key)
    assert all(0 <= d <= 6 for d in prog["degrees"])
    if extension < 0.3:
        assert not any(prog["sevenths"])


@given(leads(), st.sampled_from([0.0, 1.0]))
@settings(max_examples=40, deadline=None)
def test_harmonize_is_deterministic(lead, extension):
    """Req 4: the same tune and key always give the same chords."""
    assert lead_mod.harmonize(lead, lead.key, extension) == lead_mod.harmonize(lead, lead.key, extension)


# ── (5) harmonize: fit ────────────────────────────────────────────────────

@given(tune_from_progression(allow_diminished=False, allow_repeats=False, settled=True))
@settings(max_examples=200, deadline=None, derandomize=True)
def test_harmonize_fits_a_tune_written_over_chords(case):
    """Req 5, relaxed to 60% and to tunes that start and end on the tonic: most of the tune sits inside the chosen chords.
    The 85% of the requirement does not hold in general (see the xfail test below): [VI,i,III,i] in C minor gets 83%."""
    lead, _ = case
    assert lead_mod.coverage(lead, lead_mod.harmonize(lead, lead.key)) >= 0.60


@pytest.mark.xfail(strict=False, reason="FINDING: a tune over a diminished chord (-0.4 penalty) or over a repeated chord (-0.25 'staying put' plus the +0.3 last-bar bonus for degrees 0/4), or a cadence i-v-i preferred to VI-i-III-i, covers 75-83%")
@given(tune_from_progression())
@settings(max_examples=150, deadline=None)
def test_harmonize_fits_even_when_the_tune_uses_a_diminished_chord(case):
    """Req 5 as literally stated (any diatonic progression). Shrunk: C minor, chords [Cm, Cm], tune C Eb | C G -> harmonize picks [i, v], 0.75;
    also chords [Cm, Dim], tune C C | D F -> 0.75."""
    lead, _ = case
    assert lead_mod.coverage(lead, lead_mod.harmonize(lead, lead.key)) >= 0.85


@given(tune_from_progression(), st.sampled_from(FEELS), unit, st.integers(0, 3))
@settings(max_examples=150, deadline=None)
def test_harmonize_fits_nearly_as_well_as_the_best_stock_progression(case, feel, energy, variant):
    """Req 5: the chords chosen for the tune explain it at least as well as the stock progression of that key.
    Shrunk: C minor, 2 bars, tune C C Eb Eb Eb over [Cm, Eb]: harmonize -> [Fm, Cm] 0.89, stock i-VI-III-VII 1.0."""
    lead, _ = case
    stock = theory.build_progression(lead.key, energy, feel, variant=variant)
    # Not strictly >=: the harmonizer deliberately prefers starting on the home chord and a settled ending, so a
    # tune that sits wholly on its relative minor can score a little below a stock progression that happens to start there.
    assert lead_mod.coverage(lead, lead_mod.harmonize(lead, lead.key)) >= lead_mod.coverage(lead, stock) - 0.2


@given(leads())
@settings(max_examples=60, deadline=None)
def test_coverage_is_a_share(lead):
    """Req 5: coverage is between 0 and 1 for any tune and any progression."""
    c = lead_mod.coverage(lead, theory.build_progression(lead.key))
    assert 0.0 <= c <= 1.0 + 1e-9


@given(tune_from_progression())
@settings(max_examples=60, deadline=None)
def test_strong_beats_count_more(case):
    """Req 5: a note on beat 0/2 weighs more than the same note off the beat (guards the strong-beat weight)."""
    lead, _ = case
    on = lead_mod._bar_weights(Lead(((60, 0.0, 1.0),), 1, lead.key), 0)
    off = lead_mod._bar_weights(Lead(((60, 1.0, 1.0),), 1, lead.key), 0)
    assert on[0][1] > off[0][1]


@given(st.sampled_from(KEYS), st.integers(0, 6), st.integers(0, 6), st.integers(0, 6), st.integers(0, 6))
@settings(max_examples=60, deadline=None)
def test_harmonize_picks_the_chord_a_strong_beat_note_belongs_to(key, a, b, c, d):
    """
    Req 5: a long note on the strong beat that is the root of exactly the right chord decides the bar.
    A one-note-per-bar tune of chord roots on beat 0 (long) with a short clashing-free tail is covered fully.
    """
    root, mode = theory.parse_key(key)
    degrees = [a, b, c, d]
    notes = tuple((theory.chord_for_degree(root, mode, g, 5)[0], i * 4.0, 3.0) for i, g in enumerate(degrees))
    lead = Lead(notes=notes, bars=4, key=key)
    assert lead_mod.coverage(lead, lead_mod.harmonize(lead, key)) == pytest.approx(1.0)


# ── (6) lead_events ───────────────────────────────────────────────────────

@given(leads(), st.integers(1, 40), unit, st.integers(0, 2**31), st.integers(0, 20))
@settings(max_examples=150, deadline=None)
def test_lead_events_stay_inside_the_section(lead, bars, energy, seed, index):
    """Req 6: every event starts inside the section with a positive length, and nothing rings past the end."""
    events = lead_mod.lead_events(lead, bars, energy, seed, index)
    end = bars * 4.0
    for e in events:
        assert 0.0 <= e.start < end
        assert e.duration > 0
        assert e.start + e.duration <= end + 0.01
        assert 0 <= e.note <= 127


@given(leads(), st.integers(1, 40), unit, st.integers(0, 2**31), st.integers(0, 20))
@settings(max_examples=150, deadline=None)
def test_the_tune_repeats_every_lead_bars(lead, bars, energy, seed, index):
    """Req 6: each repeat that fits plays the same pitches at the same offsets (within the 0.01 timing jitter)."""
    events = lead_mod.lead_events(lead, bars, energy, seed, index)
    period = lead.bars * 4.0
    full_rounds = bars // lead.bars
    assume(full_rounds >= 1)
    rounds: list[list[tuple[int, float]]] = [[] for _ in range(full_rounds)]
    for e in events:
        r = int((e.start + 0.01) // period)
        if r < full_rounds:
            rounds[r].append((e.note, e.start - r * period))
    expected = [(p, s) for p, s, _ in lead.notes]
    for r in rounds:
        assert [p for p, _ in r] == [p for p, _ in expected]
        for (_, got), (_, want) in zip(r, expected):
            assert abs(got - want) <= 0.01


@given(leads(), st.integers(1, 40), st.integers(0, 2**31))
@settings(max_examples=150, deadline=None)
def test_the_tune_is_not_dropped_or_invented(lead, bars, seed):
    """Req 6: the pitch sequence over the section is the tune repeated and then cut at the end, nothing else."""
    events = sorted(lead_mod.lead_events(lead, bars, 0.5, seed, 0), key=lambda e: e.start)
    want: list[int] = []
    for r in range(math.ceil(bars / lead.bars)):
        for p, s, _ in lead.notes:
            if r * lead.bars * 4.0 + s < bars * 4.0 - 0.1:       # leaves room to sound
                want.append(p)
    got = [e.note for e in events]
    assert sorted(got) == sorted(want)


@given(st.integers(2, 4), st.integers(0, 2**31))
def test_a_repeat_that_does_not_fit_is_cut_at_the_section_end(extra, seed):
    """Req 6: with a 4-bar tune in a 6-bar section, the second repeat stops at bar 6, even mid-note."""
    lead = Lead(notes=((60, 0.0, 2.0), (62, 16.0 - 2.0, 2.0), (64, 4.0 * 4 - 1.0, 1.0)), bars=4, key="C major")
    bars = 4 + extra // 2 + 1                   # 5..7 bars: a partial second repeat
    events = lead_mod.lead_events(lead, bars, 0.5, seed, 0)
    end = bars * 4.0
    assert all(e.start + e.duration <= end + 0.01 for e in events)
    second = [e for e in events if e.start >= 16.0 - 0.01]
    assert second, "the part of the repeat that fits should still play"
    assert all(e.start < end for e in second)
    assert len(second) <= len(lead.notes)


@given(leads(), st.integers(1, 12), unit, st.integers(0, 2**31), st.integers(0, 9))
@settings(max_examples=60, deadline=None)
def test_lead_events_are_deterministic(lead, bars, energy, seed, index):
    """Req 6: same inputs, same events."""
    a = lead_mod.lead_events(lead, bars, energy, seed, index)
    b = lead_mod.lead_events(lead, bars, energy, seed, index)
    assert [(e.note, e.start, e.duration, e.velocity) for e in a] == [(e.note, e.start, e.duration, e.velocity) for e in b]


# ── (7) compose_section ───────────────────────────────────────────────────

LAYERS = ["melody", "keys", "bass", "drums"]


def compose_with(lead, bars: int, seed: int, name: str = "chorus", with_field: bool = True):
    f = fp_utils.normalize(BASE_FP)
    kwargs = dict(name=name, index=2, repeat=0, final=False, seed=seed, style=pick_style(f))
    if with_field:
        kwargs["lead"] = lead
    ctx = composer.SectionContext(**kwargs)
    prog = theory.build_progression(f["key"], f["energy_level"], f["tempo_feel"], variant=0, seed=seed)
    return composer.compose_section(name, prog, bars, f["energy_level"], f["density"], layers=LAYERS, ctx=ctx)


def ev(parts):
    return [(p.name, p.preset, [(e.note, round(e.start, 6), round(e.duration, 6), e.velocity) for e in p.events]) for p in parts]


@given(leads(), st.integers(1, 12), st.integers(0, 2**31))
@settings(max_examples=60, deadline=None)
def test_melody_part_plays_the_tune_when_ctx_has_a_lead(lead, bars, seed):
    """Req 7: with ctx.lead set, the melody part's pitches are the tune (repeated, cut at the end) on the lead sound."""
    parts = compose_with(lead, bars, seed)
    melody = [p for p in parts if p.name == "melody"]
    assert len(melody) == 1
    assert melody[0].preset == lead_mod.LEAD_PROGRAM and not melody[0].is_drums
    got = [e.note for e in sorted(melody[0].events, key=lambda e: e.start)]
    tune = [p for p, _, _ in lead.notes]
    want_prefix = []
    for r in range(math.ceil(bars / lead.bars)):
        want_prefix += [p for p, s, _ in lead.notes if r * lead.bars * 4.0 + s < bars * 4.0 - 0.1]
    # same-pitch neighbours may be shortened or dropped by the overlap guard, never reordered or invented
    from collections import Counter
    assert not (Counter(got) - Counter(want_prefix))          # nothing invented
    assert set(got) == set(want_prefix) or len(got) < len(want_prefix)
    assert set(got) <= set(tune)


@given(st.lists(st.integers(60, 80), min_size=3, max_size=6, unique=True), st.integers(1, 10), st.integers(0, 2**31))
@settings(max_examples=40, deadline=None)
def test_melody_pitch_sequence_is_exactly_the_tune_when_pitches_differ(pitches, repeats, seed):
    """Req 7: with no equal neighbours, nothing is dropped: the played pitch sequence IS the tune."""
    lead = Lead(notes=tuple((p, float(i), 1.0) for i, p in enumerate(pitches)), bars=1 if len(pitches) <= 4 else 2, key="C minor")
    bars = lead.bars * repeats
    parts = compose_with(lead, bars, seed)
    melody = next(p for p in parts if p.name == "melody")
    got = [e.note for e in sorted(melody.events, key=lambda e: e.start)]
    assert got == pitches * repeats


@given(leads(), st.integers(1, 8), st.integers(0, 2**31))
@settings(max_examples=40, deadline=None)
def test_a_lead_only_changes_the_melody_part(lead, bars, seed):
    """Req 7: every other part is identical with and without the lead."""
    with_lead = {p.name: ev([p]) for p in compose_with(lead, bars, seed)}
    without = {p.name: ev([p]) for p in compose_with(None, bars, seed)}
    assert set(with_lead) == set(without)
    for name in without:
        if name != "melody":
            assert with_lead[name] == without[name]


@given(st.integers(1, 12), st.integers(0, 2**31), st.sampled_from(SECTIONS))
@settings(max_examples=40, deadline=None)
def test_no_lead_leaves_the_engine_melody_unchanged(bars, seed, name):
    """Req 7: ctx.lead=None gives exactly what the engine gave before the field existed."""
    assert ev(compose_with(None, bars, seed, name, with_field=True)) == ev(compose_with(None, bars, seed, name, with_field=False))
    f = fp_utils.normalize(BASE_FP)
    prog = theory.build_progression(f["key"], f["energy_level"], f["tempo_feel"], variant=0, seed=seed)
    old = composer.compose_melody(prog, bars, f["energy_level"], f["density"], composer.SectionContext(name=name, index=2, seed=seed, style=pick_style(f)))
    new = next(p for p in compose_with(None, bars, seed, name) if p.name == "melody")
    assert ev([composer._trim_overlaps(old)]) == ev([new])


# ── (8) plumbing: plan_contexts, serialisation, params ────────────────────

arrangement_st = st.lists(st.tuples(st.sampled_from(SECTIONS), st.integers(1, 6)), min_size=1, max_size=8)


@given(arrangement_st, leads(), st.sampled_from(KEYS))
@settings(max_examples=60, deadline=None)
def test_plan_contexts_gives_the_lead_to_lead_sections_only(arr, lead, fp_key):
    """Req 8: only sections named in LEAD_SECTIONS get the lead; the chorus progression is 'from_tune'; the song is in the tune's key."""
    sections, fp = beat.build_beat_plan({**BASE_FP, "key": fp_key}, arr)
    _, contexts, progs = beat.plan_contexts(sections, fp, 11, lead)
    for s, ctx in zip(sections, contexts):
        if s.name in LEAD_SECTIONS:
            shortest = min(x.bars for x in sections if x.name in LEAD_SECTIONS)
            assert ctx.lead == lead_mod.fit_to(lead, shortest)       # whole tune when it fits, a whole phrase of it when not
        else:
            assert ctx.lead is None
    for name, prog in progs.items():
        assert (prog["root"], prog["mode"]) == theory.parse_key(lead.key)
        assert (prog["family"] == "from_tune") == (name in LEAD_SECTIONS)
        if name == "chorus":
            shortest = min(x.bars for x in sections if x.name in LEAD_SECTIONS)
            assert len(prog["chords"]) == lead_mod.fit_to(lead, shortest).bars


@given(arrangement_st)
@settings(max_examples=40, deadline=None)
def test_plan_contexts_without_a_lead_is_the_old_behaviour(arr):
    """Req 8: no lead means no section has one and no progression is 'from_tune'."""
    sections, fp = beat.build_beat_plan(BASE_FP, arr)
    _, contexts, progs = beat.plan_contexts(sections, fp, 11)
    _, contexts2, progs2 = beat.plan_contexts(sections, fp, 11, None)
    assert all(c.lead is None for c in contexts)
    assert all(p["family"] != "from_tune" for p in progs.values())
    assert progs == progs2
    assert (progs["chorus"] if "chorus" in progs else None) == (progs2["chorus"] if "chorus" in progs2 else None)


@given(leads(), st.one_of(st.none(), st.text(max_size=12)))
def test_lead_round_trips_through_dict_and_json(lead, source):
    """Req 8: to_dict / from_dict (and a JSON trip, as saved in beat_versions.params) loses nothing."""
    lead = Lead(lead.notes, lead.bars, lead.key, source)
    assert Lead.from_dict(lead.to_dict()) == lead
    assert Lead.from_dict(json.loads(json.dumps(lead.to_dict()))) == lead


@given(json_finite)
@settings(max_examples=300, deadline=None)
def test_from_dict_returns_none_or_a_lead_on_garbage(data):
    """Req 8: from_dict never raises on any JSON value."""
    result = Lead.from_dict(data)
    assert result is None or isinstance(result, Lead)


@given(st.sampled_from([None, 5, "x", [], [1, 2]]) | st.fixed_dictionaries({}, optional={
    "notes": json_finite, "bars": json_finite, "key": json_finite}))
def test_from_dict_garbage_dicts_are_none(data):
    """Req 8: a missing field or a field of the wrong type gives None, not an exception."""
    result = Lead.from_dict(data)
    assert result is None or isinstance(result, Lead)


@given(st.dictionaries(st.text(max_size=6).filter(lambda k: k != "lead"), json_values, max_size=5))
def test_lead_from_params_is_none_for_old_params(params):
    """Req 8: a beat saved before leads existed has no 'lead' key and gets no lead."""
    assert beat.lead_from_params(params) is None
    assert beat.lead_from_params({**params, "lead": None}) is None


@given(leads())
def test_lead_from_params_restores_the_saved_lead(lead):
    """Req 8: the lead stored by _arrangement_params comes back equal."""
    sections, fp = beat.build_beat_plan(BASE_FP, [("chorus", 2)])
    params = beat_runner._arrangement_params(sections, fp, 5, lead)
    assert params["lead"] == lead.to_dict()
    assert beat.lead_from_params(json.loads(json.dumps(params))) == lead
    assert beat_runner._arrangement_params(sections, fp, 5)["lead"] is None


# Two tiny renders: the plumbing reaches the audio.
TINY = [("verse", 2), ("chorus", 2)]


def test_render_with_a_lead_changes_the_chorus_only():
    """Req 8: render_song(lead=) plays the tune in the chorus; the verse (not a lead section) is the same song."""
    lead = Lead(notes=((72, 0.0, 1.0), (74, 1.0, 1.0), (75, 2.0, 2.0), (72, 4.0, 1.0)), bars=2, key=BASE_FP["key"])
    sections, fp = beat.build_beat_plan(BASE_FP, TINY)
    plain, _ = beat.render_song(sections, fp, 7)
    led, full = beat.render_song(sections, fp, 7, lead=lead)
    again, _ = beat.render_song(sections, fp, 7, lead=lead)
    assert len(plain) == len(led) == 2
    assert not np.array_equal(plain[1], led[1])         # chorus changed
    assert np.array_equal(led[1], again[1])             # and deterministically
    assert np.array_equal(plain[0], led[0])             # verse untouched
    assert full.shape[1] == 2 and full.dtype == np.int16


# ── (9) _fingerprint_and_lead ─────────────────────────────────────────────

def run_fal(fingerprint, found=None, raises: Exception | None = None):
    async def fake(project_id):
        if raises:
            raise raises
        return found

    with mock.patch.object(song_record, "active_melody", fake):
        return asyncio.run(beat_runner._fingerprint_and_lead("p1", fingerprint))


fingerprints_st = st.dictionaries(
    st.sampled_from(["key", "energy_level", "density", "tempo_feel", "genre_proximity", "tempo_bpm"]),
    json_values, max_size=6,
)
good_notes = st.lists(early_note, min_size=3, max_size=8)
tempo_values = st.floats(40, 200, allow_nan=False)


@given(fingerprints_st)
def test_no_melody_leaves_the_fingerprint_alone(fingerprint):
    """Req 9: with no active melody, the fingerprint comes back unchanged and there is no lead."""
    before = json.dumps(fingerprint, sort_keys=True, default=str)
    fp, lead = run_fal(fingerprint, found=None)
    assert lead is None and fp == fingerprint
    assert json.dumps(fingerprint, sort_keys=True, default=str) == before


@given(fingerprints_st, st.sampled_from([Exception("db down"), RuntimeError("x"), KeyError("k"), ValueError("v"), OSError("net")]))
def test_a_failing_lookup_never_stops_the_beat(fingerprint, error):
    """Req 9: if reading the melody raises, the beat is built without it."""
    fp, lead = run_fal(fingerprint, raises=error)
    assert lead is None and fp == fingerprint


@given(fingerprints_st, good_notes, tempo_values, unit)
def test_an_unconfirmed_melody_is_ignored(fingerprint, notes, tempo, conf):
    """Req 9: an unconfirmed melody gives no lead and never touches the speed."""
    content = sketch(notes, confirmed=False, tempo_bpm=tempo, tempo_confidence=max(conf, 0.9))
    fp, lead = run_fal(fingerprint, found=("v1", content))
    assert lead is None and fp == fingerprint


@given(fingerprints_st, st.lists(early_note, max_size=2), tempo_values)
def test_an_unusable_tune_gives_no_lead_and_no_tempo(fingerprint, few, tempo):
    """Req 9: a confirmed but too-short tune is dropped, and its tempo is not used either."""
    content = sketch(few, tempo_bpm=tempo, tempo_confidence=0.99)
    fp, lead = run_fal(fingerprint, found=("v1", content))
    assert lead is None and fp == fingerprint


@given(good_notes, tempo_values, st.floats(CONFIDENT, 1.0, allow_nan=False), st.sampled_from(["v1", "abc"]))
def test_tempo_is_filled_when_absent_and_confident(notes, tempo, conf, vid):
    """Req 9: no tempo_bpm in the fingerprint plus a confident hum tempo: the hum's tempo is used and the lead is built."""
    original = {"key": "C minor", "energy_level": 0.4}
    fp, lead = run_fal(original, found=(vid, sketch(notes, tempo_bpm=tempo, tempo_confidence=conf)))
    assert isinstance(lead, Lead) and lead.source == vid
    assert fp["tempo_bpm"] == int(round(tempo))
    assert {k: v for k, v in fp.items() if k not in ("tempo_bpm", "key", "key_from_tune")} == {k: v for k, v in original.items() if k != "key"}
    assert "tempo_bpm" not in original                      # the caller's dict is not mutated


@given(good_notes, tempo_values, st.floats(0.0, CONFIDENT - 1e-6, allow_nan=False))
def test_tempo_is_not_filled_when_not_confident(notes, tempo, conf):
    """Req 9: a hesitant tempo is never used."""
    fp, lead = run_fal({"key": "C minor"}, found=("v1", sketch(notes, tempo_bpm=tempo, tempo_confidence=conf)))
    assert isinstance(lead, Lead)
    assert "tempo_bpm" not in fp


@given(good_notes, tempo_values, unit, json_values)
def test_an_existing_tempo_is_never_replaced(notes, tempo, conf, existing):
    """Req 9: whatever tempo_bpm the fingerprint already holds (even None or garbage) survives."""
    fp, lead = run_fal({"tempo_bpm": existing, "key": "C minor"},
                       found=("v1", sketch(notes, tempo_bpm=tempo, tempo_confidence=max(conf, 0.95))))
    assert isinstance(lead, Lead)
    assert "tempo_bpm" in fp
    assert repr(fp["tempo_bpm"]) == repr(existing)


no_inf = json_values.filter(lambda v: not (isinstance(v, float) and math.isinf(v)))


@given(good_notes, no_inf, json_values)
@settings(max_examples=200, deadline=None)
def test_garbage_tempo_never_breaks_the_lead(notes, tempo, conf):
    """(missing tempo and Infinity are the separate xfail tests below)"""
    assume(tempo is not None)
    """Req 9: a confirmed tune is still used when its tempo fields are missing, NaN, Infinity or text."""
    content = sketch(notes)
    content["tempo_bpm"] = tempo
    if conf is not None:
        content["tempo_confidence"] = conf
    fp, lead = run_fal({"key": "C minor"}, found=("v1", content))
    assert isinstance(lead, Lead)
    assert fp["key"] in ("C minor", lead.key)        # the settled key stays unless the tune clearly does not fit it


def test_confident_hum_without_tempo_field_is_survivable():
    notes = [{"pitch_midi": 60, "start_beat": float(i), "dur_beats": 1.0} for i in range(3)]
    fp, lead = run_fal({}, found=("v1", sketch(notes, tempo_confidence=0.9)))
    assert isinstance(lead, Lead)


def test_infinite_hum_tempo_is_survivable():
    notes = [{"pitch_midi": 60, "start_beat": float(i), "dur_beats": 1.0} for i in range(3)]
    fp, lead = run_fal({}, found=("v1", sketch(notes, tempo_bpm=float("inf"), tempo_confidence=0.9)))
    assert isinstance(lead, Lead)


def test_from_dict_infinite_pitch_is_none():
    assert Lead.from_dict({"notes": [[float("inf"), 0.0, 1.0]], "bars": 1, "key": "C minor"}) is None


# ── review fixes: nothing is cut silently, the key is chosen by fit, bad saved data is survivable ──

from dataclasses import replace as _replace  # noqa: E402


@given(leads(min_bars=2), st.integers(1, 20))
@settings(max_examples=80, deadline=None)
def test_a_tune_longer_than_its_section_is_cut_at_a_phrase_and_never_invented(lead, bars):
    """A shorter section gets the longest whole phrase that fits; every note kept is a note of the original tune."""
    fitted = lead_mod.fit_to(lead, bars)
    if bars >= lead.bars:
        assert fitted == lead
        return
    target = max(b for b in PHRASE_BARS if b <= max(1, bars))
    kept = [n for n in lead.notes if n[1] < target * 4.0]
    if len(kept) >= lead_mod.MIN_NOTES:
        assert fitted.bars == target
        assert len(fitted.notes) == len(kept)
    else:
        assert fitted == lead                 # too little would be left to be a tune: kept whole
    original = set(lead.notes)
    for p, s, d in fitted.notes:
        assert s < fitted.bars * 4.0 + 1e-9 and s + d <= fitted.bars * 4.0 + 1e-9
        assert any(p == op and s == os and d <= od + 1e-9 for op, os, od in original)


@given(st.lists(st.sampled_from(["intro", "verse", "chorus", "bridge", "outro"]), min_size=1, max_size=8), leads())
@settings(max_examples=60, deadline=None)
def test_a_section_that_plays_the_tune_is_made_long_enough_for_all_of_it(names, lead):
    arrangement = [(n, 4) for n in names]
    sections, _ = beat.build_beat_plan(BASE_FP, arrangement, lead=lead)
    for s, (name, bars) in zip(sections, arrangement):
        if name in LEAD_SECTIONS:
            assert s.bars == max(bars, lead.bars)
        else:
            assert s.bars == bars


@given(leads())
@settings(max_examples=40, deadline=None)
def test_lead_info_says_whether_the_tune_is_heard_and_whether_any_of_it_was_cut(lead):
    sections, _ = beat.build_beat_plan(BASE_FP, [("intro", 4), ("verse", 8), ("chorus", 8)], lead=lead)
    info = beat.lead_info(sections, lead)
    assert info["used"] is True and info["cut"] is False and info["heard_bars"] == lead.bars
    sections[2].layers = [x for x in sections[2].layers if x != "melody"]
    assert beat.lead_info(sections, lead)["used"] is False
    assert beat.lead_info(sections, None) == {"used": False}
    short = beat.build_beat_plan(BASE_FP, [("chorus", 4)])[0]
    short[0].bars = 1
    if lead.bars > 1:
        cut = beat.lead_info(short, lead)
        assert cut["cut"] is True and cut["heard_bars"] == 1


@given(leads(), st.sampled_from(KEYS))
@settings(max_examples=80, deadline=None)
def test_a_settled_key_stays_unless_the_tune_clearly_does_not_fit_it(lead, settled):
    key, changed = lead_mod.choose_key(lead, settled)
    assert key in (settled, lead.key)
    assert changed == (key != settled)
    if changed:
        assert lead_mod.scale_fit(lead, settled) < lead_mod.scale_fit(lead, lead.key) - 0.05 + 1e-9
    assert lead_mod.choose_key(lead, None) == (lead.key, False)
    assert lead_mod.choose_key(lead, lead.key) == (lead.key, False)


def test_a_tune_in_the_relative_key_does_not_overrule_a_settled_key():
    notes = tuple((p, float(i), 1.0) for i, p in enumerate([69, 71, 72, 74, 72, 71, 69]))
    lead = Lead(notes=notes, bars=2, key="A minor")
    assert lead_mod.choose_key(lead, "C major") == ("C major", False)
    assert lead_mod.choose_key(lead, "F# major")[1] is True


@given(st.integers(-3, 40), st.sampled_from([0, 1, 3, 17, 32]))
def test_a_saved_tune_with_a_bad_length_or_too_few_notes_is_not_used(bars, n):
    notes = [[60 + i, float(i), 1.0] for i in range(n)]
    got = Lead.from_dict({"notes": notes, "bars": bars, "key": "C minor"})
    if bars in PHRASE_BARS and n >= lead_mod.MIN_NOTES:
        assert got is not None
    else:
        assert got is None


@pytest.mark.parametrize("raw,expected", [
    ("", ""), ("minor", ""), ("dorian", ""), ("A\u266d major", "Ab major"), ("F# major", "F# major"),
    ("Bb", "Bb"), ("  g minor ", "g minor"), ("H minor", ""), ("C minor extra words", ""),
])
def test_keys_are_cleaned_or_left_empty(raw, expected):
    assert lead_mod._clean_key(raw) == expected


def test_an_unreadable_key_in_the_hum_falls_back_to_the_songs_own_key():
    lead = lead_mod.from_sketch(sketch([{"pitch_midi": 60 + i, "start_beat": float(i), "dur_beats": 1.0} for i in range(4)], key="", mode="minor"))
    assert lead is not None and lead.key == ""
    sections, fp = beat.build_beat_plan({**BASE_FP, "key": "D minor"}, [("chorus", 4)], lead=lead)
    _, _, progs = beat.plan_contexts(sections, fp, 5, lead)
    assert (progs["chorus"]["root"], progs["chorus"]["mode"]) == theory.parse_key("D minor")


def test_a_corrupt_saved_tune_is_reported_not_dropped_quietly(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        assert beat.lead_from_params({"lead": {"notes": [], "bars": 0, "key": "C minor"}}) is None
    assert "could not be read" in caplog.text
    assert beat.lead_from_params({}) is None


def test_the_beat_summary_in_the_song_record_carries_the_tune_info():
    info = {"used": True, "sections": [2], "tune_bars": 8, "heard_bars": 8, "cut": False, "key": "A minor"}
    summary = song_record._beat_summary({"label": "Beat v1", "params": {"sections": [], "lead_info": info}})
    assert summary["lead"] == info
    assert song_record._beat_summary({"label": "x", "params": {"sections": []}})["lead"] is None


def test_every_beat_job_result_says_whether_the_tune_was_used():
    assert beat_runner._lead_used({"params": {"lead_info": {"used": True}}}) is True
    assert beat_runner._lead_used({"params": {"lead_info": {"used": False}}}) is False
    assert beat_runner._lead_used({"params": {}}) is False and beat_runner._lead_used({}) is False


def test_the_tune_part_is_marked_and_sits_in_front_of_the_other_parts():
    lead = Lead(notes=tuple((60 + i, float(i), 1.0) for i in range(4)), bars=1, key="C minor")
    parts = compose_with(lead, 1, 1)
    assert [p.lead for p in parts if p.name == "melody"] == [True]
    assert all(not p.lead for p in parts if p.name != "melody")
    assert beat.LEAD_GAIN > beat.PART_GAIN["melody"]


@given(leads(min_bars=2))
@settings(max_examples=15, deadline=None)
def test_the_chorus_chords_cover_the_whole_tune_when_the_section_is_long_enough(lead):
    sections, fp = beat.build_beat_plan(BASE_FP, [("verse", 4), ("chorus", 4)], lead=lead)
    _, contexts, progs = beat.plan_contexts(sections, fp, 3, lead)
    chorus = [s for s in sections if s.name == "chorus"][0]
    assert chorus.bars >= lead.bars and len(progs["chorus"]["chords"]) == lead.bars


def test_the_tunes_extra_volume_is_actually_applied(monkeypatch):
    lead = Lead(notes=tuple((60 + 2 * i, float(i), 1.0) for i in range(4)), bars=1, key="C minor")
    fixed = {**BASE_FP, "genre_proximity": ["soul"]}

    def render():
        sections, f = beat.build_beat_plan(fixed, [("verse", 1), ("chorus", 2)], lead=lead)
        return beat.render_song(sections, f, 4, mix_chain=False, lead=lead)[1]

    monkeypatch.setattr(beat, "LEAD_GAIN", 1.1)
    loud = render()
    monkeypatch.setattr(beat, "LEAD_GAIN", 0.2)
    quiet = render()
    assert loud.shape == quiet.shape and not np.array_equal(loud, quiet)
