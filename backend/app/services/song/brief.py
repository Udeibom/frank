"""
The song brief (song-record spec, requirement 6).

One pure function turns a SongRecord into the text every LLM call receives as
song context. Same record in, same text out. The intent and the phase are never
trimmed; when the text is too long, older material goes first.

The brief is internal context for the model. The prompts still forbid quoting
its words to the user.
"""

from __future__ import annotations

from app.services.team.plain import find_jargon, guard

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
    if facet == "references":
        return _references_text(content)
    if facet == "identity_brief":
        return _identity_text(content)
    return guard(_dump(content))


def _references_text(content: dict[str, Any]) -> Optional[str]:
    """
    Music the person named becomes only the FEELING they love in it (creative-director spec 10, requirement 2).
    The names never reach any prompt: nobody on the team aims at sounding like someone.
    """
    loved = [w for item in content.get("items", []) for w in item.get("loved", []) if isinstance(w, str)]
    # Differences Frank measured between a reference and this song (frankenstein spec 14, 6.2); they never name it.
    diffs = [d for item in content.get("items", []) if item.get("active", True)
             for d in item.get("differences", []) if isinstance(d, str) and not find_jargon(d)][:3]
    parts = []
    if loved:
        parts.append("things they love in music they pointed at: " + ", ".join(dict.fromkeys(loved)))
    if diffs:
        parts.append("compared with that music, " + " ".join(diffs).lower())
    return "; ".join(parts) or None


def _identity_text(content: dict[str, Any]) -> Optional[str]:
    """What makes this song theirs, in plain words (spec 10, requirement 1)."""
    bits = []
    for key, label in (("own_words", "their own words"), ("own_images", "their images"), ("keep", "keep"), ("avoid", "avoid")):
        vals = [v for v in content.get(key, []) if isinstance(v, str)]
        if vals:
            bits.append(f"{label}: " + "; ".join(vals[:6]))
    if content.get("voice"):
        bits.append(f"their voice: {content['voice']}")
    return " | ".join(bits) if bits else None


def _required_header(record: SongRecord) -> str:
    """Intent and phase: never trimmed."""
    intent = (record.facets.get("intent") or {}).get("text")
    lines = [
        "SONG BRIEF (internal context). Talk about the song in feelings and everyday words. "
        "Never repeat numbers, note names, key names, speeds, file addresses or technical sound terms (echo settings, "
        "smoothing, tone settings, stems, loudness) from this brief; say them in everyday words."
    ]
    lines.append(f"Phase: {record.phase}")
    lines.append(f"What they said they want: {intent}" if intent else "What they said they want: (not said yet)")
    return "\n".join(lines)


# ─── Records in everyday words (frankenstein spec 14, task 57) ──────────────────────────────────────────────
# The fingerprint and the beat, vocal and mix records used to be dumped raw (tempo_bpm, key, gain_db). Each is
# now described in words; section numbers stay, because the team's actions point at sections by number.

def _scale(value: Any, low: str, mid: str, high: str) -> Optional[str]:
    if not isinstance(value, (int, float)):
        return None
    return low if value < 0.35 else (high if value > 0.65 else mid)


def _fingerprint_text(fp: dict[str, Any]) -> str:
    bits: list[str] = []
    bpm = fp.get("tempo_bpm")
    if isinstance(bpm, (int, float)):
        bits.append("unhurried" if bpm < 80 else ("quick" if bpm > 115 else "a walking pace"))
    if isinstance(fp.get("tempo_feel"), str):
        bits.append(f"feels {fp['tempo_feel']}")
    mode = fp.get("mode") or ""
    if mode == "minor" or "minor" in str(fp.get("key", "")).lower():
        bits.append("darker, more wistful notes")
    elif mode == "major" or "major" in str(fp.get("key", "")).lower():
        bits.append("brighter, more open notes")
    elif mode == "modal":
        bits.append("notes with an unusual colour")
    for key, words in (("energy_level", ("calm", "medium energy", "high energy")),
                       ("density", ("sparse", "moderately full", "full and busy")),
                       ("brightness", ("dark sounding", "neither dark nor bright", "bright sounding")),
                       ("warmth", ("cool", "fairly warm", "warm"))):
        word = _scale(fp.get(key), *words)
        if word:
            bits.append(word)
    near = [w for w in fp.get("genre_proximity") or [] if isinstance(w, str)]
    if near:
        bits.append("leans toward " + ", ".join(near[:4]))
    hints = [w for w in fp.get("instrumentation_hints") or [] if isinstance(w, str)]
    if hints:
        bits.append("instruments: " + ", ".join(hints[:5]))
    return "; ".join(bits) or "set, nothing described yet"


