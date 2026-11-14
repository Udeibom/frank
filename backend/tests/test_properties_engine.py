"""
Property-based tests for the song engine (song-engine spec 04).

Two kinds: fast ones that look at the composed notes, and a few that render a SHORT song and
measure the audio (a render of the full default song takes about ten seconds, so those stay small).
"""
from __future__ import annotations

import numpy as np
from hypothesis import given, settings, strategies as st

from app.services.generation import beat, composer, theory
from app.services.generation import fingerprint as fp_utils
from app.services.generation.renderer import SAMPLE_RATE, TAIL_SECONDS
from app.services.generation.styles import (
    LANE_CHARS,
    LANES,
    PARTS,
    TIERS,
    _raw,
    pick_style,
    style_names,
)

KEYS = ["C minor", "A minor", "E minor", "G major", "D major", "F major", "Bb major", "F# minor"]
FEELS = ["steady", "building", "floating", "driving"]
SECTIONS = ["intro", "verse", "pre-chorus", "chorus", "bridge", "outro"]

unit = st.floats(0.0, 1.0, allow_nan=False)
seeds = st.integers(0, 2**31)
arrangements = st.lists(st.tuples(st.sampled_from(SECTIONS), st.integers(1, 12)), min_size=1, max_size=10)
fingerprints = st.fixed_dictionaries(
    {
        "tempo_bpm": st.integers(50, 180),
        "key": st.sampled_from(KEYS),
        "tempo_feel": st.sampled_from(FEELS),
        "energy_level": unit,
        "density": unit,
        "brightness": unit,
        "warmth": unit,
    }
)


def prog_for(fp: dict, seed: int = 0, variant: int = 0) -> dict:
    return theory.build_progression(fp["key"], fp["energy_level"], fp["tempo_feel"], variant=variant, seed=seed)


def events_of(parts) -> list:
    return [(p.name, p.preset, [(e.note, round(e.start, 6), round(e.duration, 6), e.velocity) for e in p.events]) for p in parts]


def compose(name: str, fp: dict, seed: int, index: int = 0, repeat: int = 0, final: bool = False, bars: int = 8,
            density: float | None = None, next_name: str | None = None, layers: list[str] | None = None):
    f = fp_utils.normalize(fp)
    ctx = composer.SectionContext(name=name, index=index, repeat=repeat, final=final, seed=seed,
                                  style=pick_style(f), next_name=next_name)
    return composer.compose_section(
        name, prog_for(f, seed), bars, f["energy_level"], f["density"] if density is None else density,
        layers=layers, ctx=ctx,
    )


# ── timing ────────────────────────────────────────────────────────────────


@given(arrangements, st.integers(50, 180))
def test_sections_are_contiguous_and_exact(arr, bpm):
    """Every section ends exactly where the next begins; the song is exactly as long as its bars."""
    sections, _ = beat.build_beat_plan({"tempo_bpm": bpm}, arr)
    spans = beat.section_spans(sections, bpm)
    assert spans[0][0] == 0
    assert all(a[1] == b[0] for a, b in zip(spans, spans[1:]))
    beats = sum(bars for _, bars in arr) * 4
    assert abs(spans[-1][1] - beats * 60.0 / bpm * SAMPLE_RATE) <= 1


def render_short(fp: dict, arr, seed: int = 7):
    sections, f = beat.build_beat_plan(fp, arr)
    mixes, full = beat.render_song(sections, f, seed)
    return sections, f, mixes, full


SHORT = [("intro", 2), ("verse", 2), ("chorus", 2), ("bridge", 2), ("outro", 2)]
BASE_FP = {"tempo_bpm": 100, "key": "C minor", "energy_level": 0.6, "density": 0.5, "warmth": 0.5, "brightness": 0.4}


def db(x: np.ndarray) -> float:
    x = x.astype(np.float64) / 32768.0
    r = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
    return 20 * np.log10(r) if r > 1e-9 else -120.0


def test_length_is_the_bars_plus_the_tail():
    sections, f, mixes, full = render_short(BASE_FP, SHORT)
    spans = beat.section_spans(sections, f["tempo_bpm"])
    assert full.shape[0] == spans[-1][1] + int(TAIL_SECONDS * SAMPLE_RATE)
    assert [m.shape[0] for m in mixes] == [b - a for a, b in spans]


def test_the_last_notes_are_allowed_to_ring_out():
    sections, f, mixes, full = render_short(BASE_FP, SHORT)
    end = beat.section_spans(sections, f["tempo_bpm"])[-1][1]
    assert db(full[end : end + int(0.3 * SAMPLE_RATE)]) > -60.0


