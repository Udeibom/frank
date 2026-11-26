"""Listener data shapes (listener spec 03). Raw numbers live in MeasurementReport; plain words in Finding."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["note", "worth_a_look", "likely_problem"]


class Unmeasured(BaseModel):
    """Something the Listener could not measure, and why, in plain words (requirement 3.1)."""
    id: str
    why: str


class SectionInfo(BaseModel):
    index: int
    name: str
    bars: int
    parts: list[str] = Field(default_factory=list)


class MeasurementReport(BaseModel):
    """
    Raw measurements. `values` maps a measurement id to a number, for example `section.3.loudness`.
    Ids used: section.{i}.{loudness|onsets_per_bar|parts|brightness|low_share|change|vocal_gap|voice_band_gap
    |melody_fit|melody_range|melody_movement}, repeat.{i}.{j}.sound, vocal.{loudness|in_tune|cents_off|timing_ms
    |timing_confidence|noise_floor}, mix.{loudness|peak|clipping|vocal_gap}, beat.{peak|clipping}.
    """
    audio_versions: dict[str, str] = Field(default_factory=dict)      # kind -> version id the numbers came from
    sections: list[SectionInfo] = Field(default_factory=list)
    score_facts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    values: dict[str, float] = Field(default_factory=dict)
    unmeasured: list[Unmeasured] = Field(default_factory=list)
    scope: Optional[list[str]] = None                                 # section names measured, None for all


class Finding(BaseModel):
    id: str                                   # the rule that fired
    plain: str                                # no jargon, no units
    severity: Severity
    confidence: float                         # 0..1
    evidence: list[str]                       # measurement ids
    sections: list[int] = Field(default_factory=list)
    parts: list[str] = Field(default_factory=list)


class FindingsReport(BaseModel):
    concern: Optional[str] = None
    findings: list[Finding] = Field(default_factory=list)
    no_clear_cause: bool = False              # a concern was raised and nothing measured explains it
    could_not_check: list[str] = Field(default_factory=list)   # plain sentences about what was not measured


class Difference(BaseModel):
    id: str
    plain: str
    before: Optional[float] = None
    after: Optional[float] = None
