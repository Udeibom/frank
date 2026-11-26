"""
Ready-made directions (spec 08).

`from_findings`: for each thing the Listener found, the moves a producer would try first. The Producer model may
write its own directions; these are what it starts from, and what Frank offers if the model is unavailable.

`experiment_menu`: when nobody can tell what is wrong (requirement 4), versions that differ in exactly ONE thing
each, so the person's ears decide and the result teaches Frank something.
"""
from __future__ import annotations

from typing import Optional

from app.services.generation.beat import SectionPlan
from app.services.refine.models import Direction


def _idx(sections: list[SectionPlan], name: str) -> list[int]:
    return [s.index for s in sections if s.name == name]


def _with(sections: list[SectionPlan], idx: list[int], part: str) -> list[int]:
    return [i for i in idx if part in sections[i].layers]


def _without(sections: list[SectionPlan], idx: list[int], part: str) -> list[int]:
    return [i for i in idx if part not in sections[i].layers]


def _beat(title: str, plain: str, *ops: dict) -> Direction:
    return Direction(title=title, plain=plain, kind="beat", actions=list(ops))


def _mix(title: str, plain: str, *actions: dict) -> Direction:
    return Direction(title=title, plain=plain, kind="mix", actions=list(actions))


CRITIC_IDS = {"part_busy", "part_loud", "chorus_thin"}


def _part_of(f: dict, sections: list[SectionPlan], where: list[int]) -> Optional[str]:
    for part in f.get("parts") or []:
        if part in {"drums", "bass", "keys", "melody", "pad", "strings", "arp"}:
            return part
    for evidence in f.get("evidence") or []:
        bits = str(evidence).split(".")
        if len(bits) >= 3 and bits[0] == "section" and bits[1].isdigit():
            part = bits[3] if len(bits) > 3 else None
            if part in {"drums", "bass", "keys", "melody", "pad", "strings", "arp"}:
                return part
        if len(bits) >= 2 and bits[0] == "part":
            part = bits[1]
            if part in {"drums", "bass", "keys", "melody", "pad", "strings", "arp"}:
                return part
    return None


def _link(d: Direction, f: dict) -> Direction:
    fid = f.get("id")
    targets = [int(i) for i in f.get("sections", []) if isinstance(i, int)]
    if not targets:
        targets = [int(a["section"]) for a in d.actions if isinstance(a.get("section"), int)]
    return d.model_copy(update={
        "addresses": [fid] if fid else [],
        "evidence": [str(e) for e in (f.get("evidence") or [])],
        "targets": targets,
        "source": "critic" if fid in CRITIC_IDS else "listener",
        "expectation": {"finding": fid, "plain": f.get("plain")},
    })


def from_findings(findings: list[dict], sections: list[SectionPlan], has_mix: bool, hummed_tune: bool = False) -> list[Direction]:
    """Candidate directions for the findings, most important finding first. Some may not apply; the caller validates."""
    out: list[Direction] = []
    for f in findings:
        start = len(out)
        fid, where = f.get("id"), [i for i in f.get("sections", []) if 0 <= i < len(sections)]
        if fid == "chorus_lift" and len(where) == 2:
            verse, chorus = where
            out.append(_beat("A bigger chorus", "Push the chorus up so it lands harder after the verse.",
                             {"op": "bigger", "section": chorus}))
            out.append(_beat("A quieter verse", "Hold the verse back, so the chorus feels bigger by comparison.",
                             {"op": "smaller", "section": verse}))
            out.append(_beat("A drum fill into the chorus", "Give the drums a roll at the end of the verse to announce the chorus.",
                             {"op": "add_fill", "section": verse}))
            missing = next((p for p in ("strings", "pad", "arp") if p not in sections[chorus].layers), None)
            if missing:
                out.append(_beat("Another layer in the chorus", "Bring in an extra layer only when the chorus starts.",
                                 {"op": "add_part", "part": missing, "section": chorus}))
        elif fid == "copy" and len(where) == 2:
            later = where[1]
            out.append(_beat("A fresh idea for the repeat", "Keep the shape but play something new the second time.",
                             {"op": "try_another", "section": later}))
            missing = next((p for p in ("arp", "strings", "pad") if p not in sections[later].layers), None)
            if missing:
                out.append(_beat("Add something the second time", "Same section, plus one new layer, so it grows.",
                                 {"op": "add_part", "part": missing, "section": later}))
            out.append(_beat("Make the repeat bigger", "The second time round plays a step bigger.", {"op": "bigger", "section": later}))
        elif fid == "flat":
            choruses, verses = _idx(sections, "chorus"), _idx(sections, "verse")
            if choruses:
                out.append(_beat("Bigger choruses", "Lift every chorus so the song has somewhere to go.", {"op": "bigger", "section": choruses}))
            if verses:
                out.append(_beat("Thinner verses", "Strip the verses back so the song breathes in and out.", {"op": "smaller", "section": verses}))
            busy = _with(sections, verses, "drums")
            if busy:
                out.append(_beat("Simpler drums in the verses", "Calmer drums in the verses, full drums in the choruses.",
                                 {"op": "sparser", "part": "drums", "section": busy}))
        elif fid == "melody_wanders" and where and not hummed_tune:
            out.append(_beat("A new tune there", "Try a different tune that sits closer to the chords.",
                             {"op": "try_another", "part": "melody", "section": where}))
            out.append(_beat("Leave the tune out there", "Take the tune out of that part so nothing clashes.",
                             {"op": "remove_part", "part": "melody", "section": where}))
        elif fid == "voice_buried" and has_mix:
            out.append(_mix("Your voice louder", "Bring your voice up over the music.",
                            {"type": "adjust_levels", "params": {"vocal_delta_db": 3}}))
            out.append(_mix("The music quieter", "Keep your voice where it is and pull the music back.",
                            {"type": "adjust_levels", "params": {"beat_delta_db": -3}}))
            out.append(_mix("Your voice clearer", "Make your voice cut through without turning it up.",
                            {"type": "apply_effect", "params": {"target": "vocal", "effect": "clarity", "on": True}}))
        elif fid == "voice_crowded":
            if has_mix:
                out.append(_mix("Clear the low end", "Clean up the deep rumble so your voice has its own space.",
                                {"type": "apply_effect", "params": {"target": "beat", "effect": "clean_low", "on": True}}))
            keys = _with(sections, where, "keys")
            if keys:
                out.append(_beat("Simpler keys under your voice", "The keys play less where you sing.",
                                 {"op": "sparser", "part": "keys", "section": keys}))
            pads = _with(sections, where, "pad")
            if pads:
                out.append(_beat("No soft background there", "Take the soft background out where you sing.",
                                 {"op": "remove_part", "part": "pad", "section": pads}))
        elif fid in ("too_quiet", "clipping", "too_loud") and has_mix:
            step = 3 if fid == "too_quiet" else -3
            out.append(_mix("Everything louder" if step > 0 else "Everything a little softer",
                            "Change the level of the whole song, keeping the balance.",
                            {"type": "adjust_levels", "params": {"vocal_delta_db": step, "beat_delta_db": step}}))
        elif fid == "part_busy" and where:
            part = _part_of(f, sections, where)
            if part:
                idxs = _with(sections, where, part)
                if idxs:
                    out.append(_beat("Give that part room", "Let one part play less, so the others can be heard.",
                                     {"op": "sparser", "part": part, "section": idxs}))
        elif fid == "part_loud" and where:
            part = _part_of(f, sections, where)
            if part:
                idxs = _with(sections, where, part)
                if idxs:
                    out.append(_beat("Bring that part back", "Hold one part back so the others sit with it.",
                                     {"op": "sparser", "part": part, "section": idxs}))
        elif fid == "chorus_thin" and where:
            for i in where:
                missing = next((p for p in ("strings", "pad", "arp") if p not in sections[i].layers), None)
                if missing:
                    out.append(_beat("A fuller chorus", "Bring in one more layer when the chorus starts.",
                                     {"op": "add_part", "part": missing, "section": i}))
        out[start:] = [_link(d, f) for d in out[start:]]
    return out


