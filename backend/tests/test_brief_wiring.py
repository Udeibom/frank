"""Every room's conversation speaks from the shared song brief (song-record spec 01, task 6)."""
import asyncio
from unittest import mock

from app.models.song import SongRecord
from app.services.song import record


def test_the_room_prompt_gets_the_shared_brief_appended():
    async def fake(project_id):
        return SongRecord(project_id=project_id)
    async def no_history(pid, room):
        return []
    with mock.patch.object(record, "get_record", fake), mock.patch("app.services.team.conversation_store.history", no_history):
        out = asyncio.run(record.system_with_brief("p1", "ROOM PROMPT", "beat_maker"))
    assert out.startswith("ROOM PROMPT") and "THE SONG SO FAR" in out and len(out) > len("ROOM PROMPT") + 60


def test_an_unreadable_record_still_gives_the_room_its_prompt_and_its_team():
    async def boom(project_id):
        raise RuntimeError("db down")
    with mock.patch.object(record, "get_record", boom):
        out = asyncio.run(record.system_with_brief("p1", "ROOM PROMPT"))
    assert out.startswith("ROOM PROMPT") and "YOUR TEAM" in out and "THE SONG SO FAR" not in out


def test_every_room_uses_the_brief():
    import pathlib
    for name in ("conversation", "feel", "beat", "voice", "mix"):
        src = pathlib.Path(f"app/routers/{name}.py").read_text()
        assert "system_with_brief(" in src, name
        assert "chat_structured(system, messages)" in src, name
