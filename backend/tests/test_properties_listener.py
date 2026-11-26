"""
Property tests for the Listener (spec 03, design "Correctness properties").
Audio is short and at 22.05 kHz so the properties run quickly.
"""
from __future__ import annotations

import asyncio
import re
from unittest import mock

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from app.services.generation.beat import SectionPlan
from app.services.listener import dsp, findings, service
from app.services.listener.models import MeasurementReport, SectionInfo

SR = 22050
BPM = 120.0                      # one bar = 2 seconds
BAR = int(2.0 * SR)
FAST = settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def noise(seed: int, seconds: float, amp: float = 0.1) -> np.ndarray:
    return (np.random.default_rng(seed).standard_normal(int(seconds * SR)) * amp).astype(np.float32)


def plan(names: list[str], bars: int = 1) -> list[SectionPlan]:
    return [SectionPlan(i, n, n.capitalize(), bars, 0.5, 0.5, layers=["keys", "bass", "drums"]) for i, n in enumerate(names)]


def song(names: list[str], amps: list[float], seed: int = 0) -> tuple[list[SectionPlan], np.ndarray]:
    secs = plan(names)
    audio = np.concatenate([noise(seed + i, 2.0, a) for i, a in enumerate(amps)])
    return secs, audio


# ── 1. gain invariance ───────────────────────────────────────────────────

@FAST
@given(st.floats(0.2, 3.0), st.integers(0, 50))
def test_scaling_the_whole_song_keeps_loudness_order_and_findings(gain, seed):
    secs, audio = song(["verse", "chorus", "verse", "chorus"], [0.05, 0.06, 0.05, 0.12], seed)
    a = service.measure_audio(secs, BPM, beat=audio, sr=SR)
    b = service.measure_audio(secs, BPM, beat=audio * np.float32(gain), sr=SR)
    la = [a.values[f"section.{i}.loudness"] for i in range(4)]
    lb = [b.values[f"section.{i}.loudness"] for i in range(4)]
    assert np.argsort(la).tolist() == np.argsort(lb).tolist()
    assert np.allclose(np.diff(la), np.diff(lb), atol=0.05)          # every gap between sections is unchanged
    gap_ids = lambda r: [f.id for f in findings.find_issues(r).findings if f.id not in ("clipping", "too_loud", "too_quiet")]
    assert gap_ids(a) == gap_ids(b)               # clipping and overall level legitimately depend on gain


# ── 2. identity ──────────────────────────────────────────────────────────

@FAST
@given(st.integers(0, 50))
def test_identical_sections_are_alike_and_silence_is_nothing_in_common(seed):
    x = noise(seed, 2.0)
    assert dsp.similarity(x, x.copy(), SR) > 0.95
    assert dsp.similarity(x, np.zeros_like(x), SR) == 0.0


# ── 3. timing recovery ───────────────────────────────────────────────────

@settings(max_examples=12, deadline=None)
@given(st.integers(20, 200), st.integers(0, 20))
def test_a_delayed_copy_is_reported_within_one_frame(delay_ms, seed):
    rng = np.random.default_rng(seed)
    t = np.arange(int(6 * SR)) / SR
    gate = (np.sin(2 * np.pi * 2.0 * t) > 0.85).astype(np.float32)           # clicky rhythm so the beat is findable
    beat = gate * rng.standard_normal(t.size).astype(np.float32)
    d = int(delay_ms / 1000 * SR)
    vocal = np.concatenate([np.zeros(d, np.float32), beat])[: beat.size]
    off, conf = dsp.timing_offset_ms(vocal, beat, SR)
    frame_ms = 256 / SR * 1000
    assert abs(off - delay_ms) <= frame_ms + 1
    assert conf > 0.3


# ── 4. silence and empty input never raise ───────────────────────────────

@FAST
@given(st.integers(0, 3 * SR))
def test_silence_and_short_audio_give_could_not_measure_not_zero(n):
    secs = plan(["verse", "chorus"])
    rep = service.measure_audio(secs, BPM, beat=np.zeros(n, np.float32), vocal=np.zeros(n, np.float32), mix=np.zeros(n, np.float32), sr=SR, key="C minor")
    assert not any(k.endswith(".loudness") for k in rep.values)
    assert rep.unmeasured
    assert all(u.why and not re.search(r"\d", u.why) for u in rep.unmeasured)
    findings.find_issues(rep, "the chorus isn't lifting")                      # must not raise


def test_nothing_at_all_is_explained_not_crashed():
    rep = service.measure_audio([], 0.0, sr=SR)
    assert rep.unmeasured
    assert dsp.loudness(None, SR) is None and dsp.brightness_hz(np.array([], np.float32), SR) is None


@FAST
@given(st.sampled_from([np.nan, np.inf, -np.inf]))
def test_garbage_samples_are_not_measured(bad):
    x = noise(1, 2.0)
    x[100] = bad
    assert dsp.loudness(x, SR) is None


# ── 5. determinism ───────────────────────────────────────────────────────

