"""Sing It (spec 06, design "Properties" 1-7, plus timing and engineer rules)."""
from __future__ import annotations

import hashlib
import io

import numpy as np
import pytest
import soundfile as sf
from hypothesis import given, settings, strategies as st

from app.services.audio import align, bleed, comp, engineer, harmony, pitch, song_notes, vocal_notes
from app.services.audio.song_notes import SongNotes, Span, target_note
from app.services.generation import beat
from app.services.generation import fingerprint as fp_utils

SR = 44100
FP = fp_utils.normalize({"tempo_bpm": 96, "key": "A minor", "energy_level": 0.6, "density": 0.5, "warmth": 0.6, "brightness": 0.4})


def song_from_plan() -> SongNotes:
    sections, fp = beat.build_beat_plan(FP)
    return song_notes.from_plan(sections, fp, 1234)


SONG = song_from_plan()


def wav(x: np.ndarray, sr: int = SR) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, x.astype(np.float32), sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()


def sung(notes: list[tuple[float, float]], sr: int = SR, gap: float = 0.3, vibrato: float = 0.0) -> np.ndarray:
    """A voice-like take: each (midi, seconds) as a harmonic tone, with breaths between."""
    out = []
    for midi, dur in notes:
        t = np.arange(int(dur * sr)) / sr
        f = 440 * 2 ** ((midi - 69 + vibrato * np.sin(2 * np.pi * 5.5 * t)) / 12)
        ph = 2 * np.pi * np.cumsum(f) / sr
        y = sum(a * np.sin(k * ph) for k, a in ((1, 0.5), (2, 0.25), (3, 0.12)))
        out += [y * np.hanning(t.size) ** 0.3 * 0.6, np.zeros(int(gap * sr))]
    return np.concatenate(out).astype(np.float32)


def note(start: float, centre: float, length: float = 0.4) -> vocal_notes.SungNote:
    return vocal_notes.SungNote(start, start + length, centre, np.full(10, centre), 0.9)


# ── song targets ─────────────────────────────────────────────────────────

def test_song_notes_cover_the_song_and_belong_to_it():
    assert SONG.sections and SONG.chords and SONG.melody
    assert SONG.scale == song_notes.scale_of("A minor")
    end = SONG.sections[-1].end
    for t in np.linspace(0, end - 0.01, 200):
        tg = SONG.at(float(t))
        assert tg.section is not None and tg.chord
    for m in SONG.melody:
        assert SONG.sections[0].start <= m.start < m.end <= end + 1e-6


@given(st.floats(40, 84), st.sampled_from([None, 57, 60, 64, 69]))
@settings(max_examples=300, deadline=None)
def test_target_is_a_song_note_or_the_tune(sung_note, melody):
    t = song_notes.Target(song_notes.scale_of("A minor"), None, melody, 0)
    got = target_note(sung_note, t)
    assert got % 12 in t.scale or (melody is not None and got % 12 == melody % 12)
    # tuning never rewrites the tune: at most the neighbouring note (measured on real hums, Nov 18)
    assert abs(got - sung_note) <= 1.5


# ── properties 1 and 2: tuning ───────────────────────────────────────────

@given(st.lists(st.tuples(st.floats(0, 60), st.floats(45, 80)), min_size=1, max_size=30, unique_by=lambda x: round(x[0], 6)),
       st.sampled_from(["light", "moderate", "full"]))
@settings(max_examples=200, deadline=None)
def test_tuning_leaves_close_notes_alone_and_moves_others_closer(raw, mode):
    notes = [note(t, c) for t, c in raw]
    moves = pitch.plan_moves(notes, SONG, mode)
    moved = {round(m["start"], 6): m for m in moves}
    threshold = max(pitch.CORRECTION_MODES[mode]["threshold_cents"], 1.0)
    for n in notes:
        tgt = target_note(n.centre, SONG.at((n.start + n.end) / 2))
        before = abs(tgt - n.centre) * 100
        m = moved.get(round(n.start, 6))
        if before < threshold:
            assert m is None, "a note already close enough is never touched"
        elif m is not None:
            after = abs(tgt - (n.centre + m["shift"])) * 100
            assert after <= before + 1e-6
            assert after < 50, "never left stranded between two notes"


def test_tuning_really_moves_the_sound_and_keeps_the_original():
    take = sung([(69.4, 0.8), (72.0, 0.8)], vibrato=0.0)          # a note 40 cents sharp, then one in tune
    raw = wav(take)
    digest = hashlib.sha256(raw).hexdigest()
    out, moves = pitch.tune_take(raw, "moderate", SongNotes(scale=song_notes.scale_of("A minor")))
    assert hashlib.sha256(raw).hexdigest() == digest
    assert len(moves) == 1 and moves[0]["to"] == 69
    y, _ = sf.read(io.BytesIO(out), dtype="float32")
    after = vocal_notes.sung_notes(y, SR)
    assert after and abs(after[0].centre - 69) < abs(69.4 - 69) - 0.15


