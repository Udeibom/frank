#!/usr/bin/env bash
#
# Downloads the SoundFont Frank's procedural music engine renders with.
# Runs locally during setup and as part of the Render build command.
# The SoundFont is not committed to the repo (it's a 14MB binary asset);
# this script makes it reproducible everywhere.

set -euo pipefail

ASSETS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets"
SF_PATH="$ASSETS_DIR/FluidR3Mono_GM.sf3"
SF_URL="https://github.com/musescore/MuseScore/raw/2.1/share/sound/FluidR3Mono_GM.sf3"

mkdir -p "$ASSETS_DIR"

if [ -f "$SF_PATH" ]; then
    echo "SoundFont already present at $SF_PATH"
    exit 0
fi

echo "Downloading FluidR3Mono_GM SoundFont..."
curl -sL -o "$SF_PATH" "$SF_URL"

# Verify it's a real SoundFont, not an HTML error page
if file "$SF_PATH" | grep -q "SoundFont"; then
    echo "SoundFont ready at $SF_PATH ($(du -h "$SF_PATH" | cut -f1))"
else
    echo "ERROR: downloaded file is not a valid SoundFont" >&2
    rm -f "$SF_PATH"
    exit 1
fi
