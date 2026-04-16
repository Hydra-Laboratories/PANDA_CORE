from __future__ import annotations

import math
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
_STEP_COUNT_SAFETY_MARGIN = 10


def _step_count_bound(z_upper: float, z_lower: float, step_size: float) -> int:
    """Upper bound on steps needed to cross [z_lower, z_upper] at step_size.

    Ceil-based so that a non-integer number of steps still reaches the
    clamped endpoint. Used as a loop-iteration cap to guarantee termination
    if hardware stalls or rounding otherwise prevents the geometric exit
    condition from firing, and — in offline mode — as the actual step count.
    """
    if step_size <= 0:
        raise ValueError(f"step_size must be positive, got {step_size}")
    span = abs(z_upper - z_lower)
    raw_steps = math.ceil(span / step_size) if span > 0 else 0
    return raw_steps + _STEP_COUNT_SAFETY_MARGIN


class ASMI(BaseInstrument):
    """Driver for the ASMI force sensor (Vernier GoDirect).

    Connects to a GoDirect force sensor over USB and provides force
    measurements.  All positioning is handled by the gantry via the Board.

    Pass ``offline=True`` for dry runs and testing — no USB connection,
    all readings return ``default_force``.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
        measurement_height: float = 0.0,
        safe_approach_height: Optional[float] = None,
        offline: bool = False,  # passed through to BaseInstrument
        default_force: float = 0.0,
        force_threshold: float = _DEFAULT_FORCE_THRESHOLD,
        sensor_channels: Optional[list[int]] = None,
        z_target: float = -17.0,
        step_size: float = 0.01,
        force_limit: float = 15.0,
        baseline_samples: int = 10,
        idle_timeout: float = 10.0,
        well_top_z: float | None = None,
        safe_z: float | None = None,
    ):
        super().__init__(
            name=name, offset_x=offset_x, offset_y=offset_y,
            depth=depth, measurement_height=measurement_height,
            safe_approach_height=safe_approach_height,
            offline=offline,
        )
        self._default_force = default_force
        self._force_threshold = force_threshold
        self._sensor_channels = sensor_channels or list(_DEFAULT_SENSOR_CHANNELS)
        self._z_target = z_target
        self._step_size = step_size
        self._force_limit = force_limit
        self._baseline_samples = baseline_samples
        self._idle_timeout = idle_timeout
        self._well_top_z = well_top_z
        self._safe_z = safe_z
        self._godirect = None
        self._device = None
        self._sensor = None

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        if self._offline:
            self.logger.info("ASMI connected (offline)")
            return
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
        if self._offline:
            self.logger.info("ASMI disconnected (offline)")
            return
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
        if self._offline:
            return True
        if self._device is None or self._sensor is None:
            return False
        try:
            self.measure()
            return True
        except ASMICommandError:
            return False

    # ── ASMI-specific commands ────────────────────────────────────────────

    def measure(self, n_samples: int = 1) -> MeasurementResult:
        """Take one or more force readings and return the result."""
        if self._offline:
            readings = tuple(self._default_force for _ in range(n_samples))
            return MeasurementResult(
                readings=readings,
                mean_n=self._default_force,
                std_n=0.0,
                timestamp=time.time(),
            )

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
        if self._offline:
            return ASMIStatus(
                is_connected=True,
                sensor_description="OfflineSensor",
            )
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
        return self.measure(n_samples=1).mean_n

    def get_baseline_force(self, samples: int = 10) -> tuple[float, float]:
        """Collect multiple force readings and return (mean, std) in Newtons."""
        result = self.measure(n_samples=samples)
        return (result.mean_n, result.std_n)

    def is_connected(self) -> bool:
        """Check if the force sensor is connected and operational."""
        if self._offline:
            return True
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

    def indentation(
        self,
        gantry,
        z_limit: float | None = None,
        step_size: float | None = None,
        force_limit: float | None = None,
        measurement_height: float | None = None,
        baseline_samples: int | None = None,
        measure_with_return: bool = False,
    ) -> dict:
        """Perform step-by-step indentation at the current XY position.

        The scan command positions the gantry at the well before calling
        this method. Indentation then:
        1. Lowers to measurement_height
        2. Takes baseline force readings
        3. Steps Z toward z_limit, reading force at each step
        4. Stops on force_limit or z_limit

        Args:
            gantry:             Gantry instance for Z movement.
            z_limit:            Z position to step down to (overrides instance default).
            step_size:          Z increment per step in mm (overrides instance default).
            force_limit:        Stop when corrected force exceeds this in N (overrides instance default).
            measurement_height: Z to descend to before starting (overrides instance default).
            baseline_samples:   Number of baseline force readings (overrides instance default).
            measure_with_return:
                                If True, after descent also step Z back up to
                                ``measurement_height`` and record each upward sample.
                                Every sample is tagged with ``direction`` ("down"
                                on descent, "up" on return).

        Returns:
            Dict with keys: measurements, baseline_avg, baseline_std,
            force_exceeded, data_points, measure_with_return. Every entry in
            ``measurements`` includes a ``direction`` field.
        """
        # Allow protocol method_kwargs to override instance defaults
        _z_target = z_limit if z_limit is not None else self._z_target
        _step_size = step_size if step_size is not None else self._step_size
        _force_limit = force_limit if force_limit is not None else self._force_limit
        _well_top_z = measurement_height if measurement_height is not None else (
            self._well_top_z if self._well_top_z is not None else self.measurement_height
        )
        _baseline_samples = baseline_samples if baseline_samples is not None else self._baseline_samples

        if self._offline:
            return self._offline_indentation(
                gantry,
                _z_target,
                _step_size,
                _well_top_z,
                measure_with_return=measure_with_return,
            )

        coords = gantry.get_coordinates()
        cur_x, cur_y = coords["x"], coords["y"]

        self._move_z(gantry, cur_x, cur_y, _well_top_z)

        baseline_avg, baseline_std = self.get_baseline_force(
            samples=_baseline_samples
        )
        self.logger.info(
            "Baseline: %.3f +/- %.3f N", baseline_avg, baseline_std
        )

        measurements = []
        force_exceeded = False
        max_steps = _step_count_bound(_well_top_z, _z_target, _step_size)

        for _ in range(max_steps):
            coords = gantry.get_coordinates()
            current_z = coords["z"]
            if current_z <= _z_target:
                self.logger.info("Reached z_target %.3f mm", _z_target)
                break
            next_z = current_z - _step_size
            self._move_z(gantry, cur_x, cur_y, next_z)

            coords = gantry.get_coordinates()
            force = self.get_force_reading()
            corrected = force - baseline_avg
            measurements.append({
                "timestamp": time.time(),
                "z_mm": coords["z"],
                "raw_force_n": force,
                "corrected_force_n": corrected,
                "direction": "down",
            })

            if len(measurements) % 10 == 0:
                self.logger.info(
                    "Step #%d: Z=%.3f mm, F=%.3f N, dF=%.3f N",
                    len(measurements), coords["z"], force, corrected,
                )

            if abs(corrected) > _force_limit:
                self.logger.info(
                    "Force limit exceeded: %.3f N > %.1f N",
                    corrected, _force_limit,
                )
                force_exceeded = True
                break
        else:
            self.logger.warning(
                "Descent hit iteration cap %d before reaching z_target %.3f",
                max_steps, _z_target,
            )

        if measure_with_return and measurements:
            self.logger.info(
                "Starting return sweep (%d descent samples collected)",
                len(measurements),
            )
            return_cap = _step_count_bound(_well_top_z, _z_target, _step_size)
            for _ in range(return_cap):
                coords = gantry.get_coordinates()
                current_z = coords["z"]
                if current_z >= _well_top_z:
                    break
                next_z = min(current_z + _step_size, _well_top_z)
                self._move_z(gantry, cur_x, cur_y, next_z)
                coords = gantry.get_coordinates()
                # Break if the gantry did not advance — prevents infinite loop
                # on stalled axis. get_coordinates reflects the real position.
                if coords["z"] <= current_z:
                    self.logger.warning(
                        "Return sweep aborted: gantry Z did not advance (%.3f)",
                        current_z,
                    )
                    break
                force = self.get_force_reading()
                corrected = force - baseline_avg
                measurements.append({
                    "timestamp": time.time(),
                    "z_mm": coords["z"],
                    "raw_force_n": force,
                    "corrected_force_n": corrected,
                    "direction": "up",
                })
            else:
                self.logger.warning(
                    "Return sweep hit iteration cap %d before reaching well_top_z %.3f",
                    return_cap, _well_top_z,
                )

        return {
            "measurements": measurements,
            "baseline_avg": baseline_avg,
            "baseline_std": baseline_std,
            "force_exceeded": force_exceeded,
            "data_points": len(measurements),
            "measure_with_return": measure_with_return,
        }

    def _offline_indentation(
        self,
        gantry,
        z_limit,
        step_size,
        measurement_height,
        measure_with_return: bool = False,
    ) -> dict:
        """Fast offline indentation — no idle-wait, synthetic data."""
        coords = gantry.get_coordinates()
        cur_x, cur_y = coords["x"], coords["y"]
        gantry.move_to(cur_x, cur_y, measurement_height)

        # Integer step counting avoids float accumulation drift at loop boundaries.
        n_down = _step_count_bound(measurement_height, z_limit, step_size) - _STEP_COUNT_SAFETY_MARGIN
        measurements = []
        for i in range(1, n_down + 1):
            z = max(measurement_height - i * step_size, z_limit)
            gantry.move_to(cur_x, cur_y, z)
            measurements.append({
                "timestamp": time.time(),
                "z_mm": z,
                "raw_force_n": self._default_force,
                "corrected_force_n": 0.0,
                "direction": "down",
            })
            if z <= z_limit:
                break

        if measure_with_return:
            z_bottom = measurements[-1]["z_mm"] if measurements else measurement_height
            n_up = _step_count_bound(measurement_height, z_bottom, step_size) - _STEP_COUNT_SAFETY_MARGIN
            for i in range(1, n_up + 1):
                z = min(z_bottom + i * step_size, measurement_height)
                gantry.move_to(cur_x, cur_y, z)
                measurements.append({
                    "timestamp": time.time(),
                    "z_mm": z,
                    "raw_force_n": self._default_force,
                    "corrected_force_n": 0.0,
                    "direction": "up",
                })
                if z >= measurement_height:
                    break

        return {
            "measurements": measurements,
            "baseline_avg": self._default_force,
            "baseline_std": 0.0,
            "force_exceeded": False,
            "data_points": len(measurements),
            "measure_with_return": measure_with_return,
        }
