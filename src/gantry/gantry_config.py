"""Gantry configuration domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkingVolume:
    """Gantry working volume bounds in millimeters.

    All coordinates use CNC convention: origin at (0, 0, 0),
    working area extends into negative space.
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

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
    homing_strategy: str
    working_volume: WorkingVolume
