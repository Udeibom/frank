"""
Where taste evidence comes from (spec 09, requirement 1.1). Each hook is fire-and-forget: it finds the song's
owner, turns what happened into signals, and never raises.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.services.taste import rules, store

log = logging.getLogger(__name__)


async def _owner(project_id: str) -> Optional[str]:
    try:
        return await asyncio.to_thread(store.owner_of, project_id)
    except Exception:  # noqa: BLE001
        return None


async def record_choice(project_id: str, direction: dict[str, Any], section_names: list[str], experiment: bool) -> None:
    """A direction (or experiment) the person chose after hearing it. Choosing one of three says what they
    liked, not what they disliked, so the others are not counted against anything."""
    user = await _owner(project_id)
    if not user:
        return
    source = "won an experiment" if experiment else "chose a direction"
    for topic, d in rules.signals_for_direction(direction.get("kind", "beat"), direction.get("actions") or [], section_names):
        await asyncio.to_thread(store.add_signal, user, project_id, topic, d, f"Chose \u201c{direction.get('title')}\u201d", source)


async def record_mismatch(project_id: str, measured: list[str], said: str) -> None:
    """The person heard something different from what was measured (Listener requirement 6)."""
    user = await _owner(project_id)
    if user:
        await asyncio.to_thread(store.add_signal, user, project_id, "other", 1,
                                f"Heard \u201c{said}\u201d where I measured: {'; '.join(measured)[:200]}", "measurement mismatch")


async def record_self(project_id: str, text: str) -> Optional[str]:
    """'I hate autotune': becomes a preference at once. Returns the kept sentence."""
    found = rules.from_self(text)
    if not found:
        return None
    user = await _owner(project_id)
    if not user:
        return None
    topic, d, sentence = found
    await asyncio.to_thread(store.add_user_stated, user, topic, d, sentence)
    return sentence


async def record_texture(project_id: str, fingerprint: dict[str, Any], approved: bool) -> None:
    """A Feel Lab texture approved (+) or passed over (-): what it was like says something about taste."""
    user = await _owner(project_id)
    if not user:
        return
    sign = 1 if approved else -1
    for key, topic in (("brightness", "brightness"), ("energy_level", "energy"), ("warmth", "warm_sounds")):
        v = fingerprint.get(key)
        if isinstance(v, (int, float)) and abs(v - 0.5) >= 0.2:
            await asyncio.to_thread(store.add_signal, user, project_id, topic, sign * (1 if v > 0.5 else -1),
                                    f"{'Liked' if approved else 'Passed on'} a sound in the Feel Lab", "texture")


async def block_for(project_id: str, role: Optional[str]) -> str:
    """The brief's "What this artist tends to like" lines for a room's specialist (requirement 3.1)."""
    user = await _owner(project_id)
    if not user:
        return ""
    rows = await asyncio.to_thread(store.for_role, user, role)
    if not rows:
        return ""
    lines = "\n".join(f"- {r['statement']}" for r in rows)
    return ("--- WHAT THIS ARTIST TENDS TO LIKE (learned over several songs, or said by them) ---\n" + lines +
            "\nUse this to choose what to try first, and you may mention it once ('you usually like ..., so I started "
            "there'). Never use it to refuse or argue with what they ask for now.")


async def preference_map(project_id: str) -> dict[str, int]:
    """topic -> direction of the owner's active preferences, for ordering directions (requirement 3.2)."""
    user = await _owner(project_id)
    if not user:
        return {}
    try:
        rows = await asyncio.to_thread(store.preferences, user)
    except Exception:  # noqa: BLE001
        return {}
    return {r["topic"]: int(r["direction"]) for r in rows if r["topic"] != "other"}
