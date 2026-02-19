"""Tests for coordinate system standardization.

All coordinates in the PANDA system are Work Position (WPos).
The driver enforces $10=0 on connect and G90 (absolute mode) after homing.
"""

import unittest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from gantry.gantry_driver.driver import Mill, wpos_pattern, Coordinates
from gantry.gantry_driver.exceptions import LocationNotFound, StatusReturnError


class TestWPosEnforcementOnConnect(unittest.TestCase):
    """$10=0 must be sent during connect_to_mill to enforce WPos reporting."""

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def test_connect_enforces_wpos_mode(
        self, mock_cmd_logger, mock_mill_logger, mock_serial
    ):
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial.return_value = mock_serial_instance

        with patch.object(
            Mill,
            "locate_mill_over_serial",
            return_value=(mock_serial_instance, "/dev/test"),
        ):
            mill = Mill()
            mill.read_mill_config = MagicMock()
            mill.write_mill_config_file = MagicMock()
            mill.read_working_volume = MagicMock()
            mill.check_for_alarm_state = MagicMock()
            mill.clear_buffers = MagicMock()
            mill.set_feed_rate = MagicMock()
            mill.enforce_wpos_mode = MagicMock()
            mill.enforce_absolute_positioning = MagicMock()

            mill.connect_to_mill(port="/dev/test")

            mill.enforce_wpos_mode.assert_called_once()

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def test_enforce_wpos_mode_sends_correct_setting(
        self, mock_cmd_logger, mock_mill_logger, mock_serial
    ):
        mill = Mill()
        mill.ser_mill = MagicMock()
        mill.execute_command = MagicMock()

        mill.enforce_wpos_mode()

        mill.execute_command.assert_called_with("$10=0")

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def test_enforce_wpos_mode_updates_config(
        self, mock_cmd_logger, mock_mill_logger, mock_serial
    ):
        mill = Mill()
        mill.ser_mill = MagicMock()
        mill.execute_command = MagicMock()
        mill.config["$10"] = "1"

        mill.enforce_wpos_mode()

        self.assertEqual(mill.config["$10"], "0")


class TestCurrentCoordinatesWPosOnly(unittest.TestCase):
    """current_coordinates() must only parse WPos, never MPos."""

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def _make_mill(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        mill = Mill()
        mill.ser_mill = MagicMock()
        return mill

    def test_parses_wpos_status(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:10.500,20.123,-5.000|FS:0,0>"
        )

        coords = mill.current_coordinates()

        self.assertEqual(coords.x, 10.5)
        self.assertEqual(coords.y, 20.123)
        self.assertEqual(coords.z, -5.0)

    def test_raises_on_mpos_only_status(self):
        """If the machine somehow returns MPos instead of WPos, we should fail clearly."""
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|MPos:-400.123,-299.999,-10.000|FS:0,0>"
        )

        with self.assertRaises(LocationNotFound):
            mill.current_coordinates()

    def test_parses_wpos_with_zero_coordinates(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:0.000,0.000,0.000|FS:0,0>"
        )

        coords = mill.current_coordinates()

        self.assertEqual(coords.x, 0.0)
        self.assertEqual(coords.y, 0.0)
        self.assertEqual(coords.z, 0.0)

    def test_parses_wpos_with_negative_coordinates(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:-100.500,-200.750,-50.250|FS:0,0>"
        )

        coords = mill.current_coordinates()

        self.assertEqual(coords.x, -100.5)
        self.assertEqual(coords.y, -200.75)
        self.assertEqual(coords.z, -50.25)

    def test_does_not_reference_config_10(self):
        """current_coordinates should not branch on $10 since we enforce WPos."""
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:1.0,2.0,3.0|FS:0,0>"
        )
        # Even with $10=1, we should still parse WPos (because we enforce $10=0)
        mill.config["$10"] = "1"

        coords = mill.current_coordinates()

        self.assertEqual(coords.x, 1.0)
        self.assertEqual(coords.y, 2.0)
        self.assertEqual(coords.z, 3.0)

    def test_with_instrument_offset(self):
        mill = self._make_mill()
        mill.ser_mill.write = MagicMock()
        mill.read = MagicMock(
            return_value="<Idle|WPos:10.0,20.0,-5.0|FS:0,0>"
        )
        mill.instrument_manager.get_offset = MagicMock(
            return_value=Coordinates(1.0, 2.0, 0.5)
        )

        instrument_coords = mill.current_coordinates(
            instrument="pipette", instrument_only=True
        )

        self.assertEqual(instrument_coords.x, 9.0)
        self.assertEqual(instrument_coords.y, 18.0)
        self.assertEqual(instrument_coords.z, -5.5)


class TestG90EnforcementOnConnect(unittest.TestCase):
    """G90 (absolute positioning) must be enforced on connect."""

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def test_connect_enforces_absolute_positioning(
        self, mock_cmd_logger, mock_mill_logger, mock_serial
    ):
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial.return_value = mock_serial_instance

        with patch.object(
            Mill,
            "locate_mill_over_serial",
            return_value=(mock_serial_instance, "/dev/test"),
        ):
            mill = Mill()
            mill.read_mill_config = MagicMock()
            mill.write_mill_config_file = MagicMock()
            mill.read_working_volume = MagicMock()
            mill.check_for_alarm_state = MagicMock()
            mill.clear_buffers = MagicMock()
            mill.set_feed_rate = MagicMock()
            mill.enforce_wpos_mode = MagicMock()
            mill.enforce_absolute_positioning = MagicMock()

            mill.connect_to_mill(port="/dev/test")

            mill.enforce_absolute_positioning.assert_called_once()

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def test_enforce_absolute_positioning_sends_g90(
        self, mock_cmd_logger, mock_mill_logger, mock_serial
    ):
        mill = Mill()
        mill.ser_mill = MagicMock()
        mill.execute_command = MagicMock()

        mill.enforce_absolute_positioning()

        mill.execute_command.assert_called_with("G90")


