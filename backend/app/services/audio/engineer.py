"""
The recording engineer (sing-it spec 06, requirement 7): after each take, check the recording itself and say at
most ONE thing, kindly, with something to try. Never a word about the singing.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy import signal

from app.services.listener import config as cfg
from app.services.listener import dsp

QUIET_PEAK_DB = -24.0        # the loudest moment of the take is this far under full scale
BLEED_CORRELATION = 0.12     # how much of the beat's own shape shows up inside the take


def bleed_amount(take: np.ndarray, beat: Optional[np.ndarray], sr: int) -> Optional[float]:
    """0..1: how strongly the take contains the beat that was playing (normalised cross-correlation peak)."""
    if beat is None:
        return None
    n = min(take.shape[0], beat.shape[0], int(30 * sr))
    if n < sr:
        return None
    dec = 8
    a = signal.decimate(take[:n].astype(np.float64), dec)
    b = signal.decimate(dsp.to_mono(beat[:n]).astype(np.float64), dec)
    a, b = a - a.mean(), b - b.mean()
    norm = float(np.sqrt((a ** 2).sum() * (b ** 2).sum()))
    if norm < 1e-9:
        return None
    lag = int(0.15 * sr / dec)
    corr = signal.correlate(a, b, mode="full", method="fft")
    mid = corr.size // 2
    return float(np.abs(corr[mid - lag: mid + lag + 1]).max() / norm)


def check(take: np.ndarray, sr: int, beat: Optional[np.ndarray] = None, headphones: Optional[bool] = None) -> tuple[Optional[str], dict]:
    """(one plain sentence or None, the facts it was based on)."""
    facts: dict = {}
    clip = dsp.clipping_share(take) or 0.0
    peak = dsp.peak_db(take)
    noise = dsp.noise_floor_db(take, sr)
    bleed = bleed_amount(take, beat, sr) if headphones is not True else None
    facts.update(clipping=clip, peak_db=peak, noise_floor_db=noise, bleed=bleed)
    if clip > cfg.CLIPPING_SHARE:
        return ("That one was so loud in places that the mic couldn't hold it. Try moving about a hand's width back "
                "from the mic for the next take."), facts
    if peak is not None and peak < QUIET_PEAK_DB:
        return "The mic only just caught you on that one. Try coming a little closer, or singing toward the mic.", facts
    if bleed is not None and bleed > BLEED_CORRELATION:
        return ("The beat is getting into your mic. I can take it out of this take, or you could use headphones for "
                "the next one."), facts
    if noise is not None and noise > cfg.NOISE_FLOOR_DB:
        return ("I can hear some background noise between your lines, like a fan or a hum. If you can, switch it off "
                "or find a quieter spot."), facts
    return None, facts
