"""
DDSP timbre transfer worker (Magenta, Apache-2.0), run in its own environment with TensorFlow.
  python ddsp_worker.py IN.wav INSTRUMENT OUT.wav CACHE_DIR

Follows Magenta's timbre-transfer colab: measure the hum's pitch (CREPE) and loudness, shift its octave toward the
instrument's usual register, match its loudness to the instrument's recordings, and resynthesise. The person's
own phrasing (where they slide, swell and breathe) is kept; only the instrument changes.
"""
from __future__ import annotations

import os
import pickle
import sys
import urllib.request

import numpy as np

SR = 16000
BUCKET = "https://storage.googleapis.com/ddsp/models/timbre_transfer_colab/2021-07-08"
STEPS = {"violin": 40000}


def fetch(instrument: str, cache: str) -> str:
    d = os.path.join(cache, f"ddsp_{instrument}")
    os.makedirs(d, exist_ok=True)
    step = STEPS.get(instrument, 20000)
    for name in (f"ckpt-{step}.data-00000-of-00001", f"ckpt-{step}.index", "dataset_statistics.pkl", "operative_config-0.gin"):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            urllib.request.urlretrieve(f"{BUCKET}/solo_{instrument}_ckpt/{name}", p)
    return d


def _stub_unused() -> None:
    """Modules ddsp.training imports at the top but timbre transfer never calls (see app.py DDSP_DEPS)."""
    import types

    for name in ("hypertune", "google", "google.cloud", "google.cloud.storage", "tensorflow_datasets", "note_seq",
                 "note_seq.sequences_lib", "tflite_support", "tensorflowjs"):
        try:
            __import__(name)
        except Exception:  # noqa: BLE001
            mod = types.ModuleType(name)
            sys.modules[name] = mod
            parent, _, child = name.rpartition(".")
            if parent in sys.modules:
                setattr(sys.modules[parent], child, mod)


def main() -> int:
    src, instrument, out, cache = sys.argv[1:5]
    _stub_unused()
    import gin
    import librosa
    import soundfile as sf
    import ddsp
    import ddsp.training
    from ddsp.training.postprocessing import detect_notes, fit_quantile_transform

    audio, _ = librosa.load(src, sr=SR, mono=True, duration=60)
    audio = audio[np.newaxis, :]
    ddsp.spectral_ops.reset_crepe()
    feats = ddsp.training.metrics.compute_audio_features(audio)
    feats["loudness_db"] = feats["loudness_db"].astype(np.float32)

    model_dir = fetch(instrument, cache)
    with open(os.path.join(model_dir, "dataset_statistics.pkl"), "rb") as f:
        stats = pickle.load(f)
    with gin.unlock_config():
        gin.parse_config_file(os.path.join(model_dir, "operative_config-0.gin"), skip_unknown=True)
    time_steps_train = gin.query_parameter("F0LoudnessPreprocessor.time_steps")
    n_samples_train = gin.query_parameter("Harmonic.n_samples")
    hop = int(n_samples_train / time_steps_train)
    time_steps = int(audio.shape[1] / hop)
    n_samples = time_steps * hop
    with gin.unlock_config():
        gin.parse_config([f"Harmonic.n_samples = {n_samples}", f"FilteredNoise.n_samples = {n_samples}",
                          f"F0LoudnessPreprocessor.time_steps = {time_steps}", "oscillator_bank.use_angular_cumsum = True"])
    for k in ("f0_hz", "f0_confidence", "loudness_db"):
        feats[k] = feats[k][:time_steps]
    feats["audio"] = feats["audio"][:, :n_samples]

    # Auto-adjust (from the colab): octave toward the instrument's mean pitch, loudness by quantile transform.
    mask_on, _ = detect_notes(feats["loudness_db"], feats["f0_confidence"], 0.85)
    if np.any(mask_on):
        target_mean = stats["mean_pitch"]
        pitch = ddsp.core.hz_to_midi(feats["f0_hz"])
        mean = np.mean(pitch[mask_on])
        shift = np.round((target_mean - mean) / 12.0)
        shift = float(np.clip(shift, -2, 2))
        feats["f0_hz"] = feats["f0_hz"] * (2.0 ** shift)
        _, loud_norm = fit_quantile_transform(feats["loudness_db"], mask_on, inv_quantile=stats["quantile_transform"])
        feats["loudness_db"] = np.where(mask_on, loud_norm[:, 0], feats["loudness_db"] - 20.0).astype(np.float32)
    feats["f0_hz"] = np.clip(feats["f0_hz"], 0.0, librosa.midi_to_hz(110.0)).astype(np.float32)

    model = ddsp.training.models.Autoencoder()
    ckpt = [f for f in os.listdir(model_dir) if f.endswith(".index")][0][:-6]
    model.restore(os.path.join(model_dir, ckpt))
    outputs = model(feats, training=False)
    gen = np.asarray(model.get_audio_from_outputs(outputs))[0]
    gen = gen / (np.abs(gen).max() + 1e-9) * 0.8
    sf.write(out, gen.astype(np.float32), SR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
