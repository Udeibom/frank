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
    """Float32 audio shaped (samples, 2): one copy of the song, which the chain then processes in place."""
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    return np.ascontiguousarray(data[:, :2])


CHUNK_SECONDS = 5.0


def _process_in_place(board: Pedalboard, audio: np.ndarray) -> np.ndarray:
    """
    Run the chain a few seconds at a time, keeping its state between chunks (reset=False), writing back into the
    same buffer. Same result as one pass; memory stays at one song plus one chunk (ship-it spec 13, req 2.1).
    """
    step = int(CHUNK_SECONDS * SR)
    board.reset()
    for start in range(0, audio.shape[0], step):
        end = min(start + step, audio.shape[0])
        y = board(np.ascontiguousarray(audio[start:end].T), SR, reset=False)
        audio[start:start + y.shape[1]] = y.T
    return audio


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
            sf.write(wf, audio, SR, format="WAV", subtype="PCM_16")
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


# ── finishing from an uncompressed mix (finish-and-intent spec 11, requirement 2) ──

LOUDNESS_TOLERANCE = 1.0     # units of the streaming loudness scale
TRUE_PEAK_DB = -1.0


def _wav_file(audio: np.ndarray) -> str:
    """(samples, channels) float -> a temporary 24-bit WAV path (no quality lost before the final encode)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wf:
        sf.write(wf, audio, SR, format="WAV", subtype="PCM_24")
        return wf.name


def _ffmpeg(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-y", *args], capture_output=True, timeout=timeout)


def measure_loudness(wav_path: str) -> dict | None:
    """FFmpeg loudnorm's first pass: the song's loudness, true peak and range, as numbers."""
    import json
    import re

    r = _ffmpeg(["-i", wav_path, "-af", f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr.decode(errors="replace"))
    if not m:
        return None
    data = json.loads(m.group(0))
    try:
        return {k: float(data[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (KeyError, ValueError):
        return None


def encode_finished(wav_path: str, measured: dict | None, extra_gain_db: float = 0.0) -> bytes:
    """Second pass: loudness to the target with the measured values (linear, no pumping), 320 kbps MP3."""
    out = wav_path[:-4] + ".finished.mp3"
    try:
        if measured is None:
            af = f"volume={extra_gain_db}dB,loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA=11"
        else:
            af = (f"volume={extra_gain_db}dB,loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA=11:"
                  f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
                  f"measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true")
        r = _ffmpeg(["-i", wav_path, "-af", af, "-ar", str(SR), "-b:a", "320k", out])
        if r.returncode != 0:
            raise RuntimeError(f"Finishing encode failed: {r.stderr.decode(errors='replace')[-300:]}")
        with open(out, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(out):
            os.remove(out)


def encode_plain(audio: np.ndarray) -> bytes:
    """The mix as it is, at full quality (320 kbps from the uncompressed render): the 'before'. (channels, samples)."""
    path = _wav_file(np.ascontiguousarray(audio.T))
    out = path[:-4] + ".plain.mp3"
    try:
        r = _ffmpeg(["-i", path, "-b:a", "320k", out])
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="replace")[-300:])
        with open(out, "rb") as f:
            return f.read()
    finally:
        for p in (path, out):
            if os.path.exists(p):
                os.remove(p)


def check_finished(mp3: bytes) -> dict:
    """The Listener's own ears on the result: loudness and clipping (requirement 2.1)."""
    from app.services.listener import dsp

    audio = _decode_with_ffmpeg(mp3)                   # (samples, channels)
    return {"loudness": dsp.loudness(audio, SR), "clipping": dsp.clipping_share(audio), "peak_db": dsp.peak_db(audio)}


def finish(audio: np.ndarray) -> tuple[bytes, dict]:
    """
    The finishing step from an UNCOMPRESSED mix shaped (channels, samples) as the mixer makes it: gentle chain, two-pass loudness to the
    streaming target with a true-peak ceiling, then measured. One corrective pass if it misses; then honest.
    """
    from app.services.listener import config as cfg

    silent = audio.size == 0 or float(np.abs(audio).max()) < 1e-6
    if silent:
        return encode_plain(audio), {"loudness": None, "clipping": 0.0, "passes": 0, "on_target": False}
    work = np.ascontiguousarray(audio.T, dtype=np.float32)          # (samples, channels), this module's shape
    _process_in_place(_master_chain(), work)
    path = _wav_file(work)
    del work
    try:
        measured = measure_loudness(path)
        mp3 = encode_finished(path, measured)
        report = check_finished(mp3)
        passes = 1
        miss = None if report["loudness"] is None else TARGET_LUFS - report["loudness"]
        if (miss is not None and abs(miss) > LOUDNESS_TOLERANCE) or (report["clipping"] or 0) > cfg.CLIPPING_SHARE:
            mp3 = encode_finished(path, measured, extra_gain_db=round(miss or -0.5, 2))
            report = check_finished(mp3)
            passes = 2
    finally:
        os.remove(path)
    lu = report["loudness"]
    report.update(passes=passes, on_target=lu is not None and abs(TARGET_LUFS - lu) <= LOUDNESS_TOLERANCE
                  and (report["clipping"] or 0) <= cfg.CLIPPING_SHARE)
    return mp3, report
