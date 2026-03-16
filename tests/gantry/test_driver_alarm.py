"""Tests for Mill.connect_to_mill alarm-state handling.

When GRBL is in alarm state it rejects all commands except $X and $H.
connect_to_mill must detect this early and skip setup commands that would
hang or fail (read_mill_config, set_feed_rate, etc.).
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from gantry.gantry_driver.driver import Mill
from gantry.gantry_driver.exceptions import MillConnectionError


class TestConnectAlarmDetection(unittest.TestCase):
    """Mill.connect_to_mill skips setup when GRBL reports alarm."""

    def _make_mill_with_mock_serial(self, status_response):
        """Create a Mill with mocked serial that returns the given status."""
        mill = Mill()
        mock_serial = MagicMock()
        mock_serial.is_open = True

        mill.locate_mill_over_serial = MagicMock(
            return_value=(mock_serial, "/dev/ttyUSB0")
        )
        mill.read = MagicMock(return_value=status_response)
        mill.read_mill_config = MagicMock()
        mill.write_mill_config_file = MagicMock()
        mill.read_working_volume = MagicMock()
        mill.clear_buffers = MagicMock()
        mill.set_feed_rate = MagicMock()
        return mill

    def test_alarm_skips_setup_commands(self):
        """When alarm detected, skip read_mill_config/set_feed_rate/etc."""
        mill = self._make_mill_with_mock_serial(
            "<Alarm|WPos:265.441,127.238,0.000|FS:0,0|Pn:Z>"
        )

        mill.connect_to_mill(port="/dev/ttyUSB0")

        mill.read_mill_config.assert_not_called()
        mill.write_mill_config_file.assert_not_called()
        mill.read_working_volume.assert_not_called()
        mill.clear_buffers.assert_not_called()
        mill.set_feed_rate.assert_not_called()

    def test_alarm_returns_serial_connection(self):
        """Even in alarm, connect returns the serial object (connection works)."""
        mill = self._make_mill_with_mock_serial(
            "<Alarm|MPos:0,0,0|FS:0,0>"
        )

        result = mill.connect_to_mill(port="/dev/ttyUSB0")

        self.assertIsNotNone(result)
        self.assertTrue(result.is_open)

    def test_alarm_case_insensitive(self):
        """Alarm detection is case-insensitive."""
        mill = self._make_mill_with_mock_serial(
            "<ALARM|MPos:0,0,0|FS:0,0>"
        )

        mill.connect_to_mill(port="/dev/ttyUSB0")

        mill.read_mill_config.assert_not_called()

    def test_no_alarm_runs_full_setup(self):
        """When status is Idle, all setup commands run normally."""
        mill = self._make_mill_with_mock_serial(
            "<Idle|WPos:100,50,0|FS:0,0>"
        )

        mill.connect_to_mill(port="/dev/ttyUSB0")

        mill.read_mill_config.assert_called_once()
        mill.write_mill_config_file.assert_called_once()
        mill.read_working_volume.assert_called_once()
        mill.clear_buffers.assert_called_once()
        mill.set_feed_rate.assert_called_once()

    def test_no_status_response_runs_full_setup(self):
        """When status query returns empty/None, assume not alarmed and proceed."""
        mill = self._make_mill_with_mock_serial("")

        mill.connect_to_mill(port="/dev/ttyUSB0")

        mill.read_mill_config.assert_called_once()
        mill.set_feed_rate.assert_called_once()

    def test_alarm_sends_status_query(self):
        """connect_to_mill sends '?' to check status after serial connect."""
        mill = self._make_mill_with_mock_serial(
            "<Idle|WPos:0,0,0|FS:0,0>"
        )

        mill.connect_to_mill(port="/dev/ttyUSB0")

        mill.ser_mill.write.assert_called_with(b"?")


if __name__ == "__main__":
    unittest.main()
