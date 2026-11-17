# Team Conversation - Implementation Plan (spec 07)

Depends on spec 01 (brief, done) and spec 03 (Listener).

- [ ] 1. Providers: one interface, Groq primary, free fallback, retries
  - _Requirements: 8.1-8.3_
- [ ] 2. Role cards from frank-team.md, with a test that they stay in step
  - _Requirements: 1.2_
- [ ] 3. Typed actions and executor (replaces Beat Room keyword matching)
  - _Requirements: 5.1, 5.2_
- [ ] 4. Router call and specialist calls
  - _Requirements: 1.1, 1.2_
- [ ] 5. Conflict detection, one bounded round, Producer settles
  - _Requirements: 2.1-2.3, 3.1_
- [ ] 6. Frank reply, mention rule, plain-language guard
  - _Requirements: 1.3, 1.4, 6.1, 6.2_
- [ ] 7. Phase: auto-switch to refining, observations only in refining
  - _Requirements: 4.1-4.3_
- [ ] 8. Conversation storage, 20-turn summaries, between-session summary (migration 006)
  - _Requirements: 7.1-7.3_
- [ ] 9. `/talk` endpoint; all six room pages use it; old routes become wrappers
  - _Requirements: 1.3_
- [ ] 10. Property tests, each proved able to fail
- [ ] 11. Live check with the real model: the three demo-story conversations, transcripts saved
