# Frankenstein - Requirements (spec 14)

## Introduction

Frank can measure sound but cannot recognise it, its hands play typed patterns rather than human ones, the
user's voice only ever becomes a vocal, and the user cannot point at the world ("like this song", "like this
photo"). This spec stitches in the technologies chosen in
`docs/research/FRANK-KIRO-AND-TECHNOLOGY-REVIEW.md` (Part 2) so they work as one body: every organ reports to
the shared song brief, shows where its help came from in plain words, and is versioned and undoable.

Founder decisions (19 Nov 2026):
- Any licence is acceptable as long as the Kiroween rules are not broken (third-party terms honoured, the repo
  stays open source, no copyrighted music in the video).
- Gemini may hear the user's vocals.
- The Hugging Face account is older than 30 days (ZeroGPU Spaces are allowed).
- ACE-Step gets one blind ear test (prepared now, judged by the founder later).
- No listening checkpoints during this build; the founder tests everything at the end.

Rule checks that changed the plan:
- Deezer's developer terms forbid using its content with AI, local copies, and playing audio outside its widget
  (developers.deezer.com/termsofuse, section III items 3, 4 and 8). Deezer previews are therefore NOT used.
  Reference songs come from the user's own file (analysed in memory, never stored) or from Jamendo, whose
  catalogue is Creative Commons and whose API is free for non-commercial use.
- The Gemini API terms allow only paid services when an app is available to users in the EEA, Switzerland or
  the UK. Every Gemini call (text fallback, listening, looking) is therefore skipped for requests from those
  regions.
- Research-only licences (NVIDIA Music Flamingo, MUSDB18, DEAM) are kept out of Frank.

## Requirements

### Requirement 1 - One body, not a pile of parts
#### Acceptance Criteria
1. EVERY new analysis SHALL write its result into the shared song brief, the fingerprint, or a stored
   measurement, never straight to the user.
2. EVERY new generator SHALL produce MIDI-like notes or parameters where it can; WHERE it produces audio, the
   result SHALL be one named, removable, versioned layer.
