"""Tapped rhythm to groove (start-from-any-input spec 02, requirement 4)."""
import io

import numpy as np
import soundfile as sf
from hypothesis import given, settings, strategies as st

from app.services.intake import rhythm

SR = 22050
PATTERNS = ["X..x.x..X..x.x.x", "X.......X...x...", "X..X..X...X.X..."]
EVEN = "X.x.X.x.X.x.X.x."          # evenly spaced taps: the speed cannot be known from the audio alone


def taps(bpm: int, pattern: str, bars: int, jitter: float = 0.006, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    step = 60 / bpm / 4
    times, amps = [], []
    for b in range(bars):
        for i, c in enumerate(pattern):
            if c in "xX":
                times.append(0.3 + (b * 16 + i) * step + rng.normal(0, jitter))
                amps.append(1.0 if c == "X" else 0.5)
    y = np.zeros(int((times[-1] + 1) * SR), dtype=np.float32)
    n = int(0.03 * SR)
    burst = np.random.default_rng(1).standard_normal(n) * np.hanning(n)
    for t, a in zip(times, amps):
        i = int(t * SR)
        y[i:i + n] += a * burst
    buf = io.BytesIO()
    sf.write(buf, y, SR, format="WAV")
    return buf.getvalue()


@settings(max_examples=12, deadline=None)
@given(st.integers(70, 130), st.sampled_from(PATTERNS), st.integers(3, 5), st.integers(0, 5))
def test_the_pattern_and_the_speed_come_back_as_tapped(bpm, pattern, bars, seed):
    g = rhythm.groove_from_audio(taps(bpm, pattern, bars, seed=seed))
    assert g.ok
    lanes = "".join("x" if (k == "x" or h == "x") else "." for k, h in zip(g.kick, g.hat))
    assert lanes == pattern.lower().replace("x", "x").replace("X", "x")
    assert abs(g.tempo_bpm - bpm) <= 2 or g.tempo_confidence < 0.6


@settings(max_examples=15, deadline=None)
@given(st.integers(70, 130), st.integers(3, 5))
def test_evenly_spaced_taps_never_claim_a_confident_speed_unless_it_is_right(bpm, bars):
    """Eighths at 70 sound the same as quarters at 140. Either the speed is right, or Frank must not be confident."""
    g = rhythm.groove_from_audio(taps(bpm, EVEN, bars))
    assert g.ok
    assert abs(g.tempo_bpm - bpm) <= 2 or g.tempo_confidence < 0.6


def test_a_clearly_accented_pattern_keeps_its_accents():
    g = rhythm.groove_from_audio(taps(100, "X..x.x..X..x.x.x", 4))
    assert g.kick == "x.......x......." and g.hat == "...x.x.....x.x.x" and g.tempo_bpm == 100


def test_too_few_taps_and_silence_get_a_kind_reason_not_a_made_up_groove():
    one = rhythm.groove_from_hits(np.array([0.2, 0.7]), np.array([1.0, 1.0]))
    assert not one.ok and one.reason and one.kick == ""
    silent = io.BytesIO()
    sf.write(silent, np.zeros(SR * 3, dtype=np.float32), SR, format="WAV")
    s = rhythm.groove_from_audio(silent.getvalue())
    assert not s.ok and "tap" in s.reason.lower()
    junk = rhythm.groove_from_audio(b"not audio")
    assert not junk.ok and junk.reason


def test_the_preview_can_be_played_back():
    g = rhythm.groove_from_audio(taps(100, "X..x.x..X..x.x.x", 4))
    mp3 = rhythm.render_preview_mp3(g)
    assert len(mp3) > 2000
