"""
Property-based tests for vocal comp assembly (app.services.audio.comp.build_comp).

Spec: .kiro/specs/voice-room/requirements.md, Requirement 6 (Vocal Comping).
  6.2 score segments, assemble the best sequence
  6.3 show which take each segment came from
  6.5 store the comp WITHOUT touching the source takes

Audio is tiny (<= ~4.5 s of sine/noise per take, at most 3 takes) because every
2 s window runs librosa.pyin per take. Example counts are capped accordingly.
"""
import io

import numpy as np
import pytest
import soundfile as sf
from hypothesis import given, settings, strategies as st

from app.services.audio import comp

SR = comp.SR
WIN_S = comp.WINDOW_SECONDS


def _wav(samples: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, samples.astype(np.float32), SR, format="WAV", subtype="FLOAT")
    return buf.getvalue()


def _tone(freq: float, n: int, amp: float) -> np.ndarray:
    t = np.arange(n) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


@st.composite
def take_sets(draw):
    """1-3 takes, each a tone or noise of 0.05-4.5 s with a unique id."""
    n = draw(st.integers(1, 3))
    takes = []
    for i in range(n):
        length = draw(st.integers(int(0.05 * SR), int(4.5 * SR)))
        kind = draw(st.sampled_from(["tone", "noise", "silence"]))
        amp = draw(st.floats(0.01, 0.9))
        if kind == "tone":
            audio = _tone(draw(st.floats(100, 600)), length, amp)
        elif kind == "noise":
            seed = draw(st.integers(0, 2**16))
            audio = (amp * np.random.default_rng(seed).uniform(-1, 1, length)).astype(
                np.float32
            )
        else:
            audio = np.zeros(length, dtype=np.float32)
        takes.append((f"take-{i}", _wav(audio), length))
    return takes


def _run(takes):
    return comp.build_comp([(tid, b) for tid, b, _ in takes])


def test_empty_input_gives_empty_comp():
    """6.5 / robustness: no takes -> no audio, no segments."""
    assert comp.build_comp([]) == (b"", [])


@given(take_sets())
@settings(max_examples=20, deadline=None)
def test_segments_tile_the_comp_without_gaps_or_overlaps(takes):
    """6.3: segments start at 0, are contiguous, non-negative length, and end at the comp end."""
    out, segs = _run(takes)
    assert segs, "non-empty input must yield at least one segment"
    assert segs[0]["start_time"] == 0.0
    for a, b in zip(segs, segs[1:]):
        assert a["end_time"] == b["start_time"]
    for s in segs:
        # Strict: no zero-length segments (regression for the tiny-tail bug).
        assert s["end_time"] > s["start_time"]
    comp_len = sf.read(io.BytesIO(out), dtype="float32")[0].shape[0]
    assert abs(segs[-1]["end_time"] - comp_len / SR) <= 0.005 + 1e-9


def test_no_zero_length_segment_for_tiny_tail_window():
    """6.3 minimal repro (found by Hypothesis, shrunk): take A is 88202 samples
    (2 s + 2 samples), take B is 88200 and louder. B wins window 1; A wins the
    2-sample tail window -> {'take_id': 'A', 'start_time': 2.0, 'end_time': 2.0}."""
    a = _wav(_tone(220, 88202, 0.1))
    b = _wav(_tone(220, 88200, 0.6))
    _, segs = comp.build_comp([("A", a), ("B", b)])
    assert all(s["end_time"] > s["start_time"] for s in segs)


@given(take_sets())
@settings(max_examples=20, deadline=None)
def test_every_segment_names_an_input_take(takes):
    """6.3: provenance is truthful - only ids that were supplied appear."""
    _, segs = _run(takes)
    ids = {tid for tid, _, _ in takes}
    assert {s["take_id"] for s in segs} <= ids


@given(take_sets())
@settings(max_examples=20, deadline=None)
def test_comp_length_equals_longest_take_and_never_clips(takes):
    """Output is exactly as long as the longest take, valid 16-bit WAV, peak <= 0.89."""
    out, _ = _run(takes)
    data, sr = sf.read(io.BytesIO(out), dtype="float32")
    assert sr == SR
    assert data.shape[0] == max(n for _, _, n in takes)
    assert np.isfinite(data).all()
    assert float(np.abs(data).max()) <= 0.89 + 1e-3


@given(take_sets())
@settings(max_examples=15, deadline=None)
def test_source_takes_are_not_touched(takes):
    """6.5: input bytes and the list handed in are unchanged after assembly."""
    arg = [(tid, b) for tid, b, _ in takes]
    snapshot = [(tid, bytes(b)) for tid, b in arg]
    comp.build_comp(arg)
    assert arg == snapshot
    assert len(arg) == len(snapshot)


@given(st.integers(int(0.2 * SR), int(4.5 * SR)), st.floats(0.05, 0.9))
@settings(max_examples=12, deadline=None)
def test_single_take_is_the_whole_comp(n, amp):
    """With one take, one segment spans the comp and cites that take."""
    _, segs = comp.build_comp([("only", _wav(_tone(220, n, amp)))])
    assert [s["take_id"] for s in segs] == ["only"]


@given(st.integers(0, 2), st.integers(0, 2**16), st.floats(100, 400))
@settings(max_examples=10, deadline=None)
def test_dominant_take_wins_every_segment(pos, seed, freq):
    """6.2: a loud steady tone beats silence and very quiet noise in every window."""
    n = int(4.0 * SR)  # two full windows
    rng = np.random.default_rng(seed)
    others = [
        np.zeros(n, dtype=np.float32),
        (0.002 * rng.uniform(-1, 1, n)).astype(np.float32),
    ]
    audios = others[:]
    audios.insert(pos, _tone(freq, n, 0.6))
    takes = [(f"t{i}", _wav(a)) for i, a in enumerate(audios)]
    _, segs = comp.build_comp(takes)
    assert {s["take_id"] for s in segs} == {f"t{pos}"}
    assert len(segs) == 1  # consecutive wins by the same take are merged


@given(st.lists(st.integers(0, 1), min_size=3, max_size=3), st.floats(100, 400))
@settings(max_examples=12, deadline=None)
def test_segments_follow_which_take_is_best_per_window(winners, freq):
    """6.2 + 6.3: with 3 windows where take i sings only in the windows it should win,
    the segments are exactly the run-length encoding of the winners, tiling 0..6 s.
    This targeted generator guarantees multi-segment output, which the broad
    generators above rarely produce."""
    win = int(WIN_S * SR)
    audios = [np.zeros(3 * win, dtype=np.float32) for _ in range(2)]
    for w, who in enumerate(winners):
        audios[who][w * win:(w + 1) * win] = _tone(freq, win, 0.6)
    _, segs = comp.build_comp([(f"t{i}", _wav(a)) for i, a in enumerate(audios)])

    expected = []
    for w, who in enumerate(winners):
        if expected and expected[-1][0] == f"t{who}":
            expected[-1][2] = (w + 1) * WIN_S
        else:
            expected.append([f"t{who}", w * WIN_S, (w + 1) * WIN_S])
    assert [[s["take_id"], s["start_time"], s["end_time"]] for s in segs] == expected
