"""
Vocal comping — stitch the best moments from several takes into one.

We split each take into short time windows, score each window by how confidently
pitched and how energetic it is (a proxy for a committed, in-tune delivery), and
for each window pick the best take. The winning windows are concatenated with
short crossfades so the seams aren't audible.

The result is a suggestion the user can accept or adjust — never the final word.
All CPU, runs in a background job.
"""

from __future__ import annotations
import io
import numpy as np
import librosa
import soundfile as sf

SR = 44100
PITCH_SR = 16000  # scoring runs at reduced rate for fast pyin
WINDOW_SECONDS = 2.0
CROSSFADE_SECONDS = 0.05


def _load(wav_bytes: bytes) -> np.ndarray:
    y, _ = librosa.load(io.BytesIO(wav_bytes), sr=SR, mono=True)
    return y.astype(np.float32)


def _window_score(segment_lo: np.ndarray) -> float:
    """
    Higher is better: confident pitch + healthy energy.
    Expects the segment already downsampled to PITCH_SR for fast pyin.
    """
    if segment_lo.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(segment_lo**2)))
    try:
        _, _, voiced_prob = librosa.pyin(
            segment_lo,
            fmin=80.0,
            fmax=1000.0,
            sr=PITCH_SR,
            hop_length=1024,
            frame_length=2048,
        )
        pitch_conf = float(np.nanmean(voiced_prob)) if voiced_prob.size else 0.0
        if np.isnan(pitch_conf):
            pitch_conf = 0.0
    except Exception:
        pitch_conf = 0.0
    # Weight pitch confidence a bit higher than loudness
    return 0.6 * pitch_conf + 0.4 * min(rms * 5.0, 1.0)


def build_comp(takes: list[tuple[str, bytes]]) -> tuple[bytes, list[dict]]:
    """
    takes: list of (take_id, wav_bytes). Returns (comp_wav_bytes, segments).
    segments: [{take_id, start_time, end_time}] describing which take won each
    window — used by the UI to show the colour-coded comp.
    """
    if not takes:
        return b"", []

    # Full-rate audio for output, plus a downsampled copy per take for scoring
    loaded = [(tid, _load(b)) for tid, b in takes]
    loaded_lo = [
        (tid, librosa.resample(a, orig_sr=SR, target_sr=PITCH_SR))
        for tid, a in loaded
    ]
    max_len = max(a.shape[0] for _, a in loaded)
    win = int(WINDOW_SECONDS * SR)
    win_lo = int(WINDOW_SECONDS * PITCH_SR)
    fade = int(CROSSFADE_SECONDS * SR)

    comp = np.zeros(max_len, dtype=np.float32)
    segments: list[dict] = []
    prev_take: str | None = None

    for wi, start in enumerate(range(0, max_len, win)):
        end = min(start + win, max_len)
        start_lo = wi * win_lo
        # Score this window across all takes (on the downsampled copies)
        best_tid, best_audio, best_score = loaded[0][0], None, -1.0
        for (tid, audio), (_, audio_lo) in zip(loaded, loaded_lo):
            seg = audio[start:end]
            if seg.shape[0] < end - start:
                seg = np.pad(seg, (0, (end - start) - seg.shape[0]))
            seg_lo = audio_lo[start_lo:start_lo + win_lo]
            score = _window_score(seg_lo)
            if score > best_score:
                best_tid, best_audio, best_score = tid, seg, score

        if best_audio is None:
            continue

        # Crossfade into the previous window to hide seams
        chunk = best_audio.copy()
        if start > 0 and fade > 0 and chunk.shape[0] >= fade:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            chunk[:fade] *= ramp
            comp[start:start + fade] *= (1.0 - ramp)
        comp[start:end] += chunk[: end - start]

        # Record the segment (merge consecutive windows from the same take).
        # A tail window too short to survive 2-decimal rounding (< 5 ms, e.g. a
        # take 2 samples longer than the others) would become a zero-length
        # segment; fold it into the previous segment instead. Found by a
        # property-based test (tests/test_properties_comp.py).
        too_short = round(end / SR, 2) <= round(start / SR, 2)
        if segments and (prev_take == best_tid or too_short):
            segments[-1]["end_time"] = round(end / SR, 2)
        else:
            segments.append(
                {
                    "take_id": best_tid,
                    "start_time": round(start / SR, 2),
                    "end_time": round(end / SR, 2),
                }
            )
        if not too_short:
            prev_take = best_tid

    # Normalize
    peak = float(np.abs(comp).max())
    if peak > 0:
        comp *= 0.89 / peak

    buf = io.BytesIO()
    sf.write(buf, comp, SR, format="WAV", subtype="PCM_16")
    return buf.getvalue(), segments


