# Stage 1: sfizz_render for the recorded instruments (frankenstein spec 14); see docker/sfizz.Dockerfile
FROM python:3.12-slim AS sfizz
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates libsndfile1-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
ARG SFIZZ_REF=1.2.3
RUN git clone --depth 1 --branch ${SFIZZ_REF} --recurse-submodules --shallow-submodules https://github.com/sfztools/sfizz.git /src/sfizz
RUN cmake -S /src/sfizz -B /src/build -DCMAKE_BUILD_TYPE=Release \
        -DSFIZZ_JACK=OFF -DSFIZZ_RENDER=ON -DSFIZZ_LV2=OFF -DSFIZZ_LV2_UI=OFF -DSFIZZ_VST=OFF -DSFIZZ_AU=OFF \
        -DSFIZZ_SHARED=OFF -DSFIZZ_TESTS=OFF -DSFIZZ_BENCHMARKS=OFF -DSFIZZ_DEMOS=OFF -DSFIZZ_DEVTOOLS=OFF \
        -DSFIZZ_USE_SNDFILE=ON \
    && cmake --build /src/build --target sfizz_render -j"$(nproc)" \
    && find /src/build -name sfizz_render -type f -exec cp {} /usr/local/bin/sfizz_render \; \
    && /usr/local/bin/sfizz_render --help | head -3

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
    git \
    libsndfile1 \
    dragonfly-reverb-vst3 \
    lsp-plugins-vst3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Memory on the 512 MB free server (ship-it spec 13): a warm, CPU-independent numba cache baked into the image,
# and fewer malloc arenas so worker threads don't each keep their own heap.
ENV NUMBA_CACHE_DIR=/app/.numba_cache \
    NUMBA_CPU_NAME=generic \
    MALLOC_ARENA_MAX=2

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps basic-pitch==0.4.0

# Copy the app
COPY . .

# Fetch the SoundFont at build time (not committed to the repo)
RUN bash scripts/fetch_soundfont.sh
# Recorded CC0 piano and strings (VSCO-2 CE) and the program that plays them
COPY --from=sfizz /usr/local/bin/sfizz_render /usr/local/bin/sfizz_render
RUN bash scripts/fetch_samples.sh /app/assets/sfz
# The pronouncing dictionary as an on-disk index, so lyrics analysis costs no memory (frankenstein spec 14)
RUN PYTHONPATH=/app python scripts/build_words_db.py
# Compile librosa's numba code now, not on the first request
RUN PYTHONPATH=/app python scripts/warm_numba.py

# Render provides $PORT at runtime
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
