from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, field_validator


class Coordinate3D(BaseModel):
    """Simple 3D coordinate representation in deck space (absolute machine coordinates)."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float

    @field_validator("x", "y", "z")
    def _validate_finite(cls, value: float, info):  # type: ignore[override]
        if not math.isfinite(value):
            raise ValueError(f"{info.field_name} must be finite (not NaN/Inf).")
        return value


class Labware(BaseModel):
    """
    Base behavior shared by all labware models.

    Concrete labware classes define their own required fields so users can inspect
    each class directly and understand exactly what YAML attributes are required.
    """

    model_config = ConfigDict(extra="forbid")

    @staticmethod
    def validate_name(value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Labware name must be a non-empty string.")
        return value

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        """Return an absolute deck coordinate for this labware."""
        raise NotImplementedError("Subclasses of Labware must implement get_location().")

    def get_initial_position(self) -> Coordinate3D:
        """
        Return the labware-level initial/anchor position.

        Subclasses are expected to override this.
        """
        raise NotImplementedError(
            "Subclasses of Labware must implement get_initial_position()."
        )
