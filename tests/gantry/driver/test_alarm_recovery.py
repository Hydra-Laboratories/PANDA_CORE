from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.gantry.gantry_driver.driver import Coordinates, Mill
from src.gantry.gantry_driver.exceptions import StatusReturnError


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


def test_compute_alarm_backoff_moves_toward_interior_from_x_max():
    mill = _mill()
    backoff = mill._compute_alarm_backoff(Coordinates(x=0.0, y=-150.0, z=-100.0))
    assert backoff.x == -2.0


def test_compute_alarm_backoff_moves_toward_interior_from_x_min():
    mill = _mill()
    backoff = mill._compute_alarm_backoff(Coordinates(x=-415.0, y=-150.0, z=-100.0))
    assert backoff.x == 2.0


def test_check_for_alarm_state_uses_recovery():
    mill = _mill()
    mill.read = MagicMock(return_value=[b"<Alarm|MPos:0,0,0|FS:0,0>"])
    mill._recover_from_alarm_state = MagicMock(return_value=True)

    mill.check_for_alarm_state()

    mill._recover_from_alarm_state.assert_called_once_with(context="connect")


def test_wait_for_completion_attempts_alarm_recovery():
    mill = _mill()
    mill._recover_from_alarm_state = MagicMock(return_value=True)
    mill.current_status = MagicMock(return_value="<Idle|MPos:0,0,0|FS:0,0>")

    result = mill._Mill__wait_for_completion("alarm:1", suppress_errors=False, timeout=0.01)

    assert "Idle" in result
    mill._recover_from_alarm_state.assert_called_once()


def test_execute_command_attempts_alarm_recovery_when_response_contains_alarm():
    mill = _mill()
    mill.ser_mill = MagicMock()
    mill.read = MagicMock(return_value="alarm:1")
    mill._recover_from_alarm_state = MagicMock(return_value=True)

    with pytest.raises(StatusReturnError):
        mill.execute_command("$X")

    mill._recover_from_alarm_state.assert_called_once()
