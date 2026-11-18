"""
Live check of the start paths (spec 02) on the deployed backend: a typed description, a hummed recording through
the one way in, and the song's intent and feeling afterwards. Throwaway account, deleted at the end.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import e2e  # noqa: E402


def main() -> int:
    uid, h = e2e.login()
    ok = True
    try:
        pid = e2e.call(h, "POST", "/projects", json={"title": "Start check"})["id"]
        r = e2e.call(h, "POST", f"/projects/{pid}/intake/description", json={"text": "it should feel like walking home alone after a party, a bit sad but warm"})
        print("description:", r)
        ok &= bool(r["ok"]) and bool(r["message"])
        intent = e2e.call(h, "GET", f"/projects/{pid}/finish/intent")
        print("intent:", intent["intent"])
        ok &= bool(intent["intent"]) and "walking home" in intent["intent"]
        fp = e2e.call(h, "GET", f"/projects/{pid}/feel/fingerprint")
        print("direction filled:", {k: v for k, v in ((fp or {}).get("fingerprint") or {}).items() if k in ("energy_level", "tempo_feel", "mode", "warmth")})
        rec = e2e.call(h, "POST", f"/projects/{pid}/intake/recording", files={"file": ("hum.wav", e2e.sung_take(), "audio/wav")})
        print("recording went:", rec["kind"])
        ok &= rec["kind"] == "hum"
        if rec.get("job_id"):
            done = e2e.job(h, rec["job_id"], "hum")
            print("tune:", done.get("description") or done.get("reason"))
    finally:
        e2e.c.delete(f"{e2e.SB}/auth/v1/admin/users/{uid}", headers=e2e.ADMIN)
    print("START OK" if ok else "START PROBLEM")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
