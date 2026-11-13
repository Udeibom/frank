"""
Audio format conversion via FFmpeg.
The browser records WebM/Opus; most of our processing needs WAV.
All conversion runs server-side on CPU.
"""

import re
import subprocess
import tempfile
import os


def to_wav(input_bytes: bytes, input_ext: str = "webm") -> bytes:
    """
    Convert arbitrary audio bytes to 44.1kHz mono/stereo WAV using FFmpeg.
    Returns the WAV bytes. Cleans up temp files immediately.
    """
    # The extension only names a temp file (FFmpeg works out the real format from the content),
    # so keep it to a few letters and digits: never something that can act like a path.
    if not re.fullmatch(r"[a-z0-9]{1,5}", input_ext.lower()):
        input_ext = "bin"
    in_path = None
    out_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=f".{input_ext}", delete=False
        ) as in_file:
            in_file.write(input_bytes)
            in_path = in_file.name

        # Distinct output name: for a .wav input the old name was identical to
        # the input, and FFmpeg cannot overwrite its own input file.
        out_path = in_path.rsplit(".", 1)[0] + ".converted.wav"

        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", in_path,
                "-ar", "44100",   # 44.1kHz working sample rate
                "-ac", "1",       # mono is fine for voice memos and vocals
                out_path,
            ],
            capture_output=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(
                # Tail, not head: the head is just FFmpeg's version banner.
                f"FFmpeg conversion failed: {result.stderr.decode(errors='replace')[-300:]}"
            )

        with open(out_path, "rb") as f:
            return f.read()
    finally:
        # Always clean up temp files — Render free tier has limited disk
        for path in (in_path, out_path):
            if path and os.path.exists(path):
                os.remove(path)
