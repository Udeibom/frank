from fastapi import APIRouter, HTTPException
from app.models.conversation import IdeaConversationRequest, ConversationResponse
from app.services.llm.groq_client import chat_structured
from app.services.song.record import system_with_brief
from app.services.team import conversation_store as convo
from app.services.llm.prompts import IDEA_ROOM_SYSTEM, build_idea_room_messages
from app.services.song import store as song_store
from app.services.song.sections import parse_section_order, structure_from_order

router = APIRouter(prefix="/projects/{project_id}/conversation", tags=["conversation"])


@router.post("/idea", response_model=ConversationResponse)
async def idea_conversation(
    project_id: str, body: IdeaConversationRequest
) -> ConversationResponse:
    """
    Idea Room co-writer. Takes the user's message plus the current lyrics
    and conversation history, returns Frank's reply and any lyric suggestions.
    """
    history = [{"role": m.role, "content": m.content} for m in body.history]
    if not history:   # after a reload the page has nothing; the stored conversation is the memory
        history = convo.recent_messages(await convo.history(project_id, "idea"))

    stated_order = parse_section_order(body.message)
    if len(stated_order) >= 2:
        await song_store.write_facet(
            project_id,
            "structure",
            structure_from_order(stated_order),
            author="user",
            operation="set_section_order",
            label="Section order from the words room",
        )

    messages = build_idea_room_messages(
        current_lyrics=body.current_lyrics,
        history=history,
        user_message=body.message,
        selected_text=body.selected_text,
    )

    system = await convo.with_earlier(project_id, "idea", await system_with_brief(project_id, IDEA_ROOM_SYSTEM, "songwriter"))
    try:
        result = chat_structured(system, messages)
        from app.services.team.identity import handle_reply

        await handle_reply(project_id, result, body.message, "idea")   # a named artist becomes a feeling (spec 10)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Frank got distracted for a second — try saying that again?",
        ) from exc

    # Only the suggest_lyrics action is valid in the Idea Room — filter the rest
    actions = [
        a for a in result.get("actions", [])
        if isinstance(a, dict) and a.get("type") == "suggest_lyrics"
    ]

    # The Creative Director: a suggestion that drops one of their own images says so, once (spec 10, req 3).
    from app.services.team import identity

    for a in actions:
        old = identity.section_text(body.current_lyrics or "", str((a.get("params") or {}).get("section_label") or ""))
        if old:
            ident, _ = await identity.context(project_id)
            found = identity.drift_notes(ident, old_text=old, new_text=str((a.get("params") or {}).get("content") or ""))
            note = await identity.mention_once(project_id, f"lyric:{found[0]}", found[0]) if found else None
            if note:
                result["message"] = f"{result.get('message', '')} {note}".strip()
                break
    result["message"] = await convo.enforce_reply(project_id, "idea", result.get("message", ""))
    await convo.record(project_id, "idea", body.message, result.get("message", ""), actions)
    return ConversationResponse(message=result.get("message", ""), actions=actions)


@router.get("/{room}/history")
async def room_history(project_id: str, room: str) -> list[dict]:
    """Every stored exchange in one room, oldest first, so a reload or another device shows the conversation."""
    if room not in convo.ROOMS:
        raise HTTPException(status_code=404, detail="I don't know that room.")
    return [{"role": t["role"], "content": t["content"], "created_at": str(t["created_at"])} for t in await convo.history(project_id, room)]


# ── Frank reads its note aloud (frankenstein spec 14, requirement 4.5) ──────────────────────────────────

from pydantic import BaseModel as _BaseModel, Field as _Field  # noqa: E402


class SpeakRequest(_BaseModel):
    text: str = _Field(min_length=1, max_length=1200)


@router.post("/speak")
async def speak(project_id: str, body: SpeakRequest) -> dict:
    import asyncio as _asyncio

    from app.services.remote import organs
    from app.services.storage.files import upload_audio

    audio = await _asyncio.to_thread(organs.try_, organs.speak, body.text)
    if not audio:
        return {"audio_url": None, "message": "My speaking voice is asleep right now. The words are on screen."}
    url = await _asyncio.to_thread(upload_audio, "voice-memos", audio, "mp3", "frank-says")
    return {"audio_url": url}
