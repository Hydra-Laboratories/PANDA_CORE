"""Simple rectangular obstacle on the deck defined by two corners."""

from __future__ import annotations

from pydantic import ConfigDict, Field, field_validator, model_validator

from .labware import BoundingBoxGeometry, Coordinate3D, Labware


class Wall(Labware):
    """Rectangular physical obstacle defined by two opposite corners.

    Walls have no slots, tips, or wells — they exist purely as geometry
    for bounds validation and collision avoidance.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    corner_min: Coordinate3D = Field(..., description="Min-coordinate corner (x, y, z).")
    corner_max: Coordinate3D = Field(..., description="Max-coordinate corner (x, y, z).")

    @field_validator("name")
    def _validate_name(cls, value: str) -> str:
        return Labware.validate_name(value)

    @model_validator(mode="after")
    def _validate_corners_and_set_geometry(self) -> "Wall":
        if self.corner_min.x >= self.corner_max.x:
            raise ValueError("corner_min.x must be < corner_max.x")
        if self.corner_min.y >= self.corner_max.y:
            raise ValueError("corner_min.y must be < corner_max.y")
        if self.corner_min.z >= self.corner_max.z:
            raise ValueError("corner_min.z must be < corner_max.z")
        self.geometry = BoundingBoxGeometry(
            length_mm=self.length_mm,
            width_mm=self.width_mm,
            height_mm=self.height_mm,
        )
        return self

    @property
    def x_min(self) -> float:
        return self.corner_min.x

    @property
    def x_max(self) -> float:
        return self.corner_max.x

    @property
    def y_min(self) -> float:
        return self.corner_min.y

    @property
    def y_max(self) -> float:
        return self.corner_max.y

    @property
    def z_min(self) -> float:
        return self.corner_min.z

    @property
    def z_max(self) -> float:
        return self.corner_max.z

    @property
    def length_mm(self) -> float:
        return self.corner_max.x - self.corner_min.x

    @property
    def width_mm(self) -> float:
        return self.corner_max.y - self.corner_min.y

    @property
    def height_mm(self) -> float:
        return self.corner_max.z - self.corner_min.z

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None or location_id in {"location", "min"}:
            return self.corner_min
        if location_id == "max":
            return self.corner_max
        raise KeyError(f"Unknown location ID '{location_id}'")

    def get_initial_position(self) -> Coordinate3D:
        return self.corner_min

    def iter_positions(self) -> dict[str, Coordinate3D]:
        return {"min": self.corner_min, "max": self.corner_max}
