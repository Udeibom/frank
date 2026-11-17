"""
The Listener service (listener spec 03): measure a song, find issues, compare versions.

`measure_audio` and `score_facts` are pure: they take arrays and plans and return a MeasurementReport.
`measure_song` loads the active audio for a project, caches by audio version id, and never writes anything
except the cache row (requirement 4.1). Specialists call these functions directly; the HTTP route only wraps
`measure_song` in a job.
"""
from __future__ import annotations

import io
import logging
from typing import Any, Optional

import numpy as np

from app.services.generation import beat as beat_engine
from app.services.generation import composer, theory
from app.services.listener import config as cfg
from app.services.listener import dsp
from app.services.listener.models import Difference, MeasurementReport, SectionInfo, Unmeasured

log = logging.getLogger(__name__)
SR = 44100
LISTENER_VERSION = 1            # bump when measurements change, so cached reports are not reused


# ── score facts: what the song's own notes say (no audio) ────────────────

def score_facts(sections: list[beat_engine.SectionPlan], fp: dict, seed: int, lead: Any = None) -> dict[int, dict[str, Any]]:
    """
    Recompose each section (cheap, deterministic) and read facts straight from the notes: which parts play,
    how many notes per bar each plays, and how the melody sits on the chords. Needs no audio.
    """
    _, contexts, progressions = beat_engine.plan_contexts(sections, fp, seed, lead)
    facts: dict[int, dict[str, Any]] = {}
    for s, ctx in zip(sections, contexts):
        prog = progressions[s.name]
        parts = composer.compose_section(s.name, prog, s.bars, s.energy, s.density, layers=s.layers, ctx=ctx)
        notes_per_bar = {p.name: round(len(p.events) / max(1, s.bars), 2) for p in parts if p.events}
        info: dict[str, Any] = {"parts": sorted(notes_per_bar), "notes_per_bar": notes_per_bar}
        melody = next((p for p in parts if p.name == "melody" and p.events), None)
        if melody is not None:
            ev = sorted(melody.events, key=lambda e: e.start)
            strong = [e for e in ev if abs((e.start % 4.0) - round(e.start % 4.0)) < 0.2 and round(e.start % 4.0) in (0, 2)]
            fits = [e for e in strong if e.note % 12 in {n % 12 for n in composer_chord(prog, int(e.start // 4))}]
            if strong:
                info["melody_fit"] = len(fits) / len(strong)
            pitches = [e.note for e in ev]
            info["melody_range"] = float(max(pitches) - min(pitches))
            if len(pitches) > 1:
                info["melody_movement"] = float(np.mean(np.abs(np.diff(pitches))))
        facts[s.index] = info
    return facts


def composer_chord(progression: dict, bar: int) -> list[int]:
    chords = progression["chords"]
    return chords[bar % len(chords)]


# ── audio measurement ────────────────────────────────────────────────────

def _slice(x: Optional[np.ndarray], span: tuple[int, int], sr: int) -> Optional[np.ndarray]:
    if x is None:
        return None
    scale = sr / SR
    a, b = int(span[0] * scale), int(span[1] * scale)
    seg = x[a:b]
    return seg if seg.size else None


def _scale_pcs(key: Optional[str]) -> Optional[set[int]]:
    if not key:
        return None
    try:
        root, mode = theory.parse_key(key)
    except Exception:  # noqa: BLE001
        return None
    return {(root + i) % 12 for i in theory.SCALE_INTERVALS.get(mode, theory.SCALE_INTERVALS["minor"])}


def measure_audio(
    sections: list[beat_engine.SectionPlan],
    bpm: float,
    *,
    beat: Optional[np.ndarray] = None,
    vocal: Optional[np.ndarray] = None,
    mix: Optional[np.ndarray] = None,
    sr: int = SR,
    key: Optional[str] = None,
    score: Optional[dict[int, dict[str, Any]]] = None,
    scope: Optional[list[str]] = None,
    vocal_contour: Optional[list[dict]] = None,
) -> MeasurementReport:
    """
    Measure what is there. `scope` is a list of section names: only those sections are measured.
    Anything missing, silent or too short goes in `unmeasured` with a plain reason, never as a zero.
    """
    rep = MeasurementReport(scope=scope)
    v, un = rep.values, rep.unmeasured
    score = score or {}
    chosen = [s for s in sections if not scope or s.name in scope]
    rep.sections = [SectionInfo(index=s.index, name=s.name, bars=s.bars, parts=list(score.get(s.index, {}).get("parts", s.layers))) for s in chosen]
    spans = dict(zip((s.index for s in sections), beat_engine.section_spans(sections, bpm))) if sections and bpm > 0 else {}

    def put(k: str, val: Optional[float], why: str) -> None:
        if val is None or not np.isfinite(val):
            un.append(Unmeasured(id=k, why=why))
        else:
            v[k] = float(val)

    # ── the beat, section by section ──
    segs: dict[int, Optional[np.ndarray]] = {}
    if beat is None:
        un.append(Unmeasured(id="beat", why="There is no beat to listen to yet."))
    else:
        for s in chosen:
            seg = _slice(beat, spans[s.index], sr)
            segs[s.index] = seg
            name = f"the {s.name}"
            put(f"section.{s.index}.loudness", dsp.loudness(seg, sr), f"I couldn't measure how strong {name} plays: it is silent or too short.")
            put(f"section.{s.index}.onsets_per_bar", dsp.onsets_per_bar(seg, sr, s.bars), f"I couldn't tell how busy {name} is.")
            put(f"section.{s.index}.brightness", dsp.brightness_hz(seg, sr), f"I couldn't measure how bright {name} sounds.")
            put(f"section.{s.index}.low_share", dsp.band_share(seg, sr, 20, 200), f"I couldn't measure the low end of {name}.")
            facts = score.get(s.index)
            if facts:
                v[f"section.{s.index}.parts"] = float(len(facts["parts"]))
                for k in ("melody_fit", "melody_range", "melody_movement"):
                    if k in facts:
                        v[f"section.{s.index}.{k}"] = float(facts[k])
            else:
                v[f"section.{s.index}.parts"] = float(len(s.layers))
        order = [s for s in chosen]
        for a, b in zip(order, order[1:]):
            if b.index == a.index + 1:
                c = dsp.change_between(segs.get(a.index), segs.get(b.index), sr)
                if c is not None:
                    v[f"section.{b.index}.change"] = c
        # repetition: same-named sections, and the chorus against the verse
        for name in {s.name for s in chosen}:
            same = [s for s in chosen if s.name == name]
            for a, b in zip(same, same[1:]):
                sim = dsp.similarity(segs.get(a.index), segs.get(b.index), sr)
                if sim is not None:
                    v[f"repeat.{a.index}.{b.index}.sound"] = sim
        verse = next((s for s in chosen if s.name == "verse"), None)
        chorus = next((s for s in chosen if s.name == "chorus"), None)
        if verse and chorus:
            sim = dsp.similarity(segs.get(verse.index), segs.get(chorus.index), sr)
            if sim is not None:
                v["song.chorus_vs_verse"] = sim
        pk, cl = dsp.peak_db(beat), dsp.clipping_share(beat)
        if pk is not None:
            v["beat.peak"] = pk
        if cl is not None:
            v["beat.clipping"] = cl

    # ── the voice ──
    if vocal is None:
        un.append(Unmeasured(id="vocal", why="There is no vocal recording to listen to yet."))
    else:
        put("vocal.loudness", dsp.loudness(vocal, sr), "I couldn't measure how loud the vocal is: it is silent or too short.")
        put("vocal.noise_floor", dsp.noise_floor_db(vocal, sr), "I couldn't measure the background noise in the vocal.")
        pcs = _scale_pcs(key)
        voiced = [c for c in (vocal_contour or []) if c.get("confidence", 0) >= 0.5]
        if vocal_contour is None:
            pass
        elif pcs is None:
            un.append(Unmeasured(id="vocal.in_tune", why="I don't know the song's notes yet, so I can't tell how your singing sits against them."))
        elif len(voiced) * 0.064 < cfg.MIN_VOICED_SECONDS:
            un.append(Unmeasured(id="vocal.in_tune", why="There isn't enough singing to tell how steadily it sits on the notes."))
        else:
            cents = dsp.cents_off_scale(np.array([c["note"] for c in voiced]), pcs)
            v["vocal.in_tune"] = float(np.mean(cents <= cfg.IN_TUNE_WITHIN_CENTS))
            v["vocal.cents_off"] = float(np.median(cents))
        if beat is not None:
            t = dsp.timing_offset_ms(vocal, beat, sr)
            if t is None:
                un.append(Unmeasured(id="vocal.timing_ms", why="I couldn't tell where your singing sits against the beat."))
            else:
                v["vocal.timing_ms"], v["vocal.timing_confidence"] = t
            for s in chosen:
                vs, bs = _slice(vocal, spans[s.index], sr), segs.get(s.index)
                lv, lb = dsp.loudness(vs, sr), dsp.loudness(bs, sr)
                if lv is not None and lb is not None:
                    v[f"section.{s.index}.vocal_gap"] = lv - lb
                bv, bb = dsp.band_level_db(vs, sr, 200, 4000), dsp.band_level_db(bs, sr, 200, 4000)
                if bv is not None and bb is not None:
                    v[f"section.{s.index}.voice_band_gap"] = bv - bb

    # ── the whole mix ──
    if mix is not None:
        put("mix.loudness", dsp.loudness(mix, sr), "I couldn't measure the overall strength of the mix.")
        pk, cl = dsp.peak_db(mix), dsp.clipping_share(mix)
        if pk is not None:
            v["mix.peak"] = pk
        if cl is not None:
            v["mix.clipping"] = cl
    if beat is not None and score:
        un.append(Unmeasured(id="part_loudness", why="I can tell which parts play and how busy each is, but not how loud each one is on its own yet."))
    return rep


# ── loading audio for a project ──────────────────────────────────────────

def decode(data: bytes) -> np.ndarray:
    """Any stored audio file to mono float at 44.1 kHz."""
    import soundfile as sf

    from app.services.audio.convert import to_wav

    x, sr = sf.read(io.BytesIO(to_wav(data, "mp3")), dtype="float32")
    assert sr == SR
    return x if x.ndim == 1 else x.mean(axis=1)


def compare(a: MeasurementReport, b: MeasurementReport) -> list[Difference]:
    """What changed between two reports, in plain words, largest loudness changes first (read-only)."""
    out: list[Difference] = []
    for key in sorted(set(a.values) & set(b.values)):
        x, y = a.values[key], b.values[key]
        if key.endswith(".loudness") and abs(y - x) >= 1.0:
            what = key.split(".")[1] if key.startswith("section.") else "the song"
            word = "louder" if y > x else "quieter"
            label = "The whole song" if key == "mix.loudness" else f"Section {what}"
            out.append(Difference(id=key, plain=f"{label} plays {word}.", before=x, after=y))
        elif key.endswith(".onsets_per_bar") and abs(y - x) >= 1.0:
            out.append(Difference(id=key, plain=f"Section {key.split('.')[1]} is {'busier' if y > x else 'sparser'}.", before=x, after=y))
    return out
