"""
Findings: small rule functions over a MeasurementReport (listener spec 03, design "Findings").
Each rule returns a Finding or None. The sentence is built from templates in plain words: no units, no
music jargon. Rules only read the report; they never invent a measurement.
"""
from __future__ import annotations

from typing import Callable, Optional

from app.services.listener import config as cfg
from app.services.listener.models import Finding, FindingsReport, MeasurementReport

ORDINALS = ["first", "second", "third", "fourth", "fifth"]
NAMES = {"verse": "verse", "chorus": "chorus", "bridge": "bridge", "intro": "intro", "outro": "ending", "pre-chorus": "build-up"}


def _v(r: MeasurementReport, key: str) -> Optional[float]:
    return r.values.get(key)


def _phrase(r: MeasurementReport, index: int) -> str:
    """'the second chorus', or just 'the chorus' when there is only one."""
    s = next(x for x in r.sections if x.index == index)
    same = [x for x in r.sections if x.name == s.name]
    word = NAMES.get(s.name, s.name)
    if len(same) == 1:
        return f"the {word}"
    n = same.index(s)
    return f"the {ORDINALS[n] if n < len(ORDINALS) else str(n + 1) + 'th'} {word}"


def _cap(text: str) -> str:
    return text[0].upper() + text[1:]


def _previous_of(r: MeasurementReport, name: str, index: int) -> Optional[int]:
    before = [s for s in r.sections if s.name == name and s.index < index]
    return before[-1].index if before else None


# ── rules ────────────────────────────────────────────────────────────────

def rule_chorus_lift(r: MeasurementReport) -> list[Finding]:
    out: list[Finding] = []
    for s in r.sections:
        if s.name != "chorus":
            continue
        prev = _previous_of(r, "verse", s.index)
        if prev is None:
            continue
        a, b = _v(r, f"section.{prev}.loudness"), _v(r, f"section.{s.index}.loudness")
        if a is None or b is None:
            continue
        gap = b - a
        pa, pb = _v(r, f"section.{prev}.parts"), _v(r, f"section.{s.index}.parts")
        if gap >= cfg.CHORUS_LIFT_MIN:
            continue
        if pa is not None and pb is not None and pb - pa >= 2 and gap > 0.5:
            continue    # clearly fuller even if not much louder: that reads as a lift
        sev = "likely_problem" if gap < cfg.CHORUS_LIFT_STRONG_PROBLEM else "worth_a_look"
        word = "almost the same strength as" if gap >= 0 else "quieter than"
        out.append(Finding(
            id="chorus_lift", severity=sev, confidence=0.8,
            plain=_cap(f"{_phrase(r, s.index)} plays at {word} {_phrase(r, prev)}, so it doesn't feel like a lift."),
            evidence=[f"section.{prev}.loudness", f"section.{s.index}.loudness"], sections=[prev, s.index]))
    return out


def rule_copy(r: MeasurementReport) -> list[Finding]:
    out: list[Finding] = []
    for key, val in sorted(r.values.items()):
        if not key.startswith("repeat.") or not key.endswith(".sound"):
            continue
        _, i, j, _ = key.split(".")
        i, j = int(i), int(j)
        if val < cfg.COPY_SIMILARITY:
            continue
        out.append(Finding(
            id="copy", severity="worth_a_look", confidence=0.75,
            plain=_cap(f"{_phrase(r, j)} sounds almost exactly like {_phrase(r, i)}."),
            evidence=[key], sections=[i, j]))
    return out


def rule_voice_buried(r: MeasurementReport) -> list[Finding]:
    out: list[Finding] = []
    for s in r.sections:
        gap = _v(r, f"section.{s.index}.vocal_gap")
        if gap is not None and gap < cfg.VOCAL_BURIED_GAP:
            out.append(Finding(
                id="voice_buried", severity="likely_problem" if gap < cfg.VOCAL_BURIED_GAP - 3 else "worth_a_look",
                confidence=0.8, plain=_cap(f"Your voice sits under the music in {_phrase(r, s.index)}."),
                evidence=[f"section.{s.index}.vocal_gap"], sections=[s.index], parts=["vocal"]))
    return out


