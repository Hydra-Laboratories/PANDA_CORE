from typing import Optional, Dict, Any
from src.core.base_instrument import BaseInstrument, InstrumentError
from src.instrument_drivers.cnc_driver.driver import Mill

class CNC(BaseInstrument):
    """
    Driver for the CNC Mill, wrapping the legacy Mill class.
    Implements the BaseInstrument interface.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
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
            # We will ignore the config port by default and pass None to trigger detection.
            # Original logic:
            # port = self.config.get("cnc", {}).get("serial_port")
            # if not port:
            #     port = self.config.get("serial_port")
            
            port = None  # Force auto-scan
            
            self.logger.info(f"Connecting to mill with port: {port} (None=Auto-scan)")
            self._mill.connect_to_mill(port=port)
            
        except Exception as e:
            self.handle_error(e, "connect")

    def disconnect(self) -> None:
        try:
            self._mill.disconnect()
        except Exception as e:
            self.handle_error(e, "disconnect")

    def health_check(self) -> bool:
        if not self._mill.active_connection:
            return False
            
        try:
            # Checking internal state first
            if not self._mill.ser_mill or not self._mill.ser_mill.is_open:
                return False

            status = self._mill.current_status()
            # Simple check for error/alarm/unknown in status string
            # Mill.current_status returns string like "<Idle|MPos:0.000,0.000,0.000|FS:0,0>"
            if "Alarm" in status or "Error" in status:
                return False
                
            return True
        except Exception:
            return False

    def home(self) -> None:
        try:
            self._mill.home()
        except Exception as e:
            self.handle_error(e, "home")

    def move_to(self, x: float, y: float, z: float) -> None:
        """
        Move to absolute coordinates (x, y, z).
        Delegates to Mill.safe_move().
        """
        try:
            self._mill.safe_move(x_coord=x, y_coord=y, z_coord=z)
        except Exception as e:
            self.handle_error(e, "move_to")

    def get_status(self) -> str:
        """Return the current status string of the mill."""
        try:
            return self._mill.current_status()
        except Exception as e:
            self.handle_error(e, "get_status")
            return "Error"

    def get_coordinates(self) -> Dict[str, float]:
        """Return current coordinates as a dict."""
        try:
            coords = self._mill.current_coordinates()
            return {"x": coords.x, "y": coords.y, "z": coords.z}
        except Exception as e:
            self.handle_error(e, "get_coordinates")
            return {"x": 0.0, "y": 0.0, "z": 0.0}
