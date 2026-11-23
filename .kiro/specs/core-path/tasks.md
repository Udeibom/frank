# Core Path — Tasks (spec 15)

Ticked only with evidence. Order agreed with the founder (23 Nov): steps 1 to 7.

## Step 1. Nothing crashes
- [ ] 1. Migration 012: job payload, claim, heartbeats, `job-inputs` bucket
  - _Requirements: 1.2, 1.4_
- [ ] 2. `dispatch.py`; every router uses it (bytes staged in storage)
  - _Requirements: 1.1, 1.3_
- [ ] 3. Worker on the frank-ears Space (own env, system libraries, assets, secrets); memory limit measured
  - _Requirements: 1.1_
- [ ] 4. Restart sweep and stale check respect claimed jobs
  - _Requirements: 1.4_
- [ ] 5. Queue position shown to the person
  - _Requirements: 1.2_

## Step 2. Speed
- [ ] 6. Hum speed: no double or half reading; consistent hums win; feeling decides between candidates
  - _Requirements: 2.1_
- [ ] 7. `slower` / `faster` operations that change the beat's speed
  - _Requirements: 2.2_
- [ ] 8. Reply claim check: Frank never says it did what it didn't
  - _Requirements: 2.3_

## Step 3. Length
- [ ] 9. New beat at least as long as the recording; mix never leaves the voice alone
  - _Requirements: 3.1, 3.2_

## Step 4. Directions
- [ ] 10. "Try something different" moves the sound on purpose; no stored copy of a heard direction
  - _Requirements: 4.1_

## Step 5. Words and next step
- [ ] 11. One next step per room; plain labels in Voice and Blend
  - _Requirements: 5.1, 5.2_

## Step 6. Honest status
- [ ] 12. Waking banner clears when the server answers
  - _Requirements: 6.1_
- [ ] 13. Reactions are never saved as the song's description
  - _Requirements: 6.2_

## Step 7. Proof
- [ ] 14. Live run of the founder's path, recorded in `docs/demo-runs/`
  - _Requirements: 7.1_