def rule_voice_crowded(r: MeasurementReport) -> list[Finding]:
    bad = [s.index for s in r.sections
           if (_v(r, f"section.{s.index}.voice_band_gap") or 0.0) < cfg.VOICE_RANGE_CROWDED_GAP
           and f"section.{s.index}.voice_band_gap" in r.values]
    if not bad:
        return []
    names = ", ".join(_phrase(r, i) for i in bad[:3])
    return [Finding(
        id="voice_crowded", severity="worth_a_look", confidence=0.6,
        plain=_cap(f"The music and your voice are fighting for the same space in {names}."),
        evidence=[f"section.{i}.voice_band_gap" for i in bad], sections=bad, parts=["vocal"])]


def rule_timing(r: MeasurementReport) -> list[Finding]:
    ms, conf = _v(r, "vocal.timing_ms"), _v(r, "vocal.timing_confidence")
    if ms is None or conf is None or conf < cfg.TIMING_MIN_CONFIDENCE or abs(ms) < cfg.TIMING_OFFSET_MS:
        return []
    word = "behind" if ms > 0 else "ahead of"
    return [Finding(id="timing", severity="worth_a_look", confidence=min(0.9, conf),
                    plain=f"Your singing runs a little {word} the beat.",
                    evidence=["vocal.timing_ms", "vocal.timing_confidence"], parts=["vocal"])]


def rule_tuning(r: MeasurementReport) -> list[Finding]:
    share = _v(r, "vocal.in_tune")
    if share is None or share >= cfg.IN_TUNE_MIN_SHARE:
        return []
    return [Finding(id="tuning", severity="note", confidence=0.65,
                    plain="Quite a few notes drift away from the notes of the song. I can nudge them if you'd like.",
                    evidence=["vocal.in_tune"], parts=["vocal"])]


def rule_melody(r: MeasurementReport) -> list[Finding]:
    out: list[Finding] = []
    for s in r.sections:
        fit = _v(r, f"section.{s.index}.melody_fit")
        if fit is not None and fit < cfg.MELODY_FIT_MIN:
            out.append(Finding(id="melody_wanders", severity="worth_a_look", confidence=0.7,
                               plain=_cap(f"The tune wanders away from the harmony in {_phrase(r, s.index)}."),
                               evidence=[f"section.{s.index}.melody_fit"], sections=[s.index], parts=["melody"]))
    return out


def rule_clipping(r: MeasurementReport) -> list[Finding]:
    for key in ("mix.clipping", "beat.clipping"):
        share = _v(r, key)
        if share is not None and share > cfg.CLIPPING_SHARE:
            return [Finding(id="clipping", severity="likely_problem", confidence=0.9,
                            plain="Parts of the song hit the loudest the sound can go, which can make it harsh.",
                            evidence=[key])]
    return []


def rule_noise(r: MeasurementReport) -> list[Finding]:
    n = _v(r, "vocal.noise_floor")
    if n is None or n <= cfg.NOISE_FLOOR_DB:
        return []
    return [Finding(id="noise", severity="worth_a_look", confidence=0.7,
                    plain="There is some background hiss or room noise between your phrases.",
                    evidence=["vocal.noise_floor"], parts=["vocal"])]


def rule_overall_level(r: MeasurementReport) -> list[Finding]:
    lu = _v(r, "mix.loudness")
    if lu is None:
        return []
    if lu < cfg.MIX_TOO_QUIET_LUFS:
        return [Finding(id="too_quiet", severity="worth_a_look", confidence=0.8,
                        plain="The whole song plays quieter than most songs do.", evidence=["mix.loudness"])]
    if lu > cfg.MIX_TOO_LOUD_LUFS:
        return [Finding(id="too_loud", severity="worth_a_look", confidence=0.8,
                        plain="The whole song is pushed very loud, so there's little room left to feel the big moments.",
                        evidence=["mix.loudness"])]
    return []


