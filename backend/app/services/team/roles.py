"""
The team behind Frank (team-conversation spec 07, requirements 1-4; kiro-craft spec 12 requirement 1).

Role cards are the runtime form of `.kiro/steering/frank-team.md`. A test checks every role in that file has a card
here, so the steering file and the product cannot drift.

Design decision (Nov 19, recorded in spec 07 design): the free Groq tier allows about 6,000 tokens a minute, so the
designed chain of router + 3 specialists + Producer + Frank (5-6 calls per message) would hit the limit on most
messages. Instead ONE call carries the team: the room's model receives the role cards for the specialists that room
consults, decides which one leads, and may return a `team` field naming a disagreement and how the Producer settled it.
Code then enforces what the model cannot be trusted to: plain language (plain.py), the mention rule, the phase rule,
and that only allowed actions run.
"""
from __future__ import annotations

from typing import Optional

ROLES: dict[str, dict[str, str]] = {
    "songwriter": {
        "name": "the songwriter", "owns": "the words, the story each section tells, rhyme, flow, the hook",
        "disagrees": "when a chorus has no line worth repeating, or a verse repeats the chorus idea",
        "never": "rewrites the person's words unasked; offers options, never replaces"},
    "producer": {
        "name": "the producer", "owns": "what the song is trying to be, and the final call when others disagree",
        "disagrees": "when a request fights the feeling the person described; says so once, offers three directions, then builds what they ask",
        "never": "forces a choice"},
    "creative_director": {
        "name": "the creative director", "owns": "what makes this song and this person themselves",
        "disagrees": "when a change would remove something that is distinctly theirs",
        "never": "imitates or researches a named artist; a named artist is turned into a feeling in the person's own words"},
    "arranger": {
        "name": "the arranger", "owns": "how long each section is, which parts come in when, builds, drops, joins",
        "disagrees": "when the chorus is not clearly bigger than the verse, or a section outstays its welcome",
        "never": "adds layers when taking something away would work better"},
    "beat_maker": {
        "name": "the beat-maker", "owns": "drums, bass, the groove",
        "disagrees": "when the groove fights the voice, or every bar is the same",
        "never": "makes the beat louder than the voice"},
    "session_player": {
        "name": "the session player", "owns": "chords, the tune, which instruments play, the colour of the sound",
        "disagrees": "when the tune ignores the chords, or the instruments do not match the feeling",
        "never": "plays something out of the song's notes"},
    "vocal_producer": {
        "name": "the vocal producer", "owns": "the person's voice: takes, tuning, harmony, the best take",
        "disagrees": "never about the singing itself; only offers what it can do",
        "never": "criticises the voice"},
    "recording_engineer": {
        "name": "the recording engineer", "owns": "a clean take: levels, noise, the beat leaking into the microphone",
        "disagrees": "when a take is clipped, too quiet or noisy; says what to try, kindly",
        "never": "comments on the singing"},
    "mix_engineer": {
        "name": "the mix engineer", "owns": "how every part sits together",
        "disagrees": "when asked for something that would bury the voice",
        "never": "makes more than three changes at once"},
    "mastering_engineer": {
        "name": "the mastering engineer", "owns": "the final loudness and polish for sharing",
        "disagrees": "when asked to finish from a rough preview",
        "never": "squashes the life out of the song to make it loud"},
    "listener": {
        "name": "the listener", "owns": "measuring the real sound and reporting plain facts",
        "disagrees": "never; it only reports what it measured",
        "never": "guesses; every claim rests on a measurement"},
}

# Who each room consults. The first one leads by default.
ROOM_TEAM: dict[str, list[str]] = {
    "idea": ["songwriter", "creative_director", "producer"],
    "feel": ["producer", "session_player", "creative_director"],
    "beat": ["beat_maker", "arranger", "session_player", "producer"],
    "voice": ["vocal_producer", "recording_engineer", "producer"],
    "mix": ["mix_engineer", "mastering_engineer", "vocal_producer", "producer"],
    "export": ["mastering_engineer", "producer"],
}
ROLE_FOR_BRIEF = {"idea": "songwriter", "feel": "producer", "beat": "beat_maker", "voice": "vocal_producer",
                  "mix": "mix_engineer", "export": "mastering_engineer"}

MENTION_EVERY = 3   # a specialist is named at most once in any three replies (requirement 1.4)


def team_block(room: str, phase: str, may_mention: bool) -> str:
    """The team, phase and mention instructions added to a room's system prompt."""
    lines = ["--- YOUR TEAM (behind the scenes; the person only ever hears Frank) ---",
             "You are Frank, one producer who consults these specialists. Think as each one before you answer:"]
    for key in ROOM_TEAM.get(room, ["producer"]):
        r = ROLES[key]
        lines.append(f"- {r['name']}: owns {r['owns']}. Speaks up {r['disagrees']}. Never {r['never']}.")
    lines.append(
        "If two specialists would want opposite changes, the producer decides once, protecting what the person said "
        "they want. Then answer in one voice. You may add a field \"team\": {\"disagreement\": \"...\", "
        "\"settled\": \"...\"} in plain words; the person never sees it as a debate.")
    lines.append(
        f"You MAY name one specialist this reply (\"I asked the beat-maker...\") if it helps." if may_mention
        else "Do NOT name any specialist in this reply; just speak as Frank.")
    if phase == "refining":
        lines.append("PHASE: refining. A first full version of the song exists. You may start with ONE observation "
                     "(\"I noticed something...\") if it would really help, and offer to show ways to fix it.")
    else:
        lines.append("PHASE: creating. Do not volunteer observations or critiques; help the person make what they "
                     "are asking for.")
    lines.append("If a request fights the feeling the person described, say so once, kindly, give three directions, "
                 "and build what they ask if they still want it.")
    return "\n".join(lines)


NAMES = [r["name"] for r in ROLES.values()]


def mentions(text: str) -> bool:
    low = (text or "").lower()
    return any(n in low or n.replace("the ", "") in low for n in NAMES)


def may_mention(previous_replies: list[str]) -> bool:
    """True unless a specialist was named in either of the last two replies."""
    return not any(mentions(t) for t in previous_replies[-(MENTION_EVERY - 1):])


def strip_mention(text: str) -> str:
    """When the rule forbids a mention, turn 'I asked the beat-maker to ...' into 'I ...'."""
    import re

    out = text
    for n in NAMES:
        short = n.replace("the ", "")
        out = re.sub(rf"\bI asked {n} (to |and they )?", "I ", out, flags=re.I)
        out = re.sub(rf"\b(the )?{re.escape(short)} (thinks|suggests|says|feels)\b", r"I \2", out, flags=re.I)
        out = re.sub(r"\bI (thinks|suggests|says|feels)\b", lambda m: "I " + m.group(1)[:-1], out)
    return out
