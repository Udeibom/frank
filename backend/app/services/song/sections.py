from __future__ import annotations

import re

from app.models.song import SECTION_NAMES

_ALIASES = {
    "hook": "chorus",
    "refrain": "chorus",
    "pre chorus": "pre-chorus",
    "prechorus": "pre-chorus",
    "build up": "pre-chorus",
    "build-up": "pre-chorus",
    "buildup": "pre-chorus",
    "ending": "outro",
    "opening": "intro",
}

_HEADING = re.compile(
    r"^\s*[\[(]?\s*(intro|verse|pre[\s-]?chorus|chorus|hook|refrain|bridge|outro)\b(?:\s*(?:no\.?|part)?\s*\d+)?\s*[)\]]?\s*:?\s*$",
    re.I,
)
_ORDER_CUE = re.compile(r"\b(sections?|order|structure|arrangement|sequence|shape|make it|use|set it|set the)\b", re.I)
_NAME = re.compile(r"\b(?:intro|verse|pre[\s-]?chorus|chorus|hook|refrain|bridge|outro)(?:\s*(?:no\.?|part)?\s*\d+)?\b", re.I)


def canonical_section_name(raw: object) -> str | None:
    text = re.sub(r"\s+", " ", str(raw or "").strip().lower())
    text = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", text)
    text = re.sub(r"\s*\d+(?:st|nd|rd|th)?\s*$", "", text)
    text = _ALIASES.get(text, text)
    return text if text in SECTION_NAMES else None


def section_headings(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for index, line in enumerate((text or "").splitlines(), 1):
        match = _HEADING.match(line)
        if not match:
            continue
        name = canonical_section_name(match.group(1))
        if name:
            out.append((name, index))
    return out


def parse_section_order(message: str) -> list[str]:
    headings = [name for name, _ in section_headings(message or "")]
    if len(headings) >= 2:
        return headings[:16]
    names: list[str] = []
    for match in _NAME.finditer(message or ""):
        name = canonical_section_name(match.group(0))
        if name:
            names.append(name)
    if not _ORDER_CUE.search(message or "") and len(names) >= 2:
        left = _NAME.sub("", message or "")
        if not re.sub(r"[\s,;:|/>\-→]+", "", left):
            return names[:16]
        return []
    return names[:16]


def structure_from_order(order: list[str]) -> dict:
    return {
        "sections": [
            {"name": name, "first_line": index + 1, "last_line": index + 1}
            for index, name in enumerate(order)
        ],
        "from_user_message": True,
    }
