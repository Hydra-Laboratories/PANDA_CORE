"""Strict Pydantic schemas for board YAML."""

from __future__ import annotations

from typing import Dict

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CollisionVectorYaml(BaseModel):
    """Three-dimensional vector used by instrument collision geometry."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float

    @field_validator("x", "y", "z")
    def _validate_finite(cls, value: float, info):  # type: ignore[override]
        if not math.isfinite(value):
            raise ValueError(f"{info.field_name} must be finite.")
        return value


class CollisionGeometryYaml(BaseModel):
    """Conservative instrument body geometry relative to the working point."""

    model_config = ConfigDict(extra="forbid")

    kind: str = "box"
    size: CollisionVectorYaml
    origin_offset: CollisionVectorYaml = Field(
        default_factory=lambda: CollisionVectorYaml(x=0.0, y=0.0, z=0.0),
    )

    @field_validator("kind")
    def _validate_kind(cls, value: str) -> str:
        if value != "box":
            raise ValueError("collision_geometry.kind must be 'box'.")
        return value

    @model_validator(mode="after")
    def _validate_size_positive(self) -> "CollisionGeometryYaml":
        if self.size.x <= 0 or self.size.y <= 0 or self.size.z <= 0:
            raise ValueError("collision_geometry.size dimensions must be positive.")
        return self


class InstrumentYamlEntry(BaseModel):
    """Schema for one instrument in board YAML.

    Common fields are declared explicitly. Driver-specific fields
    (e.g. serial_number, dll_path) pass through via extra="allow".
    """

    model_config = ConfigDict(extra="allow")

    type: str
    vendor: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    depth: float = 0.0
    measurement_height: float = 0.0
    collision_geometry: CollisionGeometryYaml | None = None


class BoardYamlSchema(BaseModel):
    """Root board YAML schema: only 'instruments' key allowed."""

    model_config = ConfigDict(extra="forbid")

    instruments: Dict[str, InstrumentYamlEntry]