# ── phrase by phrase (sing-it spec 06, requirement 5; design "Comp") ─────

SCORE_HOP = 1024             # a coarse pitch line is enough to score a phrase, and four times faster
JOIN_FADE_S = 0.03
IN_TUNE_CENTS = 35.0
WEIGHTS = {"tuning": 0.4, "timing": 0.25, "clarity": 0.2, "steadiness": 0.15}


def phrase_slots(takes: list[np.ndarray], sr: int) -> list[tuple[float, float]]:
    """Where anyone sang: each take's phrases (breath to breath), merged across takes (they share song time)."""
    from app.services.audio import vocal_notes

    spans: list[tuple[float, float]] = []
    for a in takes:
        found = vocal_notes.phrases_from_energy(a, sr)
        covered = sum(b - x for x, b in found)
        # A take with the beat in it (or constant noise) has no quiet gaps: it cannot say where lines start
        # and end, so only takes with real breaths draw the lines (found on prod Nov 18: one giant "line").
        if found and covered < 0.9 * (a.shape[0] / sr):
            spans += found
    if not spans:
        spans = [s for a in takes for s in vocal_notes.phrases_from_energy(a, sr)]
    spans.sort()
    merged: list[list[float]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + 0.05:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def tiles(slots: list[tuple[float, float]], length_s: float) -> list[tuple[float, float]]:
    """Cut the whole timeline so each phrase owns the gap halfway to its neighbours: joins fall in silence."""
    if not slots:
        return [(0.0, length_s)] if length_s > 0 else []
    cuts = [0.0] + [(slots[i][1] + slots[i + 1][0]) / 2 for i in range(len(slots) - 1)] + [length_s]
    return [(cuts[i], cuts[i + 1]) for i in range(len(slots)) if cuts[i + 1] > cuts[i]]


def score_phrase(audio: np.ndarray, sr: int, a: float, b: float, midi: np.ndarray, step: float, song) -> dict[str, float]:
    """The four scores (0..1) for one take in one phrase. A take that is silent there scores 0."""
    from app.services.audio.song_notes import target_note
    from app.services.listener import dsp

    seg = audio[int(a * sr):int(b * sr)]
    if seg.size < sr // 10 or float(np.sqrt(np.mean(seg ** 2))) < 1e-3:
        return {"tuning": 0.0, "timing": 0.0, "clarity": 0.0, "steadiness": 0.0, "total": 0.0}
    i, j = int(a / step), int(b / step)
    frames = midi[i:j]
    times = a + np.arange(frames.size) * step
    sung = [(t, m) for t, m in zip(times, frames) if np.isfinite(m)]
    if sung:
        good = sum(abs(target_note(m, song.at(t)) - m) * 100 <= IN_TUNE_CENTS for t, m in sung)
        tuning = good / len(sung)
    else:
        tuning = 0.3                                  # spoken or whispered: no pitch to judge
    spb = song.seconds_per_beat
    grid = spb / 2
    onset = next((t for t, _ in sung), a)
    timing = max(0.0, 1.0 - abs(round(onset / grid) * grid - onset) / (spb / 4))
    clip = dsp.clipping_share(seg) or 0.0
    clarity = max(0.0, 1.0 - clip * 200.0)
    hop = int(0.02 * sr)
    rms = np.sqrt(np.convolve(seg ** 2, np.ones(hop) / hop, mode="valid")[::hop]) if seg.size > hop else np.array([0.0])
    loud = 20 * np.log10(np.maximum(rms, 1e-6))
    loud = loud[loud > loud.max() - 30]
    steadiness = max(0.0, 1.0 - float(np.std(loud)) / 12.0) if loud.size else 0.0
    s = {"tuning": tuning, "timing": timing, "clarity": clarity, "steadiness": steadiness}
    s["total"] = sum(WEIGHTS[k] * v for k, v in s.items())
    return {k: round(float(v), 3) for k, v in s.items()}


def assemble(takes: dict[str, np.ndarray], sr: int, segments: list[dict]) -> np.ndarray:
    """The comp audio from tiles: each tile from its take, joined with a short crossfade inside the gap."""
    n = max(a.shape[0] for a in takes.values())
    out = np.zeros(n, dtype=np.float32)
    fade = int(JOIN_FADE_S * sr)
    for k, seg in enumerate(segments):
        a, b = int(round(seg["start_time"] * sr)), min(n, int(round(seg["end_time"] * sr)))
        lo, hi = max(0, a - (fade if k else 0)), min(n, b + (fade if k < len(segments) - 1 else 0))
        src = takes[seg["take_id"]]
        piece = np.zeros(hi - lo, dtype=np.float32)
        m = max(0, min(hi, src.shape[0]) - lo)
        piece[:m] = src[lo:lo + m]
        w = np.ones(hi - lo, dtype=np.float32)
        if k and fade:
            w[: 2 * fade] = np.linspace(0, 1, 2 * fade, dtype=np.float32)[: min(2 * fade, w.size)]
        if k < len(segments) - 1 and fade:
            w[-2 * fade:] = np.minimum(w[-2 * fade:], np.linspace(1, 0, 2 * fade, dtype=np.float32)[-min(2 * fade, w.size):])
        out[lo:hi] += piece * w
    return out


def build_phrase_comp(takes: list[tuple[str, bytes]], song=None) -> tuple[bytes, list[dict]]:
    """
    takes: (take_id, wav) in song time. Returns (comp wav, segments). Each segment is one phrase:
    {phrase_index, take_id, start_time, end_time, scores: {take_id: {...}}}. Segments tile the comp exactly.
    Falls back to the window comp when nobody sang a clear phrase.
    """
    from app.services.audio import vocal_notes
    from app.services.audio.song_notes import SongNotes

    if not takes:
        return b"", []
    song = song or SongNotes()
    loaded = {tid: _load(b) for tid, b in takes}
    length = max(a.shape[0] for a in loaded.values())
    slots = phrase_slots(list(loaded.values()), SR)
    if not slots:
        return build_comp(takes)
    lines = {tid: vocal_notes.contour(a, SR, hop=SCORE_HOP)[::2] for tid, a in loaded.items()}
    segments: list[dict] = []
    for k, ((a, b), (ta, tb)) in enumerate(zip(slots, tiles(slots, length / SR))):
        scores = {tid: score_phrase(loaded[tid], SR, a, b, lines[tid][0], lines[tid][1], song) for tid in loaded}
        best = max(loaded, key=lambda t: (scores[t]["total"], -list(loaded).index(t)))
        segments.append({"phrase_index": k, "take_id": best, "start_time": round(ta, 3), "end_time": round(tb, 3),
                         "phrase_start": round(a, 3), "phrase_end": round(b, 3), "section": song.section_at((a + b) / 2), "scores": scores})
    segments[-1]["end_time"] = round(length / SR, 3)
    return _write(assemble(loaded, SR, segments)), segments


def swap(takes: list[tuple[str, bytes]], segments: list[dict], phrase_index: int, take_id: str) -> tuple[bytes, list[dict]]:
    """The same comp with one phrase taken from another take (a NEW comp; the old one is kept by the caller)."""
    loaded = {tid: _load(b) for tid, b in takes}
    if take_id not in loaded:
        raise ValueError("That take isn't part of this comp.")
    new = [dict(s) for s in segments]
    hit = [s for s in new if s.get("phrase_index") == phrase_index]
    if not hit:
        raise ValueError("That phrase isn't in this comp.")
    hit[0]["take_id"] = take_id
    return _write(assemble(loaded, SR, new)), new


def _write(audio: np.ndarray) -> bytes:
    peak = float(np.abs(audio).max())
    if peak > 0.89:
        audio = audio * (0.89 / peak)
    buf = io.BytesIO()
    sf.write(buf, audio, SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()