def _length_word(bars: Any) -> str:
    if not isinstance(bars, (int, float)):
        return ""
    return "short" if bars <= 4 else ("long" if bars > 8 else "medium length")


def _beat_text(beat: dict[str, Any]) -> str:
    out = [str(beat.get("label") or "a beat")]
    for s in beat.get("sections") or []:
        layers = ", ".join(str(x) for x in (s.get("layers") or [])) or "nothing playing"
        length = _length_word(s.get("bars"))
        out.append(f"section {s.get('index')} {s.get('name') or ''} ({', '.join(x for x in (length, layers) if x)})")
    lead = beat.get("lead") or {}
    if lead.get("used"):
        where = ", ".join(str(i) for i in lead.get("sections") or [])
        out.append(f"their hummed tune plays in section {where}" + (", shortened to fit" if lead.get("cut") else ""))
    elif lead:
        out.append("their hummed tune is not playing in this beat")
    return "; ".join(out)


def _vocal_text(vocal: dict[str, Any]) -> str:
    n = vocal.get("takes_recorded") or 0
    out = [f"{n} take{'s' if n != 1 else ''} recorded", f"playing: {vocal.get('active', 'none chosen')}"]
    if vocal.get("tuned"):
        out.append("tuned")
    t = vocal.get("active_take") or {}
    if t.get("kind") and t["kind"] != "take":
        out.append(f"made by {str(t['kind']).replace('_', ' ')}")
    if t.get("sections"):
        out.append("covers " + ", ".join(str(x) for x in t["sections"]))
    on = t.get("on_the_notes")
    if isinstance(on, (int, float)):
        out.append("almost every note lands on the song's notes" if on >= 0.9 else
                   ("most notes land on the song's notes" if on >= 0.7 else "quite a few notes drift off the song's notes"))
    ms = t.get("sits_behind_beat_ms")
    if isinstance(ms, (int, float)):
        out.append("sings right with the beat" if abs(ms) < 15 else
                   ("sings a little behind the beat" if ms > 0 else "sings a little ahead of the beat"))
    if t.get("beat_taken_out"):
        out.append("the beat that got into the mic was taken out")
    elif t.get("beat_in_the_mic"):
        out.append("the beat got into the mic")
    return "; ".join(out)


def _mix_text(mix: dict[str, Any]) -> str:
    p = mix.get("params") or {}
    out = [str(mix.get("label") or "a mix")]
    v, b = p.get("vocal_gain_db"), p.get("beat_gain_db")
    if isinstance(v, (int, float)) and isinstance(b, (int, float)):
        gap = v - b
        out.append("voice well above the music" if gap > 4 else
                   ("voice under the music" if gap < -1 else "voice sitting just above the music"))
    for who, key in (("voice", "vocal_effects"), ("music", "beat_effects")):
        fx = [str(e).replace("_", " ") for e in p.get(key) or []]
        if fx:
            out.append(f"{who} made: " + ", ".join(fx))
    if p.get("harmony_enabled"):
        out.append("harmony voice on")
    changed = p.get("section_gain_db") or {}
    if changed:
        louder = [k for k, v in changed.items() if isinstance(v, (int, float)) and v > 0]
        quieter = [k for k, v in changed.items() if isinstance(v, (int, float)) and v < 0]
        if louder:
            out.append("made louder: " + ", ".join(louder))
        if quieter:
            out.append("made quieter: " + ", ".join(quieter))
    return "; ".join(out)


_RECORD_TEXT = {"beat": _beat_text, "vocal": _vocal_text, "mix": _mix_text}


def _summary_line(label: str, value: Optional[dict[str, Any]], full: bool) -> Optional[str]:
    if not value:
        return None
    if not full:
        return f"{label}: present"
    text = guard(_RECORD_TEXT[label.lower()](value))   # data words (layer, effect, kind names) pass the filter
    return f"{label}: {text}"


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
        parts.append(f"Musical direction: {guard(_fingerprint_text(record.fingerprint))}")

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
