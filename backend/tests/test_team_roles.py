"""Team roles, mention rule, phase (team-conversation spec 07 req 1, 4; kiro-craft spec 12 req 1)."""
from __future__ import annotations

import asyncio
import pathlib
import re
from unittest import mock

from app.models.song import SongRecord
from app.services.song import record as rec
from app.services.team import roles

STEERING = pathlib.Path(__file__).resolve().parents[2] / ".kiro" / "steering" / "frank-team.md"


def _steering_roles() -> set[str]:
    text = STEERING.read_text()
    section = text.split("## The roles", 1)[1].split("## How a request flows", 1)[0]
    names = re.findall(r"^### (.+?)(?: \(.*\))?$", section, re.M)
    return {n.strip().lower().replace(" ", "_").replace("-", "_") for n in names} - {"frank"}


def test_every_role_in_the_steering_file_has_a_runtime_card():
    missing = _steering_roles() - set(roles.ROLES)
    assert not missing, f"frank-team.md has roles with no runtime card: {missing}"


def test_every_room_consults_known_roles():
    for room, team in roles.ROOM_TEAM.items():
        assert team and all(r in roles.ROLES for r in team), room


def test_a_specialist_is_never_named_in_two_replies_in_a_row():
    named = "I asked the beat-maker to calm the drums."
    assert roles.may_mention([])
    assert not roles.may_mention(["fine", named])
    assert not roles.may_mention([named, "fine"])
    assert roles.may_mention([named, "fine", "also fine"])
    out = roles.strip_mention(named)
    assert not roles.mentions(out) and "calm the drums" in out


def test_creating_forbids_observations_and_refining_allows_one():
    assert "Do not volunteer" in roles.team_block("beat", "creating", True)
    assert "ONE observation" in roles.team_block("beat", "refining", True)
    assert "Do NOT name any specialist" in roles.team_block("mix", "creating", False)


def test_the_song_moves_to_refining_once_a_first_draft_exists():
    switched = []

    async def fake_record(pid):
        return SongRecord(project_id=pid, phase="creating", beat={"id": "b"}, vocal={"id": "v"})

    async def fake_update(pid, upd):
        switched.append(upd)

    async def no_history(pid, room):
        return []

    with mock.patch.object(rec, "get_record", fake_record), mock.patch.object(rec.projects_db, "update_project_active_state", fake_update), \
         mock.patch("app.services.team.conversation_store.history", no_history):
        out = asyncio.run(rec.system_with_brief("p1", "SYSTEM", "beat_maker"))
    assert switched == [{"phase": "refining"}]
    assert "PHASE: refining" in out and "YOUR TEAM" in out


def test_every_room_prompt_carries_its_team_and_the_producer_decides_rule():
    """Amended requirements 1.1 and 2 (founder, Nov 19): one call per message, the team and the rule in its prompt."""
    from app.services.team import roles

    for room, team in roles.ROOM_TEAM.items():
        block = roles.team_block(room, "refining", False)
        assert all(roles.ROLES[k]["name"] in block for k in team), room
        assert "the producer decides once" in block and "one voice" in block
