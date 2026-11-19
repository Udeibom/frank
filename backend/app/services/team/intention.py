"""
Protect the intention (team-conversation spec 07, requirement 3.1).

WHEN a request fights the person's stated feeling, the Producer says so ONCE, kindly, with the reason, and offers
three directions; IF the person insists, the system builds what they asked.

Pure parts (tested): which way the song leans (from the person's own words first, then the settled direction),
which way a change pulls, whether they clash, and the three directions as real typed operations.
The once-only memory and "they insisted" live in the decisions log.
"""
from __future__ import annotations

import re
from typing import Any, Optional

CALM = ("calm", "quiet", "hushed", "gentle", "soft", "intimate", "close", "whisper", "tender", "lonely", "still", "slow",
        "sleepy", "peaceful", "fragile", "bare", "sad", "melancholy", "kitchen at night", "lullaby")
BIG = ("big", "huge", "loud", "driving", "hype", "energetic", "anthem", "explosive", "euphoric", "wild", "party",
       "dancefloor", "powerful", "fast", "intense")
UP_OPS = {"bigger", "busier", "add_part"}
DOWN_OPS = {"smaller", "sparser", "remove_part"}
INSIST = re.compile(r"\b(do it anyway|just do it|i('m| am) sure|yes,? (do|make) it|go ahead|do what i (said|asked)|"
                    r"the first( one)?|option (1|one)|number one|exactly that)\b", re.I)
PICK_TWO = re.compile(r"\b(the second( one)?|option (2|two)|number two|half( of it| way)?|only in the chorus(es)?)\b", re.I)
PICK_THREE = re.compile(r"\b(the third( one)?|option (3|three)|number three|another way|the other way)\b", re.I)
KEY = "intention"


def song_lean(words: list[str], energy: Optional[float]) -> int:
    """-1 the person wants it gentle, +1 they want it big, 0 no clear lean. Their own words outrank the numbers."""
    text = " ".join(w.lower() for w in words if w)
    calm = sum(bool(re.search(rf"\b{re.escape(w)}", text)) for w in CALM)
    big = sum(bool(re.search(rf"\b{re.escape(w)}", text)) for w in BIG)
    if calm > big:
        return -1
    if big > calm:
        return 1
    if energy is not None:
        if energy <= 0.35:
            return -1
        if energy >= 0.75:
            return 1
    return 0


def _scope(op: dict, n_sections: int) -> int:
    s = op.get("section")
    if s is None:
        return n_sections
    return len(s) if isinstance(s, list) else 1


