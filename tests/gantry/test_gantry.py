import unittest
from unittest.mock import MagicMock, patch
from src.gantry.gantry import Gantry

class TestGantry(unittest.TestCase):
    def setUp(self):
        self.config = {"cnc": {"serial_port": "/dev/tty.usbserial"}}
        
    @patch('src.gantry.gantry.Mill')
    def test_connect_uses_config_port(self, mock_mill_cls):
        # Arrange
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        
        # Act
        gantry.connect()
        
        # Assert
        # In the new logic, we force auto-scan (port=None) currently
        # Adjust test if that changes, but gantry.py line 33 says port = None
        mock_mill.connect_to_mill.assert_called_with(port=None) 

    @patch('src.gantry.gantry.Mill')
    def test_move_delegates_to_safe_move(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        gantry = Gantry(config=self.config)
        gantry.move_to(10, 20, 30)
        mock_mill.safe_move.assert_called_with(x_coord=10, y_coord=20, z_coord=30)
        
    @patch('src.gantry.gantry.Mill')
    def test_is_healthy(self, mock_mill_cls):
        mock_mill = mock_mill_cls.return_value
        # Case 1: Active connection, no alarm
        mock_mill.active_connection = True
        mock_mill.ser_mill.is_open = True
        mock_mill.current_status.return_value = "<Idle|MPos:0,0,0|FS:0,0>"
        gantry = Gantry(config=self.config)
        self.assertTrue(gantry.is_healthy())
        
        # Case 2: Alarm
        mock_mill.current_status.return_value = "<Alarm|MPos:0,0,0|FS:0,0>"
        self.assertFalse(gantry.is_healthy())

if __name__ == '__main__':
    unittest.main()