def test_no_silent_gap_at_section_joins():
    """Before the fix, each join held about 1.5 seconds of near-silence."""
    sections, f, mixes, full = render_short(BASE_FP, SHORT)
    spans = beat.section_spans(sections, f["tempo_bpm"])
    half = int(0.4 * SAMPLE_RATE)
    for _, end in spans[:-1]:
        assert db(full[end - half : end + half]) > -48.0


def test_loudness_follows_the_job_of_each_section():
    sections, f, mixes, full = render_short(BASE_FP, SHORT)
    level = {s.name: db(m) for s, m in zip(sections, mixes)}
    assert level["chorus"] >= level["verse"] + 1.5
    assert level["bridge"] < level["chorus"]
    assert level["intro"] < level["chorus"]
    assert level["outro"] < level["chorus"]


def test_warmth_and_brightness_change_the_sound():
    # Same style word and same notes; only the tone settings differ, so any change is the tone itself.
    fixed = {**BASE_FP, "genre_proximity": ["soul"]}
    tiny = [("verse", 2)]
    base = render_short(fixed, tiny)[3]
    warm = render_short({**fixed, "warmth": 1.0}, tiny)[3]
    bright = render_short({**fixed, "brightness": 1.0}, tiny)[3]
    assert base.shape == warm.shape == bright.shape
    assert not np.array_equal(base, warm)
    assert not np.array_equal(base, bright)


def test_genre_and_instrument_words_change_the_music():
    base = events_of(compose("verse", BASE_FP, 5))
    other = events_of(compose("verse", {**BASE_FP, "genre_proximity": ["rock"]}, 5))
    hinted = events_of(compose("verse", {**BASE_FP, "instrumentation_hints": ["guitar"]}, 5))
    assert base != other
    assert base != hinted


def test_words_frank_cannot_act_on_are_reported():
    choice = pick_style({"genre_proximity": ["zydeco"], "instrumentation_hints": ["theremin"]})
    assert "zydeco" in choice.unsupported and "theremin" in choice.unsupported


# ── notes ─────────────────────────────────────────────────────────────────


