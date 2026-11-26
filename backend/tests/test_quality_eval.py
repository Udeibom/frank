import numpy as np

from scripts import quality_eval


def test_metrics_helpers_handle_silence_and_equal_values():
    silence = np.zeros((10, 2), dtype=np.int16)
    assert quality_eval.rms_db(silence) == -120.0
    assert quality_eval.digest(silence) == quality_eval.digest(silence.copy())


def test_section_lift_reports_each_section_and_range():
    class S:
        def __init__(self, index, name):
            self.index = index
            self.name = name

    sections = [S(0, "verse"), S(1, "chorus")]
    mixes = [np.full((10, 2), 100, dtype=np.int16), np.full((10, 2), 1000, dtype=np.int16)]
    report = quality_eval.section_lift(sections, mixes)
    assert report["0_verse"] < report["1_chorus"]
    assert round(report["range_db"], 2) == round(report["1_chorus"] - report["0_verse"], 2)


def test_compare_ignores_fingerprint_noise_and_flags_audio_changes():
    before = {"fixtures": {"one": {"audio": {"digest": "a"}, "notes": {"clash_rate": 0.1}, "fingerprint": {"warmth": 0.2}}}}
    after = {"fixtures": {"one": {"audio": {"digest": "b"}, "notes": {"clash_rate": 0.1}, "fingerprint": {"warmth": 0.9}}}}
    lines = quality_eval.compare(before, after)
    assert lines == ["changed audio: one.audio.digest"]
