from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator

from .labware import BoundingBoxGeometry, Coordinate3D, Labware

if TYPE_CHECKING:
    from .vial_holder import VialHolder


class Vial(Labware):
    """
    Labware representing a single vial.

    ``location`` is the vial's bottom-center (x, y, z) — the z component is the
    absolute deck Z of the surface the vial rests on. The top of the vial is at
    ``location.z + height_mm``.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str = Field(..., description="Unique vial name.")
    model_name: str = Field("", description="Vial model identifier.")
    height_mm: float = Field(..., description="Vial height in millimeters (bottom to rim).")
    diameter_mm: float = Field(..., description="Vial outer diameter in millimeters.")
    location: Coordinate3D = Field(..., description="Absolute XYZ of the vial bottom-center.")
    capacity_ul: float = Field(..., description="Vial capacity in microliters.")
    working_volume_ul: float = Field(..., description="Working volume per vial in microliters.")
    holder: Optional["VialHolder"] = Field(
        default=None,
        exclude=True,
        repr=False,
        description="VialHolder that contains this vial; populated by the deck loader.",
    )

    @field_validator("name")
    def _validate_non_empty_text(cls, value: str) -> str:
        return Labware.validate_name(value)

    @field_validator("capacity_ul", "working_volume_ul")
    def _validate_positive_volume(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @model_validator(mode="after")
    def _validate_working_le_capacity(self) -> "Vial":
        if self.working_volume_ul > self.capacity_ul:
            raise ValueError("working_volume_ul must be <= capacity_ul.")
        self.geometry = BoundingBoxGeometry(
            length_mm=self.diameter_mm,
            width_mm=self.diameter_mm,
            height_mm=self.height_mm,
        )
        return self

    @field_validator("diameter_mm")
    def _validate_positive_dimension(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None or location_id == self.name:
            return self.location
        raise KeyError(f"Unknown location ID '{location_id}'")

    def get_bottom_center(self) -> Coordinate3D:
        """Return the bottom-center (seat surface) coordinate of this vial."""
        return self.location

    def get_top_center(self) -> Coordinate3D:
        """Return the top-center (rim) coordinate of this vial."""
        return Coordinate3D(
            x=self.location.x,
            y=self.location.y,
            z=self.location.z + self.height_mm,
        )

    def get_initial_position(self) -> Coordinate3D:
        """
        Initial position for a single vial is its bottom-center location.
        """
        return self.location

    def iter_positions(self) -> dict[str, Coordinate3D]:
        return {"location": self.location}
