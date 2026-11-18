"""
Beat bleed removal (sing-it spec 06, requirement 4; design "Bleed removal").

When the beat played through speakers, the mic recorded it too. Frank made the beat, so it knows exactly what was
playing. Steps: line the beat up with the take (cross-correlation), learn how loud the beat arrives at the mic in
each frequency band from moments when the person is not singing, then take that much beat out of every moment
with a soft mask (never below MASK_FLOOR, so the voice does not sound underwater).
The result is only kept when it measurably removes beat and keeps the voice (ACCEPT_*); otherwise the take stays
as recorded and Frank says so. Processed in chunks so a three-minute take fits in the free server's memory.
"""
from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from scipy import signal

N_FFT, HOP = 2048, 512
CHUNK_S = 20.0
MASK_FLOOR = 0.1
OVER_SUBTRACT = 1.5          # take a little more than the estimate: room echo makes the beat arrive smeared
MAX_LAG_S = 0.15
ACCEPT_REDUCTION_DB = 6.0
ACCEPT_VOICE_DROP_DB = 2.0
MIN_GAP_FRAMES = 50          # moments without singing needed to learn how the beat arrives
VOICE_SHARE = 0.5            # a frame is singing when more than half its sound is not the beat


@dataclass
class BleedReport:
    accepted: bool
    reduction_db: float          # how much quieter the beat is inside the take
    voice_change_db: float       # how much the voice itself changed (negative: quieter)
    lag_ms: float
    reason: str = ""


