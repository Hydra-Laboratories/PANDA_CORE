from __future__ import annotations

from pydantic import ConfigDict, Field, field_validator, model_validator

from .labware import Labware, Coordinate3D


class Vial(Labware):
    """
    Labware representing a single vial.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str = Field(..., description="Unique vial name.")
    model_name: str = Field(..., description="Vial model identifier.")
    height_mm: float = Field(..., description="Vial height in millimeters.")
    diameter_mm: float = Field(..., description="Vial outer diameter in millimeters.")
    location: Coordinate3D = Field(..., description="Absolute XYZ center of this vial.")
    capacity_ul: float = Field(..., description="Vial capacity in microliters.")
    working_volume_ul: float = Field(..., description="Working volume per vial in microliters.")

    @field_validator("name", "model_name")
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
        return self

    @field_validator("height_mm", "diameter_mm")
    def _validate_positive_dimension(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @model_validator(mode="after")
    def _validate_location(self) -> "Vial":
        if self.location is None:
            raise ValueError("Vial must define a location.")
        return self

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None or location_id in {"A1", self.name}:
            return self.location
        raise KeyError(f"Unknown location ID '{location_id}'")

    def get_vial_center(self) -> Coordinate3D:
        return self.location

    def get_initial_position(self) -> Coordinate3D:
        """
        Initial position for a single vial is its center location.
        """
        return self.location

