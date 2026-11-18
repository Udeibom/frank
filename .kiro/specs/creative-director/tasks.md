# Creative Director - Implementation Plan (spec 10)

Depends on 07 (team).

- [x] 1. Identity brief writer (events, versioned facet) and "what makes this yours" view
  - _Requirements: 1.1-1.3_
  - Evidence: `services/team/identity.py refresh` (one model call over intent, lyrics, the person's own messages,
    decisions, vocal; plain-guarded; written as an `identity_brief` version; at most every 10 minutes), refreshed
    after lyrics are saved, a direction is chosen, a take is kept; rendered in every brief in plain words
    (`brief._identity_text`); `GET/POST /finish/identity`, page `/[projectId]/yours`, nav link.
- [x] 2. Named-artist detection and the one question; feeling recorded; reference never stored as a target
  - _Requirements: 2.1-2.3_
  - Evidence: `TEAM_RULE` in every room's team block; `identity.detect_reference` + `handle_reply` in all five
    rooms. The live model (Nov 18) described the artist's sound and moved the song's direction toward them, so code
    now replaces that reply with ONE plain question and holds the direction for that turn. The next answer's
    feeling words go to `feeling.loved_qualities`; the name is kept as `references` "feeling only" and the brief
    shows only the feelings. Live: "I want it to sound like Billie Eilish" -> the one question; "the whispery
    closeness, and how dark it is" -> loved ["close", "whisper", "dark"].
- [x] 3. Drift check on directions and changes, one mention, person wins
  - _Requirements: 3.1, 3.2_
  - Evidence: `identity.drift_notes` (Lock it in vs a raw voice or a dislike of tuning; taking their own tune out;
    a lyric suggestion that drops their image), `mention_once` (decision log), wired into the tune job, the refine
    proposal message and the Idea Room. The change still happens when they ask (their call wins).
- [x] 4. Tests: no web call, artist name never reaches the composer, drift property; each proved able to fail
  - Evidence: `tests/test_creative_director.py` (8 tests). Mutations: see `scripts/mutate_check.py`.