def _mono(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return x.mean(axis=1) if x.ndim == 2 else x


def find_lag(take: np.ndarray, beat: np.ndarray, sr: int) -> int:
    """Samples the beat must move later to line up with how it sits inside the take."""
    span = min(take.shape[0], beat.shape[0], int(30 * sr))
    if span < sr:
        return 0
    dec = 8                                  # 5.5 kHz is enough to line two recordings up
    a = signal.decimate(take[:span], dec).astype(np.float32)
    b = signal.decimate(beat[:span], dec).astype(np.float32)
    corr = signal.correlate(a, b, mode="full", method="fft")
    lags = signal.correlation_lags(a.size, b.size, mode="full")
    sel = np.abs(lags) <= int(MAX_LAG_S * sr / dec)
    return int(lags[sel][int(np.argmax(np.abs(corr[sel])))] * dec)


def _shift(x: np.ndarray, lag: int, n: int) -> np.ndarray:
    out = np.zeros(n, dtype=np.float32)
    if lag >= 0:
        m = min(n - lag, x.shape[0])
        if m > 0:
            out[lag:lag + m] = x[:m]
    else:
        m = min(n, x.shape[0] + lag)
        if m > 0:
            out[:m] = x[-lag:-lag + m]
    return out


def _chunks(n: int, sr: int):
    size = int(CHUNK_S * sr)
    for a in range(0, n, size):
        yield a, min(n, a + size)


def remove(take: np.ndarray, beat: np.ndarray, sr: int, voiced: np.ndarray | None = None) -> tuple[np.ndarray, BleedReport]:
    """`take` and `beat` in song time at the same rate. Returns (cleaned or original take, report)."""
    take = _mono(take)
    beat = _mono(beat)
    n = take.shape[0]
    lag = find_lag(take, beat, sr)
    b = _shift(beat, lag, n)
    if np.sqrt(np.mean(b ** 2)) < 1e-5:
        return take.copy(), BleedReport(False, 0.0, 0.0, 0.0, "no beat under this take")
    total_frames = 1 + n // HOP
    lo_bin, hi_bin = int(200 * N_FFT / sr), int(4000 * N_FFT / sr)

    def learn(mask: np.ndarray | None) -> tuple[np.ndarray, int]:
        """Least squares on power, |take|^2 ~ g^2 |beat|^2, over frames where `mask` says nobody sings."""
        cross = np.zeros(N_FFT // 2 + 1)
        energy = np.zeros(N_FFT // 2 + 1)
        used = 0
        for a, z in _chunks(n, sr):
            P = np.abs(librosa.stft(take[a:z], n_fft=N_FFT, hop_length=HOP)).astype(np.float64) ** 2
            Q = np.abs(librosa.stft(b[a:z], n_fft=N_FFT, hop_length=HOP)).astype(np.float64) ** 2
            f0 = a // HOP
            keep = np.ones(P.shape[1], dtype=bool) if mask is None else ~np.pad(mask[f0:f0 + P.shape[1]], (0, max(0, P.shape[1] - mask[f0:f0 + P.shape[1]].size)))[: P.shape[1]]
            cross += (P[:, keep] * Q[:, keep]).sum(axis=1)
            energy += (Q[:, keep] ** 2).sum(axis=1)
            used += int(keep.sum())
            del P, Q
        return np.sqrt(cross / np.maximum(energy, 1e-30)), used

    def singing(g: np.ndarray) -> np.ndarray:
        """Frames whose sound in the voice's range is mostly NOT explained by the beat."""
        share = np.ones(total_frames)
        for a, z in _chunks(n, sr):
            P = np.abs(librosa.stft(take[a:z], n_fft=N_FFT, hop_length=HOP))[lo_bin:hi_bin].astype(np.float64) ** 2
            Q = np.abs(librosa.stft(b[a:z], n_fft=N_FFT, hop_length=HOP))[lo_bin:hi_bin].astype(np.float64) ** 2
            left = np.maximum(P - (g[lo_bin:hi_bin, None] ** 2) * Q, 0.0).sum(axis=0) / np.maximum(P.sum(axis=0), 1e-20)
            f0 = a // HOP
            k = min(left.size, total_frames - f0)
            share[f0:f0 + k] = left[:k]
            del P, Q
        flags = np.convolve((share > VOICE_SHARE).astype(float), np.ones(5), mode="same") > 0   # word edges count as voice
        if (~flags).sum() < MIN_GAP_FRAMES:
            # loud bleed makes every moment look like singing at first: learn from the third least like singing
            flags = share > np.percentile(share, 33)
        return flags

    if voiced is None:
        g0, _ = learn(None)                      # the voice is not the beat, so this only overestimates a little
        voiced = singing(g0)
    g, used = learn(voiced)
    if used < MIN_GAP_FRAMES:
        return take.copy(), BleedReport(False, 0.0, 0.0, lag / sr * 1000, "not enough moments without singing to learn the beat")
    gain = g[:, None]

    # pass 2: soft mask, overlap-added chunk by chunk
    out = np.zeros(n, dtype=np.float32)
    weight = np.zeros(n, dtype=np.float32)
    pad = N_FFT
    for a, z in _chunks(n, sr):
        lo, hi = max(0, a - pad), min(n, z + pad)
        T = librosa.stft(take[lo:hi], n_fft=N_FFT, hop_length=HOP)
        B = np.abs(librosa.stft(b[lo:hi], n_fft=N_FFT, hop_length=HOP))
        B = signal.convolve2d(B, np.ones((1, 3)) / 3.0, mode="same")          # smear a little: room echo
        est = OVER_SUBTRACT * gain * B
        mag = np.abs(T)
        mask = np.clip(1.0 - (est ** 2) / np.maximum(mag ** 2, 1e-12), MASK_FLOOR, 1.0)
        y = librosa.istft(T * mask, hop_length=HOP, length=hi - lo).astype(np.float32)
        w = np.ones(hi - lo, dtype=np.float32)
        ramp = np.linspace(0, 1, pad, dtype=np.float32)
        if lo > 0:
            w[:pad] = ramp
        if hi < n:
            w[-pad:] = ramp[::-1]
        out[lo:hi] += y * w
        weight[lo:hi] += w
        del T, B, est, mag, mask, y
    out /= np.maximum(weight, 1e-6)

    report = judge(take, out, b, voiced, sr)
    report.lag_ms = round(float(lag / sr * 1000), 1)
    if not report.accepted:
        return take.copy(), report
    return out, report


def _db(x: np.ndarray) -> float:
    return 10 * np.log10(max(float(np.mean(x.astype(np.float64) ** 2)), 1e-12))


def judge(before: np.ndarray, after: np.ndarray, beat: np.ndarray, voiced: np.ndarray, sr: int) -> BleedReport:
    """
    How much beat is left: the level in moments without singing, where only the beat is heard. How much the voice
    changed: the level in sung moments. Both in dB.
    """
    frame_of = (np.arange(before.shape[0]) // HOP).clip(0, voiced.size - 1)
    sung = voiced[frame_of]
    if sung.all() or not sung.any():
        return BleedReport(False, 0.0, 0.0, 0.0, "I couldn't tell the singing from the gaps")
    reduction = _db(before[~sung]) - _db(after[~sung])
    # The sung moments held voice AND beat; the voice alone is what is left after the beat's own level
    # (as heard in the gaps) is taken away. The voice "changed" if the result is far from that.
    p_before = 10 ** (_db(before[sung]) / 10)
    p_beat = 10 ** (_db(before[~sung]) / 10)
    voice_alone = max(p_before - p_beat, p_before * 0.05)
    voice_change = _db(after[sung]) - 10 * np.log10(voice_alone)
    ok = reduction >= ACCEPT_REDUCTION_DB and voice_change > -ACCEPT_VOICE_DROP_DB
    reason = "" if ok else ("the beat was hardly in there" if reduction < ACCEPT_REDUCTION_DB else "it would have changed your voice too much")
    return BleedReport(bool(ok), round(float(reduction), 1), round(float(voice_change), 1), 0.0, reason)
