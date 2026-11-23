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
import logging
from dataclasses import dataclass, field, replace
from typing import Optional

import numpy as np

from app.services.generation import chord_tables, composer, fingerprint as fp_utils, lead as lead_mod, moments as moments_mod, polish, theory
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
MAX_GAIN_DB = 12.0
SILENCE_RMS = 4.0            # on the int16 scale: below this a section is treated as silent, not boosted
MIN_GAIN_DB = -18.0

# How loud each part is against the others before the section is set to its level.
PART_GAIN = {
    "drums": 1.0, "bass": 1.0, "keys": 0.75, "melody": 0.9, "pad": 0.55, "strings": 0.5, "arp": 0.5,
    "color": 0.6, "color_once": 0.6, "riser": 0.45, "sweep": 0.4,
    "finale_keys": 0.8, "finale_pad": 0.5, "finale_bass": 1.0, "finale_drums": 1.0,
}

LEAD_GAIN = 1.1              # the person's own tune sits a little in front of the other parts
PEAK_TARGET = 0.89
ENGINE_VERSION = 6          # bumps when a change would make an old beat sound different if re-rendered
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
    # Stable identity for seeding. A section keeps its own notes when it is moved; a repeated copy gets a new one.
    uid: Optional[int] = None
    # Per-part edits (song-engine requirement 5.3): {part: {"busy": -1..1, "preset": GM program, "reseed": n,
    # "fill": bool}}. Missing parts or keys mean "as the style decides".
    parts: dict = field(default_factory=dict)
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


# ── The music lasts as long as the singing (core-path spec 15, requirement 3) ──

MAX_SECTIONS_FOR_LENGTH = 16
MAX_SECTION_BARS = 32
LENGTH_MARGIN_S = 2.0          # the music ends a moment after the last sung note, never before it


def seconds_of_bars(bars: int, bpm: float) -> float:
    return bars * 4 * 60.0 / bpm


