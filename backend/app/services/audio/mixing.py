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
  "section_gain_db": { "chorus": 1.5 },    # per-section-name beat adjustments
  "parts": { "keys": { "level_db": -2.0, "sections": { "2": 1.0 }, "space_amount": 0.2 } },
  "interactions": { "vocal:keys": 0.3 },   # a loud voice gently clears the keys
  "drum_bus": { "on": true, "glue": 0.35 }
}

All CPU. Mixing holds a few full-length float buffers in memory, so it runs in a
background job and keeps only what it needs.
"""

from __future__ import annotations
import io
from typing import Callable
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
    Limiter,
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
def _space(kind: str, amount: float):
    from app.services.audio import plugins as studio

    return studio.space(kind, amount)


def _unit(value, default: float) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(amount):
        return default
    return max(0.0, min(1.0, amount))


def _vocal_effect_board(effect_ids: list[str], space_amount: float = 0.18) -> Pedalboard:
    plugins = []
    for eid in effect_ids:
        if eid == "space":          # "add a little space": a studio plate when installed (frankenstein spec 14, 3.6)
            amount = _unit(space_amount, 0.18)
            plugins.append(_space("plate", amount) or Reverb(room_size=0.35, wet_level=amount, dry_level=0.85))
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


def _section_spans(sections: list[dict], bpm: float) -> list[tuple[int, int]]:
    spans = []
    beats = 0.0
    seconds_per_beat = 60.0 / max(float(bpm), 1.0)
    for section in sections:
        start = int(round(beats * seconds_per_beat * SR))
        beats += float(section.get("bars", 4)) * 4.0
        end = int(round(beats * seconds_per_beat * SR))
        spans.append((start, end))
    return spans


def _apply_section_gains(
    audio: np.ndarray,
    section_gain_db: dict,
    sections: list[dict],
    bpm: float,
    per_index_db: dict | None = None,
) -> np.ndarray:
    by_name = section_gain_db or {}
    by_index = per_index_db or {}
    if not sections or (not by_name and not by_index):
        return audio
    spans = _section_spans(sections, bpm)
    length = audio.shape[1]
    gains = np.ones(length, dtype=np.float32)
    for i, (start, end) in enumerate(spans):
        end = min(end, length)
        if start >= end:
            continue
        value = by_index.get(str(i), by_index.get(i))
        if value is None:
            section = sections[i]
            value = by_name.get(section.get("name"))
            if value is None:
                value = by_name.get(section.get("label"))
        if value is None:
            continue
        try:
            db = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(db):
            continue
        gains[start:end] = _db_to_linear(max(-24.0, min(12.0, db)))
    fade = min(int(0.012 * SR), max(0, length // 8))
    if fade > 1:
        for boundary in (span[0] for span in spans[1:]):
            if boundary >= length:
                continue
            lo, hi = max(0, boundary - fade), min(length, boundary + fade)
            if lo < hi:
                left = gains[lo] if lo < boundary else gains[boundary - 1]
                right = gains[hi - 1] if hi > boundary else gains[boundary]
                gains[lo:hi] = np.linspace(left, right, hi - lo, dtype=np.float32)
    out = audio.copy()
    out *= gains[None, :]
    return out


def _duck(audio: np.ndarray, key: np.ndarray, amount: float) -> np.ndarray:
    amount = _unit(amount, 0.0) * 0.85
    if amount <= 0.0 or key.shape[1] == 0 or audio.shape[1] == 0:
        return audio
    window = max(1, int(0.03 * SR))
    mono = np.mean(np.abs(key[:, : audio.shape[1]]), axis=0) if key.shape[1] >= audio.shape[1] else np.mean(np.abs(key), axis=0)
    padded = np.pad(mono, (window // 2, window - window // 2))
    cumulative = np.cumsum(padded, dtype=np.float64)
    envelope = (cumulative[window:] - cumulative[:-window]) / window
    peak = float(envelope.max()) if envelope.size else 0.0
    if peak <= 1e-9:
        return audio
    gains = 1.0 - amount * (envelope / peak)
    n = min(audio.shape[1], gains.size)
    out = audio.copy()
    out[:, :n] *= gains[:n][None, :]
    return out


def _drum_bus_board(glue: float) -> Pedalboard:
    glue = _unit(glue, 0.35)
    plugins = [Compressor(threshold_db=-22.0, ratio=1.0 + glue * 2.5, attack_ms=12.0, release_ms=160.0)]
    if glue > 0.65:
        plugins.append(Limiter(threshold_db=-1.0))
    return Pedalboard(plugins)


PART_TONES = ("warmer", "brighter", "clearer")


def _part_board(settings: dict) -> Pedalboard:
    """One part's tone and space, in plain words (finish-and-intent spec 11, requirement 1.1)."""
    plugins = []
    tone = settings.get("tone")
    if tone == "warmer":
        plugins.append(LowShelfFilter(cutoff_frequency_hz=220, gain_db=2.5))
        plugins.append(HighShelfFilter(cutoff_frequency_hz=6000, gain_db=-1.5))
    elif tone == "brighter":
        plugins.append(HighShelfFilter(cutoff_frequency_hz=4500, gain_db=3.0))
    elif tone == "clearer":
        plugins.append(HighpassFilter(cutoff_frequency_hz=120))
        plugins.append(HighShelfFilter(cutoff_frequency_hz=3500, gain_db=1.5))
    if settings.get("space") or settings.get("space_amount"):
        amount = _unit(settings.get("space_amount", 0.2), 0.2)
        plugins.append(_space("room", amount) or Reverb(room_size=0.45, wet_level=amount, dry_level=0.9))
    return Pedalboard(plugins)


