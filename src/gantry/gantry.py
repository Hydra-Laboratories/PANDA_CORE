from typing import Optional, Dict, Any
import logging
import re
import time

from .gantry_driver.driver import Mill
from .gantry_driver.exceptions import (
    CommandExecutionError,
    LocationNotFound,
    MillConnectionError,
    StatusReturnError,
)

_STATUS_RE = re.compile(r"<(\w+)\|")
_MPOS_RE = re.compile(r"MPos:([\d.-]+),([\d.-]+),([\d.-]+)")
_WPOS_RE = re.compile(r"WPos:([\d.-]+),([\d.-]+),([\d.-]+)")
_WCO_RE = re.compile(r"WCO:([\d.-]+),([\d.-]+),([\d.-]+)")

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
        self._mill = Mill()

    def connect(self) -> None:
        """Connect to the CNC mill and validate GRBL settings.

        After establishing the serial connection:
        1. Validates GRBL settings against expected values from gantry YAML
        2. Switches GRBL to report WPos directly ($10=0)

        WPos calibration happens during homing, not connect.
        G54 offset persists in GRBL EEPROM across power cycles.
        """
        try:
            self.logger.info("Connecting to gantry (auto-scan)")
            self._mill.connect_to_mill(port=None)
            self._validate_grbl_settings()
            self._switch_to_wpos_reporting()
            self._check_alarm_state()
        except MillConnectionError as e:
            self.logger.error(f"Error connecting to gantry: {e}")
            raise

    def disconnect(self) -> None:
        try:
            self._mill.disconnect()
        except MillConnectionError as e:
            self.logger.error(f"Error disconnecting gantry: {e}")

    def is_healthy(self) -> bool:
        """Check if the gantry is connected and healthy."""
        if not self._mill.active_connection:
            return False
        try:
            if not self._mill.is_connected():
                return False
            status = self._mill.current_status()
            if "Alarm" in status or "Error" in status:
                return False
            return True
        except (MillConnectionError, StatusReturnError):
            return False

    def home(self) -> None:
        """Home the gantry using the strategy from config."""
        self._last_status = "Home"
        try:
            strategy = self.config.get("cnc", {}).get("homing_strategy")
            if strategy == "xy_hard_limits":
                self.logger.info("Using custom XY hard limit homing strategy")
                self._mill.home_xy_hard_limits()
            else:
                self._mill.home()
            self._set_home_wpos()
        except (MillConnectionError, StatusReturnError) as e:
            self.logger.error(f"Error homing gantry: {e}")
            raise

    def home_xy(self) -> None:
        """Home X and Y axes using the hard-limits strategy."""
        self._last_status = "Home"
        try:
            self._mill.home_xy_hard_limits()
            self._set_home_wpos()
        except (MillConnectionError, StatusReturnError) as e:
            self.logger.error(f"Error homing XY: {e}")
            raise

    def _validate_grbl_settings(self) -> None:
        """Compare expected GRBL settings from YAML against live controller values.

        Logs warnings for any mismatches. Raises on critical mismatches
        (direction inversion, max travel) that would cause wrong motion.
        """
        expected = self.config.get("grbl_settings")
        if not expected:
            return

        from .yaml_schema import GRBL_FIELD_TO_SETTING

        live = self._mill.grbl_settings()
        mismatches = []

        for field_name, grbl_code in GRBL_FIELD_TO_SETTING.items():
            yaml_value = expected.get(field_name)
            if yaml_value is None:
                continue

            live_raw = live.get(grbl_code)
            if live_raw is None:
                self.logger.warning(
                    "GRBL setting %s (%s) not found on controller",
                    grbl_code,
                    field_name,
                )
                continue

            live_value = float(live_raw)
            expected_float = float(yaml_value)

            if abs(live_value - expected_float) > 0.001:
                mismatches.append((field_name, grbl_code, expected_float, live_value))

        if not mismatches:
            self.logger.info("GRBL settings validation passed")
            return

        for field_name, grbl_code, expected_val, live_val in mismatches:
            self.logger.error(
                "GRBL mismatch: %s (%s) — YAML expects %.3f, controller has %.3f",
                field_name,
                grbl_code,
                expected_val,
                live_val,
            )

        critical_fields = {
            "dir_invert_mask",
            "homing_dir_mask",
            "max_travel_x",
            "max_travel_y",
            "max_travel_z",
            "steps_per_mm_x",
            "steps_per_mm_y",
            "steps_per_mm_z",
        }
        critical = [m for m in mismatches if m[0] in critical_fields]
        if critical:
            details = "; ".join(
                f"{f} ({c}): expected {e}, got {l}" for f, c, e, l in critical
            )
            raise MillConnectionError(
                f"Critical GRBL settings mismatch — motion would be wrong. {details}"
            )

    def _switch_to_wpos_reporting(self) -> None:
        """Switch GRBL to report WPos directly ($10=0).

        With $10=0, every status report contains WPos — no WCO caching needed.
        Called on connect. G54 offset is set during homing and persists in EEPROM.
        Retries up to 3 times with increasing delay to handle post-connect settling.
        """
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            time.sleep(0.5 * attempt)
            try:
                self._mill.set_grbl_setting("10", "0")
                self.logger.info("Switched GRBL to WPos reporting ($10=0)")
                break
            except (CommandExecutionError, MillConnectionError) as e:
                if attempt == max_attempts:
                    self.logger.error(
                        "Failed to set $10=0 after %d attempts: %s", max_attempts, e
                    )
                    raise
                self.logger.warning(
                    "$10=0 attempt %d failed, retrying: %s", attempt, e
                )

        time.sleep(0.2)
        raw = self._mill.query_raw_status()
        if raw and "MPos" in raw and "WPos" not in raw:
            self.logger.warning(
                "$10=0 did not take effect — status still reports MPos: %s", raw
            )
        elif raw and "WPos" in raw:
            self.logger.info("Verified: GRBL is reporting WPos")

    def _check_alarm_state(self) -> None:
        """Check if GRBL is in Alarm state after connect.

        Logs a warning but does not raise — user may need to home to clear.
        """
        raw = self._mill.query_raw_status()
        if raw and "Alarm" in raw:
            self.logger.warning(
                "GRBL is in Alarm state after connect. Home the gantry to clear. Status: %s",
                raw,
            )

    def _set_home_wpos(self) -> None:
        """Set WPos to (x_max, y_max) at the current (home) position.

        Called after homing — we know we're at the XY limit-switch corner,
        so WPos should be at the maximum of the working volume.
        As the gantry moves into the workspace, WPos decreases toward 0.
        Z is not set here — no Z limit switch, so Z must be zeroed manually.
        """
        wv = self.config.get("working_volume", {})
        x_max = float(wv.get("x_max", 0))
        y_max = float(wv.get("y_max", 0))
        if x_max <= 0 or y_max <= 0:
            self.logger.warning(
                "working_volume not set — cannot calibrate WPos. "
                "Provide working_volume in gantry config."
            )
            return

        self.logger.info(
            "Setting home WPos to (%.1f, %.1f) from working_volume",
            x_max, y_max,
        )
        self._mill.execute_command(f"G10 L20 P1 X{x_max} Y{y_max}")

    def move_to(self, x: float, y: float, z: float) -> None:
        """Move to absolute coordinates (x, y, z)."""
        try:
            self._mill.safe_move(x_coord=x, y_coord=y, z_coord=z)
        except (
            MillConnectionError,
            StatusReturnError,
            CommandExecutionError,
            ValueError,
        ) as e:
            self.logger.error(f"Error moving gantry to ({x}, {y}, {z}): {e}")
            raise

    def get_status(self) -> str:
        """Return the current status string of the mill."""
        try:
            status = self._mill.current_status()
            self._last_status = status
            return status
        except (MillConnectionError, StatusReturnError) as e:
            self.logger.error(f"Error getting status: {e}")
            return "Error"

    def _extract_status(self) -> str:
        """Return the last known status without querying the serial port."""
        return getattr(self, "_last_status", "Unknown")

    def jog(
        self, x: float = 0, y: float = 0, z: float = 0, feed: float = 1000
    ) -> None:
        """Jog the gantry by a relative offset using GRBL's $J= command."""
        parts = []
        if x != 0:
            parts.append(f"X{x}")
        if y != 0:
            parts.append(f"Y{y}")
        if z != 0:
            parts.append(f"Z{z}")
        if not parts:
            return
        cmd = f"$J=G91 {''.join(parts)} F{feed}"
        try:
            self._mill.execute_command(cmd)
        except (MillConnectionError, CommandExecutionError) as e:
            self.logger.error(f"Jog error: {e}")
            raise

    def unlock(self) -> None:
        """Send GRBL $X to clear alarm state."""
        try:
            self._mill.reset()
            time.sleep(0.3)
            raw = self._mill.query_raw_status()
            if raw and "Alarm" in raw:
                self.logger.warning("Alarm still active after $X: %s", raw)
            else:
                self.logger.info("Alarm cleared")
        except (MillConnectionError, CommandExecutionError, StatusReturnError):
            # reset() may raise due to alarm text in response — check status directly
            time.sleep(0.3)
            raw = self._mill.query_raw_status()
            if raw and "Alarm" not in raw:
                self.logger.info("Alarm cleared (reset raised but status is clean)")
            else:
                self.logger.warning("Alarm may still be active: %s", raw)

    def stop(self) -> None:
        """Immediately stop all gantry motion (GRBL feed hold)."""
        try:
            self._mill.stop()
        except (MillConnectionError, CommandExecutionError) as e:
            self.logger.error(f"Error stopping gantry: {e}")

    def get_coordinates(self) -> Dict[str, float]:
        """Return current coordinates as a dict.

        Raises on communication failure so callers can distinguish
        a real (0, 0, 0) position from a failed read.
        """
        try:
            coords = self._mill.current_coordinates()
            return {"x": coords.x, "y": coords.y, "z": coords.z}
        except (MillConnectionError, StatusReturnError, LocationNotFound) as e:
            self.logger.error(f"Error getting coordinates: {e}")
            raise

    def get_position_info(self) -> Dict[str, Any]:
        """Return status, machine coords, and work coords from GRBL status.

        Returns a dict with keys:
            status:   GRBL state string (e.g. "Idle", "Run")
            coords:   {"x", "y", "z"} — machine position (MPos)
            work_pos: {"x", "y", "z"} — work position (WPos), or None
        """
        try:
            raw = self._mill.query_raw_status()
        except Exception as e:
            self.logger.error("Error querying position: %s", e)
            return {
                "status": "Error",
                "coords": {"x": 0, "y": 0, "z": 0},
                "work_pos": None,
            }

        status_match = _STATUS_RE.search(raw)
        self._last_status = status_match.group(1) if status_match else "Unknown"

        mpos_match = _MPOS_RE.search(raw)
        wpos_match = _WPOS_RE.search(raw)
        wco_match = _WCO_RE.search(raw)

        if wco_match:
            self._last_wco = {
                "x": float(wco_match.group(1)),
                "y": float(wco_match.group(2)),
                "z": float(wco_match.group(3)),
            }

        wco = getattr(self, "_last_wco", None)
        coords: Dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0}
        work_pos: Optional[Dict[str, float]] = None

        if mpos_match:
            coords = {
                "x": float(mpos_match.group(1)),
                "y": float(mpos_match.group(2)),
                "z": float(mpos_match.group(3)),
            }
            if wco:
                work_pos = {
                    "x": coords["x"] - wco["x"],
                    "y": coords["y"] - wco["y"],
                    "z": coords["z"] - wco["z"],
                }
        elif wpos_match:
            work_pos = {
                "x": float(wpos_match.group(1)),
                "y": float(wpos_match.group(2)),
                "z": float(wpos_match.group(3)),
            }
            if wco:
                coords = {
                    "x": work_pos["x"] + wco["x"],
                    "y": work_pos["y"] + wco["y"],
                    "z": work_pos["z"] + wco["z"],
                }
            else:
                coords = dict(work_pos)

        return {"status": self._last_status, "coords": coords, "work_pos": work_pos}