def fit_arrangement(arrangement: list, bpm: float, min_seconds: float) -> list:
    """
    The arrangement made long enough for `min_seconds` of singing: another verse and chorus go in before the
    ending (the song simply has more of itself), and once the song has as many sections as it may, the ending
    grows. A song that is already long enough is returned as it is.
    """
    arr = [tuple(e) for e in arrangement]
    need = min_seconds + LENGTH_MARGIN_S
    total = lambda a: seconds_of_bars(sum(int(e[1]) for e in a), bpm)  # noqa: E731
    if min_seconds <= 0 or total(arr) >= need:
        return arr
    verse = next((e for e in arr if e[0] == "verse"), ("verse", 8))
    chorus = next((e for e in arr if e[0] == "chorus"), ("chorus", 8))
    nxt = [verse, chorus]
    turn = 0
    while total(arr) < need and len(arr) < MAX_SECTIONS_FOR_LENGTH:
        at = max((i for i, e in enumerate(arr) if e[0] == "outro"), default=len(arr))
        arr.insert(at, nxt[turn % 2])
        turn += 1
    if total(arr) < need and arr:
        last = list(arr[-1])
        short_bars = int(-(-(need - total(arr)) * bpm // 240))
        last[1] = min(MAX_SECTION_BARS, int(last[1]) + max(1, short_bars))
        arr[-1] = tuple(last)
    return arr


def extend_sections(sections: list[SectionPlan], bpm: float, min_seconds: float) -> tuple[list[SectionPlan], bool]:
    """The same for a beat that already exists: copies of its own verse and chorus, then a longer ending.
    Sections already there keep their notes; each copy gets its own identity. Returns (sections, changed)."""
    import copy

    out = copy.deepcopy(sections)
    need = min_seconds + LENGTH_MARGIN_S
    total = lambda: seconds_of_bars(sum(x.bars for x in out), bpm)  # noqa: E731
    if min_seconds <= 0 or total() >= need:
        return out, False
    for x in out:
        if x.uid is None:
            x.uid = x.index
    next_uid = max(x.uid for x in out) + 1000
    templates = [t for t in (next((x for x in out if x.name == "verse"), None),
                             next((x for x in reversed(out) if x.name == "chorus"), None)) if t is not None]
    turn = 0
    while templates and total() < need and len(out) < MAX_SECTIONS_FOR_LENGTH:
        at = max((i for i, x in enumerate(out) if x.name == "outro"), default=len(out))
        twin = copy.deepcopy(templates[turn % len(templates)])
        twin.uid, twin.stems = next_uid, {}
        next_uid += 1000
        out.insert(at, twin)
        turn += 1
    if total() < need and out:
        short_bars = int(-(-(need - total()) * bpm // 240))
        out[-1].bars = min(MAX_SECTION_BARS, out[-1].bars + max(1, short_bars))
        out[-1].stems = {}
    for i, x in enumerate(out):
        x.index = i
    _stamp_repeats(out)
    return out, True


def default_seed(fp: dict) -> int:
    """A seed that depends only on the fingerprint, so the same feeling gives the same first song."""
    return derive_seed(json.dumps(fp, sort_keys=True, default=str))


def build_beat_plan(
    fingerprint: dict, arrangement=None, seed: Optional[int] = None, lead: Optional[lead_mod.Lead] = None,
    min_seconds: float = 0.0,
) -> tuple[list[SectionPlan], dict]:
    """
    Build the section plan (no audio yet) from a fingerprint.
    When there is a tune, a section that plays it is made at least as long as the tune, so the whole tune is
    heard. Returns (sections, normalized_fingerprint).
    """
    fp = fp_utils.normalize(fingerprint)
    style = pick_style(fp)
    arrangement = fit_arrangement(arrangement or DEFAULT_ARRANGEMENT, float(fp["tempo_bpm"]), min_seconds)
    base_energy = fp["energy_level"]
    base_density = fp["density"]

    sections: list[SectionPlan] = []
    feelings: list[Optional[str]] = []
    for i, entry in enumerate(arrangement):
        name, bars = entry[0], entry[1]
        feelings.append(entry[2] if len(entry) > 2 else None)
        if lead and name in lead_mod.LEAD_SECTIONS:
            bars = max(int(bars), lead.bars)
        sections.append(SectionPlan(i, name, name.capitalize(), int(bars), 0.0, 0.0, layers=[]))
    _stamp_repeats(sections)
    for s, feeling in zip(sections, feelings):
        mult = energy_multiplier(s, feeling)
        s.energy = _clamp(base_energy * mult)
        # Density tracks energy a bit so bigger sections feel fuller
        s.density = _clamp(base_density * (0.8 + 0.4 * mult))
        s.layers = composer.layers_for_section(s.name, s.energy, s.density, s.repeat, s.final, style)
    if isinstance(fp.get("texture_palette"), int):
        # The beat keeps the sound of the direction they said yes to (core-path spec 15, 4.1)
        from app.services.generation.texture import PALETTES

        if 0 <= fp["texture_palette"] < len(PALETTES):
            _, keys, pad, _ = PALETTES[fp["texture_palette"]]
            for s in sections:
                s.parts.setdefault("keys", {}).setdefault("preset", keys)
                s.parts.setdefault("pad", {}).setdefault("preset", pad)
    return sections, fp


# How a section's feeling in the words moves its energy (from the lyrics reading, spec 02).
FEELING_ENERGY = {"angry": 0.08, "sorrowful": -0.06, "warm": 0.0, "mixed": 0.0}


def energy_multiplier(s: SectionPlan, feeling: Optional[str] = None) -> float:
    """
    The song's energy curve (song-engine requirement 2, task 3.2): each kind of section has its place (intro low,
    verse mid, build-up rising, chorus high, bridge a contrast, ending down), a chorus grows each time it comes back
    and the last one is the biggest, a returning verse is a touch fuller, and the words' feeling nudges it.
    """
    mult = SECTION_ENERGY.get(s.name, 0.8)
    if s.name == "chorus":
        mult += 0.05 * min(s.repeat, 3) + (0.04 if s.final and s.repeat >= 1 else 0.0)
    elif s.name == "verse" and s.repeat >= 1:
        mult += 0.03
    return mult + FEELING_ENERGY.get(feeling or "", 0.0)


LINE_BARS = 2                 # a sung line takes about two bars
INTRO_BARS, OUTRO_BARS = 4, 4


def arrangement_from_structure(structure: Optional[dict]) -> Optional[list[tuple[str, int, Optional[str]]]]:
    """
    The arrangement the person's own words imply (song-engine requirement 1.1, task 3.1): their sections in their
    order, each about two bars per line rounded up to whole four-bar phrases (4 to 16 bars), with an intro before and
    an ending after. If the words end on a verse, the chorus comes back once more before the ending, the way a song
    ends on its hook. Returns None when there is no usable structure (the style's template is used instead).
    """
    if not isinstance(structure, dict):
        return None
    out: list[tuple[str, int, Optional[str]]] = []
    for sec in structure.get("sections") or []:
        try:
            name = str(sec["name"]).lower()
            lines = int(sec["last_line"]) - int(sec["first_line"]) + 1
        except (KeyError, TypeError, ValueError):
            continue
        if name not in SECTION_ENERGY or lines < 1 or name in ("intro", "outro"):
            continue
        bars = min(16, max(4, -(-lines * LINE_BARS // 4) * 4))
        out.append((name, bars, sec.get("feeling")))
    if not out:
        return None
    choruses = [e for e in out if e[0] == "chorus"]
    if choruses and out[-1][0] != "chorus":
        out.append(choruses[-1])
    return [("intro", INTRO_BARS, None)] + out + [("outro", OUTRO_BARS, None)]


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
    sections: list[SectionPlan], fp: dict, seed: int, lead: Optional[lead_mod.Lead] = None
) -> tuple[StyleChoice, list[composer.SectionContext], dict[str, dict]]:
    """
    Everything the composer needs per section: the style, where it sits in the song, and the chord
    progression for each kind of section (a verse keeps the same chords every time it comes back).
    """
    style = pick_style(fp)
    if isinstance(fp.get("groove"), dict):
        # the person's own tapped rhythm replaces the style's kick and hat lanes
        from app.services.intake.rhythm import groove_to_style_drums
        style = replace(style, drums=groove_to_style_drums(fp["groove"], style.drums), own_groove=True)
    offset = derive_seed(seed, "chords") % 4
    if lead:
        playing = [s.bars for s in sections if s.name in lead_mod.LEAD_SECTIONS]
        if playing and min(playing) < lead.bars:
            lead = lead_mod.fit_to(lead, min(playing))      # one consistent, whole-phrase version of the tune
    progressions: dict[str, dict] = {}
    used_loops: set[tuple] = set()
    # When the person has hummed a tune, the whole song sits in the key of that tune.
    key = (lead.key if lead else "") or fp["key"]
    # Each kind of section gets its chords in a fixed order (not the arrangement's), so moving a section never
    # changes which chords it plays (ops property: a moved section keeps its own notes).
    kind_order = {"verse": 0, "chorus": 1, "pre-chorus": 2, "bridge": 3}
    for s in sorted({x.name: x for x in sections}.values(), key=lambda x: (kind_order.get(x.name, 9), x.name)):
        if s.name in progressions:
            continue
        if lead and s.name in lead_mod.LEAD_SECTIONS:
            progressions[s.name] = lead_mod.harmonize(lead, key, style.extension)
        else:
            variant = (ROLE_VARIANT.get(s.name, 0) + offset) % 4
            # Real songs in this style decide which of the family's loops this kind of section takes
            # (Chordonomicon, frankenstein spec 14, 3.2); never the same loop as another section already has.
            _, mode = theory.parse_key(key)
            options = theory.PROGRESSIONS[theory.choose_progression_family(mode, fp["energy_level"], fp["tempo_feel"])]
            order = chord_tables.ranked(options, style.name, s.name, mode)
            if order:
                variant = next((i for i in order if tuple(options[i]) not in used_loops), variant)
            used_loops.add(tuple(options[variant % len(options)]))
            progressions[s.name] = theory.build_progression(
                key=key,
                energy=fp["energy_level"],
                tempo_feel=fp["tempo_feel"],
                variant=variant,
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
                index=s.uid if s.uid is not None else s.index,
                parts=s.parts,
                repeat=s.repeat,
                final=s.final,
                seed=seed,
                style=style,
                next_name=nxt.name if nxt else None,
                next_energy=nxt.energy if nxt else None,
                moments=planned.get(s.index, []),
                lead=lead if (lead and s.name in lead_mod.LEAD_SECTIONS) else None,
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
    polish.process_in_place(board, audio)      # in place, a chunk at a time: no whole-song copies
    return audio


def _render_section(synth, s: SectionPlan, ctx, progression: dict, bpm: float, length: int, mix_chain: bool) -> tuple[np.ndarray, float]:
    """
    One section's audio (float32, its bars plus the ringing tail), set to the loudness its job in the song asks
    for. Also returns that gain, so the song's parts can later be rendered one at a time at the same level.
    """
    parts = composer.compose_section(
        section=s.name, progression=progression, bars=s.bars, energy=s.energy, density=s.density, layers=s.layers, ctx=ctx,
    )
    acc = np.zeros((length + int(TAIL_SECONDS * SAMPLE_RATE), 2), dtype=np.float32)
    for part in parts:
        stem = synth.render(part, bpm, s.bars * 4)
        if mix_chain:
            stem = polish.treat_part(part.name, stem.astype(np.float32), bpm)
        n = min(stem.shape[0], acc.shape[0])
        gain = LEAD_GAIN if part.lead else PART_GAIN.get(part.name, 0.7)
        acc[:n] += stem[:n].astype(np.float32) * gain
        del stem
    body = acc[:length]
    rms = float(np.sqrt(np.mean(np.square(body, dtype=np.float64)))) if body.size else 0.0
    gain = 1.0
    if rms > SILENCE_RMS:
        gain_db = _target_db(s) - 20.0 * np.log10(rms / 32768.0)
        gain = float(10.0 ** (max(MIN_GAIN_DB, min(MAX_GAIN_DB, gain_db)) / 20.0))
        acc *= gain
    return acc, gain


def _finish(song: np.ndarray, fp: dict, mix_chain: bool, song_gain: Optional[float], report: Optional[dict]) -> np.ndarray:
    """Tone, glue, one level for the whole song, fade, int16. A preview passes the full song's gain so it plays at the same level."""
    song = _tone_tilt(song, fp)
    if mix_chain:
        song = polish.treat_song(song)
    if song_gain is None:
        peak = float(np.abs(song).max())
        song_gain = (PEAK_TARGET * 32767.0) / peak if peak > 0 else 1.0
    song *= np.float32(song_gain)
    if report is not None:
        report["song_gain"] = float(song_gain)
    fade = min(int(FADE_OUT_SECONDS * SAMPLE_RATE), song.shape[0])
    if fade > 0:
        song[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)[:, None]
    np.clip(song, -32768, 32767, out=song)
    return song.astype(np.int16)


def render_song(
    sections: list[SectionPlan], fp: dict, seed: Optional[int] = None, mix_chain: bool = True,
    lead: Optional[lead_mod.Lead] = None, report: Optional[dict] = None,
) -> tuple[list[np.ndarray], np.ndarray]:
    """
    Render the whole song. Returns (per_section_audio, full_audio), both int16 stereo.
    The per-section slices are exactly the section's bars long; the full audio also holds the final
    ringing tail. Memory stays bounded: one float32 song buffer plus one section at a time.
    `report`, when given, receives the song-level gain so previews can be played at the same level.
    """
    if not sections:
        empty = np.zeros((0, 2), dtype=np.int16)
        return [], empty
    seed = default_seed(fp) if seed is None else seed
    bpm = float(fp["tempo_bpm"])
    spans = section_spans(sections, bpm)
    tail = int(TAIL_SECONDS * SAMPLE_RATE)
    song = np.zeros((spans[-1][1] + tail, 2), dtype=np.float32)
    _, contexts, progressions = plan_contexts(sections, fp, seed, lead)
    gains: list[float] = []
    with SynthSession() as synth:
        for s, ctx, (start, end) in zip(sections, contexts, spans):
            acc, gain = _render_section(synth, s, ctx, progressions[s.name], bpm, end - start, mix_chain)
            gains.append(gain)
            song[start : start + acc.shape[0]] += acc            # the tail rings over the next section
            del acc
    if report is not None:
        report["section_gains"] = [round(g, 6) for g in gains]
    full = _finish(song, fp, mix_chain, None, report)
    del song
    per_section = [full[a:b] for a, b in spans]      # views, not copies: callers only read them
    return per_section, full


def score_of(sections: list[SectionPlan], fp: dict, seed: int, lead: Optional[lead_mod.Lead] = None) -> dict[tuple, tuple]:
    """
    Every note the song would play, per (section uid, part): (sound, notes). Composition only, no synthesis, so it
    is cheap. Two plans with the same score sound the same; an edit that leaves it unchanged changed nothing.
    """
    _, contexts, progressions = plan_contexts(sections, fp, seed, lead)
    out: dict[tuple, tuple] = {}
    for s, ctx in zip(sections, contexts):
        parts = composer.compose_section(
            section=s.name, progression=progressions[s.name], bars=s.bars, energy=s.energy, density=s.density, layers=s.layers, ctx=ctx,
        )
        uid = s.uid if s.uid is not None else s.index
        for p in parts:
            out[(uid, s.index, p.name)] = (p.preset, s.bars, tuple((e.note, round(e.start, 4), round(e.duration, 4), e.velocity) for e in p.events))
    return out


PREVIEW_GAP_SECONDS = 0.6


def render_excerpt(
    sections: list[SectionPlan], indices: list[int], fp: dict, seed: int, lead: Optional[lead_mod.Lead] = None,
    song_gain: Optional[float] = None, mix_chain: bool = True,
) -> np.ndarray:
    """
    A quick preview of some sections of a plan (song-engine requirement 7.4, refine-loop requirement 2.2). The whole
    plan decides each section's chords, moments and neighbours, exactly as the full render would; only the chosen
    sections are synthesised. Runs of neighbouring sections play joined; separate runs get a short gap. With the full
    song's `song_gain` the preview plays at the level the committed song will have.
    """
    chosen = sorted({i for i in indices if 0 <= i < len(sections)})
    if not chosen:
        return np.zeros((0, 2), dtype=np.int16)
    bpm = float(fp["tempo_bpm"])
    spans = section_spans(sections, bpm)
    tail = int(TAIL_SECONDS * SAMPLE_RATE)
    _, contexts, progressions = plan_contexts(sections, fp, seed, lead)
    runs: list[list[int]] = []
    for i in chosen:
        if runs and runs[-1][-1] == i - 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    gap = int(PREVIEW_GAP_SECONDS * SAMPLE_RATE)
    total = sum(spans[r[-1]][1] - spans[r[0]][0] + tail for r in runs) + gap * (len(runs) - 1)
    out = np.zeros((total, 2), dtype=np.float32)
    pos = 0
    with SynthSession() as synth:
        for r in runs:
            origin = spans[r[0]][0]
            for i in r:
                start, end = spans[i]
                acc, _ = _render_section(synth, sections[i], contexts[i], progressions[sections[i].name], bpm, end - start, mix_chain)
                at = pos + start - origin
                n = min(acc.shape[0], out.shape[0] - at)
                out[at : at + n] += acc[:n]
                del acc
            pos += spans[r[-1]][1] - origin + tail + gap
    return _finish(out, fp, mix_chain, song_gain, None)


def render_full_beat(
    fingerprint: dict, seed: Optional[int] = None, lead: Optional[lead_mod.Lead] = None,
    structure: Optional[dict] = None, report: Optional[dict] = None, min_seconds: float = 0.0,
) -> tuple[list[SectionPlan], list[np.ndarray], np.ndarray]:
    """
    Full pipeline: plan the arrangement (from the words' structure when there is one), render the song.
    Returns (sections, per_section_audio, full_beat_audio). CPU-bound: call from a background job.
    """
    sections, fp = build_beat_plan(fingerprint, arrangement_from_structure(structure), lead=lead, min_seconds=min_seconds)
    mixes, full = render_song(sections, fp, seed, lead=lead, report=report)
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
                uid=s.get("uid"),
                parts=dict(s.get("parts") or {}),
            )
        )
    sections.sort(key=lambda x: x.index)
    _stamp_repeats(sections)
    return sections, fp


def lead_from_params(params: dict) -> Optional[lead_mod.Lead]:
    """The person's tune a saved beat was built around, if any. Older beats have none."""
    saved = params.get("lead")
    lead = lead_mod.Lead.from_dict(saved)
    if saved and lead is None:
        logging.getLogger(__name__).warning("A saved tune could not be read and was left out of this beat")
    return lead


def lead_info(sections: list[SectionPlan], lead: Optional[lead_mod.Lead]) -> dict:
    """
    What happened to the person's tune in this beat, in plain facts Frank can turn into words: was it used,
    where, and was any of it left out.
    """
    if lead is None:
        return {"used": False}
    playing = [s for s in sections if s.name in lead_mod.LEAD_SECTIONS and "melody" in s.layers]
    if not playing:
        return {"used": False, "reason": "no_chorus_plays_it", "key": lead.key}
    heard = min(lead.bars, min(s.bars for s in playing))
    return {
        "used": True,
        "sections": [s.index for s in playing],
        "tune_bars": lead.bars,
        "heard_bars": heard,
        "cut": heard < lead.bars,
        "key": lead.key,
        "source": lead.source,
    }


def rerender_all(
    sections: list[SectionPlan], fp: dict, seed: Optional[int] = None, lead: Optional[lead_mod.Lead] = None,
    report: Optional[dict] = None,
) -> tuple[list[np.ndarray], np.ndarray]:
    """Re-render every section after an edit. Returns (per_section_audio, full_beat_audio)."""
    return render_song(sections, fp, seed, lead=lead, report=report)


# ── the song's parts, one at a time (finish-and-intent spec 11, requirement 1) ──

# Parts that are built from or belong with another part are mixed with it ("the piano" includes its last chord).
PART_FAMILY = {"finale_keys": "keys", "finale_pad": "pad", "finale_bass": "bass", "finale_drums": "drums",
               "color": "extras", "color_once": "extras", "riser": "extras", "sweep": "extras"}
FAMILIES = ("drums", "bass", "keys", "melody", "pad", "strings", "arp", "extras")


def part_family(name: str) -> str:
    return PART_FAMILY.get(name, name if name in FAMILIES else "extras")


def families_in(sections: list[SectionPlan], fp: dict, seed: int, lead: Optional[lead_mod.Lead] = None) -> list[str]:
    """Which part families the song actually plays (composition only, cheap)."""
    _, contexts, progressions = plan_contexts(sections, fp, seed, lead)
    found: set[str] = set()
    for s, ctx in zip(sections, contexts):
        for p in composer.compose_section(s.name, progressions[s.name], s.bars, s.energy, s.density, layers=s.layers, ctx=ctx):
            if p.events:
                found.add(part_family(p.name))
    return [f for f in FAMILIES if f in found]


def render_parts(
    sections: list[SectionPlan], fp: dict, seed: int, lead: Optional[lead_mod.Lead], section_gains: list[float],
    song_gain: float, on_part, mix_chain: bool = True,
) -> list[str]:
    """
    Render each part family across the whole song, ONE AT A TIME, at exactly the level it has inside the full beat
    (same per-section gain, same song gain, same tone). `on_part(family, int16 stereo)` receives each and should
    encode and release it. Memory: one song-length buffer at a time. Played together at 0 dB the parts are the beat
    before its final glue (which the mix applies to the whole song instead).
    Returns the families rendered.
    """
    bpm = float(fp["tempo_bpm"])
    spans = section_spans(sections, bpm)
    tail = int(TAIL_SECONDS * SAMPLE_RATE)
    _, contexts, progressions = plan_contexts(sections, fp, seed, lead)
    done: list[str] = []
    with SynthSession() as synth:
        for family in families_in(sections, fp, seed, lead):
            song = np.zeros((spans[-1][1] + tail, 2), dtype=np.float32)
            for s, ctx, (start, end), gain in zip(sections, contexts, spans, section_gains):
                parts = composer.compose_section(
                    section=s.name, progression=progressions[s.name], bars=s.bars, energy=s.energy, density=s.density,
                    layers=s.layers, ctx=ctx,
                )
                for part in parts:
                    if part_family(part.name) != family or not part.events:
                        continue
                    stem = synth.render(part, bpm, s.bars * 4)
                    if mix_chain:
                        stem = polish.treat_part(part.name, stem.astype(np.float32), bpm)
                    n = min(stem.shape[0], song.shape[0] - start)
                    level = (LEAD_GAIN if part.lead else PART_GAIN.get(part.name, 0.7)) * gain
                    song[start:start + n] += stem[:n].astype(np.float32) * level
                    del stem
            song = _tone_tilt(song, fp)
            song *= np.float32(song_gain)
            fade = min(int(FADE_OUT_SECONDS * SAMPLE_RATE), song.shape[0])
            if fade > 0:
                song[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)[:, None]
            np.clip(song, -32768, 32767, out=song)
            on_part(family, song.astype(np.int16))
            del song
            done.append(family)
    return done
