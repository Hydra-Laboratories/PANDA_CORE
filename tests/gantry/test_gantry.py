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
        mock_mill.safe_move.assert_called_with(x_coord=10, y_coord=20, z_coord=30)

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
        mock_mill.home.side_effect = MillConnectionError("homing failed")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.home()

    @patch('gantry.gantry.Mill')
    def test_home_raises_on_status_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home.side_effect = StatusReturnError("alarm")
        gantry = Gantry(config=self.config)
        with self.assertRaises(StatusReturnError):
            gantry.home()

    @patch('gantry.gantry.Mill')
    def test_home_does_not_catch_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.home.side_effect = RuntimeError("unexpected")
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
        self.assertEqual(gantry.get_status(), "Error")

    @patch('gantry.gantry.Mill')
    def test_get_status_propagates_unexpected_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.current_status.side_effect = RuntimeError("unexpected")
        gantry = Gantry(config=self.config)
        with self.assertRaises(RuntimeError):
            gantry.get_status()

    @patch('gantry.gantry.Mill')
    def test_stop_swallows_known_errors(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.stop.side_effect = CommandExecutionError("stop failed")
        gantry = Gantry(config=self.config)
        gantry.stop()  # should not raise

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


class TestAlarmStateHandling(unittest.TestCase):
    """Tests for alarm detection, unlock, and connect-with-alarm flows."""

    def setUp(self):
        self.config = {"cnc": {"serial_port": "/dev/tty.usbserial"}}

    @patch('gantry.gantry.Mill')
    def test_check_alarm_state_does_not_raise(self, mock_mill_cls):
        """_check_alarm_state logs but never raises, even when alarm detected."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = "<Alarm|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        gantry._check_alarm_state()  # should not raise

    @patch('gantry.gantry.Mill')
    def test_check_alarm_state_queries_status(self, mock_mill_cls):
        """_check_alarm_state uses query_raw_status to detect alarm."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = "<Idle|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        gantry._check_alarm_state()
        mock_mill.query_raw_status.assert_called_once()

    @patch('gantry.gantry.Mill')
    def test_connect_completes_when_mill_alarmed(self, mock_mill_cls):
        """connect() succeeds even when mill is in alarm state."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = "<Alarm|WPos:0,0,0|FS:0,0>"
        mock_mill.grbl_settings.return_value = {}
        mock_mill.set_grbl_setting.return_value = None
        gantry = Gantry(config=self.config)
        gantry.connect()  # should not raise

    @patch('gantry.gantry.Mill')
    def test_unlock_sends_reset(self, mock_mill_cls):
        """unlock() calls _mill.reset() to send $X."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = "<Idle|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        gantry.unlock()
        mock_mill.reset.assert_called_once()

    @patch('gantry.gantry.Mill')
    def test_unlock_clears_alarm(self, mock_mill_cls):
        """unlock() checks status after reset to confirm alarm cleared."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = "<Idle|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        gantry.unlock()  # should not raise
        mock_mill.query_raw_status.assert_called()

    @patch('gantry.gantry.Mill')
    def test_unlock_handles_reset_raising(self, mock_mill_cls):
        """unlock() falls back to status check when reset() raises."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.reset.side_effect = CommandExecutionError("alarm text")
        mock_mill.query_raw_status.return_value = "<Idle|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        gantry.unlock()  # should not raise — fallback checks status

    @patch('gantry.gantry.Mill')
    def test_unlock_alarm_persists_after_reset(self, mock_mill_cls):
        """unlock() does not raise even if alarm persists after $X."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = "<Alarm|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        gantry.unlock()  # should not raise — just warns

    @patch('gantry.gantry.Mill')
    def test_is_healthy_false_on_alarm(self, mock_mill_cls):
        """is_healthy returns False when GRBL reports Alarm status."""
        mock_mill = mock_mill_cls.return_value
        mock_mill.active_connection = True
        mock_mill.is_connected.return_value = True
        mock_mill.current_status.return_value = "<Alarm|WPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        self.assertFalse(gantry.is_healthy())


class TestGetPositionInfo(unittest.TestCase):
    """Tests for Gantry.get_position_info status and coordinate parsing."""

    def setUp(self):
        self.config = {"cnc": {"serial_port": "/dev/tty.usbserial"}}

    @patch('gantry.gantry.Mill')
    def test_returns_alarm_status(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = (
            "<Alarm|WPos:265.441,127.238,0.000|FS:0,0|Pn:Z>"
        )
        gantry = Gantry(config=self.config)
        info = gantry.get_position_info()
        self.assertEqual(info["status"], "Alarm")

    @patch('gantry.gantry.Mill')
    def test_returns_idle_status(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = (
            "<Idle|WPos:100.0,50.0,-10.0|FS:0,0>"
        )
        gantry = Gantry(config=self.config)
        info = gantry.get_position_info()
        self.assertEqual(info["status"], "Idle")

    @patch('gantry.gantry.Mill')
    def test_parses_wpos(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = (
            "<Idle|WPos:150.0,80.5,-20.0|FS:0,0>"
        )
        gantry = Gantry(config=self.config)
        info = gantry.get_position_info()
        self.assertAlmostEqual(info["work_pos"]["x"], 150.0)
        self.assertAlmostEqual(info["work_pos"]["y"], 80.5)
        self.assertAlmostEqual(info["work_pos"]["z"], -20.0)

    @patch('gantry.gantry.Mill')
    def test_parses_mpos(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.return_value = (
            "<Idle|MPos:-100.0,-50.0,0.0|FS:0,0>"
        )
        gantry = Gantry(config=self.config)
        info = gantry.get_position_info()
        self.assertAlmostEqual(info["coords"]["x"], -100.0)
        self.assertAlmostEqual(info["coords"]["y"], -50.0)
        self.assertAlmostEqual(info["coords"]["z"], 0.0)

    @patch('gantry.gantry.Mill')
    def test_computes_wpos_from_mpos_and_wco(self, mock_mill_cls):
        """When MPos reported with WCO, work_pos is computed as MPos - WCO."""
        mock_mill = mock_mill_cls.return_value
        # First call seeds WCO, second returns MPos only
        mock_mill.query_raw_status.side_effect = [
            "<Idle|MPos:-100.0,-50.0,0.0|FS:0,0|WCO:-265.0,-127.0,0.0>",
        ]
        gantry = Gantry(config=self.config)
        info = gantry.get_position_info()
        # WPos = MPos - WCO = (-100 - (-265), -50 - (-127), 0 - 0)
        self.assertAlmostEqual(info["work_pos"]["x"], 165.0)
        self.assertAlmostEqual(info["work_pos"]["y"], 77.0)
        self.assertAlmostEqual(info["work_pos"]["z"], 0.0)

    @patch('gantry.gantry.Mill')
    def test_returns_error_on_exception(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.query_raw_status.side_effect = MillConnectionError("lost")
        gantry = Gantry(config=self.config)
        info = gantry.get_position_info()
        self.assertEqual(info["status"], "Error")
        self.assertEqual(info["coords"], {"x": 0, "y": 0, "z": 0})
        self.assertIsNone(info["work_pos"])


class TestSetHomeWpos(unittest.TestCase):
    """Tests for Gantry._set_home_wpos coordinate calibration."""

    @patch('gantry.gantry.Mill')
    def test_sets_g10_with_working_volume(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        config = {"working_volume": {"x_max": 300, "y_max": 200}}
        gantry = Gantry(config=config)
        gantry._set_home_wpos()
        mock_mill.execute_command.assert_called_with("G10 L20 P1 X300.0 Y200.0")

    @patch('gantry.gantry.Mill')
    def test_skips_when_no_working_volume(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config={})
        gantry._set_home_wpos()
        mock_mill.execute_command.assert_not_called()

    @patch('gantry.gantry.Mill')
    def test_skips_when_zero_values(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        config = {"working_volume": {"x_max": 0, "y_max": 0}}
        gantry = Gantry(config=config)
        gantry._set_home_wpos()
        mock_mill.execute_command.assert_not_called()


class TestJog(unittest.TestCase):
    """Tests for Gantry.jog relative movement."""

    def setUp(self):
        self.config = {"cnc": {"serial_port": "/dev/tty.usbserial"}}

    @patch('gantry.gantry.Mill')
    def test_jog_sends_grbl_command(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.jog(x=10, y=-5, feed=500)
        mock_mill.execute_command.assert_called_with("$J=G91 X10Y-5 F500")

    @patch('gantry.gantry.Mill')
    def test_jog_skips_zero_axes(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.jog(z=-2)
        mock_mill.execute_command.assert_called_with("$J=G91 Z-2 F1000")

    @patch('gantry.gantry.Mill')
    def test_jog_noop_when_all_zero(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.jog()
        mock_mill.execute_command.assert_not_called()

    @patch('gantry.gantry.Mill')
    def test_jog_raises_on_connection_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.execute_command.side_effect = MillConnectionError("lost")
        gantry = Gantry(config=self.config)
        with self.assertRaises(MillConnectionError):
            gantry.jog(x=10)

    @patch('gantry.gantry.Mill')
    def test_jog_raises_on_command_error(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.execute_command.side_effect = CommandExecutionError("fail")
        gantry = Gantry(config=self.config)
        with self.assertRaises(CommandExecutionError):
            gantry.jog(x=10)


class TestGrblSettingsValidation(unittest.TestCase):

    @patch('gantry.gantry.Mill')
    def test_validate_passes_when_settings_match(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.grbl_settings.return_value = {
            "$3": "2", "$10": "1", "$130": "300.000", "$131": "200.000",
        }
        config = {
            "grbl_settings": {
                "dir_invert_mask": 2,
                "status_report": 1,
                "max_travel_x": 300.0,
                "max_travel_y": 200.0,
            },
        }
        gantry = Gantry(config=config)
        gantry._validate_grbl_settings()  # should not raise

    @patch('gantry.gantry.Mill')
    def test_validate_raises_on_critical_mismatch(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.grbl_settings.return_value = {"$3": "0", "$130": "300.000"}
        config = {
            "grbl_settings": {
                "dir_invert_mask": 2,  # expects 2, controller has 0
            },
        }
        gantry = Gantry(config=config)
        with self.assertRaises(MillConnectionError):
            gantry._validate_grbl_settings()

    @patch('gantry.gantry.Mill')
    def test_validate_raises_on_max_travel_mismatch(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.grbl_settings.return_value = {"$130": "400.000"}
        config = {
            "grbl_settings": {"max_travel_x": 300.0},
        }
        gantry = Gantry(config=config)
        with self.assertRaises(MillConnectionError):
            gantry._validate_grbl_settings()

    @patch('gantry.gantry.Mill')
    def test_validate_skipped_when_no_grbl_settings(self, mock_mill_cls):
        gantry = Gantry(config={})
        gantry._validate_grbl_settings()  # should not raise

    @patch('gantry.gantry.Mill')
    def test_validate_warns_on_noncritical_mismatch(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.grbl_settings.return_value = {"$10": "0"}
        config = {
            "grbl_settings": {"status_report": 1},  # non-critical
        }
        gantry = Gantry(config=config)
        # Should log error but not raise
        gantry._validate_grbl_settings()

    @patch('gantry.gantry.Mill')
    def test_validate_ignores_unspecified_settings(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        mock_mill.grbl_settings.return_value = {
            "$3": "99", "$130": "999.000",  # would fail if checked
        }
        config = {
            "grbl_settings": {"homing_pull_off": 2.0},  # only check $27
        }
        gantry = Gantry(config=config)
        # $27 not in live config, so just warns
        gantry._validate_grbl_settings()


if __name__ == '__main__':
    unittest.main()
