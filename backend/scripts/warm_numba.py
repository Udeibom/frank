"""
Compile and cache numba code at Docker build time (ship-it spec 13, requirement 2.1).

librosa's numba functions compile on first import/use. On a fresh server that took 61 s and +100 MB
(381 MB idle vs 278 MB with a warm cache, measured Nov 17), which left no room in 512 MB for any job.
Running the same calls during the build writes the compiled code to NUMBA_CACHE_DIR inside the image.
NUMBA_CPU_NAME=generic (set in the Dockerfile) keeps that cache valid on whatever CPU Render runs us on.
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://build.invalid")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "build-only")

import numpy as np

import app.main  # noqa: F401  (imports every module the server imports)
import librosa

sr = 22050
t = np.arange(sr * 3) / sr
y = (0.3 * np.sin(2 * np.pi * 220 * t) * (np.sin(2 * np.pi * 2 * t) > 0)).astype(np.float32)
librosa.pyin(y, fmin=80, fmax=1000, sr=16000, frame_length=2048, hop_length=1024)
librosa.onset.onset_detect(y=y, sr=sr, hop_length=512)
librosa.onset.onset_strength(y=y, sr=sr, hop_length=256)
librosa.beat.beat_track(y=y, sr=sr)
librosa.feature.chroma_stft(y=y, sr=sr, hop_length=2048, n_fft=4096)
librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
librosa.feature.rms(y=y)
print("numba cache warmed:", os.environ.get("NUMBA_CACHE_DIR"))