def rule_flat(r: MeasurementReport) -> list[Finding]:
    ch = [(s.index, _v(r, f"section.{s.index}.change")) for s in r.sections]
    ch = [(i, c) for i, c in ch if c is not None]
    if len(ch) < 3 or max(c for _, c in ch) >= cfg.FLAT_CHANGE:
        return []
    return [Finding(id="flat", severity="worth_a_look", confidence=0.6,
                    plain="The song stays in one place: no section sounds much different from the one before it.",
                    evidence=[f"section.{i}.change" for i, _ in ch])]


# rule id -> (function, tags the person's concern can match)
RULES: dict[str, tuple[Callable[[MeasurementReport], list[Finding]], set[str]]] = {
    "chorus_lift": (rule_chorus_lift, {"lift", "chorus", "energy"}),
    "copy": (rule_copy, {"repeat", "boring", "same"}),
    "voice_buried": (rule_voice_buried, {"voice", "buried", "hear"}),
    "voice_crowded": (rule_voice_crowded, {"voice", "buried", "hear", "muddy"}),
    "timing": (rule_timing, {"voice", "timing", "off"}),
    "tuning": (rule_tuning, {"voice", "tuning", "off"}),
    "melody_wanders": (rule_melody, {"melody", "tune", "off"}),
    "clipping": (rule_clipping, {"harsh", "loud", "off"}),
    "noise": (rule_noise, {"voice", "noise", "off"}),
    "level": (rule_overall_level, {"loud", "quiet", "off"}),
    "flat": (rule_flat, {"boring", "flat", "lift", "energy", "same"}),
}

# words a person uses -> tags
CONCERN_WORDS: dict[str, set[str]] = {
    "lift": {"lift"}, "flat": {"flat"}, "boring": {"boring", "flat", "repeat"}, "chorus": {"chorus", "lift"},
    "drop": {"lift", "energy"}, "hit": {"lift", "energy"}, "bigger": {"lift", "energy"}, "energy": {"energy", "lift"},
    "same": {"same", "repeat"}, "repetitive": {"repeat", "boring"}, "repeat": {"repeat"},
    "buried": {"buried", "voice"}, "vocal": {"voice"}, "voice": {"voice"}, "hear": {"hear", "voice"},
    "words": {"voice", "hear"}, "muddy": {"muddy", "voice"}, "crowded": {"muddy", "voice"}, "thick": {"muddy"},
    "timing": {"timing"}, "late": {"timing"}, "early": {"timing"}, "behind": {"timing"},
    "tune": {"melody", "tuning"}, "flat-note": {"tuning"}, "sharp": {"tuning"}, "melody": {"melody"},
    "harsh": {"harsh"}, "loud": {"loud"}, "quiet": {"quiet"}, "noise": {"noise"}, "hiss": {"noise"},
    "off": {"off"}, "wrong": {"off"}, "weird": {"off"},
}

SEVERITY_ORDER = {"likely_problem": 0, "worth_a_look": 1, "note": 2}


def _tags(concern: Optional[str]) -> Optional[set[str]]:
    if not concern or not concern.strip():
        return None
    words = {w.strip(".,!?'\"").lower() for w in concern.split()}
    tags: set[str] = set()
    for w in words:
        tags |= CONCERN_WORDS.get(w, set())
    return tags or {"off"}


def find_issues(report: MeasurementReport, concern: Optional[str] = None) -> FindingsReport:
    """
    Run the rules the concern points at (all of them when there is none). If a concern was raised and no
    rule fires, say so: `no_clear_cause`, so the team can propose an experiment instead of inventing a reason.
    """
    tags = _tags(concern)
    found: list[Finding] = []
    for rule_id, (fn, rule_tags) in RULES.items():
        if tags is not None and "off" not in tags and not (tags & rule_tags):
            continue
        found.extend(fn(report))
    found.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.id))
    could = [u.why for u in report.unmeasured]
    return FindingsReport(concern=concern, findings=found, no_clear_cause=bool(concern) and not found, could_not_check=could)
