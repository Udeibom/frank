"""Song Record models (song-record spec 01)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# The facets that have no table of their own. Lyrics, fingerprint, beat, vocal
# and mix already live in their own tables and are linked, not copied.
Facet = Literal[
    "intent",
    "feeling",
    "melody",
    "structure",
    "references",
    "identity_brief",
]
FACETS: tuple[str, ...] = (
    "intent",
    "feeling",
    "melody",
    "structure",
    "references",
    "identity_brief",
)

Phase = Literal["creating", "refining"]

# Who made a change. "user" is the person; anything else is Frank or a specialist.
USER_AUTHOR = "user"


class FacetVersion(BaseModel):
    """One stored version of a facet. Append-only: never updated or deleted."""

    id: str
    project_id: str
    facet: str
    content: dict[str, Any]
    parent_id: Optional[str] = None
    operation: str
    op_params: dict[str, Any] = Field(default_factory=dict)
    author: str
    label: Optional[str] = None
    created_at: Optional[datetime] = None


class Decision(BaseModel):
    """A choice between options, or a rejection, with the reasons behind it."""

    id: str
    project_id: str
    summary: str
    rationale: Optional[str] = None
    proposed_by: str = "frank"
    options: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    chosen_option: Optional[str] = None
    user_reaction: Optional[str] = None
    created_at: Optional[datetime] = None


class SongRecord(BaseModel):
    """Everything Frank knows about one song, assembled for reading."""

    project_id: str
    phase: Phase = "creating"
    # Active content for each facet, or None when empty (never a made-up default).
    facets: dict[str, Optional[dict[str, Any]]] = Field(default_factory=dict)
    lyrics: Optional[str] = None
    fingerprint: Optional[dict[str, Any]] = None
    beat: Optional[dict[str, Any]] = None   # summary: sections/layers/label
    vocal: Optional[dict[str, Any]] = None  # summary: take count, active kind
    mix: Optional[dict[str, Any]] = None    # summary: label, params
    decisions: list[Decision] = Field(default_factory=list)  # newest first


# ─── API bodies ──────────────────────────────

class WriteFacetRequest(BaseModel):
    content: dict[str, Any]
    parent_id: Optional[str] = None   # defaults to the current active version
    operation: str = "user_set"
    op_params: dict[str, Any] = Field(default_factory=dict)
    label: Optional[str] = None
    activate: bool = True


class MelodyNote(BaseModel):
    pitch_midi: int
    start_beat: float
    dur_beats: float


class MelodySketch(BaseModel):
    """A tune extracted from a hum (start-from-any-input spec 02). Not used until confirmed."""

    notes: list[MelodyNote]            # snapped to the beat grid: what the music engine builds on
    performed_notes: list[MelodyNote] = Field(default_factory=list)  # timing as sung: what playback follows
    tempo_bpm: float
    tempo_confidence: float
    key: str
    mode: str
    key_confidence: float
    grid: float = 0.25
    source_audio: Optional[str] = None
    confirmed: bool = False
    fit: Optional[float] = None  # share of the hum's sung frames the notes explain (0..1)


class RestoreFacetRequest(BaseModel):
    version_id: str


class ActivateFacetRequest(BaseModel):
    version_id: str


class RecordDecisionRequest(BaseModel):
    summary: str
    rationale: Optional[str] = None
    proposed_by: str = "frank"
    options: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    chosen_option: Optional[str] = None
    user_reaction: Optional[str] = None


class SetPhaseRequest(BaseModel):
    phase: Phase


class FacetVersionResponse(BaseModel):
    id: str
    facet: str
    content: dict[str, Any]
    parent_id: Optional[str] = None
    operation: str
    author: str
    label: Optional[str] = None
    is_active: bool = False
    created_at: Optional[datetime] = None
