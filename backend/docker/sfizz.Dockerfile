# Builds sfizz_render (BSD-2) for Frank's recorded instruments (frankenstein spec 14, requirement 3.5).
# Used as a stage of backend/Dockerfile; kept separate so it can be built and tested on its own:
#   docker build -f backend/docker/sfizz.Dockerfile -t frank-sfizz backend
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
