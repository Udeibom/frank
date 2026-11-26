"""Finish and intent (spec 11): parts, finishing, intent, surprise, separate parts."""
from __future__ import annotations

import numpy as np
import pytest

from app.services.generation import beat
from app.services.generation import fingerprint as fp_utils

FP = fp_utils.normalize({"tempo_bpm": 110, "key": "D minor", "energy_level": 0.6, "density": 0.5, "warmth": 0.8, "brightness": 0.2})


def short_plan():
    sections, fp = beat.build_beat_plan(FP)
    keep = sections[:3]
    for i, s in enumerate(keep):
        s.index = i
        s.bars = 2
        s.uid = i
    beat._stamp_repeats(keep)
    return keep, fp


@pytest.mark.parametrize("mix_chain", [False, True])
def test_the_parts_add_up_to_the_beat(mix_chain):
    sections, fp = short_plan()
    report: dict = {}
    if mix_chain:
        # the full beat's final glue is the only non-linear step; compare against the beat without it
        import app.services.generation.polish as polish
        real = polish.treat_song
        polish.treat_song = lambda song: song
    try:
        _, full = beat.render_song(sections, fp, 7, mix_chain=mix_chain, report=report)
    finally:
        if mix_chain:
            polish.treat_song = real
    got: dict[str, np.ndarray] = {}
    families = beat.render_parts(sections, fp, 7, None, report["section_gains"], report["song_gain"],
                                 lambda name, audio: got.__setitem__(name, audio.astype(np.int32)), mix_chain=mix_chain)
    assert families and set(got) == set(families) and len(families) >= 3
    total = sum(got.values()).astype(np.float64)
    n = min(total.shape[0], full.shape[0])
    a, b = total[:n].mean(axis=1), full[:n].astype(np.float64).mean(axis=1)
    # The synth's chorus wobbles with time, so a part rendered on its own is never sample-identical; what must
    # hold is that it SOUNDS the same: the same shape and the same loudness moment by moment.
    assert np.corrcoef(a, b)[0, 1] > 0.99
    hop = 2205
    fa = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, "valid")[::hop]) + 1
    fb = np.sqrt(np.convolve(b ** 2, np.ones(hop) / hop, "valid")[::hop]) + 1
    loud = fb > 100
    assert np.percentile(np.abs(20 * np.log10(fa[loud] / fb[loud])), 95) < 1.0
    assert report["section_gains"] and all(g > 0 for g in report["section_gains"])


def test_finishing_reaches_streaming_loudness_without_clipping():
    from app.services.audio import mastering

    sr = mastering.SR
    t = np.arange(int(12 * sr)) / sr
    rng = np.random.default_rng(3)
    song = 0.08 * np.sin(2 * np.pi * 110 * t) + 0.03 * rng.normal(size=t.size) * (1 + np.sin(2 * np.pi * 0.25 * t))
    for k in np.arange(0, 12, 0.5):                     # a quiet mix with some hits
        i = int(k * sr)
        song[i:i + 3000] += 0.2 * np.exp(-np.arange(3000) / 500) * rng.normal(size=3000)
    mix = np.stack([song, song * 0.9]).astype(np.float32)
    before = mix.copy()
    mp3, report = mastering.finish(mix)
    assert np.array_equal(mix, before), "the mix handed in is not changed"
    assert len(mp3) > 1000
    assert report["on_target"], report
    assert abs(report["loudness"] - mastering.TARGET_LUFS) <= mastering.LOUDNESS_TOLERANCE
    assert report["clipping"] <= 1e-4


# ── mixing every part ────────────────────────────────────────────────────

def _wav(x: np.ndarray) -> bytes:
    import io

    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, x.T.astype(np.float32), 44100, format="WAV", subtype="FLOAT")
    return buf.getvalue()


def test_each_part_has_its_own_level_and_can_be_muted():
    from app.services.audio import mixing

    t = np.arange(44100) / 44100
    drums = np.stack([0.2 * np.sin(2 * np.pi * 60 * t)] * 2)
    keys = np.stack([0.2 * np.sin(2 * np.pi * 440 * t)] * 2)
    parts = [("drums", lambda: _wav(drums)), ("keys", lambda: _wav(keys))]
    base = {"beat_gain_db": 0.0, "parts": {}}
    both = mixing.render_mix(None, None, None, base, parts=parts)
    no_keys = mixing.render_mix(None, None, None, {**base, "parts": {"keys": {"muted": True}}}, parts=parts)
    quieter = mixing.render_mix(None, None, None, {**base, "parts": {"keys": {"level_db": -12}}}, parts=parts)
    spec = lambda x: np.abs(np.fft.rfft(x[0]))  # noqa: E731
    k = 440
    assert spec(no_keys)[k] < 0.01 * spec(both)[k]
    assert 0.2 < spec(quieter)[k] / spec(both)[k] < 0.3            # -12 dB is a quarter
    assert abs(spec(quieter)[60] - spec(both)[60]) / spec(both)[60] < 0.05   # the drums are untouched


