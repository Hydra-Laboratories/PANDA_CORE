from __future__ import annotations

from .holder import HolderLabware


class TipHolder(HolderLabware):
    """Bounding-box model for the tip holder fixture."""

    model_name: str = "tip_holder"
    length_mm: float = 138.0
    width_mm: float = 66.0
    height_mm: float = 22.0
