"""
Pitch tracking: librosa's pYIN with a much faster decoding step.

librosa.pyin spends nearly all of its time in a Viterbi pass that, at every moment, considers every
possible jump between every pair of pitches (about 900 x 900 for a 3-octave search). Real pitch moves
are limited to a narrow band of nearby pitches, so almost all of those comparisons can never win.
This version builds the same observation probabilities and the same transition table as librosa, but
decodes with only the allowed transitions. The answer is the same; it arrives about 10 times sooner.

It leans on three of librosa's private helpers, so librosa is pinned (see requirements.txt) and
tests/test_properties_intake.py checks that the result equals librosa.pyin exactly. If a librosa
upgrade ever changes those helpers, that test fails instead of the results quietly drifting.
"""

from __future__ import annotations

from functools import lru_cache

import numba
import numpy as np
import scipy.stats
from librosa import sequence, util
from librosa.core import pitch as _pitch

_TINY = np.finfo(np.float64).tiny


@lru_cache(maxsize=8)
def _banded_predecessors(
    n_pitch_bins: int, transition_width: int, switch_prob: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    For each state, the states that can move into it and the log-probability of that move, in
    CSR layout. Built from librosa's own transition builders so the numbers are identical; only the
    impossible (zero) entries are left out.
    """
    local = sequence.transition_local(n_pitch_bins, transition_width, window="triangle", wrap=False)
    t_switch = sequence.transition_loop(2, 1 - switch_prob)
    n_states = 2 * n_pitch_bins

    # Which pitch bins can feed which, within one voicing block. local[i, j] is the move i -> j.
    cols: list[np.ndarray] = [np.nonzero(local[:, j])[0] for j in range(n_pitch_bins)]

    indptr = np.zeros(n_states + 1, dtype=np.int64)
    idx: list[int] = []
    logp: list[float] = []
    for j in range(n_states):
        block_to, local_to = divmod(j, n_pitch_bins)
        # Ascending order of the source state, so ties resolve to the first one, as librosa does.
        for block_from in (0, 1):
            for li in cols[local_to]:
                idx.append(block_from * n_pitch_bins + int(li))
                logp.append(float(np.log(t_switch[block_from, block_to] * local[li, local_to] + _TINY)))
        indptr[j + 1] = len(idx)
    return indptr, np.asarray(idx, dtype=np.int64), np.asarray(logp, dtype=np.float64)


def _jit(fn):
    """
    Compile with numba and keep the compiled code on disk so a restart does not pay the compile
    again. If the folder is read-only (some hosts), numba cannot cache and raises at import; fall
    back to compiling in memory, which only costs a few seconds on the first hum after a restart.
    """
    try:
        return numba.njit(cache=True)(fn)
    except RuntimeError:
        return numba.njit(cache=False)(fn)


@_jit
def _viterbi_banded(
    log_obs: np.ndarray,
    indptr: np.ndarray,
    idx: np.ndarray,
    logp: np.ndarray,
    log_init: np.ndarray,
) -> np.ndarray:
    n_steps, n_states = log_obs.shape
    value = np.empty((n_steps, n_states), dtype=np.float64)
    ptr = np.zeros((n_steps, n_states), dtype=np.uint16)   # at most a few thousand states
    for j in range(n_states):
        value[0, j] = log_obs[0, j] + log_init[j]
    for t in range(1, n_steps):
        for j in range(n_states):
            best = -np.inf
            arg = 0
            for k in range(indptr[j], indptr[j + 1]):
                i = idx[k]
                v = value[t - 1, i] + logp[k]
                if v > best:  # strict: the first of equal candidates wins, like np.argmax
                    best = v
                    arg = i
            ptr[t, j] = arg
            value[t, j] = log_obs[t, j] + best
    states = np.empty(n_steps, dtype=np.int64)
    last = 0
    top = value[n_steps - 1, 0]
    for j in range(1, n_states):
        if value[n_steps - 1, j] > top:
            top = value[n_steps - 1, j]
            last = j
    states[n_steps - 1] = last
    for t in range(n_steps - 2, -1, -1):
        states[t] = ptr[t + 1, states[t + 1]]
    return states


def pyin_fast(
    y: np.ndarray,
    *,
    fmin: float,
    fmax: float,
    sr: float,
    frame_length: int,
    hop_length: int,
    resolution: float = 0.1,
    n_thresholds: int = 100,
    beta_parameters: tuple[float, float] = (2, 18),
    boltzmann_parameter: float = 2,
    max_transition_rate: float = 35.92,
    switch_prob: float = 0.01,
    no_trough_prob: float = 0.01,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Same inputs and outputs as librosa.pyin (mono, centered frames, NaN where unvoiced)."""
    win_length = frame_length // 2
    getattr(_pitch, "__check_yin_params")(
        sr=sr, fmax=fmax, fmin=fmin, frame_length=frame_length, win_length=win_length
    )
    if y.ndim != 1:
        raise ValueError("pyin_fast takes one channel of audio")
    util.valid_audio(y, mono=False)

    padded = np.pad(y, [(frame_length // 2, frame_length // 2)], mode="constant")
    y_frames = util.frame(padded, frame_length=frame_length, hop_length=hop_length)
    min_period = int(np.floor(sr / fmax))
    max_period = min(int(np.ceil(sr / fmin)), frame_length - win_length - 1)

    yin_frames = _pitch._cumulative_mean_normalized_difference(
        y_frames, frame_length, win_length, min_period, max_period
    )
    parabolic_shifts = _pitch._parabolic_interpolation(yin_frames)

    thresholds = np.linspace(0, 1, n_thresholds + 1)
    beta_probs = np.diff(scipy.stats.beta.cdf(thresholds, beta_parameters[0], beta_parameters[1]))
    n_bins_per_semitone = int(np.ceil(1.0 / resolution))
    n_pitch_bins = int(np.floor(12 * n_bins_per_semitone * np.log2(fmax / fmin))) + 1

    observation_probs, voiced_prob = getattr(_pitch, "__pyin_helper")(
        yin_frames,
        parabolic_shifts,
        sr,
        thresholds,
        boltzmann_parameter,
        beta_probs,
        no_trough_prob,
        min_period,
        fmin,
        n_pitch_bins,
        n_bins_per_semitone,
    )
    # librosa wraps the helper in np.vectorize, which adds a leading axis of size 1.
    observation_probs = np.asarray(observation_probs).reshape(2 * n_pitch_bins, -1)

    max_semitones_per_frame = round(max_transition_rate * 12 * hop_length / sr)
    transition_width = max_semitones_per_frame * n_bins_per_semitone + 1
    indptr, idx, logp = _banded_predecessors(n_pitch_bins, transition_width, switch_prob)

    p_init = np.zeros(2 * n_pitch_bins)
    p_init[n_pitch_bins:] = 1 / n_pitch_bins
    states = _viterbi_banded(
        np.log(observation_probs.T + _TINY),
        indptr,
        idx,
        logp,
        np.log(p_init + _TINY),
    )

    freqs = fmin * 2 ** (np.arange(n_pitch_bins) / (12 * n_bins_per_semitone))
    f0 = freqs[states % n_pitch_bins]
    voiced_flag = states < n_pitch_bins
    f0 = np.where(voiced_flag, f0, np.nan)
    return f0, voiced_flag, np.asarray(voiced_prob).reshape(-1)[: len(f0)]
