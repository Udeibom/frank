"""
Plain references to versions (spec 08, requirement 5.2; design "Version resolver").

resolve("give me the second version back", versions, decisions) -> Resolution. Versions are dicts with id, label,
created_at and (for beats) params.changes. The answer is always a version that exists, or two candidates to play
and ask about, or nothing (the text was not about an earlier version).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Optional

ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
            "ninth": 9, "tenth": 10, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
STOP = {"the", "a", "an", "i", "my", "me", "it", "one", "version", "back", "give", "go", "to", "before", "changed",
        "change", "that", "when", "we", "from", "of", "in", "on", "with", "please", "can", "you", "bring", "put"}


@dataclass
class Resolution:
    version: Optional[dict] = None
    candidates: list[dict] = field(default_factory=list)   # two to play and ask about
    reason: str = ""


def _when(v: dict) -> datetime:
    raw = v.get("created_at")
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOP and len(w) > 2}


VERSION_INTENT = re.compile(
    r"\b(versions?|undo|go back|back to|put (?:it|that|the \w+) back|bring (?:it|that) back|give (?:me )?(?:\w+ ){0,4}back"
    r"|(?:the )?one (?:before|from yesterday|with)|the original|previous one|earlier one|the old one|v\d{1,2})\b"
)


def is_about_versions(text: str) -> bool:
    """Only clear requests for an earlier version: "make the chorus bigger before the bridge" is not one."""
    return bool(VERSION_INTENT.search(text.lower()))


def _about(v: dict) -> str:
    changes = ((v.get("params") or {}).get("changes")) or []
    return " ".join([str(v.get("label") or ""), *map(str, changes)]).lower()


def resolve(
    text: str, versions: list[dict], decisions: Optional[list[dict]] = None, active_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Resolution:
    if not versions or not text.strip():
        return Resolution(reason="nothing")
    t = text.lower()
    ordered = sorted(versions, key=_when)                 # oldest first: "the first version" is the oldest
    by_id = {v["id"]: v for v in ordered}
    active = by_id.get(active_id) if active_id else ordered[-1]

    # "the version before I changed the chorus": the newest version made before the change that mentions it
    m = re.search(r"before (?:i|we|you) (?:changed|made|added|took|moved|tried|did)\s+(.+)", t)
    if m:
        topic = _words(m.group(1))
        hits: list[tuple[datetime, dict]] = []
        for v in ordered:
            if topic and topic & _words(_about(v)):
                hits.append((_when(v), v))
        for d in decisions or []:
            if topic and topic & _words(" ".join([str(d.get("summary", "")), str(d.get("chosen_option") or "")])):
                hits.append((_when(d), {}))
        if hits:
            moment = min(w for w, _ in hits)
            earlier = [v for v in ordered if _when(v) < moment]
            if earlier:
                return Resolution(version=earlier[-1], reason="before_change")
        return Resolution(candidates=ordered[-2:][::-1] if len(ordered) >= 2 else ordered, reason="unclear_change")

    # ordinals: "the second version", "version 2", "v2"
    n = next((ORDINALS[w] for w in re.findall(r"[a-z0-9]+", t) if w in ORDINALS), None)
    if n is None:
        m = re.search(r"\b(?:version|v|beat v|mix v)\s?(\d{1,2})\b", t)
        n = int(m.group(1)) if m else None
    if n is not None:
        if 1 <= n <= len(ordered):
            return Resolution(version=ordered[n - 1], reason="ordinal")
        return Resolution(candidates=ordered[-2:][::-1], reason="ordinal_missing")

    # "the original", "the very first"
    if "original" in t or "very first" in t or "the first one" in t:
        return Resolution(version=ordered[0], reason="ordinal")

    # "previous", "the one before", "undo", "go back": the one before the active version
    if any(w in t for w in ("previous", "undo", "one before", "go back", "last one", "before this", "put it back")):
        i = ordered.index(active) if active in ordered else len(ordered) - 1
        if i > 0:
            return Resolution(version=ordered[i - 1], reason="previous")
        return Resolution(reason="no_earlier")

    # dates: "yesterday", "this morning"
    now = now or datetime.now(timezone.utc)
    if "yesterday" in t:
        day = (now - timedelta(days=1)).date()
        same = [v for v in ordered if _when(v).date() == day]
        if len(same) == 1:
            return Resolution(version=same[0], reason="date")
        if same:
            return Resolution(candidates=same[-2:][::-1], reason="date_many")
        return Resolution(reason="date_none")

    # a label or change the person names: "the one with the strings"
    want = _words(t)
    if want:
        scored = sorted(
            ((len(want & _words(_about(v))) + SequenceMatcher(None, t, str(v.get("label") or "").lower()).ratio() * 0.5, v)
             for v in ordered), key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] >= 1.0:
            if len(scored) > 1 and scored[1][0] >= scored[0][0] - 0.1:
                return Resolution(candidates=[scored[0][1], scored[1][1]], reason="label_tie")
            return Resolution(version=scored[0][1], reason="label")
    return Resolution(reason="nothing")


def as_plain(v: dict) -> dict[str, Any]:
    return {"id": v.get("id"), "label": v.get("label"), "render_url": v.get("render_url"), "created_at": str(v.get("created_at"))}
