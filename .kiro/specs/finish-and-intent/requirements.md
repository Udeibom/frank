# Finish and Intent - Requirements (spec 11)

## Introduction
"Finished" means the person's intent is met, and the person decides (founder decision 8). Today the Mix Room
treats the whole beat as one block (only the vocal, the beat and the harmony have levels), mastering can run on
anything, nothing asks whether the song matches what the person first described, and there is no surprise
version. This spec gives the mix real parts, a finishing step worthy of sharing, the intent check, one optional
surprise, and the export.
Depends on song-engine task 5.4 (stored stems). Traces to Mix engineer, Mastering engineer, decisions 8 and 9.

## Requirements

### Requirement 1 - Mix every part
#### Acceptance Criteria
1. THE Mix Room SHALL mix the beat's parts separately (drums, bass, keys, melody, pad and the extras), plus the
   lead vocal and the harmony, each with level, tone ("warmer", "brighter", "clearer") and space, per section
   when asked ("bring the piano down in the bridge").
2. THE mix conversation SHALL make at most three changes per reply and say what it did.
3. THE stem balance view SHALL show every part, in plain names ("Drums", "Bass", "Piano").
4. Older beats without stored parts SHALL still mix as one block, and the Mix Room SHALL offer to rebuild the
   parts from the saved plan.

### Requirement 2 - Finishing worthy of sharing
#### Acceptance Criteria
1. THE finishing step SHALL bring the song to a streaming loudness (about -14 on the loudness scale used by
   streaming services) without audible pumping or clipping, measured by the Listener.
2. THE finishing step SHALL refuse to start from a low-quality preview and SHALL render the mix at full quality
   first (two-pass loudness, true 320 kbps from an uncompressed source; export-room task 7.2).
3. THE person SHALL hear before/after and choose.

### Requirement 3 - Does it match what you described?
#### Acceptance Criteria
1. THE SYSTEM SHALL keep the person's own first description of the song as the intent statement.
2. BEFORE the first export THE SYSTEM SHALL play the song and ask, in their words, whether it matches ("You said
   'standing alone in the rain after losing someone'. Does this feel like that?").
3. IF the answer is no THE SYSTEM SHALL go to the refine loop (spec 08) with the answer as the concern; IF yes
   it SHALL mark the song finished (status `exported` after export) and record the decision.

### Requirement 4 - One surprise, never a replacement
#### Acceptance Criteria
1. AFTER the person's version is complete THE SYSTEM MAY offer ONE unexpected alternative ("Before we finish, I
   tried one idea"), built as an extra version that differs in one bold way (a stripped-down version, a
   different feel), never replacing the active version.
2. THE offer SHALL happen at most once per song and SHALL be easy to skip.

### Requirement 5 - Export
#### Acceptance Criteria
1. THE person SHALL download the finished song as a high-quality MP3, and also separate parts ("Download
   separate parts") as a zip of per-part files.
2. THE final-listen screen SHALL show the waveform (export-room task 7.1).
