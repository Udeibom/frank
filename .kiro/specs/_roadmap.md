# Frank — Spec Roadmap (the map of everything)

Source of truth for the vision: `.kiro/skills/frank-team/SKILL.md`. This file is the index that keeps
every spec in view. Update the Status column whenever a spec moves. A spec is only "Done" when its
tasks are checked AND the founder has listened to or used the result.

Status key: OUTLINE (intent captured) / SPEC (requirements+design+tasks written) / BUILDING / DONE

## The specs

| # | Spec | What it gives Frank | Depends on | Status |
|---|------|---------------------|------------|--------|
| 01 | song-record | One living record of the song that every room and role reads; versions with parents; decisions log; creating/refining phase; intent statement | existing DB | BUILDING |
| 02 | start-from-any-input | Lyrics, hum, tapped rhythm, voice memo or description all fill the record; no "voice first/beat first" | 01 | BUILDING |
| 03 | listener | The team's ears: per-section and per-part measurements reported as plain facts | 01 | BUILDING |
| 04 | song-engine | The team's hands for music: arrangement depth, transitions, real stems, seeded variation, melody that follows chords, every fingerprint field wired | 01, 02 | BUILDING |
| 05 | sound-quality | Release-grade sound: spike comparing better SoundFonts + mixing chain vs hosted neural; decision recorded, then built | 04 | BUILDING |
| 06 | sing-it | The user sings: guide melody they follow, beat alignment, tuning to the song's key per note, bleed removal, comping, harmony | 02, 04 | BUILT |
| 07 | team-conversation | Shared brief in every call, role routing, several LLM providers, bounded specialist disagreement, occasional role mentions, review-vs-creating behaviour, plain-language enforcement | 01, 03 | BUILDING |
| 08 | refine-loop | Diagnose with evidence, offer 2-3 directions, preview each, commit; experiments when nobody knows; branches; "give me the second version back" | 03, 04, 07 | BUILT |
| 09 | taste-memory | Per-artist taste profile with notes per specialist; repeated-evidence rule; view/edit/forget | 01, 07 | BUILT |
| 10 | creative-director | Protects the person's own identity. NOT a "sounds like" role: no researching or imitating named artists; a named artist is turned into a feeling in the person's own words (decided Nov 13, see producer-craft.md). Identity brief | 01, 07 | BUILT |
| 11 | finish-and-intent | Mix per part, finishing, intent check ("does this match what you described?"), one optional surprise version, export | 04, 06, 08 | BUILT |
| 12 | kiro-craft | STARTED Nov 12 (hooks that run real checks, 3 new agents, mcp example, spec checker; see KIRO_USAGE.md). Still to do: role steering that doubles as runtime prompts, hooks that fire, per-role agents, an audio-analysis MCP so Kiro can check its own renders, PBT on the new invariants, CI, mcp.json.example, README/KIRO_USAGE honesty | all | BUILDING |
| 13 | ship-it | Public deployment (incl. any GPU host), all three demo stories passing end to end, license, demo video, write-up, bonus posts | all | BUILDING |
| 14 | frankenstein | The technologies from docs/research/FRANK-KIRO-AND-TECHNOLOGY-REVIEW.md stitched into one body: ears (CLAP, EffNet, Gemini listening, Audiobox, allin1, Chordino), hands (grooves, chord tables, accompaniment, CC0 samples, plugins), voice (DDSP, DiffSinger, DeepFilterNet, word timings, Kokoro), words (CMU, Datamuse, emotions), the world (references, photo, weather), memory (pgvector, Realtime) | 03, 05, 08, 09 | BUILDING |
| 15 | core-path | The main path works for a real person (founder's run, 22 Nov): no crashes on 4-minute takes (heavy jobs on a worker with memory), speed they control, beat as long as the voice, directions that differ, one next step per room, honest status, tested their way | 03, 04, 06, 11, 13 | BUILDING |

Existing specs (foundation, idea-room, feel-lab, beat-room, voice-room, mix-room, export-room, auth,
private-audio, job-reliability, voice-to-export-flow) stay as the record of what was built. New specs
above supersede them where they overlap. When a new spec changes behaviour, it says which old
requirement it replaces.

## Coverage matrix: nothing from the founder is orphaned

Founder decisions (frank-team.md):
| Decision | Owner |
|---|---|
| 1 Producer protects intention, offers 3 directions | 07, 08 |
| 2 Volunteer observations only in review mode | 01 (phase), 07 |
| 3 Creative Director with web research | 10 |
| 4 Frank always speaks; occasional role mentions | 07 |
| 5 User's feeling beats measurement | 03, 08 |
| 6 Specialists may disagree; Frank summarizes | 07 |
| 7 "We can't diagnose yet, let's experiment" | 08 |
| 8 Finished = user's intent met | 01 (intent), 11 |
| 9 One optional surprise version | 11 |
| 10 Specialist memory = relationship | 09 |

Roles: Songwriter 02/07 - Producer 07/08 - Creative Director 10 - Arranger 04 - Beat-maker 04 -
Session player 04 - Vocal producer 06 - Recording engineer 06 - Mix engineer 11 - Mastering engineer 11 -
Listener 03.

Demo stories:
| Story | Needs |
|---|---|
| 1 Grandmother song (user sings, with a guide) | 01, 02 (lyrics+feeling), 04, 05, 06, 07, 11 |
| 2 Clean hum becomes a real song | 01, 02 (hum), 04, 05, 06, 07, 08 |
| 3 "Something feels wrong" producer conversation | 03, 07, 08 |

Baseline problems found (Nov 11 audit) and where they get fixed:
| Problem | Owner |
|---|---|
| brightness / warmth / genre / instrument hints change nothing | 04 |
| Chorus barely louder than verse; bridge loudest (per-section peak normalization) | 04, 03 |
| Melody ignores chords, half the notes are not chord tones | 04 |
| Sections joined with hard cuts; no fills, builds or instrument changes | 04 |
| Same input always gives same music; "try another" can return the same clip | 04 |
| Beat stored as section blobs, not stems | 04 |
| Hum seeds only tempo + loudness; melody and key ignored; silent 90 BPM fallback | 02 |
| Vocal never aligned to the beat; tuning ignores the song's key; harmony is a fixed interval | 06 |
| Voice Room LLM sees only the take count; no room sees the whole song | 01, 07 |
| History lives in the browser and is lost on reload | 01, 07 |
| 3 of 5 hooks do nothing; 7 of 11 specs retrofitted; steering files stale | 12 |

## Order of work (dependencies, not convenience)

1. 01 -> 02 (this week): the record, then every way in.
2. 03 and 04 together: ears and hands. The 05 spike runs alongside 04 so we learn about sound early.
3. 06 once 04 exists (the singer needs a song to sing to).
4. 07 -> 08 -> 09/10: the team on top of real capabilities.
5. 11, then 12 and 13 run continuously, and close last.

Each spec: requirements -> design -> tasks are written and approved BEFORE its code. The founder
listens to the result before the spec is marked Done.
