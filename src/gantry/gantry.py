from typing import Optional, Dict, Any
import logging

from .coordinate_translator import (
    to_machine_coordinates,
    to_user_coordinates,
    translate_status_string,
)
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

    @property
    def total_z_height(self) -> Optional[float]:
        """Return configured total Z height in user space, if available."""
        if isinstance(self.config, dict):
            cnc = self.config.get("cnc", {})
            if isinstance(cnc, dict) and "total_z_height" in cnc:
                return float(cnc["total_z_height"])
            working_volume = self.config.get("working_volume", {})
            if isinstance(working_volume, dict) and "z_max" in working_volume:
                return float(working_volume["z_max"])
            return None

        if hasattr(self.config, "total_z_height"):
            return float(getattr(self.config, "total_z_height"))
        return None
    
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
        """Home the gantry using the configured homing strategy."""
        strategy = self._homing_strategy()
        try:
            if strategy == "manual_origin":
                self._mill.home_manual_origin()
            elif strategy == "standard":
                self._mill.home()
            else:
                self._mill.home_xy_hard_limits()
        except (MillConnectionError, StatusReturnError) as e:
            self.logger.error(f"Error homing gantry: {e}")
            raise

    def home_xy(self) -> None:
        """Home using XY hard limits strategy (ignores config)."""
        try:
            self._mill.home_xy_hard_limits()
        except (MillConnectionError, StatusReturnError) as e:
            self.logger.error(f"Error homing gantry: {e}")
            raise

    def _homing_strategy(self) -> str:
        """Extract homing strategy from config dict."""
        if isinstance(self.config, dict):
            cnc = self.config.get("cnc", {})
            if isinstance(cnc, dict):
                return cnc.get("homing_strategy", "xy_hard_limits")
        return "xy_hard_limits"

    def move_to(self, x: float, y: float, z: float) -> None:
        """
        Move to absolute coordinates (x, y, z).
        Delegates to Mill.safe_move() (which now checks for safe Z logic if enabled/refactored, 
        but currently in driver.py acts as a direct move wrapper with improved readability).
        """
        try:
            machine_x, machine_y, machine_z = to_machine_coordinates(x, y, z)
            self._mill.safe_move(
                x_coord=machine_x,
                y_coord=machine_y,
                z_coord=machine_z,
            )
        except (MillConnectionError, StatusReturnError, CommandExecutionError, ValueError) as e:
            self.logger.error(f"Error moving gantry to ({x}, {y}, {z}): {e}")
            raise

    def jog(self, x: float = 0, y: float = 0, z: float = 0,
            feed_rate: float = 2000) -> None:
        """Jog the gantry by a relative offset using GRBL's $J= command.

        This is non-blocking and much faster than move_to for interactive use.
        Coordinates are in user space (positive); negated for machine space.
        """
        try:
            self._mill.jog(x=-x, y=-y, z=-z, feed_rate=feed_rate)
        except (MillConnectionError, CommandExecutionError) as e:
            self.logger.error(f"Jog error: {e}")
            raise

    def jog_cancel(self) -> None:
        """Cancel any in-progress jog motion immediately."""
        try:
            self._mill.jog_cancel()
        except Exception as e:
            self.logger.error(f"Jog cancel error: {e}")

    def soft_reset(self) -> None:
        """Send a GRBL soft reset (Ctrl-X) to the controller."""
        try:
            self._mill.soft_reset()
        except Exception as e:
            self.logger.error(f"Soft reset error: {e}")
            raise

    def unlock(self) -> None:
        """Send GRBL unlock command ($X) to clear alarm state."""
        try:
            self._mill.reset()
        except (MillConnectionError, CommandExecutionError) as e:
            self.logger.error(f"Unlock error: {e}")
            raise

    def reset_and_unlock(self) -> None:
        """Soft reset + unlock in a single serial sequence."""
        try:
            self._mill.soft_reset_and_unlock()
        except (MillConnectionError, CommandExecutionError) as e:
            self.logger.error(f"Reset and unlock error: {e}")
            raise

    def get_status(self) -> str:
        """Return the current status string of the mill."""
        try:
            return translate_status_string(self._mill.current_status())
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
            x_user, y_user, z_user = to_user_coordinates(coords.x, coords.y, coords.z)
            return {"x": x_user, "y": y_user, "z": z_user}
        except (MillConnectionError, StatusReturnError, LocationNotFound) as e:
            self.logger.error(f"Error getting coordinates: {e}")
            return {"x": 0.0, "y": 0.0, "z": 0.0}

    def get_position_info(self) -> Dict[str, Any]:
        """Return coordinates, work position, and status in a single serial query."""
        try:
            coords = self._mill.current_coordinates()
            x_user, y_user, z_user = to_user_coordinates(coords.x, coords.y, coords.z)
            user_coords = {"x": x_user, "y": y_user, "z": z_user}
        except (MillConnectionError, StatusReturnError, LocationNotFound) as e:
            self.logger.error(f"Error getting position info: {e}")
            user_coords = {"x": 0.0, "y": 0.0, "z": 0.0}

        status = self._extract_status()

        return {
            "coords": user_coords,
            "work_pos": user_coords,
            "status": status,
        }

    def _extract_status(self) -> str:
        """Extract the GRBL state word from last_status (e.g. Idle, Run, Alarm:1)."""
        try:
            raw = getattr(self._mill, 'last_status', '') or ''
            if not raw:
                return "Unknown"
            # GRBL status format: <State|...>
            if raw.startswith("<") and "|" in raw:
                return raw[1:raw.index("|")]
            # Could be a bare alarm/error string
            if "alarm" in raw.lower():
                return "Alarm"
            return translate_status_string(raw)
        except Exception:
            return "Unknown"