def test_gentle_tuning_keeps_vibrato():
    take = sung([(69.4, 1.2)], vibrato=0.4)
    out, moves = pitch.tune(take, SR, "moderate", SongNotes(scale=song_notes.scale_of("A minor")))
    if not moves:
        pytest.skip("this vibrato centred inside the light threshold")
    before = vocal_notes.sung_notes(take, SR)[0].frames
    after = vocal_notes.sung_notes(out, SR)[0].frames
    assert np.nanstd(after) > 0.6 * np.nanstd(before), "the movement inside the note survives"


# ── property 3: timing ───────────────────────────────────────────────────

@given(st.floats(0.0, 0.4))
@settings(max_examples=15, deadline=None)
def test_delay_check_finds_the_delay(d):
    sr = 22050
    clicks = [0.5, 1.0, 1.5, 2.0]
    rec = np.random.default_rng(1).normal(0, 0.002, int(3.2 * sr)).astype(np.float32)
    for c in clicks:
        i = int((c + d) * sr)
        rec[i:i + 200] += np.hanning(200).astype(np.float32) * 0.8
    got, conf = align.detect_delay(rec, sr, clicks)
    assert got is not None and conf > 0.3
    assert abs(got - d) <= 128 / sr + 0.003, "within one analysis step"


@given(st.floats(0, 0.5), st.floats(0, 0.3), st.floats(0, 20))
@settings(max_examples=50, deadline=None)
def test_placing_a_take_puts_each_sound_at_its_song_time(lead_in, delay, offset):
    sr = 8000
    take = np.zeros(int((lead_in + delay + 2) * sr), dtype=np.float32)
    mark = int((lead_in + delay + 1.0) * sr)
    take[mark] = 1.0                               # sung one second after the beat started at `offset`
    placed = align.place_in_song(take, sr, lead_in, delay, offset)
    assert abs(int(np.argmax(placed)) - int((offset + 1.0) * sr)) <= 2


@given(st.lists(st.floats(0, 60), min_size=1, max_size=20), st.floats(0.3, 1.0), st.sampled_from(["light", "moderate", "full"]))
@settings(max_examples=200, deadline=None)
def test_tightening_never_moves_more_than_a_quarter_beat_and_never_in_the_gentlest(starts, spb, mode):
    moves = align.phrase_moves(starts, spb, mode)
    assert all(abs(m) <= 0.25 * spb + 1e-9 for m in moves)
    if mode == "light":
        assert not any(moves)
    grid = spb / 2
    for s, m in zip(starts, moves):
        assert abs(round(s / grid) * grid - (s + m)) <= abs(round(s / grid) * grid - s) + 1e-9, "only toward the beat"


# ── property 4: bleed ────────────────────────────────────────────────────

def fake_beat(seconds: float, sr: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    b = 0.25 * np.sin(2 * np.pi * 110 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t))
    for k in np.arange(0, seconds, 0.5):                               # a kick-and-hat pattern
        i = int(k * sr)
        b[i:i + 2000] += rng.normal(0, 0.3, min(2000, n - i)) * np.exp(-np.arange(min(2000, n - i)) / 400)
    return b.astype(np.float32)


@given(st.integers(0, 1000), st.floats(0.15, 0.5))
@settings(max_examples=4, deadline=None)
def test_bleed_removal_takes_the_beat_out_and_keeps_the_voice(seed, g):
    voice = sung([(64, 1.0), (67, 1.0), (69, 1.2), (67, 0.8), (64, 1.2)], gap=0.7)
    b = fake_beat(voice.size / SR + 0.5, SR, seed)[: voice.size]
    room = signal_room(b, g)
    take = voice + room
    out, report = bleed.remove(take, b, SR)
    assert report.accepted, report
    assert report.reduction_db >= bleed.ACCEPT_REDUCTION_DB
    sung_mask = np.abs(voice) > 1e-3
    v_before = 10 * np.log10(np.mean(voice[sung_mask] ** 2))
    v_after = 10 * np.log10(np.mean(out[sung_mask] ** 2))
    assert abs(v_after - v_before) <= 2.0 + 1.0       # the voice part stays (within the beat left in sung moments)


def signal_room(b: np.ndarray, g: float) -> np.ndarray:
    """The beat as a mic hears it from a speaker: quieter, a little delayed, a short echo, duller."""
    from scipy import signal as sg

    d = int(0.012 * SR)
    x = np.concatenate([np.zeros(d, dtype=np.float32), b[:-d]]) * g
    x = sg.lfilter([0.6, 0.3], [1.0], x).astype(np.float32)
    echo = int(0.03 * SR)
    x[echo:] += 0.25 * x[:-echo]
    return x


def test_bleed_removal_keeps_a_clean_take_as_it_was():
    voice = sung([(64, 1.0), (67, 1.0)], gap=0.6)
    b = fake_beat(voice.size / SR, SR, 3)[: voice.size]
    out, report = bleed.remove(voice, b, SR)
    assert not report.accepted and np.array_equal(out, voice)


