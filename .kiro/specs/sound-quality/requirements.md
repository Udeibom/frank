# Sound Quality - Requirements
## Introduction
This spec records the sound-quality spike (roadmap spec 05) and what it decided. It holds evidence only:
what was rendered, what the founder heard, what was measured, and what is still open. Listening files are
in `/home/caleb/frank-listening/` (outside the repo; audio never lives in the repo).
It sits under spec 04 (song-engine): the engine writes a Score, and this spec covers how the Score
sounds. The founder's earlier finding, before the spike: the main complaint was the arrangement (same
instruments throughout, layers only added, no ending), not the sample set. Spec 04's moments layer
addresses that; see Requirement 4.
## Requirements
### Requirement 1 - The default sample set is chosen by blind listening
**User Story:** As the founder, I want the sound source picked by ear, not by reputation.
#### Acceptance Criteria
1. THE spike SHALL render identical notes for two songs ("sad slow soul", "angry driving") with the
   previous set (FluidR3Mono), GeneralUser GS and MuseScore General, at matched loudness, with a
   shuffled answer key.
2. THE founder SHALL rank them blind. Result: song A best to worst = GeneralUser, MuseScore, previous.
   Song B = MuseScore, previous, GeneralUser.
3. THE SYSTEM SHALL default to MuseScore General: no set won both songs, and MuseScore was the
   most consistent (2nd and 1st). It is MIT licensed. Reported cost against the old set: about +12 MB
   memory and about +2 s render time.
### Requirement 2 - A neural "make it sound real" step is not adopted for now
#### Acceptance Criteria
1. THE spike SHALL re-voice a 20 s chorus of Frank's own render with MusicGen-melody on a free Kaggle T4
   GPU and compare it with the original.
2. Measured: about 30-35 s of GPU time per 20 s of audio; frame-by-frame chord match to the original
   0.55 and 0.63 against 0.08 for a control (same music 4 s off); tempo preserved.
3. The founder preferred Frank's own render on every question and said the neural clips were worse.
4. THE SYSTEM SHALL NOT add a neural polish step now. The Kaggle job SHALL stay reproducible so the
   question can be reopened.
5. A commercial licence for the neural model is explicitly deferred by the founder and is not decided here.
### Requirement 3 - The mixing chain's value is an open decision
#### Acceptance Criteria
1. THE spike SHALL compare the chain (`polish.py`: per-part tone, smoothing, space, position, then a
   light glue pass and ceiling) with the plain render in blind pairs, loudness matched, with a
   no-change control (the same file as A and B).
2. Result: the founder heard no difference in the two real pairs, and leaned to one side (B) in the
   identical-files control. So an effect of the chain on perceived quality is NOT shown.
3. Measured effect: about +8 dB louder at equal peak and about +20 s extra render time on a 185 s song.
4. THE decision (keep it on, make it optional, or drop it) is OPEN and belongs to the founder. Until it
   is made, the chain stays on by default in code (`mix_chain=True`).
### Requirement 4 - The arrangement is the main complaint, and its fix is not yet heard
#### Acceptance Criteria
1. The founder's earlier finding: the songs used the same instruments throughout, layers were only
   added, and there was no ending.
2. Spec 04's moments layer (late entries, dropouts, risers, stops, answers, one-time sound, a real
   ending) addresses it.
3. The founder's answer to the v3 blind test (`blind-engine-v3/`) is still unanswered. Nothing here
   claims that the arrangement problem is solved.
