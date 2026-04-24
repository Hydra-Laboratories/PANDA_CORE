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


def format_set_work_position_command(x: float, y: float, z: float) -> str:
    """Return a G10 command that assigns WPos at the current machine pose."""
    return (
        "G10 L20 P1 "
        f"X{format_gcode_number(x)} "
        f"Y{format_gcode_number(y)} "
        f"Z{format_gcode_number(z)}"
    )


def validate_deck_origin_minima(config: GantryConfig) -> None:
    """Validate that a gantry config is in the deck-origin frame shape."""
    volume = config.working_volume
    non_zero_mins = [
        (axis, value)
        for axis, value in (
            ("x_min", volume.x_min),
            ("y_min", volume.y_min),
            ("z_min", volume.z_min),
        )
        if abs(value) > _ZERO_TOLERANCE
    ]
    if non_zero_mins:
        formatted = ", ".join(f"{axis}={value}" for axis, value in non_zero_mins)
        raise ValueError(
            "Deck-origin calibration requires working_volume minima at 0.0; "
            f"got {formatted}. Use a deck-origin gantry config before setting "
            "front-left-bottom origin."
        )


def build_deck_origin_calibration_plan(
    config: GantryConfig,
) -> DeckOriginCalibrationPlan:
    """Build the GRBL command skeleton for deck-origin calibration.

    The physical travel values are intentionally not included here. They must
    be measured by jogging to a front-left XY reference and known-height Z surface,
    assigning that pose to X=0, Y=0, Z=<reference_surface_z_mm>, then re-homing
    and reading WPos at the homed back-right-top corner.
    """
    validate_deck_origin_minima(config)
    return DeckOriginCalibrationPlan(
        origin_wpos=(0.0, 0.0, 0.0),
        commands=(
            "$H",
            "G92.1",
            "<interactive jog to front-left XY/known Z reference surface>",
            "G10 L20 P1 X0 Y0 Z<reference_surface_z_mm>",
            "$H",
            "?",
        ),
    )
