"""Strict Pydantic schemas for board YAML."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict


class InstrumentYamlEntry(BaseModel):
    """Schema for one instrument in board YAML.

    Common fields are declared explicitly. Driver-specific fields
    (e.g. serial_number, dll_path) pass through via extra="allow".

    Z-offset semantics (see BaseInstrument docstring):
      * ``measurement_height`` — Z offset during the measurement/action.
      * ``safe_approach_height`` — Z offset during XY travel (defaults
        to ``measurement_height`` when omitted).
    """

    model_config = ConfigDict(extra="allow")

    type: str
    vendor: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0
    measurement_height: float = 0.0
    safe_approach_height: Optional[float] = None


class BoardYamlSchema(BaseModel):
    """Root board YAML schema: only 'instruments' key allowed."""

    model_config = ConfigDict(extra="forbid")

    instruments: Dict[str, InstrumentYamlEntry]
