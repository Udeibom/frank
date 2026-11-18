"""
The intent statement and the intent check (finish-and-intent spec 11, requirement 3).

The person's own first description of the song is kept, word for word, as the intent statement. Before the first
export, Frank plays the song and asks, in their words, whether it matches. "Not yet" goes to the refine loop with
their answer as the concern; "Yes" records the decision, and the export marks the song finished.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

log = logging.getLogger(__name__)

DESCRIBING_ROOMS = {"idea", "feel", "beat"}
MIN_WORDS = 5
# Messages that are instructions about the tool, not a description of the song.
NOT_A_DESCRIPTION = re.compile(r"^\s*(make|build|change|turn|add|remove|can you|could you|play|stop|undo|go back|give me|try)\b", re.I)


def looks_like_description(room: str, text: str) -> bool:
    words = re.findall(r"[A-Za-z']+", text)
    return room in DESCRIBING_ROOMS and len(words) >= MIN_WORDS and not NOT_A_DESCRIPTION.match(text) and "?" not in text[-2:]


async def capture(project_id: str, room: str, text: str) -> Optional[str]:
    """
    Keep the first description as the intent statement. Only the first: a later change is the person's to make
    (an intent version can only be written by them). Never raises. Returns the stored text when it was captured.
    """
    from app.models.song import USER_AUTHOR
    from app.services.song import record as song_record
    from app.services.song import store

    if not looks_like_description(room, text):
        return None
    try:
        if await song_record.active_facet(project_id, "intent"):
            return None
        await store.write_facet(project_id, "intent", {"text": text.strip()[:600], "room": room}, author=USER_AUTHOR,
                                operation="first_description", label="What you said the song is")
        return text.strip()[:600]
    except Exception:  # noqa: BLE001  the intent is a help; it never breaks a conversation
        log.warning("could not keep the intent statement", exc_info=True)
        return None


def question(intent: Optional[str]) -> str:
    if intent:
        return f"You said \u201c{intent}\u201d. Does this feel like that?"
    return "Before we finish: does this feel like the song you had in your head?"


async def state(project_id: str) -> dict[str, Any]:
    """What the Export Room needs for the check: the words, whether it was already answered, the decision."""
    from app.db import song as song_db
    from app.services.song import record as song_record

    facet = await song_record.active_facet(project_id, "intent") or {}
    decisions = await song_db.list_decisions(project_id, limit=50)
    answered = next((d for d in decisions if (d.options or [{}])[0].get("kind") == "intent_check"), None)
    return {"intent": facet.get("text"), "question": question(facet.get("text")),
            "answered": answered.chosen_option if answered else None}


async def answer(project_id: str, yes: bool, said: Optional[str]) -> dict[str, Any]:
    from app.db import song as song_db

    st = await state(project_id)
    await song_db.insert_decision(project_id, {
        "summary": "The song matches what they described" if yes else "Not yet what they described",
        "rationale": said, "proposed_by": "frank", "chosen_option": "yes" if yes else "not_yet",
        "options": [{"kind": "intent_check", "intent": st["intent"]}], "user_reaction": said,
    })
    if yes:
        return {"next": "export", "message": "Then let's finish it."}
    concern = (said or "").strip() or "it doesn't feel like what I described yet"
    return {"next": "refine", "concern": concern,
            "message": "Thanks for saying so. Let me listen for what's in the way, and I'll come back with a few ideas."}
