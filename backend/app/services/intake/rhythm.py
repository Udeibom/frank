"""
A tapped or spoken rhythm becomes a groove (start-from-any-input spec 02, requirement 4).

Steps: find the hits (onset detection), work out the speed from how the hits are spaced, snap them onto a
16-step bar, keep the bar the person played most consistently, and say how sure we are. Louder hits become
the kick lane and softer hits the hat lane, so the person's own accents survive. Nothing is invented: a
step is in the groove only if the person hit it in at least half of the bars.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

SR = 22050
HOP = 128
MIN_HITS = 6
BPM_RANGE = (60, 160)
CONFIDENT_ENOUGH = 0.6


@dataclass
class Groove:
    ok: bool
    reason: Optional[str] = None
    tempo_bpm: Optional[int] = None
    tempo_confidence: float = 0.0
    kick: str = ""                 # 16 characters: x = hit, . = nothing
    hat: str = ""
    confidence: float = 0.0
    hits: int = 0
    bars_heard: int = 0
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "reason": self.reason, "tempo_bpm": self.tempo_bpm, "tempo_confidence": self.tempo_confidence,
            "kick": self.kick, "hat": self.hat, "confidence": self.confidence, "hits": self.hits, "bars_heard": self.bars_heard,
        }


def _fit_error(times: np.ndarray, bpm: float) -> float:
    """Average distance (in steps) of the hits from the nearest sixteenth at this speed."""
    step = 60.0 / bpm / 4.0
    pos = (times - times[0]) / step
    return float(np.mean(np.abs(pos - np.round(pos))))


def _repeat_score(times: np.ndarray, bpm: float) -> float:
    """How well the bars repeat at this speed: 1 when every bar has the same hits, lower when they differ."""
    step = 60.0 / bpm / 4.0
    pos = np.round((times - times[0]) / step).astype(int)
    bars = int(pos.max() // 16) + 1
    if bars < 2:
        return 0.5
    grid = np.zeros((bars, 16))
    for p in pos:
        grid[p // 16, p % 16] = 1
    majority = grid.mean(axis=0) >= 0.5
    return float(np.mean([np.mean(grid[b].astype(bool) == majority) for b in range(bars)]))


def _filled(times: np.ndarray, bpm: float) -> float:
    """Share of the 16 steps that carry a hit at this speed. A simpler reading fills fewer."""
    step = 60.0 / bpm / 4.0
    pos = np.round((times - times[0]) / step).astype(int) % 16
    return len(set(int(p) for p in pos)) / 16.0


def pick_tempo(times: np.ndarray) -> tuple[float, float]:
    """
    The speed at which the hits sit on a grid AND the bars repeat. When several speeds fit equally well the
    one nearest a natural pace wins, and the confidence drops, because a sparse rhythm really can be read
    more than one way (the person is then asked, never told).
    """
    scored = []
    for bpm in np.arange(BPM_RANGE[0], BPM_RANGE[1] + 0.01, 0.5):
        err = _fit_error(times, bpm)
        score = err + 0.4 * (1.0 - _repeat_score(times, bpm)) + 0.02 * abs(np.log2(bpm / 95.0))
        score += 0.15 * _filled(times, bpm)          # when two speeds fit, the one with fewer busy steps is simpler
        scored.append((score, bpm, err))
    scored.sort()
    best_score, best, err = scored[0]
    rival = next((s for s in scored if abs(s[1] - best) > 4), None)
    conf = max(0.0, min(1.0, 1.0 - err / 0.25))
    if rival is not None and rival[0] - best_score < 0.02:
        conf *= 0.5
    return float(best), float(conf)


def groove_from_audio(wav_bytes: bytes) -> Groove:
    import librosa

    try:
        y, _ = librosa.load(io.BytesIO(wav_bytes), sr=SR, mono=True)
    except Exception:  # noqa: BLE001
        return Groove(False, "I couldn't open that recording. Want to try tapping it again?")
    if y.size < SR or float(np.max(np.abs(y))) < 1e-3:
        return Groove(False, "I couldn't hear any taps. Could you tap a little louder and try again?")
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    frames = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP, backtrack=False)
    times = librosa.frames_to_time(frames, sr=SR, hop_length=HOP)
    win = int(0.06 * SR)
    strength = np.array([float(np.max(np.abs(y[int(t * SR): int(t * SR) + win]), initial=0.0)) for t in times])
    return groove_from_hits(times, strength)


def groove_from_hits(times: np.ndarray, strength: np.ndarray) -> Groove:
    times = np.asarray(times, dtype=float)
    strength = np.asarray(strength, dtype=float)
    if len(times) < MIN_HITS:
        return Groove(False, "I only heard a few taps. Could you tap a bar or two of the rhythm?", hits=len(times))
    bpm, tempo_conf = pick_tempo(times)
    step = 60.0 / bpm / 4.0
    pos = np.round((times - times[0]) / step).astype(int)
    # Start the first bar on the first hit, unless the first hit is clearly a pick-up (a much softer one).
    bars = int(pos.max() // 16) + 1
    if bars < 1:
        bars = 1
    cut = np.median(strength) if strength.size else 0.0
    hits_by_step = np.zeros((bars, 16))
    loud_by_step = np.zeros((bars, 16))
    for p, s in zip(pos, strength):
        b, st = divmod(int(p), 16)
        if b < bars:
            hits_by_step[b, st] = 1
            loud_by_step[b, st] = s
    seen = hits_by_step.sum(axis=0) / bars
    keep = seen >= 0.5 if bars >= 2 else seen > 0
    if not keep.any():
        return Groove(False, "The taps didn't settle into a pattern I could follow. Could you try once more, steadily?", hits=len(times))
    accent = np.array([loud_by_step[:, i][hits_by_step[:, i] > 0].mean() if keep[i] else 0.0 for i in range(16)])
    hi, lo = float(accent[keep].max()), float(accent[keep].min())
    if lo > 0 and hi / lo >= 1.4:
        # the person played some hits clearly harder: those are the kick, the softer ones the hat
        is_kick = [bool(keep[i] and accent[i] >= (hi + lo) / 2) for i in range(16)]
    else:
        # no accents to go on: hits on the beat are the kick, the ones between are the hat
        is_kick = [bool(keep[i] and i % 4 == 0) for i in range(16)]
    kick = "".join("x" if is_kick[i] else "." for i in range(16))
    hat = "".join("x" if keep[i] and not is_kick[i] else "." for i in range(16))
    # Confidence: how repeatable the bars were, and how well the taps fitted the grid.
    if bars >= 2:
        pattern = hits_by_step[:, keep] if keep.any() else hits_by_step
        agree = float(np.mean([np.mean(hits_by_step[b] == (seen >= 0.5)) for b in range(bars)]))
    else:
        agree = 0.6
    conf = float(max(0.0, min(1.0, 0.6 * agree + 0.4 * tempo_conf)))
    return Groove(True, None, int(round(bpm)), round(tempo_conf, 2), kick, hat, round(conf, 2), len(times), bars,
                  {"bpm_error_steps": round(_fit_error(times, bpm), 3)})


def groove_to_style_drums(groove: dict, base: dict[str, str]) -> dict[str, str]:
    """
    The style's drum lanes with the person's rhythm laid over them. Their kick and hat lanes replace the
    style's; the style's snare stays, so the beat keeps a backbeat the person did not have to tap.
    """
    kick, hat = groove.get("kick") or "", groove.get("hat") or ""
    if len(kick) != 16 or len(hat) != 16 or "x" not in kick + hat:
        return base
    out = dict(base)
    merged_hat = "".join("x" if hat[i] == "x" or (kick[i] == "x" and i % 2 == 1) else "." for i in range(16))
    out["kick"] = out["half_kick"] = kick
    out["hat"] = out["half_hat"] = merged_hat if "x" in merged_hat else base["hat"]
    return out


def render_preview_mp3(groove: Groove, bars: int = 2) -> bytes:
    """Play the pattern back on drums, at the speed that was tapped, so the person can say yes or no."""
    from app.services.generation import composer, renderer

    ev: list[composer.NoteEvent] = []
    for b in range(bars):
        for i in range(16):
            beat = b * 4.0 + i * 0.25
            if groove.kick[i] == "x":
                ev.append(composer.NoteEvent(composer.KICK, beat, 0.2, 100))
            if groove.hat[i] == "x":
                ev.append(composer.NoteEvent(composer.CLOSED_HAT, beat, 0.15, 80))
        ev.append(composer.NoteEvent(composer.SNARE, b * 4.0 + 1.0, 0.2, 90))
        ev.append(composer.NoteEvent(composer.SNARE, b * 4.0 + 3.0, 0.2, 90))
    part = composer.Part("drums", 0, True, ev)
    with renderer.SynthSession() as synth:
        audio = synth.render(part, float(groove.tempo_bpm or 90), bars * 4)
    return renderer.to_mp3_bytes(audio)
