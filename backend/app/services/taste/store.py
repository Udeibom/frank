"""
Taste memory storage (spec 09). Every call names the user: taste belongs to the account, never to a project, and
one person never reads another's (the backend filters by user id; the tables also have row level security).
Forgetting deletes rows. Every function is best effort for callers that only record evidence: a failure to
remember taste never breaks what the person was doing.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.db.client import get_supabase
from app.services.taste import rules

log = logging.getLogger(__name__)


def _t(name: str):
    return get_supabase().table(name)


def owner_of(project_id: str) -> Optional[str]:
    rows = _t("projects").select("user_id").eq("id", project_id).limit(1).execute().data
    return rows[0]["user_id"] if rows else None


def _signals(user_id: str, topic: str) -> list[dict]:
    return (_t("taste_signals").select("*").eq("user_id", user_id).eq("topic", topic).order("created_at").execute().data or [])


def _learned(user_id: str, topic: str) -> Optional[dict]:
    rows = (_t("taste_preferences").select("*").eq("user_id", user_id).eq("topic", topic).neq("status", "user_stated")
            .limit(1).execute().data)
    return rows[0] if rows else None


def reevaluate(user_id: str, topic: str) -> Optional[dict]:
    """Apply the promotion and retirement rules to one topic and store the result."""
    rows = _signals(user_id, topic)
    sig = [rules.Signal(r["topic"], int(r["direction"]), r.get("project_id"), i) for i, r in enumerate(rows)]
    row = _learned(user_id, topic)
    current = rules.Outcome(row["status"], int(row["direction"]), float(row["strength"]), row["statement"]) if row else None
    out = rules.evaluate(sig, current)
    if out.status == "none":
        return None
    specialist = rules.TOPICS.get(topic, rules.TOPICS["other"])[0]
    statement = row["statement"] if row and row.get("edited_by_user") and out.direction == int(row["direction"]) else out.statement
    data = {"user_id": user_id, "specialist": specialist, "topic": topic, "direction": out.direction,
            "statement": statement, "strength": out.strength, "status": out.status}
    if row:
        return _t("taste_preferences").update(data).eq("id", row["id"]).execute().data[0]
    return _t("taste_preferences").insert(data).execute().data[0]


def add_signal(user_id: str, project_id: Optional[str], topic: str, direction: int, statement: str, source: str) -> None:
    if topic not in rules.TOPICS or direction not in (-1, 1):
        return
    try:
        specialist = rules.TOPICS[topic][0]
        _t("taste_signals").insert({"user_id": user_id, "project_id": project_id, "specialist": specialist, "topic": topic,
                                    "direction": direction, "statement": statement[:300], "source": source}).execute()
        if topic != "other":
            reevaluate(user_id, topic)
    except Exception:  # noqa: BLE001
        log.warning("could not record a taste signal", exc_info=True)


def add_user_stated(user_id: str, topic: str, direction: int, statement: str) -> Optional[dict]:
    """The person said it: it is a preference at once, in their own words."""
    try:
        specialist = rules.TOPICS.get(topic, rules.TOPICS["other"])[0]
        same = (_t("taste_preferences").select("id").eq("user_id", user_id).eq("status", "user_stated")
                .eq("statement", statement[:300]).limit(1).execute().data)
        if same:
            return same[0]
        return _t("taste_preferences").insert({"user_id": user_id, "specialist": specialist, "topic": topic, "direction": direction,
                                               "statement": statement[:300], "strength": 1.0, "status": "user_stated"}).execute().data[0]
    except Exception:  # noqa: BLE001
        log.warning("could not keep what the person said about their taste", exc_info=True)
        return None


def preferences(user_id: str, include_retired: bool = False) -> list[dict]:
    q = _t("taste_preferences").select("*").eq("user_id", user_id)
    rows = q.order("updated_at", desc=True).execute().data or []
    return [r for r in rows if include_retired or r["status"] in ("active", "user_stated")]


def edit(user_id: str, pref_id: str, statement: str) -> Optional[dict]:
    rows = (_t("taste_preferences").update({"statement": statement[:300], "edited_by_user": True})
            .eq("id", pref_id).eq("user_id", user_id).execute().data)
    return rows[0] if rows else None


def forget(user_id: str, pref_id: str) -> bool:
    """Delete the preference AND the evidence behind it (requirement 4.2)."""
    rows = _t("taste_preferences").select("*").eq("id", pref_id).eq("user_id", user_id).limit(1).execute().data
    if not rows:
        return False
    pref = rows[0]
    if pref["status"] != "user_stated":
        _t("taste_signals").delete().eq("user_id", user_id).eq("topic", pref["topic"]).execute()
    _t("taste_preferences").delete().eq("id", pref_id).eq("user_id", user_id).execute()
    return True


def forget_all(user_id: str) -> None:
    _t("taste_signals").delete().eq("user_id", user_id).execute()
    _t("taste_preferences").delete().eq("user_id", user_id).execute()


def for_role(user_id: str, role: Optional[str], limit: int = 5) -> list[dict[str, Any]]:
    """What the specialist for this room should know (strongest first); things they said always count."""
    try:
        rows = preferences(user_id)
    except Exception:  # noqa: BLE001
        return []
    mine = [r for r in rows if r["status"] == "user_stated" or r["specialist"] == role or role is None]
    mine.sort(key=lambda r: (r["status"] != "user_stated", -float(r.get("strength") or 0)))
    return mine[:limit]
