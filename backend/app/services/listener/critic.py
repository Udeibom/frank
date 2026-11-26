from __future__ import annotations

from typing import Any

import numpy as np

from app.services.listener import config as cfg
from app.services.listener.models import Finding, MeasurementReport

PART_WORDS = {
    "drums": "the drums",
    "bass": "the low part",
    "keys": "the piano",
    "melody": "the tune",
    "pad": "the soft background",
    "strings": "the strings",
    "arp": "the running pattern",
    "extras": "the extra sounds",
    "vocal": "your voice",
}

CRITIC_TAGS = {
    "part_busy": {"busy", "crowded", "muddy"},
    "part_loud": {"loud", "buried", "hear", "muddy"},
    "chorus_thin": {"empty", "thin", "lift", "chorus"},
}


def _word(part: str) -> str:
    return PART_WORDS.get(part, part)


def _evidence(report: MeasurementReport, ids: list[str]) -> list[str]:
    return [key for key in ids if key in report.values]


def _facts(report: MeasurementReport) -> list[tuple[int, dict[str, Any]]]:
    out: list[tuple[int, dict[str, Any]]] = []
    for key, value in sorted(report.score_facts.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 0):
        if isinstance(value, dict):
            out.append((int(key), value))
    return out


def rule_part_busy(report: MeasurementReport) -> list[Finding]:
    out: list[Finding] = []
    for index, facts in _facts(report):
        counts = {
            name: float(count)
            for name, count in (facts.get("notes_per_bar") or {}).items()
            if isinstance(count, (int, float)) and np.isfinite(count)
        }
        if len(counts) < 3:
            continue
        typical = float(np.median(list(counts.values())))
        for name, count in sorted(counts.items()):
            if count < cfg.PART_BUSY_MIN_NOTES or count < typical * cfg.PART_BUSY_RATIO:
                continue
            evidence = _evidence(report, [
                f"section.{index}.notes_per_bar.{name}",
                f"part.{name}.section.{index}.notes_per_bar",
            ])
            if not evidence:
                continue
            out.append(Finding(
                id="part_busy", severity="worth_a_look", confidence=0.65,
                plain=f"{_word(name).capitalize()} plays far more notes than the other parts.",
                evidence=evidence, sections=[index], parts=[name],
            ))
    return out


def rule_part_loud(report: MeasurementReport) -> list[Finding]:
    levels = {
        key.split(".", 2)[1]: float(value)
        for key, value in report.values.items()
        if key.startswith("part.") and key.endswith(".loudness") and np.isfinite(value)
    }
    if len(levels) < 3:
        return []
    out: list[Finding] = []
    typical = float(np.median(list(levels.values())))
    for name, level in sorted(levels.items()):
        if level - typical < cfg.PART_LOUD_GAP:
            continue
        loudest = max(levels.items(), key=lambda item: item[1])[0]
        if name != loudest:
            continue
        evidence = _evidence(report, [f"part.{name}.loudness"])
        if not evidence:
            continue
        out.append(Finding(
            id="part_loud", severity="worth_a_look", confidence=0.7,
            plain=f"{_word(name).capitalize()} sits out in front of the other parts.",
            evidence=evidence, parts=[name],
        ))
    return out


def rule_chorus_thin(report: MeasurementReport) -> list[Finding]:
    facts = _facts(report)
    if len(facts) < 3:
        return []
    counts: dict[int, int] = {}
    for index, fact in facts:
        parts_value = (fact.get("parts") or (report.values.get(f"section.{index}.parts") or 0))
        if isinstance(parts_value, (int, float)) and np.isfinite(parts_value):
            counts[index] = int(parts_value)
        elif isinstance(parts_value, list):
            counts[index] = len(parts_value)
    if len(counts) < 3:
        return []
    typical = float(np.median([count for index, count in counts.items()
                               if not any(s.index == index and s.name == "chorus" for s in report.sections)]))
    out: list[Finding] = []
    for section in report.sections:
        count = counts.get(section.index)
        if section.name != "chorus" or count is None or count > cfg.PART_THIN_COUNT or typical < 3:
            continue
        evidence = _evidence(report, [f"section.{section.index}.parts"])
        if not evidence:
            continue
        out.append(Finding(
            id="chorus_thin", severity="worth_a_look", confidence=0.6,
            plain="The chorus feels thin next to the rest of the song.",
            evidence=evidence, sections=[section.index],
        ))
    return out


def critique(report: MeasurementReport) -> list[Finding]:
    return rule_part_busy(report) + rule_part_loud(report) + rule_chorus_thin(report)
