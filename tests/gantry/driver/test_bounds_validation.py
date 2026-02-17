from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.gantry.gantry_driver.driver import Coordinates, Mill


def _mill() -> Mill:
    config = {
        "$20": "1",
        "$130": "415.0",
        "$131": "300.0",
        "$132": "200.0",
        "$10": "0",
        "$27": "1.0",
    }
    with (
        patch("src.gantry.gantry_driver.driver.set_up_mill_logger", return_value=MagicMock()),
        patch("src.gantry.gantry_driver.driver.set_up_command_logger", return_value=MagicMock()),
        patch.object(Mill, "read_mill_config_file", return_value=config),
    ):
        return Mill()


def test_validate_target_coordinates_accepts_limits():
    mill = _mill()

    mill._validate_target_coordinates(Coordinates(x=0.0, y=0.0, z=0.0))
    mill._validate_target_coordinates(Coordinates(x=-415.0, y=-300.0, z=-200.0))


def test_validate_target_coordinates_rejects_x_overreach():
    mill = _mill()

    with pytest.raises(Exception, match="x"):
        mill._validate_target_coordinates(Coordinates(x=1.0, y=-50.0, z=-10.0))

    with pytest.raises(Exception, match="x"):
        mill._validate_target_coordinates(Coordinates(x=-416.0, y=-50.0, z=-10.0))


def test_validate_target_coordinates_rejects_y_overreach():
    mill = _mill()

    with pytest.raises(Exception, match="y"):
        mill._validate_target_coordinates(Coordinates(x=-50.0, y=1.0, z=-10.0))

    with pytest.raises(Exception, match="y"):
        mill._validate_target_coordinates(Coordinates(x=-50.0, y=-301.0, z=-10.0))


def test_validate_target_coordinates_rejects_z_overreach():
    mill = _mill()

    with pytest.raises(Exception, match="z"):
        mill._validate_target_coordinates(Coordinates(x=-50.0, y=-50.0, z=1.0))

    with pytest.raises(Exception, match="z"):
        mill._validate_target_coordinates(Coordinates(x=-50.0, y=-50.0, z=-201.0))


def test_validate_target_coordinates_raises_descriptive_message():
    mill = _mill()

    with pytest.raises(Exception, match="target"):
        mill._validate_target_coordinates(Coordinates(x=5.0, y=0.0, z=0.0))


def test_safe_move_calls_validate_target_coordinates():
    mill = _mill()
    mill.current_coordinates = MagicMock(return_value=Coordinates(0.0, 0.0, 0.0))
    mill._validate_target_coordinates = MagicMock()
    mill.execute_command = MagicMock()

    mill.safe_move(x_coord=-10.0, y_coord=-10.0, z_coord=-10.0)

    mill._validate_target_coordinates.assert_called_once()


def test_move_to_position_calls_validate_target_coordinates():
    mill = _mill()
    mill.current_coordinates = MagicMock(return_value=Coordinates(0.0, 0.0, 0.0))
    mill._validate_target_coordinates = MagicMock()
    mill.execute_command = MagicMock()

    mill.move_to_position(x_coordinate=-10.0, y_coordinate=-10.0, z_coordinate=-10.0)

    mill._validate_target_coordinates.assert_called_once()


def test_move_to_positions_calls_validate_target_coordinates_for_each_target():
    mill = _mill()
    mill.current_coordinates = MagicMock(return_value=Coordinates(0.0, 0.0, 0.0))
    mill._validate_target_coordinates = MagicMock()
    mill.execute_command = MagicMock()

    mill.move_to_positions(
        coordinates=[
            Coordinates(-10.0, -10.0, -10.0),
            Coordinates(-20.0, -20.0, -20.0),
        ]
    )

    assert mill._validate_target_coordinates.call_count == 2
