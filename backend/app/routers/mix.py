from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.models.mix import (
    RenderMixRequest,
    MixConversationRequest,
    MixConversationResponse,
    SetActiveMixRequest,
    MixVersionResponse,
    JobResponse,
)
from app.models.conversation import ConversationAction
from app.services.llm.groq_client import chat_structured
from app.services.llm.prompts import MIX_ROOM_SYSTEM, build_mix_room_messages
from app.services.jobs.mix_runner import run_mix_job
from app.db import jobs as jobs_db
from app.db import mix as mix_db
from app.db import projects as projects_db

router = APIRouter(prefix="/projects/{project_id}/mix", tags=["mix"])

# Default starting balance: vocal present, beat sitting under it.
DEFAULT_MIX_PARAMS = {
    "vocal_gain_db": 0.0,
    "beat_gain_db": -6.0,
    "harmony_gain_db": -4.0,
    "harmony_enabled": True,
    "vocal_effects": [],
    "beat_effects": [],
    "section_gain_db": {},
}

_ALLOWED_ACTIONS = {
    "adjust_levels",
    "apply_effect",
    "toggle_harmony",
    "section_adjust",
    "analyze_mix",
}


def _clamp_db(v: float) -> float:
    return max(-24.0, min(12.0, v))


def apply_actions(params: dict, actions: list[dict]) -> tuple[dict, bool]:
    """
    Apply conversation actions to mix params. Returns (new_params, should_render).
    analyze_mix alone doesn't change params or trigger a render.
    """
    p = {**DEFAULT_MIX_PARAMS, **params}
    # Ensure list/dict fields are copies we can mutate
    p["vocal_effects"] = list(p.get("vocal_effects", []))
    p["beat_effects"] = list(p.get("beat_effects", []))
    p["section_gain_db"] = dict(p.get("section_gain_db", {}))
    render = False

    for action in actions:
        atype = action.get("type")
        ap = action.get("params", {}) or {}

        if atype == "adjust_levels":
            p["vocal_gain_db"] = _clamp_db(p["vocal_gain_db"] + float(ap.get("vocal_delta_db", 0)))
            p["beat_gain_db"] = _clamp_db(p["beat_gain_db"] + float(ap.get("beat_delta_db", 0)))
            p["harmony_gain_db"] = _clamp_db(p["harmony_gain_db"] + float(ap.get("harmony_delta_db", 0)))
            render = True

        elif atype == "apply_effect":
            target = ap.get("target")
            effect = ap.get("effect")
            on = bool(ap.get("on", True))
            key = "vocal_effects" if target == "vocal" else "beat_effects"
            if effect:
                if on and effect not in p[key]:
                    p[key].append(effect)
                elif not on and effect in p[key]:
                    p[key].remove(effect)
                render = True

        elif atype == "toggle_harmony":
            p["harmony_enabled"] = bool(ap.get("on", True))
            render = True

        elif atype == "section_adjust":
            section = ap.get("section")
            if section:
                cur = p["section_gain_db"].get(section, 0.0)
                p["section_gain_db"][section] = _clamp_db(cur + float(ap.get("delta_db", 0)))
                render = True

        elif atype == "analyze_mix":
            # Handled separately by the caller; no param change, no render
            pass

    return p, render


@router.post("/render", response_model=JobResponse)
async def render_mix(
    project_id: str, body: RenderMixRequest, background: BackgroundTasks
) -> JobResponse:
    """Render a mix version (preview or full) as a background job."""
    params = {**DEFAULT_MIX_PARAMS, **body.mix_params}
    job = await jobs_db.create_job(project_id, job_type="mix_render")
    background.add_task(run_mix_job, job["id"], project_id, params, body.quality)
    return JobResponse(job_id=job["id"])


@router.post("/conversation", response_model=MixConversationResponse)
async def mix_conversation(
    project_id: str, body: MixConversationRequest
) -> MixConversationResponse:
    """
    Mix Room conversation. Interprets the user's reaction, updates mix params,
    and tells the client whether to render. If the user can't name the problem,
    the LLM can ask to analyze — we run analysis and let it suggest a fix.
    """
    history = [{"role": m.role, "content": m.content} for m in body.history]
    params = {**DEFAULT_MIX_PARAMS, **body.mix_params}

    # First pass
    messages = build_mix_room_messages(params, history, body.message)
    try:
        result = chat_structured(MIX_ROOM_SYSTEM, messages)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Frank lost the thread for a second — say that again?"
        ) from exc

    raw_actions = [
        a for a in result.get("actions", [])
        if isinstance(a, dict) and a.get("type") in _ALLOWED_ACTIONS
    ]

    # If the model asked to analyze, run analysis on the active mix and do a
    # second pass so it can suggest a concrete fix in plain language.
    if any(a.get("type") == "analyze_mix" for a in raw_actions):
        analysis = await _analyze_active_mix(project_id)
        messages = build_mix_room_messages(params, history, body.message, analysis)
        try:
            result = chat_structured(MIX_ROOM_SYSTEM, messages)
        except Exception:
            pass
        raw_actions = [
            a for a in result.get("actions", [])
            if isinstance(a, dict) and a.get("type") in _ALLOWED_ACTIONS and a.get("type") != "analyze_mix"
        ]

    new_params, render = apply_actions(params, raw_actions)
    actions = [ConversationAction(type=a["type"], params=a.get("params", {})) for a in raw_actions]

    return MixConversationResponse(
        message=result.get("message", ""),
        mix_params=new_params,
        actions=actions,
        render=render,
    )


def _download_and_analyze(url: str) -> dict:
    """Blocking download + analysis — run via asyncio.to_thread."""
    from app.services.audio import mixing
    from app.services.storage.signing import fetch_audio_bytes

    mix = mixing._load_stereo(fetch_audio_bytes(url, timeout=30))
    return mixing.analyze_mix(mix)


async def _analyze_active_mix(project_id: str) -> dict:
    """Analyze the active mix for 'something feels off' — off the event loop."""
    import asyncio

    latest = await mix_db.get_latest_mix(project_id)
    if not latest or not latest.get("render_url"):
        return {}
    try:
        return await asyncio.to_thread(_download_and_analyze, latest["render_url"])
    except Exception:
        return {}


@router.get("/versions", response_model=list[MixVersionResponse])
async def list_mix_versions(project_id: str) -> list[MixVersionResponse]:
    versions = await mix_db.list_mix_versions(project_id)
    return [
        MixVersionResponse(
            id=v["id"],
            project_id=v["project_id"],
            render_url=v.get("render_url"),
            label=v.get("label"),
            mix_params=v.get("mix_params") or {},
            created_at=str(v["created_at"]),
        )
        for v in versions
    ]


@router.post("/versions/active")
async def set_active_mix_version(
    project_id: str, body: SetActiveMixRequest
) -> dict:
    await projects_db.update_project_active_state(
        project_id, {"active_mix_id": body.mix_version_id}
    )
    return {"status": "ok", "active_mix_id": body.mix_version_id}
