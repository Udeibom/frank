"""
Listener measurements: pure functions of audio (listener spec 03, design "Measurements").

Every function takes float audio (mono shape (n,) or stereo shape (n, 2)) and a sample rate and returns a
plain number, or None when the audio is missing, silent or too short to measure. None means "could not
measure"; it is never replaced by zero (requirement 3.1). Nothing here touches the database or any file.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
from scipy import signal

MIN_SECONDS = 0.5            # shorter than this cannot be measured reliably
SILENCE_DB = -70.0           # absolute gate: below this is treated as silence (BS.1770 absolute gate)


def to_mono(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        return x.mean(axis=1) if x.shape[1] <= 2 else x.mean(axis=0)
    return x


def _usable(x: Optional[np.ndarray], sr: int) -> bool:
    if x is None or sr <= 0:
        return False
    x = np.asarray(x)
    return x.size >= MIN_SECONDS * sr and bool(np.all(np.isfinite(x)))


# ── level ────────────────────────────────────────────────────────────────

def _k_coefficients(sr: int) -> tuple[list[float], list[float], list[float], list[float]]:
    f0, g_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / sr)
    vh = 10 ** (g_db / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    b1 = [(vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]
    a1 = [1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0]
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / sr)
    a2 = [1.0, 2.0 * (k * k - 1.0) / (1.0 + k / q + k * k), (1.0 - k / q + k * k) / (1.0 + k / q + k * k)]
    return b1, a1, [1.0, -2.0, 1.0], a2


def _hop_energies(x: np.ndarray, sr: int, hop: int) -> np.ndarray:
    """
    K-weighted energy summed over channels, per hop of samples. Filtered a few seconds at a time with the
    filter state carried across (so it is exact), never holding more than one chunk of 64-bit samples.
    """
    b1, a1, b2, a2 = _k_coefficients(sr)
    ch = x.shape[1]
    zi1 = np.zeros((2, ch))
    zi2 = np.zeros((2, ch))
    n_hops = x.shape[0] // hop
    out = np.zeros(n_hops)
    chunk = hop * 50                                    # 5 seconds at a 0.1 s hop
    for start in range(0, n_hops * hop, chunk):
        end = min(start + chunk, n_hops * hop)
        seg = np.asarray(x[start:end], dtype=np.float64)
        y, zi1 = signal.lfilter(b1, a1, seg, axis=0, zi=zi1)
        y, zi2 = signal.lfilter(b2, a2, y, axis=0, zi=zi2)
        e = (y * y).sum(axis=1)
        out[start // hop: end // hop] = e.reshape(-1, hop).sum(axis=1)
    return out


def loudness(x: Optional[np.ndarray], sr: int) -> Optional[float]:
    """Gated, K-weighted integrated loudness in LUFS-like units. None when silent or too short."""
    if not _usable(x, sr):
        return None
    x = np.asarray(x)
    if x.ndim == 1:
        x = x[:, None]
    hop = int(0.1 * sr)
    block_hops = 4                                       # 400 ms blocks, 75% overlap (BS.1770)
    if x.shape[0] < block_hops * hop:
        return None
    e = _hop_energies(x, sr, hop)
    cs = np.concatenate([[0.0], np.cumsum(e)])
    n_blocks = len(e) - block_hops + 1
    starts = np.arange(n_blocks)
    ms = (cs[starts + block_hops] - cs[starts]) / (block_hops * hop)
    with np.errstate(divide="ignore"):
        lk = -0.691 + 10 * np.log10(np.maximum(ms, 1e-12))
    keep = lk > SILENCE_DB
    if not keep.any():
        return None
    rel = -0.691 + 10 * np.log10(ms[keep].mean()) - 10.0
    keep &= lk > rel
    if not keep.any():
        return None
    return float(-0.691 + 10 * np.log10(ms[keep].mean()))


def peak_db(x: Optional[np.ndarray]) -> Optional[float]:
    if x is None or np.asarray(x).size == 0:
        return None
    p = float(np.max(np.abs(x)))
    return None if p <= 1e-9 else 20 * math.log10(p)


def clipping_share(x: Optional[np.ndarray]) -> Optional[float]:
    """Share of samples sitting at (nearly) full scale."""
    if x is None or np.asarray(x).size == 0:
        return None
    return float(np.mean(np.abs(x) >= 0.999))


def noise_floor_db(x: Optional[np.ndarray], sr: int) -> Optional[float]:
    """Level of the quietest tenth of the recording (the hiss and room tone between sounds). None without clear pauses."""
    if not _usable(x, sr):
        return None
    m = to_mono(x)
    frame = int(0.05 * sr)
    n = m.size // frame
    if n < 5:
        return None
    rms = np.sqrt((m[: n * frame].reshape(n, frame) ** 2).mean(axis=1))
    floor_db = 20 * math.log10(max(np.percentile(rms, 10), 1e-9))
    loud_db = 20 * math.log10(max(np.percentile(rms, 90), 1e-9))
    if loud_db - floor_db < 15.0:
        return None        # no real pauses in the recording, so the quiet parts are not "room noise": cannot tell
    return float(floor_db)


# ── colour ───────────────────────────────────────────────────────────────

def _spectrum(m: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    freqs, psd = signal.welch(m, fs=sr, nperseg=min(4096, m.size))
    return freqs, psd


def brightness_hz(x: Optional[np.ndarray], sr: int) -> Optional[float]:
    """Spectral centroid: where the 'weight' of the sound sits, low means dark, high means bright."""
    if not _usable(x, sr):
        return None
    freqs, psd = _spectrum(to_mono(x), sr)
    total = psd.sum()
    return None if total <= 1e-18 else float((freqs * psd).sum() / total)


def band_share(x: Optional[np.ndarray], sr: int, lo: float, hi: float) -> Optional[float]:
    """Share of the sound's energy between lo and hi Hz."""
    if not _usable(x, sr):
        return None
    freqs, psd = _spectrum(to_mono(x), sr)
    total = psd.sum()
    if total <= 1e-18:
        return None
    return float(psd[(freqs >= lo) & (freqs < hi)].sum() / total)


