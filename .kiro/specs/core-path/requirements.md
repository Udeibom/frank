# Core Path — Requirements (spec 15)

## Introduction
On 22 Nov the founder used Frank end to end as a real user: a slow worship song, five hums, a 4-minute take.
Frank failed the promise. The server ran out of memory four times, so mixes, listening and atmosphere never
finished. The song was set to double its real speed, and the Music room had no way to slow it, though the
chat said it had. "Try something different" replayed the same sound. A 90-second beat ended under a 4-minute
voice. The rooms did not say what to do next.

This spec stops new features and makes the main path work for a person with no music knowledge: hum or
describe, get music at the right speed, sing over it, hear them together, finish. Order agreed with the
founder: the seven steps below, in this order.

## Requirements

### Requirement 1 - Nothing crashes on real-length material
1. Heavy sound work (analysing takes, beats, mixes, listening, finishing, atmosphere, references) SHALL run in
   a worker with enough memory (16 GB or more on Frank's existing Hugging Face Space), not on the 512 MB API.
2. Jobs SHALL wait in a queue in the database. The person SHALL see that they are waiting, not a crash.
3. IF the worker is asleep or down THEN the API SHALL wake it and SHALL run the job itself, one at a time.
4. A restart of the API SHALL NOT fail jobs the worker is doing. A restart of the worker SHALL fail only its
   own jobs, plainly.
5. A 4-minute take SHALL be analysed, mixed, listened to and finished without failure (live check).

### Requirement 2 - Speed the person controls
1. A hummed speed SHALL NOT be read as double (or half) its real speed. When hums disagree, Frank SHALL
   choose a speed that fits the feeling, and a slow, gentle feeling SHALL never get a driving speed.
2. The Music room SHALL have "slower" and "faster" changes that really change the speed of the beat.
3. Frank SHALL never say it changed something it did not change. A claim in a reply SHALL match the changes
   actually made, or the reply SHALL be replaced with what was really done.

### Requirement 3 - The beat fits the singing
1. WHEN a recording exists THEN a new beat SHALL be built at least as long as the recording.
2. A mix SHALL never leave the voice alone after the music ends: the music is lengthened (or ends with it).

### Requirement 4 - Directions that differ
1. "Try something different" SHALL produce a direction that sounds clearly different from every direction
   already offered (different sound, movement or energy), never a stored copy of one already heard.

### Requirement 5 - Plain words and one next step
1. Every room SHALL show one clear next step for where the song is now.
2. Labels SHALL be plain: "recording" not "take", and plain names for best-of and voice tools, each with a
   one-line explanation. Tools that need something first (two recordings) SHALL say so instead of appearing
   ready.

### Requirement 6 - Honest status
1. "Frank is waking up" SHALL only show while the server is actually not answering, and SHALL go away when it
   answers.
2. A reaction ("that one isn't quite it") SHALL NOT be saved as the song's description.

### Requirement 7 - Tested the way the founder used it
1. A live run on the deployed site SHALL cover: a slow song from a hum, "make it slower", a 4-minute
   recording, the mix, listening, atmosphere and finish, and SHALL be recorded in `docs/demo-runs/`.
