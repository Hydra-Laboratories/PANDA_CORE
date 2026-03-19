import time
from typing import Optional

import serial

from instruments.base_instrument import BaseInstrument
from instruments.uv_curing.exceptions import (
    UVCuringCommandError,
    UVCuringConnectionError,
    UVCuringTimeoutError,
)
from instruments.uv_curing.models import CureResult, UVCuringStatus


class UVCuring(BaseInstrument):
    """Driver for the UV LED curing system.

    Controls a UV LED array via serial for photocuring experiments.
    The gantry handles Z positioning; this driver handles only the
    UV light (intensity, on/off timing).

    Pass ``offline=True`` for dry runs — no serial connection, all
    commands return synthetic results.

    Board YAML fields:
        port: Serial port for the UV LED controller.
        baud_rate: Serial baud rate (default 115200).
        default_intensity: Default UV intensity in % (default 100).
        default_exposure_time: Default exposure time in seconds (default 1.0).
        default_z: Default Z position for curing in mm (default -21.2).
        command_timeout: Serial command timeout in seconds (default 5.0).
    """

    def __init__(
        self,
        port: str = "",
        baud_rate: int = 115200,
        default_intensity: float = 100.0,
        default_exposure_time: float = 1.0,
        default_z: float = -21.2,
        command_timeout: float = 5.0,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
        measurement_height: float = 0.0,
        offline: bool = False,
        **kwargs,
    ):
        super().__init__(
            name=name, offset_x=offset_x, offset_y=offset_y,
            depth=depth, measurement_height=measurement_height,
            offline=offline,
        )
        self._port = port
        self._baud_rate = baud_rate
        self._default_intensity = default_intensity
        self._default_exposure_time = default_exposure_time
        self._default_z = default_z
        self._command_timeout = command_timeout
        self._serial: Optional[serial.Serial] = None
        self._led_on = False
        self._current_intensity = 0.0

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        if self._offline:
            self.logger.info("UVCuring connected (offline)")
            return
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baud_rate,
                timeout=self._command_timeout,
            )
        except serial.SerialException as exc:
            raise UVCuringConnectionError(
                f"Cannot open UV serial port {self._port}: {exc}"
            ) from exc
        time.sleep(1.0)
        self.logger.info("Connected to UV LED controller on %s", self._port)

    def disconnect(self) -> None:
        if self._led_on:
            try:
                self.led_off()
            except Exception:
                self._led_on = False
        if self._offline:
            self.logger.info("UVCuring disconnected (offline)")
            return
        if self._serial is not None:
            try:
                self._serial.close()
            except serial.SerialException:
                pass
            self._serial = None
        self.logger.info("UV LED controller disconnected")

    def health_check(self) -> bool:
        if self._offline:
            return True
        return self._serial is not None and self._serial.is_open

    # ── UV-specific commands ──────────────────────────────────────────────

    def set_intensity(self, percent: float) -> None:
        """Set UV LED intensity (0-100%)."""
        percent = max(0.0, min(100.0, percent))
        if self._offline:
            self._current_intensity = percent
            return
        self._send_command(f"INTENSITY {percent:.1f}")
        self._current_intensity = percent
        self.logger.info("UV intensity set to %.1f%%", percent)

    def led_on(self) -> None:
        """Turn UV LED on at the current intensity."""
        if self._offline:
            self._led_on = True
            return
        self._send_command("LED ON")
        self._led_on = True
        self.logger.info("UV LED on")

    def led_off(self) -> None:
        """Turn UV LED off."""
        if self._offline:
            self._led_on = False
            return
        self._send_command("LED OFF")
        self._led_on = False
        self.logger.info("UV LED off")

    def cure(
        self,
        intensity: Optional[float] = None,
        exposure_time: Optional[float] = None,
        well_id: str = "",
    ) -> CureResult:
        """Execute a timed UV cure cycle.

        Sets intensity, turns LED on, waits for exposure_time, turns off.

        Args:
            intensity: UV intensity in % (uses default if None).
            exposure_time: Exposure duration in seconds (uses default if None).
            well_id: Well identifier for metadata.

        Returns:
            CureResult with exposure parameters and timestamp.
        """
        intensity = intensity if intensity is not None else self._default_intensity
        exposure_time = exposure_time if exposure_time is not None else self._default_exposure_time

        if intensity <= 0:
            raise UVCuringCommandError("Intensity must be > 0%")
        if exposure_time <= 0:
            raise UVCuringCommandError("Exposure time must be > 0s")

        self.set_intensity(intensity)
        self.led_on()

        if not self._offline:
            time.sleep(exposure_time)
        self.led_off()

        self.logger.info(
            "Cured well %s: %.1f%% for %.1fs",
            well_id, intensity, exposure_time,
        )

        return CureResult(
            well_id=well_id,
            intensity_percent=intensity,
            exposure_time_s=exposure_time,
            z_mm=self._default_z,
            timestamp=time.time(),
        )

    def measure(self, **kwargs) -> CureResult:
        """Protocol-compatible alias for cure().

        Called by the scan command: ``method: cure`` or ``method: measure``.
        """
        return self.cure(**kwargs)

    def get_status(self) -> UVCuringStatus:
        """Return a snapshot of the UV system state."""
        return UVCuringStatus(
            is_connected=self.health_check(),
            led_on=self._led_on,
            current_intensity=self._current_intensity,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _send_command(self, command: str) -> str:
        """Send a command to the UV controller and return the response."""
        if self._serial is None or not self._serial.is_open:
            raise UVCuringCommandError("Not connected to UV controller")
        try:
            self._serial.write((command + "\n").encode())
            self._serial.flush()
            response = self._serial.readline().decode().strip()
            if not response:
                raise UVCuringTimeoutError(
                    f"No response to '{command}' within {self._command_timeout}s"
                )
            if response.startswith("ERR"):
                raise UVCuringCommandError(
                    f"UV command '{command}' failed: {response}"
                )
            return response
        except serial.SerialException as exc:
            raise UVCuringCommandError(
                f"Serial error sending '{command}': {exc}"
            ) from exc
