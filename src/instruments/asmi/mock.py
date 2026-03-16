import time
from typing import Optional

from instruments.base_instrument import BaseInstrument
from instruments.asmi.models import ASMIStatus, MeasurementResult


class MockASMI(BaseInstrument):
    """In-memory mock of the ASMI force sensor for testing."""

    def __init__(
        self,
        default_force: float = 0.0,
        name: Optional[str] = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        depth: float = 0.0,
        measurement_height: float = 0.0,
    ):
        super().__init__(
            name=name, offset_x=offset_x, offset_y=offset_y,
            depth=depth, measurement_height=measurement_height,
        )
        self._connected = False
        self._default_force = default_force
        self.command_history: list[str] = []

    # ── BaseInstrument interface ──────────────────────────────────────────

    def connect(self) -> None:
        self._connected = True
        self.logger.info("MockASMI connected")

    def disconnect(self) -> None:
        self._connected = False
        self.logger.info("MockASMI disconnected")

    def health_check(self) -> bool:
        return self._connected

    # ── ASMI-specific commands ────────────────────────────────────────────

    def measure(self, n_samples: int = 1) -> MeasurementResult:
        self.command_history.append(f"measure n_samples={n_samples}")
        readings = tuple(self._default_force for _ in range(n_samples))
        return MeasurementResult(
            readings=readings,
            mean_n=self._default_force,
            std_n=0.0,
            timestamp=time.time(),
        )

    def get_status(self) -> ASMIStatus:
        self.command_history.append("get_status")
        return ASMIStatus(
            is_connected=self._connected,
            sensor_description="MockSensor" if self._connected else None,
        )

    # ── Convenience methods (match real ASMI driver API) ──────────────────

    def get_force_reading(self) -> float:
        result = self.measure(n_samples=1)
        return result.mean_n

    def get_baseline_force(self, samples: int = 10) -> tuple[float, float]:
        result = self.measure(n_samples=samples)
        return (result.mean_n, result.std_n)

    def is_connected(self) -> bool:
        return self._connected
