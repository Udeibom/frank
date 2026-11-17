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


# ── moments: the one-off things that make it feel arranged ────────────────

from app.services.generation import moments as mo  # noqa: E402
from app.services.generation import touches  # noqa: E402

FULL = [("intro", 4), ("verse", 8), ("chorus", 8), ("verse", 8), ("chorus", 8), ("bridge", 4), ("chorus", 8), ("outro", 4)]
song_shapes = st.lists(st.tuples(st.sampled_from(SECTIONS), st.integers(1, 12)), min_size=1, max_size=10)


def facts_for(shape):
    sections, _ = beat.build_beat_plan({}, shape)
    return sections, mo.facts_from(sections)


@given(song_shapes, seeds, unit, unit)
@settings(max_examples=60, deadline=None)
def test_moments_are_planned_inside_their_section(shape, seed, warmth, brightness):
    sections, facts = facts_for(shape)
    plan = mo.plan_moments(facts, seed, warmth, brightness)
    for f in facts:
        for m in plan[f.index]:
            assert 0 <= m.bar and m.bar + m.bars <= f.bars if m.kind in ("dropout", "late_entry") else m.bar == 0
            if m.kind in ("dropout", "late_entry"):
                assert f.bars >= 8


@given(song_shapes, seeds)
@settings(max_examples=60, deadline=None)
def test_a_song_has_one_ending_and_at_most_one_one_off(shape, seed):
    sections, facts = facts_for(shape)
    plan = mo.plan_moments(facts, seed, 0.6, 0.4)
    kinds = [(f.index, m.kind) for f in facts for m in plan[f.index]]
    assert [i for i, k in kinds if k == "ending"] == [facts[-1].index]
    assert sum(1 for _, k in kinds if k == "one_off") <= 1
    has_place = any((f.name == "bridge" or (f.name == "chorus" and f.final)) and not (f is facts[-1] and f.bars < 3) for f in facts)
    assert sum(1 for _, k in kinds if k == "one_off") == (1 if has_place else 0)


@given(song_shapes, seeds, st.integers(0, 9))
@settings(max_examples=40, deadline=None)
def test_changing_one_sections_length_does_not_move_the_others_moments(shape, seed, which):
    which %= len(shape)
    other = list(shape)
    name, bars = other[which]
    other[which] = (name, bars + 1)
    a = mo.plan_moments(facts_for(shape)[1], seed, 0.6, 0.4)
    b = mo.plan_moments(facts_for(other)[1], seed, 0.6, 0.4)
    for i in range(len(shape)):
        if i != which and i != which - 1:                # the section before may change what it leads into
            assert a[i] == b[i]


def full_song_parts(seed: int, fp=None):
    fp = fp or {**BASE_FP, "genre_proximity": ["soul"]}
    sections, f = beat.build_beat_plan(fp, FULL)
    _, contexts, progs = beat.plan_contexts(sections, f, seed)
    out = []
    for s, ctx in zip(sections, contexts):
        parts = composer.compose_section(s.name, progs[s.name], s.bars, s.energy, s.density, layers=s.layers, ctx=ctx)
        out.append((s, ctx, progs[s.name], parts))
    return out


@given(seeds)
@settings(max_examples=25, deadline=None)
def test_the_song_ends_on_one_held_chord_with_a_crash(seed):
    s, ctx, prog, parts = full_song_parts(seed)[-1]
    lo = s.bars * 4.0 - 4.0
    for p in parts:
        if p.name.startswith("finale"):
            continue
        assert not [e for e in p.events if e.start >= lo], p.name
    names = {p.name for p in parts}
    assert {"finale_keys", "finale_drums", "finale_bass"} <= names
    assert any(e.note == composer.CRASH for p in parts if p.name == "finale_drums" for e in p.events)


@given(seeds)
@settings(max_examples=25, deadline=None)
def test_a_stop_leaves_the_last_beat_silent_and_a_late_entry_waits(seed):
    for s, ctx, prog, parts in full_song_parts(seed):
        end = s.bars * 4.0
        kinds = {m.kind for m in ctx.moments}
        if "stop" in kinds and "ending" not in kinds:
            for p in parts:
                assert not [e for e in p.events if e.start >= end - 1.0], p.name
        for m in ctx.moments:
            if m.kind == "late_entry":
                for p in parts:
                    if p.name in m.parts:
                        assert not [e for e in p.events if e.start < m.bar * 4.0 - 0.001]


