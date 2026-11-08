# Spec 07 — Export Room

## Overview

The Export Room is the finish line. The user listens to the final mix one more time, optionally applies a mastering pass, and downloads their song as an MP3. It is the simplest room in Frank — it should feel like a celebration, not a form.

---

## Requirements

### R1 — Final Listen
- The Export Room loads with the active mix version playing (or ready to play)
- The waveform is shown — the full song, from start to finish
- The system greets: "Here's your song. Take a final listen before you take it with you."
- A single large play button

### R2 — Mastering Pass (Optional)
- One-button mastering: "Make it radio ready"
- Applies a mastering chain server-side: multiband compression, limiting, loudness normalization to -14 LUFS
- Async job — takes 30-60 seconds
- The result plays automatically when ready: "Here's the mastered version — does it feel better?"
- The user can compare: original mix vs mastered
- Mastering is non-destructive — the un-mastered mix is preserved
- If the user doesn't like it: "Go back to the un-mastered version" — one click

### R3 — Export
- A single "Download" button — downloads the MP3
- The song filename: `[project-title].mp3` (sanitized for filesystem use)
- Before download, the full render runs if it hasn't already (or if the mix has changed since the last full render)
- Show progress: "Preparing your download..." for the final render
- After download: "It's yours. Good luck with it." — simple, warm

### R4 — Export History
- All exports are stored as records in the `exports` table
- A collapsible panel shows past exports: date, which mix version was used
- Re-download any past export

### R5 — Backend: Export Endpoints
- `POST /projects/{project_id}/export` — trigger a final export render
  - Request: `{ mix_version_id: string, apply_mastering: bool }`
  - Response: `{ job_id: string }`
- `GET /projects/{project_id}/exports` — list all exports
- `GET /projects/{project_id}/exports/{export_id}/download` — returns a signed Supabase Storage URL for direct download

### R6 — Backend: Mastering Chain
- `services/audio/mastering.py`:
  - Input: WAV from mix render
  - Apply via pedalboard: multiband compressor, limiter, loudness normalization (-14 LUFS)
  - Output: mastered WAV → converted to MP3 320kbps via FFmpeg
  - Store in Supabase Storage under `exports/`

---

## Design Notes

- The Export Room should feel like the end of a journey, not a checkout page
- "It's yours. Good luck with it." — that line matters. Frank has been with them the whole way.
- The download should be instant once the file is ready — no re-processing on click
- No settings, no options, no confusion. One song, one download.

---

## Implementation Tasks

### Task 1 — Final listen UI
- [ ] Load and play active mix on entry
- [ ] Full waveform display

### Task 2 — Mastering
- [ ] "Make it radio ready" button
- [ ] Async job, play result, compare before/after
- [ ] Revert to un-mastered

### Task 3 — Download
- [ ] "Download" button triggers final render if needed
- [ ] Download from signed Supabase URL
- [ ] Filename sanitization

### Task 4 — Export history
- [ ] List past exports, re-download links

### Task 5 — Backend: mastering pipeline
- [ ] `services/audio/mastering.py` with pedalboard chain
- [ ] WAV to MP3 320kbps via FFmpeg
- [ ] Supabase Storage upload

### Task 6 — Backend: export routes
- [ ] All three endpoints
- [ ] Signed URL generation for download
- [ ] Export record creation in DB

---

## Post-Review Follow-Ups (Spec 07)

From the Frank Code Reviewer pass. Addressed in this spec:
- **C1 (duplicate exports / re-render on every download):** exports now dedup by (mix_version_id + mastered). Download reuses an existing export if one matches — instant, no duplicate rows.
- **C2 (R4 "which mix version"):** `exports` table gained `mix_version_id` and `mastered` columns; both are recorded and returned. This also powers the dedup.
- **C3 (R5 signed URL):** the exports bucket is now private, and the download endpoint returns a time-limited signed URL from the stored `storage_path` (public-URL fallback for legacy rows).
- **W2/W3 (R2 auto-play + compare):** the mastered version auto-plays when ready, with a "Radio-ready version" badge and one-click "Go back to the original".
- **W4 (silent failures):** entry load errors and master/download failures now surface plain-language messages.
- **S3 (emotional finish):** "It's yours. Good luck with it." now appears right after a successful download, not merely when history exists.

Deferred, with reasoning:
1. **W1 — waveform display (R1).** The final-listen screen shows a large play button and the song, but not a rendered waveform. Deferred as visual polish; the core "final listen" works. A waveform overlay would need peak data from the backend (a small addition).
2. **S1 — two-pass loudnorm.** Single-pass loudnorm hits the target well enough for the MVP; two-pass is more accurate and worth it later for a stronger "radio ready" claim.
3. **W5 — 320k over a 192k mix source.** The export container is 320k but the mix render it's built from is 192k MP3, so it can't recover lost detail. A true-320k export would render from the un-encoded mix buffer; tracked as a quality improvement.
4. **W6 — heavy-job concurrency guard.** Same cross-cutting item tracked since Spec 03: a single-slot queue for mastering/mix/beat renders would harden the free-tier instance. Deferred.