# ── property 5: phrase comp tiles the comp ───────────────────────────────

@given(st.lists(st.integers(0, 2), min_size=3, max_size=3), st.integers(2, 3))
@settings(max_examples=6, deadline=None)
def test_phrase_comp_tiles_the_timeline_and_picks_the_singer(singers, n_takes):
    gap = int(0.5 * SR)
    length = 3 * (int(0.9 * SR) + gap)
    takes = [np.random.default_rng(i).normal(0, 1e-4, length).astype(np.float32) for i in range(n_takes)]
    for k, who in enumerate(singers):
        who %= n_takes
        a = k * (int(0.9 * SR) + gap)
        takes[who][a:a + int(0.9 * SR)] += sung([(64 + k, 0.9)], gap=0.0)[: int(0.9 * SR)]
    raw = [(f"t{i}", wav(t)) for i, t in enumerate(takes)]
    before = [hashlib.sha256(b).hexdigest() for _, b in raw]
    out, segs = comp.build_phrase_comp(raw, SongNotes(scale=song_notes.scale_of("A minor")))
    assert [hashlib.sha256(b).hexdigest() for _, b in raw] == before
    assert segs[0]["start_time"] == 0.0
    for a, b in zip(segs, segs[1:]):
        assert a["end_time"] == b["start_time"] and a["end_time"] > a["start_time"]
    assert abs(segs[-1]["end_time"] - length / SR) < 0.002
    assert [s["take_id"] for s in segs] == [f"t{w % n_takes}" for w in singers]
    _, swapped = comp.swap(raw, segs, 0, f"t{(singers[0] + 1) % n_takes}")
    assert swapped[0]["take_id"] != segs[0]["take_id"] and [s["take_id"] for s in swapped[1:]] == [s["take_id"] for s in segs[1:]]


# ── property 6: every harmony note is a chord note ───────────────────────

@given(st.lists(st.tuples(st.floats(0, 60), st.floats(52, 76)), min_size=1, max_size=40), st.sampled_from(["above", "below"]))
@settings(max_examples=200, deadline=None)
def test_every_harmony_note_is_a_chord_note(raw, direction):
    notes = [note(t, c) for t, c in raw]
    plan = harmony.plan_harmony(notes, SONG, direction)
    assert len(plan) == len(notes)
    for p in plan:
        chord = SONG.at((p["start"] + p["end"]) / 2).chord
        assert p["note"] % 12 in chord
        assert (p["note"] > p["sung"]) if direction == "above" else (p["note"] < p["sung"])
        assert abs(p["note"] - p["sung"]) <= 12


def test_harmony_only_in_the_chosen_sections():
    choruses = {s.value[0] for s in SONG.sections if s.value[1] == "chorus"}
    notes = [note(t, 64.0) for t in np.arange(0, SONG.sections[-1].end - 1, 0.5)]
    plan = harmony.plan_harmony(notes, SONG, "above", choruses)
    assert plan and all(p["section"] in choruses for p in plan)


def test_harmony_audio_keeps_the_original():
    take = sung([(64, 0.6), (67, 0.6)])
    raw = wav(take)
    digest = hashlib.sha256(raw).hexdigest()
    out, plan = harmony.chord_harmony(raw, SONG, "above")
    assert hashlib.sha256(raw).hexdigest() == digest and plan
    y, _ = sf.read(io.BytesIO(out), dtype="float32")
    assert y.shape[0] == take.shape[0] and np.abs(y).max() > 0.1


# ── the recording engineer ───────────────────────────────────────────────

def test_the_engineer_says_one_kind_thing_about_the_recording_only():
    loud = np.clip(sung([(64, 1.0)]) * 4, -1, 1)
    msg, _ = engineer.check(loud, SR)
    assert msg and "back" in msg
    quiet = sung([(64, 1.0)]) * 0.02
    assert "closer" in engineer.check(quiet, SR)[0]
    clean, _ = engineer.check(sung([(64, 1.0), (67, 1.0)]), SR)
    assert clean is None
    voice = sung([(64, 1.0), (67, 1.0), (69, 1.0)], gap=0.6)
    b = fake_beat(voice.size / SR, SR, 1)[: voice.size]
    assert "beat" in engineer.check(voice + signal_room(b, 0.4), SR, beat=b)[0]
    for m in (msg, engineer.check(quiet, SR)[0]):
        assert not any(w in m.lower() for w in ("flat", "sharp", "off-key", "out of tune", "pitchy", "bad"))


@given(st.integers(45, 80), st.sampled_from(["above", "below"]))
@settings(max_examples=100, deadline=None)
def test_without_chords_the_harmony_is_a_third_in_the_scale(sung_target, direction):
    scale = song_notes.scale_of("A minor")
    h = harmony.harmony_note(sung_target, None, scale, direction)
    assert h % 12 in scale and 2 <= abs(h - sung_target) <= 5 and ((h > sung_target) == (direction == "above"))
