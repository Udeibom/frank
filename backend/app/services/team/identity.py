"""
The Creative Director (spec 10): protects what makes THIS song and THIS person themselves.

- The identity brief: one model call over the person's own words and choices, written as a new version of the
  `identity_brief` facet, at most once every IDENTITY_EVERY seconds per song. Every specialist sees it (brief).
- Named artists become feelings: when the person names an artist or a song, the room asks ONE question about what
  they love in it; the feeling words go to the `feeling` facet, the name to `references` marked "feeling only"
  (the brief never shows names, and nothing aims at sounding like anyone). No role has a web tool.
- The drift check: pure rules that say, once, when a change would remove something that is theirs.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

IDENTITY_EVERY = 600
_last_run: dict[str, float] = {}

IDENTITY_SYSTEM = """You are the Creative Director on Frank's team. You protect what makes this song and this person
themselves. From their own messages, words and choices, write what is distinctively THEIRS, in plain everyday words.
Never compare them to any artist. Never use music terms.
Reply as JSON only:
{"own_words": ["short phrases they actually used about the song"], "own_images": ["images from their lyrics or talk"],
 "voice": "one sentence on how they sing or want their voice to feel, or empty",
 "keep": ["things to protect, e.g. 'the line about the porch light', 'your voice raw, not tuned hard'"],
 "avoid": ["things they rejected"]}
