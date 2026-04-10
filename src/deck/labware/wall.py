"""Simple rectangular obstacle on the deck defined by location and dimensions."""

from __future__ import annotations

from .holder import HolderLabware


class Wall(HolderLabware):
    """Rectangular physical obstacle defined by a reference point and bounding box.

    Walls have no slots, tips, or wells — they exist purely as geometry
    for bounds validation and collision avoidance.
    """

    model_name: str = "wall"
