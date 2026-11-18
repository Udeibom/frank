"""
Stored conversations (team-conversation spec 07, requirement 7).

Every exchange in every room is written here, so reloading the page or opening the song on another device shows
the conversation. After 20 exchanges in a room the older turns are summarised into one paragraph, which every
later reply in that room is given instead of the old turns. Storage problems never stop a reply.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.db.client import get_supabase

log = logging.getLogger(__name__)
ROOMS = ("idea", "feel", "beat", "voice", "mix", "export")
KEEP_TURNS = 40                 # 20 exchanges kept word for word
SUMMARISE_EVERY = 10            # summarise again once this many more turns have scrolled out of the window

SUMMARY_SYSTEM = (
    "You summarise a conversation between a person and Frank, their music producer, in one short paragraph. "
    "Keep what the person wants, what they liked and disliked, what was changed, and anything still open. "
    "Plain words, no music jargon, no numbers. Reply with the paragraph only."
)


def _rows(project_id: str, room: str) -> list[dict]:
    return (
        get_supabase().table("conversation_turns").select("role,content,actions,created_at")
        .eq("project_id", project_id).eq("room", room).order("created_at").execute().data
    )


async def history(project_id: str, room: str) -> list[dict[str, Any]]:
    """Every stored turn in a room, oldest first. Empty on any storage problem."""
    try:
        return await asyncio.to_thread(_rows, project_id, room)
    except Exception:  # noqa: BLE001
        log.warning("could not read conversation history", exc_info=True)
        return []


async def record(project_id: str, room: str, user_message: str, reply: str, actions: Optional[list] = None) -> None:
    """Store one exchange. Best effort: a storage failure is logged, never shown to the person."""
    actions = [a if isinstance(a, dict) else getattr(a, "model_dump", lambda: a)() for a in (actions or [])]
    rows = [
        {"project_id": project_id, "room": room, "role": "user", "content": user_message[:8000], "actions": []},
        {"project_id": project_id, "room": room, "role": "assistant", "content": reply[:8000], "actions": actions or []},
    ]
    try:
        await asyncio.to_thread(lambda: get_supabase().table("conversation_turns").insert(rows).execute())
    except Exception:  # noqa: BLE001
        log.warning("could not store conversation turn", exc_info=True)
    # The person's first description of the song becomes the intent statement (spec 11, requirement 3.1).
    from app.services.finish.intent import capture, looks_like_description

    if looks_like_description(room, user_message):
        await capture(project_id, room, user_message)


def _summary_row(project_id: str, room: str) -> Optional[dict]:
    rows = (get_supabase().table("conversation_summaries").select("summary,turns_covered")
            .eq("project_id", project_id).eq("room", room).limit(1).execute().data)
    return rows[0] if rows else None


async def earlier_summary(project_id: str, room: str) -> Optional[str]:
    """
    The paragraph that stands in for turns older than the last 20 exchanges, refreshed when enough new turns have
    scrolled out. None while the conversation is still short.
    """
    try:
        turns = await history(project_id, room)
        older = turns[:-KEEP_TURNS] if len(turns) > KEEP_TURNS else []
        if not older:
            return None
        row = await asyncio.to_thread(_summary_row, project_id, room)
        if row and len(older) - int(row["turns_covered"]) < SUMMARISE_EVERY:
            return row["summary"]
        from app.services.llm.groq_client import chat_text

        transcript = "\n".join(f"{'Person' if t['role'] == 'user' else 'Frank'}: {t['content']}" for t in older[-80:])
        prior = f"Earlier summary: {row['summary']}\n\n" if row else ""
        summary = await asyncio.to_thread(chat_text, SUMMARY_SYSTEM, prior + transcript, 0.2)
        await asyncio.to_thread(lambda: get_supabase().table("conversation_summaries").upsert(
            {"project_id": project_id, "room": room, "summary": summary, "turns_covered": len(older)}).execute())
        return summary
    except Exception:  # noqa: BLE001
        log.warning("could not summarise the conversation", exc_info=True)
        return None


async def with_earlier(project_id: str, room: str, system: str) -> str:
    """The room's system prompt plus the summary of turns older than the last 20 exchanges, when there is one."""
    summary = await earlier_summary(project_id, room)
    return f"{system}\n\n--- EARLIER IN THIS ROOM (summary) ---\n{summary}" if summary else system


def recent_messages(turns: list[dict], limit: int = KEEP_TURNS) -> list[dict]:
    """The last exchanges in the shape the model expects."""
    return [{"role": t["role"], "content": t["content"]} for t in turns[-limit:] if t.get("content")]


async def enforce_reply(project_id: str, room: str, message: str) -> str:
    """Code-side team rules on a reply before anyone sees it: no specialist named twice within three replies."""
    from app.services.team import roles

    if not roles.mentions(message):
        return message
    previous = [t["content"] for t in await history(project_id, room) if t["role"] == "assistant"]
    return message if roles.may_mention(previous) else roles.strip_mention(message)
