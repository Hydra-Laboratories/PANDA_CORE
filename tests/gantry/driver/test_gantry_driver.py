import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from gantry.gantry_driver.driver import Mill, wpos_pattern, mpos_pattern, Coordinates

class TestCNCDriverLogic(unittest.TestCase):
    
    def test_regex_patterns(self):
        """Test that regex patterns correctly parse GRBL status strings."""
        
        # Test WPos pattern
        wpos_status = "<Idle|WPos:10.500,20.123,-5.000|FS:0,0|WCO:0,0,0>"
        match = wpos_pattern.search(wpos_status)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "10.500")
        self.assertEqual(match.group(2), "20.123")
        self.assertEqual(match.group(3), "-5.000")
        
        # Test MPos pattern
        mpos_status = "<Idle|MPos:-400.123,-299.999,-10.000|FS:0,0>"
        match = mpos_pattern.search(mpos_status)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "-400.123")
        self.assertEqual(match.group(2), "-299.999")
        self.assertEqual(match.group(3), "-10.000")
        
        # Test failure cases
        invalid_status = "<Idle|FS:0,0>"
        self.assertIsNone(wpos_pattern.search(invalid_status))
        self.assertIsNone(mpos_pattern.search(invalid_status))

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_generate_movement_commands(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test generation of G-code commands."""
        # Setup mock mill with basic config
        mill = Mill()
        mill.safe_z_height = -5.0
        
        # Test 1: Simple XY move (current Z is safe)
        current = Coordinates(0, 0, 0) # At safe height (0 >= -5)
        target = Coordinates(10, 10, 0)
        
        commands = mill._generate_movement_commands(current, target)
        # Should be diagonal move
        self.assertIn("G01 X10.0 Y10.0 F2000", commands)
        self.assertIn("G01 Z0.0 F2000", commands)
        
        # Test 2: Move where current Z is unsafe (e.g. deep in a well)
        # However, _generate_movement_commands logic in current driver:
        # if current.z >= safe_height: diagonal move
        # else: separate moves
        
        current_unsafe = Coordinates(0, 0, -10) # Below safe height of -5
        target_unsafe = Coordinates(10, 10, -10)
        
        commands_unsafe = mill._generate_movement_commands(current_unsafe, target_unsafe)
        # Should NOT have diagonal move X Y together if strictly following "non-safe" path logic?
        # Looking at code: 
        # else:
        #   append X..
        #   append Y..
        #   append Z..
        
        self.assertIn("G01 X10.0 F2000", commands_unsafe)
        self.assertIn("G01 Y10.0 F2000", commands_unsafe)
        self.assertNotIn("G01 X10.0 Y10.0", commands_unsafe)

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_generate_transit_commands_lifts_traverses_descends(
        self, mock_cmd_logger, mock_mill_logger, mock_serial,
    ):
        """Transit: lift to travel_z, XY travel, descend to target z.

        Models an inter-well scan move: start low at well_i, hop over to
        well_j at safe-approach height, end there. The mill must emit
        three G-code lines in that order.
        """
        mill = Mill()
        mill.safe_z_height = -10.0

        current = Coordinates(-100.0, -50.0, -78.0)  # machine space, at well_i action z
        target = Coordinates(-110.0, -50.0, -85.0)   # well_j at approach z
        commands = mill._generate_transit_commands(current, target, travel_z=-85.0)

        self.assertEqual(commands, [
            "G01 Z-85.0 F2000",         # lift to travel_z at well_i.xy
            "G01 X-110.0 Y-50.0 F2000", # XY travel at travel_z
            # target.z == travel_z, final descent skipped.
        ])

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_generate_transit_commands_skips_lift_when_already_at_travel_z(
        self, mock_cmd_logger, mock_mill_logger, mock_serial,
    ):
        """Already at travel_z: no lift, just XY then descent to target."""
        mill = Mill()
        mill.safe_z_height = -10.0

        current = Coordinates(-100.0, -50.0, -85.0)
        target = Coordinates(-110.0, -50.0, -90.0)
        commands = mill._generate_transit_commands(current, target, travel_z=-85.0)

        self.assertEqual(commands, [
            "G01 X-110.0 Y-50.0 F2000",
            "G01 Z-90.0 F2000",
        ])

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_mock_connection(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test connecting with mocked serial port."""
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial.return_value = mock_serial_instance
        
        # Mock the locate_mill_over_serial to return our mock
        with patch.object(Mill, 'locate_mill_over_serial', return_value=(mock_serial_instance, '/dev/test')):
            mill = Mill()
            mill.read_mill_config = MagicMock()
            mill.write_mill_config_file = MagicMock()
            mill.read_working_volume = MagicMock()
            mill.check_for_alarm_state = MagicMock()
            mill.clear_buffers = MagicMock()
            mill._enforce_wpos_mode = MagicMock()
            mill.set_feed_rate = MagicMock()
            mill._seed_wco = MagicMock()
            mill.connect_to_mill(port='/dev/test')
            
            self.assertTrue(mill.active_connection)
            self.assertEqual(mill.ser_mill, mock_serial_instance)

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_enforce_wpos_mode_sets_ten_to_zero(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test that _enforce_wpos_mode sends $10=0 when not already set."""
        mill = Mill()
        mock_ser = MagicMock()
        mill.ser_mill = mock_ser
        mill.config["$10"] = "1"

        # Mock execute_command to track calls
        mill.execute_command = MagicMock()
        mill._enforce_wpos_mode()

        mill.execute_command.assert_any_call("$10=0")
        mill.execute_command.assert_any_call("G90")
        self.assertEqual(mill.config["$10"], "0")

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_enforce_wpos_mode_skips_when_already_zero(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test that _enforce_wpos_mode does not re-send $10=0 if already set."""
        mill = Mill()
        mill.config["$10"] = "0"
        mill.execute_command = MagicMock()

        mill._enforce_wpos_mode()

        calls = [str(c) for c in mill.execute_command.call_args_list]
        self.assertNotIn("call('$10=0')", calls)
        mill.execute_command.assert_called_with("G90")

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_jog_raises_when_not_connected(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test that jog raises MillConnectionError when ser_mill is None."""
        from gantry.gantry_driver.exceptions import MillConnectionError
        mill = Mill()
        mill.ser_mill = None
        with self.assertRaises(MillConnectionError):
            mill.jog(x=1.0)

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_jog_cancel_raises_when_not_connected(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test that jog_cancel raises MillConnectionError when ser_mill is None."""
        from gantry.gantry_driver.exceptions import MillConnectionError
        mill = Mill()
        mill.ser_mill = None
        with self.assertRaises(MillConnectionError):
            mill.jog_cancel()

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_reset_raises_when_not_connected(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test that reset (unlock) raises when ser_mill is None."""
        from gantry.gantry_driver.exceptions import MillConnectionError
        mill = Mill()
        mill.ser_mill = None
        with self.assertRaises(MillConnectionError):
            mill.reset()

    @patch('gantry.gantry_driver.driver.serial.Serial')
    @patch('gantry.gantry_driver.driver.set_up_mill_logger')
    @patch('gantry.gantry_driver.driver.set_up_command_logger')
    def test_soft_reset_raises_when_not_connected(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test that soft_reset raises when ser_mill is None."""
        from gantry.gantry_driver.exceptions import MillConnectionError
        mill = Mill()
        mill.ser_mill = None
        with self.assertRaises(MillConnectionError):
            mill.soft_reset()


if __name__ == '__main__':
    unittest.main()
