import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.instrument_drivers.cnc_driver.driver import Mill, wpos_pattern, mpos_pattern, Coordinates

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

    @patch('src.instrument_drivers.cnc_driver.driver.serial.Serial')
    @patch('src.instrument_drivers.cnc_driver.driver.set_up_mill_logger')
    @patch('src.instrument_drivers.cnc_driver.driver.set_up_command_logger')
    def test_generate_movement_commands(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test generation of G-code commands."""
        # Setup mock mill with basic config
        mill = Mill()
        mill.max_z_height = 0.0
        mill.safe_z_height = -5.0
        
        # Test 1: Simple XY move (current Z is safe)
        current = Coordinates(0, 0, 0) # At safe height (0 >= -5)
        target = Coordinates(10, 10, 0)
        
        commands = mill._generate_movement_commands(current, target)
        # Should be diagonal move
        self.assertIn("G01 X10 Y10", commands)
        self.assertIn("G01 Z0", commands)
        
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
        
        self.assertIn("G01 X10", commands_unsafe)
        self.assertIn("G01 Y10", commands_unsafe)
        self.assertNotIn("G01 X10 Y10", commands_unsafe)

    @patch('src.instrument_drivers.cnc_driver.driver.serial.Serial')
    @patch('src.instrument_drivers.cnc_driver.driver.set_up_mill_logger')
    @patch('src.instrument_drivers.cnc_driver.driver.set_up_command_logger')
    def test_mock_connection(self, mock_cmd_logger, mock_mill_logger, mock_serial):
        """Test connecting with mocked serial port."""
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial.return_value = mock_serial_instance
        
        # Mock the locate_mill_over_serial to return our mock
        with patch.object(Mill, 'locate_mill_over_serial', return_value=(mock_serial_instance, '/dev/test')):
            mill = Mill()
            mill.connect_to_mill(port='/dev/test')
            
            self.assertTrue(mill.active_connection)
            self.assertEqual(mill.ser_mill, mock_serial_instance)

if __name__ == '__main__':
    unittest.main()
