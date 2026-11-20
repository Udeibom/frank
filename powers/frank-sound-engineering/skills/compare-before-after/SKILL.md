---
name: compare-before-after
description: Compare two renders of the same music (before and after a code change) with Frank's Listener and report what changed in plain words with numbers. Use when a change is meant to alter the sound, to prove it did what was intended and nothing else.
---
# Compare before and after

1. Render the same song with the same seed before and after the change (stash or check out the old code for the
   before render; never compare two different seeds).
2. Call `compare_files(before, after, kind)`.
3. Check the intended change appears (for example "the chorus is 2.1 loudness units louder than the verse, up from
   0.8") and that nothing else moved by more than the tool's noise (loudness 0.5 LU, brightness 5 %).
4. Report: what was meant to change, what did, and anything that changed that should not have.
5. Match loudness before anyone listens: the louder version always sounds better.
