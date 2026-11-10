"""
Property-based tests for the mastering chain (`master`).

Spec: .kiro/specs/export-room/requirements.md, Requirements 2 (optional,
non-destructive mastering to -14 LUFS with limiting) and 6 (320 kbps MP3).

master() shells out to FFmpeg, so inputs are 1-3 s and max_examples is tiny.
Measurements use ffprobe / FFmpeg's ebur128 filter (pyloudnorm is not installed).

Constants measured against the real code (not guessed):
  * limiter ceiling and loudnorm true-peak target: -1.0 dBFS
  * output sample rate is 48 kHz (loudnorm resamples), bitrate 320000, stereo
  * MP3 adds ~32-40 ms of padding to the duration
  * integrated loudness lands on -14.0 LUFS (+/-0.1 observed)
"""
import io
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from hypothesis import given, settings, strategies as st

from app.services.audio import mastering

SR = 44100
CEILING_DB = -1.0
TARGET_LUFS = -14.0
LUFS_TOLERANCE = 1.0          # LU; observed error is ~0.1
MAX_PAD_S = 0.08              # observed MP3 padding is 0.032-0.040 s
SLOW = settings(max_examples=4, deadline=None)


# ── helpers ──────────────────────────────────────────────────────
def _tone_wav(amp: float, dur: float, freq: float, channels: int, seed: int) -> bytes:
    """A tone plus a little noise at peak-ish amplitude `amp` (PCM16 WAV)."""
    t = np.arange(int(SR * dur)) / SR
    rng = np.random.default_rng(seed)
    x = 0.6 * np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * 2 * freq * t)
    x = x + 0.1 * rng.standard_normal(len(t))
    x = np.clip(amp * x, -1.0, 1.0).astype(np.float32)
    if channels == 2:
        x = np.column_stack([x, x * 0.8])
    buf = io.BytesIO()
    sf.write(buf, x, SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _ffprobe(data: bytes, suffix: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(data)
        f.flush()
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f.name],
            capture_output=True, text=True, check=True,
        ).stdout
    return json.loads(out)


def _ebur128(data: bytes, suffix: str) -> tuple[float, float]:
    """Return (integrated LUFS, true peak dBFS) measured by FFmpeg."""
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(data)
        f.flush()
        err = subprocess.run(
            ["ffmpeg", "-nostats", "-i", f.name, "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, check=True,
        ).stderr
    summary = err[err.rfind("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    peak = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1))
    return lufs, peak


def _decode_pcm(data: bytes) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(data)
        f.flush()
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", f.name, "-f", "f32le", "-ac", "2", "-"],
            capture_output=True, check=True,
        ).stdout
    return np.frombuffer(raw, dtype=np.float32)


inputs = st.fixed_dictionaries({
    "amp": st.floats(min_value=0.002, max_value=1.0),
    "dur": st.floats(min_value=1.0, max_value=3.0),
    "freq": st.floats(min_value=80.0, max_value=2000.0),
    "channels": st.sampled_from([1, 2]),
    "seed": st.integers(0, 1000),
})


# ── Req 6.1: output is a decodable 320 kbps MP3 ─────────────────
@given(inputs)
@SLOW
def test_output_is_decodable_320kbps_stereo_mp3(p):
    """Req 6.1: output is MP3 at 320 kbps, decodes to non-empty finite audio."""
    out = mastering.master(_tone_wav(**p))
    info = _ffprobe(out, ".mp3")
    stream = info["streams"][0]
    assert stream["codec_name"] == "mp3"
    assert int(stream["bit_rate"]) == 320_000
    assert stream["channels"] == 2
    pcm = _decode_pcm(out)
    assert pcm.size > 0 and np.isfinite(pcm).all()


# ── Req 2.2: limiting ───────────────────────────────────────────
@given(inputs)
@SLOW
def test_peaks_stay_under_ceiling(p):
    """Req 2.2: limiting. True peak <= -1 dBFS and no decoded sample above it."""
    out = mastering.master(_tone_wav(**p))
    _, true_peak = _ebur128(out, ".mp3")
    assert true_peak <= CEILING_DB + 1e-6
    assert float(np.abs(_decode_pcm(out)).max()) <= 10 ** (CEILING_DB / 20)


# ── Req 2.2 / 6.1: loudness to -14 LUFS from quiet and loud ─────
@given(inputs)
@SLOW
def test_loudness_lands_on_target(p):
    """Req 2.2/6.1: integrated loudness is within 1 LU of -14 LUFS."""
    out = mastering.master(_tone_wav(**p))
    lufs, _ = _ebur128(out, ".mp3")
    assert abs(lufs - TARGET_LUFS) <= LUFS_TOLERANCE


@pytest.mark.parametrize("amp", [0.002, 1.0])
def test_loudness_moves_toward_target_from_extremes(amp):
    """Req 2.2: a very quiet and a clipping-loud input both end near -14 LUFS,
    and end closer to it than they started."""
    wav = _tone_wav(amp, 2.0, 220.0, 2, 1)
    before, _ = _ebur128(wav, ".wav")
    after, _ = _ebur128(mastering.master(wav), ".mp3")
    assert abs(after - TARGET_LUFS) < abs(before - TARGET_LUFS)
    assert abs(after - TARGET_LUFS) <= LUFS_TOLERANCE


# ── Duration preserved ──────────────────────────────────────────
@given(inputs)
@SLOW
def test_duration_preserved_within_mp3_padding(p):
    """Req 2.2: audio is not truncated. Output is never shorter and at most
    ~80 ms longer than the input (measured MP3 padding: 32-40 ms)."""
    out = mastering.master(_tone_wav(**p))
    stream = _ffprobe(out, ".mp3")["streams"][0]
    decoded_s = _decode_pcm(out).size / 2 / int(stream["sample_rate"])
    expected = int(SR * p["dur"]) / SR
    assert expected - 0.01 <= decoded_s <= expected + MAX_PAD_S


# ── Req 2.4: non-destructive ────────────────────────────────────
@given(inputs)
@SLOW
def test_input_bytes_not_mutated(p):
    """Req 2.4: the un-mastered mix is untouched. A bytearray (the only mutable
    bytes-like) is passed so in-place writes would be detectable."""
    original = _tone_wav(**p)
    arg = bytearray(original)
    mastering.master(arg)
    assert bytes(arg) == original


def test_no_temp_files_left_behind(tmp_path, monkeypatch):
    """Deployment: free-tier disk/memory. master() cleans every temp file."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    mastering.master(_tone_wav(0.5, 1.0, 220.0, 2, 0))
    assert list(Path(tmp_path).iterdir()) == []


# ── Regression: silent input used to crash the encode ───────────
def test_silent_input_still_produces_mp3():
    """Req 6.1: master() returns an MP3 for any valid mix, incl. silence.
    Found by this suite: loudnorm on pure silence made libmp3lame abort
    (psymodel.c calc_energy assertion, rc=134). Fixed by skipping loudnorm
    for silent audio."""
    buf = io.BytesIO()
    sf.write(buf, np.zeros((SR, 2), np.float32), SR, format="WAV", subtype="PCM_16")
    out = mastering.master(buf.getvalue())
    assert _ffprobe(out, ".mp3")["streams"][0]["codec_name"] == "mp3"
