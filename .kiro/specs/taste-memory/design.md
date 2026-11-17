# Taste Memory - Design (spec 09)

## Data (migration 008, RLS by user_id)
`taste_signals(id, user_id, project_id, specialist, topic, direction (+1|-1), statement, source, created_at)`
`taste_preferences(id, user_id, specialist, topic, statement, strength, status: active|retired|user_stated,
 edited_by_user bool, updated_at)`

`topic` is a short key from a fixed vocabulary (for example `verse_density`, `vocal_closeness`,
`autotune_amount`, `chorus_size`, `lyric_cliche`, `brightness`, `speed`), so signals about the same thing meet.
The fixed vocabulary lives in `services/taste/topics.py`; the model maps a free-text signal to a topic or
`other` (other is never promoted).

## Promotion
After each new signal: for (user, topic) count signals by direction across distinct projects. Promote when
`same_direction >= 3 and projects >= 2`; strength = net / total. Retire after two consecutive opposite signals.
A direct statement ("I hate autotune") creates a `user_stated` preference immediately.

## Use
`build_brief` gains a "What this artist tends to like" block for the role, max 5 lines. The proposer (spec 08)
orders directions by matching preferences.

## UI
`/taste` page reachable from the studio menu: a list of plain sentences, edit in place, "Forget this",
"Forget everything" (with confirm). Plain words only.

## Properties
1. One signal never creates a preference (except user_stated). 2. Signals from one project never create a
preference. 3. Forget deletes rows. 4. A user never sees another user's taste (RLS test with two users).
