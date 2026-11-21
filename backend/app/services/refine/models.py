"""The refine loop's data (spec 08, design "Pieces")."""
from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Kind = Literal["beat", "mix"]


class Direction(BaseModel):
    """One way to fix what feels wrong: a short plain description tied to typed actions."""
    title: str = Field(max_length=80)
    plain: str = Field(max_length=300)
    kind: Kind
    # beat: typed operations (generation/ops.py). mix: Mix Room actions ({"type": ..., "params": {...}}).
    actions: list[dict[str, Any]] = Field(min_length=1, max_length=4)
    changes: list[str] = Field(default_factory=list)     # what the actions do, in plain sentences (filled on validation)
    sections: list[int] = Field(default_factory=list)    # sections a preview plays (beat), empty for the whole song
    preview_url: Optional[str] = None
    before_url: Optional[str] = None
    # Meta Audiobox Aesthetics before/after (frankenstein spec 14, 2.4): {"before", "after", "plain"}
    made_well: Optional[dict[str, Any]] = None

    def signature(self) -> str:
        """Two directions with the same signature would sound the same: they are not two choices."""
        return self.kind + ":" + json.dumps(sorted(json.dumps(a, sort_keys=True) for a in self.actions))


class Proposal(BaseModel):
    id: Optional[str] = None
    project_id: str
    concern: Optional[str] = None
    findings: dict[str, Any] = Field(default_factory=dict)
    experiment: bool = False
    directions: list[Direction] = Field(default_factory=list)
    based_on: dict[str, Optional[str]] = Field(default_factory=dict)
    chosen: Optional[int] = None
    message: str = ""
