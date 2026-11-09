# Export Room — Design

## Overview

The Export Room is the simplest room: final listen, optional mastering, one download. The design goal from `design-and-ui.md` is emotional — it should feel like the end of a journey, not a checkout page. The correctness work (Spec 07 review) centered on making downloads instant and non-duplicating, delivering files privately via signed URLs, and recording exactly which mix each export came from.

## Architecture

```
Entry ─▶ load active mix ─▶ play (warm greeting)
Master ─▶ POST /export(mix_version_id, apply_mastering=true) ─▶ job
   mastering.master: mix WAV → pedalboard(multiband comp, limiter, loudnorm -14 LUFS) → WAV → 320k MP3
   store exports/ (private) ; export row (mix_version_id, mastered=true, storage_path)
Download ─▶ dedup by (mix_version_id + mastered)
   exists? reuse : render full ─▶ GET /exports/{id}/download ─▶ signed URL
```

## Components and Interfaces

### Frontend
- Final-listen screen: large play button, warm greeting, active mix loaded.
- "Make it radio ready" action; auto-plays the mastered result with a "Radio-ready version" badge and one-click "Go back to the original".
- "Download" button; shows "Preparing your download..." only when a render is needed; closing message on success.
- Collapsible export history with re-download links.

### Backend
- `routers/export.py` — export (render/master), list, download (signed URL).
- `services/audio/mastering.py` — pedalboard mastering chain + FFmpeg 320k encode.
- `services/storage/files.py` — private bucket upload + `create_signed_url`.
- `db/exports.py` — export records, dedup lookup.

## Data Models

- `exports` (project_id, `mix_version_id`, `storage_path`, audio_url, format, quality, `mastered`, created_at). The `mix_version_id` and `mastered` columns (added in this spec) record provenance and power dedup.

Design decisions:
- **Dedup by (mix_version_id + mastered)** — the same mix exported twice reuses the row and file, so download is instant and history stays clean.
- **Private bucket + signed URLs** — exports are the user's finished work; the download endpoint mints a time-limited signed URL from `storage_path` (with a public-URL fallback for legacy rows).
- **Mastering non-destructive** — the un-mastered mix is preserved; "go back to the original" is a pointer change, not a re-render.

## Error Handling

- Entry-load, master, and download failures surface plain-language messages rather than silent failures or raw errors.
- The closing line ("It's yours. Good luck with it.") appears right after a successful download, tied to the success event rather than to history existing.

## Testing Strategy

- Manual: enter, listen, master, compare and revert, download (instant on repeat), re-download from history.
- Property-based candidate (later spec): loudness normalization peak ≤ target.

## Deferred (tracked)

1. **Waveform on the final-listen screen (W1).** Play works; a waveform overlay needs peak data from the backend — visual polish.
2. **Two-pass loudnorm (S1).** Single-pass hits the target well enough for the MVP; two-pass is more accurate for a stronger "radio ready" claim.
3. **True 320k from an un-encoded source (W5).** The export container is 320k but the mix source is 192k MP3, so lost detail can't be recovered; a true-320k export would render from the un-encoded mix buffer.
4. **Heavy-job concurrency guard (W6).** A single-slot queue for mastering/mix/beat renders would harden the free-tier instance — the same cross-cutting item tracked since the Feel Lab.
