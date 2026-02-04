import sys
import unittest
from unittest.mock import MagicMock, patch
import time

# Mock cv2 and ultralytics modules
# This allows the tests to run even if the actual libraries aren't installed
# or to isolate from the actual hardware/library behavior.
mock_cv2 = MagicMock()
mock_ultralytics = MagicMock()
sys.modules["cv2"] = mock_cv2
sys.modules["ultralytics"] = mock_ultralytics

# We will import the functions to test from main.
# Since main.py might not exist or be importable yet during the very first run,
# we wrap this in a try-except or just let it fail typically, but for TDD we expect failure.
# However, to write the test file successfully, we just presume it will be available.

class TestYOLOApp(unittest.TestCase):

    def setUp(self):
        # We attempt to import here so we can reload or handle import issues if needed
        # But standard python import at top is fine if we assume file structure exists
        pass

    def test_load_model(self):
        """Test that the YOLO model is loaded correctly."""
        # Append parent dir to path to find main.py
        import os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
        # Reload main to ensure we get fresh state if needed, 
        # but here we rely on the global mock we set up at the top.
        try:
            from main import load_model
        except ImportError:
            self.fail("Could not import 'load_model' from 'main'. file may not exist yet.")

        # Call the function
        model = load_model("yolo11n.pt")

        # Assertions
        # access the global mock_ultralytics.YOLO
        mock_ultralytics.YOLO.assert_called_with("yolo11n.pt")
        self.assertIsNotNone(model)

    def test_process_frame(self):
        """Test the frame processing logic (inference and plotting)."""
        import os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
        try:
            from main import process_frame
        except ImportError:
            self.fail("Could not import 'process_frame' from 'main'.")

        # Simulate a frame (just an object)
        fake_frame = MagicMock()
        
        # Mock the model behavior
        mock_model = MagicMock()
        mock_result = MagicMock()
        # The model returns a list of Results objects
        mock_model.return_value = [mock_result]
        
        # The result object has a plot() method that returns the annotated frame
        annotated_frame_mock = MagicMock()
        mock_result.plot.return_value = annotated_frame_mock
        
        # Execute
        result_frame = process_frame(mock_model, fake_frame)
        
        # Verify
        mock_model.assert_called_with(fake_frame)
        mock_result.plot.assert_called_once()
        self.assertEqual(result_frame, annotated_frame_mock)

    def test_calculate_fps(self):
        """Test FPS calculation based on time difference."""
        import os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
        try:
            from main import calculate_fps
        except ImportError:
            self.fail("Could not import 'calculate_fps' from 'main'.")

        # Case 1: 100ms difference -> 10 FPS
        start_time = 100.0
        end_time = 100.1
        fps = calculate_fps(start_time, end_time)
        self.assertAlmostEqual(fps, 10.0, places=1)

        # Case 2: Zero difference (edge case check, should handle gracefully or return 0/inf)
        # For this simple script, we might expect it to handle division by zero or large number
        # Let's just test normal behavior for now.
        start_time = 100.0
        end_time = 100.033 # ~30 FPS
        fps = calculate_fps(start_time, end_time)
        self.assertAlmostEqual(fps, 30.3, places=1)

if __name__ == '__main__':
    unittest.main()
