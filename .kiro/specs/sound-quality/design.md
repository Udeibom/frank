# Sound Quality - Design
## Overview
No new component was designed by this spec. It records how the spike was run, what code changed as a
result, and what is still open. The sound source sits behind the renderer contract in spec 04, so a
change of sample set touched configuration only.
```
Score (spec 04) -> Renderer (FluidSynth + sample set) -> per-part audio -> polish chain (optional) -> mix
```
## The spike
- Sample sets: renders in `sf-spike/`, loudness-matched blind set in `blind-soundfonts/` (3 versions per
  song, shuffled; seed 20251115; `ANSWER_KEY.txt` lists the mapping and the measured LUFS). Founder
  answers are written in `blind-soundfonts/LISTEN_FIRST.md`.
- Neural test: `scratch/kjob/run.py` (MusicGen-melody, fp16, guidance 3, 1000 tokens) with
  `kernel-metadata.json`; Kaggle log in `scratch/kout/frank-neural-spike.log` (T4; 35.4 s and 29.9 s for
  19.94 s of audio). Chord match from `scratch/chroma_check.py`. Founder answers in
  `neural-spike/LISTEN_FIRST.md`.
- Mixing chain: `blind-polish/` (pair 1 control, pairs 2 and 3 real), answers in its `LISTEN_FIRST.md`.
  Measurement notes below.
## Decisions in code
- `backend/app/config.py` `soundfont_path` = `assets/MuseScore_General.sf3`.
- `backend/scripts/fetch_soundfont.sh` downloads that file; `backend/Dockerfile` runs it at build.
- `backend/app/services/generation/polish.py`; `beat.render_song(..., mix_chain=True)` is the default.
## Open
- Mixing chain: keep, make optional, or drop. Options: (1) keep on, accepting +20 s per 185 s song for
  a measurable but unheard change; (2) off by default with a switch; (3) remove the code. A fairer
  test would use more pairs and repeat the control; the founder noted possible bias in his own listening.
## Caveats on the numbers
- "Tempo preserved": the beat tracker read 70 BPM for both neural clips and 136 for the original, which
  is a half-time reading of the same pulse, not a drift.
- The +12 MB, +2 s, +8 dB and +20 s figures are reported by the founder's session, not re-measured here.
## Correctness properties (PBT)
Existing tests for the chain (spec 04 file): length and finiteness kept, aliases valid, panning never
louder, chain changes sound but not timing, every part goes through the chain only when it is on.
No property test covers the choice of sample set.