@FAST
@given(st.integers(0, 50))
def test_same_audio_same_report(seed):
    secs, audio = song(["verse", "chorus"], [0.05, 0.1], seed)
    assert service.measure_audio(secs, BPM, beat=audio, sr=SR) == service.measure_audio(secs, BPM, beat=audio, sr=SR)


# ── 6. read-only ─────────────────────────────────────────────────────────

@FAST
@given(st.integers(0, 50))
def test_measuring_never_changes_its_input(seed):
    secs, audio = song(["verse", "chorus"], [0.05, 0.1], seed)
    vocal = noise(seed + 9, 4.0)
    before = (audio.copy(), vocal.copy(), [s.__dict__.copy() for s in secs])
    service.measure_audio(secs, BPM, beat=audio, vocal=vocal, mix=audio, sr=SR, key="C minor")
    assert np.array_equal(audio, before[0]) and np.array_equal(vocal, before[1])
    assert [s.__dict__ for s in secs] == before[2]


def test_listening_to_a_project_writes_nothing_but_the_cache():
    from app.services.listener import project

    writes: list[tuple[str, str]] = []

    class Table:
        def __init__(self, name): self.name = name
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return mock.Mock(data=[])
        def upsert(self, *a, **k): writes.append((self.name, "upsert")); return self
        def insert(self, *a, **k): writes.append((self.name, "insert")); return self
        def update(self, *a, **k): writes.append((self.name, "update")); return self
        def delete(self, *a, **k): writes.append((self.name, "delete")); return self

    sb = mock.Mock(); sb.table = lambda name: Table(name)
    secs, audio = song(["verse", "chorus"], [0.05, 0.1])
    fp = {"tempo_bpm": 120, "key": "C minor"}
    beat_version = {"id": "b1", "render_url": "x", "params": {"fingerprint": fp, "seed": 1, "sections": [
        {"index": s.index, "name": s.name, "bars": s.bars, "energy": 0.5, "density": 0.5, "layers": s.layers} for s in secs]}}

    async def state(_): return {"active_beat_version_id": "b1"}
    async def get_beat(_): return beat_version
    with mock.patch.object(project, "get_supabase", lambda: sb), \
         mock.patch.object(project.projects_db, "get_project_active_state", state), \
         mock.patch.object(project.beat_db, "get_beat_version", get_beat), \
         mock.patch.object(project, "fetch_audio_bytes", lambda url: b"x"), \
         mock.patch.object(project.service, "decode", lambda b: np.concatenate([audio, audio])[: len(audio)]), \
         mock.patch.object(project.service, "score_facts", lambda *a, **k: {}):
        rep = asyncio.run(project.measure_song("p1"))
    assert rep.values and all(t == "listener_cache" for t, _ in writes)


# ── 7. honesty ───────────────────────────────────────────────────────────

def test_no_rule_firing_with_a_concern_means_no_clear_cause_and_no_made_up_finding():
    rep = MeasurementReport(sections=[SectionInfo(index=0, name="verse", bars=4)], values={"section.0.loudness": -20.0})
    out = findings.find_issues(rep, "something feels off")
    assert out.no_clear_cause and out.findings == []
    assert not findings.find_issues(rep, None).no_clear_cause              # no concern, nothing to explain


@FAST
@given(st.lists(st.floats(0.01, 0.4), min_size=4, max_size=4), st.integers(0, 20))
def test_every_finding_points_at_measurements_that_exist(amps, seed):
    secs, audio = song(["verse", "chorus", "verse", "chorus"], amps, seed)
    vocal = noise(seed + 5, 8.0, 0.2)
    rep = service.measure_audio(secs, BPM, beat=audio, vocal=vocal, mix=audio, sr=SR, key="C minor")
    for f in findings.find_issues(rep).findings:
        assert f.evidence and all(e in rep.values for e in f.evidence)
        assert 0.0 <= f.confidence <= 1.0


def test_the_chorus_that_is_as_quiet_as_the_verse_is_found_and_a_real_lift_is_not():
    secs, flat = song(["verse", "chorus"], [0.05, 0.052])
    _, lifted = song(["verse", "chorus"], [0.05, 0.15])
    got = findings.find_issues(service.measure_audio(secs, BPM, beat=flat, sr=SR), "the chorus doesn't lift")
    assert [f.id for f in got.findings] == ["chorus_lift"] and "chorus" in got.findings[0].plain
    ok = findings.find_issues(service.measure_audio(secs, BPM, beat=lifted, sr=SR), "the chorus doesn't lift")
    assert ok.no_clear_cause


def test_a_buried_voice_is_found_and_a_clear_one_is_not():
    secs, beat = song(["verse", "chorus"], [0.2, 0.2])
    quiet = noise(4, 4.0, 0.01)
    loud = noise(4, 4.0, 0.4)
    assert "voice_buried" in [f.id for f in findings.find_issues(service.measure_audio(secs, BPM, beat=beat, vocal=quiet, sr=SR)).findings]
    assert "voice_buried" not in [f.id for f in findings.find_issues(service.measure_audio(secs, BPM, beat=beat, vocal=loud, sr=SR)).findings]


# ── plain language ───────────────────────────────────────────────────────

