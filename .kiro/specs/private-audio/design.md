# Private Audio — Design

## Overview

Two choke points and one switch, and no data migration.

```
write  upload_audio() ─▶ stores file, returns the public-style URL ─▶ saved in DB (unchanged)
read   any JSON response ─▶ SignedUrlMiddleware ─▶ swaps storage URLs for signed ones ─▶ browser
job    fetch_audio_bytes(url) ─▶ parse (bucket, path) ─▶ storage.download() with service role
switch every bucket ─▶ public = false
```

## Decisions

- **The stored URL becomes a permanent reference, not a link.** A "public-style" URL still identifies exactly one file (`bucket` + `path`). Keeping it avoids rewriting every row across eleven columns. It is only ever a working link after the middleware swaps it.
- **One ASGI middleware over every JSON response**, instead of editing each endpoint. This is the only place that guarantees "a new route can't forget". It is pure ASGI, not `BaseHTTPMiddleware`, to avoid that class's buffering and background-task quirks. It sits inside the CORS middleware so error and CORS headers are unaffected.
- **Match whole values only.** A string is rewritten only if the entire string is a Frank storage URL. Chat text that happens to mention one is untouched.
- **Pure core, injected signer.** `parse_storage_url` and `sign_json` do no I/O; the real signer is passed in. That makes the rewrite property-testable without a network.
- **Signed links last 2 hours; we reuse one for up to 1 hour.** Every link handed out therefore has at least an hour left. The cache is bounded and evicts expired entries first.
- **Jobs read through `storage.download()`.** It uses the service role, so it keeps working whatever a bucket's visibility is, and avoids an extra signing round trip.
- **Fail open on signing errors, not on authorization.** If Supabase Storage is down the response is returned unsigned; the browser then can't play the file, but the app does not 500. Authorization (who gets a response at all) is the auth layer's job.

## Components

- `app/services/storage/signing.py` — `parse_storage_url`, `sign_json`, the cached batch signer, `fetch_audio_bytes`.
- `app/middleware/signed_urls.py` — the ASGI middleware.
- `app/main.py` — registers it.
- Four call sites switch from `httpx.get(url)` to `fetch_audio_bytes(url)`: `voice_runner`, `mix_runner`, `export_runner`, `routers/mix.py`.
- A one-off script/migration sets buckets private.

## Limits

- A signed link is a capability: whoever holds it can play that file until it expires (2 h). That is the intended trade-off versus a permanent public URL.
- A page left open past the expiry holds a dead link until it reloads that data. Navigating between rooms re-reads state, which refreshes links.
- Newly created buckets default to whatever Supabase's default is; `upload_audio` does not create buckets, so this is a deployment step to remember.
