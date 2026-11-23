# Music that plays to the singer, live

Run 2026-11-23 against https://frank-api-pzjo.onrender.com from a Kaggle kernel, fresh account deleted afterwards.
Script: `backend/scripts/ops/e2e_follow.py`. Result: **9 of 9 PASS**. The core path (`e2e_core.py`) was run again
after this change: still 16 of 16.

A song was sung with no music under it: verse, chorus, verse, chorus, at 69 beats a minute, first bar line 3.1 s
into the recording, the chorus higher than the verse and coming back. Frank had first built music from the feeling
at 96. After the recording was checked, Frank built new music around the singing by itself:

| What a pianist would do | What was sung | What Frank built |
|---|---|---|
| play at the singer's speed | 69 | 69.0 |
| put the bar lines where theirs fall | 3.10 s | 3.12 s |
| change where they change | verse 3.1, chorus 30.9, verse 58.8, chorus 86.6 s | verse 3.12, chorus 30.95, verse 58.77, chorus 86.6 s, ending 114.4 s |
| leave the tune to them | | no tune part anywhere |
| finish with them | last note about 117 s | blend 123 s: two bars that settle home |
| keep what was there | | the music from the feeling kept as Beat v1 |
| not fight their speed | "slower" | refused: "This music follows your singing, so its speed is your speed..." |

Found by this run and fixed before the second pass: the length check measured the music from 0 s instead of where
it starts in the recording, and added a verse the singing did not have (property
`test_music_built_from_the_singing_is_never_lengthened_again_before_a_blend`).

## Not covered
- A real person's singing: the song here is made of clean held notes. Real voices drift, slide and breathe; the
  speed and sections are found from where notes start, which real singing gives less cleanly.
- Words: Whisper heard nothing in the made-up voice, so sections were found from the melody. With real lyrics they
  are placed by when each line was sung.
- Nobody listened. About 70% of what was sung sits inside the chord under it in the audio check
  (`scripts/follow_check.py`); the founder judges whether the chords feel right.
