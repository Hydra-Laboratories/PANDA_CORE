from __future__ import annotations

from typing import Dict

from pydantic import ConfigDict, Field, field_validator, model_validator

from .labware import Coordinate3D, Labware


class LabwareSlot(Labware):
    """
    Addressable placement point inside a holder.

    The slot stores only deck-space metadata for now. Future work can attach
    occupancy, collision geometry, or compatibility rules here without having
    to change the holder API.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    location: Coordinate3D = Field(..., description="Absolute XYZ location for this slot.")
    supported_labware_types: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Optional labware type names that this slot is intended to accept.",
    )
    description: str | None = Field(default=None, description="Optional free-text note.")

    @field_validator("supported_labware_types")
    def _validate_supported_labware_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise ValueError("supported_labware_types entries must be non-empty strings.")
        return normalized

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None or location_id in {"location", "anchor"}:
            return self.location
        raise KeyError(f"Unknown location ID '{location_id}'")

    def get_initial_position(self) -> Coordinate3D:
        return self.location

    def iter_positions(self) -> dict[str, Coordinate3D]:
        return {"location": self.location}


class HolderLabware(Labware):
    """Base class for physical deck fixtures defined by a bounding box."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str = Field(..., description="Unique holder name.")
    model_name: str = Field(..., description="Holder model identifier.")
    location: Coordinate3D = Field(..., description="Absolute XYZ reference point for this holder.")
    length_mm: float = Field(..., description="Bounding-box X dimension in millimeters.")
    width_mm: float = Field(..., description="Bounding-box Y dimension in millimeters.")
    height_mm: float = Field(..., description="Bounding-box Z dimension in millimeters.")
    slots: Dict[str, LabwareSlot] = Field(
        default_factory=dict,
        description="Optional addressable placement slots defined inside the holder.",
    )

    @field_validator("name", "model_name")
    def _validate_non_empty_text(cls, value: str) -> str:
        return Labware.validate_name(value)

    @field_validator("length_mm", "width_mm", "height_mm")
    def _validate_positive_dimension(cls, value: float, info):  # type: ignore[override]
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive.")
        return value

    @field_validator("slots")
    def _validate_slot_names(cls, value: Dict[str, LabwareSlot]) -> Dict[str, LabwareSlot]:
        for slot_name in value:
            if not slot_name.strip():
                raise ValueError("Holder slot names must be non-empty strings.")
        return value

    def get_location(self, location_id: str | None = None) -> Coordinate3D:
        if location_id is None or location_id in {"location", "anchor", self.name}:
            return self.location

        try:
            return self.slots[location_id].location
        except KeyError as exc:
            raise KeyError(f"Unknown location ID '{location_id}'") from exc

    def get_slot(self, slot_id: str) -> Coordinate3D:
        return self.get_location(slot_id)

    def get_initial_position(self) -> Coordinate3D:
        return self.location

    def iter_positions(self) -> dict[str, Coordinate3D]:
        positions = {"location": self.location}
        positions.update({slot_id: slot.location for slot_id, slot in self.slots.items()})
        return positions


class TipHolder(HolderLabware):
    """Bounding-box model for the tip holder fixture."""

    model_name: str = "tip_holder"
    length_mm: float = 138.0
    width_mm: float = 66.0
    height_mm: float = 22.0


class TipDisposal(HolderLabware):
    """Bounding-box model for the used-tip disposal fixture."""

    model_name: str = "tip_disposal"
    length_mm: float = 198.0
    width_mm: float = 62.0
    height_mm: float = 30.0


class WellPlateHolder(HolderLabware):
    """Holder for a single well plate or slide-mounted plate assembly."""

    model_name: str = "SlideHolder_Top"
    length_mm: float = 100.0
    width_mm: float = 155.0
    height_mm: float = 14.8

    def get_plate_slot(self, slot_id: str = "plate") -> Coordinate3D:
        return self.get_slot(slot_id)


class VialHolder(HolderLabware):
    """Holder for a linear array of vial slots."""

    model_name: str = "9VialHolder20mL_TightFit"
    length_mm: float = 36.2
    width_mm: float = 300.2
    height_mm: float = 35.1
    slot_count: int = Field(default=9, description="Maximum number of supported vial slots.")

    @field_validator("slot_count")
    def _validate_slot_count(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("slot_count must be positive.")
        return value

    @model_validator(mode="after")
    def _validate_slot_capacity(self) -> "VialHolder":
        if len(self.slots) > self.slot_count:
            raise ValueError("slots count must be <= slot_count.")
        return self

    def get_vial_slot(self, slot_id: str) -> Coordinate3D:
        return self.get_slot(slot_id)
