from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field, field_validator, model_validator


class Coordinate3D(BaseModel):
    """Simple 3D coordinate representation in deck space (absolute machine coordinates)."""

    x: float
    y: float
    z: float


class Labware(BaseModel):
    """
    Base model for all labware on the deck.

    Labware instances provide a mapping from logical position IDs (e.g. \"A1\")
    to absolute 3D centers in deck coordinates. Subclasses (e.g. WellPlate, Vial)
    extend this with domain-specific geometry.
    """

    name: str = Field(..., description="Unique labware name (e.g. 'SBS_96').")
    locations: Dict[str, Coordinate3D] = Field(
        default_factory=dict,
        description="Mapping from position IDs (e.g. 'A1') to absolute XYZ centers.",
    )

    @field_validator("name")
    def _validate_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Labware name must be a non-empty string.")
        return value

    @model_validator(mode="after")
    def _validate_locations(self) -> "Labware":
        # Subclasses such as WellPlate and Vial may populate `locations`
        # in their own `model_validator` methods. Here we simply enforce
        # that, after all validation, at least one location exists.
        if not getattr(self, "locations", None):
            raise ValueError("Labware must define at least one location.")
        return self

    def get_location(self, location_id: str) -> Coordinate3D:
        """
        Return the center coordinate for a logical location ID.

        Raises:
            KeyError: if the location ID does not exist on this labware.
        """
        try:
            return self.locations[location_id]
        except KeyError as exc:
            raise KeyError(f"Unknown location ID '{location_id}'") from exc

