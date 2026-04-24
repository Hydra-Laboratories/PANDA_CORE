"""Strict Pydantic schemas for gantry YAML."""

from __future__ import annotations

from typing import Literal, Optional

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


class GrblSettingsYaml(BaseModel):
    """Expected GRBL controller settings, validated against live hardware on connect.

    These mirror the GRBL $ settings that affect motion behavior.
    All fields are optional — only specified values are checked.
    """

    model_config = ConfigDict(extra="forbid")

    dir_invert_mask: Optional[int] = None       # $3  — direction port invert bitmask
    status_report: Optional[int] = None         # $10 — 0=WPos, 1=MPos
    soft_limits: Optional[bool] = None          # $20
    hard_limits: Optional[bool] = None          # $21
    homing_enable: Optional[bool] = None        # $22
    homing_dir_mask: Optional[int] = None       # $23 — homing direction invert bitmask
    homing_pull_off: Optional[float] = None     # $27 — mm
    steps_per_mm_x: Optional[float] = None      # $100
    steps_per_mm_y: Optional[float] = None      # $101
    steps_per_mm_z: Optional[float] = None      # $102
    max_rate_x: Optional[float] = None          # $110 — mm/min
    max_rate_y: Optional[float] = None          # $111
    max_rate_z: Optional[float] = None          # $112
    accel_x: Optional[float] = None             # $120 — mm/s²
    accel_y: Optional[float] = None             # $121
    accel_z: Optional[float] = None             # $122
    max_travel_x: Optional[float] = None        # $130 — mm
    max_travel_y: Optional[float] = None        # $131
    max_travel_z: Optional[float] = None        # $132


# Mapping from GrblSettingsYaml field names to GRBL $ codes
GRBL_FIELD_TO_SETTING = {
    "dir_invert_mask": "$3",
    "status_report": "$10",
    "soft_limits": "$20",
    "hard_limits": "$21",
    "homing_enable": "$22",
    "homing_dir_mask": "$23",
    "homing_pull_off": "$27",
    "steps_per_mm_x": "$100",
    "steps_per_mm_y": "$101",
    "steps_per_mm_z": "$102",
    "max_rate_x": "$110",
    "max_rate_y": "$111",
    "max_rate_z": "$112",
    "accel_x": "$120",
    "accel_y": "$121",
    "accel_z": "$122",
    "max_travel_x": "$130",
    "max_travel_y": "$131",
    "max_travel_z": "$132",
}


class CncYaml(BaseModel):
    """CNC gantry settings."""

    model_config = ConfigDict(extra="forbid")

    homing_strategy: Literal["xy_hard_limits", "standard", "manual_origin"]
    total_z_height: float
    y_axis_motion: Literal["head", "bed"] = "head"
    structure_clearance_z: Optional[float] = None

    @model_validator(mode="after")
    def _validate_total_z_height_positive(self) -> "CncYaml":
        if self.total_z_height <= 0:
            raise ValueError("total_z_height must be > 0.")
        if (
            self.structure_clearance_z is not None
            and self.structure_clearance_z < 0
        ):
            raise ValueError("structure_clearance_z must be >= 0.")
        return self


class GantryYamlSchema(BaseModel):
    """Root gantry YAML schema."""

    model_config = ConfigDict(extra="forbid")

    serial_port: str
    cnc: CncYaml
    working_volume: WorkingVolumeYaml
    grbl_settings: Optional[GrblSettingsYaml] = None

    @model_validator(mode="after")
    def _validate_total_height_covers_working_z(self) -> "GantryYamlSchema":
        if self.cnc.total_z_height < self.working_volume.z_max:
            raise ValueError(
                "cnc.total_z_height must be >= working_volume.z_max."
            )
        return self
