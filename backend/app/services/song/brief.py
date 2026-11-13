"""
The song brief (song-record spec, requirement 6).

One pure function turns a SongRecord into the text every LLM call receives as
song context. Same record in, same text out. The intent and the phase are never
trimmed; when the text is too long, older material goes first.

The brief is internal context for the model. The prompts still forbid quoting
its words to the user.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.models.song import Decision, SongRecord

DEFAULT_BUDGET_CHARS = 6000
MAX_DECISIONS = 12

# Which part of the record a specialist sees in full detail (others get a summary line).
ROLE_DETAIL: dict[str, str] = {
    "beat_maker": "beat",
    "arranger": "beat",
    "session_player": "beat",
    "vocal_producer": "vocal",
    "recording_engineer": "vocal",
    "mix_engineer": "mix",
    "mastering_engineer": "mix",
}


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))


def _melody_text(content: dict[str, Any]) -> str:
    """A hummed tune in everyday words. The model never gets note numbers, key names or speeds."""
    notes = content.get("performed_notes") or content.get("notes") or []
    state = "confirmed by the person" if content.get("confirmed") else "not confirmed yet"
    return f"a tune the person hummed, {len(notes)} notes long, {state}"


def _facet_text(record: SongRecord, facet: str) -> Optional[str]:
    content = record.facets.get(facet)
    if not content:
        return None
    if facet == "melody":
        return _melody_text(content)
    return _dump(content)


def _required_header(record: SongRecord) -> str:
    """Intent and phase: never trimmed."""
    intent = (record.facets.get("intent") or {}).get("text")
    lines = [
        "SONG BRIEF (internal context). Talk about the song in feelings and everyday words. "
        "Never repeat numbers, note names, key names, speeds or file addresses from this brief."
    ]
    lines.append(f"Phase: {record.phase}")
    lines.append(f"What they said they want: {intent}" if intent else "What they said they want: (not said yet)")
    return "\n".join(lines)


def _summary_line(label: str, value: Optional[dict[str, Any]], full: bool) -> Optional[str]:
    if not value:
        return None
    return f"{label}: {_dump(value)}" if full else f"{label}: present"


def _decision_line(d: Decision) -> str:
    chosen = d.chosen_option or "no choice yet"
    reaction = f"; reaction: {d.user_reaction}" if d.user_reaction else ""
    return f"- {d.summary} (by {d.proposed_by}; chosen: {chosen}{reaction})"


def _rejected_lines(decisions: list[Decision]) -> list[str]:
    out: list[str] = []
    for d in decisions:
        if d.user_reaction and d.user_reaction.lower().startswith("reject"):
            out.append(f"- {d.summary}")
    return out


def _render(
    record: SongRecord,
    role: Optional[str],
    decisions: list[Decision],
    lyrics_limit: Optional[int],
    detail: bool,
) -> str:
    focus = ROLE_DETAIL.get(role or "")
    parts: list[str] = [_required_header(record)]

    for facet, label in (
        ("feeling", "Feeling"),
        ("structure", "Structure"),
        ("melody", "Melody"),
        ("identity_brief", "Identity"),
        ("references", "References"),
    ):
        text = _facet_text(record, facet)
        if text:
            parts.append(f"{label}: {text}")

    if record.lyrics:
        lyrics = record.lyrics
        if lyrics_limit is not None and len(lyrics) > lyrics_limit:
            lyrics = lyrics[:lyrics_limit].rstrip() + " ..."
        parts.append(f"Lyrics:\n{lyrics}")
    else:
        parts.append("Lyrics: none yet")

    if record.fingerprint:
        parts.append(f"Musical direction (fingerprint): {_dump(record.fingerprint)}")

    for label, key, value in (
        ("Beat", "beat", record.beat),
        ("Vocal", "vocal", record.vocal),
        ("Mix", "mix", record.mix),
    ):
        line = _summary_line(label, value, full=(detail or focus == key))
        parts.append(line if line else f"{label}: none yet")

    if decisions:
        parts.append("Recent decisions (newest first):\n" + "\n".join(_decision_line(d) for d in decisions))
    rejected = _rejected_lines(decisions)
    if rejected:
        parts.append("Already rejected (do not offer again unchanged):\n" + "\n".join(rejected))

    return "\n".join(parts)


def build_brief(
    record: SongRecord,
    role: Optional[str] = None,
    budget_chars: int = DEFAULT_BUDGET_CHARS,
) -> str:
    """
    Build the song brief. If it is over `budget_chars`, trim in this order:
    older decisions, then the lyrics, then detail on beat/vocal/mix, then facets.
    The intent and the phase are never trimmed, so the result can only exceed the
    budget when those alone do.
    """
    decisions = list(record.decisions[:MAX_DECISIONS])
    lyrics_limit: Optional[int] = None
    detail = True

    text = _render(record, role, decisions, lyrics_limit, detail)
    if len(text) <= budget_chars:
        return text

    # 1. drop the oldest decisions one at a time
    while decisions and len(text) > budget_chars:
        decisions = decisions[:-1]
        text = _render(record, role, decisions, lyrics_limit, detail)
    if len(text) <= budget_chars:
        return text

    # 2. shorten the lyrics by halves
    limit = len(record.lyrics or "")
    while limit > 0 and len(text) > budget_chars:
        limit //= 2
        lyrics_limit = limit
        text = _render(record, role, decisions, lyrics_limit, detail)
    if len(text) <= budget_chars:
        return text

    # 3. summarise beat / vocal / mix
    detail = False
    text = _render(record, role, decisions, lyrics_limit, detail)
    if len(text) <= budget_chars:
        return text

    # 4. last resort: keep only the always-kept header
    return _required_header(record)
