# Listener - Design

## Overview

A pure-analysis service in `backend/app/services/listener/`. It takes audio (and the section plan when
known) and returns a `MeasurementReport` plus a `FindingsReport`. It has no database writes except a
measurement cache keyed by audio version id. Because it is plain Python functions, the same code is exposed
two ways: to specialists inside Frank, and to Kiro as an MCP tool (spec 12) so Kiro can check its own renders.

## Measurements (all deterministic functions of audio)

| Group | Measures | Method |
|---|---|---|
| Level | integrated loudness per section and per part, peak, loudness range | ITU-R BS.1770 style K-weighted loudness (pyloudnorm or an ffmpeg `ebur128` pass); gated |
| Density | note onsets per bar, simultaneous parts | onset detection; part count from stems or the Score |
| Colour | brightness, low-end share | spectral centroid; band energy ratios |
| Change | difference between adjacent sections | distance between section feature vectors (loudness, density, colour, chroma) |
| Repetition | similarity of same-named sections and of chorus vs verse | self-similarity of chroma and MFCC features; melody interval similarity |
| Melody | range, movement, chord-tone fit on strong beats | from the Score or extracted notes; against the progression |
| Vocal tuning | steadiness and distance to the song's notes | pyin vs the song's scale; per-phrase |
| Timing | offset between vocal and beat | cross-correlation of onset envelopes; reports milliseconds internally |
| Competition | vocal vs beat energy overlap in the voice range | band energy overlap on the 200-4000 Hz range |
| Safety | clipping, noise floor, silence | sample statistics |

Section boundaries come from the beat plan (known by construction), so no section detection is needed.

## Findings

Rule-based, each rule a small function: `rule(measurements) -> Finding | None`. Examples:
- "The chorus plays at almost the same strength as the verse" when the loudness gap is below a threshold
  and part count change is small.
- "Your voice sits under the music in the chorus" when the vocal-to-beat gap is below a threshold.
- "The second verse is a copy of the first" when similarity is above a threshold.
- "Your singing runs a little behind the beat" when the timing offset passes a threshold and is stable.
- "The melody wanders away from the harmony in the verse" when strong-beat fit is low.

Thresholds live in one config file, with a comment saying where each came from. Each finding carries
`evidence: [measurement_id]`, `scope: {sections, parts}`, `severity`, `confidence`, and `plain: str`.
If no rule fires for a requested concern, the report says `no_clear_cause: true`.

## Interfaces

```
measure_song(project_id, scope=None) -> MeasurementReport     # cached by version ids
find_issues(report, concern: str | None) -> FindingsReport
compare(version_a, version_b) -> list[Difference]             # used by previews and experiments
```

- `POST /projects/{id}/listen` starts a job (scope optional); result is both reports.
- Specialists (spec 07) call the functions directly, not through HTTP.
- Cache table `listener_cache(audio_version_id, kind, report JSONB, created_at)`.

## Plain-language boundary

Raw numbers and units stay in `MeasurementReport`. `Finding.plain` is written from templates with
no jargon. A check in the plain-language script (spec 12) scans the templates.

## Memory and speed

Load each section or stem on its own, compute features with fixed downsampling, free buffers between
steps. A full song measures in a background job; section-scoped questions measure only what is needed.

## Correctness properties (PBT)

1. Gain invariance: scaling a whole mix by a constant leaves the ordering of section loudness and all
   "gap" findings unchanged.
2. Identity: two identical sections have similarity near 1; a section against silence has similarity near 0.
3. Timing recovery: delaying a copy of a signal by d samples is reported as an offset within one analysis frame of d.
4. Silence and empty input never raise; they return a "could not measure" result.
5. Determinism: same audio, same report.
6. Read-only: calling the Listener leaves every version, file and pointer unchanged.
7. Honesty: when no rule fires, `no_clear_cause` is true and no finding is fabricated.
