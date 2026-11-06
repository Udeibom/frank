from fastapi import APIRouter, HTTPException
from app.models.conversation import IdeaConversationRequest, ConversationResponse
from app.services.llm.groq_client import chat_structured
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

    messages = build_idea_room_messages(
        current_lyrics=body.current_lyrics,
        history=history,
        user_message=body.message,
        selected_text=body.selected_text,
    )

    try:
        result = chat_structured(IDEA_ROOM_SYSTEM, messages)
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

    return ConversationResponse(message=result.get("message", ""), actions=actions)
