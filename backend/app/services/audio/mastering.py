"""
Mastering — the final polish that makes a mix sound "radio ready".

A gentle mastering chain: shape the tone, glue it with compression, catch peaks
with a brickwall limiter (pedalboard), then normalize loudness to a streaming
target (-14 LUFS) with FFmpeg's loudnorm during the MP3 encode.

Non-destructive: mastering takes the mix render and produces a new file. The
un-mastered mix is always preserved.
"""

from __future__ import annotations
import io
import subprocess
import tempfile
import os
import numpy as np
import soundfile as sf
from pedalboard import (
    Pedalboard,
    Compressor,
    BrickwallLimiter,
    LowShelfFilter,
    HighShelfFilter,
    Gain,
)

SR = 44100
TARGET_LUFS = -14.0  # common streaming loudness target


def _load_stereo(wav_bytes: bytes) -> np.ndarray:
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    if data.ndim == 1:
        data = np.column_stack([data, data])
    return data.T.astype(np.float32)  # (channels, samples)


def _master_chain() -> Pedalboard:
    """
    A restrained mastering chain. The goal is polish, not loudness-war crushing:
    - a touch of low and high shelf for warmth and air
    - gentle glue compression
    - a brickwall limiter to stop peaks before loudness normalization
    """
    return Pedalboard([
        LowShelfFilter(cutoff_frequency_hz=120, gain_db=1.0),
        HighShelfFilter(cutoff_frequency_hz=8000, gain_db=1.5),
        Compressor(threshold_db=-16, ratio=2.0, attack_ms=10, release_ms=120),
        Gain(gain_db=2.0),
        BrickwallLimiter(ceiling_db=-1.0, release_ms=100),
    ])


def master(wav_bytes_or_mp3: bytes) -> bytes:
    """
    Master an audio file and return MP3 (320kbps) bytes.

    Input can be WAV or MP3 (soundfile reads both via libsndfile; if it can't,
    we fall back to decoding with FFmpeg). Output is a mastered MP3 at the
    streaming loudness target.
    """
    # Decode to float stereo
    try:
        audio = _load_stereo(wav_bytes_or_mp3)
    except Exception:
        audio = _decode_with_ffmpeg(wav_bytes_or_mp3)

    # Apply the pedalboard mastering chain
    board = _master_chain()
    processed = board(audio, SR)

    # Encode to MP3 with loudnorm to the LUFS target
    return _encode_mastered_mp3(processed)


def _decode_with_ffmpeg(data: bytes) -> np.ndarray:
    """Fallback decode (e.g. MP3) to float stereo via FFmpeg."""
    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(data)
            in_path = f.name
        out_path = in_path + ".wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-ar", str(SR), "-ac", "2", out_path],
            capture_output=True,
            timeout=120,
            check=True,
        )
        with open(out_path, "rb") as f:
            return _load_stereo(f.read())
    finally:
        for p in (in_path, out_path):
            if p and os.path.exists(p):
                os.remove(p)


def _encode_mastered_mp3(audio: np.ndarray) -> bytes:
    """
    Write the processed audio, then run FFmpeg loudnorm to the LUFS target while
    encoding to 320kbps MP3.
    """
    wav_path = mp3_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wf:
            sf.write(wf, audio.T, SR, format="WAV", subtype="PCM_16")
            wav_path = wf.name
        mp3_path = wav_path[:-4] + ".mastered.mp3"

        # Silence has no loudness to normalize, and loudnorm on pure silence
        # makes libmp3lame abort (psymodel assertion, exit 134). Found by a
        # property-based test (tests/test_properties_mastering.py). Encode
        # silent audio as-is instead.
        silent = audio.size == 0 or float(np.abs(audio).max()) < 1e-6
        filters = [] if silent else ["-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.0:LRA=11"]

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", wav_path,
                *filters,
                "-b:a", "320k",
                mp3_path,
            ],
            capture_output=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(
                # Tail, not head: the head is only FFmpeg's version banner.
                f"Mastering encode failed: {result.stderr.decode(errors='replace')[-300:]}"
            )
        with open(mp3_path, "rb") as f:
            return f.read()
    finally:
        for p in (wav_path, mp3_path):
            if p and os.path.exists(p):
                os.remove(p)
