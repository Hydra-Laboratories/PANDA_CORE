"""Helpers for deck-origin work-coordinate calibration."""

from __future__ import annotations

from dataclasses import dataclass

from .gantry_config import GantryConfig


_ZERO_TOLERANCE = 1e-9


@dataclass(frozen=True)
class DeckOriginCalibrationPlan:
    """Concrete GRBL command skeleton for physical-origin calibration."""

    origin_wpos: tuple[float, float, float]
    commands: tuple[str, ...]


def format_gcode_number(value: float) -> str:
    """Format a float compactly for G-code command strings."""
    formatted = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return formatted if formatted and formatted != "-0" else "0"


def format_set_work_position_command(
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
) -> str:
    """Return a G10 command that assigns WPos at the current machine pose."""
    parts = ["G10 L20 P1"]
    if x is not None:
        parts.append(f"X{format_gcode_number(x)}")
    if y is not None:
        parts.append(f"Y{format_gcode_number(y)}")
    if z is not None:
        parts.append(f"Z{format_gcode_number(z)}")
    if len(parts) == 1:
        raise ValueError("At least one axis must be supplied.")
    return " ".join(parts)


def validate_deck_origin_minima(config: GantryConfig) -> None:
    """Validate that a gantry config is in the deck-origin frame shape."""
    volume = config.working_volume
    non_zero_xy_mins = [
        (axis, value)
        for axis, value in (
            ("x_min", volume.x_min),
            ("y_min", volume.y_min),
        )
        if abs(value) > _ZERO_TOLERANCE
    ]
    if non_zero_xy_mins:
        formatted = ", ".join(f"{axis}={value}" for axis, value in non_zero_xy_mins)
        raise ValueError(
            "Deck-origin calibration requires working_volume X/Y minima at 0.0; "
            f"got {formatted}. Use a deck-origin gantry config before setting "
            "front-left-bottom origin."
        )
    if volume.z_min < -_ZERO_TOLERANCE:
        raise ValueError(
            "Deck-origin calibration requires working_volume.z_min >= 0.0; "
            f"got z_min={volume.z_min}. Use a deck-origin gantry config before "
            "setting front-left-bottom origin."
        )


def build_deck_origin_calibration_plan(
    config: GantryConfig,
) -> DeckOriginCalibrationPlan:
    """Build the GRBL command skeleton for FLB deck-origin calibration."""
    if config.calibration_homing is None:
        raise ValueError(
            "Deck-origin calibration requires cnc.calibration_homing with "
            "runtime_brt and origin_flb profiles. The script must not infer "
            "$3 or $23."
        )
    runtime = config.calibration_homing.runtime_brt
    origin = config.calibration_homing.origin_flb
    return DeckOriginCalibrationPlan(
        origin_wpos=(0.0, 0.0, 0.0),
        commands=(
            "$$",
            f"$3={format_gcode_number(origin.dir_invert_mask)}",
            f"$23={format_gcode_number(origin.homing_dir_mask)}",
            "$22=1",
            "$H  # FLB",
            "G54",
            "G92.1",
            "G10 L20 P1 X0 Y0 Z0",
            "$20=0",
            "<estimate working_volume maxima from configured bounds minus margin>",
            "<blocking move to estimated BRT inspection pose>",
            "$130=<x_span_mm>",
            "$131=<y_span_mm>",
            "$132=<z_span_mm>",
            "$22=1",
            "$20=1",
            f"$3={format_gcode_number(runtime.dir_invert_mask)}",
            f"$23={format_gcode_number(runtime.homing_dir_mask)}",
            "$22=1  # restore runtime profile without BRT $H",
            "?",
            "<optional instrument TCP calibration>",
        ),
    )
