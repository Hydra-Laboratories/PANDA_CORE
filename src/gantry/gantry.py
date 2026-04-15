from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

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

_STATUS_RE = re.compile(r"<([^|>]+)")

logger = logging.getLogger(__name__)


class Gantry:
    """High-level gantry wrapper around the low-level Mill driver.

    User-facing coordinates are positive-space XYZ. The underlying GRBL
    controller still operates in negative machine space, so this wrapper
    handles translation at the boundary.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        offline: bool = False,
    ) -> None:
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._offline = offline
        self._offline_coords = {"x": 0.0, "y": 0.0, "z": 0.0}
        self._mill: Mill | None = None if offline else Mill()

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
        """Connect to the CNC mill via auto-scan of available serial ports."""
        if self._offline:
            return
        assert self._mill is not None
        try:
            self.logger.info("Connecting to gantry via auto-scan")
            self._mill.connect_to_mill(port=None)
            self._validate_grbl_settings()
            self._check_alarm_state()
        except MillConnectionError as exc:
            self.logger.error("Error connecting to gantry: %s", exc)
            raise

    def disconnect(self) -> None:
        if self._offline:
            return
        assert self._mill is not None
        try:
            self._mill.disconnect()
        except MillConnectionError as exc:
            self.logger.error("Error disconnecting gantry: %s", exc)

    def is_healthy(self) -> bool:
        """Check if the gantry is connected and healthy."""
        if self._offline:
            return True
        assert self._mill is not None
        if not self._mill.active_connection:
            self.logger.debug("Health check: no active connection")
            return False

        try:
            if not self._mill.ser_mill or not self._mill.ser_mill.is_open:
                self.logger.debug("Health check: serial port not open")
                return False

            status = self._mill.current_status()
            if "Alarm" in status or "Error" in status:
                self.logger.debug("Health check: unhealthy status: %s", status)
                return False

            return True
        except (MillConnectionError, StatusReturnError) as exc:
            self.logger.debug("Health check failed: %s", exc)
            return False

    def home(self) -> None:
        """Home the gantry using the configured homing strategy."""
        if self._offline:
            return
        assert self._mill is not None
        strategy = self._homing_strategy()
        try:
            if strategy == "manual_origin":
                self._mill.home_manual_origin()
            elif strategy == "standard":
                self._mill.home()
            elif strategy == "xy_hard_limits":
                self._mill.home_xy_hard_limits()
            else:
                raise ValueError(f"Unknown homing strategy: {strategy!r}")
        except (MillConnectionError, StatusReturnError) as exc:
            self.logger.error("Error homing gantry: %s", exc)
            raise

    def home_xy(self) -> None:
        """Home X/Y using the hard-limits strategy, ignoring config."""
        if self._offline:
            return
        assert self._mill is not None
        try:
            self._mill.home_xy_hard_limits()
        except (MillConnectionError, StatusReturnError) as exc:
            self.logger.error("Error homing gantry: %s", exc)
            raise

    def move_to(
        self,
        x: float,
        y: float,
        z: float,
        travel_z: Optional[float] = None,
    ) -> None:
        """Move to absolute user-space coordinates.

        ``travel_z`` (user space), if given, becomes the Z during XY
        travel: the gantry lifts/lowers to it at the current XY before
        moving XY, then descends/ascends to the target Z. This is how
        higher layers (Board, protocol commands) express "travel above
        this labware" without the mill baking in a machine-wide retract.
        """
        if self._offline:
            if travel_z is not None:
                # Dry runs only record the final tip pose. Log the transit
                # height so offline protocol validation can still reason
                # about approach path (e.g. assert it stays above labware).
                self.logger.debug(
                    "Offline move to (%s, %s, %s) via travel_z=%s", x, y, z, travel_z,
                )
            self._offline_coords = {"x": x, "y": y, "z": z}
            return
        assert self._mill is not None
        try:
            machine_x, machine_y, machine_z = to_machine_coordinates(x, y, z)
            machine_travel_z = (
                to_machine_coordinates(0.0, 0.0, travel_z)[2]
                if travel_z is not None
                else None
            )
            self._mill.move_to_position(
                x_coordinate=machine_x,
                y_coordinate=machine_y,
                z_coordinate=machine_z,
                travel_z=machine_travel_z,
            )
        except (
            MillConnectionError,
            StatusReturnError,
            CommandExecutionError,
            ValueError,
        ) as exc:
            self.logger.error(
                "Error moving gantry to (%s, %s, %s): %s", x, y, z, exc
            )
            raise

    def jog(
        self,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        feed_rate: float = 2000,
    ) -> None:
        """Jog by a relative user-space offset."""
        if self._offline:
            self._offline_coords = {
                "x": self._offline_coords["x"] + x,
                "y": self._offline_coords["y"] + y,
                "z": self._offline_coords["z"] + z,
            }
            return
        assert self._mill is not None
        try:
            self._mill.jog(x=-x, y=-y, z=-z, feed_rate=feed_rate)
        except (MillConnectionError, CommandExecutionError) as exc:
            self.logger.error("Jog error: %s", exc)
            raise

    def jog_cancel(self) -> None:
        """Cancel any in-progress jog motion immediately."""
        if self._offline:
            return
        assert self._mill is not None
        try:
            self._mill.jog_cancel()
        except (MillConnectionError, CommandExecutionError) as exc:
            self.logger.error("Jog cancel error: %s", exc)
            raise

    def soft_reset(self) -> None:
        """Send a GRBL soft reset (Ctrl-X) to the controller."""
        if self._offline:
            return
        assert self._mill is not None
        try:
            self._mill.soft_reset()
        except Exception as exc:
            self.logger.error("Soft reset error: %s", exc)
            raise

    def unlock(self) -> None:
        """Send GRBL unlock command ($X) to clear alarm state."""
        if self._offline:
            return
        assert self._mill is not None
        try:
            self._mill.reset()
        except (MillConnectionError, CommandExecutionError) as exc:
            self.logger.error("Unlock error: %s", exc)
            raise

    def reset_and_unlock(self) -> None:
        """Soft reset + unlock in a single serial sequence."""
        if self._offline:
            return
        assert self._mill is not None
        try:
            self._mill.soft_reset_and_unlock()
        except (MillConnectionError, CommandExecutionError) as exc:
            self.logger.error("Reset and unlock error: %s", exc)
            raise

    def get_status(self) -> str:
        """Return the current status string translated to user-space coords."""
        if self._offline:
            return "Idle"
        assert self._mill is not None
        try:
            return translate_status_string(self._mill.current_status())
        except (MillConnectionError, StatusReturnError) as exc:
            self.logger.error("Error getting status: %s", exc)
            return "StatusQueryFailed"

    def stop(self) -> None:
        """Immediately stop all gantry motion (GRBL feed hold)."""
        if self._offline:
            return
        assert self._mill is not None
        try:
            self._mill.stop()
        except (MillConnectionError, CommandExecutionError) as exc:
            self.logger.error("Error stopping gantry: %s", exc)
            raise

    def get_coordinates(self) -> Dict[str, float]:
        """Return current user-space coordinates as a dict."""
        if self._offline:
            return dict(self._offline_coords)
        assert self._mill is not None
        coords = self._mill.current_coordinates()
        x_user, y_user, z_user = to_user_coordinates(coords.x, coords.y, coords.z)
        return {"x": x_user, "y": y_user, "z": z_user}

    def get_position_info(self) -> Dict[str, Any]:
        """Return coordinates, work position, and last-known status."""
        if self._offline:
            coords = dict(self._offline_coords)
            return {"coords": coords, "work_pos": coords, "status": "Idle"}

        assert self._mill is not None
        coords = self._mill.current_coordinates()
        x_user, y_user, z_user = to_user_coordinates(coords.x, coords.y, coords.z)
        user_coords = {"x": x_user, "y": y_user, "z": z_user}
        status = self._extract_status()
        return {
            "coords": user_coords,
            "work_pos": user_coords,
            "status": status,
        }

    def set_serial_timeout(self, timeout: float) -> None:
        """Set the serial read timeout on the active mill connection."""
        if self._offline:
            return
        assert self._mill is not None
        if self._mill.ser_mill is not None:
            self._mill.ser_mill.timeout = timeout

    def zero_coordinates(self) -> None:
        """Zero the work coordinate system at the current position."""
        if self._offline:
            self._offline_coords = {"x": 0.0, "y": 0.0, "z": 0.0}
            return
        assert self._mill is not None
        try:
            self._mill.execute_command("G92 X0 Y0 Z0")
            self.logger.info("Work coordinates zeroed")
        except (MillConnectionError, CommandExecutionError) as exc:
            self.logger.error("Error zeroing coordinates: %s", exc)
            raise

    def configure_speeds(
        self,
        homing_feed: Optional[float] = None,
        homing_seek: Optional[float] = None,
        max_rate: Optional[float] = None,
        acceleration: Optional[float] = None,
    ) -> None:
        """Apply speed and acceleration overrides to the GRBL controller."""
        if self._offline:
            return
        assert self._mill is not None
        if homing_feed is not None:
            self._mill.set_grbl_setting("24", str(homing_feed))
        if homing_seek is not None:
            self._mill.set_grbl_setting("25", str(homing_seek))
        if max_rate is not None:
            for code in ("110", "111", "112"):
                self._mill.set_grbl_setting(code, str(max_rate))
        if acceleration is not None:
            for code in ("120", "121", "122"):
                self._mill.set_grbl_setting(code, str(acceleration))
        self.logger.info("Speed config applied")

    def _homing_strategy(self) -> str:
        """Extract the configured homing strategy from dict or dataclass config."""
        if isinstance(self.config, dict):
            cnc = self.config.get("cnc", {})
            if isinstance(cnc, dict):
                return cnc.get("homing_strategy", "xy_hard_limits")
        if hasattr(self.config, "homing_strategy"):
            value = getattr(self.config, "homing_strategy")
            return getattr(value, "value", value)
        return "xy_hard_limits"

    def _extract_status(self) -> str:
        """Extract the GRBL state word from the last raw status string."""
        try:
            assert self._mill is not None
            raw = getattr(self._mill, "last_status", "") or ""
            if not raw:
                return "Unknown"
            match = _STATUS_RE.search(raw)
            if match:
                return match.group(1)
            if "alarm" in raw.lower():
                return "Alarm"
            return translate_status_string(raw)
        except (ValueError, AttributeError) as exc:
            self.logger.debug("Failed to extract status: %s", exc)
            return "Unknown"

    def _expected_grbl_settings(self) -> Optional[Dict[str, float]]:
        """Return expected GRBL settings normalized to $-code keys."""
        if isinstance(self.config, dict):
            raw = self.config.get("grbl_settings")
            if not raw:
                return None
            from .yaml_schema import GRBL_FIELD_TO_SETTING

            expected: Dict[str, float] = {}
            for field_name, grbl_code in GRBL_FIELD_TO_SETTING.items():
                value = raw.get(field_name)
                if value is not None:
                    expected[grbl_code] = float(value)
            return expected

        expected = getattr(self.config, "expected_grbl_settings", None)
        return expected or None

    def _validate_grbl_settings(self) -> None:
        """Compare configured GRBL expectations against the connected controller."""
        expected = self._expected_grbl_settings()
        if not expected or self._offline:
            return

        assert self._mill is not None
        live = self._mill.grbl_settings()
        mismatches = []
        for grbl_code, expected_value in expected.items():
            live_raw = live.get(grbl_code)
            if live_raw is None:
                self.logger.warning(
                    "GRBL setting %s not found on controller", grbl_code
                )
                continue
            if abs(float(live_raw) - float(expected_value)) > 0.001:
                mismatches.append((grbl_code, float(expected_value), float(live_raw)))

        if not mismatches:
            self.logger.info("GRBL settings validation passed")
            return

        critical = {"$3", "$23", "$100", "$101", "$102", "$130", "$131", "$132"}
        critical_mismatches = [item for item in mismatches if item[0] in critical]
        for grbl_code, expected_value, live_value in mismatches:
            self.logger.error(
                "GRBL mismatch: %s expected %.3f, controller has %.3f",
                grbl_code,
                expected_value,
                live_value,
            )
        if critical_mismatches:
            details = "; ".join(
                f"{code}: expected {expected_value}, got {live_value}"
                for code, expected_value, live_value in critical_mismatches
            )
            raise MillConnectionError(
                f"Critical GRBL settings mismatch — motion would be wrong. {details}"
            )

    def _check_alarm_state(self) -> None:
        """Log an alarm state after connect without raising."""
        if self._offline:
            return
        assert self._mill is not None
        raw = self._mill.query_raw_status()
        if raw and "Alarm" in raw:
            self.logger.warning(
                "GRBL is in Alarm state after connect. Home to clear. Status: %s",
                raw,
            )
