# Refine Loop - Design (spec 08)

## Pieces
| Piece | Where |
|---|---|
| Direction model `Direction{id, title, plain, actions: [typed], scope: {sections}, preview_url?}` | `services/refine/models.py` |
| Proposer: Producer call with Listener findings + record -> 2-3 Directions, validated (distinct action sets) | `services/refine/propose.py` |
| Preview runner: applies actions to an IN-MEMORY copy of the active plan / mix params, renders only affected sections (song-engine 7.2 partial re-render), uploads to a `previews/` prefix, never writes versions | `services/jobs/preview_runner.py` |
| Commit: runs the same actions through the normal job path (new version + active pointer) | executor from spec 07 |
| Experiments: a fixed menu of single-variable changes, ranked by which sections the complaint names | `services/refine/experiments.py` |
| Version resolver: `resolve(text, versions, decisions) -> version | [candidates]` | `services/refine/resolve.py` |
| Proposals stored: `refine_proposals(id, project_id, concern, findings, directions jsonb, chosen, created_at)` | migration 007 |

## Preview speed
Partial re-render renders only sections whose plan changed plus one bar of neighbours for the joins, then
splices into the cached full render (per-section MP3s already stored per beat version). Mix previews reuse the
existing 64 kbps preview render. Target: one 8-bar section in < 30 s on a 0.1-CPU Render instance; measured on
deploy, and the progress text says the honest wait.

## Experiment menu
energy (chorus fuller / verse thinner), tune (chorus up an octave-step on the engine melody, not on a hummed
tune), speed (+-6%), space (more/less room on the vocal), density (busier/sparser drums), colour (warmer/brighter).
Each experiment changes one field; property-tested.

## Version resolver
Ordinal ("second", "first", "last", "previous"), relative ("before I changed X" -> latest version created before
the decision whose summary mentions X), date ("yesterday"), label match (fuzzy). Returns a single version or the
top two candidates.

## UI
Conversation shows direction cards (title, one sentence, play preview, "Use this"). A/B compare plays current and
preview from the same position. Version history panel per layer reuses BeatVersions / MixVersions / takes.

## Properties
1. Previews never change any version row or active pointer. 2. Directions in one proposal have distinct action
sets. 3. Each experiment differs from the current version in exactly one field. 4. Resolver returns a version
that exists in the project or asks.
