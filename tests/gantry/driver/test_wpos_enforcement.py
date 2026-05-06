"""Unit tests for WPos enforcement in Mill driver."""

import unittest
from unittest.mock import MagicMock, patch

from gantry.gantry_driver.driver import Mill, wpos_pattern, mpos_pattern, wco_pattern
from gantry.gantry_driver.exceptions import StatusReturnError
from gantry.gantry_driver.instruments import Coordinates


class TestWposEnforcement(unittest.TestCase):
    """Tests that Mill always returns work position coordinates."""

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def _make_mill(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Create a Mill with mocked serial for testing."""
        mill = Mill()
        mill.ser_mill = MagicMock()
        mill.active_connection = True
        mill.config["$10"] = "0"
        mill.config["$27"] = "2.000"
        return mill

    def test_current_coordinates_returns_wpos_when_wpos_reported(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(return_value="<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>")
        coords = mill.current_coordinates()
        self.assertEqual(coords.x, 10.0)
        self.assertEqual(coords.y, 20.0)
        self.assertEqual(coords.z, 5.0)

    def test_current_coordinates_extracts_status_from_multiline_read(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="ok\n<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>\n"
        )
        coords = mill.current_coordinates()
        self.assertEqual(coords.x, 10.0)
        self.assertEqual(coords.y, 20.0)
        self.assertEqual(coords.z, 5.0)
        mill.ser_mill.write.assert_called_once_with(b"?")

    def test_extract_status_line_ignores_serial_chatter(self):
        status = Mill._extract_status_line(
            "ok\n[MSG:Reset to continue]\n<Idle|WPos:1.000,2.000,3.000|FS:0,0>\n"
        )
        self.assertEqual(status, "<Idle|WPos:1.000,2.000,3.000|FS:0,0>")

    def test_extract_status_line_ignores_incomplete_status_fragment(self):
        status = Mill._extract_status_line("<Idle|WPos:1.000,2.000,3")
        self.assertEqual(status, "")

    def test_extract_status_line_skips_incomplete_fragment_before_complete_status(self):
        status = Mill._extract_status_line(
            "<Idle|WPos:1.000,2.000,3\n"
            "<Idle|WPos:4.000,5.000,6.000|FS:0,0>\n"
        )
        self.assertEqual(status, "<Idle|WPos:4.000,5.000,6.000|FS:0,0>")

    def test_current_status_queries_before_reading_status(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>"
        )

        status = mill.current_status()

        self.assertEqual(status, "<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>")
        mill.ser_mill.write.assert_called_once_with(b"?")

    def test_current_status_retries_after_incomplete_status_fragment(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            side_effect=[
                "<Idle|WPos:10.000,20.000,5",
                "<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>",
            ]
        )

        status = mill.current_status()

        self.assertEqual(status, "<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>")
        self.assertEqual(mill.ser_mill.write.call_count, 2)
        mill.ser_mill.write.assert_called_with(b"?")

    def test_current_coordinates_requeries_after_incomplete_status_fragment(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            side_effect=[
                "<Idle|WPos:10.000,20.000,5",
                "<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>",
            ]
        )

        coords = mill.current_coordinates()

        self.assertEqual(coords.x, 10.0)
        self.assertEqual(coords.y, 20.0)
        self.assertEqual(coords.z, 5.0)
        self.assertEqual(mill.ser_mill.write.call_count, 2)
        mill.ser_mill.write.assert_called_with(b"?")

    def test_current_status_extracts_status_from_multiline_read(self):
        mill = self._make_mill()
        mill.read = MagicMock(
            return_value="ok\n<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>\n"
        )

        status = mill.current_status()

        self.assertEqual(status, "<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>")

    def test_current_status_raises_when_chatter_contains_alarm(self):
        mill = self._make_mill()
        mill.read = MagicMock(
            return_value=(
                "ok\nALARM:2\n"
                "<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>\n"
            )
        )

        with self.assertRaisesRegex(StatusReturnError, "ALARM:2"):
            mill.current_status()

    def test_current_coordinates_raises_when_chatter_contains_alarm(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value=(
                "ok\nALARM:2\n"
                "<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>\n"
            )
        )

        with self.assertRaisesRegex(StatusReturnError, "ALARM:2"):
            mill.current_coordinates()
        self.assertEqual(mill.last_status, mill.read.return_value)
        mill.ser_mill.write.assert_called_once_with(b"?")

    def test_current_coordinates_raises_when_retry_chatter_contains_error(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            side_effect=[
                "<Idle|WPos:10.000,20.000,5",
                "error:15\n<Idle|WPos:10.000,20.000,5.000|Bf:15,127|FS:0,0>\n",
            ]
        )

        with self.assertRaisesRegex(StatusReturnError, "error:15"):
            mill.current_coordinates()
        self.assertEqual(mill.ser_mill.write.call_count, 2)
        mill.ser_mill.write.assert_called_with(b"?")

    def test_current_coordinates_converts_mpos_to_wpos(self):
        mill = self._make_mill()
        mill.config["$10"] = "1"  # Force MPos mode
        mill._wco = Coordinates(-300.0, -200.0, -80.0)
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|MPos:-290.000,-190.000,-75.000|Bf:15,127|FS:0,0>"
        )
        coords = mill.current_coordinates()
        # WPos = MPos - WCO = -290 - (-300) = 10, etc.
        self.assertAlmostEqual(coords.x, 10.0, places=3)
        self.assertAlmostEqual(coords.y, 10.0, places=3)
        self.assertAlmostEqual(coords.z, 5.0, places=3)

    def test_current_coordinates_updates_wco_from_status(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:0.000,0.000,0.000|Bf:15,127|FS:0,0|WCO:-300.000,-200.000,-80.000>"
        )
        self.assertIsNone(mill._wco)
        mill.current_coordinates()
        self.assertIsNotNone(mill._wco)
        self.assertEqual(mill._wco.x, -300.0)
        self.assertEqual(mill._wco.y, -200.0)
        self.assertEqual(mill._wco.z, -80.0)

    def test_machine_coordinates_returns_mpos(self):
        mill = self._make_mill()
        mill._wco = Coordinates(-300.0, -200.0, -80.0)
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(return_value="<Idle|WPos:10.000,10.000,5.000|Bf:15,127|FS:0,0>")
        mpos = mill.machine_coordinates()
        # MPos = WPos + WCO = 10 + (-300) = -290, etc.
        self.assertAlmostEqual(mpos.x, -290.0, places=3)
        self.assertAlmostEqual(mpos.y, -190.0, places=3)
        self.assertAlmostEqual(mpos.z, -75.0, places=3)

    def test_query_wco_returns_cached(self):
        mill = self._make_mill()
        mill._wco = Coordinates(-300.0, -200.0, -80.0)
        wco = mill._query_work_coordinate_offset()
        self.assertEqual(wco.x, -300.0)
        self.assertEqual(wco.y, -200.0)
        self.assertEqual(wco.z, -80.0)

    def test_query_wco_seeds_when_none(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:0.000,0.000,0.000|Bf:15,127|FS:0,0|WCO:-300.000,-200.000,-80.000>"
        )
        self.assertIsNone(mill._wco)
        wco = mill._query_work_coordinate_offset()
        self.assertEqual(wco.x, -300.0)

    def test_wco_pattern_matches(self):
        status = "<Idle|WPos:0,0,0|Bf:15,127|FS:0,0|WCO:-300.000,-200.000,-80.000>"
        match = wco_pattern.search(status)
        self.assertIsNotNone(match)
        self.assertEqual(float(match.group(1)), -300.0)
        self.assertEqual(float(match.group(2)), -200.0)
        self.assertEqual(float(match.group(3)), -80.0)

    def test_move_to_position_uses_wpos_internally(self):
        """Verify move_to_position's internal current_coordinates call gets WPos."""
        mill = self._make_mill()
        mill.config["$10"] = "0"
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(return_value="<Idle|WPos:0.000,0.000,0.000|Bf:15,127|FS:0,0>")

        commands_sent = []
        mill.execute_command = lambda cmd: commands_sent.append(cmd) or "ok"

        mill.move_to_position(x_coordinate=-10.0, y_coordinate=-10.0, z_coordinate=0.0)

        # X and Y are always emitted on separate lines — no diagonal.
        x_commands = [c for c in commands_sent if "X-10.0" in c and "Y" not in c]
        y_commands = [c for c in commands_sent if "Y-10.0" in c and "X" not in c]
        self.assertEqual(len(x_commands), 1)
        self.assertEqual(len(y_commands), 1)


if __name__ == '__main__':
    unittest.main()
