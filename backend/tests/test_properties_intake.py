"""
Property-based tests for hum-to-melody (start-from-any-input spec 02, tasks 7.1 to 7.6).

Hums are synthesised from known notes, so the right answer is known. The pitch tracker is real
(librosa pyin); there is no mocking of the thing under test.
"""
from __future__ import annotations

import io
import os
import pathlib
import re

import numpy as np
import pytest
import soundfile as sf
from hypothesis import HealthCheck, Phase, given, settings, strategies as st

from app.services.intake import melody as m
from app.services.generation.theory import NOTE_NAMES

SR = m.SR
SLOW = settings(
    max_examples=6,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    phases=[Phase.explicit, Phase.reuse, Phase.generate],  # shrinking a pitch-tracker run takes minutes
)


# ─── Helpers ─────────────────────────────────

def synth_hum(notes: list[tuple[int, float]], gap: float = 0.07, vibrato: float = 0.15) -> tuple[np.ndarray, list[float]]:
    """A voice-like hum: sine with light vibrato and a short silence between notes. Returns (audio, onsets)."""
    chunks: list[np.ndarray] = [np.zeros(int(0.3 * SR))]
    onsets: list[float] = []
    t_cursor = 0.3
    for midi, dur in notes:
        n = int(dur * SR)
        t = np.arange(n) / SR
        f0 = 440.0 * 2 ** ((midi + vibrato * np.sin(2 * np.pi * 5.0 * t) - 69) / 12.0)
        phase = 2 * np.pi * np.cumsum(f0) / SR
        env = np.minimum(1.0, np.minimum(t / 0.03, (dur - t) / 0.03)).clip(0, 1)
        chunks.append((0.4 * env * (np.sin(phase) + 0.3 * np.sin(2 * phase))).astype(np.float32))
        chunks.append(np.zeros(int(gap * SR)))
        onsets.append(t_cursor)
        t_cursor += dur + gap
    chunks.append(np.zeros(int(0.3 * SR)))
    return np.concatenate(chunks).astype(np.float32), onsets


