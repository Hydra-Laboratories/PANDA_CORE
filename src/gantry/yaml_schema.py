"""Strict Pydantic schemas for gantry YAML."""

from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from instruments.yaml_schema import InstrumentYamlEntry

from .grbl_settings import GrblSettingsYaml


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


class HomingProfileYaml(BaseModel):
    """Explicit GRBL settings for one homing profile."""

    model_config = ConfigDict(extra="forbid")

    dir_invert_mask: int
    homing_dir_mask: int


class CalibrationHomingYaml(BaseModel):
    """Calibration-only homing profiles for FLB/BRT switching."""

    model_config = ConfigDict(extra="forbid")

    runtime_brt: HomingProfileYaml
    origin_flb: HomingProfileYaml


class CncYaml(BaseModel):
    """CNC gantry settings."""

    model_config = ConfigDict(extra="forbid")

    homing_strategy: Literal["standard"]
    total_z_height: float
    y_axis_motion: Literal["head", "bed"] = "head"
    structure_clearance_z: Optional[float] = None
    calibration_homing: Optional[CalibrationHomingYaml] = None

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
    """Root gantry YAML schema.

    A gantry YAML is the machine configuration: motion envelope, controller
    expectations, and mounted instruments.
    """

    model_config = ConfigDict(extra="forbid")

    serial_port: str
    cnc: CncYaml
    working_volume: WorkingVolumeYaml
    grbl_settings: Optional[GrblSettingsYaml] = None
    instruments: Dict[str, InstrumentYamlEntry] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_total_height_covers_working_z(self) -> "GantryYamlSchema":
        if self.cnc.total_z_height < self.working_volume.z_max:
            raise ValueError(
                "cnc.total_z_height must be >= working_volume.z_max."
            )
        return self

    @model_validator(mode="after")
    def _validate_calibration_runtime_matches_grbl(self) -> "GantryYamlSchema":
        calibration = self.cnc.calibration_homing
        if calibration is None:
            return self
        if self.grbl_settings is None:
            raise ValueError(
                "cnc.calibration_homing requires grbl_settings.dir_invert_mask "
                "and grbl_settings.homing_dir_mask so runtime_brt is anchored "
                "to the normal runtime profile."
            )

        expected_pairs = (
            ("dir_invert_mask", calibration.runtime_brt.dir_invert_mask),
            ("homing_dir_mask", calibration.runtime_brt.homing_dir_mask),
        )
        for field_name, profile_value in expected_pairs:
            grbl_value = getattr(self.grbl_settings, field_name)
            if grbl_value is None:
                raise ValueError(
                    f"cnc.calibration_homing.runtime_brt.{field_name} "
                    f"requires grbl_settings.{field_name}."
                )
            if int(grbl_value) != int(profile_value):
                raise ValueError(
                    f"cnc.calibration_homing.runtime_brt.{field_name} must "
                    f"match grbl_settings.{field_name}; got {profile_value} "
                    f"vs {grbl_value}."
                )
        return self
