import unittest
from unittest.mock import patch

from gantry.gantry import Gantry
from gantry.gantry_driver.exceptions import (
    CommandExecutionError,
    LocationNotFound,
    MillConnectionError,
    StatusReturnError,
)


class TestGantry(unittest.TestCase):
    def setUp(self):
        self.config = {"cnc": {"serial_port": "/dev/tty.usbserial"}}

    @patch("gantry.gantry.Mill")
    def test_connect_uses_config_port(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.connect()
        mock_mill.connect_to_mill.assert_called_with(port=None)

    @patch("gantry.gantry.Mill")
    def test_move_delegates_to_move_to_position(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.move_to(10, 20, 30)
        mock_mill.move_to_position.assert_called_with(
            x_coordinate=10.0,
            y_coordinate=20.0,
            z_coordinate=-30.0,
            travel_z=None,
        )

    @patch("gantry.gantry.Mill")
    def test_move_with_travel_z_passes_through_translated(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.move_to(10, 20, 30, travel_z=50)
        mock_mill.move_to_position.assert_called_with(
            x_coordinate=10.0,
            y_coordinate=20.0,
            z_coordinate=-30.0,
            travel_z=-50.0,
        )

    @patch("gantry.gantry.Mill")
    def test_is_healthy(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.return_value = "<Idle|MPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        self.assertTrue(gantry.is_healthy())

        mock_mill.current_status.return_value = "<Alarm|MPos:0,0,0|FS:0,0>"
        self.assertFalse(gantry.is_healthy())

    @patch("gantry.gantry.Mill")
    def test_connect_raises_mill_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.connect_to_mill.side_effect = MillConnectionError("no port")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.connect()

    @patch("gantry.gantry.Mill")
    def test_connect_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.connect_to_mill.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.connect()

    @patch("gantry.gantry.Mill")
    def test_disconnect_swallows_mill_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.disconnect.side_effect = MillConnectionError("port busy")
        gantry = Gantry(config=self.config)
        gantry.disconnect()

    @patch("gantry.gantry.Mill")
    def test_disconnect_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.disconnect.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.disconnect()

    @patch("gantry.gantry.Mill")
    def test_is_healthy_returns_false_on_status_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.side_effect = StatusReturnError("bad status")
        gantry = Gantry(config=self.config)
        self.assertFalse(gantry.is_healthy())

    @patch("gantry.gantry.Mill")
    def test_is_healthy_returns_false_on_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.side_effect = MillConnectionError("lost")
        gantry = Gantry(config=self.config)
        self.assertFalse(gantry.is_healthy())

    @patch("gantry.gantry.Mill")
    def test_is_healthy_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.is_healthy()

    @patch("gantry.gantry.Mill")
    def test_home_raises_on_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home_xy_hard_limits.side_effect = MillConnectionError("homing failed")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.home()

    @patch("gantry.gantry.Mill")
    def test_home_raises_on_status_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home_xy_hard_limits.side_effect = StatusReturnError("alarm")
        gantry = Gantry(config=self.config)
        with self.assertRaises(StatusReturnError):
            gantry.home()

    @patch("gantry.gantry.Mill")
    def test_home_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home_xy_hard_limits.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.home()

    @patch("gantry.gantry.Mill")
    def test_home_raises_on_unknown_strategy(self, mock_mill_cls):
        gantry = Gantry(config={"cnc": {"homing_strategy": "nonexistent"}})
        with self.assertRaises(ValueError):
            gantry.home()

    @patch("gantry.gantry.Mill")
    def test_move_to_raises_on_command_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.move_to_position.side_effect = CommandExecutionError("move failed")
        gantry = Gantry(config=self.config)
        with self.assertRaises(CommandExecutionError):
            gantry.move_to(10, 20, 30)

    @patch("gantry.gantry.Mill")
    def test_move_to_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.move_to_position.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.move_to(10, 20, 30)

    @patch("gantry.gantry.Mill")
    def test_get_status_returns_error_on_status_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_status.side_effect = StatusReturnError("bad")
        gantry = Gantry(config=self.config)
        self.assertEqual(gantry.get_status(), "StatusQueryFailed")

    @patch("gantry.gantry.Mill")
    def test_get_status_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_status.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.get_status()

    @patch("gantry.gantry.Mill")
    def test_stop_raises_on_known_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.stop.side_effect = CommandExecutionError("stop failed")
        gantry = Gantry(config=self.config)
        with self.assertRaises(CommandExecutionError):
            gantry.stop()

    @patch("gantry.gantry.Mill")
    def test_stop_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.stop.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.stop()

    @patch("gantry.gantry.Mill")
    def test_get_coordinates_raises_on_known_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_coordinates.side_effect = LocationNotFound()
        gantry = Gantry(config=self.config)
        with self.assertRaises(LocationNotFound):
            gantry.get_coordinates()

    @patch("gantry.gantry.Mill")
    def test_get_coordinates_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_coordinates.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.get_coordinates()

    @patch("gantry.gantry.Mill")
    def test_jog_cancel_raises_on_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.jog_cancel.side_effect = MillConnectionError("not connected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.jog_cancel()

    @patch("gantry.gantry.Mill")
    def test_get_position_info_raises_on_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_coordinates.side_effect = StatusReturnError("fail")
        gantry = Gantry(config=self.config)
        with self.assertRaises(StatusReturnError):
            gantry.get_position_info()

    @patch("gantry.gantry.Mill")
    def test_extract_status_returns_idle_from_grbl_string(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.last_status = "<Idle|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        self.assertEqual(gantry._extract_status(), "Idle")

    @patch("gantry.gantry.Mill")
    def test_extract_status_returns_unknown_when_empty(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.last_status = ""
        gantry = Gantry(config=self.config)
        self.assertEqual(gantry._extract_status(), "Unknown")

    @patch("gantry.gantry.Mill")
    def test_zero_coordinates_sends_g92(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.zero_coordinates()
        mock_mill.execute_command.assert_called_with("G92 X0 Y0 Z0")

    @patch("gantry.gantry.Mill")
    def test_set_serial_timeout_updates_serial_object(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.set_serial_timeout(0.5)
        self.assertEqual(mock_mill.ser_mill.timeout, 0.5)


class TestGrblSettingsValidation(unittest.TestCase):
    @patch("gantry.gantry.Mill")
    def test_validate_passes_when_settings_match(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.grbl_settings.return_value = {
            "$3": "2",
            "$10": "1",
            "$130": "300.000",
            "$131": "200.000",
        }
        gantry = Gantry(
            config={
                "grbl_settings": {
                    "dir_invert_mask": 2,
                    "status_report": 1,
                    "max_travel_x": 300.0,
                    "max_travel_y": 200.0,
                },
            }
        )
        gantry._validate_grbl_settings()

    @patch("gantry.gantry.Mill")
    def test_validate_raises_on_critical_mismatch(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.grbl_settings.return_value = {"$3": "0", "$130": "300.000"}
        gantry = Gantry(config={"grbl_settings": {"dir_invert_mask": 2}})
        with self.assertRaises(MillConnectionError):
            gantry._validate_grbl_settings()

    @patch("gantry.gantry.Mill")
    def test_validate_skipped_when_no_grbl_settings(self, mock_mill_cls):
        gantry = Gantry(config={})
        gantry._validate_grbl_settings()


if __name__ == "__main__":
    unittest.main()
