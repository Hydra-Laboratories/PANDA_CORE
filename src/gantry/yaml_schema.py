"""Strict Pydantic schemas for gantry YAML."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class WorkingVolumeYaml(BaseModel):
    """Gantry working volume bounds in millimeters."""

    model_config = ConfigDict(extra="forbid")

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    @model_validator(mode="after")
    def _validate_min_less_than_max(self) -> "WorkingVolumeYaml":
        for axis in ("x", "y", "z"):
            min_val = getattr(self, f"{axis}_min")
            max_val = getattr(self, f"{axis}_max")
            if min_val >= max_val:
                raise ValueError(
                    f"{axis}_min ({min_val}) must be < {axis}_max ({max_val})"
                )
        return self


class CncYaml(BaseModel):
    """CNC gantry settings."""

    model_config = ConfigDict(extra="forbid")

    homing_strategy: Literal["xy_hard_limits", "standard"]


class GantryYamlSchema(BaseModel):
    """Root gantry YAML schema."""

    model_config = ConfigDict(extra="forbid")

    serial_port: str
    cnc: CncYaml
    working_volume: WorkingVolumeYaml
