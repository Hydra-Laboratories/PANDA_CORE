"""Strict Pydantic schemas for board YAML."""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, ConfigDict


class InstrumentYamlEntry(BaseModel):
    """Schema for one instrument in board YAML.

    Common fields are declared explicitly. Driver-specific fields
    (e.g. serial_number, dll_path) pass through via extra="allow".
    """

    model_config = ConfigDict(extra="allow")

    type: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0
    measurement_height: float = 0.0


class BoardYamlSchema(BaseModel):
    """Root board YAML schema: only 'instruments' key allowed."""

    model_config = ConfigDict(extra="forbid")

    instruments: Dict[str, InstrumentYamlEntry]
