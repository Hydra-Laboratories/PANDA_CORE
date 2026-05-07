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
    ``measurement_height`` and ``safe_approach_height`` are *labware-relative*
    offsets (mm above the labware's ``height_mm`` surface; negative = below).

    ``measurement_height`` is owned here — protocol ``measure``/``scan``
    commands do not accept it.

    ``safe_approach_height`` may be set here, on the ``scan`` command, or
    both; at least one source must define it and conflicting values across
    sources are rejected. ``safe_approach_height`` is consumed by ``scan``
    only; ``measure`` does not use it. Inter-labware travel uses the
    gantry-level ``safe_z`` (absolute), not any instrument-level field.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    vendor: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0
    measurement_height: Optional[float] = None
    safe_approach_height: Optional[float] = None
