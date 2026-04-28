"""Gantry configuration domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class HomingStrategy(str, Enum):
    """Supported CNC homing strategies."""

    STANDARD = "standard"


class YAxisMotion(str, Enum):
    """Whether Y-axis motion moves the head or the bed (base plate)."""

    HEAD = "head"
    BED = "bed"


@dataclass(frozen=True)
class WorkingVolume:
    """Gantry working volume bounds in millimeters.

    Bounds are inclusive and use the CubOS deck-origin frame for supported
    protocol execution.
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    def __post_init__(self) -> None:
        for axis in ("x", "y", "z"):
            lo = getattr(self, f"{axis}_min")
            hi = getattr(self, f"{axis}_max")
            if lo >= hi:
                raise ValueError(
                    f"{axis}_min ({lo}) must be < {axis}_max ({hi})"
                )

    def contains(self, x: float, y: float, z: float) -> bool:
        """Return True if (x, y, z) is within this working volume (inclusive)."""
        return (
            self.x_min <= x <= self.x_max
            and self.y_min <= y <= self.y_max
            and self.z_min <= z <= self.z_max
        )


@dataclass(frozen=True)
class GantryConfig:
    """Loaded gantry configuration."""

    serial_port: str
    homing_strategy: HomingStrategy
    total_z_height: float
    working_volume: WorkingVolume
    y_axis_motion: YAxisMotion = YAxisMotion.HEAD
    structure_clearance_z: Optional[float] = None
    expected_grbl_settings: Optional[Dict[str, float]] = field(default=None)

    def __post_init__(self) -> None:
        if self.total_z_height <= 0:
            raise ValueError(
                f"total_z_height ({self.total_z_height}) must be > 0"
            )
        if self.structure_clearance_z is not None:
            if not (
                self.working_volume.z_min
                <= self.structure_clearance_z
                <= self.working_volume.z_max
            ):
                raise ValueError(
                    "structure_clearance_z must be within the configured "
                    "working-volume Z bounds."
                )
