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
    be measured by jogging to a front-left XY reference, assigning only X/Y to
    zero, jogging to a known-height labware/artifact Z reference surface,
    assigning only Z to that surface height, then re-homing and reading WPos at
    the homed back-right-top corner.
    """
    validate_deck_origin_minima(config)
    return DeckOriginCalibrationPlan(
        origin_wpos=(0.0, 0.0, 0.0),
        commands=(
            "$H",
            "G92.1",
            "<interactive jog to front-left XY origin/lower reach point>",
            "G10 L20 P1 X0 Y0",
            "<interactive jog to labware/artifact Z reference surface>",
            "G10 L20 P1 Z<reference_surface_z_mm>",
            "$H",
            "?",
        ),
    )
