"""
Beat builder: assembles a whole song's instrumental from the engine (song-engine spec 04).

A beat is a list of sections (intro, verse, chorus, ...). Because every note is composed on purpose,
we know exactly where each section starts and ends and which parts are in it.

What this module is responsible for, and why:
  - EXACT TIMING. A section's audio is placed at the sample where its bars begin (computed from the
    running total, so rounding never drifts). A section's last notes are allowed to ring over the
    next section instead of being followed by a silent gap. The beat is exactly as long as its bars,
    plus the final ringing tail. The Mix Room's section gains and the vocal timing rely on this.
  - DELIBERATE LOUDNESS. Each section is set to a loudness for its job in the song (a chorus is the
    loudest, an intro and outro sit back), instead of every section being pushed to the same level.
  - TONE. The fingerprint's warmth and brightness tilt the sound; they are no longer ignored.
  - SEEDS. The same seed gives the same song; a new seed gives a different one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.services.generation import composer, fingerprint as fp_utils, moments as moments_mod, theory
from app.services.generation.renderer import SAMPLE_RATE, TAIL_SECONDS, SynthSession
from app.services.generation.rng import derive_seed
from app.services.generation.styles import StyleChoice, pick_style

# A standard song arrangement. Each entry is (section_name, bars).
DEFAULT_ARRANGEMENT = [
    ("intro", 4),
    ("verse", 8),
    ("chorus", 8),
    ("verse", 8),
    ("chorus", 8),
    ("bridge", 4),
    ("chorus", 8),
    ("outro", 4),
]

# Energy multiplier per section: choruses lift, intros and outros sit back.
SECTION_ENERGY = {
    "intro": 0.6,
    "verse": 0.8,
    "pre-chorus": 0.95,
    "chorus": 1.1,
    "bridge": 0.7,
    "outro": 0.5,
}

# Which version of the chord pattern each kind of section uses (the song's seed shifts all of them).
ROLE_VARIANT = {"intro": 0, "verse": 0, "pre-chorus": 1, "chorus": 1, "bridge": 2, "outro": 0}

# How loud each kind of section is, in decibels relative to the first chorus.
CHORUS_RMS_DB = -18.0
LOUDNESS_OFFSET_DB = {"intro": -5.0, "verse": -2.5, "pre-chorus": -1.2, "chorus": 0.0, "bridge": -3.5, "outro": -6.0}
LATER_CHORUS_BONUS_DB = 0.7
MAX_GAIN_DB = 24.0
MIN_GAIN_DB = -18.0

# How loud each part is against the others before the section is set to its level.
PART_GAIN = {
    "drums": 1.0, "bass": 1.0, "keys": 0.75, "melody": 0.9, "pad": 0.55, "strings": 0.5, "arp": 0.5,
    "color": 0.6, "color_once": 0.6, "riser": 0.45, "sweep": 0.4,
    "finale_keys": 0.8, "finale_pad": 0.5, "finale_bass": 1.0, "finale_drums": 1.0,
}

PEAK_TARGET = 0.89
FADE_OUT_SECONDS = 1.5
EQ_MIN_DB = 0.25


@dataclass
class SectionPlan:
    """One section of the arrangement."""
    index: int
    name: str            # "intro", "verse", "chorus", ...
    label: str           # user-facing label, defaults to a title-cased name
    bars: int
    energy: float
    density: float
    layers: list[str]    # which parts are present
    repeat: int = 0      # how many sections of this kind came before it
    final: bool = False  # the last section of its kind
    # Rendered stems: stem_type -> int16 stereo audio
    stems: dict[str, np.ndarray] = field(default_factory=dict)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _stamp_repeats(sections: list[SectionPlan]) -> None:
    """Fill in `repeat` and `final` from the order of the sections."""
    seen: dict[str, int] = {}
    totals: dict[str, int] = {}
    for s in sections:
        totals[s.name] = totals.get(s.name, 0) + 1
    for s in sections:
        s.repeat = seen.get(s.name, 0)
        seen[s.name] = s.repeat + 1
        s.final = s.repeat + 1 == totals[s.name]


def default_seed(fp: dict) -> int:
    """A seed that depends only on the fingerprint, so the same feeling gives the same first song."""
    return derive_seed(json.dumps(fp, sort_keys=True, default=str))


def build_beat_plan(
    fingerprint: dict, arrangement=None, seed: Optional[int] = None
) -> tuple[list[SectionPlan], dict]:
    """
    Build the section plan (no audio yet) from a fingerprint.
    Returns (sections, normalized_fingerprint).
    """
    fp = fp_utils.normalize(fingerprint)
    style = pick_style(fp)
    arrangement = arrangement or DEFAULT_ARRANGEMENT
    base_energy = fp["energy_level"]
    base_density = fp["density"]

    sections: list[SectionPlan] = []
    for i, (name, bars) in enumerate(arrangement):
        mult = SECTION_ENERGY.get(name, 0.8)
        energy = _clamp(base_energy * mult)
        # Density tracks energy a bit so bigger sections feel fuller
        density = _clamp(base_density * (0.8 + 0.4 * mult))
        sections.append(
            SectionPlan(i, name, name.capitalize(), int(bars), energy, density, layers=[])
        )
    _stamp_repeats(sections)
    for s in sections:
        s.layers = composer.layers_for_section(s.name, s.energy, s.density, s.repeat, s.final, style)
    return sections, fp


def section_spans(sections: list[SectionPlan], bpm: float) -> list[tuple[int, int]]:
    """
    (start, end) sample of every section. Both come from the running total of beats, so a section
    ends exactly where the next begins and rounding never builds up.
    """
    spans: list[tuple[int, int]] = []
    beats = 0
    seconds_per_beat = 60.0 / bpm
    for s in sections:
        start = int(round(beats * seconds_per_beat * SAMPLE_RATE))
        beats += s.bars * 4
        end = int(round(beats * seconds_per_beat * SAMPLE_RATE))
        spans.append((start, end))
    return spans


def plan_contexts(
    sections: list[SectionPlan], fp: dict, seed: int
) -> tuple[StyleChoice, list[composer.SectionContext], dict[str, dict]]:
    """
    Everything the composer needs per section: the style, where it sits in the song, and the chord
    progression for each kind of section (a verse keeps the same chords every time it comes back).
    """
    style = pick_style(fp)
    offset = derive_seed(seed, "chords") % 4
    progressions: dict[str, dict] = {}
    for s in sections:
        if s.name not in progressions:
            progressions[s.name] = theory.build_progression(
                key=fp["key"],
                energy=fp["energy_level"],
                tempo_feel=fp["tempo_feel"],
                variant=(ROLE_VARIANT.get(s.name, 0) + offset) % 4,
                extension=style.extension,
                seed=derive_seed(seed, "voicing", s.name),
            )
    planned = moments_mod.plan_moments(moments_mod.facts_from(sections), seed, fp["warmth"], fp["brightness"])
    contexts: list[composer.SectionContext] = []
    for i, s in enumerate(sections):
        nxt = sections[i + 1] if i + 1 < len(sections) else None
        contexts.append(
            composer.SectionContext(
                name=s.name,
                index=s.index,
                repeat=s.repeat,
                final=s.final,
                seed=seed,
                style=style,
                next_name=nxt.name if nxt else None,
                next_energy=nxt.energy if nxt else None,
                moments=planned.get(s.index, []),
            )
        )
    return style, contexts, progressions


def _target_db(section: SectionPlan) -> float:
    target = CHORUS_RMS_DB + LOUDNESS_OFFSET_DB.get(section.name, -2.5)
    if section.name == "chorus":
        target += LATER_CHORUS_BONUS_DB * min(section.repeat, 2)
    return target


def _tone_tilt(audio: np.ndarray, fp: dict) -> np.ndarray:
    """Warmth lifts the low end, brightness lifts the top. Skipped when the change would be inaudible."""
    low_db = (fp["warmth"] - 0.5) * 6.0
    high_db = (fp["brightness"] - 0.5) * 8.0
    if abs(low_db) < EQ_MIN_DB and abs(high_db) < EQ_MIN_DB:
        return audio
    from pedalboard import HighShelfFilter, LowShelfFilter, Pedalboard

    board = Pedalboard([])
    if abs(low_db) >= EQ_MIN_DB:
        board.append(LowShelfFilter(cutoff_frequency_hz=200.0, gain_db=low_db))
    if abs(high_db) >= EQ_MIN_DB:
        board.append(HighShelfFilter(cutoff_frequency_hz=5000.0, gain_db=high_db))
    out = board(audio.T.astype(np.float32), SAMPLE_RATE)
    return out.T


def render_song(
    sections: list[SectionPlan], fp: dict, seed: Optional[int] = None
) -> tuple[list[np.ndarray], np.ndarray]:
    """
    Render the whole song. Returns (per_section_audio, full_audio), both int16 stereo.
    The per-section slices are exactly the section's bars long; the full audio also holds the final
    ringing tail. Memory stays bounded: one float32 song buffer plus one section at a time.
    """
    if not sections:
        empty = np.zeros((0, 2), dtype=np.int16)
        return [], empty
    seed = default_seed(fp) if seed is None else seed
    bpm = float(fp["tempo_bpm"])
    spans = section_spans(sections, bpm)
    tail = int(TAIL_SECONDS * SAMPLE_RATE)
    total = spans[-1][1]
    song = np.zeros((total + tail, 2), dtype=np.float32)
    _, contexts, progressions = plan_contexts(sections, fp, seed)

    with SynthSession() as synth:
        for s, ctx, (start, end) in zip(sections, contexts, spans):
            parts = composer.compose_section(
                section=s.name,
                progression=progressions[s.name],
                bars=s.bars,
                energy=s.energy,
                density=s.density,
                layers=s.layers,
                ctx=ctx,
            )
            acc = np.zeros((end - start + tail, 2), dtype=np.float32)
            for part in parts:
                stem = synth.render(part, bpm, s.bars * 4)
                n = min(stem.shape[0], acc.shape[0])
                acc[:n] += stem[:n].astype(np.float32) * PART_GAIN.get(part.name, 0.7)
                del stem
            body = acc[: end - start]
            rms = float(np.sqrt(np.mean(np.square(body, dtype=np.float64)))) if body.size else 0.0
            if rms > 0:
                wanted = _target_db(s)
                gain_db = wanted - 20.0 * np.log10(rms / 32768.0)
                gain_db = max(MIN_GAIN_DB, min(MAX_GAIN_DB, gain_db))
                acc *= float(10.0 ** (gain_db / 20.0))
            song[start : start + acc.shape[0]] += acc            # the tail rings over the next section
            del acc

    song = _tone_tilt(song, fp)
    peak = float(np.abs(song).max())
    if peak > 0:
        song *= (PEAK_TARGET * 32767.0) / peak
    fade = min(int(FADE_OUT_SECONDS * SAMPLE_RATE), tail)
    if fade > 0:
        song[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)[:, None]
    full = np.clip(song, -32768, 32767).astype(np.int16)
    per_section = [full[a:b].copy() for a, b in spans]
    return per_section, full


def render_full_beat(
    fingerprint: dict, seed: Optional[int] = None
) -> tuple[list[SectionPlan], list[np.ndarray], np.ndarray]:
    """
    Full pipeline: plan the arrangement, render the song.
    Returns (sections, per_section_audio, full_beat_audio). CPU-bound: call from a background job.
    """
    sections, fp = build_beat_plan(fingerprint)
    mixes, full = render_song(sections, fp, seed)
    return sections, mixes, full


def sections_from_params(params: dict) -> tuple[list[SectionPlan], dict]:
    """
    Reconstruct the section plan from a stored beat_versions.params blob.
    Older saved beats have no repeat or seed information; both are worked out here.
    """
    fp = fp_utils.normalize(params.get("fingerprint", {}))
    sections: list[SectionPlan] = []
    for s in params.get("sections", []):
        sections.append(
            SectionPlan(
                index=s["index"],
                name=s["name"],
                label=s.get("label", s["name"].capitalize()),
                bars=s["bars"],
                energy=s["energy"],
                density=s["density"],
                layers=list(s["layers"]),
            )
        )
    sections.sort(key=lambda x: x.index)
    _stamp_repeats(sections)
    return sections, fp


def rerender_all(
    sections: list[SectionPlan], fp: dict, seed: Optional[int] = None
) -> tuple[list[np.ndarray], np.ndarray]:
    """Re-render every section after an edit. Returns (per_section_audio, full_beat_audio)."""
    return render_song(sections, fp, seed)


def apply_section_instruction(
    section: SectionPlan, instruction: str | None, fp: dict
) -> None:
    """
    Nudge a section's parameters based on a plain-language instruction keyword.
    The LLM passes along the user's intent; we translate it to concrete changes.
    This is what makes "the verse feels too empty" a real, explainable edit.
    """
    text = (instruction or "").lower()

    if any(w in text for w in ("empty", "sparse", "bare", "fuller", "full", "more")):
        section.density = _clamp(section.density + 0.25)
        # Add a layer the section doesn't have yet
        for candidate in ("melody", "pad", "bass"):
            if candidate not in section.layers:
                section.layers.append(candidate)
                break
    if any(w in text for w in ("busy", "cluttered", "too much", "simpler", "strip", "less")):
        section.density = _clamp(section.density - 0.25)
    if any(w in text for w in ("harder", "bigger", "energy", "punch", "powerful")):
        section.energy = _clamp(section.energy + 0.2)
        section.density = _clamp(section.density + 0.1)
    if any(w in text for w in ("softer", "calmer", "gentler", "quieter", "back")):
        section.energy = _clamp(section.energy - 0.2)
