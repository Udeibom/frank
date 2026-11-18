from fastapi import APIRouter, HTTPException
from app.models.conversation import IdeaConversationRequest, ConversationResponse
from app.services.llm.groq_client import chat_structured
from app.services.song.record import system_with_brief
from app.services.team import conversation_store as convo
from app.services.llm.prompts import IDEA_ROOM_SYSTEM, build_idea_room_messages

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

    messages = build_idea_room_messages(
        current_lyrics=body.current_lyrics,
        history=history,
        user_message=body.message,
        selected_text=body.selected_text,
    )

    system = await convo.with_earlier(project_id, "idea", await system_with_brief(project_id, IDEA_ROOM_SYSTEM, "songwriter"))
    try:
        result = chat_structured(system, messages)
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

    result["message"] = await convo.enforce_reply(project_id, "idea", result.get("message", ""))
    await convo.record(project_id, "idea", body.message, result.get("message", ""), actions)
    return ConversationResponse(message=result.get("message", ""), actions=actions)


@router.get("/{room}/history")
async def room_history(project_id: str, room: str) -> list[dict]:
    """Every stored exchange in one room, oldest first, so a reload or another device shows the conversation."""
    if room not in convo.ROOMS:
        raise HTTPException(status_code=404, detail="I don't know that room.")
    return [{"role": t["role"], "content": t["content"], "created_at": str(t["created_at"])} for t in await convo.history(project_id, room)]
