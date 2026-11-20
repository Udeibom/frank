---
name: producer-craft
description: What working producers, mixers and songwriters say about making songs, and what Frank does with each lesson (chorus lift, vocal placement, the no 'sounds like' rule, arrangement moves). Use when changing the engine, the Listener's thresholds, the refine loop's experiments, or the creative director.
---

# Producer craft: what working producers say, and what Frank does with it

Why this exists: the founder is not a producer and does not want Frank's questions to rest on an
assumption. Before Frank's conversation design (specs 07, 08, 10) hardens, this records what working
producers and songwriters actually say, with the source, so a design choice can point at evidence.

Written Nov 13. Status: research notes, not requirements. Only the items marked BUILT are in the code.

## What I could and could not get

I READ these in full or in the relevant part:
- Rick Rubin, CBS *60 Minutes* interview transcript (Anderson Cooper, May 2023). Primary source.
- Dan Wilson and Teddy Geiger on the *Switched on Pop* podcast, "5 rules of great songwriting collabs"
  (transcript excerpts, High Road Touring / Vulture).
- Jack Antonoff, GRAMMY.com interview (2024).

I could only see the OPENING of these (the rest is behind a paywall): Tape Op interviews with Finneas
(Billie Eilish's producer) and Greg Kurstin (Adele, Sia). One Antonoff line below comes from a search
snippet of a fan repost; I did not check it against the original, so treat it as unverified.

I did NOT find a list of the exact questions top producers ask. Interviews describe a way of listening
and a few rules, not a script. Blog posts and Q&A sites that offer question lists were low quality and
are not used here. So this note gives principles, not a question bank, and the wording of Frank's
questions is still ours to test with real users.

## What they say

1. **Listen to the feeling, not the parts.** Rubin, asked what he is listening for in a room full of
   instruments: "I'm not listening to any of those things... I'm listening to the feeling." He also says
   he knows nothing technical and that his value is knowing what he likes and saying what he feels.
2. **Don't push your presence.** Rubin: "My aim is not to have my presence felt. Unless it's necessary,
   unless it's helpful." Wilson and Geiger: resist over-explaining, keep theory to a minimum, because
   explaining pulls the writer away from the song.
3. **Don't say no before you have heard it.** Wilson's first rule: don't reject an idea until you have
   heard it; if the people you work with are feeling something real, follow that.
4. **Help the artist look inside, don't tell them the answer.** Rubin says he is "giving cues to look for
   in yourself because it all has to do with the artist." Kesha, on his homework: write a full essay about
   everything you need to say until you can't write any more; then "the song kinda started forming itself".
5. **Follow what feels exciting.** Antonoff: there is a lot of moving instruments, lyrics and thoughts
   around with no direction "until one thing feels exciting, and then you follow that thing." He also says
   he does not sit and think about genre or who a song will satisfy.
6. **The audience comes last.** Rubin: "the audience doesn't know what they want."
7. **Take things away.** Rubin calls himself a reducer: get the point across with the least information,
   find what is actually necessary. Finneas (opening of his Tape Op interview) clears space around Billie
   Eilish's voice by putting less in. Kurstin (opening of his): on the other side of the glass his job is to
   help artists with their vision.
8. **A song can hold everything.** Unverified repost of Antonoff: a song "should have the whole gamut of
   what it actually is like for the artist to be alive at that moment."

## What this changes in Frank

BUILT (Nov 13):
- **Frank no longer forces an either-or.** The founder's lyric holds anger and sorrow together, and Frank
  asked "more defiant anger or deep sorrow?" That is a false choice (see 8). Now anger and sorrow both count
  as one dark mood, so a song that moves between them is not "unsure", and Frank stays quiet. When the song
  truly holds a dark and a warm feeling, Frank asks "which should the music lean into most, or should it
  hold both?" and the "or both" is added by code, not left to the model.
- **One question, only when it would change the music** (points 2 and 5), never a list.
- **The question uses the song's own feelings** ("the dark humor or the gentle remembrance"), not generic
  "sad or hopeful" (points 1 and 4).

CANDIDATES, not built, each with the point behind it. They go to the founder before any code:
- **An open invitation next to the question** (4): "Want to tell me what this song is about, in your own
  words? As much as you like." For people who have a lot to say and no words for the music.
- **Show, don't argue** (3): when the person doubts a suggestion, Frank plays the alternative instead of
  explaining why it is better. Already the plan for spec 08; this is evidence for it.
- **Take away before adding** (7): the engine (spec 04) should get richer through variation and good
  parts, not through piling on layers. This sits beside the founder's request for less "basic" music: more
  craft, not more clutter.
- **Don't ask for genres or "who is this for?"** (5, 6). Frank already avoids tempo, key and genre.

## DECIDED (founder, Nov 13): no "sounds like" game

The Creative Director (frank-team.md, decision 3) would research what a named artist sounds like.
Dan Wilson and Teddy Geiger say the "sounds like" game is irrelevant and can be a trap ("I don't want to
just make another one of those"); Wilson's view is that you do best by sounding like yourself. Other
sources I only saw in snippets treat reference tracks as normal in pre-production, so the evidence is
mixed. The founder's decision: follow what the proven producers say. So:
- Frank does NOT research or imitate what a named artist sounds like, and does not steer anyone toward
  "sounding like" someone. The Creative Director is not a "who do you sound like" role.
- If the person names an artist anyway, Frank does not ignore it or lecture. It turns the name into a
  FEELING in the person's own terms (close, hushed, wide, raw) by asking what they love about it, builds
  from that feeling, and moves on. The artist's sound is never copied.
- The Creative Director's job is to protect the person's own identity: what is distinctively theirs in
  their words, their voice and their choices, and to say so when a direction drifts from it.
- This amends decision 3 in `frank-team.md` (which says the Creative Director may search the web for what
  an artist sounds like). That file was open in the founder's editor when this was decided, so its wording
  has NOT been changed yet; this section is the current rule until the founder updates that file.

## Sources

- CBS News, "In Shangri-La with music producer Rick Rubin", 60 Minutes, May 28, 2023.
- High Road Touring, "5 Rules of Great Songwriting Collabs, According to Teddy Geiger and Semisonic's Dan
  Wilson" (from Vulture / Switched on Pop), 2021.
- GRAMMY.com, Jack Antonoff interview on working with Taylor Swift, Sabrina Carpenter and Bleachers, 2024.
- Tape Op, interviews with Finneas O'Connell (issue 165) and Greg Kurstin (issue 135): openings only.
