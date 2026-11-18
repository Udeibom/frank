"""Every room's conversation is reachable, speaks from the shared brief, and is stored (spec 07 req 7)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import require_project_access

ROOM_ROUTES = {
    "idea": "/projects/p1/conversation/idea", "feel": "/projects/p1/feel/conversation",
    "beat": "/projects/p1/beat/conversation", "voice": "/projects/p1/voice/conversation",
    "mix": "/projects/p1/mix/conversation",
}


def test_every_room_has_a_conversation_route():
    paths = {getattr(r, "path", "") for r in main.app.routes}
    for room, path in ROOM_ROUTES.items():
        assert path.replace("p1", "{project_id}") in paths, room
    assert "/projects/{project_id}/conversation/{room}/history" in paths


@pytest.mark.parametrize("room", list(ROOM_ROUTES))
def test_each_room_stores_the_exchange_and_uses_the_earlier_summary(room, monkeypatch):
    from app.services.team import conversation_store as convo
    from app.services.song import record as song_record
    stored, systems = [], []

    async def fake_record(pid, r, user, reply, actions=None):
        stored.append((pid, r, user, reply))

    async def fake_earlier(pid, r, system):
        return system + "\nEARLIER: they like it sparse"

    async def fake_brief(pid, system, role=None):
        return system

    def fake_chat(system, messages, temperature=0.7):
        systems.append(system)
        return {"message": "I made the drums a little calmer. How does that feel?", "actions": []}

    monkeypatch.setattr(convo, "record", fake_record)
    monkeypatch.setattr(convo, "with_earlier", fake_earlier)
    for mod in ("conversation", "feel", "beat", "voice", "mix"):
        r = __import__(f"app.routers.{mod}", fromlist=["x"])
        monkeypatch.setattr(r, "chat_structured", fake_chat, raising=False)
        monkeypatch.setattr(r, "system_with_brief", fake_brief, raising=False)

    async def no_takes(pid):
        return []
    from app.db import voice as voice_db
    monkeypatch.setattr(voice_db, "list_takes", no_takes)
    main.app.dependency_overrides[require_project_access] = lambda: None
    try:
        body = {"message": "calm the drums down", "history": []}
        if room == "idea":
            body["current_lyrics"] = ""
        res = TestClient(main.app).post(ROOM_ROUTES[room], json=body)
    finally:
        main.app.dependency_overrides.clear()
    assert res.status_code == 200, res.text
    assert stored == [("p1", room, "calm the drums down", "I made the drums a little calmer. How does that feel?")]
    assert systems and "EARLIER: they like it sparse" in systems[0]
