"""Shared instrument YAML schemas for machine configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class InstrumentYamlEntry(BaseModel):
    """Schema for one gantry-mounted instrument.

    Common fields are declared explicitly. Driver-specific fields
    (e.g. serial_number, dll_path) pass through via extra="allow".

    Z semantics
    -----------
    Instruments declare only their physical mounting (``offset_x``,
    ``offset_y``, ``depth``). Labware-relative motion heights live on the
    protocol commands that engage with labware:

    * ``measurement_height`` — first-class arg to ``measure`` and ``scan``.
    * ``safe_approach_height`` — first-class arg to ``scan``.

    Inter-labware travel uses the gantry-level ``safe_z`` (absolute).
    """

    model_config = ConfigDict(extra="allow")

    type: str
    vendor: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0
