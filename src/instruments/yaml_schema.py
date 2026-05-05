"""Shared instrument YAML schemas for machine configuration."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class InstrumentYamlEntry(BaseModel):
    """Schema for one gantry-mounted instrument.

    Common fields are declared explicitly. Driver-specific fields
    (e.g. serial_number, dll_path) pass through via extra="allow".

    Z semantics
    -----------
    ``measurement_height`` is a *labware-relative* offset (mm above the
    labware's ``height_mm`` surface; negative = below). It is one of two
    allowed sources for a measure/scan action's measurement height — the
    other being the protocol command. Exactly one source must be set per
    command (XOR rule, enforced in semantic validation).

    Inter-labware travel uses the gantry-level ``safe_z`` (absolute), not
    any instrument-level field.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    vendor: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0
    measurement_height: Optional[float] = None
