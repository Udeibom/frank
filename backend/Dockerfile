# Frank backend — needs native FluidSynth + FFmpeg, so we use a Docker image
# rather than Render's plain Python environment (which can't install apt packages).
# Render supports deploying from a Dockerfile on the free tier.

FROM python:3.12-slim

# System dependencies for the procedural music engine and audio conversion:
#   - fluidsynth + libfluidsynth: SoundFont synthesis (pyfluidsynth links to it)
#   - ffmpeg: audio format conversion and mixing
#   - curl: used by the soundfont fetch script
RUN apt-get update && apt-get install -y --no-install-recommends \
    fluidsynth \
    libfluidsynth3 \
    ffmpeg \
    librubberband2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the app
COPY . .

# Fetch the SoundFont at build time (not committed to the repo)
RUN bash scripts/fetch_soundfont.sh

# Render provides $PORT at runtime
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
