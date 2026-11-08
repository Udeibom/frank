"""
Mixing engine — combine the vocal, harmony, and beat into one song.

Loads each layer, applies gain and (plain-language) effects, overlays them, and
renders a mix. Effects run through pedalboard; the user never sees the knobs —
they say "more warmth" and we translate to an EQ/saturation move here.

mix_params shape (stored on each mix version):
{
  "vocal_gain_db": 0.0,
  "beat_gain_db": -6.0,
  "harmony_gain_db": -3.0,
  "harmony_enabled": true,
  "vocal_effects": ["warm", "space"],     # plain-language effect ids
  "beat_effects": ["clean_low"],
  "section_gain_db": { "chorus": 1.5 }     # per-section-name beat adjustments
}

All CPU. Mixing holds a few full-length float buffers in memory, so it runs in a
background job and keeps only what it needs.
"""

from __future__ import annotations
import io
import numpy as np
import soundfile as sf
from pedalboard import (
    Pedalboard,
    Reverb,
    Compressor,
    HighpassFilter,
    LowShelfFilter,
    HighShelfFilter,
    Gain,
)

SR = 44100


def _db_to_linear(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _load_stereo(wav_bytes: bytes) -> np.ndarray:
    """Load audio as float32 shape (2, N) for pedalboard (channels-first)."""
    data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    if data.ndim == 1:
        data = np.column_stack([data, data])
    # pedalboard expects (channels, samples)
    stereo = data.T
    if sr != SR:
        # Rare — our pipeline is 44.1k throughout — but guard anyway
        import librosa

        stereo = np.vstack(
            [librosa.resample(stereo[c], orig_sr=sr, target_sr=SR) for c in range(stereo.shape[0])]
        )
    return stereo.astype(np.float32)


# Plain-language effect ids -> pedalboard chains. These are what the LLM emits
# (never raw DSP terms) and what we translate to actual processing.
def _vocal_effect_board(effect_ids: list[str]) -> Pedalboard:
    plugins = []
    for eid in effect_ids:
        if eid == "space":          # "add a little space"
            plugins.append(Reverb(room_size=0.35, wet_level=0.18, dry_level=0.85))
        elif eid == "warm":         # "warm it up"
            plugins.append(LowShelfFilter(cutoff_frequency_hz=200, gain_db=2.5))
            plugins.append(Compressor(threshold_db=-18, ratio=2.0))
        elif eid == "smooth":       # "smooth it out"
            plugins.append(Compressor(threshold_db=-16, ratio=3.0))
        elif eid == "clarity":      # lift presence so vocals cut through
            plugins.append(HighShelfFilter(cutoff_frequency_hz=4000, gain_db=2.0))
        elif eid == "closer":       # "bring it closer" — less space, gentle comp
            plugins.append(Compressor(threshold_db=-20, ratio=2.5))
    return Pedalboard(plugins)


def _beat_effect_board(effect_ids: list[str]) -> Pedalboard:
    plugins = []
    for eid in effect_ids:
        if eid == "clean_low":      # "clean up the low end" / fix muddiness
            plugins.append(HighpassFilter(cutoff_frequency_hz=90))
        elif eid == "warm":
            plugins.append(LowShelfFilter(cutoff_frequency_hz=180, gain_db=1.5))
        elif eid == "sit_back":     # let the beat sit under the vocal
            plugins.append(HighShelfFilter(cutoff_frequency_hz=3500, gain_db=-2.0))
    return Pedalboard(plugins)


def _apply(board: Pedalboard, audio: np.ndarray) -> np.ndarray:
    if len(board) == 0:
        return audio
    return board(audio, SR)


def _apply_section_gains(
    beat: np.ndarray,
    section_gain_db: dict,
    sections: list[dict],
    bpm: int,
) -> np.ndarray:
    """
    Apply per-section gain to the beat by time-windowing. Sections are laid out
    in order; each is `bars` long at `bpm` (4 beats per bar). We know the
    boundaries by construction (the engine built them), so no detection is
    needed. A gain named by section type (e.g. "chorus") applies to every
    section of that type.
    """
    if not section_gain_db or not sections:
        return beat

    samples_per_beat = SR * 60.0 / max(bpm, 1)
    cursor = 0
    for s in sections:
        bars = int(s.get("bars", 4))
        length = int(bars * 4 * samples_per_beat)
        name = s.get("name", "")
        gain_db = section_gain_db.get(name)
        if gain_db:
            end = min(cursor + length, beat.shape[1])
            beat[:, cursor:end] *= _db_to_linear(float(gain_db))
        cursor += length
        if cursor >= beat.shape[1]:
            break
    return beat


def render_mix(
    vocal_wav: bytes | None,
    beat_wav: bytes | None,
    harmony_wav: bytes | None,
    mix_params: dict,
    beat_sections: list[dict] | None = None,
    beat_bpm: int = 90,
) -> np.ndarray:
    """
    Combine the layers into one stereo float32 mix (channels-first), applying
    gains, effects, and per-section beat gains. Returns the mixed audio array.

    Memory: each source's decoded buffer is summed into the accumulator and then
    released before the next, so we don't hold vocal+beat+harmony all at once.
    """
    mix: np.ndarray | None = None

    def _add(layer: np.ndarray) -> None:
        nonlocal mix
        if mix is None:
            mix = np.zeros(layer.shape, dtype=np.float32)
        if layer.shape[1] > mix.shape[1]:
            grown = np.zeros((2, layer.shape[1]), dtype=np.float32)
            grown[:, : mix.shape[1]] += mix
            mix = grown
        mix[:, : layer.shape[1]] += layer

    if beat_wav:
        beat = _load_stereo(beat_wav)
        beat = _apply(_beat_effect_board(mix_params.get("beat_effects", [])), beat)
        beat = _apply_section_gains(
            beat, mix_params.get("section_gain_db", {}), beat_sections or [], beat_bpm
        )
        beat *= _db_to_linear(mix_params.get("beat_gain_db", -6.0))
        _add(beat)
        del beat

    if vocal_wav:
        vocal = _load_stereo(vocal_wav)
        vocal = _apply(_vocal_effect_board(mix_params.get("vocal_effects", [])), vocal)
        vocal *= _db_to_linear(mix_params.get("vocal_gain_db", 0.0))
        _add(vocal)
        del vocal

    if harmony_wav and mix_params.get("harmony_enabled", True):
        harmony = _load_stereo(harmony_wav)
        harmony *= _db_to_linear(mix_params.get("harmony_gain_db", -4.0))
        _add(harmony)
        del harmony

    if mix is None:
        return np.zeros((2, 0), dtype=np.float32)

    # Protect against clipping with a touch of headroom
    peak = float(np.abs(mix).max())
    if peak > 0.97:
        mix *= 0.97 / peak

    return mix


def to_mp3_bytes(mix: np.ndarray, bitrate: str = "192k") -> bytes:
    """Encode a (2, N) float mix to MP3 via FFmpeg."""
    import subprocess
    import tempfile
    import os

    wav_path = None
    mp3_path = None
    try:
        # soundfile wants (samples, channels)
        interleaved = mix.T
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wf:
            sf.write(wf, interleaved, SR, format="WAV", subtype="PCM_16")
            wav_path = wf.name
        mp3_path = wav_path[:-4] + ".mp3"
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-b:a", bitrate, mp3_path],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"MP3 encode failed: {result.stderr.decode()[:200]}")
        with open(mp3_path, "rb") as f:
            return f.read()
    finally:
        for p in (wav_path, mp3_path):
            if p and os.path.exists(p):
                os.remove(p)


def analyze_mix(mix: np.ndarray) -> dict:
    """
    Basic analysis of a rendered mix for "something feels off" help. Returns
    plain findings the LLM turns into friendly language (never raw numbers to
    the user).
    """
    if mix.shape[1] == 0:
        return {}
    mono = mix.mean(axis=0)
    rms = float(np.sqrt(np.mean(mono**2)))
    peak = float(np.abs(mono).max())

    # Rough spectral balance via FFT bands
    spectrum = np.abs(np.fft.rfft(mono[: SR * 10]))  # first 10s is enough
    freqs = np.fft.rfftfreq(min(len(mono), SR * 10), 1 / SR)
    low = float(spectrum[(freqs < 250)].mean()) if spectrum.size else 0.0
    mid = float(spectrum[(freqs >= 250) & (freqs < 4000)].mean()) if spectrum.size else 0.0
    high = float(spectrum[(freqs >= 4000)].mean()) if spectrum.size else 0.0
    total = low + mid + high + 1e-9

    return {
        "loudness": round(rms, 4),
        "headroom": round(1.0 - peak, 3),
        "low_ratio": round(low / total, 3),
        "mid_ratio": round(mid / total, 3),
        "high_ratio": round(high / total, 3),
        "low_heavy": bool(low / total > 0.5),
        "harsh": bool(high / total > 0.4),
    }
