# Taste Memory - Implementation Plan (spec 09)

Depends on 07 (team) and 08 (refine signals).

- [x] 1. Tables, RLS, topics vocabulary (migration 009; 008 went to sing-it)
  - _Requirements: 1.2, 4.3_
  - Evidence: `db/migrations/009_taste_memory.sql` applied Nov 18 (RLS `user_id = auth.uid()`);
    `services/taste/rules.py TOPICS` (fixed vocabulary, plain sentences, `other` never promoted).
- [x] 2. Signal recording from every source listed in requirement 1
  - _Requirements: 1.1_
  - Evidence: `services/taste/signals.py`: chosen directions and won experiments (`routers/refine.py choose`),
    Feel Lab approvals (`routers/feel.py save_fingerprint`), measurement mismatches (`refine disagree`), what the
    person says about themselves (`conversation_store.record`, every room).
    Not recorded: lyric options taken or refused. The Idea Room offers options inside its reply text, with no
    typed "option chosen" event to record; left for when the Idea Room gets typed options.
    Decision: choosing one direction of three counts for what was chosen; the others are not counted as dislikes.
- [x] 3. Promotion and retirement rules
  - _Requirements: 2.1, 2.2_
  - Evidence: `rules.evaluate` (3 signals, 2 songs, majority; weakens on contradiction; 2 in a row retire),
    `store.reevaluate`.
- [x] 4. Brief block and direction ordering
  - _Requirements: 3.1, 3.2_
  - Evidence: `signals.block_for` appended in `record.system_with_brief` for the room's specialist (max 5 lines,
    "never use it to refuse"); `propose(prefs=...)` orders directions and tells the Producer.
- [x] 5. Taste page: view, edit, forget, forget all
  - _Requirements: 4.1, 4.2_
  - Evidence: `routers/taste.py`, `app/(studio)/taste/page.tsx` (link in the studio nav and on Your Songs).
- [x] 6. Property tests incl. two-user RLS check, each proved able to fail
  - Evidence: `tests/test_properties_taste.py` (8 tests); `scripts/ops/rls_check.py` on prod Nov 18: "RLS OK"
    (B reads none of A's rows directly or through the backend, A reads their own, forget-all deletes, every
    public table has RLS). Mutations: see `scripts/mutate_check.py` taste entries.