class TestG90AfterHoming(unittest.TestCase):
    """G90 must be enforced after both homing methods."""

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def test_home_enforces_g90_after_completion(
        self, mock_cmd_logger, mock_mill_logger, mock_serial
    ):
        mill = Mill()
        mill.ser_mill = MagicMock()
        mill.execute_command = MagicMock()
        mill.current_status = MagicMock(return_value="<Idle|WPos:0,0,0|FS:0,0>")

        mill.home()

        # G90 should be the last command sent
        calls = mill.execute_command.call_args_list
        self.assertEqual(calls[-1], call("G90"))


class TestPostHomingCoordinateValidation(unittest.TestCase):
    """After homing, WPos should be near the expected origin."""

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def _make_mill(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        mill = Mill()
        mill.ser_mill = MagicMock()
        return mill

    def test_validate_post_homing_coordinates_passes_near_origin(self):
        mill = self._make_mill()

        coords = Coordinates(0.0, 0.0, -2.0)
        # Should not raise
        mill.validate_post_homing_coordinates(coords)

    def test_validate_post_homing_coordinates_fails_on_wildly_off(self):
        mill = self._make_mill()

        coords = Coordinates(-300.0, -200.0, -50.0)
        with self.assertRaises(StatusReturnError):
            mill.validate_post_homing_coordinates(coords)

    def test_homing_sequence_validates_coordinates(self):
        mill = self._make_mill()
        mill.home = MagicMock()
        mill.set_feed_rate = MagicMock()
        mill.clear_buffers = MagicMock()
        mill.check_max_z_height = MagicMock()
        mill.current_coordinates = MagicMock(
            return_value=Coordinates(0.0, 0.0, 0.0)
        )
        mill.validate_post_homing_coordinates = MagicMock()

        mill.homing_sequence()

        mill.validate_post_homing_coordinates.assert_called_once()


class TestMachineCoordinatesMethod(unittest.TestCase):
    """machine_coordinates() should compute MPos from WPos + WCO."""

    @patch("gantry.gantry_driver.driver.serial.Serial")
    @patch("gantry.gantry_driver.driver.set_up_mill_logger")
    @patch("gantry.gantry_driver.driver.set_up_command_logger")
    def _make_mill(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        mill = Mill()
        mill.ser_mill = MagicMock()
        return mill

    def test_machine_coordinates_with_zero_wco(self):
        mill = self._make_mill()
        mill.current_coordinates = MagicMock(
            return_value=Coordinates(10.0, 20.0, -5.0)
        )
        mill._query_work_coordinate_offset = MagicMock(
            return_value=Coordinates(0.0, 0.0, 0.0)
        )

        mpos = mill.machine_coordinates()

        self.assertEqual(mpos.x, 10.0)
        self.assertEqual(mpos.y, 20.0)
        self.assertEqual(mpos.z, -5.0)

    def test_machine_coordinates_with_nonzero_wco(self):
        mill = self._make_mill()
        mill.current_coordinates = MagicMock(
            return_value=Coordinates(10.0, 20.0, -5.0)
        )
        mill._query_work_coordinate_offset = MagicMock(
            return_value=Coordinates(-100.0, -50.0, -10.0)
        )

        mpos = mill.machine_coordinates()

        # MPos = WPos + WCO
        self.assertEqual(mpos.x, -90.0)
        self.assertEqual(mpos.y, -30.0)
        self.assertEqual(mpos.z, -15.0)

    def test_query_work_coordinate_offset_parses_gcode_params(self):
        mill = self._make_mill()
        # $# returns lines like [G54:0.000,0.000,0.000] etc.
        # WCO from a status with WCO: tag
        mill.execute_command = MagicMock(return_value="[G54:-100.000,-50.000,-10.000]")

        wco = mill._query_work_coordinate_offset()

        self.assertEqual(wco.x, -100.0)
        self.assertEqual(wco.y, -50.0)
        self.assertEqual(wco.z, -10.0)


class TestWPosPatternOnly(unittest.TestCase):
    """Only wpos_pattern should be used; mpos_pattern should be removed."""

    def test_wpos_pattern_matches_valid_status(self):
        status = "<Idle|WPos:10.500,20.123,-5.000|FS:0,0>"
        match = wpos_pattern.search(status)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "10.500")
        self.assertEqual(match.group(2), "20.123")
        self.assertEqual(match.group(3), "-5.000")

    def test_wpos_pattern_does_not_match_mpos(self):
        status = "<Idle|MPos:-400.123,-299.999,-10.000|FS:0,0>"
        match = wpos_pattern.search(status)
        self.assertIsNone(match)

    def test_mpos_pattern_no_longer_exported(self):
        """mpos_pattern should be removed from driver module."""
        from gantry.gantry_driver import driver

        self.assertFalse(hasattr(driver, "mpos_pattern"))


if __name__ == "__main__":
    unittest.main()
