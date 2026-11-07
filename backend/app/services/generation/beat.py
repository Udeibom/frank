"""
Beat builder — assembles a full multi-section instrumental from the engine.

A beat is an arrangement of sections (intro, verse, chorus, ...). Each section
has stems (drums, bass, keys, melody, pad). Because we compose everything
explicitly, we know exactly where each section starts and ends and which stems
are in it — no onset-detection guesswork. That is what makes every piece
independently regenerable, which is the whole point of Frank's controllability.

This module produces an in-memory beat plan and renders it to per-stem audio.
Persistence (storing stems/versions) is handled by the caller/job runner.
"""

from __future__ import annotations
from dataclasses import dataclass, field

import numpy as np

from app.services.generation import theory, composer, renderer, fingerprint as fp_utils
from app.services.generation.renderer import SynthSession

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

# Energy multiplier per section — choruses lift, intros/outros sit back.
SECTION_ENERGY = {
    "intro": 0.6,
    "verse": 0.8,
    "chorus": 1.1,
    "bridge": 0.7,
    "outro": 0.5,
}


@dataclass
class SectionPlan:
    """One section of the arrangement."""
    index: int
    name: str            # "intro", "verse", "chorus", ...
    label: str           # user-facing label, defaults to a title-cased name
    bars: int
    energy: float
    density: float
    layers: list[str]    # which stems are present
    # Rendered stems: stem_type -> int16 stereo audio
    stems: dict[str, np.ndarray] = field(default_factory=dict)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def build_beat_plan(fingerprint: dict, arrangement=None) -> tuple[list[SectionPlan], dict]:
    """
    Build the section plan (no audio yet) from a fingerprint.
    Returns (sections, normalized_fingerprint).
    """
    fp = fp_utils.normalize(fingerprint)
    arrangement = arrangement or DEFAULT_ARRANGEMENT

    base_energy = fp["energy_level"]
    base_density = fp["density"]

    sections: list[SectionPlan] = []
    for i, (name, bars) in enumerate(arrangement):
        mult = SECTION_ENERGY.get(name, 0.8)
        energy = _clamp(base_energy * mult)
        # Density tracks energy a bit so bigger sections feel fuller
        density = _clamp(base_density * (0.8 + 0.4 * mult))
        layers = composer.layers_for_section(name, energy, density)
        sections.append(
            SectionPlan(
                index=i,
                name=name,
                label=name.capitalize(),
                bars=bars,
                energy=energy,
                density=density,
                layers=layers,
            )
        )
    return sections, fp


def render_section_stems(
    section: SectionPlan, fp: dict, synth: SynthSession | None = None
) -> dict[str, np.ndarray]:
    """
    Render each stem of a section to audio. Returns stem_type -> audio array.
    A fresh progression per section keeps variety while staying in key.

    If a shared SynthSession is given, it's reused (fast — SoundFont loaded once);
    otherwise a temporary one is created for this section.

    NOTE: holds all of a section's stems in memory at once. Fine for one section
    (a few arrays), but never call this for every section simultaneously — use
    render_section_mix / iter_section_mixes for the memory-frugal path.
    """
    prog = theory.build_progression(
        key=fp["key"],
        energy=section.energy,
        tempo_feel=fp["tempo_feel"],
        variant=section.index,  # vary the progression per section
    )
    parts = composer.compose_section(
        section=section.name,
        progression=prog,
        bars=section.bars,
        energy=section.energy,
        density=section.density,
        layers=section.layers,
    )
    total_beats = section.bars * 4

    def render_all(s: SynthSession) -> dict[str, np.ndarray]:
        return {p.name: s.render(p, fp["tempo_bpm"], total_beats) for p in parts}

    if synth is not None:
        return render_all(synth)
    with SynthSession() as s:
        return render_all(s)


def render_section_mix(
    section: SectionPlan, fp: dict, synth: SynthSession
) -> np.ndarray:
    """
    Render one section and return a single mixed-down stereo array.

    Memory-frugal: each stem is rendered, summed into an accumulator, then
    released before the next stem. Only one stem array plus the accumulator is
    alive at a time, instead of holding every stem of the section at once.
    """
    prog = theory.build_progression(
        key=fp["key"],
        energy=section.energy,
        tempo_feel=fp["tempo_feel"],
        variant=section.index,
    )
    parts = composer.compose_section(
        section=section.name,
        progression=prog,
        bars=section.bars,
        energy=section.energy,
        density=section.density,
        layers=section.layers,
    )
    total_beats = section.bars * 4

    acc: np.ndarray | None = None
    for part in parts:
        stem = synth.render(part, fp["tempo_bpm"], total_beats)
        if acc is None:
            acc = np.zeros(stem.shape, dtype=np.float64)
        # Sum into the float accumulator, then drop the stem array
        if stem.shape[0] > acc.shape[0]:
            grown = np.zeros(stem.shape, dtype=np.float64)
            grown[: acc.shape[0]] += acc
            acc = grown
        acc[: stem.shape[0]] += stem.astype(np.float64)
        del stem

    if acc is None:
        return np.zeros((0, 2), dtype=np.int16)

    # Normalize this section to a healthy, consistent level
    peak = np.abs(acc).max()
    if peak > 0:
        acc *= (0.89 * 32767.0) / peak
    return acc.astype(np.int16)


def render_section_mixes(
    sections: list[SectionPlan], fp: dict
) -> list[np.ndarray]:
    """
    Render every section to a single mixed array each, reusing one synth.
    Returns a list of per-section stereo arrays (one per section), in order.

    Memory: only the per-section mixes are retained (≈8 arrays), never all the
    individual stems at once. This is what keeps a full beat within a small
    memory budget (Render free tier).
    """
    mixes: list[np.ndarray] = []
    with SynthSession() as synth:
        for section in sections:
            mixes.append(render_section_mix(section, fp, synth))
    return mixes


def assemble_from_mixes(mixes: list[np.ndarray]) -> np.ndarray:
    """Concatenate per-section mixes into the full beat."""
    nonempty = [m for m in mixes if m.shape[0] > 0]
    if not nonempty:
        return np.zeros((0, 2), dtype=np.int16)
    return np.concatenate(nonempty, axis=0)


def render_full_beat(
    fingerprint: dict,
) -> tuple[list[SectionPlan], list[np.ndarray], np.ndarray]:
    """
    Full pipeline: plan the arrangement, render each section to a mix, and
    assemble the complete beat.

    Returns (sections, per_section_mixes, full_beat_audio).
    CPU-bound and memory-frugal — call from a background job.
    """
    sections, fp = build_beat_plan(fingerprint)
    mixes = render_section_mixes(sections, fp)
    full = assemble_from_mixes(mixes)
    return sections, mixes, full


def sections_from_params(params: dict) -> tuple[list[SectionPlan], dict]:
    """
    Reconstruct the section plan from a stored beat_versions.params blob.
    Stems are left empty — the caller re-renders whatever it needs.
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
    return sections, fp


def rerender_all(
    sections: list[SectionPlan], fp: dict
) -> tuple[list[np.ndarray], np.ndarray]:
    """
    Re-render every section after an edit, memory-frugally.
    Returns (per_section_mixes, full_beat_audio).
    """
    mixes = render_section_mixes(sections, fp)
    full = assemble_from_mixes(mixes)
    return mixes, full


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
