#!/usr/bin/env bash
# Recorded CC0 instruments for Frank's engine (frankenstein spec 14, requirement 3.5): Versilian Studios VSCO-2 CE
# (public domain, CC0). Only the instruments Frank uses: an upright piano for "keys" and a violin section for
# "strings". Fetched at Docker build time and during local setup; never committed (about 250 MB).
#   bash scripts/fetch_samples.sh [DEST]      # default backend/assets/sfz
set -euo pipefail
DEST="${1:-$(cd "$(dirname "$0")/.." && pwd)/assets/sfz}"
if [ -f "$DEST/VSUpright1.sfz" ] && [ -f "$DEST/ViolinEnsSusVib.sfz" ]; then
  echo "samples already in $DEST"; exit 0
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --quiet --depth 1 --branch SFZ --filter=blob:none --sparse https://github.com/sgossner/VSCO-2-CE.git "$TMP/vsco"
cd "$TMP/vsco"
git sparse-checkout set --no-cone "/VSUpright1.sfz" "/ViolinEnsSusVib.sfz" "/LICENSE" "/Keys/Upright Nr1/" "/Strings/Violin Section/susVib/"
mkdir -p "$DEST"
cp -r VSUpright1.sfz ViolinEnsSusVib.sfz LICENSE Keys Strings "$DEST/"
# sfz files from Windows use backslashes in paths; make them portable.
sed -i 's#\\#/#g' "$DEST/VSUpright1.sfz" "$DEST/ViolinEnsSusVib.sfz"
du -sh "$DEST"
