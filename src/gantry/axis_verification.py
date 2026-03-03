"""Pure helpers for hardware axis-position verification scripts."""

from __future__ import annotations

from typing import Any, Mapping

from .gantry_config import WorkingVolume

_AXIS_TO_INDEX = {"x": 0, "y": 1, "z": 2}


def working_volume_from_config(config: Mapping[str, Any]) -> WorkingVolume:
    """Build a WorkingVolume from a raw gantry config dict."""
    raw_volume = config.get("working_volume")
    if not isinstance(raw_volume, Mapping):
        raise ValueError("Gantry config must include a 'working_volume' mapping.")

    required_keys = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
    missing = [key for key in required_keys if key not in raw_volume]
    if missing:
        raise ValueError(f"Missing required working_volume keys: {', '.join(missing)}")

    return WorkingVolume(
        x_min=float(raw_volume["x_min"]),
        x_max=float(raw_volume["x_max"]),
        y_min=float(raw_volume["y_min"]),
        y_max=float(raw_volume["y_max"]),
        z_min=float(raw_volume["z_min"]),
        z_max=float(raw_volume["z_max"]),
    )


def build_safe_xy_corners(
    volume: WorkingVolume,
    edge_margin_mm: float,
    z_height: float | None = None,
) -> list[tuple[float, float, float]]:
    """Return 4 XY corner targets inset from hard edges by margin."""
    if edge_margin_mm < 0:
        raise ValueError("edge_margin_mm must be >= 0.")

    x_low = volume.x_min + edge_margin_mm
    x_high = volume.x_max - edge_margin_mm
    y_low = volume.y_min + edge_margin_mm
    y_high = volume.y_max - edge_margin_mm

    if x_low >= x_high or y_low >= y_high:
        raise ValueError("edge_margin_mm is too large for the configured working volume.")

    z = volume.z_min if z_height is None else float(z_height)
    if not volume.contains(x_low, y_low, z):
        raise ValueError("z_height is outside the configured working volume.")

    return [
        (x_low, y_low, z),
        (x_high, y_low, z),
        (x_high, y_high, z),
        (x_low, y_high, z),
    ]


def choose_axis_target(
    start_xyz: tuple[float, float, float],
    axis: str,
    step_mm: float,
    volume: WorkingVolume,
    edge_margin_mm: float,
) -> tuple[float, float, float]:
    """Choose a safe step target for one axis, preferring + direction."""
    normalized_axis = axis.lower()
    if normalized_axis not in _AXIS_TO_INDEX:
        raise ValueError(f"Unsupported axis '{axis}'. Expected one of x, y, z.")
    if step_mm <= 0:
        raise ValueError("step_mm must be > 0.")
    if edge_margin_mm < 0:
        raise ValueError("edge_margin_mm must be >= 0.")

    index = _AXIS_TO_INDEX[normalized_axis]
    values = [float(start_xyz[0]), float(start_xyz[1]), float(start_xyz[2])]

    lower_bound = getattr(volume, f"{normalized_axis}_min") + edge_margin_mm
    upper_bound = getattr(volume, f"{normalized_axis}_max") - edge_margin_mm
    current_value = values[index]

    if current_value + step_mm <= upper_bound:
        values[index] = current_value + step_mm
        return (values[0], values[1], values[2])
    if current_value - step_mm >= lower_bound:
        values[index] = current_value - step_mm
        return (values[0], values[1], values[2])

    raise ValueError(
        f"Unable to apply step of {step_mm}mm on axis {normalized_axis} "
        "within margin-constrained bounds."
    )


def is_within_tolerance(actual: float, expected: float, tolerance_mm: float) -> bool:
    """Return True if absolute error is within tolerance."""
    if tolerance_mm < 0:
        raise ValueError("tolerance_mm must be >= 0.")
    return abs(actual - expected) <= tolerance_mm