def request_pull(ops: list[dict], n_sections: int) -> int:
    """+1 a change that makes the song clearly bigger, -1 clearly smaller, 0 a small or mixed change."""
    up = sum(_scope(o, n_sections) for o in ops if o.get("op") in UP_OPS)
    down = sum(_scope(o, n_sections) for o in ops if o.get("op") in DOWN_OPS)
    wide = max(2, n_sections // 2)                      # half the song or more counts as clearly
    if up >= wide and up > down:
        return 1
    if down >= wide and down > up:
        return -1
    return 0


def _names(sections: list[dict]) -> list[str]:
    return [str(s.get("name", "")) for s in sections]


def three_directions(ops: list[dict], sections: list[dict], pull: int) -> list[dict]:
    """1. exactly what they asked; 2. part of it (choruses only, or verses only); 3. the same aim another way."""
    names = _names(sections)
    choruses = [i for i, n in enumerate(names) if n == "chorus"]
    verses = [i for i, n in enumerate(names) if n == "verse"]
    part_where = choruses if pull > 0 else verses
    half = [{**o, "section": part_where} for o in ops if o.get("op") in (UP_OPS | DOWN_OPS)] if part_where else []
    if pull > 0:
        before = [i - 1 for i in choruses if i > 0]
        other = [{"op": "add_fill", "section": before}] if before else [{"op": "bigger", "section": choruses[-1:]}] if choruses else []
        other_words = "keep it gentle and give the choruses a lift with a drum roll going into them"
        half_words = "make only the choruses bigger, so the verses stay gentle"
    else:
        other = [{"op": "sparser", "part": "drums", "section": verses}] if verses else []
        other_words = "keep its energy but let the drums breathe in the verses"
        half_words = "calm only the verses, so the choruses keep their size"
    out = [{"title": "Exactly what you asked", "operations": ops}]
    if half:
        out.append({"title": half_words, "operations": half})
    if other:
        out.append({"title": other_words, "operations": other})
    return out


def message(their_words: Optional[str], pull: int, directions: list[dict]) -> str:
    feel = f"\u201c{their_words}\u201d" if their_words else ("gentle and close" if pull > 0 else "big and full of energy")
    change = "bigger and busier" if pull > 0 else "smaller and quieter"
    options = "; ".join(f"{n}. {d['title'].lower() if n > 1 else 'do exactly that'}" for n, d in enumerate(directions, 1))
    return (f"Happy to. One thing first, so it's your choice: you described this song as {feel}, and making it "
            f"{change} across the song pulls away from that. I can {options}. Which would you like?")


def choice(text: str) -> Optional[int]:
    """What the reply to the question picked: 0 exactly that, 1 part of it, 2 another way, None not an answer."""
    if INSIST.search(text or ""):
        return 0
    if PICK_TWO.search(text or ""):
        return 1
    if PICK_THREE.search(text or ""):
        return 2
    return None


# ── the parts that read and write the song ───────────────────────────────

async def _their_words(project_id: str) -> tuple[list[str], Optional[str], Optional[float]]:
    from app.db import feel as feel_db
    from app.services.song import record as song_record

    intent = (await song_record.active_facet(project_id, "intent") or {}).get("text")
    feeling = await song_record.active_facet(project_id, "feeling") or {}
    words = [intent or "", *feeling.get("words", []), *feeling.get("loved_qualities", []), str(feeling.get("summary") or "")]
    latest = await feel_db.get_latest_fingerprint(project_id)
    energy = ((latest or {}).get("fingerprint") or {}).get("energy_level")
    return words, intent, float(energy) if isinstance(energy, (int, float)) else None


async def _pending(project_id: str) -> Optional[dict]:
    """The question asked last in this song, if the person has not answered it yet."""
    from app.db import song as song_db

    for d in await song_db.list_decisions(project_id, limit=20):
        opt = (d.options or [{}])[0]
        if opt.get("kind") == KEY:
            return None if d.chosen_option else {"id": d.id, **opt}
    return None


async def check(project_id: str, user_message: str, ops: list[dict], sections: list[dict]) -> tuple[Optional[str], Optional[list[dict]]]:
    """
    (message to say instead, operations to run instead). (None, None): nothing to do, run as asked.
    (message, []): hold the change and ask. (None, ops): they answered the question; run these.
    """
    from app.db import song as song_db
    from app.db.client import get_supabase

    try:
        pending = await _pending(project_id)
        if pending:
            pick = choice(user_message)
            if pick is not None and pick < len(pending["directions"]):
                get_supabase().table("song_decisions").update({"chosen_option": pending["directions"][pick]["title"],
                                                                "user_reaction": user_message[:300]}).eq("id", pending["id"]).execute()
                return None, pending["directions"][pick]["operations"]
            if ops:
                # they asked again instead of choosing: that is insisting, so build it
                get_supabase().table("song_decisions").update({"chosen_option": "Exactly what you asked",
                                                                "user_reaction": user_message[:300]}).eq("id", pending["id"]).execute()
                return None, None
        if not ops:
            return None, None
        pull = request_pull(ops, len(sections))
        words, intent, energy = await _their_words(project_id)
        lean = song_lean(words, energy)
        if pull == 0 or lean == 0 or pull == lean:
            return None, None
        for d in await song_db.list_decisions(project_id, limit=100):       # once per song and direction
            opt = (d.options or [{}])[0]
            if opt.get("kind") == KEY and opt.get("pull") == pull:
                return None, None
        directions = three_directions(ops, sections, pull)
        said = message(intent, pull, directions)
        await song_db.insert_decision(project_id, {
            "summary": "A change pulled away from the feeling they described", "rationale": said, "proposed_by": "producer",
            "options": [{"kind": KEY, "pull": pull, "directions": directions}], "user_reaction": user_message[:300],
        })
        return said, []
    except Exception:  # noqa: BLE001  the check is a courtesy; a failure never blocks what they asked
        import logging

        logging.getLogger(__name__).warning("intention check failed", exc_info=True)
        return None, None
