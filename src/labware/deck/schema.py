"""Strict Pydantic schemas for deck YAML."""

from __future__ import annotations

from typing import Annotated, Dict, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Point3D(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    z: float


class _CalibrationPoints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Preferred location for A1 in deck YAML.
    a1: _Point3D | None = None
    a2: _Point3D


class WellPlateEntry(BaseModel):
    """Strict schema for one well plate in deck labware."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    type: Literal["well_plate"] = "well_plate"
    name: str
    model_name: str
    rows: int
    columns: int
    length_mm: float
    width_mm: float
    height_mm: float
    # Backward compatibility: top-level A1 is accepted but deprecated.
    a1: _Point3D | None = None
    calibration: _CalibrationPoints
    x_offset_mm: float
    y_offset_mm: float
    capacity_ul: float
    working_volume_ul: float

    @property
    def a1_point(self) -> _Point3D:
        """Return canonical A1 point, preferring calibration.a1."""
        a1 = self.calibration.a1 or self.a1
        if a1 is None:
            raise ValueError("Calibration must define `a1` (prefer `calibration.a1`).")
        return a1

    @model_validator(mode="after")
    def _validate_two_point_calibration(self) -> "WellPlateEntry":
        a1, a2 = self.a1_point, self.calibration.a2
        if a1.x == a2.x and a1.y == a2.y:
            raise ValueError("Calibration points A1 and A2 must not be identical.")
        same_x = abs(a1.x - a2.x) < 1e-9
        same_y = abs(a1.y - a2.y) < 1e-9
        if not same_x and not same_y:
            raise ValueError(
                "Calibration A2 must be axis-aligned with A1 (same x or same y); diagonal orientation is invalid."
            )
        if self.working_volume_ul > self.capacity_ul:
            raise ValueError("working_volume_ul must be <= capacity_ul.")
        if self.capacity_ul <= 0 or self.working_volume_ul <= 0:
            raise ValueError("capacity_ul and working_volume_ul must be positive.")
        return self


class VialEntry(BaseModel):
    """Strict schema for one vial labware in deck labware."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    type: Literal["vial"] = "vial"
    name: str
    model_name: str
    height_mm: float
    diameter_mm: float
    location: _Point3D
    capacity_ul: float
    working_volume_ul: float

    @model_validator(mode="after")
    def _validate_vial_volumes(self) -> "VialEntry":
        if self.working_volume_ul > self.capacity_ul:
            raise ValueError("working_volume_ul must be <= capacity_ul.")
        if self.capacity_ul <= 0 or self.working_volume_ul <= 0:
            raise ValueError("capacity_ul and working_volume_ul must be positive.")
        return self


LabwareEntry = Annotated[
    Union[WellPlateEntry, VialEntry],
    Field(discriminator="type"),
]


class DeckSchema(BaseModel):
    """Root deck YAML schema: only 'labware' key allowed."""

    model_config = ConfigDict(extra="forbid")

    labware: Dict[str, LabwareEntry] = Field(
        ..., description="Mapping of labware key to well_plate or vial entry."
    )

