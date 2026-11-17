# Refine Loop - Implementation Plan (spec 08)

Depends on 03 (Listener), 04 (typed operations, partial re-render), 07 (team, actions).

- [ ] 1. Direction model, proposals table (migration 007)
  - _Requirements: 2.1, 3.1_
- [ ] 2. Proposer from Listener findings; disagreement with a measurement records a mismatch
  - _Requirements: 1.1-1.3, 2.1_
- [ ] 3. Preview runner (in-memory plan, partial re-render, previews prefix, no writes)
  - _Requirements: 2.2, 2.3_
- [ ] 4. Commit path and decision record; "how does that feel?"
  - _Requirements: 3.1, 3.2_
- [ ] 5. Experiments menu and runner
  - _Requirements: 4.1, 4.2_
- [ ] 6. Version resolver and "give it back" action
  - _Requirements: 5.1, 5.2_
- [ ] 7. UI: direction cards, A/B compare, version history per layer
  - _Requirements: 2.4, 5.3_
- [ ] 8. Property tests, each proved able to fail
- [ ] 9. Demo story 3 end to end on the deployed URL, recorded
