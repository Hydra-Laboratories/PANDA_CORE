"""Tests for gantry deck-origin calibration helpers."""

from __future__ import annotations

import pytest

from gantry.gantry_config import (
    CalibrationHomingProfiles,
    GantryConfig,
    HomingProfile,
    HomingStrategy,
    WorkingVolume,
)
from gantry.origin import (
    DeckOriginCalibrationPlan,
    build_deck_origin_calibration_plan,
    format_gcode_number,
    format_set_work_position_command,
    validate_deck_origin_minima,
)


def _deck_origin_config(
    *,
    x_min: float = 0.0,
    y_min: float = 0.0,
    z_min: float = 0.0,
    x_max: float = 300.0,
    y_max: float = 200.0,
    z_max: float = 80.0,
    calibration_homing: bool = True,
) -> GantryConfig:
    return GantryConfig(
        serial_port="/dev/null",
        homing_strategy=HomingStrategy.STANDARD,
        total_z_height=z_max,
        working_volume=WorkingVolume(
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            z_min=z_min,
            z_max=z_max,
        ),
        calibration_homing=(
            CalibrationHomingProfiles(
                runtime_brt=HomingProfile(
                    dir_invert_mask=1,
                    homing_dir_mask=0,
                ),
                origin_flb=HomingProfile(
                    dir_invert_mask=1,
                    homing_dir_mask=7,
                ),
            )
            if calibration_homing
            else None
        ),
    )


class TestFormatGcodeNumber:

    def test_strips_trailing_zeros(self):
        assert format_gcode_number(1.250000) == "1.25"

    def test_strips_trailing_decimal_point(self):
        assert format_gcode_number(7.0) == "7"

    def test_collapses_negative_zero(self):
        assert format_gcode_number(-0.0) == "0"

    def test_preserves_negative_values(self):
        assert format_gcode_number(-12.5) == "-12.5"

    def test_rounds_to_six_decimals(self):
        assert format_gcode_number(0.1234567) == "0.123457"

    def test_handles_integer_input(self):
        assert format_gcode_number(0) == "0"


class TestFormatSetWorkPositionCommand:

    def test_all_axes(self):
        cmd = format_set_work_position_command(x=10.0, y=20.0, z=30.0)
        assert cmd == "G10 L20 P1 X10 Y20 Z30"

    def test_x_only(self):
        assert format_set_work_position_command(x=5.5) == "G10 L20 P1 X5.5"

    def test_y_only(self):
        assert format_set_work_position_command(y=2.0) == "G10 L20 P1 Y2"

    def test_z_only(self):
        assert format_set_work_position_command(z=-1.25) == "G10 L20 P1 Z-1.25"

    def test_x_and_z_skips_y(self):
        cmd = format_set_work_position_command(x=1.0, z=2.0)
        assert cmd == "G10 L20 P1 X1 Z2"

    def test_no_axes_raises(self):
        with pytest.raises(ValueError, match="At least one axis"):
            format_set_work_position_command()


class TestValidateDeckOriginMinima:

    def test_valid_zero_minima(self):
        validate_deck_origin_minima(_deck_origin_config())

    def test_z_min_at_negative_tolerance(self):
        validate_deck_origin_minima(_deck_origin_config(z_min=-1e-12))

    def test_rejects_nonzero_x_min(self):
        with pytest.raises(ValueError, match="x_min"):
            validate_deck_origin_minima(_deck_origin_config(x_min=0.5))

    def test_rejects_nonzero_y_min(self):
        with pytest.raises(ValueError, match="y_min"):
            validate_deck_origin_minima(_deck_origin_config(y_min=-0.5))

    def test_rejects_both_x_and_y_min(self):
        with pytest.raises(ValueError) as info:
            validate_deck_origin_minima(_deck_origin_config(x_min=0.1, y_min=0.2))
        assert "x_min" in str(info.value)
        assert "y_min" in str(info.value)

    def test_rejects_negative_z_min(self):
        with pytest.raises(ValueError, match="z_min"):
            validate_deck_origin_minima(_deck_origin_config(z_min=-1.0))


class TestBuildDeckOriginCalibrationPlan:

    def test_origin_wpos_is_zero(self):
        plan = build_deck_origin_calibration_plan(_deck_origin_config())
        assert plan.origin_wpos == (0.0, 0.0, 0.0)

    def test_returns_plan_instance(self):
        plan = build_deck_origin_calibration_plan(_deck_origin_config())
        assert isinstance(plan, DeckOriginCalibrationPlan)

    def test_rejects_missing_calibration_profiles(self):
        with pytest.raises(ValueError, match="calibration_homing"):
            build_deck_origin_calibration_plan(
                _deck_origin_config(calibration_homing=False)
            )

    def test_command_sequence_starts_with_snapshot_and_flb_profile(self):
        plan = build_deck_origin_calibration_plan(_deck_origin_config())
        assert plan.commands[:4] == ("$$", "$3=1", "$23=7", "$22=1")
        assert "$H  # FLB" in plan.commands
        assert "$H  # BRT" not in plan.commands

    def test_command_sequence_pins_g92_clear_before_origin_assignment(self):
        plan = build_deck_origin_calibration_plan(_deck_origin_config())
        commands = list(plan.commands)
        assert "G92.1" in commands
        assert "G10 L20 P1 X0 Y0 Z0" in commands
        assert commands.index("G92.1") < commands.index("G10 L20 P1 X0 Y0 Z0")

    def test_command_sequence_restores_brt_profile_without_homing(self):
        plan = build_deck_origin_calibration_plan(_deck_origin_config())
        commands = list(plan.commands)
        idx_enable = commands.index("$20=1")
        restore_idx = commands.index("$23=0", idx_enable)
        assert commands.index("$3=1", idx_enable) < restore_idx
        assert not any(command.startswith("$H") and "BRT" in command for command in commands)

    def test_command_sequence_disables_soft_limits_before_writing_max_travel(self):
        plan = build_deck_origin_calibration_plan(_deck_origin_config())
        commands = list(plan.commands)
        idx_disable = commands.index("$20=0")
        idx_x = commands.index("$130=<x_span_mm>")
        idx_y = commands.index("$131=<y_span_mm>")
        idx_z = commands.index("$132=<z_span_mm>")
        idx_homing = commands.index("$22=1", idx_z)
        idx_enable = commands.index("$20=1")
        assert idx_disable < idx_x < idx_y < idx_z < idx_homing < idx_enable

    def test_command_sequence_does_not_re_home_after_soft_limit_reenable(self):
        plan = build_deck_origin_calibration_plan(_deck_origin_config())
        commands = list(plan.commands)
        idx_enable = commands.index("$20=1")
        restore_runtime = commands.index("$22=1  # restore runtime profile without BRT $H")
        assert restore_runtime > idx_enable
        assert not any(command.startswith("$H") and "BRT" in command for command in commands)
        assert commands[-2] == "?"
        assert commands[-1] == "<optional instrument TCP calibration>"
