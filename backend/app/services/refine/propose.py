"""
The proposer (spec 08, requirements 1 and 2): Listener findings -> two or three distinct directions.

The diagnosis comes only from what the Listener returned. One Producer model call phrases it and picks or writes
the directions; every direction is then checked by applying its actions to a copy of the plan (or the mix
settings). Anything that does not apply, or would sound the same as another direction, is dropped, and the
ready-made directions fill the gap. With no clear cause Frank says so and offers single-change experiments.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.services.generation import ops as ops_mod
from app.services.generation.beat import SectionPlan
from app.services.refine import experiments
from app.services.refine.models import Direction
from app.services.team import plain

log = logging.getLogger(__name__)

MIN_DIRECTIONS, MAX_DIRECTIONS = 2, 3
PREVIEW_MAX_SECTIONS = 2
MIX_TYPES = {"adjust_levels", "apply_effect", "toggle_harmony", "section_adjust"}


# ── what a direction touches ─────────────────────────────────────────────

def _fingerprint(s: SectionPlan) -> str:
    return json.dumps([s.name, s.bars, round(s.energy, 4), round(s.density, 4), sorted(s.layers), s.parts], sort_keys=True, default=str)


def changed_sections(old: list[SectionPlan], new: list[SectionPlan], old_seed: int, new_seed: int) -> list[int]:
    """Indices in the NEW plan whose own plan changed (matched by the section's stable identity)."""
    if old_seed != new_seed:
        return [s.index for s in new]
    before = {(s.uid if s.uid is not None else s.index): (s.index, _fingerprint(s)) for s in old}
    out: list[int] = []
    for s in new:
        was = before.get(s.uid if s.uid is not None else s.index)
        if was is None or was[1] != _fingerprint(s) or was[0] != s.index:
            out.append(s.index)
    return out


def preview_sections(changed: list[int], total: int) -> list[int]:
    """
    What a preview plays: the first changed section, plus the one after it so the change is heard in context
    (a quieter verse only makes sense next to its chorus). At most PREVIEW_MAX_SECTIONS, to keep the wait short.
    """
    if not changed:
        return []
    first = changed[0]
    run = [first]
    if first + 1 < total:
        run.append(first + 1)
    elif first - 1 >= 0:
        run.insert(0, first - 1)
    return run[:PREVIEW_MAX_SECTIONS]


# ── checking a direction ─────────────────────────────────────────────────

def _mix_sentence(action: dict) -> str:
    t, p = action.get("type"), action.get("params") or {}
    if t == "adjust_levels":
        bits = []
        for key, who in (("vocal_delta_db", "your voice"), ("beat_delta_db", "the music"), ("harmony_delta_db", "the harmony")):
            v = float(p.get(key, 0) or 0)
            if v:
                bits.append(f"{who} {'up' if v > 0 else 'down'} a little")
        return ("I'd bring " + " and ".join(bits) + ".") if bits else ""
    if t == "apply_effect":
        what = {"space": "space around", "warm": "warmth on", "smooth": "a smoother sound on", "clarity": "clarity on",
                "closer": "a closer sound on", "clean_low": "a cleaner low end on", "sit_back": "a softer top on"}.get(p.get("effect"), "a change on")
        target = "your voice" if p.get("target") == "vocal" else "the music"
        return f"I'd {'add' if p.get('on', True) else 'take off'} {what} {target}."
    if t == "toggle_harmony":
        return "I'd bring the harmony in." if p.get("on", True) else "I'd take the harmony out."
    if t == "section_adjust":
        return f"I'd make the {p.get('section', 'section')} {'louder' if float(p.get('delta_db', 0)) > 0 else 'softer'}."
    return ""


def validate(
    d: Direction, sections: list[SectionPlan], seed: int, mix_params: Optional[dict]
) -> Optional[Direction]:
    """The direction with its plain changes and preview sections filled in, or None if it cannot be applied."""
    if d.kind == "beat":
        if not sections:
            return None
        try:
            new, new_seed, changes = ops_mod.apply_operations(sections, seed, d.actions)
        except ops_mod.OpError:
            return None
        changed = changed_sections(sections, new, seed, new_seed)
        if not changed:
            return None
        return d.model_copy(update={"changes": changes, "sections": preview_sections(changed, len(new))})
    if mix_params is None:
        return None
    from app.routers.mix import apply_actions          # the Mix Room's own rules for its settings

    if any(a.get("type") not in MIX_TYPES for a in d.actions):
        return None
    try:
        after, _ = apply_actions(mix_params, d.actions)
        before, _ = apply_actions(mix_params, [])
    except (TypeError, ValueError):
        return None
    if after == before:
        return None
    changes = [s for s in (_mix_sentence(a) for a in d.actions) if s]
    return d.model_copy(update={"changes": changes, "sections": []})


def pick_distinct(candidates: list[Direction], limit: int = MAX_DIRECTIONS) -> list[Direction]:
    """Keep the first of any directions that would sound the same (spec 08 property 2)."""
    out: list[Direction] = []
    seen: set[str] = set()
    for d in candidates:
        sig = d.signature()
        if sig in seen:
            continue
        seen.add(sig)
        out.append(d)
        if len(out) == limit:
            break
    return out


# ── the Producer's call ──────────────────────────────────────────────────

PRODUCER_SYSTEM = """You are the producer on Frank's team. The person said something about their song feels wrong.
The Listener measured the song. Your job: say in one or two short sentences what the Listener found (ONLY what it
found, in plain words, comparing parts of the song, never numbers or music terms), then offer two or three different
directions to try. Each direction changes different things. Prefer the ready-made options; you may write your own
using the same action format. Never promise a result; the person will listen to each before choosing.
If the Listener found no clear cause, say honestly you can't tell yet and that each option changes just one thing.

Beat actions (section = position in the song, starting at 0; a list means several sections):
busier/sparser {part, section}, bigger/smaller {section}, add_part/remove_part {part, section},
swap_sound {part, sound, section}, add_fill {section}, try_another {part?, section}.
Parts: drums, bass, keys, melody, pad, strings, arp.
Mix actions: adjust_levels {vocal_delta_db, beat_delta_db}, apply_effect {target: vocal|beat, effect, on}.

Reply as JSON only:
{"message": "...", "directions": [{"option": <number of a ready-made option>} or
 {"title": "...", "plain": "...", "kind": "beat"|"mix", "actions": [...]}]}"""


def _plan_lines(sections: list[SectionPlan]) -> str:
    return "\n".join(f"{s.index}: {s.name} ({s.bars} bars) playing {', '.join(s.layers)}" for s in sections)


def _ask_producer(concern: str, found: dict, sections: list[SectionPlan], options: list[Direction]) -> dict:
    from app.services.llm.groq_client import chat_structured

    lines = [f"The person said: {concern or '(nothing specific, they want it better)'}",
             "The song:\n" + (_plan_lines(sections) or "(no beat yet)"),
             "The Listener found:" if found.get("findings") else "The Listener found no clear cause.",
             *[f"- {f['plain']} (sections {f.get('sections', [])})" for f in found.get("findings", [])[:5]],
             "Ready-made options:",
             *[f"{n}. {d.title}: {d.plain} -> {d.kind} {json.dumps(d.actions)}" for n, d in enumerate(options, 1)]]
    return chat_structured(PRODUCER_SYSTEM, [{"role": "user", "content": "\n".join(lines)}], temperature=0.4)


def _from_reply(reply: dict, options: list[Direction]) -> list[Direction]:
    out: list[Direction] = []
    for raw in reply.get("directions") or []:
        if not isinstance(raw, dict):
            continue
        n = raw.get("option")
        if isinstance(n, int) and 1 <= n <= len(options):
            out.append(options[n - 1])
            continue
        try:
            out.append(Direction(title=plain.guard(str(raw.get("title", ""))[:80]), plain=plain.guard(str(raw.get("plain", ""))[:300]),
                                 kind=raw.get("kind"), actions=raw.get("actions") or []))
        except Exception:  # noqa: BLE001  a malformed direction is simply not offered
            continue
    return [d for d in out if d.title and d.plain]


def fallback_message(found: dict, experiment: bool) -> str:
    if experiment:
        return ("I listened, and I can't point to one clear thing yet. So let's let your ears decide: each of these "
                "changes just one thing. Have a listen and tell me which feels closer.")
    first = found["findings"][0]["plain"]
    return f"I listened. {first} Here are a few ways we could go. Have a listen to each before you pick."


def propose(
    concern: Optional[str], found: dict, sections: list[SectionPlan], seed: int, mix_params: Optional[dict],
    hummed_tune: bool, use_model: bool = True,
) -> tuple[str, list[Direction], bool]:
    """
    Returns (message, directions, experiment). `found` is a FindingsReport dict. Directions are validated and
    distinct; there are two or three when the song allows that many different changes.
    """
    has_mix = mix_params is not None
    experiment = not found.get("findings")
    ready = (experiments.experiment_menu(sections, hummed_tune, has_mix, concern) if experiment
             else experiments.from_findings(found["findings"], sections, has_mix))
    ready = pick_distinct([v for v in (validate(d, sections, seed, mix_params) for d in ready) if v], limit=6)
    if not experiment and len(ready) < MIN_DIRECTIONS:
        extra = [validate(d, sections, seed, mix_params) for d in experiments.experiment_menu(sections, hummed_tune, has_mix, concern)]
        ready += [v for v in extra if v]
    ready = pick_distinct(ready, limit=6)

    message, chosen = "", []
    if use_model and ready:
        try:
            reply = _ask_producer(concern or "", found, sections, ready)
            message = str(reply.get("message") or "")
            picked = _from_reply(reply, ready)
            chosen = [v for v in (validate(d, sections, seed, mix_params) for d in picked) if v]
            if experiment:   # an experiment changes exactly one thing; the model may not widen it
                chosen = [d for d in chosen if len(d.actions) == 1]
        except Exception as exc:  # noqa: BLE001  the ready-made directions still work without the model
            log.warning("producer call failed, using ready-made directions: %s", exc)
    directions = pick_distinct(chosen + ready, MAX_DIRECTIONS)
    return plain.guard(message) or fallback_message(found, experiment), directions, experiment
