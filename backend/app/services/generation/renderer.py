"""
Renderer — plays composed MIDI parts through FluidSynth + a SoundFont to
produce real instrument audio. CPU-only, no GPU, no neural models.

Each Part is rendered to its own WAV buffer (a stem). The engine can also mix
stems together into a single buffer. All audio is 44.1kHz stereo int16.
"""

from __future__ import annotations
import os
import numpy as np
import fluidsynth
from app.config import get_settings
from app.services.generation.composer import Part, NoteEvent

SAMPLE_RATE = 44100
DRUM_CHANNEL = 9


def _soundfont_path() -> str:
    settings = get_settings()
    path = settings.soundfont_path
    if not os.path.isabs(path):
        # Resolve relative to the backend root (two levels up from this file's
        # package: app/services/generation -> app -> backend)
        backend_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        path = os.path.join(backend_root, path)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"SoundFont not found at {path}. Run scripts/fetch_soundfont.sh."
        )
    return path


def _beats_to_samples(beats: float, bpm: float) -> int:
    seconds = beats * (60.0 / bpm)
    return int(seconds * SAMPLE_RATE)


class SynthSession:
    """
    Holds one FluidSynth instance with the SoundFont loaded once, so multiple
    parts can be rendered without reloading the 14MB SoundFont each time.

    Loading the SoundFont dominates render time; reusing it across all stems in
    a beat cuts full-beat render time by roughly an order of magnitude.

    Use as a context manager:
        with SynthSession() as synth:
            audio = synth.render(part, bpm, total_beats)
    """

    def __init__(self) -> None:
        self._fs = fluidsynth.Synth(samplerate=float(SAMPLE_RATE))
        self._sfid = self._fs.sfload(_soundfont_path())

    def render(self, part: Part, bpm: float, total_beats: float) -> np.ndarray:
        fs = self._fs
        channel = DRUM_CHANNEL if part.is_drums else 0
        if part.is_drums:
            fs.program_select(channel, self._sfid, 128, 0)  # GM drum kit
        else:
            fs.program_select(channel, self._sfid, 0, part.preset)

        events: list[tuple[int, str, int, int]] = []
        for ev in part.events:
            on_at = _beats_to_samples(ev.start, bpm)
            off_at = _beats_to_samples(ev.start + ev.duration, bpm)
            events.append((on_at, "on", ev.note, ev.velocity))
            events.append((off_at, "off", ev.note, 0))
        events.sort(key=lambda e: e[0])

        total_samples = _beats_to_samples(total_beats, bpm)
        tail_samples = int(1.5 * SAMPLE_RATE)
        out = np.zeros((total_samples + tail_samples, 2), dtype=np.int16)
        cursor = 0

        def render_into(start: int, end: int):
            n = end - start
            if n <= 0:
                return
            raw = fs.get_samples(n)
            frame = np.frombuffer(raw, dtype=np.int16).reshape(-1, 2)
            out[start:start + frame.shape[0]] = frame[: end - start]

        for sample_idx, kind, note, vel in events:
            if sample_idx > cursor:
                render_into(cursor, min(sample_idx, out.shape[0]))
                cursor = sample_idx
            if kind == "on":
                fs.noteon(channel, note, vel)
            else:
                fs.noteoff(channel, note)

        if cursor < out.shape[0]:
            render_into(cursor, out.shape[0])

        # Silence any lingering notes before the next part reuses this channel
        fs.all_notes_off(channel)
        return out

    def close(self) -> None:
        if self._fs is not None:
            self._fs.delete()
            self._fs = None

    def __enter__(self) -> "SynthSession":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def render_part(part: Part, bpm: float, total_beats: float) -> np.ndarray:
    """
    Render a single Part to a stereo int16 numpy array.
    Convenience wrapper that creates and tears down a one-off SynthSession.
    For rendering many parts, use a shared SynthSession instead.
    """
    with SynthSession() as synth:
        return synth.render(part, bpm, total_beats)


def mix_stems(stems: list[np.ndarray], target_peak: float = 0.89) -> np.ndarray:
    """
    Sum stereo stems and normalize to a healthy listening level.

    SoundFont output tends to be conservative in level, so a raw sum often
    sits far below full scale (quiet). We normalize the mix so its peak reaches
    `target_peak` of int16 full scale, giving consistent, audible loudness
    without clipping. target_peak < 1.0 leaves a little headroom.
    """
    if not stems:
        return np.zeros((0, 2), dtype=np.int16)

    max_len = max(s.shape[0] for s in stems)
    acc = np.zeros((max_len, 2), dtype=np.float64)
    for s in stems:
        acc[: s.shape[0]] += s.astype(np.float64)

    peak = np.abs(acc).max()
    limit = 32767.0
    if peak > 0:
        # Normalize up (or down) so the loudest point hits target_peak * full scale
        acc *= (target_peak * limit) / peak

    return acc.astype(np.int16)


def to_wav_bytes(audio: np.ndarray) -> bytes:
    """Encode a stereo int16 array as WAV bytes (used for processing)."""
    import io
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def to_mp3_bytes(audio: np.ndarray, bitrate: str = "192k") -> bytes:
    """
    Encode a stereo int16 array as MP3 bytes via FFmpeg.

    Stored/playable renders use MP3, not WAV: a full 2.5-minute beat is ~25MB as
    WAV but ~3-4MB as MP3, which keeps uploads well within Supabase free-tier
    limits and streams faster to the browser. WAV is kept only for intermediate
    processing where quality must be lossless.
    """
    import subprocess
    import tempfile
    import os
    import soundfile as sf

    wav_path = None
    mp3_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wf:
            sf.write(wf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
            wav_path = wf.name
        mp3_path = wav_path[:-4] + ".mp3"

        result = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-b:a", bitrate, mp3_path],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"MP3 encode failed: {result.stderr.decode()[:200]}"
            )
        with open(mp3_path, "rb") as f:
            return f.read()
    finally:
        for p in (wav_path, mp3_path):
            if p and os.path.exists(p):
                os.remove(p)
