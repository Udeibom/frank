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


# ─── Reading a song's words (start-from-any-input spec 02, requirement 2) ───

SECTION_NAMES: tuple[str, ...] = ("intro", "verse", "pre-chorus", "chorus", "bridge", "outro")
TEMPO_FEELS: tuple[str, ...] = ("steady", "building", "floating", "driving")
MODES: tuple[str, ...] = ("minor", "major")
SECTION_FEELINGS: tuple[str, ...] = ("sorrowful", "angry", "warm", "mixed")


class LyricSection(BaseModel):
    """A stretch of the lyrics. Lines are numbered 1..N counting only non-empty lines."""

    name: str
    first_line: int
    last_line: int
    feeling: Optional[str] = None     # "sorrowful", "warm" or "mixed": how this stretch feels


class LyricsFeeling(BaseModel):
    summary: str = ""
    themes: list[str] = Field(default_factory=list)
    imagery: list[str] = Field(default_factory=list)
    emotional_arc: Optional[str] = None


class LyricsHints(BaseModel):
    """What the words suggest for the music. Only used when `confidence` is high enough."""

    energy_level: Optional[float] = None
    density: Optional[float] = None
    tempo_feel: Optional[str] = None
    mode: Optional[str] = None
    confidence: float = 0.0          # how sure the energy, density and feel are
    mode_confidence: float = 0.0     # how sure the dark-or-warm mood is (decided in code from the sections)


class LyricsReading(BaseModel):
    ok: bool
    line_count: int = 0
    feeling: Optional[LyricsFeeling] = None
    sections: list[LyricSection] = Field(default_factory=list)
    hints: Optional[LyricsHints] = None
    question: Optional[str] = None
    reason: Optional[str] = None      # a plain reason when ok is False
    from_model: bool = False          # False when only the stanza-based structure could be built
    truncated: bool = False           # True when the song was too long and only the first part was read
    based_on: Optional[str] = None    # fingerprint of the exact words that were read


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