@given(seeds)
@settings(max_examples=25, deadline=None)
def test_answers_are_notes_of_the_chord_playing(seed):
    for s, ctx, prog, parts in full_song_parts(seed):
        for p in parts:
            if p.name != "color":
                continue
            for e in p.events:
                pcs = {n % 12 for n in prog["chords"][int(e.start // 4) % len(prog["chords"])]}
                assert e.note % 12 in pcs


@given(seeds)
@settings(max_examples=25, deadline=None)
def test_the_one_time_sound_plays_in_one_section_only(seed):
    where = [s.index for s, ctx, prog, parts in full_song_parts(seed) if any(p.name == "color_once" for p in parts)]
    assert len(where) == 1


@given(seeds)
@settings(max_examples=15, deadline=None)
def test_moments_never_break_the_playing_rules(seed):
    for s, ctx, prog, parts in full_song_parts(seed):
        for p in parts:
            for e in p.events:
                assert 0 <= e.note <= 127 and 1 <= e.velocity <= 127 and e.start >= 0 and e.duration > 0
                assert e.start < s.bars * 4.0
            if not p.is_drums:
                by_pitch: dict[int, list] = {}
                for e in p.events:
                    by_pitch.setdefault(e.note, []).append(e)
                for events in by_pitch.values():
                    events.sort(key=lambda e: e.start)
                    for a, b in zip(events, events[1:]):
                        assert a.start + a.duration <= b.start + 1e-9


def test_different_kinds_of_section_get_different_sounds():
    sounds = {mo._colour(11, n, True) for n in ("verse", "chorus", "bridge", "outro")}
    assert len(sounds) == 4


# ── polish: the per-instrument mixing chain ───────────────

from app.services.generation import polish  # noqa: E402

noise_len = st.integers(2000, 30000)


def noise(n: int, seed: int, level: float = 6000.0) -> np.ndarray:
    return (np.random.default_rng(seed).standard_normal((n, 2)) * level).astype(np.float32)


@given(st.sampled_from(sorted(polish.STRIPS)), noise_len, seeds, st.integers(50, 180))
@settings(max_examples=30, deadline=None)
def test_treating_a_part_keeps_its_length_and_stays_finite(name, n, seed, bpm):
    x = noise(n, seed)
    y = polish.treat_part(name, x, bpm)
    assert y.shape == x.shape and y.dtype == np.float32
    assert np.isfinite(y).all()


def test_unknown_parts_pass_through_untouched():
    x = noise(5000, 1)
    assert polish.treat_part("something_new", x, 90) is x


def test_every_alias_points_at_a_real_strip():
    assert all(target in polish.STRIPS for target in polish.ALIASES.values())


def test_the_bass_loses_rumble_and_the_pad_gets_space():
    t = np.arange(44100 * 2) / 44100
    rumble = (np.sin(2 * np.pi * 10 * t) * 8000).astype(np.float32)[:, None].repeat(2, axis=1)
    settled = polish.treat_part("bass", rumble, 90)[44100:]          # after the filter has settled
    assert np.abs(settled).max() < 8000 * 0.4
    click = np.zeros((44100 * 2, 2), dtype=np.float32)
    click[100:140] = 12000
    out = polish.treat_part("pad", click, 90)
    assert np.abs(out[22050:]).max() > 1.0          # a tail rings long after the click


@given(st.floats(-1.0, 1.0, allow_nan=False))
def test_panning_never_makes_the_sound_louder_overall(pan):
    x = noise(4000, 3)
    y = polish._pan(x, pan)
    assert float(np.sum(y ** 2)) <= float(np.sum(x ** 2)) * 1.01


def test_the_song_pass_never_goes_over_the_ceiling():
    loud = np.clip(noise(44100 * 3, 5, 12000.0), -32000, 32000)
    out = polish.treat_song(loud)
    assert out.shape == loud.shape
    assert np.abs(out).max() <= 32768 * 10 ** (polish.CEILING_DB / 20) + 1


def test_the_chain_changes_the_sound_but_not_the_timing():
    fixed = {**BASE_FP, "genre_proximity": ["soul"]}
    sections, f = beat.build_beat_plan(fixed, [("verse", 2), ("chorus", 2)])
    _, plain = beat.render_song(sections, f, 9, mix_chain=False)
    _, polished = beat.render_song(sections, f, 9, mix_chain=True)
    assert plain.shape == polished.shape
    assert not np.array_equal(plain, polished)
    assert np.abs(polished).max() <= 32767


def test_every_part_goes_through_the_chain_when_it_is_on_and_none_when_off(monkeypatch):
    seen: list[str] = []
    real = polish.treat_part

    def spy(name, audio, bpm):
        seen.append(name)
        return real(name, audio, bpm)

    monkeypatch.setattr(polish, "treat_part", spy)
    fixed = {**BASE_FP, "genre_proximity": ["soul"]}
    sections, f = beat.build_beat_plan(fixed, [("verse", 2), ("chorus", 2)])
    beat.render_song(sections, f, 9, mix_chain=False)
    assert seen == []
    beat.render_song(sections, f, 9, mix_chain=True)
    wanted = sum(len(composer.compose_section(s.name, theory.build_progression(f["key"], f["energy_level"], f["tempo_feel"]), s.bars, s.energy, s.density, layers=s.layers)) for s in sections)
    assert len(seen) >= wanted - 1 and {"drums", "bass", "keys"} <= set(seen)


# ── review fixes ──────────────────────────────────────────

@given(seeds)
@settings(max_examples=40, deadline=None)
def test_the_one_time_sound_is_never_planned_where_the_ending_would_erase_it(seed):
    shape = [("intro", 4), ("verse", 8), ("chorus", 2)]          # last section is too short to keep it
    facts = facts_for(shape)[1]
    plan = mo.plan_moments(facts, seed, 0.6, 0.4)
    last = facts[-1].index
    assert not any(m.kind == "one_off" for m in plan[last])


def test_an_empty_section_stays_silent_instead_of_being_boosted():
    sections, f = beat.build_beat_plan({**BASE_FP}, [("verse", 2), ("chorus", 2)])
    sections[0].layers = []
    mixes, full = beat.render_song(sections, f, 3, mix_chain=False)
    assert db(mixes[0]) < -60.0


def test_the_ceiling_in_the_chain_matches_the_final_peak_level():
    assert abs(10 ** (polish.CEILING_DB / 20.0) - beat.PEAK_TARGET) < 0.02


def test_fetch_script_rejects_a_file_that_is_not_a_soundfont(tmp_path):
    import subprocess
    from pathlib import Path
    script = Path(__file__).resolve().parent.parent / "scripts" / "fetch_soundfont.sh"
    text = script.read_text()
    assert "RIFF" in text and "sfbk" in text and ".part" in text and "curl -fsSL" in text
    assert "file \"$SF_PATH\"" not in text            # the `file` command is not in the slim image


# ── a tapped rhythm changes the drums (start-from-any-input 3.2) ──
def test_a_tapped_groove_replaces_the_kick_and_hat_lanes_and_keeps_the_snare():
    from app.services.generation import beat, composer
    from app.services.intake.rhythm import groove_to_style_drums
    from app.services.generation.styles import pick_style
    fp = {"tempo_bpm": 100, "key": "C minor", "energy_level": 0.6, "density": 0.5}
    groove = {"kick": "x..x.x..x.......", "hat": "...........x.x.x"}
    secs, nfp = beat.build_beat_plan({**fp, "groove": groove})
    style, ctxs, progs = beat.plan_contexts(secs, nfp, 1)
    assert style.drums["kick"] == groove["kick"]
    assert style.drums["snare"] == pick_style(nfp).drums["snare"]
    parts = composer.compose_section("verse", progs["verse"], 4, 0.6, 0.5, layers=["drums"], ctx=next(c for c in ctxs if c.name == "verse"))
    kicks = sorted({round(e.start % 4.0, 2) for e in parts[0].events if e.note == composer.KICK and e.start % 4.0 < 3.5})
    assert 0.0 in kicks and 0.75 in kicks                 # steps 0 and 3 of the tapped pattern


def test_a_broken_groove_leaves_the_style_alone():
    from app.services.intake.rhythm import groove_to_style_drums
    base = {"kick": "x...", "half_kick": "x...", "hat": "x...", "half_hat": "x..."}
    for bad in ({}, {"kick": "x", "hat": "x"}, {"kick": "." * 16, "hat": "." * 16}):
        assert groove_to_style_drums(bad, base) == base