def to_wav_bytes(y: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, y, SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def raw(pitch: float, start: float, dur: float) -> m.RawNote:
    return m.RawNote(start_s=start, end_s=start + dur, midi=int(round(pitch)), midi_f=float(pitch))


@st.composite
def tunes(draw):
    """A short tune: 8 to 12 notes between 50 and 66, no jump bigger than a fifth. Valid by construction
    (an earlier version filtered random lists, discarded ~95%, and Hypothesis sometimes refused to run)."""
    pitch = draw(st.integers(52, 62))
    out = []
    for _ in range(draw(st.integers(8, 12))):
        out.append((pitch, draw(st.floats(0.3, 0.7))))
        pitch = min(66, max(50, pitch + draw(st.integers(-7, 7))))
    return out


# ─── 7.2 Round trip: known notes come back ───

@SLOW
@given(tunes())
def test_hummed_notes_are_recovered_with_their_pitch_and_timing(tune):
    y, onsets = synth_hum(tune)
    midi, _prob, times = m.track_pitch(y)
    got = m.segment_notes(midi, times, m.track_energy(y))
    found = 0
    for (pitch, _dur), onset in zip(tune, onsets):
        if any(abs(g.midi_f - pitch) <= 0.5 and abs(g.start_s - onset) <= 0.12 for g in got):
            found += 1
    assert found / len(tune) >= 0.85
    assert len(got) <= len(tune) * 1.25  # no swarm of invented notes


# ─── 7.1 Key is transposition-equivariant ────

note_sets = st.lists(
    st.tuples(st.integers(48, 72), st.floats(0.1, 2.0)),
    min_size=6,
    max_size=30,
)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(note_sets, st.integers(1, 11))
def test_transposing_a_tune_transposes_its_key_by_the_same_amount(tune, k):
    base = [raw(p, i * 3.0, d) for i, (p, d) in enumerate(tune)]
    moved = [raw(p + k, i * 3.0, d) for i, (p, d) in enumerate(tune)]
    key_a, mode_a, _ = m.estimate_key(base)
    key_b, mode_b, _ = m.estimate_key(moved)
    assert mode_a == mode_b
    assert NOTE_NAMES.index(key_b) == (NOTE_NAMES.index(key_a) + k) % 12


# ─── 7.3 Tempo ───────────────────────────────

def grid_onsets(bpm: int, steps: list[int], jitter: np.ndarray, start: float) -> np.ndarray:
    eighth = 60.0 / bpm / 2.0
    return start + np.cumsum(steps) * eighth + jitter


steps_strategy = st.lists(st.integers(1, 3), min_size=14, max_size=30)


@given(st.integers(70, 130), steps_strategy, st.floats(0.0, 3.0))
@settings(deadline=None)   # the speed finder takes a variable time on a busy machine; only the answer matters
def test_tempo_ignores_how_much_silence_comes_first(bpm, steps, lead):
    rng = np.random.default_rng(1)
    jitter = rng.uniform(-0.012, 0.012, len(steps))
    a, _, _ = m.estimate_tempo(grid_onsets(bpm, steps, jitter, 0.2))
    b, _, _ = m.estimate_tempo(grid_onsets(bpm, steps, jitter, 0.2 + lead))
    assert a == b


@given(st.integers(70, 130), steps_strategy)
@settings(deadline=None)   # the speed finder takes a variable time on a busy machine; only the answer matters
def test_a_steady_pulse_is_found_or_its_double_or_half(bpm, steps):
    rng = np.random.default_rng(2)
    jitter = rng.uniform(-0.012, 0.012, len(steps))
    got, conf, _ = m.estimate_tempo(grid_onsets(bpm, steps, jitter, 0.4))
    assert got is not None
    assert any(abs(got - bpm * f) <= 2.5 for f in (0.5, 1.0, 2.0)), (bpm, got)
    assert conf > 0.3


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(st.integers(0, m.MIN_ONSETS_FOR_TEMPO - 1))
def test_too_few_note_starts_means_no_tempo_not_a_made_up_one(n):
    bpm, conf, _ = m.estimate_tempo(np.linspace(0.5, 3.0, n))
    assert bpm is None and conf == 0.0


# ─── Tuning ──────────────────────────────────

@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(
    st.lists(st.tuples(st.integers(48, 72), st.floats(-0.1, 0.1)), min_size=6, max_size=24),
    st.floats(0.36, 0.5),
    st.sampled_from([1, -1]),
)
def test_a_hum_sitting_between_two_notes_still_gets_steady_notes(sung, offset, side):
    # The singer is centred about halfway between two standard notes and wobbles a little.
    # Plain rounding would flip between the neighbours; tuning to the singer fixes that.
    notes = [raw(p + side * offset + wobble, i * 0.6, 0.5) for i, (p, wobble) in enumerate(sung)]
    m.apply_tuning(notes)
    expected = [p for p, _ in sung]
    pitches = [n.midi for n in notes]
    # All notes land on one consistent side of the halfway point.
    shifts = {n - e for n, e in zip(pitches, expected)}
    assert len(shifts) == 1


# ─── Rounding to the beat grid ───────────────

@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(
    st.lists(st.tuples(st.floats(0.05, 0.8), st.floats(0.08, 1.2)), min_size=1, max_size=25),
    st.integers(60, 140),
    st.floats(0.0, 0.5),
    st.sampled_from([m.GRID_BEATS, m.COARSE_GRID_BEATS]),
)
def test_quantised_notes_start_on_the_grid_and_never_overlap(gaps_and_lengths, bpm, phase, grid):
    t = 0.2
    notes = []
    for gap, length in gaps_and_lengths:
        notes.append(raw(60, t, length))
        t += length + gap
    out = m.quantise(notes, float(bpm), phase, grid)
    assert len(out) == len(notes)
    assert out[0].start_beat == 0.0
    for a, b in zip(out, out[1:]):
        assert a.start_beat + a.dur_beats <= b.start_beat + 1e-9
    for n in out:
        assert n.start_beat >= 0
        assert n.dur_beats >= grid
        assert abs(n.start_beat / grid - round(n.start_beat / grid)) < 1e-9
        assert abs(n.dur_beats / grid - round(n.dur_beats / grid)) < 1e-9


# ─── 7.6 Silence and noise are turned away ───

def test_silence_is_rejected_with_a_plain_reason():
    result = m.extract_melody(to_wav_bytes(np.zeros(SR * 6, dtype=np.float32)))
    assert not result.ok
    assert result.sketch is None
    assert result.reason and "tune" in result.reason.lower()


@settings(max_examples=3, deadline=None)
@given(st.integers(0, 10_000), st.floats(0.05, 0.4))
def test_plain_noise_is_rejected_not_turned_into_notes(seed, level):
    rng = np.random.default_rng(seed)
    noise = (level * rng.standard_normal(SR * 6)).astype(np.float32)
    result = m.extract_melody(to_wav_bytes(noise))
    assert not result.ok
    assert result.sketch is None


def test_a_clean_hum_is_accepted_and_described_without_music_terms():
    tune = [(55, 0.5), (57, 0.5), (59, 0.5), (57, 0.5), (55, 0.7), (52, 0.5), (55, 0.5), (57, 0.8), (55, 0.6)]
    y, _ = synth_hum(tune)
    result = m.extract_melody(to_wav_bytes(y))
    assert result.ok, result.reason
    text = m.describe_melody(result.sketch)
    for banned in ("bpm", "tempo", "key", "major", "minor", "semitone", "note"):
        assert banned not in text.lower()
    assert result.sketch.confirmed is False  # never used until the person says it's their tune


# ─── Musical cleanup ─────────────────────────

messy_tunes = st.lists(
    st.tuples(st.integers(40, 76), st.floats(0.05, 1.0)),
    min_size=5,
    max_size=30,
)


def tune_from(pairs) -> list[m.RawNote]:
    notes, t = [], 0.0
    for pitch, dur in pairs:
        notes.append(raw(pitch, t, dur))
        t += dur + 0.05
    return notes


def pitch_distance(a: int, b: int) -> int:
    """Distance in notes, ignoring whole octaves."""
    d = abs(a - b) % 12
    return min(d, 12 - d)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(messy_tunes, st.integers(0, 11), st.sampled_from(["major", "minor"]), st.floats(0.0, 1.0))
def test_cleanup_only_removes_notes_keeps_order_and_the_overall_span(pairs, tonic, mode, conf):
    notes = tune_from(pairs)
    out, _ = m.clean_up(notes, tonic, mode, conf)
    assert 1 <= len(out) <= len(notes)
    assert all(a.start_s <= b.start_s for a, b in zip(out, out[1:]))
    assert out[0].start_s == pytest.approx(notes[0].start_s)
    assert out[-1].end_s == pytest.approx(notes[-1].end_s)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(messy_tunes, st.integers(0, 11), st.sampled_from(["major", "minor"]), st.floats(0.0, 1.0))
def test_cleanup_never_moves_a_note_further_than_its_neighbour_note_name(pairs, tonic, mode, conf):
    notes = tune_from(pairs)
    before = [n.midi for n in notes]
    out, report = m.clean_up(notes, tonic, mode, conf)
    # Every surviving note is within two notes (ignoring octave moves) of some original note it came from.
    originals = set(before)
    for n in out:
        assert any(pitch_distance(n.midi, o) <= 2 for o in originals)
    assert [n.midi for n in notes] == before  # the input is left untouched


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(messy_tunes, st.integers(0, 11), st.sampled_from(["major", "minor"]), st.floats(0.0, m.CONFIDENT - 0.01))
def test_cleanup_does_not_force_notes_into_a_key_it_is_unsure_about(pairs, tonic, mode, conf):
    _, report = m.clean_up(tune_from(pairs), tonic, mode, conf)
    assert report["out_of_key_snapped"] == 0


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(st.integers(0, 11), st.integers(1, 3))
def test_a_tidy_tune_is_left_alone(tonic, octaves):
    # Long, in-key notes where every note name is used plenty: nothing to clean.
    scale = [(tonic + i) % 12 for i in m.MAJOR_SCALE]
    # Three smooth runs up the scale; each run sits in its own octave (a real tune does not
    # jump an octave on every note).
    pairs = [
        (48 + 12 * (run % octaves) + (pc - tonic) % 12, 0.5)
        for run in range(3)
        for pc in scale
    ]
    notes = tune_from(pairs)
    out, report = m.clean_up(notes, tonic, "major", 0.9)
    assert [n.midi for n in out] == [n.midi for n in notes]
    assert sum(report.values()) == 0


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(st.integers(48, 70), st.sampled_from([1, -1]), st.integers(2, 18))
def test_a_stray_note_one_step_from_the_note_the_tune_lives_on_becomes_that_note(home, side, where):
    # A tune that sits on one note, with a single brief wobble a step away.
    pairs = [(home, 0.5)] * 20
    pairs[where] = (home + side, 0.3)
    out, report = m.clean_up(tune_from(pairs), home % 12, "major", 0.0)
    assert report["wobble_snapped"] == 1
    assert {n.midi for n in out} == {home}


# ─── Playback follows the singer's own timing ─

sung_tunes = st.lists(
    st.tuples(st.integers(40, 76), st.floats(0.06, 1.2), st.floats(0.0, 0.6)),
    min_size=1,
    max_size=30,
)


def sung_from(items) -> list[m.RawNote]:
    notes, t = [], 0.3
    for pitch, dur, gap in items:
        notes.append(raw(pitch, t, dur))
        t += dur + gap
    return notes


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(sung_tunes, st.integers(50, 180))
def test_performed_notes_keep_the_singers_timing_instead_of_snapping_to_a_grid(items, bpm):
    notes = sung_from(items)
    out = m.performed_notes(notes, float(bpm))
    assert len(out) == len(notes)
    assert out[0].start_beat == 0.0
    per_second = bpm / 60.0
    for n_in, n_out in zip(notes, out):
        assert n_out.pitch_midi == n_in.midi
        assert n_out.start_beat == pytest.approx((n_in.start_s - notes[0].start_s) * per_second, abs=1e-3)


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(sung_tunes, st.integers(50, 180))
def test_performed_notes_never_overlap_and_always_have_length(items, bpm):
    out = m.performed_notes(sung_from(items), float(bpm))
    for a, b in zip(out, out[1:]):
        assert a.start_beat + a.dur_beats <= b.start_beat + 1e-3 or a.dur_beats == pytest.approx(0.05, abs=1e-6)
        assert b.start_beat >= a.start_beat
    assert all(n.dur_beats > 0 for n in out)


def test_playback_uses_the_sung_timing_when_it_exists():
    from app.models.song import MelodyNote, MelodySketch
    from app.services.intake import preview
    snapped = [MelodyNote(pitch_midi=60, start_beat=0.0, dur_beats=0.5)]
    sung = [MelodyNote(pitch_midi=60, start_beat=0.0, dur_beats=0.37)]
    sketch = MelodySketch(notes=snapped, performed_notes=sung, tempo_bpm=90, tempo_confidence=0.5,
                          key="C major", mode="major", key_confidence=0.5)
    events = preview._shaped_events(sketch)
    assert events[0].duration < 0.5  # followed the sung 0.37, not the snapped 0.5
    sketch_old = sketch.model_copy(update={"performed_notes": []})
    assert preview._shaped_events(sketch_old)[0].duration > events[0].duration  # falls back to the grid version


# ─── Octave glitches ─────────────────────────

@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(
    st.integers(48, 66),
    st.lists(st.integers(-2, 2), min_size=8, max_size=20),
    st.integers(2, 6),
    st.sampled_from([12, -12]),
    st.floats(0.1, 1.2),
)
def test_a_note_an_octave_away_from_a_steady_tune_is_moved_back_whatever_its_length(
    home, steps, where, jump, length
):
    where = min(where, len(steps) - 2)
    pairs = [(home + d, 0.5) for d in steps]
    # the displaced note is the one before it, an octave away (so it is clearly an octave out)
    pairs[where] = (pairs[where - 1][0] + jump, length)
    out, report = m.clean_up(tune_from(pairs), home % 12, "major", 0.0)
    assert report["octave_fixed"] >= 1
    assert max(n.midi for n in out) - min(n.midi for n in out) <= 9


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(st.integers(48, 66), st.sampled_from([12, -12]))
def test_a_real_octave_leap_that_stays_there_is_not_flattened(home, jump):
    # The tune moves up (or down) an octave and keeps going: two neighbours on the same new level.
    pairs = [(home, 0.5)] * 6 + [(home + jump, 0.5)] * 6
    out, _ = m.clean_up(tune_from(pairs), home % 12, "major", 0.0)
    assert [n.midi for n in out] == [p for p, _ in pairs]


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(st.integers(48, 66), st.integers(7, 9), st.integers(2, 12), st.floats(0.1, 1.2))
def test_a_big_but_ordinary_leap_up_and_back_down_is_a_tune_not_a_glitch(home, leap, where, length):
    # A sixth up and back again is a normal melodic move. Only a full octave out is treated as a tracking error.
    pairs = [(home, 0.5)] * 14
    pairs[where] = (home + leap, length)
    out, report = m.clean_up(tune_from(pairs), home % 12, "major", 0.0)
    assert report["octave_fixed"] == 0
    assert out[where].midi == home + leap if len(out) == len(pairs) else True


# ─── The fast pitch tracker equals librosa's exactly ─

import librosa  # noqa: E402

from app.services.intake.pitch_track import pyin_fast  # noqa: E402

FULL_LOW_HZ = float(librosa.note_to_hz(m.SEARCH_LOW))
FULL_HIGH_HZ = float(librosa.note_to_hz(m.SEARCH_HIGH))
TRACK = dict(sr=m.SR, frame_length=m.FRAME, hop_length=m.HOP)


def assert_same_as_librosa(y: np.ndarray) -> None:
    f_ref, v_ref, p_ref = librosa.pyin(
        y, fmin=FULL_LOW_HZ, fmax=FULL_HIGH_HZ, resolution=m.PYIN_RESOLUTION, **TRACK
    )
    f_new, v_new, p_new = pyin_fast(y, fmin=FULL_LOW_HZ, fmax=FULL_HIGH_HZ, resolution=m.PYIN_RESOLUTION, **TRACK)
    assert np.array_equal(v_ref, v_new), "voiced/unvoiced decisions differ"
    assert np.allclose(f_ref, f_new, equal_nan=True, rtol=0, atol=1e-9), "pitches differ"
    assert np.allclose(np.nan_to_num(p_ref), np.nan_to_num(p_new), atol=1e-12), "confidences differ"


@SLOW
@given(tunes())
def test_the_fast_pitch_tracker_gives_exactly_librosas_answer_on_hums(tune):
    y, _ = synth_hum(tune)
    assert_same_as_librosa(y)


@settings(max_examples=3, deadline=None)
@given(st.integers(0, 10_000), st.floats(0.02, 0.5))
def test_the_fast_pitch_tracker_gives_exactly_librosas_answer_on_noise(seed, level):
    y = (level * np.random.default_rng(seed).standard_normal(SR * 3)).astype(np.float32)
    assert_same_as_librosa(y)


def test_the_fast_pitch_tracker_gives_exactly_librosas_answer_on_silence_and_a_pure_tone():
    assert_same_as_librosa(np.zeros(SR * 2, dtype=np.float32))
    t = np.arange(SR * 2) / SR
    assert_same_as_librosa((0.4 * np.sin(2 * np.pi * 220 * t)).astype(np.float32))


@SLOW
@given(tunes(), st.integers(0, 10_000), st.floats(0.08, 0.3))
def test_the_fast_pitch_tracker_gives_exactly_librosas_answer_on_breathy_hums(tune, seed, breath):
    # Real hums are not clean: breath, room noise, dropouts. That is where the decoder has to decide
    # between "voiced" and "not voiced", so this is the input that exercises the switching costs.
    y, _ = synth_hum(tune, vibrato=0.4)
    noise = np.random.default_rng(seed).standard_normal(y.size).astype(np.float32)
    assert_same_as_librosa((y + breath * noise).astype(np.float32))


# Real recordings are never committed to the repo. To run this check on real hums, point
# FRANK_TEST_HUM_DIR at a folder of .flac/.wav/.webm hums, e.g. ~/frank-listening/humming.
REAL_HUMS = os.environ.get("FRANK_TEST_HUM_DIR")


@pytest.mark.skipif(not REAL_HUMS, reason="set FRANK_TEST_HUM_DIR to a folder of real hums to run this")
def test_the_fast_pitch_tracker_gives_exactly_librosas_answer_on_real_hums():
    files = sorted(p for p in pathlib.Path(REAL_HUMS).iterdir() if p.suffix.lower() in {".flac", ".wav", ".webm", ".ogg", ".mp3"})
    assert files, "no hums found in FRANK_TEST_HUM_DIR"
    for f in files[:3]:
        y = m.decode_mono(f.read_bytes(), f.suffix.lstrip("."))
        assert_same_as_librosa(y[: SR * 10])  # the first 10 seconds keeps the comparison quick


def test_the_fast_tracker_still_loads_when_the_compile_cache_folder_is_read_only(monkeypatch):
    # Numba raises RuntimeError at decoration time when it cannot write its cache (a read-only host).
    # The tracker must fall back to compiling in memory instead of failing to import.
    import numba

    from app.services.intake import pitch_track

    real_njit = numba.njit

    def njit_that_cannot_cache(*args, **kwargs):
        if kwargs.get("cache"):
            raise RuntimeError("cannot cache function: no locator available for file")
        return real_njit(*args, **kwargs)

    monkeypatch.setattr(numba, "njit", njit_that_cannot_cache)
    compiled = pitch_track._jit(lambda x: x + 1)
    assert compiled(41) == 42


# ─── Review findings (Code Reviewer and Integration Tester, Nov 12) ─

from app.routers import intake as intake_router  # noqa: E402
from app.services.audio.convert import to_wav  # noqa: E402
from app.services.intake import hints  # noqa: E402


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(st.one_of(st.none(), st.text(max_size=40)))
def test_whatever_the_filename_the_upload_extension_is_a_few_safe_letters(name):
    ext = intake_router.safe_extension(name)
    assert re.fullmatch(r"[a-z0-9]{1,5}", ext)


@pytest.mark.parametrize("name", ["hum.webm", "hum.FLAC", "x.m4a", "../../etc/passwd", "a.b/c", "noextension", "x." + "a" * 40, None])
def test_known_and_hostile_filenames(name):
    ext = intake_router.safe_extension(name)
    assert re.fullmatch(r"[a-z0-9]{1,5}", ext)
    if name == "hum.FLAC":
        assert ext == "flac"
    if name in ("../../etc/passwd", "a.b/c", "noextension", None):
        assert ext == "webm"


@settings(max_examples=30, deadline=None)   # each example starts FFmpeg, which takes a variable time
@given(st.text(min_size=1, max_size=30))
def test_converting_never_lets_the_extension_act_like_a_path(ext):
    # Garbage audio is fine to fail on; what must never happen is a path-related crash
    # (FileNotFoundError and friends) caused by the extension.
    try:
        to_wav(b"not audio at all", ext)
    except RuntimeError:
        pass  # FFmpeg could not read it: expected, and handled as "I couldn't open that recording"


def test_a_recording_over_a_minute_is_turned_away_before_any_heavy_work():
    long_silence = np.zeros(int((m.MAX_HUM_SECONDS + 5) * SR), dtype=np.float32)
    result = m.extract_melody(to_wav_bytes(long_silence))
    assert not result.ok and result.sketch is None
    assert "minute" in result.reason.lower()
    assert result.diagnostics == {}  # it never reached pitch tracking


@settings(deadline=None)   # the first calls warm caches; timing is not what is tested
@given(st.floats(0.0, 1.0), st.floats(0.0, 1.0))
def test_what_frank_is_unsure_about_is_a_short_list_of_simple_keys_most_important_first(key_conf, tempo_conf):
    from app.models.song import MelodySketch

    sketch = MelodySketch(notes=[], tempo_bpm=90, tempo_confidence=tempo_conf, key="C major", mode="major", key_confidence=key_conf)
    out = hints.unsure_about(sketch)
    assert set(out) <= {"mood", "speed"}
    assert ("mood" in out) == (key_conf < m.CONFIDENT)
    assert ("speed" in out) == (tempo_conf < m.CONFIDENT)
    if len(out) == 2:
        assert out == ["mood", "speed"]


# confirm: validate before writing, and saying yes twice is saying it once
import asyncio  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from app.models.song import FacetVersion, MelodyNote, MelodySketch  # noqa: E402


def _sketch(confirmed: bool) -> dict:
    return MelodySketch(
        notes=[MelodyNote(pitch_midi=60, start_beat=0, dur_beats=1)],
        tempo_bpm=90, tempo_confidence=0.9, key="C major", mode="major", key_confidence=0.9, confirmed=confirmed,
    ).model_dump(mode="json")


def _fake_world(monkeypatch, content: dict):
    version = FacetVersion(id="v1", project_id="p1", facet="melody", content=content, parent_id=None, operation="extract", author="frank")
    calls = {"written": 0, "activated": []}

    async def list_versions(project_id, facet=None):
        return [version]

    async def write_facet(*a, **k):
        calls["written"] += 1
        return FacetVersion(id="v2", project_id="p1", facet="melody", content={**content, "confirmed": True}, parent_id="v1", operation="confirm_melody", author="user")

    async def activate(project_id, facet, version_id):
        calls["activated"].append(version_id)

    monkeypatch.setattr(intake_router.song_db, "list_versions", list_versions)
    monkeypatch.setattr(intake_router.store, "write_facet", write_facet)
    monkeypatch.setattr(intake_router.store, "activate_facet_version", activate)
    return calls


def test_confirming_a_broken_tune_writes_nothing(monkeypatch):
    calls = _fake_world(monkeypatch, {"notes": "not a list"})
    with pytest.raises(HTTPException) as err:
        asyncio.run(intake_router.confirm_melody("p1", "v1"))
    assert err.value.status_code == 400
    assert calls["written"] == 0


def test_confirming_an_unconfirmed_tune_writes_exactly_one_version(monkeypatch):
    calls = _fake_world(monkeypatch, _sketch(confirmed=False))
    asyncio.run(intake_router.confirm_melody("p1", "v1"))
    assert calls["written"] == 1


def test_confirming_an_already_confirmed_tune_only_makes_it_the_live_one(monkeypatch):
    calls = _fake_world(monkeypatch, _sketch(confirmed=True))
    result = asyncio.run(intake_router.confirm_melody("p1", "v1"))
    assert calls["written"] == 0 and calls["activated"] == ["v1"]
    assert result.version.is_active


# the fast pitch tracker on the hardest case: sudden big jumps between steady tones
def _jumpy_tones(seed: int, hold_ms: int, jump_notes: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pieces, note = [], 55.0
    for _ in range(40):
        note = float(np.clip(note + rng.choice([-1, 1]) * jump_notes, 45, 75))
        n = int(hold_ms / 1000 * SR)
        t = np.arange(n) / SR
        pieces.append((0.4 * np.sin(2 * np.pi * 440.0 * 2 ** ((note - 69) / 12) * t)).astype(np.float32))
    return np.concatenate(pieces)


@settings(max_examples=4, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.integers(0, 10_000), st.integers(15, 60), st.integers(4, 19))
def test_the_fast_pitch_tracker_matches_librosa_through_sudden_large_jumps(seed, hold_ms, jump):
    assert_same_as_librosa(_jumpy_tones(seed, hold_ms, jump))