3. EVERY change made with help from a new technology SHALL carry a provenance line in plain words ("Drums: from
   a real drummer's groove"), shown on the change line, and listed on the song's credits page.
4. WHEN a remote organ (a Space or an API) is unavailable, asleep or out of quota, THE SYSTEM SHALL fall back to
   the existing CPU path or say plainly what it could not do, and never fail the user's action.

### Requirement 2 - Ears: Frank recognises what it hears
#### Acceptance Criteria
1. THE SYSTEM SHALL embed audio and text in one space (CLAP) and use it to rank Feeling directions against the
   user's own words, and to find "more like this one".
2. THE SYSTEM SHALL label style and mood of a render or reference (Discogs-EffNet models) and add a Listener
   finding when the render does not sound like the brief.
3. THE mix engineer SHALL be able to send a section bounce to Gemini with the Listener's numbers and get at most
   three plain-language notes; the Listener SHALL confirm a note before Frank acts on it.
4. THE refine loop SHALL score before and after with Audiobox Aesthetics and report whether a change helped.
5. THE SYSTEM SHALL find sections, beats and chords in audio it did not make (allin1, Chordino).
6. THE SYSTEM SHALL offer a neural pitch tracker (Basic Pitch; PESTO) beside pyin, with pyin as the fallback,
   and an automated comparison on fixed hums.

### Requirement 3 - Hands: the engine plays like people
#### Acceptance Criteria
1. Drums SHALL be able to take timing and velocity from real drummers (Groove MIDI Dataset templates), chosen
   per style and by typed operations ("looser", "tighter").
2. Chord progressions SHALL be weighted by real-song statistics per genre and section (Chordonomicon tables);
   Frank's theory code still decides.
3. Arrangement statistics (which parts play in which sections) SHALL be mined from Lakh/Slakh MIDI into the
   style tables.
4. Accompaniment SHALL be proposable as notes from the user's melody (Anticipatory Music Transformer).
5. Key instruments SHALL be able to render through recorded CC0 samples (VSCO-2 CE / VCSL with sfizz) beside
   FluidSynth.
6. "Add space" and the master SHALL be able to use free studio plugins loaded by pedalboard.
7. A short recorded atmosphere layer SHALL be addable from Freesound (CC0 / CC BY only, attributed) or Stable
   Audio 3 Small.
8. ACE-Step's add-one-part ability SHALL be prepared as a blind ear test, not shipped.

### Requirement 4 - Voice: the user's voice becomes more of the song
#### Acceptance Criteria
1. A hum or take SHALL be able to become an instrument that keeps the user's phrasing (DDSP timbre transfer).
2. A guide vocal SHALL sing the user's lyrics on the melody (DiffSinger), labelled as a guide only.
3. Takes SHALL be cleaned of background noise (DeepFilterNet) as a derived take, the original kept.
4. Takes SHALL get word timings (Groq Whisper) so a line can be redone and the Words room can follow along.
5. Frank SHALL be able to speak its notes aloud (Kokoro), off by default.

### Requirement 5 - Words: lyrics with an ear for rhythm
#### Acceptance Criteria
1. THE Words room SHALL show syllables per line, stressed syllables and rhyme families (CMU Pronouncing
   Dictionary), in a rich editor (Tiptap), in plain words.
2. THE co-writer SHALL offer near rhymes and sound-alikes (Datamuse), with the dictionary as offline fallback.
3. THE lyrics' emotional arc SHALL be read per section (GoEmotions) and offered as a shape for the song's
   energy.

### Requirement 6 - Pointing at the world
#### Acceptance Criteria
1. THE user SHALL be able to give a reference song as their own file (with a rights confirmation, analysed in
   memory, never stored) or pick one from Jamendo's Creative Commons catalogue.
2. THE reference SHALL be split into parts (BS-RoFormer) and described (CLAP, EffNet, allin1, Chordino, Basic
   Pitch) as a target fingerprint and a plain-words comparison.
3. A named song or artist SHALL be looked up (MusicBrainz, ListenBrainz) and researched (Exa, Firecrawl) into
   plain facts for the creative director, never quoted lyrics.
4. THE Finish room SHALL offer a master matched to the reference (Matchering) beside Frank's own, to compare.
5. THE Blend room SHALL offer mix settings predicted from the reference (Diff-MST), as editable parameters.
6. THE user SHALL be able to bring a photo; Frank SHALL read its mood (Gemini vision) and colours into feeling
   words and fingerprint hints.
7. THE user SHALL be able to start from "right now" (local time and weather from Open-Meteo) as feeling words.

### Requirement 7 - Memory and nervous system
#### Acceptance Criteria
1. Sound embeddings SHALL be stored in Supabase pgvector beside taste memory, textures, parts and references.
2. Job progress SHALL arrive through Supabase Realtime, with polling kept as the fallback.

### Requirement 8 - Seeing and handling the song
#### Acceptance Criteria
1. Takes, comps and mixes SHALL show waveforms with regions (WaveSurfer).
2. THE song's versions SHALL be shown as a family tree (React Flow).
3. THE Finish room SHALL offer "Download the notes" (MIDI) and a credits page (who and what made each part,
   what needs attribution).
4. THE Voice room SHALL offer a 20-second headphone check.
5. THE Blend room SHALL offer an optional "conduct" mode: a raised or lowered hand seen by the camera
   (MediaPipe, in the browser, no audio processed) shapes a part's level.

### Requirement 9 - Rules and data
#### Acceptance Criteria
1. Gemini SHALL be skipped for requests from the EEA, Switzerland or the UK, and the user SHALL be told once
   that short clips are sent to Google to listen.
2. `THIRD_PARTY.md` SHALL list every model, dataset, API and library added, with licence, attribution and use.
3. Public datasets SHALL be mined offline into small committed JSON tables; no dataset is downloaded at request
   time.
4. Song Describer captions SHALL calibrate the words-to-fingerprint mapping with CLAP.
5. MTG-Jamendo mood labels SHALL check that mood words land near music with that mood.
