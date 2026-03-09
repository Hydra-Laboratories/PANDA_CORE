import unittest
from unittest.mock import MagicMock, patch
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

    @patch('gantry.gantry.Mill')
    def test_connect_uses_config_port(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.connect()
        mock_mill.connect_to_mill.assert_called_with(port=None)

    @patch('gantry.gantry.Mill')
    def test_move_delegates_to_safe_move(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.move_to(10, 20, 30)
        mock_mill.safe_move.assert_called_with(x_coord=-10.0, y_coord=-20.0, z_coord=-30.0)

    @patch('gantry.gantry.Mill')
    def test_is_healthy(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.return_value = "<Idle|MPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        self.assertTrue(gantry.is_healthy())

        mock_mill.current_status.return_value = "<Alarm|MPos:0,0,0|FS:0,0>"
        self.assertFalse(gantry.is_healthy())

    # -- Exception specificity tests --

    @patch('gantry.gantry.Mill')
    def test_connect_raises_mill_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.connect_to_mill.side_effect = MillConnectionError("no port")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.connect()

    @patch('gantry.gantry.Mill')
    def test_connect_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.connect_to_mill.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.connect()

    @patch('gantry.gantry.Mill')
    def test_disconnect_swallows_mill_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.disconnect.side_effect = MillConnectionError("port busy")
        gantry = Gantry(config=self.config)
        gantry.disconnect()  # should not raise

    @patch('gantry.gantry.Mill')
    def test_disconnect_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.disconnect.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.disconnect()

    @patch('gantry.gantry.Mill')
    def test_is_healthy_returns_false_on_status_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.side_effect = StatusReturnError("bad status")
        gantry = Gantry(config=self.config)
        self.assertFalse(gantry.is_healthy())

    @patch('gantry.gantry.Mill')
    def test_is_healthy_returns_false_on_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.side_effect = MillConnectionError("lost")
        gantry = Gantry(config=self.config)
        self.assertFalse(gantry.is_healthy())

    @patch('gantry.gantry.Mill')
    def test_is_healthy_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.is_healthy()

    @patch('gantry.gantry.Mill')
    def test_home_raises_on_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home_xy_hard_limits.side_effect = MillConnectionError("homing failed")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.home()

    @patch('gantry.gantry.Mill')
    def test_home_raises_on_status_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home_xy_hard_limits.side_effect = StatusReturnError("alarm")
        gantry = Gantry(config=self.config)
        with self.assertRaises(StatusReturnError):
            gantry.home()

    @patch('gantry.gantry.Mill')
    def test_home_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home_xy_hard_limits.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.home()

    @patch('gantry.gantry.Mill')
    def test_move_to_raises_on_command_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.safe_move.side_effect = CommandExecutionError("move failed")
        gantry = Gantry(config=self.config)
        with self.assertRaises(CommandExecutionError):
            gantry.move_to(10, 20, 30)

    @patch('gantry.gantry.Mill')
    def test_move_to_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.safe_move.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.move_to(10, 20, 30)

    @patch('gantry.gantry.Mill')
    def test_get_status_returns_error_on_status_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_status.side_effect = StatusReturnError("bad")
        gantry = Gantry(config=self.config)
        self.assertEqual(gantry.get_status(), "StatusQueryFailed")

    @patch('gantry.gantry.Mill')
    def test_get_status_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_status.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.get_status()

    @patch('gantry.gantry.Mill')
    def test_stop_raises_on_known_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.stop.side_effect = CommandExecutionError("stop failed")
        gantry = Gantry(config=self.config)
        with self.assertRaises(CommandExecutionError):
            gantry.stop()

    @patch('gantry.gantry.Mill')
    def test_stop_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.stop.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.stop()

    @patch('gantry.gantry.Mill')
    def test_get_coordinates_raises_on_known_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_coordinates.side_effect = LocationNotFound()
        gantry = Gantry(config=self.config)
        with self.assertRaises(LocationNotFound):
            gantry.get_coordinates()

    @patch('gantry.gantry.Mill')
    def test_get_coordinates_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_coordinates.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.get_coordinates()


    @patch('gantry.gantry.Mill')
    def test_jog_cancel_raises_on_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.jog_cancel.side_effect = MillConnectionError("not connected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.jog_cancel()

    @patch('gantry.gantry.Mill')
    def test_home_raises_on_unknown_strategy(self, mock_mill_cls):
        config = {"cnc": {"homing_strategy": "nonexistent"}}
        gantry = Gantry(config=config)
        with self.assertRaises(ValueError):
            gantry.home()

    @patch('gantry.gantry.Mill')
    def test_get_position_info_raises_on_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_coordinates.side_effect = StatusReturnError("fail")
        gantry = Gantry(config=self.config)
        with self.assertRaises(StatusReturnError):
            gantry.get_position_info()

    @patch('gantry.gantry.Mill')
    def test_extract_status_returns_idle_from_grbl_string(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.last_status = "<Idle|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        self.assertEqual(gantry._extract_status(), "Idle")

    @patch('gantry.gantry.Mill')
    def test_extract_status_returns_unknown_when_empty(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.last_status = ""
        gantry = Gantry(config=self.config)
        self.assertEqual(gantry._extract_status(), "Unknown")


if __name__ == '__main__':
    unittest.main()