def render_mix(
    vocal_wav: bytes | None,
    beat_wav: bytes | None,
    harmony_wav: bytes | None,
    mix_params: dict,
    beat_sections: list[dict] | None = None,
    beat_bpm: float = 90,
    parts: list[tuple[str, Callable[[], bytes]]] | None = None,
    beat_start_s: float = 0.0,
) -> np.ndarray:
    """
    Combine the layers into one stereo float32 mix (channels-first), applying
    gains, effects, and per-section beat gains. Returns the mixed audio array.

    Memory: each source's decoded buffer is summed into the accumulator and then
    released before the next, so we don't hold vocal+beat+harmony all at once.
    """
    mix: np.ndarray | None = None
    # Music built from the singing starts where its first bar falls in the recording (core-path spec 15, 8):
    # a moment of silence before the music, never a shift of the voice.
    lead_in = max(0, int(round(float(beat_start_s or 0.0) * SR)))

    def _late(layer: np.ndarray) -> np.ndarray:
        if lead_in <= 0:
            return layer
        return np.concatenate([np.zeros((layer.shape[0], lead_in), dtype=layer.dtype), layer], axis=1)

    def _add(layer: np.ndarray) -> None:
        nonlocal mix
        if mix is None:
            mix = np.zeros(layer.shape, dtype=np.float32)
        if layer.shape[1] > mix.shape[1]:
            grown = np.zeros((2, layer.shape[1]), dtype=np.float32)
            grown[:, : mix.shape[1]] += mix
            mix = grown
        mix[:, : layer.shape[1]] += layer

    def _merge(base: np.ndarray | None, layer: np.ndarray) -> np.ndarray:
        if base is None:
            return layer.copy()
        if layer.shape[1] > base.shape[1]:
            grown = np.zeros((2, layer.shape[1]), dtype=np.float32)
            grown[:, : base.shape[1]] += base
            base = grown
        base[:, : layer.shape[1]] += layer
        return base

    interactions: dict[str, list[tuple[str, float]]] = {}
    for pair, amount in (mix_params.get("interactions") or {}).items():
        key, _, target = str(pair).partition(":")
        amount = _unit(amount, 0.0)
        if key and target and amount > 0.0:
            interactions.setdefault(target, []).append((key, amount))
    vocal = None
    if parts and any(key == "vocal" for ducks in interactions.values() for key, _ in ducks) and vocal_wav:
        vocal = _load_stereo(vocal_wav)

    if parts:
        # The beat as its parts: each fetched, treated, levelled and added, then released (512 MB server).
        # The whole-beat settings (its level, effects, per-section levels) still apply to every part.
        settings_for = mix_params.get("parts") or {}
        beat_board = _beat_effect_board(mix_params.get("beat_effects", []))
        needed_keys = {key for ducks in interactions.values() for key, _ in ducks if key != "vocal"}
        key_buffers = {}
        for name, fetch in parts:
            if name in needed_keys:
                key_buffers[name] = _load_stereo(fetch())
        bus = mix_params.get("drum_bus") or {}
        drum_bus: np.ndarray | None = None
        for name, fetch in parts:
            st = settings_for.get(name) or {}
            if st.get("muted"):
                continue
            part = _load_stereo(fetch())
            part = _apply(_part_board(st), part)
            part = _apply_section_gains(part, {}, beat_sections or [], beat_bpm, st.get("sections") or {})
            part = _apply(beat_board, part)
            part = _apply_section_gains(part, mix_params.get("section_gain_db", {}), beat_sections or [], beat_bpm)
            for key, amount in interactions.get(name, []):
                key_audio = vocal if key == "vocal" else key_buffers.get(key)
                if key_audio is not None:
                    part = _duck(part, key_audio, amount)
            part *= _db_to_linear(float(st.get("level_db", 0.0)) + float(mix_params.get("beat_gain_db", -6.0)))
            if name == "drums" and bus.get("on"):
                drum_bus = _merge(drum_bus, part)
            else:
                _add(_late(part))
            del part
        if drum_bus is not None:
            drum_bus = _apply(_drum_bus_board(float(bus.get("glue", 0.35))), drum_bus)
            _add(_late(drum_bus))
            del drum_bus
    elif beat_wav:
        beat = _load_stereo(beat_wav)
        beat = _apply(_beat_effect_board(mix_params.get("beat_effects", [])), beat)
        beat = _apply_section_gains(
            beat, mix_params.get("section_gain_db", {}), beat_sections or [], beat_bpm
        )
        beat *= _db_to_linear(mix_params.get("beat_gain_db", -6.0))
        _add(_late(beat))
        del beat

    if vocal_wav:
        if vocal is None:
            vocal = _load_stereo(vocal_wav)
        vocal = _apply(_vocal_effect_board(mix_params.get("vocal_effects", []),
                                           mix_params.get("vocal_space_amount", 0.18)), vocal)
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

    atmo = mix_params.get("atmosphere") or {}
    if atmo.get("url") and atmo.get("enabled", True):
        # A recorded or generated atmosphere (frankenstein spec 14, 3.7): one removable layer, looped under the
        # whole song, faded in and out, kept low. It never fails the mix.
        try:
            from app.services.storage.signing import fetch_audio_bytes

            layer = _load_stereo(fetch_audio_bytes(atmo["url"]))
            mix += atmosphere_bed(layer, mix.shape[1], float(atmo.get("level_db", -20.0)))
            del layer
        except Exception:  # noqa: BLE001
            pass

    # Protect against clipping with a touch of headroom
    peak = float(np.abs(mix).max())
    if peak > 0.97:
        mix *= 0.97 / peak

    return mix


