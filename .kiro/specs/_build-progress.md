# Build progress (kept up to date during the build; read this first after an interruption)

Deployed: frontend https://frank-bay-zeta.vercel.app · backend https://frank-api-pzjo.onrender.com (Render srv-dbtv8e0n74is73evdbdg)
Ops: `backend/scripts/ops/render.py wait|logs|events|env`, `backend/scripts/ops/e2e.py` (full HTTP walkthrough on prod).

## Done (committed and pushed)
- Server fits 512 MB: SoundFont dynamic sample loading, chunked in-place mastering (beat + export), chunked loudness,
  22 kHz listener decode, warm numba cache baked into the image, one heavy job at a time with memory released after each.
- Song engine: typed edit operations (`generation/ops.py`, `/beat/operations`), stable section identity, per-part edits,
  "another song" seed, keyword editor removed; planner from the words' structure; energy curve.
- Listener (spec 03) service, job, cache table; shared song brief in every room; tapped rhythm; tune fixes 4.9-4.11.

## Verified on production
- beat 261-280 s, mix 34-53 s, listen 69 s. Export crashed for memory before the release fix (commit 7c4e830); re-check pending.

## Next, in order
1. Confirm prod e2e passes through export.
2. Team conversation (spec 07): providers with Gemini fallback, plain-language guard, stored history, phase switch.
3. Refine loop (spec 08): directions + previews + commit, experiments, version resolver.
4. Sing it (spec 06): song-aware tuning, harmony from chords, guide track, alignment, engineer messages.
5. Finish (spec 11): parts in the mix, intent check, surprise, separate parts download.
6. Taste memory (09), creative director (10), start-anywhere rest (02), kiro-craft (12), demo runs (13).
