"""
Privacy check over real HTTP (taste-memory spec 09 task 6; ship-it spec 13 RLS audit).

Two throwaway accounts. A makes a song with a take and a taste line. B then tries to read A's things two ways:
directly against the database with B's own login (row level security must return nothing) and through Frank's
backend (ownership checks must answer "not found"). Also lists any table in the public schema without row level
security. Both accounts are deleted at the end.

  venv/bin/python scripts/ops/rls_check.py      (needs SUPABASE_ACCESS_TOKEN for the table list)
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import e2e  # noqa: E402

TABLES = ["projects", "project_active_state", "lyrics_versions", "fingerprints", "texture_samples", "beat_versions",
          "beat_stems", "vocal_takes", "vocal_comps", "mix_versions", "exports", "async_jobs", "song_facet_versions",
          "song_decisions", "conversation_turns", "conversation_summaries", "refine_proposals", "taste_signals",
          "taste_preferences", "user_settings", "guide_renders", "listener_cache"]


def token_headers(h: dict) -> dict:
    return {"apikey": e2e.ANON, "Authorization": h["Authorization"]}


def main() -> int:
    problems: list[str] = []
    a_id, a = e2e.login()
    b_id, b = e2e.login()
    try:
        pid = e2e.call(a, "POST", "/projects", json={"title": "A's private song"})["id"]
        e2e.call(a, "POST", f"/projects/{pid}/voice/takes", files={"file": ("take.wav", e2e.sung_take(), "audio/wav")})
        e2e.call(a, "POST", f"/projects/{pid}/feel/conversation", json={"message": "I hate autotune on my voice, keep it natural"})
        mine = e2e.call(a, "GET", "/taste")["items"]
        if not mine:
            problems.append("A's own taste line was not kept ('I hate autotune')")
        print("A's taste:", [i["statement"] for i in mine])

        # 1. straight at the database with B's login: row level security
        for t in TABLES:
            r = e2e.c.get(f"{e2e.SB}/rest/v1/{t}?select=*", headers=token_headers(b))
            if r.status_code == 404:
                continue                                    # table not exposed / not present
            rows = r.json() if r.status_code == 200 else []
            if isinstance(rows, list) and rows:
                problems.append(f"B can read {len(rows)} row(s) of {t}")
        # and A can see A's own taste the same way (the policy is not simply "nobody")
        own = e2e.c.get(f"{e2e.SB}/rest/v1/taste_preferences?select=id", headers=token_headers(a)).json()
        if not own:
            problems.append("A cannot read A's own taste through row level security (policy too strict)")

        # 2. through Frank's backend: ownership checks
        for path in (f"/projects/{pid}", f"/projects/{pid}/voice/takes", f"/projects/{pid}/beat/versions",
                     f"/projects/{pid}/finish/intent", f"/projects/{pid}/refine/latest"):
            r = e2e.c.get(e2e.API + path, headers=b)
            if r.status_code != 404:
                problems.append(f"B got {r.status_code} for {path}")
        if e2e.call(b, "GET", "/taste")["items"]:
            problems.append("B's taste page shows someone else's lines")
        if mine:
            r = e2e.c.delete(f"{e2e.API}/taste/{mine[0]['id']}", headers=b)
            if r.status_code != 404:
                problems.append(f"B could forget A's taste line ({r.status_code})")
        # forgetting deletes
        e2e.call(a, "DELETE", "/taste")
        left = e2e.c.get(f"{e2e.SB}/rest/v1/taste_signals?select=id&user_id=eq.{a_id}", headers=e2e.ADMIN).json()
        left += e2e.c.get(f"{e2e.SB}/rest/v1/taste_preferences?select=id&user_id=eq.{a_id}", headers=e2e.ADMIN).json()
        if left:
            problems.append(f"'Forget everything' left {len(left)} row(s) behind")
    finally:
        for uid in (a_id, b_id):
            e2e.c.delete(f"{e2e.SB}/auth/v1/admin/users/{uid}", headers=e2e.ADMIN)

    # 3. tables without row level security at all
    if os.environ.get("SUPABASE_ACCESS_TOKEN"):
        out = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sql.py"),
                              "select tablename from pg_tables where schemaname='public' and not rowsecurity"],
                             capture_output=True, text=True).stdout
        print("tables without row level security:", out.strip())
        if '"tablename"' in out:
            problems.append(f"tables without row level security: {out.strip()}")
    for p in problems:
        print("PROBLEM:", p)
    print("RLS OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
