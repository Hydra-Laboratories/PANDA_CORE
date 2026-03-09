"""Tests for Gantry user/machine translation boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from gantry.gantry import Gantry


def _config() -> dict:
    return {
        "cnc": {"homing_strategy": "standard", "total_z_height": 90.0},
        "working_volume": {
            "x_min": 0.0,
            "x_max": 300.0,
            "y_min": 0.0,
            "y_max": 200.0,
            "z_min": 0.0,
            "z_max": 80.0,
        },
    }


@patch("gantry.gantry.Mill")
def test_move_to_translates_user_to_machine_coordinates(mock_mill_cls) -> None:
    gantry = Gantry(config=_config())
    gantry.move_to(150.0, 100.0, 40.0)
    mock_mill_cls.return_value.safe_move.assert_called_once_with(
        x_coord=-150.0,
        y_coord=-100.0,
        z_coord=-40.0,
    )


@patch("gantry.gantry.Mill")
def test_get_coordinates_translates_machine_to_user(mock_mill_cls) -> None:
    mock_mill_cls.return_value.current_coordinates.return_value = SimpleNamespace(
        x=-150.0,
        y=-100.0,
        z=-40.0,
    )
    gantry = Gantry(config=_config())
    coords = gantry.get_coordinates()
    assert coords == {"x": 150.0, "y": 100.0, "z": 40.0}


@patch("gantry.gantry.Mill")
def test_get_status_translates_visible_coordinates(mock_mill_cls) -> None:
    mock_mill_cls.return_value.current_status.return_value = (
        "<Idle|MPos:-150.000,-100.000,-40.000|Bf:15,127|FS:0,0>"
    )
    gantry = Gantry(config=_config())
    status = gantry.get_status()
    assert status == "<Idle|MPos:150.000,100.000,40.000|Bf:15,127|FS:0,0>"


@patch("gantry.gantry.Mill")
def test_zero_home_coordinates_stay_zero(mock_mill_cls) -> None:
    mock_mill_cls.return_value.current_coordinates.return_value = SimpleNamespace(
        x=0.0,
        y=0.0,
        z=0.0,
    )
    gantry = Gantry(config=_config())
    assert gantry.get_coordinates() == {"x": 0.0, "y": 0.0, "z": 0.0}


@patch("gantry.gantry.Mill")
def test_boundary_translation(mock_mill_cls) -> None:
    gantry = Gantry(config=_config())
    gantry.move_to(300.0, 200.0, 80.0)
    mock_mill_cls.return_value.safe_move.assert_called_once_with(
        x_coord=-300.0,
        y_coord=-200.0,
        z_coord=-80.0,
    )


@patch("gantry.gantry.Mill")
def test_jog_negates_user_coordinates(mock_mill_cls) -> None:
    gantry = Gantry(config=_config())
    gantry.jog(x=5.0, y=3.0, z=1.0)
    mock_mill_cls.return_value.jog.assert_called_once_with(
        x=-5.0, y=-3.0, z=-1.0, feed_rate=2000,
    )


@patch("gantry.gantry.Mill")
def test_jog_cancel_delegates_to_mill(mock_mill_cls) -> None:
    gantry = Gantry(config=_config())
    gantry.jog_cancel()
    mock_mill_cls.return_value.jog_cancel.assert_called_once()


@patch("gantry.gantry.Mill")
def test_unlock_delegates_to_mill_reset(mock_mill_cls) -> None:
    gantry = Gantry(config=_config())
    gantry.unlock()
    mock_mill_cls.return_value.reset.assert_called_once()


def test_total_z_height_property_from_config() -> None:
    gantry = Gantry(config=_config())
    assert gantry.total_z_height == 90.0
