"""
Frank never says it did what it didn't (core-path spec 15, requirement 2.3).

On 22 Nov the person said "it's too fast" three times. Frank answered "I slowed the groove" while the change it
made only loosened the drums: the speed never moved. Now a request about speed always becomes a real speed
change, and a reply that talks about speed without one is replaced with the truth.
"""
from __future__ import annotations

import re
from typing import Optional

_SLOWER = re.compile(r"\b(too fast|too quick|too rushed|rushed|rushing|slow (it )?down|slower|more slowly|calmer pace|"
                     r"slow(er)? speed|reduce the speed|less fast|half ?time)\b", re.I)
_FASTER = re.compile(r"\b(too slow|dragging|drags|speed (it )?up|faster|quicker|more pace|pick up the pace|"
                     r"increase the speed|double ?time)\b", re.I)
_SPEED_TALK = re.compile(r"\b(slow(ed|er|ing)?|fast(er)?|speed|pace|tempo|quicker|bpm)\b", re.I)
_A_LOT = re.compile(r"\b(much|way|a lot|really|very|too)\b", re.I)


def speed_wanted(text: str) -> Optional[tuple[str, str]]:
    """("slower"|"faster", "a_little"|"a_lot") when the person asks about speed, else None."""
    slower, faster = bool(_SLOWER.search(text or "")), bool(_FASTER.search(text or ""))
    if slower == faster:
        return None
    return ("slower" if slower else "faster", "a_lot" if _A_LOT.search(text or "") else "a_little")


def talks_about_speed(text: str) -> bool:
    return bool(_SPEED_TALK.search(text or ""))


def fix_speed(person: str, reply: str, ops: list[dict]) -> tuple[str, list[dict]]:
    """
    The reply and operations, made honest about speed. A speed request with no speed change gets one added; a
    reply that talks about speed when nothing changes speed is replaced.
    """
    has_speed = any(isinstance(o, dict) and o.get("op") in ("slower", "faster") for o in ops)
    wanted = speed_wanted(person)
    if wanted and not has_speed:
        op, amount = wanted
        ops = [*ops, {"op": op, "amount": amount}]
        has_speed = True
        size = "a lot " if amount == "a_lot" else "a little "
        reply = (f"I'm making the whole song {size}{'slower' if op == 'slower' else 'faster'} now, every part and your "
                 "tune with it. Give it a listen when it's ready. Does that feel better?")
    if talks_about_speed(reply) and not has_speed:
        reply = ("I've made the change you can see below. The speed is still the same. Do you want the song slower or faster?"
                 if ops else "I haven't changed the speed. Do you want the song slower or faster?")
    return reply, ops