JARGON = re.compile(r"\b(db|hz|khz|lufs|bpm|tempo|key|mode|reverb|eq|compress\w*|stems?|midi|daw|vst|quantiz\w*|chroma|mfcc|cents?|ms|milliseconds?|semitones?|onsets?)\b", re.I)


def test_every_sentence_the_rules_can_say_is_plain_words():
    secs = plan(["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"])
    v: dict[str, float] = {}
    for s in secs:
        v[f"section.{s.index}.loudness"] = -20.0
        v[f"section.{s.index}.parts"] = 3.0
        v[f"section.{s.index}.vocal_gap"] = -9.0
        v[f"section.{s.index}.voice_band_gap"] = -9.0
        v[f"section.{s.index}.melody_fit"] = 0.1
        v[f"section.{s.index}.change"] = 0.0
    v.update({"repeat.1.3.sound": 0.99, "vocal.timing_ms": 90.0, "vocal.timing_confidence": 0.9, "vocal.in_tune": 0.2,
              "vocal.noise_floor": -30.0, "mix.clipping": 0.05, "mix.loudness": -30.0})
    rep = MeasurementReport(sections=[SectionInfo(index=s.index, name=s.name, bars=s.bars) for s in secs], values=v)
    out = findings.find_issues(rep, "something is off")
    assert {f.id for f in out.findings} >= {"chorus_lift", "copy", "voice_buried", "voice_crowded", "timing", "tuning", "melody_wanders", "clipping", "noise", "too_quiet", "flat"}
    for f in out.findings:
        assert not JARGON.search(f.plain), f.plain
        assert not re.search(r"\d", f.plain), f.plain
    loud = MeasurementReport(sections=rep.sections, values={**v, "mix.loudness": -3.0})
    assert any(f.id == "too_loud" for f in findings.find_issues(loud, "loud").findings)
    for f in findings.find_issues(loud, "loud").findings:
        assert not JARGON.search(f.plain)


def test_compare_reports_what_changed_in_plain_words():
    a = MeasurementReport(values={"section.1.loudness": -20.0, "mix.loudness": -18.0})
    b = MeasurementReport(values={"section.1.loudness": -16.0, "mix.loudness": -18.2})
    diffs = service.compare(a, b)
    assert [d.id for d in diffs] == ["section.1.loudness"] and "louder" in diffs[0].plain


def test_noise_is_only_measured_when_the_recording_has_pauses():
    steady = noise(3, 6.0, 0.2)                                   # sound all the way through: no pauses to judge by
    assert dsp.noise_floor_db(steady, SR) is None
    pauses = np.concatenate([noise(4, 1.0, 0.2), noise(5, 1.0, 0.002)] * 3)   # phrases with a quiet room between them
    floor = dsp.noise_floor_db(pauses, SR)
    assert floor is not None and floor < -40


def test_part_loudness_is_measured_from_cached_stems():
    secs, beat = song(["verse", "chorus"], [0.1, 0.2])
    score = {0: {"parts": ["keys", "bass", "drums"], "notes_per_bar": {"keys": 4, "bass": 2, "drums": 8}},
             1: {"parts": ["keys", "bass", "drums"], "notes_per_bar": {"keys": 4, "bass": 2, "drums": 8}}}
    rep = service.measure_audio(secs, BPM, beat=beat, parts={"keys": beat, "bass": beat * 0.3}, sr=SR, score=score)
    assert rep.score_facts["0"]["notes_per_bar"]["keys"] == 4
    assert "part.keys.loudness" in rep.values and "part.bass.loudness" in rep.values
    assert "part.keys.section.1.loudness" in rep.values
    assert not any(u.id == "part_loudness" for u in rep.unmeasured)


def test_symbolic_critic_findings_point_at_real_evidence_and_stay_plain():
    from app.services.listener import critic

    secs = plan(["verse", "chorus", "verse", "chorus"])
    values: dict[str, float] = {}
    facts: dict[str, dict] = {}
    for s in secs:
        note_counts = {"keys": 8.0, "bass": 2.0, "drums": 2.0}
        if s.name == "chorus":
            note_counts = {"keys": 8.0, "bass": 2.0}
        facts[str(s.index)] = {"parts": list(note_counts), "notes_per_bar": note_counts}
        values[f"section.{s.index}.parts"] = float(len(note_counts))
        for part, count in note_counts.items():
            values[f"section.{s.index}.notes_per_bar.{part}"] = count
    values["part.keys.loudness"] = -10.0
    values["part.bass.loudness"] = -20.0
    values["part.drums.loudness"] = -20.0
    rep = MeasurementReport(sections=[SectionInfo(index=s.index, name=s.name, bars=s.bars) for s in secs], values=values, score_facts=facts)
    found = findings.find_issues(rep, "busy loud and thin")
    ids = {f.id for f in found.findings}
    assert {"part_busy", "part_loud", "chorus_thin"} <= ids
    for f in found.findings:
        assert f.evidence and all(e in rep.values for e in f.evidence)
        assert not JARGON.search(f.plain) and not re.search(r"\d", f.plain)
