from __future__ import annotations

from typing import Dict, Optional

from pydantic import ConfigDict, Field, PrivateAttr, model_validator

from .holder import _SEAT_Z_TOLERANCE_MM, HolderLabware
from .labware import Coordinate3D, Labware
from .well_plate import WellPlate


class WellPlateHolder(HolderLabware):
    """Holder for a single well plate or slide-mounted plate assembly."""

    model_config = ConfigDict(
        extra="forbid", protected_namespaces=(), validate_assignment=True
    )

    model_name: str = "SlideHolder_Top"
    length_mm: float = 100.0
    width_mm: float = 155.0
    height_mm: float = 14.8
    labware_support_height_mm: float = 10.0
    labware_seat_height_from_bottom_mm: float = 5.0
    well_plate: Optional[WellPlate] = Field(
        default=None,
        description="Well plate held by this holder.",
    )

    # Tracks the plate this holder owned at the end of the most recent
    # successful validator run, so reassignment clears the previous plate's
    # `.holder` back-reference.
    _prev_well_plate: Optional[WellPlate] = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _validate_holder_state(self) -> "WellPlateHolder":
        plate = self.well_plate

        if plate is None:
            if self._prev_well_plate is not None and self._prev_well_plate.holder is self:
                self._prev_well_plate.holder = None
            self._prev_well_plate = None
            return self

        # WellPlateHolder narrows labware_seat_height_from_bottom_mm to a
        # non-optional float at the field level, so it is always set here.

        if plate.holder is not None and plate.holder is not self:
            raise ValueError(
                f"well_plate '{plate.name}' is already held by another "
                f"WellPlateHolder ('{plate.holder.name}'); each plate may "
                "belong to at most one holder."
            )

        if plate.height_mm is None:
            raise ValueError(
                f"well_plate '{plate.name}' held by WellPlateHolder '{self.name}' "
                "has no height_mm; top-Z calculations would fail at runtime."
            )

        expected_z = self.location.z + self.labware_seat_height_from_bottom_mm
        a1 = plate.get_initial_position()
        if abs(a1.z - expected_z) > _SEAT_Z_TOLERANCE_MM:
            raise ValueError(
                f"well_plate '{plate.name}' A1 z={a1.z} is inconsistent with "
                f"WellPlateHolder '{self.name}' seat z={expected_z} "
                f"(holder.location.z + labware_seat_height_from_bottom_mm)."
            )

        # Clear back-ref on the previously held plate if it was replaced.
        if (
            self._prev_well_plate is not None
            and self._prev_well_plate is not plate
            and self._prev_well_plate.holder is self
        ):
            self._prev_well_plate.holder = None

        plate.holder = self
        self._prev_well_plate = plate
        return self

    def _iter_contained_labware(self) -> Dict[str, Labware]:
        if self.well_plate is None:
            return {}
        return {self.well_plate.name: self.well_plate}

    def get_plate_slot(self, slot_id: str = "plate") -> Coordinate3D:
        return self.get_slot(slot_id)

    def get_plate_top_z(self) -> float:
        """Return the absolute deck Z of the top surface of the held plate.

        The holder validator already requires ``well_plate.height_mm`` to be
        set when a plate is assigned, so these raises are unreachable for
        holders constructed through normal paths. They guard programmatic
        callers who construct `WellPlateHolder(name=..., location=...)`
        without a plate and then call this helper anyway.

        Raises:
            ValueError: if this holder does not contain a well plate, or if
                the held plate somehow has no ``height_mm``.
        """
        if self.well_plate is None:
            raise ValueError(
                f"WellPlateHolder '{self.name}' does not contain a well plate."
            )
        if self.well_plate.height_mm is None:
            raise ValueError(
                f"WellPlate '{self.well_plate.name}' requires height_mm to compute top Z."
            )
        a1 = self.well_plate.get_initial_position()
        return a1.z + self.well_plate.height_mm
