#!/usr/bin/env bash
# Recorded CC0 instruments for Frank's engine (frankenstein spec 14, requirement 3.5): Versilian Studios VSCO-2 CE
# (public domain, CC0). The subset Frank plays: piano, strings, bass, harp, woodwinds and brass. Fetched at Docker
# build time and during local setup; never committed (a few hundred MB).
#   bash scripts/fetch_samples.sh [DEST]      # default backend/assets/sfz
set -euo pipefail
DEST="${1:-$(cd "$(dirname "$0")/.." && pwd)/assets/sfz}"
if [ -f "$DEST/VSUpright1.sfz" ] && [ -f "$DEST/Harp.sfz" ] && [ -f "$DEST/FluteSusVib.sfz" ]; then
  echo "samples already in $DEST"; exit 0
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --quiet --depth 1 --branch SFZ --filter=blob:none --sparse https://github.com/sgossner/VSCO-2-CE.git "$TMP/vsco"
cd "$TMP/vsco"
git sparse-checkout set --no-cone \
  "/LICENSE" "/README.md" \
  "/VSUpright1.sfz" "/UprightPiano.sfz" "/Harp.sfz" "/Glockenspiel.sfz" "/Marimba.sfz" "/Xylophone.sfz" \
  "/ViolinEnsSusVib.sfz" "/ViolinEnsSusVib-Quiet.sfz" "/ViolaEnsSusVib.sfz" "/ViolaEnsSusVib-Quiet.sfz" \
  "/CelloEnsSusVib.sfz" "/ContrabassSusVB.sfz" "/FluteSusVib.sfz" "/OboeSusVib.sfz" \
  "/ClarinetSus.sfz" "/BassoonSus.sfz" "/TrumpetSus.sfz" "/FHornSus.sfz" "/TromboneSus.sfz" "/TubaSus.sfz" \
  "/Keys/Upright Nr1/" "/Keys/Upright Piano/" "/Keys/Organ/Loud/" "/Keys/Organ/Quiet/" \
  "/Strings/Violin Section/susVib/" "/Strings/Viola Section/susvib/" "/Strings/Cello Section/susvib/" \
  "/Strings/Solo Contrabass/SusVib/" "/Strings/Harp/" \
  "/Woodwinds/Flute/susvib/" "/Woodwinds/Oboe/Vib/" "/Woodwinds/Clarinet/susLong/" "/Woodwinds/Bassoon/sus/" \
  "/Brass/Trumpet/sus/" "/Brass/F Horn/sus/" "/Brass/Tenor Trombone/sus/" "/Brass/Tuba/sus/"
mkdir -p "$DEST"
cp -r VSUpright1.sfz UprightPiano.sfz Harp.sfz Glockenspiel.sfz Marimba.sfz Xylophone.sfz LICENSE "$DEST/"
cp -r ViolinEnsSusVib.sfz ViolinEnsSusVib-Quiet.sfz ViolaEnsSusVib.sfz ViolaEnsSusVib-Quiet.sfz \
  CelloEnsSusVib.sfz ContrabassSusVB.sfz FluteSusVib.sfz OboeSusVib.sfz ClarinetSus.sfz BassoonSus.sfz \
  TrumpetSus.sfz FHornSus.sfz TromboneSus.sfz TubaSus.sfz "$DEST/"
cp -r Keys Strings Woodwinds Brass "$DEST/"
# sfz files from Windows use backslashes in paths; make them portable.
for f in "$DEST"/*.sfz; do sed -i 's#\\#/#g' "$f"; done
du -sh "$DEST"