At most 6 items per list. Only what the material shows; empty lists are fine."""

TEAM_RULE = """NAMED ARTISTS: if the person names an artist, a band or a song as a reference, do not describe, research
or copy that artist's sound, and do not lecture them. Ask ONE warm question about what they love in it, in feeling
words (close, hushed, wide, raw, bouncy...). In your JSON add "named_reference": "<the name>" when they named one, and
"loved_qualities": ["feeling words"] when they told you what they love. Build from the feeling, never the name."""


def _strings(value: Any, limit: int = 6, length: int = 160) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip()[:length] for v in value if isinstance(v, (str, int, float)) and str(v).strip()][:limit]


def clean_identity(raw: dict[str, Any]) -> dict[str, Any]:
    from app.services.team import plain

    out = {k: [plain.guard(x) for x in _strings(raw.get(k))] for k in ("own_words", "own_images", "keep", "avoid")}
    out["voice"] = plain.guard(str(raw.get("voice") or "").strip()[:240])
    return out


async def _material(project_id: str) -> str:
    from app.db import song as song_db
    from app.services.song import record as song_record
    from app.services.team import conversation_store as convo

    record = await song_record.get_record(project_id)
    said: list[str] = []
    for room in ("idea", "feel", "beat", "voice", "mix"):
        try:
            said += [t["content"] for t in await convo.history(project_id, room) if t["role"] == "user"]
        except Exception:  # noqa: BLE001
            pass
    decisions = await song_db.list_decisions(project_id, limit=20)
    lines = [f"What they said the song is: {(record.facets.get('intent') or {}).get('text') or '(not said yet)'}",
             f"Lyrics:\n{record.lyrics or '(none yet)'}",
             "Their own messages:", *[f"- {m[:200]}" for m in said[-40:]],
             "Their choices:", *[f"- {d.summary}" + (f" (said: {d.user_reaction})" if d.user_reaction else "") for d in decisions]]
    if record.vocal:
        lines.append(f"Their voice so far: {record.vocal}")
    return "\n".join(lines)


async def refresh(project_id: str, force: bool = False) -> Optional[dict[str, Any]]:
    """Write a new identity brief version. Throttled; never raises."""
    from app.services.llm.groq_client import chat_structured
    from app.services.song import store

    now = time.monotonic()
    if not force and now - _last_run.get(project_id, -IDENTITY_EVERY) < IDENTITY_EVERY:
        return None
    _last_run[project_id] = now
    try:
        material = await _material(project_id)
        raw = await asyncio.to_thread(chat_structured, IDENTITY_SYSTEM, [{"role": "user", "content": material}], 0.3)
        content = clean_identity(raw if isinstance(raw, dict) else {})
        if not any(content[k] for k in ("own_words", "own_images", "keep")) and not content["voice"]:
            return None
        await store.write_facet(project_id, "identity_brief", content, author="creative_director",
                                operation="identity_refresh", label="What makes this song yours")
        return content
    except Exception:  # noqa: BLE001
        log.warning("could not refresh the identity brief", exc_info=True)
        return None


def refresh_soon(project_id: str) -> None:
    """After a major choice (lyrics saved, a direction chosen, a take kept): refresh without making anyone wait."""
    try:
        asyncio.get_running_loop().create_task(refresh(project_id))
    except RuntimeError:
        pass


REFERENCE = re.compile(
    r"\b(?:sound|sounds|sounding|feel|feels|vibe|vibes|something|kind of|kinda|more|just|be)?\s*(?:like|by|from|inspired by)\s+"
    r"((?:[A-Z][\w'\u2019.&-]*)(?:\s+(?:[A-Z][\w'\u2019.&-]*|of|the|and|&)){0,4})")
NOT_NAMES = {"I", "I'm", "Me", "My", "It", "The", "A", "This", "That", "We", "You", "Frank", "Something"}
ASK = ("I love that you have something in mind. What is it about that music that pulls you in: how close and quiet "
       "it feels, how big and wide, how raw, or the way it moves?")
FEELING_WORDS = ("close", "quiet", "hushed", "whisper", "intimate", "soft", "gentle", "warm", "dark", "moody", "eerie",
                 "dreamy", "wide", "big", "huge", "spacious", "open", "raw", "rough", "honest", "bouncy", "groovy", "moves",
                 "driving", "slow", "floating", "sad", "happy", "bright", "lonely", "tender", "angry", "hopeful")


def detect_reference(text: str) -> Optional[str]:
    """'make it sound like Billie Eilish' -> 'Billie Eilish'. Names are capitalised; the sentence start is not a name."""
    for m in REFERENCE.finditer(text or ""):
        name = m.group(1).strip(" .,'")
        words = name.split()
        while words and words[-1] in {"of", "the", "and", "&"}:
            words.pop()
        if words and (words[0] not in NOT_NAMES or (words[0] == "The" and len(words) > 1)):
            return " ".join(words)[:80]
    return None


def feelings_in(text: str) -> list[str]:
    low = (text or "").lower()
    return [w for w in FEELING_WORDS if re.search(rf"\b{w}", low)][:8]


async def handle_reply(project_id: str, result: dict[str, Any], user_message: str = "", room: str = "") -> None:
    """
    A named artist becomes a feeling (requirement 2). When the person names one, the reply is ONE plain question
    about what they love in it (no description of anyone's sound, no lecture) and the song's direction waits for
    their answer. Their answer's feeling words are kept; the name is kept only as "feeling only".
    """
    from app.services.song import record as song_record
    from app.services.song import store
    from app.services.team import conversation_store as convo

    name = str(result.pop("named_reference", "") or "").strip()[:80] or (detect_reference(user_message) or "")
    loved = [w.lower() for w in _strings(result.pop("loved_qualities", None), 8, 40)]
    if name:
        result["message"] = ASK
        result.pop("fingerprint_update", None)          # nothing moves toward anyone's sound
        result["actions"] = []
    elif room and not loved:
        try:
            last = [t for t in await convo.history(project_id, room) if t["role"] == "assistant"][-1:]
        except Exception:  # noqa: BLE001
            last = []
        if last and last[0]["content"].strip() == ASK:
            loved = feelings_in(user_message)
    if not name and not loved:
        return
    try:
        if loved:
            feeling = dict(await song_record.active_facet(project_id, "feeling") or {})
            feeling["loved_qualities"] = list(dict.fromkeys([*feeling.get("loved_qualities", []), *loved]))[:12]
            await store.write_facet(project_id, "feeling", feeling, author="creative_director", operation="loved_qualities")
        refs = dict(await song_record.active_facet(project_id, "references") or {"items": []})
        items = list(refs.get("items", []))
        if name and not any(i.get("name", "").lower() == name.lower() for i in items):
            items.append({"name": name, "use": "feeling_only", "loved": loved})
        elif loved and items:
            items[-1] = {**items[-1], "loved": list(dict.fromkeys([*items[-1].get("loved", []), *loved]))}
        if items != refs.get("items"):
            await store.write_facet(project_id, "references", {"items": items}, author="creative_director", operation="named_reference")
    except Exception:  # noqa: BLE001
        log.warning("could not keep the named reference as a feeling", exc_info=True)


# ── the drift check (requirement 3) ──────────────────────────────────────

RAW_VOICE = re.compile(r"\b(raw|natural|untuned|not tuned|real|as i sing|imperfect)\b", re.I)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def drift_notes(
    identity: Optional[dict[str, Any]], *, tune_mode: Optional[str] = None, direction: Optional[dict[str, Any]] = None,
    their_tune: bool = False, old_text: Optional[str] = None, new_text: Optional[str] = None,
    hates_tuning: bool = False,
) -> list[str]:
    """One plain sentence per thing the change would take away from them, with a way to keep it. Pure."""
    identity = identity or {}
    notes: list[str] = []
    keep = " ".join(identity.get("keep", []) + [identity.get("voice", "")])
    if tune_mode == "full" and (hates_tuning or RAW_VOICE.search(keep)):
        notes.append("You said you want your voice to sound like you, and \"Lock it in\" makes it sound tuned. "
                     "\"Just the obvious bits\" keeps your character. Your call.")
    if direction and their_tune:
        for a in direction.get("actions") or []:
            if a.get("op") == "remove_part" and a.get("part") == "melody":
                notes.append("That would take your own tune out of that part. I can keep your tune and change the rest instead.")
                break
    if old_text is not None and new_text is not None:
        new = _norm(new_text)
        for image in identity.get("own_images", []) + identity.get("own_words", []):
            img = _norm(image)
            if len(img) >= 4 and img in _norm(old_text) and img not in new:
                notes.append(f"This version loses \u201c{image}\u201d, which is yours. Want to keep that line in?")
                break
    return list(dict.fromkeys(notes))


async def context(project_id: str) -> tuple[dict[str, Any], bool]:
    """(identity brief, does the person dislike sounding tuned) for the drift check. Never raises."""
    from app.services.song import record as song_record

    identity: dict[str, Any] = {}
    hates = False
    try:
        identity = dict(await song_record.active_facet(project_id, "identity_brief") or {})
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.taste.signals import preference_map

        hates = (await preference_map(project_id)).get("autotune_amount") == -1
    except Exception:  # noqa: BLE001
        pass
    return identity, hates


async def mention_once(project_id: str, key: str, note: str) -> Optional[str]:
    """The Creative Director says a drift note ONCE per song and thing (requirement 3.1); recorded as a decision."""
    from app.db import song as song_db

    try:
        for d in await song_db.list_decisions(project_id, limit=100):
            if (d.options or [{}])[0].get("kind") == "drift" and (d.options or [{}])[0].get("key") == key:
                return None
        await song_db.insert_decision(project_id, {"summary": "The Creative Director spoke up", "rationale": note,
                                                   "proposed_by": "creative_director", "options": [{"kind": "drift", "key": key}]})
    except Exception:  # noqa: BLE001
        log.warning("could not record a drift note", exc_info=True)
    return note


SECTION_HEAD = re.compile(r"^\s*[\[(]?\s*(intro|verse|pre-chorus|prechorus|chorus|hook|refrain|bridge|outro|ending)"
                          r"\s*\d*\s*[\])]?\s*:?\s*$", re.I)


def section_text(lyrics: str, label: str) -> Optional[str]:
    """The lines under a heading like "Chorus" / "[Chorus]" / "Chorus:" in the person's lyrics, if there is one."""
    if not label.strip() or not lyrics.strip():
        return None
    out: list[str] = []
    inside = False
    for line in lyrics.splitlines():
        m = SECTION_HEAD.match(line)
        if m:
            if inside:
                break
            inside = m.group(1).strip().lower() == label.strip().lower()
            continue
        if inside:
            out.append(line)
    text = "\n".join(out).strip()
    return text or None