def experiment_menu(
    sections: list[SectionPlan], hummed_tune: bool, has_mix: bool, concern: Optional[str] = None
) -> list[Direction]:
    """
    Single-change experiments, ordered so the part of the song the person named comes first.
    Each changes exactly one thing (spec 08 property 3).
    """
    verses, choruses = _idx(sections, "verse"), _idx(sections, "chorus")
    menu: list[tuple[str, Direction]] = []
    if verses:
        menu.append(("verse", _beat("Thinner verses", "Only the verses change: they play smaller and lighter.",
                                    {"op": "smaller", "section": verses})))
    if choruses:
        menu.append(("chorus", _beat("Fuller choruses", "Only the choruses change: they play bigger.",
                                     {"op": "bigger", "section": choruses})))
    tune = _with(sections, choruses, "melody")
    if tune and not hummed_tune:          # never rewrite a tune the person hummed
        menu.append(("chorus", _beat("A new tune idea", "Only the chorus tune changes; everything else stays.",
                                     {"op": "try_another", "part": "melody", "section": tune})))
    keys = [s.index for s in sections if "keys" in s.layers]
    if keys:
        menu.append(("keys", _beat("Warmer keys", "Only the sound of the keys changes, to a softer, warmer one.",
                                   {"op": "swap_sound", "part": "keys", "sound": "electric piano", "section": keys})))
    # More single changes, so there are always at least two to hear even when the ones above change nothing
    # (a chorus already as big as it goes, keys already on that sound; found by a property test, Nov 18).
    verse_drums = _with(sections, verses, "drums")
    if verse_drums:
        menu.append(("verse", _beat("Simpler drums in the verses", "Only the verse drums change: they play less.",
                                    {"op": "sparser", "part": "drums", "section": verse_drums})))
    before_chorus = [i - 1 for i in choruses if i > 0 and "drums" in sections[i - 1].layers]
    if before_chorus:
        menu.append(("chorus", _beat("A drum fill into the chorus", "Only one thing is added: a drum roll that announces the chorus.",
                                     {"op": "add_fill", "section": before_chorus})))
    if keys:
        menu.append(("keys", _beat("Brighter keys", "Only the sound of the keys changes, to a brighter piano.",
                                   {"op": "swap_sound", "part": "keys", "sound": "bright piano", "section": keys})))
    if has_mix:
        menu.append(("voice", _mix("More space around your voice", "Only your voice changes: it sounds like a bigger room.",
                                   {"type": "apply_effect", "params": {"target": "vocal", "effect": "space", "on": True}})))
    words = (concern or "").lower()
    named = {"verse": "verse" in words, "chorus": "chorus" in words, "voice": any(w in words for w in ("voice", "vocal", "sing"))}
    menu.sort(key=lambda kv: 0 if named.get(kv[0]) else 1)       # stable: the menu's order otherwise
    return [d.model_copy(update={"source": "experiment", "addresses": [], "evidence": [], "targets": []}) for _, d in menu]