def atmosphere_bed(layer: np.ndarray, length: int, level_db: float, fade_s: float = 3.0) -> np.ndarray:
    """Loop a (2, N) sound to `length` samples with short crossfades at the joins, fade the ends, set its level."""
    if layer.shape[1] == 0 or length <= 0:
        return np.zeros((2, max(0, length)), dtype=np.float32)
    xf = min(int(0.5 * SR), layer.shape[1] // 4)
    out = np.zeros((2, length), dtype=np.float32)
    pos = 0
    ramp = np.linspace(0, 1, xf, dtype=np.float32) if xf > 0 else np.zeros(0, dtype=np.float32)
    while pos < length:
        seg = layer[:, : min(layer.shape[1], length - pos)].astype(np.float32).copy()
        if pos > 0 and xf > 0 and seg.shape[1] > xf:
            seg[:, :xf] *= ramp
            out[:, pos : pos + xf] *= 1 - ramp[: min(xf, length - pos)]
        out[:, pos : pos + seg.shape[1]] += seg
        step = layer.shape[1] - xf if layer.shape[1] > xf else layer.shape[1]
        pos += max(1, step)
    f = min(int(fade_s * SR), length // 2)
    if f > 0:
        out[:, :f] *= np.linspace(0, 1, f, dtype=np.float32)
        out[:, -f:] *= np.linspace(1, 0, f, dtype=np.float32)
    peak = float(np.abs(out).max()) or 1.0
    return out / peak * _db_to_linear(level_db)


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
