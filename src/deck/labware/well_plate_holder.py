from __future__ import annotations

from .holder import HolderLabware
from .labware import Coordinate3D


class WellPlateHolder(HolderLabware):
    """Holder for a single well plate or slide-mounted plate assembly."""

    model_name: str = "SlideHolder_Top"
    length_mm: float = 100.0
    width_mm: float = 155.0
    height_mm: float = 14.8
    labware_support_height_mm: float = 10.0
    labware_seat_height_from_bottom_mm: float = 5.0

    def get_plate_slot(self, slot_id: str = "plate") -> Coordinate3D:
        return self.get_slot(slot_id)
