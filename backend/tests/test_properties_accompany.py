"""
Music that plays to the singer (core-path spec 15, requirement 8), as properties over made-up sung songs with a known
speed, bar line and sections (tests/accompany_songs.py). The audio version is scripts/follow_check.py.
"""
from __future__ import annotations

import math

from hypothesis import given, settings, strategies as st

from accompany_songs import song
from app.services.generation import accompany, beat as beat_engine
from app.services.generation import fingerprint as fp_utils

speeds = st.floats(min_value=60, max_value=128, allow_nan=False)
starts = st.floats(min_value=0.3, max_value=6.0, allow_nan=False)
forms = st.sampled_from(["VCVC", "VVCVC", "VCVCC", "VCVCVC"])


def _octave_equal(found: float, true: float) -> bool:
    return any(abs(found - true * f) / (true * f) < 0.01 for f in (0.5, 1.0, 2.0))


@settings(deadline=None, max_examples=60)
@given(speeds, starts, forms)
def test_frank_finds_the_singers_speed_and_bar_line(bpm, start, form):
    notes, _ = song(bpm=bpm, start_s=start, form=form)
    g = accompany.grid_from_notes(notes)
    assert _octave_equal(g.bpm, bpm), (g.bpm, bpm)
    if abs(g.bpm - bpm) / bpm < 0.01:                    # same count: the bar line is where they sang it
        bar = 240.0 / bpm
        off = ((g.start_s - start) / bar) % 1.0
        assert min(off, 1 - off) * 4 < 0.25, (g.start_s, start)


@settings(deadline=None, max_examples=60)
@given(speeds, starts, forms)
def test_the_music_changes_where_the_singer_changes(bpm, start, form):
    notes, sung_at = song(bpm=bpm, start_s=start, form=form)
    grid = accompany.Grid(bpm, start % (240.0 / bpm))
    found = accompany.sections_from_phrases(notes, grid)
    changes_sung = [t for (n, t), (m, _) in zip(sung_at[1:], sung_at[:-1]) if n != m]
    changes_found = [s.start_s for a, s in zip(found[:-1], found[1:]) if s.name != a.name]
    assert len(changes_found) == len(changes_sung)
    for a, b in zip(changes_found, changes_sung):
        assert abs(a - b) <= grid.beat_s + 1e-6
    # and the higher, returning melody is the chorus
    assert [s.name for s in found][0] == "verse" and "chorus" in [s.name for s in found]


@settings(deadline=None, max_examples=40)
@given(speeds, starts, forms, st.floats(0.1, 0.9), st.floats(0.1, 0.9))
def test_the_plan_plays_to_the_singer(bpm, start, form, energy, density):
    notes, _ = song(bpm=bpm, start_s=start, form=form)
    grid = accompany.Grid(bpm, start % (240.0 / bpm))
    sung = accompany.sections_from_phrases(notes, grid)
    fp = fp_utils.normalize({"tempo_bpm": bpm, "energy_level": energy, "density": density})
    acc = accompany.plan(notes, grid, sung, fp)
    assert acc is not None
    secs = acc.sections
    # Their voice is the tune: no competing melody anywhere
    assert all("melody" not in s.layers for s in secs)
    # Every section has one chord per bar, all from the key
    for s in secs:
        h = s.parts["harmony"]
        assert len(h["degrees"]) == s.bars and all(0 <= d < 7 for d in h["degrees"])
    # The music lasts past their last note, and ends home
    music_end = grid.start_s + beat_engine.seconds_of_bars(sum(s.bars for s in secs), bpm)
    assert music_end >= acc.last_note_s
    assert secs[-1].name == "outro" and secs[-1].parts["harmony"]["degrees"][-1] == 0
    # Choruses are never smaller than the verses around them
    verse_e = [s.energy for s in secs if s.name == "verse"]
    chorus_e = [s.energy for s in secs if s.name == "chorus"]
    if verse_e and chorus_e:
        assert min(chorus_e) >= max(verse_e) - 1e-9 or math.isclose(min(chorus_e), max(verse_e), abs_tol=0.02)


@settings(deadline=None, max_examples=40)
@given(speeds, starts)
def test_most_of_what_they_sing_sits_in_the_chord_under_it(bpm, start):
    from app.services.audio import song_notes

    notes, _ = song(bpm=bpm, start_s=start, form="VCVC")
    grid = accompany.Grid(bpm, start % (240.0 / bpm))
    fp = fp_utils.normalize({"tempo_bpm": bpm, "energy_level": 0.5, "density": 0.5})
    acc = accompany.plan(notes, grid, accompany.sections_from_phrases(notes, grid), fp)
    fp = {**fp, "key": acc.key, "mode": acc.key.split()[1], "music_start_s": grid.start_s}
    chords = song_notes.from_plan(acc.sections, fp, 1).chords
    inside = total = 0.0
    for n in notes:
        mid = (n.start + n.end) / 2
        chord = next((c.value for c in chords if c.start <= mid < c.end), None)
        if chord is not None:
            total += n.end - n.start
            inside += (n.end - n.start) * (int(round(n.pitch)) % 12 in chord)
    assert total > 0 and inside / total >= 0.5, inside / total
