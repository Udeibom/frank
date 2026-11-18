"""Start from any input (spec 02): description and voice-memo path, one way in, tune-vs-words question."""
from __future__ import annotations

import io
import json

import numpy as np
import soundfile as sf
from hypothesis import given, settings, strategies as st

from app.services.intake import description, merge


def test_only_confident_well_formed_hints_are_offered_and_every_value_has_a_confidence():
    raw = {"summary": "A lonely walk home at 3am, quiet and cold.", "feeling_words": ["Lonely", "cold", 7],
           "hints": {"energy_level": {"value": 0.2, "confidence": 0.9}, "brightness": {"value": 0.3, "confidence": 0.4},
                     "warmth": {"value": 7, "confidence": 0.9}, "mode": {"value": "Dorian", "confidence": 0.9},
                     "tempo_feel": {"value": "floating", "confidence": 0.7}, "tempo_bpm": {"value": 80, "confidence": 1}},
           "question": ""}
    out = description.clean(raw)
    assert out["hints"] == {"energy_level": 0.2, "tempo_feel": "floating"}
    assert set(out["confidence"]) == {"energy_level", "brightness", "tempo_feel"}
    assert "3" not in out["summary"] and out["feeling_words"] == ["lonely", "cold"]


@settings(max_examples=200, deadline=None)
@given(st.dictionaries(st.sampled_from(["energy_level", "brightness", "warmth", "density", "mode", "tempo_feel", "bpm"]),
                       st.fixed_dictionaries({"value": st.one_of(st.floats(-2, 2), st.text(max_size=8), st.none()),
                                              "confidence": st.one_of(st.floats(-1, 2), st.none())}), max_size=7))
def test_whatever_the_model_says_the_hints_stay_in_range(hints):
    out = description.clean({"hints": hints})
    for k, v in out["hints"].items():
        if k in description.NUMERIC:
            assert 0.0 <= v <= 1.0
        else:
            assert v in description.CHOICES[k]
        assert out["confidence"][k] >= description.CONFIDENT


def test_a_broken_answer_is_asked_again_once():
    answers = iter(["not json", json.dumps({"summary": "Soft and hopeful.", "hints": {}})])
    calls = []

    def fake(system, user, temp):
        calls.append(user)
        return next(answers)

    out = description.read_description("it should feel soft and hopeful, like morning", fake)
    assert out["summary"] == "Soft and hopeful." and len(calls) == 2 and "<description>" in calls[0]


def test_the_question_reads_right_for_one_tune_and_for_words():
    c = [merge.Conflict("mode", "major", "minor")]
    assert merge.conflict_question(c, "tune").startswith("Your tune feels heavier")
    assert merge.conflict_question(c, "words").startswith("Your words feel heavier")


def _wav(x: np.ndarray, sr: int = 44100) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, x.astype(np.float32), sr, format="WAV")
    return buf.getvalue()


def test_humming_takes_the_tune_path_and_talking_takes_the_words_path():
    from app.routers.intake import is_speech

    sr = 44100
    hum = []
    for midi in (60, 62, 64, 62, 60):
        t = np.arange(int(0.8 * sr)) / sr
        f = 440 * 2 ** ((midi - 69) / 12)
        hum += [0.4 * np.sin(2 * np.pi * f * t) * np.hanning(t.size) ** 0.2, np.zeros(int(0.1 * sr))]
    hum_wav = _wav(np.concatenate(hum))
    rng = np.random.default_rng(2)
    talk = []
    for _ in range(14):                                 # short syllables: noise bursts with a little moving pitch
        n = int(rng.uniform(0.08, 0.18) * sr)
        t = np.arange(n) / sr
        f = rng.uniform(110, 220) * (1 + 0.3 * t / t[-1])
        talk += [0.2 * (np.sin(2 * np.pi * np.cumsum(f) / sr) * 0.5 + rng.normal(0, 0.3, n)) * np.hanning(n), np.zeros(int(0.07 * sr))]
    talk_wav = _wav(np.concatenate(talk))
    assert not is_speech(hum_wav, words=0)
    assert not is_speech(hum_wav, words=8), "a sung line with words is still a tune"
    assert is_speech(talk_wav, words=12)
