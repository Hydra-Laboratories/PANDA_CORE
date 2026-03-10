"""TipRack labware: a grid of disposable pipette tips."""

from __future__ import annotations

from typing import Dict

from pydantic import ConfigDict, Field, field_validator, model_validator

from .labware import Coordinate3D, Labware


class TipRack(Labware):
    """Labware representing a rack of disposable pipette tips.

    Tips are boolean present/absent -- no volume tracking is needed.
    Coordinates for each tip slot are expressed as absolute deck coordinates.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str = Field(..., description="Unique tip rack name.")
    model_name: str = Field(..., description="Tip rack model identifier.")
    length_mm: float = Field(..., description="Overall rack length in millimeters.")
    width_mm: float = Field(..., description="Overall rack width in millimeters.")
    height_mm: float = Field(..., description="Overall rack height in millimeters.")
    rows: int = Field(
        ...,
        gt=0,
        le=26,
        description="Number of tip rows. Max 26 (A-Z).",
    )
    columns: int = Field(..., gt=0, description="Number of tip columns.")
    wells: Dict[str, Coordinate3D] = Field(
        ...,
        description="Mapping from slot ID (e.g. 'A1') to absolute XYZ position.",
    )

    @field_validator("name", "model_name")
    def _validate_non_empty_text(cls, value: str) -> str:
        return Labware.validate_name(value)

    @field_validator("length_mm", "width_mm", "height_mm")
    def _validate_positive_dimension(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @model_validator(mode="before")
    def _validate_wells(cls, data):
        wells: Dict[str, Coordinate3D] = data.get("wells") or {}
        if not wells:
            raise ValueError("TipRack must define at least one well.")
        if "A1" not in wells:
            raise ValueError("TipRack must define an 'A1' well for anchoring.")
        return data

    @model_validator(mode="after")
    def _validate_well_count(self) -> "TipRack":
        expected = self.rows * self.columns
        if len(self.wells) != expected:
            raise ValueError(
                f"TipRack wells count must equal rows*columns ({expected}), "
                f"got {len(self.wells)}."
            )
        return self

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None:
            raise KeyError("TipRack location_id is required, e.g. 'A1'.")
        try:
            return self.wells[location_id]
        except KeyError as exc:
            raise KeyError(f"Unknown well ID '{location_id}'") from exc

    def get_initial_position(self) -> Coordinate3D:
        """Initial position for a tip rack: the A1 slot."""
        return self.wells["A1"]
