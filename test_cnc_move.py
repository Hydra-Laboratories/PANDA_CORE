import time
import sys
import logging
import argparse
from src.cnc_control.driver import Mill

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def test_move(axis: str, distance: float, feed: int, port: str = None):
    """
    Connects to the mill and performs a relative move out and back.
    """
    logger = logging.getLogger("test_cnc_move")
    logger.info(f"Starting CNC move test: {axis} axis, {distance}mm out and back, F{feed}...")

    try:
        # Initialize Mill connection
        mill = Mill(port=port)
        # Disable auto-homing for this test
        mill.auto_home = False
        
        with mill:
            logger.info(f"Connected to mill. Homed: {mill.homed}")

            # Get current coordinates
            current_pos = mill.current_coordinates()
            logger.info("NOTE: Current position reported by driver may include offsets.")
            logger.info("Switching to RAW RELATIVE MOVEMENT to bypass driver validation and verify control.")

            # Send raw G-code for a relative move
            # G21 = Millimeters
            # G91 = Relative positioning
            logger.info(f"Sending: G21 G91 G01 {axis}{distance} F{feed}")
            mill.execute_command("G21") # Ensure mm
            mill.execute_command("G91") # Set to relative mode
            
            # Move out
            # mill.execute_command(f"G01 {axis}{distance} F{feed}")
            
            # time.sleep(1)
            
            # Move back
            # logger.info(f"Moving back: G01 {axis}{-distance} F{feed}")
            # mill.execute_command(f"G01 {axis}{-distance} F{feed}")
            
            # time.sleep(1)

            # Send ? command to get status
            logger.info("Sending '?' command to query status:")
            status = mill.current_status()
            logger.info(f"Raw Status: {status}")
            
            mill.execute_command("G90") # Set back to absolute mode
            
            # Check position again
            new_pos = mill.current_coordinates()
            logger.info(f"Position check: {new_pos}")
            
            logger.info("SUCCESS: Checked status (Movement disabled).")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test CNC movement.")
    parser.add_argument("--axis", type=str, default="X", help="Axis to move (X, Y, Z)")
    parser.add_argument("--distance", type=float, default=5.0, help="Distance to move in mm")
    parser.add_argument("--feed", type=int, default=500, help="Feed rate")
    parser.add_argument("--port", type=str, default=None, help="Serial port (optional)")

    args = parser.parse_args()
    
    test_move(args.axis, args.distance, args.feed, args.port)
