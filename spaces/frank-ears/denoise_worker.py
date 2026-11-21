"""
DeepFilterNet (MIT / Apache-2.0) room-noise removal, run by app.py in its own process with no GPU visible.
  python denoise_worker.py IN.wav OUT.wav
"""
from __future__ import annotations

import sys
import types


def main() -> int:
    src, out = sys.argv[1:3]
    # deepfilternet imports a torchaudio module that newer torchaudio removed; it only needs the type name.
    if "torchaudio.backend.common" not in sys.modules:
        mod = types.ModuleType("torchaudio.backend.common")
        mod.AudioMetaData = object
        sys.modules["torchaudio.backend"] = types.ModuleType("torchaudio.backend")
        sys.modules["torchaudio.backend.common"] = mod
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from df.enhance import enhance, init_df

    model, state, _ = init_df()
    y, _ = librosa.load(src, sr=state.sr(), mono=True, duration=600)
    cleaned = enhance(model, state, torch.from_numpy(y.astype(np.float32))[None, :])
    sf.write(out, cleaned.squeeze(0).numpy(), state.sr())
    return 0


if __name__ == "__main__":
    sys.exit(main())
