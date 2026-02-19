from typing import Optional, Dict, Any, Tuple
import logging
from .gantry_driver.driver import Mill
from .gantry_driver.exceptions import (
    CommandExecutionError,
    LocationNotFound,
    MillConnectionError,
    StatusReturnError,
)

logger = logging.getLogger(__name__)

class Gantry:
    """
    Hardware interface for the CNC Gantry / Motion Controller.
    
    This class wraps the low-level Mill driver to provide a high-level
    interface for moving the gantry. It is NOT an Instrument and does
    not inherit from BaseInstrument.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # partial initialization of Mill without port 
        # (port is late-bound in connect())
        self._mill = Mill() 
    
    def connect(self) -> None:
        """
        Connect to the CNC mill.
        Priority:
        1. config['cnc']['serial_port']
        2. config['serial_port']
        3. Auto-scan (if port is None)
        """
        try:
            # User requested to prioritize auto-scan.
            port = None  # Force auto-scan

            self.logger.info(f"Connecting to gantry with port: {port} (None=Auto-scan)")
            self._mill.connect_to_mill(port=port)
            
        except MillConnectionError as e:
            self.logger.error(f"Error connecting to gantry: {e}")
            raise

    def disconnect(self) -> None:
        try:
            self._mill.disconnect()
        except MillConnectionError as e:
            self.logger.error(f"Error disconnecting gantry: {e}")
            # We don't necessarily raise here as disconnect is often cleanup

    def is_healthy(self) -> bool:
        """Check if the gantry is connected and healthy."""
        if not self._mill.active_connection:
            return False
            
        try:
            # Checking internal state first
            if not self._mill.ser_mill or not self._mill.ser_mill.is_open:
                return False

            status = self._mill.current_status()
            # Simple check for error/alarm/unknown in status string
            if "Alarm" in status or "Error" in status:
                return False
                
            return True
        except (MillConnectionError, StatusReturnError):
            return False

    def home(self) -> None:
        """Home the gantry."""
        try:
            strategy = self.config.get("cnc", {}).get("homing_strategy")
            # Default to None or check if strategy is specifically set
            # The mill driver now handles standard homing efficiently
            if strategy == "xy_hard_limits":
                self.logger.info("Using custom XY hard limit homing strategy")
                self._mill.home_xy_hard_limits()
            else:
                self._mill.home()
        except (MillConnectionError, StatusReturnError) as e:
            self.logger.error(f"Error homing gantry: {e}")
            raise

    def move_to(self, x: float, y: float, z: float) -> None:
        """
        Move to absolute coordinates (x, y, z).
        Delegates to Mill.safe_move() (which now checks for safe Z logic if enabled/refactored, 
        but currently in driver.py acts as a direct move wrapper with improved readability).
        """
        try:
            self._mill.safe_move(x_coord=x, y_coord=y, z_coord=z)
        except (MillConnectionError, StatusReturnError, CommandExecutionError, ValueError) as e:
            self.logger.error(f"Error moving gantry to ({x}, {y}, {z}): {e}")
            raise

    def get_status(self) -> str:
        """Return the current status string of the mill."""
        try:
            return self._mill.current_status()
        except (MillConnectionError, StatusReturnError) as e:
            self.logger.error(f"Error getting status: {e}")
            return "Error"

    def stop(self) -> None:
        """Immediately stop all gantry motion (GRBL feed hold)."""
        try:
            self._mill.stop()
        except (MillConnectionError, CommandExecutionError) as e:
            self.logger.error(f"Error stopping gantry: {e}")

    def get_coordinates(self) -> Dict[str, float]:
        """Return current coordinates as a dict."""
        try:
            coords = self._mill.current_coordinates()
            return {"x": coords.x, "y": coords.y, "z": coords.z}
        except (MillConnectionError, StatusReturnError, LocationNotFound) as e:
            self.logger.error(f"Error getting coordinates: {e}")
            return {"x": 0.0, "y": 0.0, "z": 0.0}
