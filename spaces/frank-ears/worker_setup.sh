#!/usr/bin/env bash
# Frank's job worker on this Space (core-path spec 15, requirement 1): the backend's own code in its own
# environment, with the same Python (3.12), libraries, sounds and plugins as the Render server, so a job sounds
# the same wherever it runs. Run by app.py in the background at start-up; the worker only starts (and only
# tells the API it is there) after everything here has finished.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$HERE/worker"                       # backend code, uploaded by tools/spaces/deploy.py ears
BASE="${FRANK_WORKER_HOME:-/tmp/frank-worker}"
mkdir -p "$BASE" "$HOME/.vst3" "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"

# Python 3.12 and the backend's requirements (uv fetches a standalone Python; no root needed)
if [ ! -x "$BASE/env/bin/python" ]; then
  python -m uv venv --python 3.12 "$BASE/env"
fi
python -m uv pip install -q --python "$BASE/env/bin/python" -r "$W/requirements.txt"
python -m uv pip install -q --python "$BASE/env/bin/python" --no-deps basic-pitch==0.4.0

# Studio reverbs: Dragonfly's official Linux build (GPL-3.0); bookworm has no VST3 package for it
if [ ! -d "$HOME/.vst3/DragonflyPlateReverb.vst3" ]; then
  curl -fsSL -o "$BASE/df.tar.xz" https://github.com/michaelwillis/dragonfly-reverb/releases/download/3.2.10/dragonfly-reverb-3.2.10-linux-x86_64.tar.xz
  tar -xJf "$BASE/df.tar.xz" -C "$BASE"
  find "$BASE" -maxdepth 3 -name "Dragonfly*.vst3" -type d -exec cp -r {} "$HOME/.vst3/" \;
fi

# The program that plays the recorded piano and strings (same version as the Render image)
if [ ! -x "$HOME/.local/bin/sfizz_render" ]; then
  rm -rf "$BASE/sfizz"
  git clone -q --depth 1 --branch 1.2.3 --recurse-submodules --shallow-submodules https://github.com/sfztools/sfizz.git "$BASE/sfizz"
  cmake -S "$BASE/sfizz" -B "$BASE/sfizz/build" -DCMAKE_BUILD_TYPE=Release \
    -DSFIZZ_JACK=OFF -DSFIZZ_RENDER=ON -DSFIZZ_LV2=OFF -DSFIZZ_LV2_UI=OFF -DSFIZZ_VST=OFF -DSFIZZ_AU=OFF \
    -DSFIZZ_SHARED=OFF -DSFIZZ_TESTS=OFF -DSFIZZ_BENCHMARKS=OFF -DSFIZZ_DEMOS=OFF -DSFIZZ_DEVTOOLS=OFF \
    -DSFIZZ_USE_SNDFILE=ON > "$BASE/sfizz-cmake.log"
  cmake --build "$BASE/sfizz/build" --target sfizz_render -j"$(nproc)" > "$BASE/sfizz-build.log"
  find "$BASE/sfizz/build" -name sfizz_render -type f -exec cp {} "$HOME/.local/bin/sfizz_render" \;
fi

# Sounds and the words index, inside the backend folder where the code expects them
cd "$W"
[ -f assets/MuseScore_General.sf3 ] || bash scripts/fetch_soundfont.sh
[ -f assets/sfz/Harp.sfz ] || bash scripts/fetch_samples.sh "$W/assets/sfz"
[ -f assets/words.sqlite ] || PYTHONPATH="$W" "$BASE/env/bin/python" scripts/build_words_db.py
echo "worker setup complete"
