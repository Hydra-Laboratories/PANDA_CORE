from __future__ import annotations

from typing import Dict

from pydantic import Field, field_validator, model_validator

from .labware import Labware, Coordinate3D


class Vial(Labware):
    """
    Labware representing one or more vial positions (e.g. a vial rack).

    Each logical vial ID (e.g. \"A1\") maps to an absolute deck coordinate.
    """

    height_mm: float = Field(..., description="Vial height in millimeters.")
    diameter_mm: float = Field(..., description="Vial outer diameter in millimeters.")
    center: Coordinate3D = Field(
        ...,
        description="Anchor position for the vial labware (typically the vial center).",
    )
    vials: Dict[str, Coordinate3D] = Field(
        ...,
        description="Mapping from vial ID (e.g. 'A1') to absolute XYZ centers.",
    )

    @field_validator("height_mm", "diameter_mm")
    def _validate_positive_dimension(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @model_validator(mode="before")
    def _sync_vials_and_locations(cls, data):
        vials: Dict[str, Coordinate3D] = data.get("vials") or {}
        if not vials:
            raise ValueError("Vial labware must define at least one vial position.")

        # Mirror vials into the base Labware `locations` mapping so base APIs work.
        data["locations"] = dict(vials)
        return data

    def get_vial_center(self, vial_id: str) -> Coordinate3D:
        """
        Convenience wrapper to fetch a vial center by ID.
        """
        try:
            return self.vials[vial_id]
        except KeyError as exc:
            raise KeyError(f"Unknown vial ID '{vial_id}'") from exc

    def get_initial_position(self) -> Coordinate3D:
        """
        Initial position for vial labware: the configured center.
        """
        return self.center

