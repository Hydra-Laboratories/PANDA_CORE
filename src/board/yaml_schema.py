"""Strict Pydantic schemas for board YAML."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class InstrumentYamlEntry(BaseModel):
    """Schema for one instrument in board YAML.

    Common fields are declared explicitly. Driver-specific fields
    (e.g. serial_number, dll_path) pass through via extra="allow".

    Z semantics (see BaseInstrument docstring):
      * ``measurement_height`` — absolute deck-frame action Z.
      * ``safe_approach_height`` — absolute deck-frame XY-travel Z
        (defaults to ``measurement_height`` when omitted). Must be >=
        ``measurement_height`` in the +Z-up frame.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    vendor: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0
    measurement_height: float = 0.0
    safe_approach_height: Optional[float] = None

    @model_validator(mode="after")
    def _validate_approach_height(self) -> "InstrumentYamlEntry":
        if (
            self.safe_approach_height is not None
            and self.safe_approach_height < self.measurement_height
        ):
            raise ValueError(
                f"safe_approach_height ({self.safe_approach_height}) must be "
                f">= measurement_height ({self.measurement_height}). "
                f"Otherwise Board.move_to_labware would travel XY below the "
                f"action Z, defeating the retract-travel-lower safety guarantee."
            )
        return self


class BoardYamlSchema(BaseModel):
    """Root board YAML schema: only 'instruments' key allowed."""

    model_config = ConfigDict(extra="forbid")

    instruments: Dict[str, InstrumentYamlEntry]
