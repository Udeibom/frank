"""
Live check of the frankenstein spec 14 routes over real HTTP, against FRANK_API (default: the deployed backend).
Unlike e2e.py it does not stop at the first failure: every step is tried and reported, because several organs
depend on things outside Frank (a Space's free GPU quota, a key the founder has not created yet). A step that
fails with a plain message the person would understand counts as "plain"; a crash or a technical message is "FAIL".
  python scripts/ops/e2e_frankenstein.py
The throwaway account is deleted at the end; the project stays (projects are never deleted).
"""
from __future__ import annotations
import io
import struct
import sys
import time
import zlib
import httpx
import numpy as np
from e2e import ADMIN, API, SB, c, login, sung_take  # noqa: E402  (same folder)
try:
    from app.services.team.plain import find_jargon  # noqa: E402
except ImportError:                                     # running off this machine: the same word list
    import re
    def find_jargon(text: str) -> list[str]:
        rx = r"\b(bpm|tempo|reverb|compress\w*|eq|quanti[sz]\w*|stems?|midi|daw|vst|lufs|k?hz|db)\b"
        return sorted({m.group(0).lower() for m in re.finditer(rx, text or "", re.I)})
RESULTS: list[tuple[str, str, str]] = []
REGION = {"X-Frank-Region": "NG"}                       # a region where Gemini is allowed
def record(step: str, status: str, note: str) -> None:
    RESULTS.append((step, status, note))
    print(f"{status:5} {step}: {note[:200]}")
def plain_error(text: str) -> bool:
    """A message the person could read: no codes, no tracebacks, no jargon."""
    low = text.lower()
    return not find_jargon(text) and not any(t in low for t in ("traceback", "exception", "error 5", "internal server"))
def step(h: dict, name: str, method: str, path: str, **kw):
    for attempt in range(12):
        try:
            r = c.request(method, API + path, headers={**h, **REGION}, **kw)
        except httpx.HTTPError as e:                    # this machine's network, or the server restarting
            if attempt == 11:
                record(name, "FAIL", f"network: {e}")
                return None
            time.sleep(15)
            continue
        if r.status_code in (502, 503) and attempt < 3:
            time.sleep(20)
            continue
        if r.status_code >= 400:
            detail = r.text[:300]
            record(name, "plain" if r.status_code < 500 and plain_error(detail) else "FAIL", f"{r.status_code} {detail}")
            return None
        return r.json() if r.content else {}
    return None
def job(h: dict, name: str, started: dict | None, limit: float = 600) -> dict | None:
    if not started or "job_id" not in started:
        return None
    t = time.time()
    while time.time() - t < limit:
        j = step(h, name + " (status)", "GET", f"/jobs/{started['job_id']}/status")
        if j and j["status"] == "complete":
            record(name, "ok", f"in {time.time() - t:.0f}s {str(j.get('result'))[:160]}")
            return j.get("result") or {}
        if j and j["status"] == "failed":
            err = j.get("error") or ""
            record(name, "plain" if plain_error(err) else "FAIL", f"failed plainly: {err}" if plain_error(err) else err)
            return None
        time.sleep(4)
    record(name, "FAIL", f"still running after {limit:.0f}s")
    return None
def png(w: int = 64, h: int = 48) -> bytes:
    """A small dusk-coloured picture, written by hand so this needs no imaging library."""
    rows = b""
    for y in range(h):
        rows += b"\x00" + bytes([int(40 + 120 * y / h), int(30 + 40 * y / h), int(90 + 60 * (1 - y / h))]) * w
    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
