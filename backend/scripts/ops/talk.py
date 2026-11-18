"""Ask a room's conversation endpoint something, in-process (no server), against a real project. Prints the reply.
  python scripts/ops/talk.py <room> <project_id> "message" """
import json, sys
from fastapi.testclient import TestClient
from app import main
from app.auth import require_project_access
room, pid, msg = sys.argv[1], sys.argv[2], sys.argv[3]
path = {"idea": f"/projects/{pid}/conversation/idea", "beat": f"/projects/{pid}/beat/conversation",
        "feel": f"/projects/{pid}/feel/conversation", "voice": f"/projects/{pid}/voice/conversation",
        "mix": f"/projects/{pid}/mix/conversation"}[room]
main.app.dependency_overrides[require_project_access] = lambda: None
body = {"message": msg, "history": []}
if room == "beat":
    from app.db.client import get_supabase
    st = get_supabase().table("project_active_state").select("active_beat_version_id").eq("project_id", pid).execute().data
    v = get_supabase().table("beat_versions").select("params").eq("id", st[0]["active_beat_version_id"]).execute().data[0]
    body["beat_state"] = {"sections": v["params"]["sections"]}
if room == "idea":
    body["current_lyrics"] = ""
r = TestClient(main.app).post(path, json=body)
print(r.status_code, json.dumps(r.json(), indent=1)[:1500])
