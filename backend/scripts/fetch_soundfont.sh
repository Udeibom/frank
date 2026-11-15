#!/usr/bin/env bash
#
# Downloads the SoundFont Frank's procedural music engine renders with.
# Runs locally during setup and as part of the Docker build.
# The SoundFont is not committed to the repo (it's a 40MB binary asset);
# this script makes it reproducible everywhere.
set -euo pipefail
ASSETS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets"
SF_PATH="$ASSETS_DIR/MuseScore_General.sf3"
SF_URL="https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf3"
MIN_BYTES=20000000

mkdir -p "$ASSETS_DIR"

# A SoundFont file starts with the letters RIFF and has "sfbk" at byte 8. Checked with head and
# tr, which every image has (the `file` command is not in the slim Python image).
is_soundfont() {
    [ -f "$1" ] \
        && [ "$(stat -c %s "$1")" -ge "$MIN_BYTES" ] \
        && [ "$(head -c 4 "$1")" = "RIFF" ] \
        && [ "$(head -c 12 "$1" | tail -c 4)" = "sfbk" ]
}

if is_soundfont "$SF_PATH"; then
    echo "SoundFont already present at $SF_PATH"
    exit 0
fi

echo "Downloading MuseScore General SoundFont (MIT licence)..."
PART="$SF_PATH.part"
rm -f "$PART" "$SF_PATH"
# -f fails on an error page, --retry covers a flaky connection. The file only gets its real name
# after it has been checked, so a half-finished download is never mistaken for a good one.
curl -fsSL --retry 3 --connect-timeout 20 --max-time 600 -o "$PART" "$SF_URL"

if is_soundfont "$PART"; then
    mv "$PART" "$SF_PATH"
    echo "SoundFont ready at $SF_PATH ($(du -h "$SF_PATH" | cut -f1))"
else
    echo "ERROR: downloaded file is not a valid SoundFont" >&2
    rm -f "$PART"
    exit 1
fi
