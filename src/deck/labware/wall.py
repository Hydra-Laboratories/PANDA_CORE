"""Simple rectangular obstacle on the deck defined by location and dimensions."""

from __future__ import annotations

from .holder import HolderLabware
from .labware import Coordinate3D


class Wall(HolderLabware):
    """Rectangular physical obstacle defined by a reference point and bounding box.

    ``location`` is the minimum-coordinate corner of the wall. The box
    extends ``+length_mm`` in X, ``+width_mm`` in Y, ``+height_mm`` in Z.

    Walls have no slots, tips, or wells — they exist purely as geometry
    for bounds validation and collision avoidance.
    """

    model_name: str = "wall"

    @property
    def x_min(self) -> float:
        return self.location.x

    @property
    def x_max(self) -> float:
        return self.location.x + self.length_mm

    @property
    def y_min(self) -> float:
        return self.location.y

    @property
    def y_max(self) -> float:
        return self.location.y + self.width_mm

    @property
    def z_min(self) -> float:
        return self.location.z

    @property
    def z_max(self) -> float:
        return self.location.z + self.height_mm

    def iter_positions(self) -> dict[str, Coordinate3D]:
        """Return the corner positions of the wall bounding box."""
        z_lo, z_hi = self.z_min, self.z_max
        return {
            "location": self.location,
            "min": Coordinate3D(x=self.x_min, y=self.y_min, z=z_lo),
            "max": Coordinate3D(x=self.x_max, y=self.y_max, z=z_hi),
        }
