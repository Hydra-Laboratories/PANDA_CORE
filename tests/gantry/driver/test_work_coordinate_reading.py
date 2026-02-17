from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.gantry.gantry_driver.driver import Mill


def _mill(status_mode: str = "1") -> Mill:
    config = {
        "$20": "1",
        "$130": "415.0",
        "$131": "300.0",
        "$132": "200.0",
        "$10": status_mode,
        "$27": "1.0",
    }
    with (
        patch("src.gantry.gantry_driver.driver.set_up_mill_logger", return_value=MagicMock()),
        patch("src.gantry.gantry_driver.driver.set_up_command_logger", return_value=MagicMock()),
        patch.object(Mill, "read_mill_config_file", return_value=config),
    ):
        mill = Mill()
    mill.ser_mill = MagicMock()
    return mill


def test_current_coordinates_prefers_wpos_even_when_status_mode_is_mpos():
    mill = _mill(status_mode="1")
    mill.read = MagicMock(return_value="<Idle|MPos:236.293,73.637,105.961|WPos:-10.000,-20.000,-30.000|FS:0,0>")

    coords = mill.current_coordinates()

    assert coords.x == -10.0
    assert coords.y == -20.0
    assert coords.z == -30.0


def test_current_coordinates_derives_wpos_from_mpos_and_wco():
    mill = _mill(status_mode="1")
    mill.read = MagicMock(return_value="<Idle|MPos:236.293,73.637,105.961|WCO:246.293,93.637,135.961|FS:0,0>")

    coords = mill.current_coordinates()

    assert coords.x == -10.0
    assert coords.y == -20.0
    assert coords.z == -30.0
