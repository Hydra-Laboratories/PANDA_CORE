"""Strict Pydantic schemas for deck YAML."""

from __future__ import annotations

from typing import Annotated, Dict, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _YamlPoint3D(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    z: float


class _YamlCalibrationPoints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Preferred location for A1 in deck YAML.
    a1: _YamlPoint3D | None = None
    a2: _YamlPoint3D


class WellPlateYamlEntry(BaseModel):
    """Strict schema for one well plate in deck labware."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    type: Literal["well_plate"] = "well_plate"
    name: str
    model_name: str
    rows: int = Field(..., gt=0)
    columns: int = Field(..., gt=0)
    length_mm: float
    width_mm: float
    height_mm: float
    # Backward compatibility: top-level A1 is accepted but deprecated.
    a1: _YamlPoint3D | None = None
    calibration: _YamlCalibrationPoints
    x_offset_mm: float
    y_offset_mm: float
    capacity_ul: float
    working_volume_ul: float

    @property
    def a1_point(self) -> _YamlPoint3D:
        """Return canonical A1 point, preferring calibration.a1."""
        a1 = self.calibration.a1 or self.a1
        if a1 is None:
            raise ValueError("Calibration must define `a1` (prefer `calibration.a1`).")
        return a1

    @model_validator(mode="after")
    def _validate_two_point_calibration(self) -> "WellPlateYamlEntry":
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
        if self.x_offset_mm == 0 or self.y_offset_mm == 0:
            raise ValueError("x_offset_mm and y_offset_mm must be non-zero.")
        return self


class VialYamlEntry(BaseModel):
    """Strict schema for one vial labware in deck labware."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    type: Literal["vial"] = "vial"
    name: str
    model_name: str
    height_mm: float
    diameter_mm: float
    location: _YamlPoint3D
    capacity_ul: float
    working_volume_ul: float

    @model_validator(mode="after")
    def _validate_vial_volumes(self) -> "VialYamlEntry":
        if self.working_volume_ul > self.capacity_ul:
            raise ValueError("working_volume_ul must be <= capacity_ul.")
        if self.capacity_ul <= 0 or self.working_volume_ul <= 0:
            raise ValueError("capacity_ul and working_volume_ul must be positive.")
        return self


LabwareYamlEntry = Annotated[
    Union[WellPlateYamlEntry, VialYamlEntry],
    Field(discriminator="type"),
]


class DeckYamlSchema(BaseModel):
    """Root deck YAML schema: only 'labware' key allowed."""

    model_config = ConfigDict(extra="forbid")

    labware: Dict[str, LabwareYamlEntry] = Field(
        ..., description="Mapping of labware key to well_plate or vial entry."
    )
