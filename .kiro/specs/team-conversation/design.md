# Team Conversation - Design (spec 07)

## Flow per message
```
POST /projects/{id}/talk {room, message}
  -> load record + brief (record.system_with_brief) + stored history/summary for the room
  -> router: one cheap JSON call -> {specialists: [..], concern: str|null, needs_listening: bool}
  -> if needs_listening: Listener find_issues(cached report, concern)        (spec 03)
  -> each chosen specialist (max 3): JSON {position, actions: [typed], evidence: [ids|"user words"]}
  -> conflict check (code): actions on the same target with opposite direction
       -> one round: each specialist sees the other's position, may revise
       -> Producer call settles: keeps a set of actions
  -> Frank call: writes the reply from the kept positions (one voice, mention rule)
  -> plain-language guard (code: terms replaced directly)
  -> store exchange; return {message, actions, findings_shown}
```
The room pages call `/talk` instead of their own `/conversation` routes. The old routes stay as thin wrappers
for one release, then are removed.

## Specialists as data
`backend/app/services/team/roles.py` loads `.kiro/skills/frank-team/SKILL.md`-derived role cards from
`services/team/roles.json` (owns, hears, changes, disagrees_when, never, allowed_actions). The steering file
stays the human source; a test checks every role in the steering file has a card (spec 12 "role steering that
doubles as runtime prompts").

## Typed actions
`services/team/actions.py`: one Pydantic model per action, for example
`BeatSectionEdit{section_index, change: more_energy|less_energy|busier|sparser|add_part|remove_part, part?}`,
`ArrangeSections{op: reorder|duplicate|remove, ...}`, `RegenerateSection{section_index, new_seed}`,
`MixLevel{target: vocal|beat|harmony|part:<name>, section?, direction, amount: small|medium}`,
`MixTone{target, change: warmer|brighter|clearer|smoother}`, `MixSpace{target, change: more|less}`,
`VocalTune{take_id, mode}`, `VocalAlign`, `VocalRemoveBleed`, `VocalComp`, `VocalHarmony{sections, type}`,
`LyricOptions{lines, options}`, `FeelUpdate{fields}`, `GenerateTexture`, `Listen{scope, concern}`,
`ProposeDirections` (spec 08). The executor maps each to the existing job endpoints.

## Mention rule
Stored per room: `turns_since_mention`. Frank's prompt is told whether a mention is allowed this turn.

## Phase switch
`record.has_first_draft` exists. On mix render completion the runner sets phase to `refining` if it was
`creating` and a beat and a vocal exist (decision recorded in the decisions log).

## Storage (additive migration 006)
`conversation_turns(id, project_id, room, role, content, actions jsonb, created_at)`;
`conversation_summaries(project_id, room, summary, upto_turn_id, updated_at)`.
`projects.session_summary text` for the between-sessions summary.

## Providers
`services/llm/providers.py`: `chat_json(system, messages)` tries Groq (`openai/gpt-oss-120b`), on 429/5xx/timeout
tries the fallback. Fallback: Google Gemini API free tier (`gemini-2.5-flash`, JSON mode) with key
`GEMINI_API_KEY`. If no fallback key is set, the second try is Groq's smaller JSON-capable model. The model
names live in this one file.

## Plain-language guard
`services/team/plain.py`: regex list from conversation-layer steering (BPM, tempo, key/mode as music terms,
reverb, compression, EQ, Hz/kHz/dB, quantization, stem, DAW, VST, MIDI, LUFS) plus replacements table.
Shared with the Plain Language Auditor agent. Each term is replaced directly (no model rewrite; founder agreed Nov 19).

## Token budget (the reason for the decision above)
Groq free tier is 6,000 tokens/min. Router + up to 3 specialists + Frank is too much per message at full
brief size, so: router and Frank get the full brief; specialists get the role-trimmed brief
(`build_brief(record, role, budget_chars=2500)`); a message that only needs one specialist skips the
conflict round. Measured target: under 5,000 tokens for a typical message.

## Properties
1. Every executed action validates against its schema. 2. A reply never contains a banned term after the guard.
3. Mentions never occur in two consecutive replies. 4. The conflict round runs at most once. 5. History reload
returns the same turns in the same order.