def band_level_db(x: Optional[np.ndarray], sr: int, lo: float, hi: float) -> Optional[float]:
    if not _usable(x, sr):
        return None
    freqs, psd = _spectrum(to_mono(x), sr)
    e = psd[(freqs >= lo) & (freqs < hi)].sum()
    return None if e <= 1e-18 else float(10 * math.log10(e))


# ── density ──────────────────────────────────────────────────────────────

def onsets_per_bar(x: Optional[np.ndarray], sr: int, bars: float) -> Optional[float]:
    """How many new sounds start in each bar, on average. A measure of how busy the section is."""
    if not _usable(x, sr) or bars <= 0:
        return None
    import librosa

    m = to_mono(x).astype(np.float32)
    if np.max(np.abs(m)) < 1e-6:
        return None
    onsets = librosa.onset.onset_detect(y=m, sr=sr, units="time", hop_length=512)
    return float(len(onsets) / bars)


# ── similarity and change ────────────────────────────────────────────────

def _chroma(x: np.ndarray, sr: int) -> Optional[np.ndarray]:
    import librosa

    m = to_mono(x).astype(np.float32)
    if np.max(np.abs(m)) < 1e-6:
        return None
    return librosa.feature.chroma_stft(y=m, sr=sr, hop_length=2048, n_fft=4096)


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na < 1e-12 or nb < 1e-12 else float(np.dot(a, b) / (na * nb))


def similarity(a: Optional[np.ndarray], b: Optional[np.ndarray], sr: int) -> Optional[float]:
    """
    How alike two stretches of audio are, from 0 (nothing in common) to 1 (the same). Compares the notes
    heard over time (chroma, frame by frame) and the overall tone colour (MFCC averages). Two identical
    signals give about 1; a signal against silence gives 0.
    """
    if not (_usable(a, sr) and _usable(b, sr)):
        return None
    ca, cb = _chroma(a, sr), _chroma(b, sr)
    if ca is None or cb is None:
        return 0.0                                   # one side is silent: nothing in common
    n = min(ca.shape[1], cb.shape[1])
    frames = [_cos(ca[:, i], cb[:, i]) for i in range(n)]
    notes = float(np.mean(frames)) if frames else 0.0
    import librosa

    ma = librosa.feature.mfcc(y=to_mono(a).astype(np.float32), sr=sr, n_mfcc=13).mean(axis=1)[1:]
    mb = librosa.feature.mfcc(y=to_mono(b).astype(np.float32), sr=sr, n_mfcc=13).mean(axis=1)[1:]
    colour = (_cos(ma, mb) + 1) / 2
    return float(max(0.0, min(1.0, 0.7 * notes + 0.3 * colour)))


def change_between(a: Optional[np.ndarray], b: Optional[np.ndarray], sr: int) -> Optional[float]:
    """How different one section is from the next: 0 none, 1 completely. Loudness and colour included."""
    if not (_usable(a, sr) and _usable(b, sr)):
        return None
    sim = similarity(a, b, sr)
    la, lb = loudness(a, sr), loudness(b, sr)
    if sim is None or la is None or lb is None:
        return None
    loud = min(1.0, abs(la - lb) / 12.0)
    return float(max(0.0, min(1.0, 0.6 * (1 - sim) + 0.4 * loud)))


# ── voice against beat ───────────────────────────────────────────────────

def timing_offset_ms(vocal: Optional[np.ndarray], beat: Optional[np.ndarray], sr: int, max_ms: float = 300.0) -> Optional[tuple[float, float]]:
    """
    How far the vocal sits from the beat. Cross-correlates the 'new sound starts' curves of both.
    Returns (offset in ms, confidence 0..1). A positive offset means the vocal comes AFTER the beat.
    """
    if not (_usable(vocal, sr) and _usable(beat, sr)):
        return None
    import librosa

    hop = 256
    ev = librosa.onset.onset_strength(y=to_mono(vocal).astype(np.float32), sr=sr, hop_length=hop)
    eb = librosa.onset.onset_strength(y=to_mono(beat).astype(np.float32), sr=sr, hop_length=hop)
    n = min(ev.size, eb.size)
    if n < 20 or ev[:n].std() < 1e-6 or eb[:n].std() < 1e-6:
        return None
    ev, eb = (ev[:n] - ev[:n].mean()), (eb[:n] - eb[:n].mean())
    max_lag = int(max_ms / 1000 * sr / hop)
    corr = signal.correlate(ev, eb, mode="full")
    lags = signal.correlation_lags(n, n, mode="full")
    sel = np.abs(lags) <= max_lag
    c, l = corr[sel], lags[sel]
    norm = float(np.sqrt((ev ** 2).sum() * (eb ** 2).sum())) or 1.0
    best = int(np.argmax(c))
    offset_ms = float(l[best] * hop / sr * 1000)
    conf = float(max(0.0, min(1.0, c[best] / norm * 2.0)))
    return offset_ms, conf


def cents_off_scale(midi: np.ndarray, scale_pcs: set[int]) -> np.ndarray:
    """Distance in cents from each pitch to the nearest note of the song's scale."""
    out = np.empty(len(midi))
    pcs = sorted(scale_pcs)
    for i, m in enumerate(midi):
        best = 1e9
        base = math.floor(m)
        for cand in range(base - 2, base + 4):
            if cand % 12 in pcs:
                best = min(best, abs(m - cand) * 100.0)
        out[i] = best
    return out
