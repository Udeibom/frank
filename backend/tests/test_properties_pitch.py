"""Pitch-shift invariants (Rubber Band via pylibrb). Few examples: each runs DSP."""
import numpy as np
from hypothesis import given, settings, strategies as st

from app.services.audio.pitch import _pitch_shift

SR = 22050


def _tone(freq: float, seconds: float) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


@given(
    st.floats(min_value=110.0, max_value=880.0),
    st.floats(min_value=-4.0, max_value=4.0),
    st.floats(min_value=0.5, max_value=1.5),
)
@settings(max_examples=15, deadline=None)
def test_pitch_shift_preserves_duration(freq, semitones, seconds):
    """Correcting pitch must not change timing, or vocals drift off the beat."""
    y = _tone(freq, seconds)
    out = _pitch_shift(y, SR, semitones)
    # Rubber Band adds a small latency/tail; allow 5% or 50 ms.
    assert abs(len(out) - len(y)) <= max(0.05 * len(y), 0.05 * SR)


@given(st.floats(min_value=110.0, max_value=880.0))
@settings(max_examples=10, deadline=None)
def test_zero_shift_returns_input_unchanged(freq):
    y = _tone(freq, 0.5)
    assert np.array_equal(_pitch_shift(y, SR, 0.0), y)


@given(st.floats(min_value=110.0, max_value=880.0), st.floats(-4.0, 4.0))
@settings(max_examples=15, deadline=None)
def test_pitch_shift_output_is_finite_and_bounded(freq, semitones):
    out = _pitch_shift(_tone(freq, 0.6), SR, semitones)
    assert np.isfinite(out).all()
    assert float(np.abs(out).max()) < 2.0
