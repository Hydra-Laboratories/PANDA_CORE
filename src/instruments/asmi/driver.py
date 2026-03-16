import statistics
import time
from typing import Optional

from instruments.base_instrument import BaseInstrument
from instruments.asmi.exceptions import (
    ASMICommandError,
    ASMIConnectionError,
)
from instruments.asmi.models import ASMIStatus, MeasurementResult

_DEFAULT_FORCE_THRESHOLD = -100
_DEFAULT_SENSOR_CHANNELS = [1]


class ASMI(BaseInstrument):
    """Driver for the ASMI force sensor (Vernier GoDirect).

    Connects to a GoDirect force sensor over USB and provides force
    measurements.  All positioning is handled by the gantry via the Board.

    Constructor accepts BaseInstrument fields plus:
        force_threshold: GoDirect device detection threshold (default -100).
        sensor_channels: List of sensor channel indices to enable (default [1]).
    """

    def __init__(
        self,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
        measurement_height: float = 0.0,
        force_threshold: float = _DEFAULT_FORCE_THRESHOLD,
        sensor_channels: Optional[list[int]] = None,
        # Indentation measurement parameters (configurable via board YAML)
        z_target: float = -17.0,
        step_size: float = 0.01,
        force_limit: float = 15.0,
        well_top_z: float = -9.0,
        safe_z: float = -50.0,
        baseline_samples: int = 10,
        idle_timeout: float = 10.0,
    ):
        super().__init__(
            name=name, offset_x=offset_x, offset_y=offset_y,
            depth=depth, measurement_height=measurement_height,
        )
        self._force_threshold = force_threshold
        self._sensor_channels = sensor_channels or list(_DEFAULT_SENSOR_CHANNELS)
        self._z_target = z_target
        self._step_size = step_size
        self._force_limit = force_limit
        self._well_top_z = well_top_z
        self._safe_z = safe_z
        self._baseline_samples = baseline_samples
        self._idle_timeout = idle_timeout
        self._godirect = None
        self._device = None
        self._sensor = None

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        try:
            from godirect import GoDirect
        except ImportError as exc:
            raise ASMIConnectionError(
                "godirect package required: pip install godirect"
            ) from exc

        self._godirect = GoDirect(use_ble=False, use_usb=True)
        device = self._godirect.get_device(threshold=self._force_threshold)
        if device is None:
            raise ASMIConnectionError(
                "No GoDirect force sensor found. Check USB connection."
            )
        if not device.open(auto_start=False):
            raise ASMIConnectionError("Failed to open GoDirect device")

        device.enable_sensors(self._sensor_channels)
        sensors = device.get_enabled_sensors()
        if not sensors:
            device.close()
            raise ASMIConnectionError("No sensors enabled on GoDirect device")

        self._device = device
        self._sensor = sensors[0]
        self.logger.info(
            "Connected to force sensor: %s", self._sensor.sensor_description
        )

    def disconnect(self) -> None:
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
            self._sensor = None
        if self._godirect is not None:
            try:
                self._godirect.quit()
            except Exception:
                pass
            self._godirect = None
        self.logger.info("ASMI force sensor disconnected")

    def health_check(self) -> bool:
        if self._device is None or self._sensor is None:
            return False
        try:
            self.measure()
            return True
        except ASMICommandError:
            return False

    # ── ASMI-specific commands ────────────────────────────────────────────

    def measure(self, n_samples: int = 1) -> MeasurementResult:
        """Take one or more force readings and return the result.

        Args:
            n_samples: Number of readings to collect. When greater than 1
                the result includes mean and standard deviation across all
                samples.
        """
        if self._device is None or self._sensor is None:
            raise ASMICommandError("Force sensor not connected")

        readings: list[float] = []
        for _ in range(n_samples):
            self._device.start()
            value = 0.0
            if self._device.read():
                value = self._sensor.values[0]
                self._sensor.clear()
            self._device.stop()
            readings.append(value)

        mean = statistics.mean(readings)
        std = statistics.stdev(readings) if len(readings) > 1 else 0.0
        return MeasurementResult(
            readings=tuple(readings),
            mean_n=mean,
            std_n=std,
            timestamp=time.time(),
        )

    def get_status(self) -> ASMIStatus:
        """Return a snapshot of the sensor state."""
        description = None
        if self._sensor is not None:
            try:
                description = self._sensor.sensor_description
            except Exception:
                pass
        return ASMIStatus(
            is_connected=self._device is not None and self._sensor is not None,
            sensor_description=description,
        )

    # ── Convenience methods ───────────────────────────────────────────────

    def get_force_reading(self) -> float:
        """Take a single force reading and return the value in Newtons."""
        result = self.measure(n_samples=1)
        return result.mean_n

    def get_baseline_force(self, samples: int = 10) -> tuple[float, float]:
        """Collect multiple force readings and return (mean, std) in Newtons."""
        result = self.measure(n_samples=samples)
        return (result.mean_n, result.std_n)

    def is_connected(self) -> bool:
        """Check if the force sensor is connected and operational."""
        return self._device is not None and self._sensor is not None

    # ── Indentation measurement ───────────────────────────────────────────

    def _wait_for_idle(self, gantry) -> bool:
        start = time.time()
        while time.time() - start < self._idle_timeout:
            if "Idle" in gantry.get_status():
                return True
            time.sleep(0.02)
        return False

    def _move_z(self, gantry, x, y, z):
        gantry.move_to(x, y, z)
        self._wait_for_idle(gantry)

    def indentation(self, gantry) -> dict:
        """Perform step-by-step indentation at the current XY position.

        The scan command positions the gantry at the well before calling
        this method. Indentation then:
        1. Lowers to well_top_z
        2. Takes baseline force readings
        3. Steps Z toward z_target, reading force at each step
        4. Stops on force_limit or z_target
        5. Returns to safe_z

        Args:
            gantry: Gantry instance for Z movement.

        Returns:
            Dict with keys: measurements, baseline_avg, baseline_std,
            force_exceeded, data_points.
        """
        coords = gantry.get_coordinates()
        cur_x, cur_y = coords["x"], coords["y"]

        # Lower to measurement start
        self._move_z(gantry, cur_x, cur_y, self._well_top_z)

        # Baseline
        baseline_avg, baseline_std = self.get_baseline_force(
            samples=self._baseline_samples
        )
        self.logger.info(
            "Baseline: %.3f +/- %.3f N", baseline_avg, baseline_std
        )

        measurements = []
        force_exceeded = False

        # Step-by-step indentation
        while True:
            coords = gantry.get_coordinates()
            current_z = coords["z"]
            if current_z <= self._z_target:
                self.logger.info("Reached z_target %.3f mm", self._z_target)
                break
            next_z = current_z - self._step_size
            self._move_z(gantry, cur_x, cur_y, next_z)

            coords = gantry.get_coordinates()
            force = self.get_force_reading()
            corrected = force - baseline_avg
            measurements.append({
                "timestamp": time.time(),
                "z_mm": coords["z"],
                "raw_force_n": force,
                "corrected_force_n": corrected,
            })

            if len(measurements) % 10 == 0:
                self.logger.info(
                    "Step #%d: Z=%.3f mm, F=%.3f N, dF=%.3f N",
                    len(measurements), coords["z"], force, corrected,
                )

            if abs(corrected) > self._force_limit:
                self.logger.info(
                    "Force limit exceeded: %.3f N > %.1f N",
                    corrected, self._force_limit,
                )
                force_exceeded = True
                break

        # Return to safe height
        self._move_z(gantry, cur_x, cur_y, self._safe_z)

        return {
            "measurements": measurements,
            "baseline_avg": baseline_avg,
            "baseline_std": baseline_std,
            "force_exceeded": force_exceeded,
            "data_points": len(measurements),
        }
