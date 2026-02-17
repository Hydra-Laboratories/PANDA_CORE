from __future__ import annotations

from unittest.mock import MagicMock

from test_scripts.validate_overreach_recovery_hardware import connect_and_home


def test_connect_and_home_calls_connect_then_home():
    gantry = MagicMock()

    connect_and_home(gantry)

    gantry.connect.assert_called_once()
    gantry.home.assert_called_once()