def main() -> None:
    uid, h = login()
    try:
        pid = step(h, "project", "POST", "/projects", json={"title": "Frankenstein check"})["id"]
        print("project", pid)
        p = f"/projects/{pid}"
        words = "I walk alone down the quiet road\nThe lights are low and the night is cold\nBut I will sing until the morning comes\nAnd hold the light when the darkness runs"
        fp = {"tempo_bpm": 84, "key": "A minor", "mode": "minor", "energy_level": 0.5, "density": 0.45, "brightness": 0.35,
              "warmth": 0.7, "tempo_feel": "steady", "genre_proximity": ["soul"], "instrumentation_hints": ["piano"]}

        # Starting points from the world
        r = step(h, "intake/moment", "POST", f"{p}/intake/moment", json={"latitude": 6.52, "longitude": 3.38, "hour": 21})
        if r:
            record("intake/moment", "ok", str(r)[:200])
        r = step(h, "intake/picture", "POST", f"{p}/intake/picture", files={"file": ("dusk.png", png(), "image/png")})
        if r:
            record("intake/picture", "ok", str(r)[:200])

        # Words
        step(h, "lyrics save", "POST", f"{p}/lyrics", json={"content": words, "label": "v1"})
        for name, path, body in (("lyrics/analyse", "analyse", {"text": words}), ("lyrics/rhymes", "rhymes", {"word": "road"}),
                                 ("lyrics/emotions", "emotions", {"text": words})):
            r = step(h, name, "POST", f"{p}/lyrics/{path}", json=body)
            if r:
                record(name, "ok", str(r)[:200])

        # Feel and beat
        step(h, "feel fingerprint", "POST", f"{p}/feel/fingerprint", json={"fingerprint": fp, "conversation_summary": "warm and slow"})
        beat = job(h, "beat", step(h, "beat start", "POST", f"{p}/beat/generate", json={"fingerprint": fp}))
        r = step(h, "feel/ranked", "GET", f"{p}/feel/ranked")
        if r is not None:
            record("feel/ranked", "ok", str(r)[:200])
        if beat and beat.get("render_url"):
            r = step(h, "song/peaks", "GET", f"{p}/song/peaks", params={"url": beat["render_url"], "points": 200})
            if r:
                peaks = r.get("peaks") or []
                ok = len(peaks) > 50 and all(0 <= x <= 1 for x in peaks)
                record("song/peaks", "ok" if ok else "FAIL", f"{len(peaks)} points, max {max(peaks or [0]):.2f}")
        r = step(h, "finish/notes", "POST", f"{p}/finish/notes")
        if r:
            url = r.get("url") or r.get("audio_url") or ""
            head = c.get(url).content[:4] if url else b""
            record("finish/notes", "ok" if head == b"MThd" else "FAIL", f"{url[:80]} starts {head!r}")

        # Voice
        up = step(h, "take upload", "POST", f"{p}/voice/takes", files={"file": ("take.wav", sung_take(), "audio/wav")})
        tid = (up or {}).get("id") or ((up or {}).get("take") or {}).get("id")
        if tid:
            step(h, "take active", "POST", f"{p}/voice/active", json={"vocal_id": tid, "vocal_type": "take"})
            time.sleep(8)
            job(h, "voice/quiet", step(h, "voice/quiet start", "POST", f"{p}/voice/takes/{tid}/quiet"), 400)
            job(h, "voice/instrument", step(h, "voice/instrument start", "POST", f"{p}/voice/takes/{tid}/instrument", json={"instrument": "violin"}), 400)
        job(h, "voice/guide/sung", step(h, "voice/guide/sung start", "POST", f"{p}/voice/guide/sung"), 500)
        job(h, "beat/accompany", step(h, "beat/accompany start", "POST", f"{p}/beat/accompany"), 400)

        # Mix and finish
        mix = job(h, "mix", step(h, "mix start", "POST", f"{p}/mix/render", json={"mix_params": {}, "quality": "full"}))
        job(h, "mix/atmosphere (recorded)", step(h, "mix/atmosphere start", "POST", f"{p}/mix/atmosphere", json={"source": "recorded", "words": ["rain"]}), 300)
        listened = job(h, "listen", step(h, "listen start", "POST", f"{p}/listen", json={"concern": "the chorus doesn't lift"}))
        if listened:
            record("listen findings", "ok", str((listened.get("findings") or {}).get("findings"))[:200])
        r = step(h, "references/jamendo search", "GET", f"{p}/references/jamendo", params={"q": "soul"})
        if r is not None:
            record("references/jamendo search", "ok", str(r)[:160])
        job(h, "references/named", step(h, "references/named start", "POST", f"{p}/references/named",
                                        json={"text": "Feeling Good by Nina Simone"}), 300)
        if mix:
            buf = io.BytesIO()
            import soundfile as sf
            sr = 44100
            t = np.arange(sr * 8) / sr
            sf.write(buf, 0.2 * np.sin(2 * np.pi * 220 * t) * (1 + np.sin(2 * np.pi * 2 * t)) / 2, sr, format="WAV")
            job(h, "export/match", step(h, "export/match start", "POST", f"{p}/export/match",
                                        data={"mix_version_id": mix["mix_version_id"], "rights_confirmed": "true"},
                                        files={"file": ("mine.wav", buf.getvalue(), "audio/wav")}), 500)
        r = step(h, "finish/credits", "GET", f"{p}/finish/credits")
        if r:
            record("finish/credits", "ok", str(r)[:300])
        r = step(h, "conversation/speak", "POST", f"{p}/conversation/speak", json={"text": "I made the chorus a little bigger. Does that feel closer?"})
        if r:
            url = r.get("url") or r.get("audio_url") or ""
            record("conversation/speak", "ok" if url or r.get("audio") else "FAIL", str(r)[:160])
    finally:
        if uid:
            c.delete(f"{SB}/auth/v1/admin/users/{uid}", headers=ADMIN)
    print("\nSUMMARY")
    for s, st, n in RESULTS:
        if st != "ok" or not s.endswith("(status)"):
            print(f"  {st:5} {s}")
    sys.exit(1 if any(st == "FAIL" for _, st, _ in RESULTS) else 0)
if __name__ == "__main__":
    main()