def test_the_mix_room_makes_at_most_three_changes_and_understands_parts():
    from app.routers.mix import DEFAULT_MIX_PARAMS, apply_actions

    acts = [{"type": "part_adjust", "params": {"part": "piano", "level_delta_db": -3, "section_index": 5}},
            {"type": "part_adjust", "params": {"part": "drums", "tone": "warmer"}},
            {"type": "adjust_levels", "params": {"vocal_delta_db": 2}},
            {"type": "apply_effect", "params": {"target": "vocal", "effect": "space", "on": True}}]
    p, render = apply_actions(dict(DEFAULT_MIX_PARAMS), acts)
    assert render
    assert p["parts"]["keys"]["sections"]["5"] == -3 and "level_db" not in p["parts"]["keys"]
    assert p["parts"]["drums"]["tone"] == "warmer"
    assert p["vocal_gain_db"] == 2
    assert "space" not in p["vocal_effects"], "a fourth change is not made"


def test_mix_room_understands_room_amount_interaction_and_drum_bus():
    from app.routers.mix import DEFAULT_MIX_PARAMS, apply_actions

    acts = [
        {"type": "apply_effect", "params": {"target": "vocal", "effect": "space", "on": True, "amount": 0.42}},
        {"type": "duck", "params": {"key": "vocal", "target": "piano", "amount": 3.0}},
        {"type": "drum_bus", "params": {"on": True, "glue": 2.0}},
    ]
    p, render = apply_actions(dict(DEFAULT_MIX_PARAMS), acts)
    assert render
    assert p["vocal_space_amount"] == 0.42
    assert p["interactions"] == {"vocal:keys": 1.0}
    assert p["drum_bus"] == {"on": True, "glue": 1.0}


def test_mix_room_part_space_and_section_index_are_clamped():
    from app.routers.mix import DEFAULT_MIX_PARAMS, apply_actions

    acts = [
        {"type": "part_adjust", "params": {"part": "piano", "space_amount": 0.6}},
        {"type": "section_adjust", "params": {"section_index": 2, "delta_db": 40.0}},
    ]
    p, render = apply_actions(dict(DEFAULT_MIX_PARAMS), acts)
    assert render
    assert p["parts"]["keys"]["space_amount"] == 0.6
    assert p["section_gain_db"]["2"] == 12.0


# ── intent, surprise, separate parts, waveform ──────────────────────────

def test_the_first_description_is_kept_and_asked_back_in_their_words():
    from app.services.finish import intent

    assert intent.looks_like_description("feel", "standing alone in the rain after losing someone")
    assert not intent.looks_like_description("feel", "make it faster")
    assert not intent.looks_like_description("mix", "standing alone in the rain after losing someone")
    assert not intent.looks_like_description("idea", "can you help me with the words")
    q = intent.question("standing alone in the rain after losing someone")
    assert "standing alone in the rain after losing someone" in q and q.endswith("?")


def test_the_surprise_changes_one_bold_thing_and_keeps_the_tune():
    from app.services.finish import surprise
    from app.services.generation import ops

    sections, fp = beat.build_beat_plan(FP)
    for s in sections:
        s.uid = s.index
    title, plain, raw = surprise.choose_idea(sections)
    new, seed, changes = ops.apply_operations(sections, 7, raw)
    assert title and plain and changes
    if raw[0]["op"] == "remove_part":
        assert all(a["part"] in surprise.BACKBONE for a in raw)
        assert all(("melody" in a.layers) == ("melody" in b.layers) for a, b in zip(sections, new)), "the tune stays"
    sparse = [beat.SectionPlan(index=i, name="verse", label="Verse", bars=8, energy=0.3, density=0.3, layers=["keys"], uid=i) for i in range(3)]
    assert surprise.choose_idea(sparse)[2] == [{"op": "another_song"}]


def test_separate_parts_zip_has_plain_names_and_every_file():
    import io
    import zipfile

    from app.services.finish import parts_zip

    files = [(parts_zip.file_name(p), b"x" * 10) for p in ("drums", "keys", "melody", "pad")] + [("Your voice.mp3", b"v")]
    z = zipfile.ZipFile(io.BytesIO(parts_zip.build_zip(files, "Rain / song")))
    names = sorted(n.split("/", 1)[1] for n in z.namelist())
    assert names == sorted(["Drums.mp3", "Keys.mp3", "Tune.mp3", "Soft background.mp3", "Your voice.mp3", "README.txt"])
    assert all("/" not in n.split("/", 1)[0] for n in z.namelist())


def test_the_waveform_is_a_short_shape_between_zero_and_one():
    from app.services.jobs.export_runner import WAVE_POINTS, waveform

    audio = np.random.default_rng(1).normal(0, 0.3, (2, 44100 * 20)).astype(np.float32)
    w = waveform(audio)
    assert 0 < len(w) <= WAVE_POINTS and max(w) == 1.0 and min(w) >= 0
    assert waveform(np.zeros((2, 0), dtype=np.float32)) == []


def test_a_taste_statement_is_not_the_song_description():
    from app.services.finish import intent

    assert not intent.looks_like_description("feel", "I hate autotune on my voice, keep it natural")
    assert intent.looks_like_description("feel", "a song for my grandmother who sang to me every night")