@given(fingerprints, seeds, st.integers(0, 3))
@settings(max_examples=60, deadline=None)
def test_melody_strong_beats_are_chord_tones(fp, seed, variant):
    f = fp_utils.normalize(fp)
    prog = prog_for(f, seed, variant)
    ctx = composer.SectionContext(name="chorus", seed=seed, style=pick_style(f))
    part = composer.compose_melody(prog, 8, f["energy_level"], f["density"], ctx)
    for ev in part.events:
        pos = ev.start % 4
        if min(abs(pos), abs(pos - 2)) < 0.1:
            assert ev.note % 12 in {n % 12 for n in prog["chords"][int(ev.start // 4) % len(prog["chords"])]}


@given(fingerprints, seeds, st.sampled_from(SECTIONS))
@settings(max_examples=60, deadline=None)
def test_no_part_plays_the_same_pitch_twice_at_once(fp, seed, name):
    for part in compose(name, fp, seed):
        if part.is_drums:
            continue
        by_pitch: dict[int, list] = {}
        for e in part.events:
            by_pitch.setdefault(e.note, []).append(e)
        for events in by_pitch.values():
            events.sort(key=lambda e: e.start)
            for a, b in zip(events, events[1:]):
                assert a.start + a.duration <= b.start + 1e-9, part.name


@given(fingerprints, seeds, st.sampled_from(SECTIONS))
@settings(max_examples=40, deadline=None)
def test_every_note_is_playable(fp, seed, name):
    for part in compose(name, fp, seed):
        for e in part.events:
            assert 0 <= e.note <= 127 and 1 <= e.velocity <= 127 and e.start >= 0 and e.duration > 0
            assert e.start < 8 * 4


@given(fingerprints, seeds, st.sampled_from(SECTIONS))
@settings(max_examples=30, deadline=None)
def test_same_seed_same_music(fp, seed, name):
    assert events_of(compose(name, fp, seed)) == events_of(compose(name, fp, seed))


@given(fingerprints, seeds)
@settings(max_examples=30, deadline=None)
def test_a_new_seed_gives_different_music(fp, seed):
    a = events_of(compose("chorus", {**fp, "energy_level": max(fp["energy_level"], 0.5)}, seed, layers=["keys", "bass", "drums", "melody"]))
    b = events_of(compose("chorus", {**fp, "energy_level": max(fp["energy_level"], 0.5)}, seed + 1, layers=["keys", "bass", "drums", "melody"]))
    assert a != b


@given(fingerprints, seeds)
@settings(max_examples=30, deadline=None)
def test_a_returning_verse_is_not_a_copy(fp, seed):
    layers = ["keys", "bass", "drums", "melody"]
    first = events_of(compose("verse", fp, seed, index=1, repeat=0, layers=layers))
    second = events_of(compose("verse", fp, seed, index=3, repeat=1, layers=layers))
    assert first != second


def drum_notes(fp, seed, name, next_name):
    part = next(p for p in compose(name, fp, seed, layers=["drums"], next_name=next_name) if p.name == "drums")
    return part


@given(fingerprints, seeds)
@settings(max_examples=30, deadline=None)
def test_a_chorus_starts_with_a_crash(fp, seed):
    chorus = drum_notes(fp, seed, "chorus", None)
    assert any(e.note == composer.CRASH and e.start < 0.5 for e in chorus.events)


@given(fingerprints, seeds)
@settings(max_examples=30, deadline=None)
def test_a_fill_only_touches_the_bar_before_the_chorus(fp, seed):
    key = lambda p, lo, hi: sorted((e.note, round(e.start, 4)) for e in p.events if lo <= e.start < hi)
    plain, into = drum_notes(fp, seed, "verse", None), drum_notes(fp, seed, "verse", "chorus")
    assert key(plain, 0, 27.9) == key(into, 0, 27.9)


def test_the_bar_before_a_chorus_is_sometimes_a_fill():
    fp = {**BASE_FP, "energy_level": 0.8}
    differs = sum(
        sorted((e.note, round(e.start, 4)) for e in drum_notes(fp, s, "verse", None).events if e.start >= 28)
        != sorted((e.note, round(e.start, 4)) for e in drum_notes(fp, s, "verse", "chorus").events if e.start >= 28)
        for s in range(40)
    )
    assert differs >= 10


@given(fingerprints, seeds, st.integers(1, 4))
@settings(max_examples=30, deadline=None)
def test_changing_one_section_leaves_the_others_alone(fp, seed, which):
    names = ["intro", "verse", "chorus", "verse", "chorus", "bridge"]

    def song(density_of: dict[int, float]):
        return [events_of(compose(n, fp, seed, index=i, density=density_of.get(i))) for i, n in enumerate(names)]

    base = song({})
    changed = song({which: 0.05})
    for i in range(len(names)):
        if i != which:
            assert base[i] == changed[i]


@given(fingerprints, seeds)
@settings(max_examples=30, deadline=None)
def test_more_density_never_means_fewer_notes(fp, seed):
    layers = ["keys", "bass", "drums"]
    count = lambda d: sum(len(p.events) for p in compose("verse", fp, seed, density=d, layers=layers))
    assert count(0.9) >= count(0.1)


@given(st.lists(st.lists(st.integers(36, 84), min_size=3, max_size=4, unique=True), min_size=1, max_size=6))
def test_voice_leading_keeps_the_same_notes(chords):
    chords = [sorted(c) for c in chords]
    voiced = theory.voice_lead(chords)
    assert len(voiced) == len(chords)
    for before, after in zip(chords, voiced):
        assert sorted({n % 12 for n in before}) == sorted({n % 12 for n in after})


@given(st.sampled_from(KEYS), unit, st.sampled_from(FEELS), st.integers(0, 3), seeds)
@settings(max_examples=40, deadline=None)
def test_voice_leading_moves_less_than_root_position(key, energy, feel, variant, seed):
    led = theory.build_progression(key, energy, feel, variant=variant, seed=seed, voice=True)["chords"]
    plain = theory.build_progression(key, energy, feel, variant=variant, seed=seed, voice=False)["chords"]
    move = lambda cs: sum(sum(abs(a - b) for a, b in zip(sorted(x), sorted(y))) for x, y in zip(cs, cs[1:] + cs[:1]))
    assert move(led) <= move(plain)


# ── style data ────────────────────────────────────────────────────────────


def test_style_file_is_valid():
    raw = _raw()
    assert len(style_names()) >= 8
    for name in ["_default", *style_names()]:
        data = raw[name] if name == "_default" else {**raw["_default"], **raw[name]}
        for lane, pattern in (data.get("drums") or {}).items():
            assert lane in LANES, (name, lane)
            assert len(pattern) == 16 and set(pattern) <= LANE_CHARS, (name, lane, pattern)
    for name in style_names():
        choice = pick_style({"genre_proximity": [raw[name]["keywords"][0]]})
        assert choice.name == name
        assert set(choice.instruments) >= set(PARTS)
        assert all(0 <= p <= 127 for p in choice.instruments.values())
        for table in (choice.keys, choice.bass):
            counts = [len(table[t]) for t in TIERS]
            assert counts == sorted(counts), (name, counts)
