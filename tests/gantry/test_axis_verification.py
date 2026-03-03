"""Tests for hardware axis-position verification helpers."""

from __future__ import annotations

import pytest

from src.gantry.axis_verification import (
    build_safe_xy_corners,
    choose_axis_target,
    is_within_tolerance,
    working_volume_from_config,
)
from src.gantry.gantry_config import WorkingVolume


def _sample_config() -> dict:
    return {
        "working_volume": {
            "x_min": 0.0,
            "x_max": 300.0,
            "y_min": 0.0,
            "y_max": 200.0,
            "z_min": 0.0,
            "z_max": 80.0,
        }
    }


def test_working_volume_from_config_returns_working_volume() -> None:
    volume = working_volume_from_config(_sample_config())
    assert volume == WorkingVolume(
        x_min=0.0,
        x_max=300.0,
        y_min=0.0,
        y_max=200.0,
        z_min=0.0,
        z_max=80.0,
    )


def test_build_safe_xy_corners_returns_four_points_inside_volume() -> None:
    volume = working_volume_from_config(_sample_config())
    corners = build_safe_xy_corners(volume, edge_margin_mm=10.0, z_height=0.0)

    assert len(corners) == 4
    assert corners == [
        (10.0, 10.0, 0.0),
        (290.0, 10.0, 0.0),
        (290.0, 190.0, 0.0),
        (10.0, 190.0, 0.0),
    ]
    assert all(volume.contains(*corner) for corner in corners)


def test_choose_axis_target_prefers_positive_direction() -> None:
    volume = working_volume_from_config(_sample_config())
    start = (150.0, 100.0, 0.0)

    assert choose_axis_target(start, axis="x", step_mm=5.0, volume=volume, edge_margin_mm=10.0) == (
        155.0,
        100.0,
        0.0,
    )


def test_choose_axis_target_falls_back_to_negative_direction() -> None:
    volume = working_volume_from_config(_sample_config())
    start = (289.0, 100.0, 0.0)

    assert choose_axis_target(start, axis="x", step_mm=5.0, volume=volume, edge_margin_mm=10.0) == (
        284.0,
        100.0,
        0.0,
    )


def test_choose_axis_target_raises_when_step_cannot_fit_margin_window() -> None:
    volume = working_volume_from_config(_sample_config())
    start = (150.0, 100.0, 0.0)

    with pytest.raises(ValueError, match="Unable to apply step"):
        choose_axis_target(
            start,
            axis="x",
            step_mm=500.0,
            volume=volume,
            edge_margin_mm=10.0,
        )


def test_is_within_tolerance_uses_absolute_error() -> None:
    assert is_within_tolerance(actual=10.02, expected=10.0, tolerance_mm=0.05)
    assert not is_within_tolerance(actual=10.08, expected=10.0, tolerance_mm=0.05)
